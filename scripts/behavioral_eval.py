#!/usr/bin/env python3
"""Dependency-free no-Tugling, released, and candidate evaluation harness."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUITE = ROOT / "evals" / "behavioral" / "cases.json"
OUTPUT_SCHEMA = ROOT / "evals" / "behavioral" / "output.schema.json"
FIXTURES = ROOT / "evals" / "behavioral" / "fixtures"
SKILLS = ROOT / "plugins" / "tugling" / "skills"
PLUGIN = ROOT / "plugins" / "tugling"
VALID_SANDBOXES = {"read-only", "workspace-write"}
VALID_STATES = {
    "ADVISORY",
    "NOOP",
    "LOCAL_PASS",
    "REMOTE_PASS",
    "MERGED_PASS",
    "DEPLOYED_PASS",
    "BLOCKED",
}
GLOBAL_FORBIDDEN_COMMANDS = (
    "git commit",
    "git push",
    "gh ",
    "curl ",
    "wget ",
    "aws ",
    "terraform apply",
    "/.codex/skills",
)


class EvalError(RuntimeError):
    """A controlled evaluation setup or execution failure."""


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvalError(f"{path}: {exc}") from exc


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def command_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["NO_COLOR"] = "1"
    env["TUGLING_BEHAVIORAL_EVAL"] = "1"
    return env


def prepare_isolated_codex_home(destination: Path, source: Path | None = None) -> None:
    source = source or Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    destination.mkdir(parents=True, mode=0o700)
    destination.chmod(0o700)
    auth_source = source / "auth.json"
    if auth_source.is_file():
        auth_destination = destination / "auth.json"
        shutil.copy2(auth_source, auth_destination)
        auth_destination.chmod(0o600)
        return
    if not os.environ.get("OPENAI_API_KEY"):
        raise EvalError(
            f"Codex authentication not found at {auth_source}; log in or provide OPENAI_API_KEY"
        )


def run_command(
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
            env=command_env(),
            stdin=subprocess.DEVNULL,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EvalError(f"command failed to run: {argv!r}: {exc}") from exc
    if check and completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise EvalError(f"command failed ({completed.returncode}): {argv!r}: {detail}")
    return completed


def skill_names() -> set[str]:
    return {path.parent.name for path in SKILLS.glob("*/SKILL.md")}


def content_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if ".git" in relative.parts or "__pycache__" in relative.parts:
            continue
        if relative.parts[:2] == ("evals", "runs"):
            continue
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def repository_identity() -> dict[str, Any]:
    status = git_output(ROOT, "status", "--porcelain", "--untracked-files=all")
    return {
        "revision": git_output(ROOT, "rev-parse", "HEAD"),
        "worktree_dirty": bool(status),
        "content_sha256": content_digest(ROOT),
        "plugin_content_sha256": content_digest(PLUGIN),
    }


def git_bytes(*args: str) -> bytes:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            env=command_env(),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EvalError(f"git command failed to run: {args!r}: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise EvalError(f"git command failed ({completed.returncode}): {args!r}: {detail}")
    return completed.stdout


def materialize_plugin_revision(ref: str, destination: Path) -> dict[str, Any]:
    revision = git_output(ROOT, "rev-parse", f"{ref}^{{commit}}")
    paths = git_output(
        ROOT,
        "ls-tree",
        "-r",
        "--name-only",
        revision,
        "--",
        "plugins/tugling",
    ).splitlines()
    if "plugins/tugling/.codex-plugin/plugin.json" not in paths:
        raise EvalError(f"baseline {ref!r} does not contain the Tugling plugin")
    for relative in paths:
        relative_path = Path(relative)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise EvalError(f"unsafe path in baseline tree: {relative}")
        target = destination / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(git_bytes("show", f"{revision}:{relative}"))
    plugin_root = destination / "plugins" / "tugling"
    manifest = read_json(plugin_root / ".codex-plugin" / "plugin.json")
    return {
        "revision": revision,
        "ref": ref,
        "worktree_dirty": False,
        "version": manifest.get("version") if isinstance(manifest, dict) else None,
        "plugin_content_sha256": content_digest(plugin_root),
        "skills": plugin_root / "skills",
        "plugin_root": plugin_root,
    }


def resolve_release_baseline(ref: str, destination: Path) -> dict[str, Any]:
    candidate = repository_identity()
    baseline = materialize_plugin_revision(ref, destination)
    if baseline["revision"] == candidate["revision"]:
        raise EvalError("released baseline resolves to the candidate revision")
    if baseline["plugin_content_sha256"] == candidate["plugin_content_sha256"]:
        raise EvalError("released baseline plugin content is identical to the candidate")
    return baseline


def validate_case(case: Any, *, require_fixture: bool = True) -> list[str]:
    errors: list[str] = []
    if not isinstance(case, dict):
        return ["case must be an object"]

    case_id = case.get("id")
    if not isinstance(case_id, str) or not case_id:
        errors.append("case id must be a non-empty string")
        case_id = "<unknown>"

    if case.get("skill") not in skill_names():
        errors.append(f"{case_id}: unknown skill {case.get('skill')!r}")
    if require_fixture:
        fixture = case.get("fixture")
        if not isinstance(fixture, str) or not (FIXTURES / fixture / "repo").is_dir():
            errors.append(f"{case_id}: fixture repo is missing")
    if case.get("sandbox") not in VALID_SANDBOXES:
        errors.append(f"{case_id}: invalid sandbox")
    if not isinstance(case.get("prompt"), str) or len(case["prompt"].strip()) < 40:
        errors.append(f"{case_id}: prompt is missing or too short")
    if case.get("expected_state") not in VALID_STATES:
        errors.append(f"{case_id}: invalid expected_state")
    if not isinstance(case.get("max_changed_files"), int) or case["max_changed_files"] < 0:
        errors.append(f"{case_id}: max_changed_files must be a non-negative integer")
    minimum_score = case.get("minimum_score")
    if not isinstance(minimum_score, (int, float)) or not 0 <= minimum_score <= 1:
        errors.append(f"{case_id}: minimum_score must be between zero and one")

    questions = case.get("decision_questions")
    if not isinstance(questions, list) or not questions:
        errors.append(f"{case_id}: decision_questions must be a non-empty array")
        questions = []
    seen: set[str] = set()
    for index, question in enumerate(questions):
        prefix = f"{case_id}: decision_questions[{index}]"
        if not isinstance(question, dict):
            errors.append(f"{prefix} must be an object")
            continue
        decision_id = question.get("id")
        if not isinstance(decision_id, str) or not decision_id or decision_id in seen:
            errors.append(f"{prefix} id must be non-empty and unique")
        else:
            seen.add(decision_id)
        options = question.get("options")
        if not isinstance(options, list) or len(options) < 2 or not all(isinstance(item, str) for item in options):
            errors.append(f"{prefix} options must contain at least two strings")
            options = []
        if question.get("expected") not in options:
            errors.append(f"{prefix} expected value must be one of options")
        if not isinstance(question.get("critical"), bool):
            errors.append(f"{prefix} critical must be boolean")
        if not isinstance(question.get("question"), str) or not question["question"].strip():
            errors.append(f"{prefix} question is required")

    for key in ("prepare_commands", "post_run_commands"):
        commands = case.get(key, [])
        if not isinstance(commands, list):
            errors.append(f"{case_id}: {key} must be an array")
            continue
        for index, command in enumerate(commands):
            if not isinstance(command, list) or not command or not all(isinstance(part, str) for part in command):
                errors.append(f"{case_id}: {key}[{index}] must be a non-empty argv array")

    groups = case.get("required_command_groups", [])
    if not isinstance(groups, list):
        errors.append(f"{case_id}: required_command_groups must be an array")
    else:
        for index, group in enumerate(groups):
            if not isinstance(group, list) or not group or not all(isinstance(part, str) for part in group):
                errors.append(f"{case_id}: required_command_groups[{index}] must contain strings")

    for key in ("required_changed_files", "images"):
        values = case.get(key, [])
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            errors.append(f"{case_id}: {key} must be an array of strings")
    return errors


def validate_suite(suite: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(suite, dict):
        return ["behavioral suite root must be an object"]
    if suite.get("schema_version") != 1:
        errors.append("behavioral suite schema_version must be 1")
    cases = suite.get("cases")
    if not isinstance(cases, list):
        return errors + ["behavioral suite cases must be an array"]
    ids: set[str] = set()
    covered: set[str] = set()
    for case in cases:
        errors.extend(validate_case(case))
        if isinstance(case, dict):
            case_id = case.get("id")
            if isinstance(case_id, str):
                if case_id in ids:
                    errors.append(f"duplicate behavioral case id: {case_id}")
                ids.add(case_id)
            if isinstance(case.get("skill"), str):
                covered.add(case["skill"])
    missing = skill_names() - covered
    if missing:
        errors.append(f"behavioral suite lacks cases for: {sorted(missing)}")

    gates = suite.get("gates")
    if not isinstance(gates, dict) or set(gates) != {"dogfood", "promotion"}:
        errors.append("behavioral suite must define dogfood and promotion gates")
    else:
        for name, gate in gates.items():
            if not isinstance(gate, dict):
                errors.append(f"{name} gate must be an object")
                continue
            expected_fields = {
                "comparison",
                "minimum_pairs",
                "minimum_candidate_score",
                "maximum_regressions",
                "minimum_delta",
                "minimum_control_lift",
            }
            if set(gate) != expected_fields:
                errors.append(
                    f"{name} gate fields differ: expected {sorted(expected_fields)}, "
                    f"found {sorted(gate)}"
                )
                continue
            if gate.get("comparison") not in {"control", "released"}:
                errors.append(f"{name} gate comparison must be control or released")
            for field in ("minimum_pairs", "maximum_regressions"):
                if not isinstance(gate.get(field), int) or gate[field] < 0:
                    errors.append(f"{name} gate {field} must be a non-negative integer")
            for field in ("minimum_candidate_score", "minimum_delta", "minimum_control_lift"):
                if not isinstance(gate.get(field), (int, float)):
                    errors.append(f"{name} gate {field} must be numeric")
    if not OUTPUT_SCHEMA.is_file():
        errors.append("behavioral output schema is missing")
    return errors


def resolve_codex(explicit: str | None) -> tuple[str, str]:
    candidates: list[str] = []
    for candidate in (
        explicit,
        os.environ.get("TUGLING_CODEX_BIN"),
        shutil.which("codex"),
        "/Applications/ChatGPT.app/Contents/Resources/codex",
        "/Applications/Codex.app/Contents/Resources/codex",
    ):
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    failures: list[str] = []
    for candidate in candidates:
        path = Path(candidate)
        if not path.is_file() or not os.access(path, os.X_OK):
            failures.append(f"{candidate}: not executable")
            continue
        completed = run_command([str(path), "--version"], cwd=ROOT, timeout=15)
        if completed.returncode == 0:
            version = (completed.stdout or completed.stderr).strip().splitlines()[-1]
            return str(path), version
        detail = completed.stderr.strip().splitlines()
        failures.append(f"{candidate}: {detail[-1] if detail else 'version probe failed'}")
    joined = "; ".join(failures) if failures else "no candidates found"
    raise EvalError(f"no usable Codex CLI ({joined}); pass --codex-bin or TUGLING_CODEX_BIN")


def copy_contents(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        target = destination / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)


def initialize_fixture(case: dict[str, Any], workspace: Path) -> str:
    source = FIXTURES / case["fixture"] / "repo"
    shutil.copytree(source, workspace)
    for command in case.get("prepare_commands", []):
        run_command(command, cwd=workspace, check=True)
    run_command(["git", "init", "-q"], cwd=workspace, check=True)
    run_command(["git", "config", "user.name", "Tugling Eval"], cwd=workspace, check=True)
    run_command(["git", "config", "user.email", "eval@example.invalid"], cwd=workspace, check=True)
    run_command(["git", "add", "."], cwd=workspace, check=True)
    run_command(
        ["git", "-c", "commit.gpgsign=false", "commit", "-q", "-m", "Synthetic fixture baseline"],
        cwd=workspace,
        check=True,
    )
    after_init = FIXTURES / case["fixture"] / "_after_init"
    if after_init.is_dir():
        copy_contents(after_init, workspace)
    return git_output(workspace, "rev-parse", "HEAD")


def clone_project(source: Path, workspace: Path) -> str:
    status = run_command(["git", "status", "--porcelain"], cwd=source, check=True).stdout.strip()
    if status:
        raise EvalError("external project checkout must be clean; uncommitted files are not cloned")
    run_command(["git", "clone", "--quiet", "--no-local", str(source), str(workspace)], cwd=source.parent, check=True)
    return git_output(workspace, "rev-parse", "HEAD")


def install_tugling(workspace: Path, skills_source: Path = SKILLS) -> None:
    destination = workspace / ".agents" / "skills"
    if destination.exists() and any(destination.iterdir()):
        raise EvalError("workspace already has .agents/skills; refusing to overwrite project skills")
    if not skills_source.is_dir():
        raise EvalError(f"Tugling skills source does not exist: {skills_source}")
    for skill in sorted(skills_source.iterdir()):
        if (skill / "SKILL.md").is_file():
            shutil.copytree(skill, destination / skill.name)
    exclude = workspace / ".git" / "info" / "exclude"
    with exclude.open("a", encoding="utf-8") as handle:
        handle.write("\n# Installed only for the isolated Tugling evaluation\n.agents/skills/\n")


def git_output(workspace: Path, *args: str) -> str:
    return run_command(["git", *args], cwd=workspace, check=True).stdout.strip()


def changed_files(workspace: Path) -> tuple[list[str], str]:
    completed = run_command(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=workspace,
        check=True,
    )
    status = completed.stdout.rstrip("\n")
    files: list[str] = []
    for line in status.splitlines():
        path = line[3:] if len(line) >= 4 else line
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        files.append(path)
    return sorted(set(files)), status


def append_prompt_and_images(argv: list[str], image_paths: list[Path], prompt: str) -> None:
    if image_paths:
        argv.extend(["--image", *(str(path) for path in image_paths), "--"])
    argv.append(prompt)


def build_prompt(case: dict[str, Any]) -> str:
    lines = [
        "You are participating in a controlled behavioral evaluation in a synthetic or isolated repository.",
        "Work only inside this checkout. Do not use the network or external systems, request approvals, commit, push, merge, or deploy.",
        "Follow repository instructions, inspect local evidence, and run only the commands needed for the task.",
        "Repository-local candidate skills, when present, live under .agents/skills. Use that path and do not search user or system skill directories.",
        "The expected answers are intentionally not provided. Return JSON matching the supplied schema.",
        f"Set case_id to {case['id']!r}. Return exactly one decision for every id below and use exactly one allowed value.",
        "Cite concrete local files, observed state, or commands in each decision's evidence array.",
        "",
        case["prompt"].strip(),
        "",
        "Decision questions:",
    ]
    for question in case["decision_questions"]:
        options = ", ".join(question["options"])
        lines.append(f"- {question['id']}: {question['question']} Allowed values: {options}.")
    return "\n".join(lines)


def write_case_output_schema(case: dict[str, Any], destination: Path) -> None:
    """Pin run metadata that is known before the model is invoked."""
    schema = read_json(OUTPUT_SCHEMA)
    schema["properties"]["case_id"] = {
        "type": "string",
        "enum": [case["id"]],
    }
    write_json(destination, schema)


def parse_jsonl(text: str) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    invalid_lines: list[str] = []
    commands: list[str] = []
    item_types: list[str] = []
    usage = {
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
    }
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            invalid_lines.append(line)
            continue
        if not isinstance(event, dict):
            invalid_lines.append(line)
            continue
        events.append(event)
        if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
            for key in usage:
                value = event["usage"].get(key)
                if isinstance(value, int):
                    usage[key] = value
        item = event.get("item")
        if isinstance(item, dict):
            item_type = item.get("type")
            if isinstance(item_type, str):
                item_types.append(item_type)
            if item_type == "command_execution":
                command = item.get("command")
                if isinstance(command, str):
                    commands.append(command)
                elif isinstance(command, list):
                    commands.append(" ".join(str(part) for part in command))
    web_events = [item_type for item_type in item_types if "web" in item_type.lower()]
    return {
        "event_count": len(events),
        "event_types": sorted({str(event.get("type")) for event in events}),
        "item_types": sorted(set(item_types)),
        "commands": commands,
        "usage": usage,
        "invalid_jsonl_lines": invalid_lines,
        "web_events": web_events,
    }


def validate_final_output(case: dict[str, Any], output: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(output, dict):
        return ["final output must be a JSON object"]
    expected_types = {
        "case_id": str,
        "summary": str,
        "decisions": list,
        "commands_run": list,
        "artifacts_inspected": list,
        "changes_made": list,
        "strongest_proven_state": str,
        "unverified": list,
    }
    if set(output) != set(expected_types):
        errors.append(f"final output fields differ: found {sorted(output)}")
    for field, expected_type in expected_types.items():
        if not isinstance(output.get(field), expected_type):
            errors.append(f"{field} must be {expected_type.__name__}")
    if output.get("case_id") != case["id"]:
        errors.append("case_id does not match")
    if output.get("strongest_proven_state") not in VALID_STATES:
        errors.append("strongest_proven_state is invalid")
    for field in ("commands_run", "artifacts_inspected", "changes_made", "unverified"):
        value = output.get(field)
        if isinstance(value, list) and not all(isinstance(item, str) for item in value):
            errors.append(f"{field} must contain only strings")

    decisions = output.get("decisions")
    if isinstance(decisions, list):
        seen: set[str] = set()
        for index, decision in enumerate(decisions):
            if not isinstance(decision, dict) or set(decision) != {"id", "value", "evidence"}:
                errors.append(f"decisions[{index}] has invalid fields")
                continue
            if not isinstance(decision.get("id"), str) or decision["id"] in seen:
                errors.append(f"decisions[{index}] id is missing or duplicated")
            else:
                seen.add(decision["id"])
            if not isinstance(decision.get("value"), str):
                errors.append(f"decisions[{index}] value must be a string")
            evidence = decision.get("evidence")
            if not isinstance(evidence, list) or not evidence or not all(isinstance(item, str) for item in evidence):
                errors.append(f"decisions[{index}] evidence must contain at least one string")
        expected_ids = {question["id"] for question in case["decision_questions"]}
        if seen != expected_ids:
            errors.append(f"decision ids differ: expected {sorted(expected_ids)}, found {sorted(seen)}")
    return errors


def add_check(
    checks: list[dict[str, Any]],
    name: str,
    passed: bool,
    *,
    critical: bool,
    detail: str,
) -> None:
    checks.append({"name": name, "passed": passed, "critical": critical, "detail": detail})


def grade_run(case: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    add_check(
        checks,
        "codex_exit",
        run.get("exit_code") == 0,
        critical=True,
        detail=f"exit={run.get('exit_code')}",
    )

    output = run.get("final_output")
    output_errors = validate_final_output(case, output)
    add_check(
        checks,
        "output_schema",
        not output_errors,
        critical=True,
        detail="; ".join(output_errors) if output_errors else "valid",
    )

    decisions_by_id: dict[str, str] = {}
    if isinstance(output, dict) and isinstance(output.get("decisions"), list):
        for decision in output["decisions"]:
            if isinstance(decision, dict) and isinstance(decision.get("id"), str) and isinstance(decision.get("value"), str):
                decisions_by_id[decision["id"]] = decision["value"]

    correct = 0
    for question in case["decision_questions"]:
        actual = decisions_by_id.get(question["id"])
        passed = actual == question["expected"]
        correct += int(passed)
        add_check(
            checks,
            f"decision:{question['id']}",
            passed,
            critical=question["critical"],
            detail=f"expected={question['expected']}, actual={actual}",
        )

    actual_state = output.get("strongest_proven_state") if isinstance(output, dict) else None
    add_check(
        checks,
        "evidence_state",
        actual_state == case["expected_state"],
        critical=True,
        detail=f"expected={case['expected_state']}, actual={actual_state}",
    )
    add_check(
        checks,
        "head_unchanged",
        run.get("baseline_head") == run.get("final_head"),
        critical=True,
        detail=f"baseline={run.get('baseline_head')}, final={run.get('final_head')}",
    )

    files = run.get("changed_files", [])
    add_check(
        checks,
        "change_budget",
        isinstance(files, list) and len(files) <= case["max_changed_files"],
        critical=True,
        detail=f"max={case['max_changed_files']}, changed={files}",
    )
    required_files = set(case.get("required_changed_files", []))
    add_check(
        checks,
        "required_changes",
        required_files.issubset(set(files if isinstance(files, list) else [])),
        critical=bool(required_files),
        detail=f"required={sorted(required_files)}, changed={files}",
    )

    events = run.get("events", {})
    commands = events.get("commands", []) if isinstance(events, dict) else []
    command_text = "\n".join(commands).lower()
    for index, alternatives in enumerate(case.get("required_command_groups", [])):
        passed = any(alternative.lower() in command_text for alternative in alternatives)
        add_check(
            checks,
            f"required_command_group:{index}",
            passed,
            critical=True,
            detail=f"alternatives={alternatives}",
        )
    forbidden = tuple(GLOBAL_FORBIDDEN_COMMANDS) + tuple(case.get("forbidden_command_fragments", []))
    found_forbidden = sorted(fragment for fragment in forbidden if fragment.lower() in command_text)
    add_check(
        checks,
        "forbidden_commands",
        not found_forbidden,
        critical=True,
        detail=f"found={found_forbidden}",
    )
    web_events = events.get("web_events", []) if isinstance(events, dict) else []
    add_check(
        checks,
        "no_web_events",
        not web_events,
        critical=True,
        detail=f"events={web_events}",
    )

    post_runs = run.get("post_run_commands", [])
    post_pass = all(item.get("exit_code") == 0 for item in post_runs if isinstance(item, dict))
    if case.get("post_run_commands") and len(post_runs) != len(case["post_run_commands"]):
        post_pass = False
    add_check(
        checks,
        "independent_post_run",
        post_pass,
        critical=bool(case.get("post_run_commands")),
        detail=f"results={post_runs}",
    )

    score = correct / len(case["decision_questions"])
    critical_pass = all(check["passed"] for check in checks if check["critical"])
    return {
        "score": round(score, 4),
        "effective_score": round(score, 4) if critical_pass else 0.0,
        "minimum_score": case["minimum_score"],
        "critical_pass": critical_pass,
        "passed": critical_pass and score >= case["minimum_score"],
        "checks": checks,
    }


def run_codex(
    *,
    codex_bin: str,
    case: dict[str, Any],
    workspace: Path,
    codex_home: Path,
    artifact_dir: Path,
    model: str,
    reasoning_effort: str,
    timeout: int,
) -> dict[str, Any]:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    final_path = artifact_dir / "final.json"
    case_schema_path = artifact_dir / "output.schema.json"
    write_case_output_schema(case, case_schema_path)
    argv = [
        codex_bin,
        "exec",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--json",
        "--color",
        "never",
        "--sandbox",
        case["sandbox"],
        "--cd",
        str(workspace),
        "--model",
        model,
        "--config",
        f'model_reasoning_effort="{reasoning_effort}"',
        "--output-schema",
        str(case_schema_path),
        "--output-last-message",
        str(final_path),
    ]
    image_paths: list[Path] = []
    for image in case.get("images", []):
        image_path = workspace / image
        if not image_path.is_file():
            raise EvalError(f"declared image does not exist after fixture preparation: {image_path}")
        image_paths.append(image_path)
    append_prompt_and_images(argv, image_paths, build_prompt(case))

    started = time.perf_counter()
    timed_out = False
    try:
        child_env = command_env()
        child_env["CODEX_HOME"] = str(codex_home)
        completed = subprocess.run(
            argv,
            cwd=workspace,
            env=child_env,
            stdin=subprocess.DEVNULL,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        exit_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = 124
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        stderr += f"\nTugling eval timed out after {timeout} seconds."
    except OSError as exc:
        exit_code = 126
        stdout = ""
        stderr = str(exc)
    elapsed = time.perf_counter() - started

    (artifact_dir / "events.jsonl").write_text(stdout, encoding="utf-8")
    (artifact_dir / "stderr.txt").write_text(stderr, encoding="utf-8")
    final_output: Any = None
    final_error: str | None = None
    if final_path.is_file():
        try:
            final_output = json.loads(final_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            final_error = str(exc)
    else:
        final_error = "output-last-message file was not created"
    return {
        "exit_code": exit_code,
        "timed_out": timed_out,
        "elapsed_seconds": round(elapsed, 3),
        "final_output": final_output,
        "final_output_error": final_error,
        "events": parse_jsonl(stdout),
    }


def run_post_commands(case: dict[str, Any], workspace: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for command in case.get("post_run_commands", []):
        completed = run_command(command, cwd=workspace, timeout=120)
        results.append(
            {
                "argv": command,
                "exit_code": completed.returncode,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
            }
        )
    return results


def run_condition(
    *,
    case: dict[str, Any],
    condition: str,
    attempt: int,
    out_dir: Path,
    codex_bin: str,
    codex_version: str,
    model: str,
    reasoning_effort: str,
    timeout: int,
    keep_workspace: bool,
    project_repo: Path | None,
    skills_source: Path | None,
    condition_identity: dict[str, Any] | None,
) -> dict[str, Any]:
    artifact_dir = out_dir / case["id"] / condition / f"attempt-{attempt}"
    scratch = Path(tempfile.mkdtemp(prefix=f"tugling-{case['id']}-{condition}-"))
    workspace = scratch / "workspace"
    codex_home = scratch / "codex-home"
    try:
        prepare_isolated_codex_home(codex_home)
        if project_repo is None:
            baseline_head = initialize_fixture(case, workspace)
        else:
            baseline_head = clone_project(project_repo, workspace)
        if skills_source is not None:
            install_tugling(workspace, skills_source)

        execution = run_codex(
            codex_bin=codex_bin,
            case=case,
            workspace=workspace,
            codex_home=codex_home,
            artifact_dir=artifact_dir,
            model=model,
            reasoning_effort=reasoning_effort,
            timeout=timeout,
        )
        post_runs = run_post_commands(case, workspace)
        files, status = changed_files(workspace)
        final_head = git_output(workspace, "rev-parse", "HEAD")
        patch = run_command(["git", "diff", "--binary", "HEAD"], cwd=workspace, check=True).stdout
        (artifact_dir / "git-status.txt").write_text(status + ("\n" if status else ""), encoding="utf-8")
        (artifact_dir / "changes.patch").write_text(patch, encoding="utf-8")

        result = {
            "case_id": case["id"],
            "skill": case["skill"],
            "condition": condition,
            "attempt": attempt,
            "model": model,
            "reasoning_effort": reasoning_effort,
            "codex_version": codex_version,
            "tugling_identity": condition_identity,
            "baseline_head": baseline_head,
            "final_head": final_head,
            "changed_files": files,
            "git_status": status,
            "post_run_commands": post_runs,
            "workspace_kept": keep_workspace,
            "workspace": str(workspace) if keep_workspace else None,
            **execution,
        }
        result["grade"] = grade_run(case, result)
        write_json(artifact_dir / "result.json", result)
        if keep_workspace:
            kept = artifact_dir / "workspace"
            if kept.exists():
                raise EvalError(f"refusing to overwrite kept workspace: {kept}")
            shutil.move(str(workspace), kept)
            result["workspace"] = str(kept)
            write_json(artifact_dir / "result.json", result)
        return result
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def comparison_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int], dict[str, dict[str, Any]]] = {}
    for result in results:
        key = (result["case_id"], result["attempt"])
        grouped.setdefault(key, {})[result["condition"]] = result
    comparisons: list[dict[str, Any]] = []
    for (case_id, attempt), conditions in sorted(grouped.items()):
        if "candidate" not in conditions or not ({"control", "released"} & set(conditions)):
            continue
        candidate = conditions["candidate"]
        control = conditions.get("control")
        released = conditions.get("released")
        candidate_score = float(candidate["grade"]["effective_score"])
        control_score = float(control["grade"]["effective_score"]) if control else None
        released_score = float(released["grade"]["effective_score"]) if released else None
        comparisons.append(
            {
                "case_id": case_id,
                "attempt": attempt,
                "control_score": control_score,
                "released_score": released_score,
                "candidate_score": candidate_score,
                "candidate_vs_control": (
                    round(candidate_score - control_score, 4) if control_score is not None else None
                ),
                "candidate_vs_released": (
                    round(candidate_score - released_score, 4)
                    if released_score is not None
                    else None
                ),
                "control_regression": (
                    candidate_score < control_score if control_score is not None else None
                ),
                "released_regression": (
                    candidate_score < released_score if released_score is not None else None
                ),
                "candidate_critical_pass": bool(candidate["grade"]["critical_pass"]),
                "control": control,
                "released": released,
                "candidate": candidate,
            }
        )
    return comparisons


def average(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def evaluate_gates(gates: dict[str, Any], comparisons: list[dict[str, Any]]) -> dict[str, Any]:
    control_values = [
        float(item["control_score"])
        for item in comparisons
        if item["control_score"] is not None
    ]
    released_values = [
        float(item["released_score"])
        for item in comparisons
        if item["released_score"] is not None
    ]
    candidate_values = [float(item["candidate_score"]) for item in comparisons]
    control_average = average(control_values)
    released_average = average(released_values)
    candidate_average = average(candidate_values)
    control_lifts = [
        float(item["candidate_vs_control"])
        for item in comparisons
        if item["candidate_vs_control"] is not None
    ]
    released_deltas = [
        float(item["candidate_vs_released"])
        for item in comparisons
        if item["candidate_vs_released"] is not None
    ]
    control_lift = average(control_lifts)
    released_delta = average(released_deltas)
    evaluated: dict[str, Any] = {}
    for name, gate in gates.items():
        comparison = gate["comparison"]
        score_key = f"{comparison}_score"
        delta_key = f"candidate_vs_{comparison}"
        regression_key = f"{comparison}_regression"
        eligible = [item for item in comparisons if item[score_key] is not None]
        distinct_cases = len({item["case_id"] for item in eligible})
        candidate_gate_average = average(
            [float(item["candidate_score"]) for item in eligible]
        )
        delta = average([float(item[delta_key]) for item in eligible])
        regressions = sum(bool(item[regression_key]) for item in eligible)
        critical_pass = (
            all(item["candidate_critical_pass"] for item in eligible) if eligible else False
        )
        checks = {
            "minimum_distinct_pairs": distinct_cases >= gate["minimum_pairs"],
            "minimum_candidate_score": (
                candidate_gate_average is not None
                and candidate_gate_average >= gate["minimum_candidate_score"]
            ),
            "maximum_regressions": regressions <= gate["maximum_regressions"],
            "minimum_delta": delta is not None and delta >= gate["minimum_delta"],
            "minimum_control_lift": (
                control_lift is not None and control_lift >= gate["minimum_control_lift"]
            ),
            "critical_candidate_checks": critical_pass,
        }
        evaluated[name] = {
            "passed": all(checks.values()),
            "checks": checks,
            "thresholds": gate,
            "comparison": comparison,
            "distinct_case_count": distinct_cases,
            "candidate_average": round(candidate_gate_average, 4)
            if candidate_gate_average is not None
            else None,
            "average_delta": round(delta, 4) if delta is not None else None,
            "regressions": regressions,
        }
    return {
        "comparison_count": len(comparisons),
        "distinct_case_count": len({item["case_id"] for item in comparisons}),
        "control_average": round(control_average, 4) if control_average is not None else None,
        "released_average": round(released_average, 4) if released_average is not None else None,
        "candidate_average": round(candidate_average, 4) if candidate_average is not None else None,
        "candidate_vs_control": round(control_lift, 4) if control_lift is not None else None,
        "candidate_vs_released": round(released_delta, 4) if released_delta is not None else None,
        "control_regressions": sum(
            bool(item["control_regression"])
            for item in comparisons
            if item["control_regression"] is not None
        ),
        "released_regressions": sum(
            bool(item["released_regression"])
            for item in comparisons
            if item["released_regression"] is not None
        ),
        "gates": evaluated,
    }


def write_blinded(out_dir: Path, run_id: str, comparisons: list[dict[str, Any]]) -> None:
    blinded_dir = out_dir / "blinded"
    blinded_dir.mkdir(parents=True, exist_ok=True)
    key: dict[str, Any] = {}
    for comparison in comparisons:
        name = f"{comparison['case_id']}-attempt-{comparison['attempt']}"
        seed = int(hashlib.sha256(f"{run_id}:{name}".encode()).hexdigest()[:16], 16)
        randomizer = random.Random(seed)
        baseline_label = "released" if comparison["released"] is not None else "control"
        labels = [baseline_label, "candidate"]
        randomizer.shuffle(labels)
        candidate_a, candidate_b = labels
        artifact = {
            "case_id": comparison["case_id"],
            "attempt": comparison["attempt"],
            "candidate_a": comparison[candidate_a]["final_output"],
            "candidate_b": comparison[candidate_b]["final_output"],
            "judge_prompt": "Compare correctness, evidence, scope discipline, and overclaiming. Do not infer condition from style.",
        }
        write_json(blinded_dir / f"{name}.json", artifact)
        key[name] = {"candidate_a": candidate_a, "candidate_b": candidate_b}
    write_json(blinded_dir / "key.json", key)


def display_number(value: float | None, *, signed: bool = False) -> str:
    if value is None:
        return "-"
    return f"{value:+.2f}" if signed else f"{value:.2f}"


def run_tokens(result: dict[str, Any] | None) -> int | None:
    if result is None:
        return None
    usage = result["events"]["usage"]
    return int(usage["input_tokens"]) + int(usage["output_tokens"])


def report_markdown(
    summary: dict[str, Any],
    comparisons: list[dict[str, Any]],
    results: list[dict[str, Any]],
) -> str:
    lines = [
        "# Tugling behavioral evaluation",
        "",
        f"Run: `{summary['run_id']}`",
        "",
        "This is exploratory no-Tugling, released, and candidate evidence from isolated local runs.",
        "",
        "| Case | No Tugling | Released | Candidate | Candidate vs released | Tokens N / R / C | Seconds N / R / C |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for comparison in comparisons:
        control = comparison["control"]
        released = comparison["released"]
        candidate = comparison["candidate"]
        delta = (
            comparison["candidate_vs_released"]
            if released is not None
            else comparison["candidate_vs_control"]
        )
        seconds = [
            f"{item['elapsed_seconds']:.1f}" if item is not None else "-"
            for item in (control, released, candidate)
        ]
        tokens = [str(run_tokens(item)) if item is not None else "-" for item in (control, released, candidate)]
        lines.append(
            f"| {comparison['case_id']} | {display_number(comparison['control_score'])} | "
            f"{display_number(comparison['released_score'])} | {display_number(comparison['candidate_score'])} | "
            f"{display_number(delta, signed=True)} | {' / '.join(tokens)} | {' / '.join(seconds)} |"
        )
    if not comparisons:
        lines.append("| No complete comparisons | - | - | - | - | - | - |")
    metrics = summary["metrics"]
    lines.extend(
        [
            "",
            f"No-Tugling average: **{display_number(metrics['control_average'])}**",
            f"Released average: **{display_number(metrics['released_average'])}**",
            f"Candidate average: **{display_number(metrics['candidate_average'])}**",
            f"Candidate vs no Tugling: **{display_number(metrics['candidate_vs_control'], signed=True)}**",
            f"Candidate vs released: **{display_number(metrics['candidate_vs_released'], signed=True)}**",
            f"Candidate regressions vs released: **{metrics['released_regressions']}**",
            "",
            "## Gates",
            "",
        ]
    )
    for name, gate in summary["metrics"]["gates"].items():
        lines.append(f"- `{name}`: **{'PASS' if gate['passed'] else 'NOT MET'}**")
        for check, passed in gate["checks"].items():
            lines.append(f"  - {check}: {'pass' if passed else 'not met'}")
    lines.extend(
        [
            "",
            "## Run identity",
            "",
            f"- Candidate Tugling revision: `{summary['candidate_identity']['revision']}`",
            f"- Candidate content SHA-256: `{summary['candidate_identity']['content_sha256']}`",
            f"- Candidate worktree dirty: `{str(summary['candidate_identity']['worktree_dirty']).lower()}`",
            f"- Released Tugling revision: `{summary['released_identity']['revision'] if summary['released_identity'] else 'not run'}`",
            f"- Codex: `{summary['codex_version']}`",
            f"- Model: `{summary['model']}`",
            f"- Reasoning effort: `{summary['reasoning_effort']}`",
            f"- Conditions run: `{', '.join(summary['conditions'])}`",
            "",
            "Raw JSONL, independent grader results, Git state, and blinded artifacts are adjacent to this report.",
            "A gate passing does not prove remote checks, merge, deployment, or production behavior.",
            "",
        ]
    )
    failed = [result for result in results if not result["grade"]["passed"]]
    if failed:
        lines.extend(["## Runs needing review", ""])
        for result in failed:
            lines.append(
                f"- `{result['case_id']}` / `{result['condition']}` / attempt {result['attempt']}: "
                f"score {result['grade']['score']:.2f}, critical pass={result['grade']['critical_pass']}"
            )
        lines.append("")
    return "\n".join(lines)


def plugin_surface_changes(baseline: dict[str, Any]) -> dict[str, Any]:
    baseline_manifest = read_json(
        Path(baseline["plugin_root"]) / ".codex-plugin" / "plugin.json"
    )
    candidate_manifest = read_json(PLUGIN / ".codex-plugin" / "plugin.json")

    def capabilities(value: Any) -> list[str]:
        if not isinstance(value, dict) or not isinstance(value.get("interface"), dict):
            return []
        items = value["interface"].get("capabilities", [])
        return sorted(str(item) for item in items) if isinstance(items, list) else []

    def special_paths(root: Path, kind: str) -> list[str]:
        paths: list[str] = []
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(root)
            if kind == "hooks" and (
                "hooks" in relative.parts or path.name in {"hooks.json", "hooks.yaml"}
            ):
                paths.append(relative.as_posix())
            if kind == "permissions" and (
                path.name in {".mcp.json", ".app.json", "mcp.json"}
                or "mcpServers" in path.read_text(encoding="utf-8", errors="ignore")
            ):
                paths.append(relative.as_posix())
        return sorted(paths)

    baseline_root = Path(baseline["plugin_root"])
    changed = git_output(
        ROOT,
        "diff",
        "--name-only",
        baseline["revision"],
        "--",
        "plugins/tugling",
    ).splitlines()
    before_capabilities = capabilities(baseline_manifest)
    after_capabilities = capabilities(candidate_manifest)
    before_hooks = special_paths(baseline_root, "hooks")
    after_hooks = special_paths(PLUGIN, "hooks")
    before_permission_files = special_paths(baseline_root, "permissions")
    after_permission_files = special_paths(PLUGIN, "permissions")
    return {
        "changed_plugin_paths": changed,
        "capabilities_before": before_capabilities,
        "capabilities_after": after_capabilities,
        "permissions_changed": (
            before_capabilities != after_capabilities
            or before_permission_files != after_permission_files
        ),
        "permission_files_before": before_permission_files,
        "permission_files_after": after_permission_files,
        "hooks_changed": before_hooks != after_hooks,
        "hook_files_before": before_hooks,
        "hook_files_after": after_hooks,
    }


def privacy_scan() -> dict[str, Any]:
    tracked = git_output(ROOT, "ls-files").splitlines()
    sensitive_names = {"auth.json", "credentials", "credentials.json", "id_rsa"}
    findings: list[str] = []
    for relative in tracked:
        path = Path(relative)
        lowered = [part.lower() for part in path.parts]
        name = path.name.lower()
        if relative.startswith(".tugling/local/"):
            findings.append(relative)
        elif name in sensitive_names or name.endswith((".pem", ".key", ".p12")):
            findings.append(relative)
        elif any(part == ".env" for part in lowered):
            findings.append(relative)
    return {
        "passed": not findings,
        "tracked_sensitive_paths": sorted(set(findings)),
        "tracked_path_count": len(tracked),
    }


def policy_scan(pattern_file: Path | None) -> dict[str, Any]:
    if pattern_file is None:
        return {
            "configured": False,
            "passed": False,
            "pattern_file_sha256": None,
            "pattern_count": 0,
            "current_tree_matches": [],
            "history_matches": [],
        }
    try:
        raw = pattern_file.read_bytes()
    except OSError as exc:
        raise EvalError(f"policy pattern file: {exc}") from exc
    pattern_values = [
        line.strip()
        for line in raw.decode("utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not pattern_values:
        raise EvalError("policy pattern file contains no patterns")
    try:
        compiled = [re.compile(value, re.IGNORECASE) for value in pattern_values]
    except re.error as exc:
        raise EvalError(f"invalid policy pattern: {exc}") from exc

    current_matches: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if ".git" in relative.parts or "__pycache__" in relative.parts:
            continue
        if relative.parts[:2] == ("evals", "runs"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(pattern.search(text) for pattern in compiled):
            current_matches.append(relative.as_posix())

    history_matches: list[dict[str, str]] = []
    git_args = ["grep", "-I", "-l", "-i", "-E"]
    for value in pattern_values:
        git_args.extend(["-e", value])
    for revision in git_output(ROOT, "rev-list", "--all").splitlines():
        completed = run_command(
            ["git", *git_args, revision, "--", "."],
            cwd=ROOT,
        )
        if completed.returncode not in {0, 1}:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise EvalError(f"policy history scan failed for {revision}: {detail}")
        for line in completed.stdout.splitlines():
            path = line.split(":", 1)[-1]
            history_matches.append({"revision": revision, "path": path})

    return {
        "configured": True,
        "passed": not current_matches and not history_matches,
        "pattern_file_sha256": hashlib.sha256(raw).hexdigest(),
        "pattern_count": len(pattern_values),
        "current_tree_matches": sorted(set(current_matches)),
        "history_matches": [
            {"revision": revision, "path": path}
            for revision, path in sorted(
                {(item["revision"], item["path"]) for item in history_matches}
            )
        ],
    }


def condition_totals(results: list[dict[str, Any]]) -> dict[str, Any]:
    totals: dict[str, Any] = {}
    for condition in ("control", "released", "candidate"):
        selected = [result for result in results if result["condition"] == condition]
        if not selected:
            continue
        totals[condition] = {
            "runs": len(selected),
            "input_tokens": sum(
                int(result["events"]["usage"]["input_tokens"]) for result in selected
            ),
            "output_tokens": sum(
                int(result["events"]["usage"]["output_tokens"]) for result in selected
            ),
            "elapsed_seconds": round(
                sum(float(result["elapsed_seconds"]) for result in selected),
                3,
            ),
            "average_effective_score": round(
                sum(float(result["grade"]["effective_score"]) for result in selected)
                / len(selected),
                4,
            ),
        }
    return totals


def release_proof(
    *,
    summary: dict[str, Any],
    comparisons: list[dict[str, Any]],
    results: list[dict[str, Any]],
    policy: dict[str, Any],
    privacy: dict[str, Any],
    surface: dict[str, Any],
) -> dict[str, Any]:
    baseline = summary["released_identity"]
    candidate = summary["candidate_identity"]
    promotion = summary["metrics"]["gates"].get("promotion", {})
    checks = {
        "released_baseline_present": baseline is not None,
        "distinct_revisions": bool(baseline) and baseline["revision"] != candidate["revision"],
        "distinct_plugin_content": bool(baseline)
        and baseline["plugin_content_sha256"] != candidate["plugin_content_sha256"],
        "candidate_worktree_clean": not candidate["worktree_dirty"],
        "promotion_gate": bool(promotion.get("passed")),
        "privacy_scan": bool(privacy["passed"]),
        "policy_scan_configured": bool(policy["configured"]),
        "policy_scan": bool(policy["passed"]),
    }
    per_case = [
        {
            "case_id": item["case_id"],
            "attempt": item["attempt"],
            "control_score": item["control_score"],
            "released_score": item["released_score"],
            "candidate_score": item["candidate_score"],
            "candidate_vs_control": item["candidate_vs_control"],
            "candidate_vs_released": item["candidate_vs_released"],
            "released_regression": item["released_regression"],
            "candidate_critical_pass": item["candidate_critical_pass"],
        }
        for item in comparisons
    ]
    return {
        "schema_version": 1,
        "run_id": summary["run_id"],
        "created_at": summary["created_at"],
        "passed": all(checks.values()),
        "checks": checks,
        "candidate": candidate,
        "released": baseline,
        "reproducibility": {
            "codex_version": summary["codex_version"],
            "model": summary["model"],
            "reasoning_effort": summary["reasoning_effort"],
            "conditions": summary["conditions"],
            "attempts": summary["attempts"],
            "case_ids": summary["case_ids"],
        },
        "metrics": summary["metrics"],
        "per_case": per_case,
        "usage_and_latency": condition_totals(results),
        "plugin_surface_changes": surface,
        "privacy_scan": privacy,
        "policy_scan": policy,
    }


def release_proof_markdown(proof: dict[str, Any]) -> str:
    lines = [
        "# Tugling release proof",
        "",
        f"Status: **{'PASS' if proof['passed'] else 'NOT READY'}**",
        "",
        f"Candidate: `{proof['candidate']['revision']}`",
        f"Released baseline: `{proof['released']['revision'] if proof['released'] else 'missing'}`",
        "",
        "## Checks",
        "",
    ]
    for name, passed in proof["checks"].items():
        lines.append(f"- {name}: {'pass' if passed else 'not met'}")
    lines.extend(
        [
            "",
            "## Behavioral comparison",
            "",
            f"- Candidate average: {display_number(proof['metrics']['candidate_average'])}",
            f"- Candidate vs no Tugling: {display_number(proof['metrics']['candidate_vs_control'], signed=True)}",
            f"- Candidate vs released: {display_number(proof['metrics']['candidate_vs_released'], signed=True)}",
            f"- Regressions vs released: {proof['metrics']['released_regressions']}",
            "",
            "## Change surface",
            "",
            f"- Permissions changed: {str(proof['plugin_surface_changes']['permissions_changed']).lower()}",
            f"- Hooks changed: {str(proof['plugin_surface_changes']['hooks_changed']).lower()}",
            f"- Changed plugin paths: {len(proof['plugin_surface_changes']['changed_plugin_paths'])}",
            "",
            "Exact model settings, tokens, latency, per-case scores, scan digests, and gates are in `release-proof.json`.",
            "",
        ]
    )
    return "\n".join(lines)


def select_cases(suite: dict[str, Any], requested: list[str]) -> list[dict[str, Any]]:
    cases = suite["cases"]
    if not requested or requested == ["all"]:
        return cases
    by_id = {case["id"]: case for case in cases}
    unknown = [case_id for case_id in requested if case_id not in by_id]
    if unknown:
        raise EvalError(f"unknown case ids: {unknown}")
    return [by_id[case_id] for case_id in requested]


def conditions_for(value: str) -> list[str]:
    aliases = {
        "control": ["control"],
        "released": ["released"],
        "candidate": ["candidate"],
        "treatment": ["candidate"],
        "both": ["control", "candidate"],
        "all": ["control", "released", "candidate"],
    }
    return aliases[value]


def default_out_dir() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return ROOT / "evals" / "runs" / stamp


def run_evaluation(
    *,
    suite: dict[str, Any],
    cases: list[dict[str, Any]],
    args: argparse.Namespace,
    project_repo: Path | None = None,
) -> tuple[dict[str, Any], int]:
    codex_bin, codex_version = resolve_codex(args.codex_bin)
    out_dir = Path(args.out).resolve() if args.out else default_out_dir()
    if out_dir.exists() and any(out_dir.iterdir()):
        raise EvalError(f"output directory is not empty: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = out_dir.name
    conditions = conditions_for(args.condition)
    candidate_identity = repository_identity()
    baseline_scratch: Path | None = None
    baseline: dict[str, Any] | None = None
    released_identity: dict[str, Any] | None = None
    baseline_surface: dict[str, Any] | None = None
    if "released" in conditions:
        if not args.baseline_ref:
            raise EvalError("--baseline-ref is required when running the released condition")
        baseline_scratch = Path(tempfile.mkdtemp(prefix="tugling-released-baseline-"))
        baseline = resolve_release_baseline(args.baseline_ref, baseline_scratch)
        released_identity = {
            key: value
            for key, value in baseline.items()
            if key not in {"skills", "plugin_root"}
        }
        baseline_surface = plugin_surface_changes(baseline)

    sources: dict[str, tuple[Path | None, dict[str, Any] | None]] = {
        "control": (None, None),
        "released": (
            Path(baseline["skills"]) if baseline else None,
            released_identity,
        ),
        "candidate": (SKILLS, candidate_identity),
    }
    results: list[dict[str, Any]] = []
    try:
        total = len(cases) * len(conditions) * args.attempts
        completed_count = 0
        for case in cases:
            for attempt in range(1, args.attempts + 1):
                for condition in conditions:
                    completed_count += 1
                    print(
                        f"[{completed_count}/{total}] {case['id']} {condition} attempt {attempt}",
                        file=sys.stderr,
                        flush=True,
                    )
                    skills_source, condition_identity = sources[condition]
                    result = run_condition(
                        case=case,
                        condition=condition,
                        attempt=attempt,
                        out_dir=out_dir,
                        codex_bin=codex_bin,
                        codex_version=codex_version,
                        model=args.model,
                        reasoning_effort=args.reasoning_effort,
                        timeout=args.timeout,
                        keep_workspace=args.keep_workspaces,
                        project_repo=project_repo,
                        skills_source=skills_source,
                        condition_identity=condition_identity,
                    )
                    results.append(result)
    finally:
        if baseline_scratch is not None:
            shutil.rmtree(baseline_scratch, ignore_errors=True)

    comparisons = comparison_results(results)
    metrics = evaluate_gates(suite["gates"], comparisons)
    summary = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "candidate_identity": candidate_identity,
        "released_identity": released_identity,
        "codex_version": codex_version,
        "model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "conditions": conditions,
        "attempts": args.attempts,
        "case_ids": [case["id"] for case in cases],
        "project_revision": git_output(project_repo, "rev-parse", "HEAD") if project_repo else None,
        "metrics": metrics,
        "results": results,
    }
    write_json(out_dir / "summary.json", summary)
    write_blinded(out_dir, run_id, comparisons)
    (out_dir / "report.md").write_text(
        report_markdown(summary, comparisons, results),
        encoding="utf-8",
    )
    proof: dict[str, Any] | None = None
    if baseline is not None:
        policy_path = Path(args.policy_pattern_file).resolve() if args.policy_pattern_file else None
        proof = release_proof(
            summary=summary,
            comparisons=comparisons,
            results=results,
            policy=policy_scan(policy_path),
            privacy=privacy_scan(),
            surface=baseline_surface or {},
        )
        write_json(out_dir / "release-proof.json", proof)
        (out_dir / "release-proof.md").write_text(
            release_proof_markdown(proof),
            encoding="utf-8",
        )
    print(f"report: {out_dir / 'report.md'}")

    exit_code = 0
    if args.require_gate:
        gate = metrics["gates"].get(args.require_gate)
        if not gate or not gate["passed"]:
            exit_code = 2
        if args.require_gate == "promotion" and (proof is None or not proof["passed"]):
            exit_code = 2
    elif any(result["exit_code"] != 0 for result in results):
        exit_code = 1
    return summary, exit_code


def add_run_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--condition",
        choices=("control", "released", "candidate", "treatment", "both", "all"),
        default="both",
    )
    parser.add_argument("--baseline-ref")
    parser.add_argument("--policy-pattern-file")
    parser.add_argument("--attempts", type=int, default=1)
    parser.add_argument("--model", required=True)
    parser.add_argument("--reasoning-effort", choices=("low", "medium", "high", "xhigh"), required=True)
    parser.add_argument("--codex-bin")
    parser.add_argument("--out")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--keep-workspaces", action="store_true")
    parser.add_argument("--require-gate", choices=("dogfood", "promotion"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="validate the suite without calling a model")
    validate_parser.add_argument("--suite", default=str(DEFAULT_SUITE))

    run_parser = subparsers.add_parser(
        "run", help="run synthetic no-Tugling, released, and candidate cases"
    )
    run_parser.add_argument("--suite", default=str(DEFAULT_SUITE))
    run_parser.add_argument("--case", action="append", default=[])
    add_run_arguments(run_parser)

    project_parser = subparsers.add_parser("project", help="run one external case against a clean local project")
    project_parser.add_argument("--repo", required=True)
    project_parser.add_argument("--case-file", required=True)
    add_run_arguments(project_parser)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        if args.command == "validate":
            suite = read_json(Path(args.suite))
            errors = validate_suite(suite)
            if errors:
                for error in errors:
                    print(f"ERROR: {error}", file=sys.stderr)
                return 1
            print(f"Behavioral suite passed: {len(suite['cases'])} cases across {len(skill_names())} skills.")
            return 0

        if args.attempts < 1:
            raise EvalError("--attempts must be at least one")
        if args.timeout < 30:
            raise EvalError("--timeout must be at least 30 seconds")
        if args.command == "run":
            suite = read_json(Path(args.suite))
            errors = validate_suite(suite)
            if errors:
                raise EvalError("invalid suite: " + "; ".join(errors))
            cases = select_cases(suite, args.case)
            _, exit_code = run_evaluation(suite=suite, cases=cases, args=args)
            return exit_code

        project_repo = Path(args.repo).resolve()
        if not project_repo.is_dir():
            raise EvalError(f"project repository does not exist: {project_repo}")
        external = read_json(Path(args.case_file))
        case = external.get("case") if isinstance(external, dict) and "case" in external else external
        errors = validate_case(case, require_fixture=False)
        if errors:
            raise EvalError("invalid external case: " + "; ".join(errors))
        suite = {
            "schema_version": 1,
            "gates": {
                "dogfood": {
                    "comparison": "control",
                    "minimum_pairs": 1,
                    "minimum_candidate_score": 0.85,
                    "maximum_regressions": 0,
                    "minimum_delta": 0.0,
                    "minimum_control_lift": 0.0,
                },
                "promotion": {
                    "comparison": "control",
                    "minimum_pairs": 1,
                    "minimum_candidate_score": 0.9,
                    "maximum_regressions": 0,
                    "minimum_delta": 0.02,
                    "minimum_control_lift": 0.02,
                },
            },
            "cases": [case],
        }
        _, exit_code = run_evaluation(
            suite=suite,
            cases=[case],
            args=args,
            project_repo=project_repo,
        )
        return exit_code
    except EvalError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
