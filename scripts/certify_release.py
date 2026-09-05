#!/usr/bin/env python3
"""Maintainer-dispatched certification using the independently pinned controller.

Run with python -I. Candidate files are data; evaluators, fixtures, schemas,
thresholds, and certificate assembly always come from this controller checkout.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager, redirect_stdout
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
from typing import Any, Iterator
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import behavioral_eval as behavioral
import clean_room_install as clean_room
import codex_runtime as runtime
import release_controller as controller
import release_gate as gate

REPOSITORY = "cyyapye/tugling"
MODEL = "gpt-5.4-mini"
EFFORT = "medium"
CODEX_VERSION = "0.153.4"
TASK_TIMEOUT = 180
MAX_CERTIFICATE_BYTES = 256 * 1024


class CertificationError(RuntimeError):
    pass


def positive_integer(value: str, ceiling: int) -> int:
    if not re.fullmatch(r"[1-9][0-9]{0,9}", value) or int(value) > ceiling:
        raise CertificationError("missing, malformed, or excessive token limit")
    return int(value)


def authorize(env: dict[str, str]) -> dict[str, Any]:
    if (env.get("GITHUB_REPOSITORY") != REPOSITORY
            or env.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or env.get("GITHUB_RUN_ATTEMPT") != "1"
            or env.get("CERTIFICATION_ENABLED") != "true"
            or env.get("APPROVE_PAID_RUN") != "true"):
        raise CertificationError("certification requires an enabled, newly approved maintainer dispatch")
    pin = env.get("CONTROLLER_SHA", "")
    if not controller.SHA.fullmatch(pin) or env.get("WORKFLOW_SHA") != pin:
        raise CertificationError("workflow is not the separately approved certification controller")
    if (env.get("GITHUB_SHA") != pin
            or not controller.CONTROLLER_TAG.fullmatch(env.get("GITHUB_REF_NAME", ""))
            or env.get("GITHUB_REF") != f"refs/tags/{env.get('GITHUB_REF_NAME')}"):
        raise CertificationError("certification must use the approved controller tag before spending")
    candidate, baseline = env.get("CANDIDATE_SHA", ""), env.get("BASELINE_SHA", "")
    if not controller.SHA.fullmatch(candidate) or not controller.SHA.fullmatch(baseline):
        raise CertificationError("candidate and baseline must be full lowercase commit SHAs")
    limits = {}
    for kind, ceiling in (("INPUT", 100_000_000), ("OUTPUT", 10_000_000)):
        configured = positive_integer(env.get(f"MAX_{kind}_TOKENS", ""), ceiling)
        requested = positive_integer(env.get(f"APPROVED_{kind}_TOKENS", ""), configured)
        limits[f"{kind.lower()}_limit"] = requested
    run_id = env.get("GITHUB_RUN_ID", "")
    if not re.fullmatch(r"[1-9][0-9]{0,19}", run_id):
        raise CertificationError("invalid GitHub run identity")
    return {"repository": REPOSITORY, "controller_sha": pin, "candidate_sha": candidate,
            "baseline_sha": baseline, "run_id": run_id, "run_attempt": 1, **limits}


def require_successful_verify(candidate: str) -> None:
    url = (f"https://api.github.com/repos/{REPOSITORY}/actions/workflows/verify.yml/runs"
           f"?event=push&head_sha={candidate}&per_page=1")
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "tugling-certification"}
    if os.environ.get("GH_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    with urlopen(Request(url, headers=headers), timeout=30) as response:
        runs = json.load(response).get("workflow_runs", [])
    if (not runs or runs[0].get("head_sha") != candidate
            or runs[0].get("status") != "completed" or runs[0].get("conclusion") != "success"):
        raise CertificationError("latest push Verify run for this exact candidate has not passed")


def require_fresh_refs(repository: Path, request: dict[str, Any]) -> None:
    refs = controller.remote_refs(repository, "0.0.0", controller.git_env())
    if (refs.get("refs/heads/main") != request["candidate_sha"]
            or refs.get("refs/heads/stable") != request["baseline_sha"]):
        raise CertificationError("main or stable moved; review a fresh dispatch")


def prepare_candidate(destination: Path, request: dict[str, Any], *,
                      remote: str = controller.REMOTE) -> dict[str, Any]:
    destination.mkdir()
    controller.git(destination, "init", "--template=", ".")
    controller.git(destination, "remote", "add", "origin", remote)
    controller.git(destination, "fetch", "--no-tags", "origin", request["controller_sha"],
                   "refs/heads/main:refs/remotes/origin/main",
                   "refs/heads/stable:refs/remotes/origin/stable")
    require_fresh_refs(destination, request)
    candidate, baseline = request["candidate_sha"], request["baseline_sha"]
    controller.require_reviewed_ruler(destination, request["controller_sha"], candidate)
    controller.git(destination, "merge-base", "--is-ancestor", request["controller_sha"], candidate)
    controller.git(destination, "merge-base", "--is-ancestor", baseline, candidate)
    # Reject symlinks/submodules before checkout or any recursive package scan.
    for revision in {candidate, baseline}:
        entries = controller.tree(destination, revision)
        if len(entries) > controller.MAX_DATA_FILES:
            raise CertificationError("candidate or baseline exceeds the file limit")
        size = 0
        for name, (mode, oid) in entries.items():
            relative = PurePosixPath(name)
            if mode not in {"100644", "100755"} or relative.is_absolute() or ".." in relative.parts:
                raise CertificationError("candidate and baseline must contain only regular files")
            size += int(controller.text_git(destination, "cat-file", "-s", oid))
            if size > controller.MAX_DATA_BYTES:
                raise CertificationError("candidate or baseline exceeds the byte limit")
    before = {key: value for key, value in controller.tree(destination, baseline).items()
              if key.startswith("plugins/tugling/")}
    after = {key: value for key, value in controller.tree(destination, candidate).items()
             if key.startswith("plugins/tugling/")}
    controller.git(destination, "checkout", "--detach", candidate)
    plugin = clean_room.package_report(destination)
    with candidate_source(destination), tempfile.TemporaryDirectory(prefix="tugling-baseline-data-") as directory:
        released = behavioral.materialize_plugin_revision(baseline, Path(directory))
        surface = behavioral.plugin_surface_changes(released)
        if surface["hooks_changed"] or surface["permissions_changed"]:
            raise CertificationError("hook or permission changes need a separate release design review")
        if before != after:
            refs = controller.remote_refs(destination, plugin["version"], controller.git_env())
            if (tuple(map(int, plugin["version"].split("."))) <= tuple(map(int, released["version"].split(".")))
                    or f"refs/tags/v{plugin['version']}" in refs):
                raise CertificationError("changed plugin needs a new, unpublished release version before paid evaluation")
    return {"state": "UNCHANGED_PLUGIN" if before == after else "CERTIFICATION_REQUIRED",
            "request": request, "plugin": plugin}


@contextmanager
def candidate_source(root: Path) -> Iterator[None]:
    # ROOT controls Git scans and source identity only. These constants retain
    # their controller paths: DEFAULT_SUITE, FIXTURES, OUTPUT_SCHEMA, RELEASE_MATRIX.
    original = behavioral.ROOT, behavioral.PLUGIN, behavioral.SKILLS
    behavioral.ROOT, behavioral.PLUGIN, behavioral.SKILLS = (
        root, root / "plugins/tugling", root / "plugins/tugling/skills")
    try:
        yield
    finally:
        behavioral.ROOT, behavioral.PLUGIN, behavioral.SKILLS = original


def check_public_policy(candidate: Path, pattern_file: Path) -> None:
    if not pattern_file.is_file() or not 0 < pattern_file.stat().st_size <= 48 * 1024:
        raise CertificationError("configured public-policy patterns are required")
    with candidate_source(candidate):
        policy = behavioral.policy_scan(pattern_file)
        if not policy["configured"] or not policy["passed"] or not behavioral.privacy_scan()["passed"]:
            raise CertificationError("candidate failed the configured public-policy or privacy scan")


def certify(candidate: Path, request: dict[str, Any], pattern_file: Path,
            output: Path, private: Path, budget: runtime.RunBudget) -> None:
    if not runtime.proxy_arguments():
        raise CertificationError("CI certification requires the official Codex Action proxy")
    codex_bin, version = clean_room.resolve_codex(None)
    if version != f"codex-cli {CODEX_VERSION}":
        raise CertificationError("Codex CLI differs from the reviewed runtime pin")
    # Do the cheap checks before admitting any model work.
    require_fresh_refs(candidate, request)
    check_public_policy(candidate, pattern_file)
    budget.begin()
    clean = clean_room.public_install(
        source=REPOSITORY, ref=request["candidate_sha"], expected_root=candidate,
        codex_bin=codex_bin, codex_version=version, auth_home=private / "no-auth",
        live=True, model=MODEL, reasoning_effort=EFFORT, timeout=TASK_TIMEOUT,
    )
    if clean.get("passed") is not True:
        raise CertificationError("clean-install task failed; certification stops")
    budget.record(clean["live"]["usage"])
    clean_path = private / "clean-room.json"
    gate.write_json(clean_path, clean)
    matrix = gate.validate_matrix()
    with candidate_source(candidate):
        suite = behavioral.read_json(behavioral.DEFAULT_SUITE)
        args = argparse.Namespace(
            codex_bin=codex_bin, out=str(private / "behavioral"), condition="all",
            baseline_ref=request["baseline_sha"], model=MODEL, reasoning_effort=EFFORT,
            attempts=matrix["minimum_attempts"], jobs=1, timeout=TASK_TIMEOUT,
            keep_workspaces=False, policy_pattern_file=str(pattern_file), require_gate="promotion",
        )
        with (private / "harness.log").open("w", encoding="utf-8") as log, redirect_stdout(log):
            _, exit_code = behavioral.run_evaluation(suite=suite, cases=suite["cases"], args=args, budget=budget)
    if exit_code != 0:
        raise CertificationError("full behavioral promotion gate did not pass")
    certificate = gate.assemble_certificate(
        version=gate.plugin_identity(candidate)["version"],
        behavioral_path=private / "behavioral/release-proof.json", clean_room_path=clean_path,
        package_source_root=candidate,
    )
    if certificate["passed"] is not True or budget.tasks != budget.task_limit:
        raise CertificationError("certification did not complete the full reviewed task matrix")
    require_fresh_refs(candidate, request)
    output.mkdir()
    gate.write_json(output / "certificate.json", certificate)
    gate.verify_certificate(path=output / "certificate.json", package_source_root=candidate)
    envelope = {
        "schema_version": 1, "state": "CERTIFIED", **request,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "certificate_sha256": gate.file_digest(output / "certificate.json"),
        "usage": budget.report(), "model": MODEL, "reasoning_effort": EFFORT,
        "codex_version": version,
    }
    gate.write_json(output / "certification.json", envelope)
    validate_artifact(output, request)


def validate_artifact(output: Path, request: dict[str, Any]) -> None:
    names = {"certificate.json", "certification.json"}
    if {path.name for path in output.iterdir()} != names:
        raise CertificationError("unexpected certification artifact files")
    for name in names:
        path = output / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_CERTIFICATE_BYTES:
            raise CertificationError("certification artifact must be bounded regular JSON")
    certificate = gate.read_json(output / "certificate.json")
    envelope = gate.read_json(output / "certification.json")
    envelope_keys = {*request, "schema_version", "state", "created_at", "certificate_sha256",
                     "usage", "model", "reasoning_effort", "codex_version"}
    if (not isinstance(envelope, dict) or set(envelope) != envelope_keys or envelope.get("schema_version") != 1
            or envelope.get("state") != "CERTIFIED"
            or any(envelope.get(key) != value for key, value in request.items())
            or envelope.get("certificate_sha256") != gate.file_digest(output / "certificate.json")
            or envelope.get("model") != MODEL or envelope.get("reasoning_effort") != EFFORT
            or envelope.get("codex_version") != f"codex-cli {CODEX_VERSION}"):
        raise CertificationError("certificate envelope does not match this approved workflow run")
    if (not isinstance(certificate, dict) or certificate.get("passed") is not True
            or certificate.get("behavioral", {}).get("evaluated_revision") != request["candidate_sha"]
            or certificate.get("behavioral", {}).get("released_revision") != request["baseline_sha"]
            or certificate.get("clean_room", {}).get("revision") != request["candidate_sha"]):
        raise CertificationError("certificate does not bind the exact candidate and baseline")
    for section in ("behavioral", "clean_room"):
        if (certificate[section].get("model") != MODEL
                or certificate[section].get("reasoning_effort") != EFFORT):
            raise CertificationError("certificate used different model settings")
    matrix = gate.validate_matrix()
    if (certificate["behavioral"].get("case_ids") != matrix["required_case_ids"]
            or certificate["behavioral"].get("attempts") != matrix["minimum_attempts"]
            or certificate["clean_room"].get("codex_version") != envelope["codex_version"]):
        raise CertificationError("certificate runtime or matrix differs from this controller")
    expected_tasks = len(matrix["required_case_ids"]) * matrix["minimum_attempts"] * 3 + 1
    usage = envelope.get("usage", {})
    if (usage.get("completed_tasks") != expected_tasks or usage.get("task_limit") != expected_tasks
            or usage.get("input_limit") != request["input_limit"]
            or usage.get("output_limit") != request["output_limit"]
            or usage.get("accounting") != "between-tasks-not-hard-billing-cap"
            or usage.get("in_flight_or_unaccounted_task") is not False):
        raise CertificationError("incomplete certification task or budget evidence")
    accounted = runtime.RunBudget(request["input_limit"], request["output_limit"], expected_tasks)
    accounted.record(usage)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "run", "validate-artifact"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--policy-pattern-file")
    parser.add_argument("--proxy-info")
    args = parser.parse_args()
    budget = None
    try:
        request = authorize(dict(os.environ))
        if (controller.text_git(ROOT, "rev-parse", "HEAD") != request["controller_sha"]
                or controller.text_git(ROOT, "status", "--porcelain", "--untracked-files=all")):
            raise CertificationError("controller checkout must be clean and match the approved pin")
        output = Path(args.out).resolve()
        if args.command == "validate-artifact":
            validate_artifact(output, request)
            with tempfile.TemporaryDirectory(prefix="tugling-attestation-check-") as directory:
                candidate = Path(directory) / "candidate"
                prepare_candidate(candidate, request)
                gate.verify_certificate(path=output / "certificate.json", package_source_root=candidate)
            return 0
        require_successful_verify(request["candidate_sha"])
        with tempfile.TemporaryDirectory(prefix="tugling-certification-") as directory:
            private = Path(directory)
            candidate = private / "candidate"
            plan = prepare_candidate(candidate, request)
            if args.command == "plan":
                gate.write_json(output, plan)
                if os.environ.get("GITHUB_OUTPUT"):
                    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
                        stream.write(f"state={plan['state']}\n")
                print(plan["state"])
                return 0
            if plan["state"] != "CERTIFICATION_REQUIRED":
                raise CertificationError("unchanged plugin content needs no new behavioral certificate")
            if not args.policy_pattern_file or not args.proxy_info:
                raise CertificationError("policy patterns and official proxy server info are required")
            info = gate.read_json(Path(args.proxy_info))
            port = info.get("port")
            if type(port) is not int or not 1 <= port <= 65535:
                raise CertificationError("invalid official proxy server info")
            os.environ["TUGLING_CODEX_PROXY_URL"] = f"http://127.0.0.1:{port}/v1"
            os.environ.pop("GH_TOKEN", None)
            matrix = gate.validate_matrix()
            tasks = len(matrix["required_case_ids"]) * matrix["minimum_attempts"] * 3 + 1
            budget = runtime.RunBudget(request["input_limit"], request["output_limit"], tasks)
            certify(candidate, request, Path(args.policy_pattern_file), output, private, budget)
            print("CERTIFIED: sanitized evidence is ready for attestation and human review")
        return 0
    except (CertificationError, controller.ControllerError, runtime.BudgetError, behavioral.EvalError,
            clean_room.CleanRoomError, gate.ReleaseGateError, OSError, ValueError,
            KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        # Model diagnostics, candidate prose, private paths and policy patterns
        # must never escape into a public workflow log or artifact on failure.
        detail = str(exc) if isinstance(exc, (CertificationError, runtime.BudgetError)) else type(exc).__name__
        print(f"CERTIFICATION_FAILED: {detail}; no attested certificate", file=sys.stderr)
        if budget is not None:
            print(json.dumps(budget.report(), sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
