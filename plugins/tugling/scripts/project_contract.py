#!/usr/bin/env python3
"""Validate a project's Tugling adapter without network access or dependencies."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import signal
import stat
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DEFAULT_CONFIG = Path(".tugling/project.json")
VALID_CHANNELS = {"pinned", "stable", "preview"}
VALID_LEARNING_MODES = {"off", "local"}
FLOW_EXECUTION_ENV = "TUGLING_NATIVE_FLOW_ACTIVE"
CANONICAL_EXECUTION_ENV = "TUGLING_CANONICAL_ACTIVE"
REVISION_RE = re.compile(r"[0-9a-f]{40}")
RECEIPT_DIRECTORY = ".tugling/local/verification/managed-v1"
RECEIPT_OWNER = b"Tugling project verification receipts v1\n"
RECEIPT_NAME = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.json")
MAX_RECEIPT_BYTES = 256 * 1024
MAX_RECEIPT_ENTRIES = 1024
DEFAULT_RECEIPT_RETENTION = {"max_age_seconds": 7 * 86400, "max_files": 64,
                             "max_bytes": 16 * 1024 * 1024}
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[oprsu]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
)


class ContractError(RuntimeError):
    """A project adapter is missing, unsafe, or internally inconsistent."""


def run(
    argv: list[str],
    *,
    cwd: Path,
    timeout: int = 120,
    check: bool = False,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "NO_COLOR": "1", **(env or {})},
            stdin=subprocess.DEVNULL,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ContractError(f"command failed to run: {argv!r}: {exc}") from exc
    if check and completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ContractError(f"command failed ({completed.returncode}): {argv!r}: {detail}")
    return completed


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"{path}: {exc}") from exc


def require_object(
    value: Any, *, label: str, keys: set[str], optional: set[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{label} must be an object")
    if not keys.issubset(value) or set(value) - keys - (optional or set()):
        raise ContractError(
            f"{label} fields differ: expected {sorted(keys)}, found {sorted(value)}"
        )
    return value


def committed_file(root: Path, value: Any, *, label: str) -> tuple[Path, str]:
    path, relative = relative_path(root, value, label=label)
    if path.resolve() != path or not path.is_file():
        raise ContractError(f"{label} must be a regular project file without symlinks: {relative}")
    require_tracked(root, relative, label=label)
    return path, relative


def validate_verification_map(root: Path, value: Any) -> dict[str, Any]:
    """Map user flows onto native checks; never start a second runtime harness."""
    path, relative = committed_file(root, value, label="project.verification")
    mapping = require_object(
        read_json(path), label="verification map", keys={"schema_version", "flows"},
        optional={"requirements"},
    )
    assert_no_embedded_secrets(mapping)
    if type(mapping["schema_version"]) is not int or mapping["schema_version"] != 1:
        raise ContractError("verification map schema_version must be 1")
    flows = mapping["flows"]
    if not isinstance(flows, list) or not 1 <= len(flows) <= 32:
        raise ContractError("verification map needs 1 to 32 flows")
    seen: set[str] = set()
    for flow in flows:
        require_object(flow, label="verification flow", keys={
            "id", "description", "argv", "timeout_seconds", "sources", "runtime",
        })
        flow_id = flow["id"]
        if (not isinstance(flow_id, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", flow_id)
                or flow_id in seen):
            raise ContractError("verification flow ids must be unique lowercase names")
        seen.add(flow_id)
        if not isinstance(flow["description"], str) or not flow["description"].strip():
            raise ContractError(f"flow {flow_id}: describe the user behavior being checked")
        argv = flow["argv"]
        if (not isinstance(argv, list) or not argv
                or not all(isinstance(part, str) and part.strip() and "\0" not in part for part in argv)):
            raise ContractError(f"flow {flow_id}: argv must be a non-empty argument array")
        timeout = flow["timeout_seconds"]
        if type(timeout) is not int or not 1 <= timeout <= 3600:
            raise ContractError(f"flow {flow_id}: timeout_seconds must be between 1 and 3600")
        sources = flow["sources"]
        if not isinstance(sources, list) or not sources:
            raise ContractError(f"flow {flow_id}: name the native tests and lifecycle source files")
        for source in sources:
            committed_file(root, source, label=f"flow {flow_id} source")
        runtime = flow["runtime"]
        if runtime is not None:
            require_object(runtime, label=f"flow {flow_id} runtime", keys={
                "owner", "launch", "health", "cleanup",
            })
            if runtime["owner"] != "native-command":
                raise ContractError(f"flow {flow_id}: runtime owner must be native-command")
            for key in ("launch", "health", "cleanup"):
                if not isinstance(runtime[key], str) or not runtime[key].strip():
                    raise ContractError(f"flow {flow_id}: document native runtime {key}")
    requirements = mapping.get("requirements")
    if "requirements" in mapping:
        if not isinstance(requirements, list) or not 1 <= len(requirements) <= 64:
            raise ContractError("verification requirements must contain 1 to 64 project rules")
        requirement_ids: set[str] = set()
        for requirement in requirements:
            require_object(requirement, label="verification requirement", keys={
                "id", "description", "sources", "flows",
            })
            rule_id = requirement["id"]
            if (not isinstance(rule_id, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", rule_id)
                    or rule_id in requirement_ids):
                raise ContractError("verification requirement ids must be unique lowercase names")
            requirement_ids.add(rule_id)
            if not isinstance(requirement["description"], str) or not requirement["description"].strip():
                raise ContractError(f"requirement {rule_id}: describe the accepted project rule")
            sources = requirement["sources"]
            if not isinstance(sources, list) or not sources:
                raise ContractError(f"requirement {rule_id}: name the authoritative policy sources")
            for source in sources:
                committed_file(root, source, label=f"requirement {rule_id} source")
            checks = requirement["flows"]
            if (not isinstance(checks, list) or not checks
                    or not all(isinstance(key, str) and key in seen for key in checks)
                    or len(set(checks)) != len(checks)):
                raise ContractError(f"requirement {rule_id}: map to distinct existing native flows")
    return {"path": relative, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "flows": flows, "requirements": requirements}


def required_flow_ids(mapping: dict[str, Any] | None) -> list[str]:
    if mapping is None or not mapping.get("requirements"):
        raise ContractError("required verification needs project.verification with non-empty requirements")
    required = {flow_id for rule in mapping["requirements"] for flow_id in rule["flows"]}
    # Preserve the map's reviewed execution order and run shared checks once.
    return [flow["id"] for flow in mapping["flows"] if flow["id"] in required]


def flow_execution_ancestry(root: Path, *, canonical: bool = False) -> list[str]:
    """Refuse project cycles while permitting checks of independent fixture repos."""
    try:
        variable = CANONICAL_EXECUTION_ENV if canonical else FLOW_EXECUTION_ENV
        ancestry = json.loads(os.environ.get(variable, "[]"))
    except (ValueError, TypeError) as exc:
        raise ContractError("invalid native flow execution ancestry") from exc
    if (not isinstance(ancestry, list) or len(ancestry) >= 32
            or not all(isinstance(value, str) for value in ancestry)):
        raise ContractError("invalid or excessive native flow execution ancestry")
    project = str(root.resolve())
    if project in ancestry:
        raise ContractError("recursive native flow execution is not allowed; map leaf test commands")
    return [*ancestry, project]


def clean_revision(root: Path) -> str:
    if Path(git_output(root, "rev-parse", "--show-toplevel")).resolve() != root:
        raise ContractError("flow evidence requires the project repository root")
    if git_output(root, "status", "--porcelain", "--untracked-files=all", "--ignore-submodules=none"):
        raise ContractError("flow evidence requires a clean committed project, including untracked files")
    flags = git_output(root, "ls-files", "-v", "-z").split("\0")
    if any(entry and (entry[0].islower() or entry[0] == "S") for entry in flags):
        raise ContractError("flow evidence requires no assume-unchanged or skip-worktree files")
    return git_output(root, "rev-parse", "HEAD")


def stop_process_group(process: subprocess.Popen[Any]) -> bool:
    """Reap only the process group created for this command, including on timeout."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return False
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        process.poll()
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            # Darwin can briefly return EPERM while a signalled group is being
            # reaped. Keep waiting within the same deadline; never infer success.
            pass
        time.sleep(0.05)
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=5)
    return True


