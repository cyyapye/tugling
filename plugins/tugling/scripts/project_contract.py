#!/usr/bin/env python3
"""Validate a project's Tugling adapter without network access or dependencies."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


DEFAULT_CONFIG = Path(".tugling/project.json")
VALID_CHANNELS = {"pinned", "stable", "preview"}
VALID_LEARNING_MODES = {"off", "local"}
REVISION_RE = re.compile(r"[0-9a-f]{40}")
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
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "NO_COLOR": "1"},
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


def require_object(value: Any, *, label: str, keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{label} must be an object")
    if set(value) != keys:
        raise ContractError(
            f"{label} fields differ: expected {sorted(keys)}, found {sorted(value)}"
        )
    return value


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
    completed = run(["git", "ls-files", "--error-unmatch", "--", relative], cwd=root)
    if completed.returncode != 0:
        raise ContractError(f"{label} must be committed: {relative}")


def require_ignored(root: Path, relative: str, *, label: str) -> None:
    completed = run(["git", "check-ignore", "-q", "--no-index", "--", relative], cwd=root)
    if completed.returncode != 0:
        raise ContractError(f"{label} must be ignored by Git: {relative}")
    tracked = run(["git", "ls-files", "--error-unmatch", "--", relative], cwd=root)
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

    native_result: dict[str, Any] | None = None
    if run_native:
        completed = run(verify_argv, cwd=root, timeout=native_timeout)
        native_result = {
            "argv": verify_argv,
            "exit_code": completed.returncode,
        }
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise ContractError(
                f"canonical verification failed ({completed.returncode}): {detail[-2000:]}"
            )

    return {
        "status": "PASS",
        "project_revision": git_output(root, "rev-parse", "HEAD"),
        "tugling": {
            "channel": channel,
            "configured_revision": configured_revision,
            "source_revision": identity["revision"],
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
    }


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
    parser.add_argument("--run-native", action="store_true")
    parser.add_argument("--native-timeout", type=int, default=1800)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
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
        )
    except ContractError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            "Tugling project contract passed: "
            f"{report['tugling']['version']} at {report['tugling']['source_revision'] or 'installed source'}, "
            f"{report['dogfood']['questions']} dogfood decisions, learning {report['learning']['mode']}."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
