#!/usr/bin/env python3
"""Immutable task identities, receipts, admission and recovery for certification.

Two serial lanes own disjoint halves of the approved observed-token budget.
Receipts live in GitHub artifacts, never in a runner-local recovery database.
An admission is uploaded before a worker may call a model. Missing paid usage
blocks further admission; synthetic diagnostics can exercise recovery for free.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

try:
    from . import certify_release as cert
except ImportError:
    import certify_release as cert

MAX_RECORD_BYTES = 32 * 1024
MAX_RECORDS = 91 * 3 * 2
STATES = {"RESULT", "TASK_ERROR", "INFRA_ERROR"}


class TaskError(RuntimeError):
    pass


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def task_definitions() -> list[dict]:
    matrix = cert.gate.validate_matrix()
    tasks = [{"case_id": "public-install", "condition": "candidate", "trial": 1}]
    for case_id in matrix["required_case_ids"]:
        for trial in range(1, matrix["minimum_attempts"] + 1):
            for condition in matrix["conditions"]:
                tasks.append({"case_id": case_id, "condition": condition, "trial": trial})
    return [{"id": f"t{index:03d}", "lane": index % 2, **task}
            for index, task in enumerate(tasks)]


def manifest(request: dict, *, synthetic: bool = False) -> dict:
    body = {"schema_version": 1, "request": request, "synthetic": synthetic,
            "model": cert.MODEL, "effort": cert.EFFORT, "codex_version": cert.CODEX_VERSION,
            "tasks": task_definitions(), "max_attempts": 3, "lanes": 2}
    return {**body, "id": digest(body)}


def validate_manifest(value: dict) -> None:
    if not isinstance(value, dict) or type(value.get("synthetic")) is not bool:
        raise TaskError("invalid certification manifest")
    request = value.get("request")
    if not isinstance(request, dict) or value != manifest(request, synthetic=value["synthetic"]):
        raise TaskError("manifest differs from the reviewed task matrix or runtime")
    for key in ("candidate_sha", "baseline_sha", "controller_sha"):
        if not cert.controller.SHA.fullmatch(str(request.get(key, ""))):
            raise TaskError("invalid manifest revision")
    if request.get("repository") != cert.REPOSITORY or request.get("run_attempt") != 1:
        raise TaskError("invalid manifest authority")
    if not str(request.get("run_id", "")).isdigit():
        raise TaskError("invalid certification identity")
    for key in ("input_limit", "output_limit"):
        if type(request.get(key)) is not int or request[key] < 2:
            raise TaskError("invalid lane budget")


def task_for(plan: dict, task_id: str) -> dict:
    matches = [task for task in plan["tasks"] if task["id"] == task_id]
    if len(matches) != 1:
        raise TaskError("unknown task")
    return matches[0]


def record(plan: dict, task_id: str, attempt: int, kind: str, **fields: Any) -> dict:
    return {"schema_version": 1, "manifest_id": plan["id"], "task_id": task_id,
            "attempt": attempt, "kind": kind, **fields}


def valid_usage(value: Any) -> bool:
    keys = {"input_tokens", "output_tokens", "cached_input_tokens"}
    return (isinstance(value, dict) and set(value) == keys
            and all(type(v) is int and v >= 0 for v in value.values())
            and value["input_tokens"] > 0 and value["cached_input_tokens"] <= value["input_tokens"])


def validate_record(plan: dict, value: dict) -> None:
    base = {"schema_version", "manifest_id", "task_id", "attempt", "kind"}
    if not isinstance(value, dict) or value.get("manifest_id") != plan["id"]:
        raise TaskError("receipt belongs to another certification")
    task = task_for(plan, value.get("task_id"))
    if (value.get("schema_version") != 1 or type(value.get("attempt")) is not int
            or not 0 <= value["attempt"] < plan["max_attempts"]):
        raise TaskError("invalid receipt generation")
    if value.get("kind") == "admission":
        if set(value) != base:
            raise TaskError("unexpected admission fields")
        return
    if value.get("kind") != "result" or set(value) != base | {"state", "usage", "evidence"}:
        raise TaskError("unexpected receipt fields")
    if value["state"] not in STATES:
        raise TaskError("invalid task state")
    if value["usage"] is not None and not valid_usage(value["usage"]):
        raise TaskError("invalid reported usage")
    if value["state"] != "RESULT":
        if value["evidence"] is not None:
            detail = value["evidence"]
            if (not isinstance(detail, dict) or set(detail) != {"stage", "category"}
                    or detail["stage"] not in {"runtime", "candidate", "installation", "evaluation"}
                    or detail["category"] not in {"TaskError", "CleanRoomError", "ControllerError", "EvalError",
                         "PermissionError", "FileNotFoundError", "TimeoutExpired", "BudgetError", "unexpected"}):
                raise TaskError("invalid fixed failure category")
        return
    if not valid_usage(value["usage"]):
        raise TaskError("completed verification requires reported usage")
    evidence = value["evidence"]
    if task["case_id"] == "public-install":
        expected = {"passed", "checks", "mode", "source", "plugin", "codex", "live"}
        if not isinstance(evidence, dict) or set(evidence) != expected:
            raise TaskError("invalid installation evidence")
        # Validate the public projection by re-projecting it. No arbitrary model text.
        if evidence != clean_evidence(evidence, plan):
            raise TaskError("installation evidence contains unexpected data")
    else:
        if not isinstance(evidence, dict) or set(evidence) != {"score", "critical_pass", "passed", "elapsed_seconds"}:
            raise TaskError("invalid behavioral evidence")
        if any(type(evidence[key]) is not bool for key in ("critical_pass", "passed")):
            raise TaskError("invalid behavioral verdict")
        for key, maximum in (("score", 1), ("elapsed_seconds", 600)):
            if (type(evidence[key]) not in (int, float) or not math.isfinite(evidence[key])
                    or not 0 <= evidence[key] <= maximum):
                raise TaskError("invalid behavioral measurement")


def clean_evidence(raw: dict, plan: dict) -> dict:
    names = ("marketplace_add", "plugin_add", "exact_public_revision", "isolated_install_path",
             "marketplace_package_matches_candidate", "installed_plugin_matches_candidate",
             "live_exit_zero", "live_skill_selected", "live_repository_native_contract",
             "live_no_false_pass", "live_no_edits_reported", "live_repository_unchanged",
             "live_native_gate_not_run")
    live = raw.get("live", {})
    # Identities come from trusted controller inputs, never assistant strings.
    revision = plan["request"]["candidate_sha"]
    plugin = raw.get("plugin", {})
    if not isinstance(plugin, dict) or set(plugin) != {"name", "version", "content_sha256", "skills"}:
        raise TaskError("invalid public package identity")
    if (plugin["name"] != "tugling" or not cert.controller.VERSION.fullmatch(str(plugin["version"]))
            or not cert.controller.DIGEST.fullmatch(str(plugin["content_sha256"]))
            or plugin["skills"] != sorted(cert.behavioral.skill_names())):
        raise TaskError("invalid public package identity")
    checks = {key: raw.get("checks", {}).get(key) is True for key in names}
    return {"passed": raw.get("passed") is True and all(checks.values()),
            "checks": checks,
            "mode": "public-cli-live",
            "source": {"repository": plan["request"]["repository"],
                       "requested_revision": revision, "resolved_revision": revision},
            "plugin": plugin, "codex": {"version": f"codex-cli {cert.CODEX_VERSION}"},
            "live": {"ran": live.get("ran") is True,
                     "repository_unchanged": live.get("repository_unchanged") is True,
                     "selected_skill": "repo-verify" if live.get("selected_skill") == "repo-verify" else None,
                     "verification_order": "repository-native-first" if live.get("verification_order") == "repository-native-first" else None,
                     "installed_skill_read_observed": live.get("installed_skill_read_observed") is True,
                     "model": cert.MODEL, "reasoning_effort": cert.EFFORT}}


def load_records(directory: Path, plan: dict) -> list[dict]:
    files = sorted(directory.rglob("*.json")) if directory.exists() else []
    if len(files) > MAX_RECORDS:
        raise TaskError("too many receipts")
    result = []
    seen = {}
    for path in files:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_RECORD_BYTES:
            raise TaskError("receipt must be bounded regular JSON")
        value = json.loads(path.read_text())
        validate_record(plan, value)
        key = (value["task_id"], value["attempt"], value["kind"])
        if key in seen and seen[key] != value:
            raise TaskError("conflicting receipts")
        if key not in seen:
            seen[key] = value
            result.append(value)
    return result


def accepted(records: list[dict]) -> dict[str, dict]:
    results = {}
    for item in records:
        if item["kind"] != "result" or item["state"] == "INFRA_ERROR":
            continue
        if item["task_id"] in results and results[item["task_id"]] != item:
            raise TaskError("multiple terminal outcomes for one task")
        results[item["task_id"]] = item
    return results


def accounting(plan: dict, records: list[dict], lane: int | None = None) -> dict:
    chosen = [r for r in records if lane is None or task_for(plan, r["task_id"])["lane"] == lane]
    admissions = {(r["task_id"], r["attempt"]) for r in chosen if r["kind"] == "admission"}
    outcomes = {(r["task_id"], r["attempt"]): r for r in chosen if r["kind"] == "result"}
    if set(outcomes) - admissions:
        raise TaskError("result without durable admission")
    unknown = [key for key in admissions if key not in outcomes or outcomes[key]["usage"] is None]
    totals = {key: sum(r["usage"][key] for r in outcomes.values() if r["usage"] is not None)
              for key in ("input_tokens", "output_tokens", "cached_input_tokens")}
    return {**totals, "unaccounted_attempts": len(unknown)}


def admit(plan: dict, records: list[dict], task_id: str, attempt: int) -> dict | None:
    validate_manifest(plan)
    task = task_for(plan, task_id)
    if task_id in accepted(records):
        return None
    if type(attempt) is not int or not 0 <= attempt < plan["max_attempts"]:
        raise TaskError("recovery exhausted")
    if any(r["task_id"] == task_id and r["attempt"] == attempt for r in records):
        raise TaskError("attempt already admitted; never replay model execution")
    usage = accounting(plan, records, task["lane"])
    if usage["unaccounted_attempts"] and not plan["synthetic"]:
        raise TaskError("ACCOUNTING_BLOCKED: an admitted paid task has missing usage")
    for key in ("input", "output"):
        limit = plan["request"][f"{key}_limit"] // 2
        if usage[f"{key}_tokens"] >= limit:
            raise TaskError("BUDGET_BLOCKED: lane token threshold reached")
    return record(plan, task_id, attempt, "admission")


def recovery(plan: dict, records: list[dict], attempt: int) -> list[dict]:
    validate_manifest(plan)
    if not 1 <= attempt < plan["max_attempts"]:
        raise TaskError("invalid recovery round")
    if any(r["attempt"] >= attempt for r in records):
        raise TaskError("stale recovery planner")
    completed = accepted(records)
    blocked_lanes = set()
    for lane in (0, 1):
        usage = accounting(plan, records, lane)
        if ((usage["unaccounted_attempts"] and not plan["synthetic"])
                or any(usage[f"{key}_tokens"] >= plan["request"][f"{key}_limit"] // 2
                       for key in ("input", "output"))):
            blocked_lanes.add(lane)
    pending = []
    for task in plan["tasks"]:
        if task["id"] in completed or task["lane"] in blocked_lanes:
            continue
        # Missing admission means the task never became eligible to spend.
        prior = [r for r in records if r["task_id"] == task["id"]]
        if any(r["attempt"] >= attempt for r in prior):
            raise TaskError("stale recovery planner")
        if not plan["synthetic"] and any(r["kind"] == "admission" for r in prior):
            results = {(r["attempt"]): r for r in prior if r["kind"] == "result"}
            if any(r["attempt"] not in results or results[r["attempt"]]["usage"] is None
                   for r in prior if r["kind"] == "admission"):
                continue
        pending.append(task)
    return pending