def run_flow(root: Path, flow: dict[str, Any]) -> dict[str, Any]:
    started = time.monotonic()
    result: dict[str, Any] = {"id": flow["id"], "argv": flow["argv"], "exit_code": None,
                              "failure": None, "forced_cleanup": False}
    process = None
    try:
        # Stream native output to stderr: JSON stdout stays usable and no logs or secrets
        # are copied into the evidence file. Native commands own service readiness/teardown.
        process = subprocess.Popen(
            flow["argv"], cwd=root, stdin=subprocess.DEVNULL, stdout=sys.stderr,
            stderr=sys.stderr, start_new_session=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "NO_COLOR": "1",
                 FLOW_EXECUTION_ENV: json.dumps(flow_execution_ancestry(root))},
        )
        result["exit_code"] = process.wait(timeout=flow["timeout_seconds"])
        if result["exit_code"] != 0:
            result["failure"] = "command-failed"
    except subprocess.TimeoutExpired:
        result["failure"] = "timeout"
    except KeyboardInterrupt:
        result["failure"] = "interrupted"
    except OSError:
        result["failure"] = "could-not-start"
    finally:
        if process is not None:
            try:
                result["forced_cleanup"] = stop_process_group(process)
                if result["forced_cleanup"] and result["failure"] is None:
                    result["failure"] = "native-cleanup-incomplete"
            except (OSError, subprocess.TimeoutExpired):
                result["forced_cleanup"] = True
                result["failure"] = "cleanup-failed"
        result["duration_seconds"] = round(time.monotonic() - started, 3)
    return result


