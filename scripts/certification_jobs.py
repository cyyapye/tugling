#!/usr/bin/env python3
"""Trusted GitHub-side checkpoint coordinator; never executes candidate code.

Each serial lane publishes immutable cumulative checkpoints. Loading the latest
checkpoint costs one bounded artifact listing and one download per lane, rather
than downloading every individual result on every task. The manifest and final
certificate are owned by separate jobs. Worker processes receive no GitHub token.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.request import Request, urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
try:
    from . import certification_tasks as tasks
    from . import certify_release as cert
except ImportError:
    import certification_tasks as tasks
    import certify_release as cert

MAX_CHECKPOINT_BYTES = 2 * 1024 * 1024


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(value, sort_keys=True, allow_nan=False) + "\n"
    if len(serialized.encode()) > MAX_CHECKPOINT_BYTES:
        raise tasks.TaskError("checkpoint size limit exceeded")
    temporary = path.with_suffix(".pending")
    temporary.write_text(serialized)
    temporary.replace(path)


def output(key: str, value) -> None:
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as stream:
            stream.write(key + "=" + (json.dumps(value, separators=(",", ":"))
                                      if not isinstance(value, str) else value) + "\n")


def checkpoint(plan: dict, records: list[dict], lane: int) -> dict:
    chosen = [r for r in records if tasks.task_for(plan, r["task_id"])["lane"] == lane]
    return {"schema_version": 1, "manifest_id": plan["id"], "lane": lane,
            "generation": len(chosen), "records": chosen}


def validate_checkpoint(plan: dict, value: dict, lane: int) -> list[dict]:
    if (not isinstance(value, dict) or set(value) != {"schema_version", "manifest_id", "lane", "generation", "records"}
            or value["schema_version"] != 1 or value["manifest_id"] != plan["id"] or value["lane"] != lane
            or not isinstance(value["records"], list) or len(value["records"]) > tasks.MAX_RECORDS
            or value["generation"] != len(value["records"])):
        raise tasks.TaskError("invalid lane checkpoint")
    seen = set()
    for item in value["records"]:
        tasks.validate_record(plan, item)
        identity = (item["task_id"], item["attempt"], item["kind"])
        if identity in seen or tasks.task_for(plan, item["task_id"])["lane"] != lane:
            raise tasks.TaskError("duplicate or cross-lane receipt")
        seen.add(identity)
    tasks.accounting(plan, value["records"], lane)
    tasks.accepted(value["records"])
    return value["records"]


def github_json(path: str) -> dict:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "tugling-certification"}
    if os.environ.get("GH_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    with urlopen(Request("https://api.github.com" + path, headers=headers), timeout=30) as response:
        data = response.read(MAX_CHECKPOINT_BYTES + 1)
    if len(data) > MAX_CHECKPOINT_BYTES:
        raise tasks.TaskError("GitHub response exceeds the coordinator limit")
    return json.loads(data)


def artifact_list(plan: dict) -> list[dict]:
    request = plan["request"]
    prefix = f"/repos/{request['repository']}/actions/runs/{request['run_id']}/artifacts"
    artifacts = []
    # Three attempts per task, admission/result checkpoints and telemetry.
    for page in range(1, 10):
        data = github_json(prefix + f"?per_page=100&page={page}")
        artifacts.extend(data.get("artifacts", []))
        if len(artifacts) >= data.get("total_count", 0):
            break
    else:
        raise tasks.TaskError("artifact count exceeds the reviewed bound")
    for artifact in artifacts:
        validate_provenance(plan, artifact)
    return artifacts


def validate_provenance(plan: dict, artifact: dict) -> None:
    run = artifact.get("workflow_run", {})
    if (str(run.get("id")) != str(plan["request"]["run_id"])
            or run.get("head_sha") != plan["request"]["controller_sha"]
            or type(run.get("repository_id")) is not int
            or run["repository_id"] <= 0
            or run.get("head_repository_id") != run["repository_id"]):
        raise tasks.TaskError("artifact provenance differs from the approved run")


def artifact_files(plan: dict, artifact: dict, names: set[str]) -> dict[str, bytes]:
    import subprocess
    validate_provenance(plan, artifact)
    if artifact.get("expired") or artifact.get("size_in_bytes", 0) > MAX_CHECKPOINT_BYTES:
        raise tasks.TaskError("expired or oversized artifact")
    fetched = subprocess.run(["gh", "api", f"repos/{plan['request']['repository']}/actions/artifacts/{artifact['id']}/zip"],
                             capture_output=True, timeout=45, check=False)
    if fetched.returncode or len(fetched.stdout) > MAX_CHECKPOINT_BYTES:
        raise tasks.TaskError("artifact download failed")
    with zipfile.ZipFile(io.BytesIO(fetched.stdout)) as archive:
        entries = archive.infolist()
        if (len(entries) != len(names) or {entry.filename for entry in entries} != names
                or sum(entry.file_size for entry in entries) > MAX_CHECKPOINT_BYTES
                or any((entry.external_attr >> 16) & 0o170000 == 0o120000 for entry in entries)):
            raise tasks.TaskError("invalid artifact archive")
        return {entry.filename: archive.read(entry) for entry in entries}


def load_remote(plan: dict, lanes: tuple[int, ...] = (0, 1)) -> list[dict]:
    artifacts = artifact_list(plan)
    records = []
    for lane in lanes:
        pattern = re.compile(rf"checkpoint-{plan['id'][:16]}-lane{lane}-([0-9]+)\Z")
        eligible = [(int(match[1]), artifact) for artifact in artifacts
                    if (match := pattern.fullmatch(artifact.get("name", "")))]
        if not eligible:
            continue
        maximum = max(generation for generation, _ in eligible)
        heads = [artifact for generation, artifact in eligible if generation == maximum]
        if len(heads) != 1 or heads[0].get("expired") or heads[0].get("size_in_bytes", 0) > MAX_CHECKPOINT_BYTES:
            raise tasks.TaskError("missing, expired, conflicting or oversized checkpoint")
        artifact = heads[0]
        value = json.loads(artifact_files(plan, artifact, {"checkpoint.json"})["checkpoint.json"])
        if value.get("generation") != maximum:
            raise tasks.TaskError("checkpoint generation differs from artifact identity")
        records.extend(validate_checkpoint(plan, value, lane))
    return records


def reuse_final(plan: dict, destination: Path) -> bool:
    request = plan["request"]
    name = "recovery-diagnostic" if plan["synthetic"] else f"certification-{request['candidate_sha']}-{request['run_id']}-1"
    found = [artifact for artifact in artifact_list(plan) if artifact.get("name") == name]
    if not found:
        return False
    if len(found) != 1:
        raise tasks.TaskError("conflicting final artifacts")
    names = {"recovery-diagnostic.json"} if plan["synthetic"] else {"certificate.json", "certification.json"}
    files = artifact_files(plan, found[0], names)
    destination.mkdir(parents=True, exist_ok=True)
    for filename, contents in files.items():
        (destination / filename).write_bytes(contents)
    if plan["synthetic"]:
        report = json.loads(files["recovery-diagnostic.json"])
        if (report.get("passed") is not True or report.get("synthetic_only") is not True
                or report.get("manifest_id") != plan["id"]
                or report.get("completed_tasks") != len(plan["tasks"])
                or any(report.get(key) is not True for key in ("worker_loss_recovered",
                       "uploaded_result_preserved", "failing_verification_preserved"))
                or report.get("certificate_created") is not False):
            raise tasks.TaskError("saved diagnostic did not pass")
    else:
        cert.validate_artifact(destination, request)
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "candidate"
            cert.prepare_candidate(candidate, request)
            cert.gate.verify_certificate(path=destination / "certificate.json", package_source_root=candidate)
    return True


def emit_checkpoint(plan: dict, records: list[dict], lane: int, destination: Path) -> None:
    value = checkpoint(plan, records, lane)
    validate_checkpoint(plan, value, lane)
    write(destination / "checkpoint.json", value)
    output("artifact", f"checkpoint-{plan['id'][:16]}-lane{lane}-{value['generation']}")


def assemble(plan: dict, records: list[dict], destination: Path, policy: Path | None) -> None:
    accepted = tasks.accepted(records)
    expected = {task["id"] for task in plan["tasks"]}
    usage = tasks.accounting(plan, records)
    complete = set(accepted) == expected
    if plan["synthetic"]:
        # A failing candidate is intentional and must remain failed after recovery.
        failing = accepted.get("t003", {}).get("evidence", {})
        recovered = accepted.get("t002", {}).get("attempt") == 1
        preserved = accepted.get("t006", {}).get("attempt") == 0
        passed = (complete and recovered and preserved and failing.get("passed") is False
                  and all(item["state"] == "RESULT" for item in accepted.values()))
        report = {"synthetic_only": True, "manifest_id": plan["id"], "passed": passed, "completed_tasks": len(accepted),
                  "worker_loss_recovered": recovered, "uploaded_result_preserved": preserved,
                  "failing_verification_preserved": failing.get("passed") is False,
                  "certificate_created": False, "usage_is_synthetic": True,
                  "task_failures": [{"task_id": item["task_id"], "diagnostic": item["evidence"]}
                                    for item in accepted.values() if item["state"] != "RESULT"],
                  "observed_usage": usage}
        write(destination / "recovery-diagnostic.json", report)
        if not passed:
            raise tasks.TaskError("synthetic recovery contract did not pass")
        return
    if usage["unaccounted_attempts"]:
        raise tasks.TaskError("ACCOUNTING_BLOCKED: paid usage is incomplete")
    if not complete or any(r["state"] != "RESULT" for r in accepted.values()):
        raise tasks.TaskError("INCOMPLETE: the exact task matrix has missing or failed executions")
    if policy is None:
        raise tasks.TaskError("policy patterns required for final verification")
    budget = cert.runtime.RunBudget(plan["request"]["input_limit"], plan["request"]["output_limit"], len(expected))
    for item in accepted.values():
        budget.record(item["usage"])
    # Also count any reported, retried infrastructure attempts in admission totals.
    for key in ("input", "output"):
        if usage[f"{key}_tokens"] > plan["request"][f"{key}_limit"]:
            raise tasks.TaskError("BUDGET_BLOCKED: total observed usage exceeds approval")
    with tempfile.TemporaryDirectory(prefix="tugling-aggregate-") as directory:
        private = Path(directory)
        candidate = private / "candidate"
        cert.prepare_candidate(candidate, plan["request"])
        cert.check_public_policy(candidate, policy)
        with cert.candidate_source(candidate):
            baseline = cert.behavioral.resolve_release_baseline(plan["request"]["baseline_sha"], private / "released")
            results = []
            for task in plan["tasks"][1:]:
                item = accepted[task["id"]]
                evidence = item["evidence"]
                results.append({"case_id": task["case_id"], "condition": task["condition"],
                    "attempt": task["trial"], "grade": {"effective_score": evidence["score"],
                    "critical_pass": evidence["critical_pass"], "passed": evidence["passed"]},
                    "events": {"usage": item["usage"]}, "elapsed_seconds": evidence["elapsed_seconds"]})
            suite = cert.behavioral.read_json(cert.behavioral.DEFAULT_SUITE)
            matrix = cert.gate.validate_matrix()
            comparisons = cert.behavioral.comparison_results(results)
            summary = {"run_id": plan["request"]["run_id"], "created_at": datetime.now(timezone.utc).isoformat(),
                "candidate_identity": cert.behavioral.repository_identity(),
                "released_identity": {key: value for key, value in baseline.items() if key not in {"skills", "plugin_root"}},
                "metrics": cert.behavioral.evaluate_gates(suite["gates"], comparisons),
                "codex_version": f"codex-cli {cert.CODEX_VERSION}", "model": cert.MODEL,
                "reasoning_effort": cert.EFFORT, "attempts": matrix["minimum_attempts"],
                "conditions": matrix["conditions"], "case_ids": matrix["required_case_ids"], "jobs": 2}
            proof = cert.behavioral.release_proof(summary=summary, comparisons=comparisons, results=results,
                policy=cert.behavioral.policy_scan(policy), privacy=cert.behavioral.privacy_scan(),
                surface=cert.behavioral.plugin_surface_changes(baseline))
            write(private / "behavioral.json", proof)
        write(private / "clean.json", accepted["t000"]["evidence"])
        certificate = cert.gate.assemble_certificate(version=cert.gate.plugin_identity(candidate)["version"],
            behavioral_path=private / "behavioral.json", clean_room_path=private / "clean.json", package_source_root=candidate)
        if not certificate["passed"]:
            failures = json.dumps(tasks.failed_candidate_checks(plan, records), sort_keys=True)
            raise tasks.TaskError("VERIFICATION_FAILED: the full promotion gate did not pass; candidate_checks=" + failures)
        cert.require_fresh_refs(candidate, plan["request"])
        write(destination / "certificate.json", certificate)
        cert.gate.verify_certificate(path=destination / "certificate.json", package_source_root=candidate)
        envelope = {"schema_version": 1, "state": "CERTIFIED", **plan["request"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "certificate_sha256": cert.gate.file_digest(destination / "certificate.json"),
            "usage": {**budget.report(), **{key: usage[key] for key in ("input_tokens", "output_tokens", "cached_input_tokens")}},
            "model": cert.MODEL, "reasoning_effort": cert.EFFORT, "codex_version": f"codex-cli {cert.CODEX_VERSION}"}
        write(destination / "certification.json", envelope)
        cert.validate_artifact(destination, plan["request"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "admit", "finish", "recover", "aggregate"))
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--task")
    parser.add_argument("--lane", type=int, choices=(0, 1))
    parser.add_argument("--attempt", type=int, default=0)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--worker-result", type=Path)
    parser.add_argument("--policy", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "plan":
            if args.synthetic:
                revision = os.environ["GITHUB_SHA"]
                request = {"repository": cert.REPOSITORY, "controller_sha": revision,
                    "candidate_sha": revision, "baseline_sha": revision,
                    "run_id": os.environ["GITHUB_RUN_ID"], "run_attempt": 1,
                    "input_limit": 5_000_000, "output_limit": 500_000}
                if os.environ.get("GITHUB_RUN_ATTEMPT") != "1":
                    raise tasks.TaskError("diagnostics require a fresh run")
            else:
                request = cert.authorize(dict(os.environ))
                if cert.controller.text_git(ROOT, "rev-parse", "HEAD") != request["controller_sha"]:
                    raise tasks.TaskError("controller checkout differs from approval")
                cert.require_successful_verify(request["candidate_sha"])
                with tempfile.TemporaryDirectory() as directory:
                    candidate = Path(directory) / "candidate"
                    preflight = cert.prepare_candidate(candidate, request)
                    if preflight["state"] != "CERTIFICATION_REQUIRED":
                        output("required", "false")
                        return 0
                    cert.check_public_policy(candidate, args.policy)
            plan = tasks.manifest(request, synthetic=args.synthetic)
            tasks.validate_manifest(plan)
            write(args.out / "manifest.json", plan)
            output("required", "true")
            for lane in (0, 1):
                output(f"lane{lane}", [t["id"] for t in plan["tasks"] if t["lane"] == lane])
            return 0
        plan = json.loads(args.manifest.read_text())
        tasks.validate_manifest(plan)
        if str(plan["request"]["run_id"]) != os.environ.get("GITHUB_RUN_ID"):
            raise tasks.TaskError("cross-run checkpoint reuse is forbidden")
        if not plan["synthetic"] and cert.authorize(dict(os.environ)) != plan["request"]:
            raise tasks.TaskError("approval differs from the immutable manifest")
        if args.command == "admit":
            lane = tasks.task_for(plan, args.task)["lane"]
            if lane != args.lane:
                raise tasks.TaskError("worker belongs to another budget lane")
            records = load_remote(plan, (lane,))
            admission = tasks.admit(plan, records, args.task, args.attempt)
            if admission is None:
                output("execute", "false")
                return 0
            records.append(admission)
            emit_checkpoint(plan, records, lane, args.out)
            write(args.out / "admission.json", admission)
            output("execute", "true")
        elif args.command == "finish":
            value = json.loads((args.out / "checkpoint.json").read_text())
            records = validate_checkpoint(plan, value, args.lane)
            if (args.worker_result and args.worker_result.is_file() and not args.worker_result.is_symlink()
                    and args.worker_result.stat().st_size <= tasks.MAX_RECORD_BYTES):
                result = json.loads(args.worker_result.read_text())
                tasks.validate_record(plan, result)
                if result["task_id"] != args.task or result["attempt"] != args.attempt:
                    raise tasks.TaskError("worker returned another attempt's result")
            else:
                state = "INFRA_ERROR" if plan["synthetic"] and args.task == "t002" else "TASK_ERROR"
                result = tasks.record(plan, args.task, args.attempt, "result", state=state, usage=None, evidence=None)
            records.append(result)
            emit_checkpoint(plan, records, args.lane, args.out)
        elif args.command == "recover":
            records = load_remote(plan)
            pending = tasks.recovery(plan, records, args.attempt)
            for lane in (0, 1):
                output(f"lane{lane}", [task["id"] for task in pending if task["lane"] == lane])
            write(args.out / "recovery.json", {"pending": [task["id"] for task in pending],
                "accepted": len(tasks.accepted(records)), "accounting": tasks.accounting(plan, records)})
        else:
            existing = reuse_final(plan, args.out)
            if not existing:
                assemble(plan, load_remote(plan), args.out, args.policy)
            output("existing", "true" if existing else "false")
        return 0
    except Exception as exc:
        # Known controller categories are public; arbitrary provider errors are not.
        detail = str(exc) if isinstance(exc, tasks.TaskError) else type(exc).__name__
        print("CERTIFICATION_BLOCKED: " + detail, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
