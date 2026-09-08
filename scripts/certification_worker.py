#!/usr/bin/env python3
"""Execute exactly one admitted task under the isolated worker identity."""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout, redirect_stderr
import json
import os
from pathlib import Path
import pwd
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
try:
    from . import certification_tasks as tasks
    from . import certification_sandbox as sandbox
    from . import certify_release as cert
except ImportError:
    import certification_tasks as tasks
    import certification_sandbox as sandbox
    import certify_release as cert


def execute(plan: dict, admission: dict, directory: Path, policy: Path | None) -> dict:
    tasks.validate_manifest(plan)
    tasks.validate_record(plan, admission)
    if admission["kind"] != "admission":
        raise tasks.TaskError("worker requires its exact admitted attempt")
    task = tasks.task_for(plan, admission["task_id"])
    usage = None
    state = "TASK_ERROR"
    evidence = None
    stage = "runtime"
    failure = None
    try:
        binary, version = cert.clean_room.resolve_codex(None)
        if version != f"codex-cli {cert.CODEX_VERSION}" or not cert.runtime.proxy_arguments():
            raise tasks.TaskError("worker runtime differs from the reviewed pin")
        if plan["synthetic"]:
            stage = "installation"
            # Exercise the actual pinned CLI, install, tool call and accounting.
            # Fault selection is controller-owned and cannot be enabled in paid mode.
            raw = cert.clean_room.public_install(
                source=os.environ["PUBLIC_REPOSITORY"], ref=os.environ["PUBLIC_REVISION"],
                expected_root=ROOT, codex_bin=binary, codex_version=version,
                auth_home=directory / "no-auth", live=True, model=cert.MODEL,
                reasoning_effort=cert.EFFORT, timeout=45)
            usage = raw.get("live", {}).get("usage")
            if not raw.get("passed") or not tasks.valid_usage(usage):
                raise tasks.TaskError("synthetic public installation failed")
            if task["id"] == "t002" and admission["attempt"] == 0:
                # A synthetic in-flight worker death. The uploaded admission
                # survives, while this process cannot emit a result.
                os._exit(71)
            if task["case_id"] == "public-install":
                evidence = tasks.clean_evidence(raw, plan)
            else:
                evidence = {"score": 1.0 if task["condition"] == "candidate" else 0.5,
                            "critical_pass": True, "passed": True, "elapsed_seconds": 0.0}
                if task["id"] == "t003":
                    evidence.update(score=0.0, critical_pass=False, passed=False)
            state = "RESULT"
        else:
            stage = "candidate"
            candidate = directory / "candidate"
            cert.prepare_candidate(candidate, plan["request"])
            # The manifest preflight checked policy for this exact candidate.
            # The independent aggregator repeats it before certificate assembly.
            if task["case_id"] == "public-install":
                stage = "installation"
                raw = cert.clean_room.public_install(
                    source=cert.REPOSITORY, ref=plan["request"]["candidate_sha"], expected_root=candidate,
                    codex_bin=binary, codex_version=version, auth_home=directory / "no-auth",
                    live=True, model=cert.MODEL, reasoning_effort=cert.EFFORT, timeout=cert.TASK_TIMEOUT)
                usage = raw.get("live", {}).get("usage")
                evidence = tasks.clean_evidence(raw, plan)
                state = "RESULT" if tasks.valid_usage(usage) else "TASK_ERROR"
            else:
                stage = "evaluation"
                suite = cert.behavioral.read_json(cert.behavioral.DEFAULT_SUITE)
                case = next(case for case in suite["cases"] if case["id"] == task["case_id"])
                with cert.candidate_source(candidate):
                    released = cert.behavioral.resolve_release_baseline(
                        plan["request"]["baseline_sha"], directory / "released")
                    source = {"control": None, "released": Path(released["skills"]),
                              "candidate": cert.behavioral.SKILLS}[task["condition"]]
                    raw = cert.behavioral.run_condition(
                        case=case, condition=task["condition"], attempt=task["trial"],
                        out_dir=directory / "raw", codex_bin=binary, codex_version=version,
                        model=cert.MODEL, reasoning_effort=cert.EFFORT, timeout=cert.TASK_TIMEOUT,
                        keep_workspace=False, project_repo=None, skills_source=source, condition_identity=None)
                    # Retain reported usage even when the task or grade fails.
                    usage = raw.get("events", {}).get("usage")
                    if raw["exit_code"] == 0 and tasks.valid_usage(usage):
                        evidence = {"score": raw["grade"]["effective_score"],
                                    "critical_pass": raw["grade"]["critical_pass"],
                                    "passed": raw["grade"]["passed"],
                                    "elapsed_seconds": raw["elapsed_seconds"]}
                        state = "RESULT"
    except Exception as exc:
        # No arbitrary exception strings, private paths or model output enter
        # public evidence. A worker exception is never a retry-for-a-better-grade.
        state, evidence = "TASK_ERROR", None
        category = type(exc).__name__
        if category not in {"TaskError", "CleanRoomError", "ControllerError", "EvalError",
                            "PermissionError", "FileNotFoundError", "TimeoutExpired", "BudgetError"}:
            category = "unexpected"
        failure = {"stage": stage, "category": category}
    if not tasks.valid_usage(usage):
        usage = None
    if state != "RESULT":
        evidence = failure
    result = tasks.record(plan, task["id"], admission["attempt"], "result",
                          state=state, usage=usage, evidence=evidence)
    tasks.validate_record(plan, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--admission", type=Path, required=True)
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != "linux" or os.getuid() != pwd.getpwnam(sandbox.WORKER_USER).pw_uid:
        raise SystemExit("worker must run as the isolated Linux user")
    plan = json.loads(args.manifest.read_text())
    admission = json.loads(args.admission.read_text())
    with tempfile.TemporaryDirectory(prefix="task-") as directory:
        with open(Path(directory) / "private.log", "w") as stream, redirect_stdout(stream), redirect_stderr(stream):
            result = execute(plan, admission, Path(directory), args.policy)
    temporary = args.out.with_suffix(".pending")
    temporary.write_text(json.dumps(result, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