def evidence_file(root: Path, value: str) -> Path:
    path, relative = relative_path(root, value, label="flow evidence")
    if not relative.startswith(".tugling/local/verification/") or path.suffix != ".json":
        raise ContractError("flow evidence must be a JSON file under .tugling/local/verification/")
    if path.resolve() != path:
        raise ContractError("flow evidence must not follow symlinks")
    require_ignored(root, relative, label="flow evidence")
    return path


def receipt_retention(value: Any) -> dict[str, int]:
    policy = require_object(value, label="project.receipt_retention",
                            keys=set(DEFAULT_RECEIPT_RETENTION))
    limits = {"max_age_seconds": (1, 365 * 86400), "max_files": (1, 256),
              "max_bytes": (MAX_RECEIPT_BYTES, 64 * 1024 * 1024)}
    for key, (minimum, maximum) in limits.items():
        if type(policy[key]) is not int or not minimum <= policy[key] <= maximum:
            raise ContractError(f"receipt_retention.{key} must be {minimum} to {maximum}")
    return dict(policy)


@contextlib.contextmanager
def defer_receipt_interrupts():
    # Keep ownership registration and bounded teardown intact on SIGINT/SIGTERM.
    previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM})
    try:
        yield
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous)


def receipt_entries(directory: int) -> list[str]:
    names = []
    with os.scandir(directory) as entries:
        for entry in entries:
            if len(names) == MAX_RECEIPT_ENTRIES:
                raise ContractError("receipt directory exceeds the bounded scan; preserve and inspect it")
            names.append(entry.name)
    return names


def regular_receipt_file(directory: int, name: str, flags: int) -> int:
    descriptor = os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=directory)
    info = os.fstat(descriptor)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.geteuid():
        os.close(descriptor)
        raise ContractError(f"receipt store requires an owned regular file: {name}")
    return descriptor


@contextlib.contextmanager
def receipt_store(root: Path):
    """Lock a private namespace; never traverse links or recursively remove files."""
    if os.name != "posix":
        raise ContractError("receipt cleanup requires macOS or Linux file locking")
    import fcntl

    evidence_file(root, f"{RECEIPT_DIRECTORY}/probe.json")
    with contextlib.ExitStack() as resources:
        try:
            directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            resources.callback(os.close, directory)
            for part in RECEIPT_DIRECTORY.split("/"):
                try:
                    os.mkdir(part, mode=0o700, dir_fd=directory)
                except FileExistsError:
                    pass
                directory = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                    dir_fd=directory)
                resources.callback(os.close, directory)
            lock = regular_receipt_file(directory, ".lock", os.O_RDWR | os.O_CREAT)
            resources.callback(os.close, lock)
            if os.fstat(lock).st_size:
                raise ContractError("receipt store lock must be empty")
            deadline = time.monotonic() + 2
            while True:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise ContractError("receipt cleanup is busy; no native command started")
                    time.sleep(.02)
            names = receipt_entries(directory)
            if ".owner" not in names:
                if set(names) != {".lock"}:
                    raise ContractError("unmarked receipt directory contains files; preserve and inspect it")
                marker = regular_receipt_file(directory, ".owner", os.O_WRONLY | os.O_CREAT | os.O_EXCL)
                with os.fdopen(marker, "wb") as output:
                    output.write(RECEIPT_OWNER)
            marker = regular_receipt_file(directory, ".owner", os.O_RDONLY)
            with os.fdopen(marker, "rb") as source:
                if source.read(len(RECEIPT_OWNER) + 1) != RECEIPT_OWNER:
                    raise ContractError("receipt ownership marker differs; preserve and inspect it")
            yield directory
        except OSError as exc:
            raise ContractError(f"receipt store unavailable: {exc}") from exc


def prune_receipts(directory: int, policy: dict[str, int], *, reserve: bool = False) -> dict[str, int]:
    """Called under the store lock. Active writers reserve one full receipt each."""
    import fcntl

    receipts = []
    for name in receipt_entries(directory):
        if not RECEIPT_NAME.fullmatch(name):
            continue
        info = os.stat(name, dir_fd=directory, follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.geteuid():
            continue
        descriptor = regular_receipt_file(directory, name, os.O_RDWR)
        try:
            active = False
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                active = True
            current = os.fstat(descriptor)
            if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
                raise ContractError("receipt changed during cleanup; preserve and retry")
            receipts.append((name, current, active))
        finally:
            os.close(descriptor)
    count = len(receipts) + int(reserve)
    budgeted = sum(max(info.st_size, MAX_RECEIPT_BYTES) if active else info.st_size
                   for _, info, active in receipts) + int(reserve) * MAX_RECEIPT_BYTES
    actual = sum(info.st_size for _, info, _ in receipts)
    removed = removed_bytes = 0
    cutoff = time.time() - policy["max_age_seconds"]
    for name, info, active in sorted(receipts, key=lambda item: (item[1].st_mtime_ns, item[0])):
        if active or (info.st_mtime > cutoff and count <= policy["max_files"]
                      and budgeted <= policy["max_bytes"]):
            continue
        descriptor = regular_receipt_file(directory, name, os.O_RDWR)
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ContractError("receipt became active during cleanup; preserve and retry")
            current = os.stat(name, dir_fd=directory, follow_symlinks=False)
            if (current.st_dev, current.st_ino, current.st_mtime_ns, current.st_size, current.st_nlink) != (
                    info.st_dev, info.st_ino, info.st_mtime_ns, info.st_size, 1):
                raise ContractError("receipt changed during cleanup; preserve and retry")
            os.unlink(name, dir_fd=directory)
            removed += 1
            removed_bytes += info.st_size
            count -= 1
            budgeted -= info.st_size
        finally:
            os.close(descriptor)
    if count > policy["max_files"] or budgeted > policy["max_bytes"]:
        raise ContractError("active receipts exhaust retention capacity; no new native command started")
    return {"removed_files": removed, "removed_bytes": removed_bytes,
            "retained_files": len(receipts) - removed, "retained_bytes": actual - removed_bytes,
            "active_files": sum(active for _, _, active in receipts), "budgeted_bytes": budgeted}


def cleanup_receipts(root: Path, policy: dict[str, int]) -> dict[str, int]:
    if os.name != "posix":
        raise ContractError("receipt cleanup requires macOS or Linux file locking")
    with defer_receipt_interrupts(), receipt_store(root) as directory:
        return prune_receipts(directory, policy)


def receipt_bytes(evidence: dict[str, Any]) -> bytes:
    payload = (json.dumps(evidence, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if len(payload) > MAX_RECEIPT_BYTES:
        raise ContractError("verification receipt exceeds the 256 KiB per-run limit")
    return payload


def write_receipt(descriptor: int, evidence: dict[str, Any]) -> None:
    payload = receipt_bytes(evidence)
    os.lseek(descriptor, 0, os.SEEK_SET)
    os.ftruncate(descriptor, 0)
    with os.fdopen(descriptor, "wb", closefd=False) as output:
        output.write(payload)


def verification_identity(root: Path, config_path: Path, mapping: dict[str, Any]) -> dict[str, str]:
    if not config_path.is_relative_to(root):
        raise ContractError("flow execution requires a committed project config inside the repository")
    config_file, _ = committed_file(root, str(config_path.relative_to(root)), label="project config")
    return {"project_revision": clean_revision(root),
            "config_sha256": hashlib.sha256(config_file.read_bytes()).hexdigest(),
            "map_sha256": mapping["sha256"],
            "helper_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def execute_flows(
    root: Path, config_path: Path, report: dict[str, Any], selected: list[str],
    *, required: bool = False,
) -> dict[str, Any]:
    if os.name != "posix":
        raise ContractError("flow execution requires POSIX process-group cleanup (macOS or Linux)")
    flow_execution_ancestry(root)
    mapping = report["verification"]
    if mapping is None:
        raise ContractError("--run-flow requires project.verification")
    if required and selected != required_flow_ids(mapping):
        raise ContractError("required verification must execute the complete required flow set")
    by_id = {flow["id"]: flow for flow in mapping["flows"]}
    if not selected or len(set(selected)) != len(selected) or any(flow_id not in by_id for flow_id in selected):
        raise ContractError("--run-flow requires distinct ids present in the verification map")
    if sum(by_id[flow_id]["timeout_seconds"] for flow_id in selected) > 7200:
        raise ContractError("selected flow timeout budget must not exceed 7200 seconds")
    identity = verification_identity(root, config_path, mapping)
    run_id = str(uuid.uuid4())
    relative = f"{RECEIPT_DIRECTORY}/{run_id}.json"
    name = f"{run_id}.json"
    evidence: dict[str, Any] = {"schema_version": 1, "kind": "tugling-native-flows",
        "run_id": run_id, **identity, "tugling": report["tugling"],
        "started_at": datetime.now(timezone.utc).isoformat(), "state": "FLOWS_FAIL",
        "requested_flows": selected, "results": [], "worktree_unchanged": False}
    if required:
        evidence.update(kind="tugling-required-flows", state="REQUIRED_FAIL",
                        requirements=mapping["requirements"])
    # Check the largest result shape before spending native work or disk capacity.
    receipt_bytes({**evidence, "finished_at": "0" * 64, "results": [
        {"id": flow_id, "argv": by_id[flow_id]["argv"], "exit_code": -9999999999,
         "failure": "native-cleanup-incomplete", "forced_cleanup": False,
         "duration_seconds": 9999999999.999} for flow_id in selected]})
    policy = report["receipt_retention"]
    descriptor = None
    try:
        import fcntl

        with defer_receipt_interrupts(), receipt_store(root) as directory:
            prune_receipts(directory, policy, reserve=True)
            descriptor = regular_receipt_file(directory, name, os.O_RDWR | os.O_CREAT | os.O_EXCL)
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            write_receipt(descriptor, evidence)
        for flow_id in selected:
            result = run_flow(root, by_id[flow_id])
            evidence["results"].append(result)
            if result["failure"] is not None:
                break
        try:
            evidence["worktree_unchanged"] = clean_revision(root) == identity["project_revision"]
        except ContractError:
            pass
        if (len(evidence["results"]) == len(selected) and evidence["worktree_unchanged"]
                and all(result["failure"] is None for result in evidence["results"])):
            evidence["state"] = "REQUIRED_PASS" if required else "FLOWS_PASS"
    finally:
        if descriptor is not None:
            with defer_receipt_interrupts():
                try:
                    evidence["finished_at"] = datetime.now(timezone.utc).isoformat()
                    write_receipt(descriptor, evidence)
                    with receipt_store(root) as directory:
                        current = os.stat(name, dir_fd=directory, follow_symlinks=False)
                        original = os.fstat(descriptor)
                        if (current.st_dev, current.st_ino) != (original.st_dev, original.st_ino):
                            raise ContractError("active receipt moved during verification")
                        prune_receipts(directory, policy)
                finally:
                    os.close(descriptor)
    return {"state": evidence["state"], "path": relative, "evidence": evidence}


def check_flow_evidence(
    root: Path, config_path: Path, report: dict[str, Any], relative: str,
    *, required: bool = False,
) -> dict[str, Any]:
    """Check freshness and scope of a local receipt; this is not an attestation."""
    mapping = report["verification"]
    if mapping is None:
        raise ContractError("--check-flow-evidence requires project.verification")
    evidence = read_json(evidence_file(root, relative))
    identity = verification_identity(root, config_path, mapping)
    if not isinstance(evidence, dict) or any(evidence.get(key) != value for key, value in identity.items()):
        raise ContractError("flow evidence is stale or belongs to a different project, map, or helper")
    by_id = {flow["id"]: flow for flow in mapping["flows"]}
    selected = evidence.get("requested_flows")
    results = evidence.get("results")
    success_state = "REQUIRED_PASS" if required else "FLOWS_PASS"
    kind = "tugling-required-flows" if required else "tugling-native-flows"
    if required and (selected != required_flow_ids(mapping)
                     or evidence.get("requirements") != mapping["requirements"]):
        raise ContractError("required evidence must cover every current project requirement")
    if (type(evidence.get("schema_version")) is not int or evidence["schema_version"] != 1
            or evidence.get("kind") != kind
            or evidence.get("state") != success_state or evidence.get("worktree_unchanged") is not True
            or not isinstance(selected, list) or not selected
            or not all(isinstance(key, str) and key in by_id for key in selected)
            or len(set(selected)) != len(selected)
            or not isinstance(results, list) or len(results) != len(selected)):
        raise ContractError("flow evidence does not prove a complete successful selection")
    for flow_id, result in zip(selected, results):
        if (not isinstance(result, dict) or result.get("id") != flow_id
                or result.get("argv") != by_id[flow_id]["argv"]
                or type(result.get("exit_code")) is not int or result["exit_code"] != 0
                or "failure" not in result or result["failure"] is not None
                or result.get("forced_cleanup") is not False):
            raise ContractError("flow evidence contains an unsuccessful or mismatched command")
    return {"state": success_state, "path": relative, "evidence": evidence}


def relative_path(root: Path, value: Any, *, label: str) -> tuple[Path, str]:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{label} must be a non-empty relative path")
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ContractError(f"{label} must stay inside the project")
    normalized = candidate.as_posix()
    return root / candidate, normalized


def git_output(root: Path, *args: str, check: bool = True) -> str:
    completed = run(["git", *args], cwd=root, check=check)
    return completed.stdout.strip()


def require_git_repository(root: Path) -> None:
    if git_output(root, "rev-parse", "--is-inside-work-tree", check=False) != "true":
        raise ContractError(f"project is not a Git worktree: {root}")


def require_tracked(root: Path, relative: str, *, label: str) -> None:
    completed = run(["git", "--literal-pathspecs", "ls-files", "--error-unmatch", "--", relative], cwd=root)
    if completed.returncode != 0:
        raise ContractError(f"{label} must be committed: {relative}")


def require_ignored(root: Path, relative: str, *, label: str) -> None:
    completed = run(["git", "check-ignore", "-q", "--no-index", "--", relative], cwd=root)
    if completed.returncode != 0:
        raise ContractError(f"{label} must be ignored by Git: {relative}")
    tracked = run(["git", "--literal-pathspecs", "ls-files", "--error-unmatch", "--", relative], cwd=root)
    if tracked.returncode == 0:
        raise ContractError(f"{label} must never be committed: {relative}")


def find_plugin_root(source_root: Path) -> Path:
    candidates = (
        source_root / "plugins" / "tugling",
        source_root,
    )
    for candidate in candidates:
        if (candidate / ".codex-plugin" / "plugin.json").is_file():
            return candidate
    raise ContractError(f"Tugling plugin manifest not found under {source_root}")


def source_identity(source_root: Path) -> dict[str, Any]:
    plugin_root = find_plugin_root(source_root)
    manifest = read_json(plugin_root / ".codex-plugin" / "plugin.json")
    if not isinstance(manifest, dict):
        raise ContractError("plugin manifest must be an object")
    if manifest.get("name") != "tugling" or not isinstance(manifest.get("version"), str):
        raise ContractError("source plugin manifest is not Tugling")
    revision = git_output(source_root, "rev-parse", "HEAD", check=False)
    if not REVISION_RE.fullmatch(revision):
        revision = None
    return {
        "plugin_root": str(plugin_root),
        "version": manifest["version"],
        "revision": revision,
        "worktree_clean": not bool(git_output(source_root, "status", "--porcelain", "--untracked-files=all")) if revision else None,
    }


def validate_dogfood_case(path: Path) -> dict[str, Any]:
    value = require_object(
        read_json(path),
        label="dogfood case",
        keys={"schema_version", "data_policy", "case"},
    )
    if value.get("schema_version") != 1:
        raise ContractError("dogfood case schema_version must be 1")
    if value.get("data_policy") != "synthetic-only":
        raise ContractError("dogfood case must declare data_policy synthetic-only")
    case = value.get("case")
    required = {
        "id",
        "skill",
        "sandbox",
        "minimum_score",
        "expected_state",
        "max_changed_files",
        "prompt",
        "decision_questions",
    }
    if not isinstance(case, dict) or not required.issubset(case):
        raise ContractError("dogfood case is missing behavioral-evaluation fields")
    if not isinstance(case.get("prompt"), str) or len(case["prompt"].strip()) < 40:
        raise ContractError("dogfood case prompt is missing or too short")
    questions = case.get("decision_questions")
    if not isinstance(questions, list) or not questions:
        raise ContractError("dogfood case needs at least one decision question")
    for index, question in enumerate(questions):
        if not isinstance(question, dict):
            raise ContractError(f"dogfood decision_questions[{index}] must be an object")
        expected = question.get("expected")
        options = question.get("options")
        if not isinstance(options, list) or expected not in options:
            raise ContractError(
                f"dogfood decision_questions[{index}] expected value must be an allowed option"
            )
    return {"id": case.get("id"), "skill": case.get("skill"), "questions": len(questions)}


def assert_no_embedded_secrets(value: Any) -> None:
    serialized = json.dumps(value, sort_keys=True)
    if any(pattern.search(serialized) for pattern in SECRET_PATTERNS):
        raise ContractError("project adapter appears to contain secret material")


def validate_project(
    *,
    root: Path,
    config_path: Path,
    source_root: Path,
    source_mode: str,
    run_native: bool = False,
    native_timeout: int = 1800,
    run_flows: list[str] | None = None,
    check_evidence: str | None = None,
    run_required: bool = False,
    check_required_evidence: str | None = None,
    cleanup_evidence: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    config_path = config_path if config_path.is_absolute() else root / config_path
    require_git_repository(root)
    config = require_object(
        read_json(config_path),
        label="project adapter",
        keys={"schema_version", "tugling", "project", "learning"},
    )
    assert_no_embedded_secrets(config)
    if config.get("schema_version") != 1:
        raise ContractError("project adapter schema_version must be 1")

    tugling = require_object(
        config.get("tugling"),
        label="project adapter tugling",
        keys={"repository", "channel", "revision", "version"},
    )
    repository = tugling.get("repository")
    if not isinstance(repository, str) or not repository.startswith("https://github.com/"):
        raise ContractError("tugling.repository must be an HTTPS GitHub repository")
    channel = tugling.get("channel")
    if channel not in VALID_CHANNELS:
        raise ContractError(f"tugling.channel must be one of {sorted(VALID_CHANNELS)}")
    configured_revision = tugling.get("revision")
    if channel == "pinned":
        if not isinstance(configured_revision, str) or not REVISION_RE.fullmatch(configured_revision):
            raise ContractError("pinned Tugling requires a full 40-character revision")
    elif configured_revision is not None:
        raise ContractError("stable and preview channels must set revision to null")
    if not isinstance(tugling.get("version"), str) or not tugling["version"]:
        raise ContractError("tugling.version must be a non-empty string")

    identity = source_identity(source_root.resolve())
    if identity["version"] != tugling["version"]:
        raise ContractError(
            f"Tugling version mismatch: adapter {tugling['version']}, source {identity['version']}"
        )
    effective_mode = source_mode
    if effective_mode == "auto":
        effective_mode = "pinned" if channel == "pinned" else "candidate"
    if effective_mode == "pinned":
        if not identity["revision"]:
            raise ContractError("pinned verification requires a Git checkout of Tugling")
        if identity["revision"] != configured_revision:
            raise ContractError(
                "Tugling revision mismatch: "
                f"adapter {configured_revision}, source {identity['revision']}"
            )

    project = require_object(
        config.get("project"),
        label="project adapter project",
        keys={"adapter", "instructions", "canonical_verify", "ci_workflow", "dogfood_case"},
        optional={"verification", "receipt_retention"},
    )
    adapter_path, adapter_relative = relative_path(root, project.get("adapter"), label="project.adapter")
    if not adapter_path.is_file():
        raise ContractError(f"project adapter file does not exist: {adapter_relative}")
    require_tracked(root, adapter_relative, label="project.adapter")
    adapter_text = adapter_path.read_text(encoding="utf-8")
    if not re.search(r"^##\s+Tugling project adapter\s*$", adapter_text, re.MULTILINE | re.IGNORECASE):
        raise ContractError(f"{adapter_relative} is missing a 'Tugling project adapter' section")

    instructions = project.get("instructions")
    if not isinstance(instructions, list) or not instructions:
        raise ContractError("project.instructions must be a non-empty array")
    instruction_paths: list[str] = []
    for index, value in enumerate(instructions):
        instruction_path, relative = relative_path(
            root,
            value,
            label=f"project.instructions[{index}]",
        )
        if not instruction_path.is_file():
            raise ContractError(f"project instruction file does not exist: {relative}")
        require_tracked(root, relative, label=f"project.instructions[{index}]")
        instruction_paths.append(relative)
    if adapter_relative not in instruction_paths:
        raise ContractError("project.adapter must also appear in project.instructions")

    verify_argv = project.get("canonical_verify")
    if (
        not isinstance(verify_argv, list)
        or not verify_argv
        or not all(isinstance(part, str) and part for part in verify_argv)
    ):
        raise ContractError("project.canonical_verify must be a non-empty argv array")

    ci_workflow, ci_relative = relative_path(root, project.get("ci_workflow"), label="project.ci_workflow")
    if not ci_workflow.is_file():
        raise ContractError(f"project CI workflow does not exist: {ci_relative}")
    require_tracked(root, ci_relative, label="project.ci_workflow")

    dogfood_path, dogfood_relative = relative_path(
        root,
        project.get("dogfood_case"),
        label="project.dogfood_case",
    )
    if not dogfood_path.is_file():
        raise ContractError(f"project dogfood case does not exist: {dogfood_relative}")
    require_tracked(root, dogfood_relative, label="project.dogfood_case")
    dogfood = validate_dogfood_case(dogfood_path)

    learning = require_object(
        config.get("learning"),
        label="project adapter learning",
        keys={"mode", "local_path"},
    )
    if learning.get("mode") not in VALID_LEARNING_MODES:
        raise ContractError(f"learning.mode must be one of {sorted(VALID_LEARNING_MODES)}")
    _, local_relative = relative_path(root, learning.get("local_path"), label="learning.local_path")
    if not local_relative.startswith(".tugling/local/"):
        raise ContractError("learning.local_path must stay under .tugling/local/")
    require_ignored(root, local_relative, label="learning.local_path")

    mapping = validate_verification_map(root, project["verification"]) if "verification" in project else None
    policy = receipt_retention(project.get("receipt_retention", DEFAULT_RECEIPT_RETENTION))
    if sum(bool(value) for value in (run_native, run_flows, check_evidence,
                                    run_required, check_required_evidence, cleanup_evidence)) > 1:
        raise ContractError("choose one of native verification, selected flows, or an evidence check")
    if run_native or run_flows or run_required:
        flow_execution_ancestry(root)

    native_result: dict[str, Any] | None = None
    if run_native:
        completed = run(verify_argv, cwd=root, timeout=native_timeout, env={
            CANONICAL_EXECUTION_ENV: json.dumps(flow_execution_ancestry(root, canonical=True)),
        })
        native_result = {
            "argv": verify_argv,
            "exit_code": completed.returncode,
        }
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise ContractError(
                f"canonical verification failed ({completed.returncode}): {detail[-2000:]}"
            )

    report = {
        "status": "PASS",
        "project_revision": git_output(root, "rev-parse", "HEAD"),
        "tugling": {
            "channel": channel,
            "configured_revision": configured_revision,
            "source_revision": identity["revision"],
            "source_worktree_clean": identity["worktree_clean"],
            "version": identity["version"],
            "source_mode": effective_mode,
        },
        "adapter": adapter_relative,
        "instructions": instruction_paths,
        "ci_workflow": ci_relative,
        "canonical_verify": verify_argv,
        "dogfood": dogfood,
        "learning": {
            "mode": learning["mode"],
            "local_path": local_relative,
            "git_ignored": True,
        },
        "native_verification": native_result,
        "verification": mapping,
        "flow_verification": None,
        "receipt_retention": policy,
        "receipt_cleanup": None,
    }
    if run_required:
        report["flow_verification"] = execute_flows(
            root, config_path, report, required_flow_ids(mapping), required=True,
        )
    elif check_required_evidence:
        report["flow_verification"] = check_flow_evidence(
            root, config_path, report, check_required_evidence, required=True,
        )
    elif run_flows:
        report["flow_verification"] = execute_flows(root, config_path, report, run_flows)
    elif check_evidence:
        report["flow_verification"] = check_flow_evidence(root, config_path, report, check_evidence)
    elif cleanup_evidence:
        report["receipt_cleanup"] = cleanup_receipts(root, policy)
    if report["flow_verification"] and report["flow_verification"]["state"] not in {"FLOWS_PASS", "REQUIRED_PASS"}:
        report["status"] = "FAIL"
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".", help="project repository to validate")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument(
        "--source-root",
        default=str(Path(__file__).resolve().parents[3]),
        help="Tugling repository or plugin root used for this check",
    )
    parser.add_argument("--source-mode", choices=("auto", "pinned", "candidate"), default="auto")
    execution = parser.add_mutually_exclusive_group()
    execution.add_argument("--run-native", action="store_true")
    execution.add_argument("--run-flow", action="append", help="run one mapped native flow; repeat for a selection")
    execution.add_argument("--run-required", action="store_true", help="run all flows covering declared project requirements")
    execution.add_argument("--check-flow-evidence", help="check a local receipt against the current clean commit")
    execution.add_argument("--check-required-evidence", help="require complete current evidence for all project requirements")
    execution.add_argument("--cleanup-evidence", action="store_true",
                           help="expire and bound helper-owned receipts without running native commands")
    parser.add_argument("--native-timeout", type=int, default=1800)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    previous_handler = None
    if args.run_flow or args.run_required or args.cleanup_evidence:
        def interrupted(signum: int, frame: Any) -> None:
            raise KeyboardInterrupt
        previous_handler = signal.signal(signal.SIGTERM, interrupted)
    try:
        if args.native_timeout < 30:
            raise ContractError("--native-timeout must be at least 30 seconds")
        report = validate_project(
            root=Path(args.repo),
            config_path=Path(args.config),
            source_root=Path(args.source_root),
            source_mode=args.source_mode,
            run_native=args.run_native,
            native_timeout=args.native_timeout,
            run_flows=args.run_flow,
            check_evidence=args.check_flow_evidence,
            run_required=args.run_required,
            check_required_evidence=args.check_required_evidence,
            cleanup_evidence=args.cleanup_evidence,
        )
    except ContractError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        if previous_handler is not None:
            signal.signal(signal.SIGTERM, previous_handler)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["receipt_cleanup"] is not None:
        print(f"RECEIPTS_CLEANED: {json.dumps(report['receipt_cleanup'], sort_keys=True)}")
    elif report["flow_verification"]:
        result = report["flow_verification"]
        scope = "all declared requirements" if args.run_required or args.check_required_evidence else "selected native flows only"
        print(f"{result['state']}: {result['path']} ({scope}; canonical and remote readiness require their own evidence)")
    else:
        print(
            "Tugling project contract passed: "
            f"{report['tugling']['version']} at {report['tugling']['source_revision'] or 'installed source'}, "
            f"{report['dogfood']['questions']} dogfood decisions, learning {report['learning']['mode']}."
        )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
