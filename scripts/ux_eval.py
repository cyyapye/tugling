#!/usr/bin/env python3
"""Freeze and review local UX correction diagnostics; never run or certify a model."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import re
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUITE = ROOT / "evals/ux/cases.json"
CONDITIONS = ("control", "released", "candidate")
ID = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")


class UXError(ValueError):
    pass


def require(value, message):
    if not value:
        raise UXError(message)


def read(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise UXError(f"cannot read JSON: {path}: {exc}") from exc


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def relative_file(root, name):
    require(isinstance(name, str) and name, "file reference must be nonempty")
    rel = Path(name)
    require(not rel.is_absolute() and ".." not in rel.parts, "file reference must be relative")
    path = root / rel
    require(path.is_file() and not any((root / Path(*rel.parts[:i])).is_symlink()
                                     for i in range(1, len(rel.parts) + 1)),
            f"missing file or symlink: {name}")
    require(path.resolve().is_relative_to(root.resolve()), "file escapes root")
    return path


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def load_suite(path):
    path = Path(path)
    suite = read(path)
    require(isinstance(suite, dict) and suite.get("schema_version") == 1, "invalid suite version")
    require(ID.fullmatch(suite.get("id", "")), "invalid suite id")
    require(suite.get("stage") in ("development", "confirmation"), "invalid study stage")
    author = suite.get("task_author", {})
    require(isinstance(author, dict) and isinstance(author.get("id"), str) and author["id"],
            "task author identity required")
    require(type(author.get("candidate_aware")) is bool, "candidate awareness must be explicit")
    cases = suite.get("cases")
    require(isinstance(cases, list) and cases, "cases must be nonempty")
    ids = set()
    for case in cases:
        require(isinstance(case, dict) and ID.fullmatch(case.get("id", "")), "invalid case id")
        require(case["id"] not in ids, "duplicate case id")
        ids.add(case["id"])
        require(case.get("split") in ("development", "holdout"), "invalid case split")
        require(isinstance(case.get("provenance"), str) and case["provenance"], "case provenance required")
        for field in ("task", "context", "fixture", "checks"):
            relative_file(path.parent, case.get(field))
        require(Path(case["fixture"]).suffix == ".html", "fixture must be self-contained HTML")
        replacements = case.get("byte_replacements", {})
        require(isinstance(replacements, dict) and all(isinstance(k, str) and k
                and isinstance(v, str) and v for k, v in replacements.items()), "invalid byte replacement oracle")
        if replacements:
            original = relative_file(path.parent, case["fixture"]).read_text()
            require(all(original.count(k) == 1 for k in replacements), "byte oracle replacements must be unique")
        criteria = case.get("criteria")
        require(isinstance(criteria, list) and criteria, "criteria must be nonempty")
        units = set()
        for unit in criteria:
            require(isinstance(unit, dict) and ID.fullmatch(unit.get("id", "")), "invalid unit id")
            require(unit["id"] not in units, "duplicate unit id; count across widths once")
            units.add(unit["id"])
            require(unit.get("category") in ("target", "guardrail"), "invalid category")
            require(unit.get("severity") in ("major", "critical"), "invalid severity")
            require(unit.get("evidence_kind") in ("render", "interaction", "storage", "bytes"),
                    "invalid evidence kind")
            require(isinstance(unit.get("criterion"), str) and unit["criterion"], "criterion required")
    require(any(u["category"] == "target" for c in cases for u in c["criteria"]), "target criteria required")
    require(any(u["category"] == "guardrail" for c in cases for u in c["criteria"]), "guardrails required")
    if suite["stage"] == "confirmation":
        require(not author["candidate_aware"], "confirmation needs a candidate-blind task author")
        relative_file(path.parent, author.get("evidence"))
        require(any(c["split"] == "holdout" and any(u["category"] == "target" for u in c["criteria"])
                    for c in cases), "confirmation needs a fresh target holdout")
    return suite


def validate_runtime(runtime, suite):
    require(isinstance(runtime, dict), "runtime must be an object")
    for field in ("model", "effort", "cli_version", "browser_version", "timezone", "locale",
                  "operator_id", "candidate_author_id"):
        require(isinstance(runtime.get(field), str) and runtime[field], f"runtime {field} required")
    attempts = runtime.get("attempts")
    require(integer(attempts, 1) and attempts <= 3, "attempts must be 1..3")
    require(integer(runtime.get("timeout_seconds"), 30) and runtime["timeout_seconds"] <= 600,
            "timeout must be 30..600 seconds")
    repairs = runtime.get("repair_rounds", 0)
    require(integer(repairs) and repairs <= 2, "repair_rounds must be 0..2")
    calls = len(suite["cases"]) * len(CONDITIONS) * attempts * (1 + repairs)
    require(calls <= 36 and runtime.get("max_calls") == calls, "max_calls must equal the bounded full matrix")
    for field in ("max_input_tokens", "max_output_tokens"):
        require(integer(runtime.get(field), 1), f"positive {field} admission limit required")
    views = runtime.get("viewports")
    require(isinstance(views, list) and len(views) >= 2 and len(set(views)) == len(views)
            and all(isinstance(v, str) and re.fullmatch(r"[1-9][0-9]*x[1-9][0-9]*", v) for v in views),
            "distinct desktop/phone viewport identities required")
    widths = [int(view.split("x")[0]) for view in views]
    require(any(width <= 480 for width in widths) and any(width >= 1024 for width in widths),
            "viewports must include a phone width <=480 and desktop width >=1024")
    require(isinstance(runtime.get("observer_files"), list) and runtime["observer_files"],
            "freeze the actual observer code before admission")
    sources = runtime.get("sources", {})
    require(isinstance(sources, dict) and set(sources) == {"released", "candidate"}, "exact sources required")
    for source in sources.values():
        require(isinstance(source, dict) and re.fullmatch(r"[0-9a-f]{40}", source.get("commit", ""))
                and SHA.fullmatch(source.get("skills_sha256", "")), "full source commit and skills digest required")
    require(sources["released"]["skills_sha256"] != sources["candidate"]["skills_sha256"],
            "candidate skill content must differ from released")
    if suite["stage"] == "confirmation":
        require(attempts == 3, "confirmation requires three attempts; one attempt is exploratory")
        require(suite["task_author"]["id"] not in (runtime["operator_id"], runtime["candidate_author_id"]),
                "confirmation task author must be independent of candidate author and operator")


def inventory(root):
    files = {}
    for path in sorted(root.rglob("*")):
        require(not path.is_symlink(), "symlinks forbidden in frozen evidence")
        if path.is_file() and path != root / "freeze.json":
            files[path.relative_to(root).as_posix()] = digest(path)
    return files


PROBE_FILES = ("before", "source_readback", "expected", "after", "events", "execution", "stderr")


def validate_preflight(receipt, root):
    """Require retained builder read/edit evidence, not only a working browser."""
    require(receipt.get("passed") is True, "passing preflight required")
    probe = receipt.get("builder_probe", {})
    require(isinstance(probe, dict) and all(name in probe for name in PROBE_FILES),
            "preflight requires a builder source-read and artifact-edit probe")
    files = {name: relative_file(root, probe[name]) for name in PROBE_FILES}
    before, expected, after = (files[name].read_bytes() for name in ("before", "expected", "after"))
    require(before == files["source_readback"].read_bytes(), "builder source readback differs from input")
    require(before != expected and after == expected,
            "builder must deliver the exact nonempty preflight edit")
    execution = read(files["execution"])
    require(execution.get("exit_code") == 0 and execution.get("timed_out") is False
            and execution.get("cleanup_complete") is True, "builder preflight execution incomplete")
    rows = [json.loads(line) for line in files["events"].read_text().splitlines() if line.strip()]
    require(all(isinstance(row, dict) for row in rows), "malformed preflight event")
    require(not any(row.get("type") in ("error", "turn.failed") for row in rows),
            "builder preflight runtime failed")
    usages = [row.get("usage") for row in rows if row.get("type") == "turn.completed"]
    require(len(usages) == 1 and isinstance(usages[0], dict)
            and integer(usages[0].get("input_tokens"), 1)
            and integer(usages[0].get("cached_input_tokens"))
            and integer(usages[0].get("output_tokens"))
            and usages[0]["cached_input_tokens"] <= usages[0]["input_tokens"],
            "builder preflight usage missing or invalid")
    items = [row.get("item", {}) for row in rows if row.get("type") == "item.completed"]
    require(any(item.get("type") == "file_change" and item.get("status") == "completed"
                or item.get("type") == "command_execution" and item.get("exit_code") == 0
                for item in items), "builder preflight needs an observed successful native edit tool")
    return files


def artifact_write_failed(rows, stderr, artifact):
    """Recognize a denied write to this artifact; ordinary patch misses differ."""
    target = Path(artifact).resolve()
    prefix = "Failed to write file "
    denied_paths = [Path(line.strip()[len(prefix):]) for line in stderr.splitlines()
                    if line.strip().startswith(prefix)]
    denied = any(path.is_absolute() and path.resolve() == target for path in denied_paths)
    return denied and any(
        row.get("type") == "item.completed" and row.get("item", {}).get("type") == "file_change"
        and row["item"].get("status") == "failed"
        and any(Path(change.get("path", "")).is_absolute()
                and Path(change["path"]).resolve() == target for change in row["item"].get("changes", []))
        for row in rows)


def freeze(suite_path, runtime_path, out):
    suite_path, out = Path(suite_path), Path(out)
    suite, runtime = load_suite(suite_path), read(runtime_path)
    validate_runtime(runtime, suite)
    # No live admission happens here. Preflight/calibration evidence is mandatory
    # before a producer starts any model, and is hashed with the observer checks.
    preflight_files = {}
    for name in ("preflight", "calibration"):
        receipt = read(relative_file(Path(runtime_path).parent, runtime.get(name)))
        require(receipt.get("passed") is True, f"passing {name} required")
        if name == "preflight":
            preflight_files = validate_preflight(receipt, Path(runtime_path).parent)
        if name == "calibration":
            require(set(receipt.get("controls", [])) >= {
                "valid-alternative", "lost-edit", "meaning-loss", "unprotected-erasure"},
                "calibration must accept alternatives and reject substantive bad controls")
    out.mkdir(parents=True, exist_ok=False)
    frozen_suite = json.loads(json.dumps(suite))
    for case in frozen_suite["cases"]:
        target = out / "inputs" / case["id"]
        target.mkdir(parents=True)
        for field, name in (("task", "task.md"), ("context", "context.md"),
                            ("fixture", "index.html"), ("checks", "checks.md")):
            shutil.copyfile(relative_file(suite_path.parent, case[field]), target / name)
            case[field] = (target / name).relative_to(out).as_posix()
    if suite["stage"] == "confirmation":
        shutil.copyfile(relative_file(suite_path.parent, suite["task_author"]["evidence"]), out / "author-evidence.md")
        frozen_suite["task_author"]["evidence"] = "author-evidence.md"
    for name in ("preflight", "calibration"):
        shutil.copyfile(relative_file(Path(runtime_path).parent, runtime[name]), out / f"{name}.json")
        runtime[name] = f"{name}.json"
    preflight = read(out / "preflight.json")
    for name, source in preflight_files.items():
        dest = out / "preflight-evidence" / name / source.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        preflight["builder_probe"][name] = dest.relative_to(out).as_posix()
    write(out / "preflight.json", preflight)
    observer_files = []
    for index, name in enumerate(runtime["observer_files"]):
        source = relative_file(Path(runtime_path).parent, name)
        dest = out / "observers" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        observer_files.append(dest.relative_to(out).as_posix())
    runtime["observer_files"] = observer_files
    # Retain the exact evaluator, not merely its hash, for future reproduction.
    shutil.copyfile(Path(__file__), out / "evaluator.py")
    write(out / "suite.json", frozen_suite)
    write(out / "runtime.json", runtime)
    schedule = []
    for attempt in range(1, runtime["attempts"] + 1):
        for index, case in enumerate(suite["cases"]):
            start = (index + attempt - 1) % len(CONDITIONS)
            order = CONDITIONS[start:] + CONDITIONS[:start]
            schedule.extend({"case": case["id"], "attempt": attempt, "condition": arm} for arm in order)
    write(out / "schedule.json", schedule)
    write(out / "freeze.json", {"schema_version": 1, "files": inventory(out)})
    return digest(out / "freeze.json")


def check_freeze(root):
    root = Path(root)
    require(read(root / "freeze.json").get("files") == inventory(root), "frozen evaluator/input/runtime drift")
    require(digest(Path(__file__)) == digest(root / "evaluator.py"),
            "running evaluator differs from frozen evaluator; use the frozen code or label a new regrade")
    suite, runtime = load_suite(root / "suite.json"), read(root / "runtime.json")
    validate_runtime(runtime, suite)
    return suite, runtime, digest(root / "freeze.json")


def case_for(suite, case_id):
    matches = [c for c in suite["cases"] if c["id"] == case_id]
    require(len(matches) == 1, "unknown case")
    return matches[0]


def capture(frozen, records, case_id, condition, attempt, phase, artifact, events, receipt, screenshots=(), *, stderr):
    suite, runtime, frozen_sha = check_freeze(frozen)
    case_for(suite, case_id)
    require(condition in CONDITIONS and integer(attempt, 1) and attempt <= runtime["attempts"], "unknown trial")
    require(phase in ("first-delivery", "repair-1", "repair-2"), "unknown delivery phase")
    require(phase == "first-delivery" or int(phase[-1]) <= runtime.get("repair_rounds", 0),
            "repair was not included in the frozen call budget")
    info = read(receipt)
    require(Path(artifact).is_file() and not Path(artifact).is_symlink(), "artifact must be a regular file")
    require(info.get("freeze_sha256") == frozen_sha, "receipt belongs to another freeze")
    require(info.get("model") == runtime["model"] and info.get("effort") == runtime["effort"], "model settings drift")
    require(info.get("case") == case_id and info.get("condition") == condition and info.get("attempt") == attempt
            and info.get("phase") == phase, "receipt trial identity mismatch")
    require(info.get("runtime_sha256") == digest(Path(frozen) / "runtime.json")
            and info.get("fixture_sha256") == digest(Path(frozen) / case_for(suite, case_id)["fixture"]),
            "receipt runtime/fixture binding mismatch")
    expected_source = None if condition == "control" else runtime["sources"][condition]["skills_sha256"]
    require(info.get("skills_sha256") == expected_source, "receipt skill-source binding mismatch")
    if phase == "first-delivery":
        require(info.get("user_feedback_received") is False, "first delivery must precede user feedback")
    event_rows = []
    for line in Path(events).read_text().splitlines():
        if line.strip():
            value = json.loads(line)
            require(isinstance(value, dict), "malformed event")
            event_rows.append(value)
    completions = [e.get("usage") for e in event_rows if e.get("type") == "turn.completed"]
    usage = completions[0] if len(completions) == 1 else None
    known = isinstance(usage, dict) and all(integer(usage.get(k)) for k in (
        "input_tokens", "cached_input_tokens", "output_tokens"))
    known = known and usage["cached_input_tokens"] <= usage["input_tokens"]
    known = known and usage["input_tokens"] > 0
    complete = (info.get("exit_code") == 0 and info.get("timed_out") is False
                and info.get("cleanup_complete") is True and known
                and not any(e.get("type") in ("turn.failed", "error") for e in event_rows))
    write_failure = (digest(artifact) == info["fixture_sha256"]
                     and artifact_write_failed(event_rows, Path(stderr).read_text(), artifact))
    complete = complete and not write_failure
    target = Path(records) / case_id / condition / str(attempt) / phase
    if phase != "first-delivery":
        prior = target.parent / ("first-delivery" if phase == "repair-1" else "repair-1") / "capture.json"
        require(prior.is_file(), "capture first delivery and preceding repair before later feedback")
    retained = check_record_budget(records, frozen_sha, runtime)
    within_budget = (retained["calls"] + 1 <= runtime["max_calls"] and known
                     and retained["input_tokens"] + usage["input_tokens"] <= runtime["max_input_tokens"]
                     and retained["output_tokens"] + usage["output_tokens"] <= runtime["max_output_tokens"])
    complete = complete and within_budget
    target.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(artifact, target / "index.html")
    shutil.copyfile(events, target / "events.jsonl")
    shutil.copyfile(stderr, target / "stderr.txt")
    shutil.copyfile(receipt, target / "producer-receipt.json")
    names = []
    for i, screenshot in enumerate(screenshots):
        require(Path(screenshot).suffix.lower() == ".png", "screenshots must be PNG")
        name = f"screen-{i + 1}.png"
        shutil.copyfile(screenshot, target / name)
        names.append(name)
    value = {"case": case_id, "condition": condition, "attempt": attempt, "phase": phase,
             "freeze_sha256": frozen_sha, "complete": complete, "usage": usage if known else None,
             "unresolved_artifact_write_failure": bool(write_failure),
             "within_frozen_budget": bool(within_budget),
             "screenshots": names, "files": inventory(target)}
    write(target / "capture.json", value)
    return value


def load_capture(path, frozen_sha):
    value = read(path / "capture.json")
    files = inventory(path)
    files.pop("capture.json", None)
    require(value.get("files") == files and value.get("freeze_sha256") == frozen_sha, "capture drift")
    return value


def check_record_budget(records, frozen_sha, runtime):
    """Independently account all retained phases, including earlier repairs."""
    totals = {"input_tokens": 0, "output_tokens": 0}
    calls = 0
    for path in Path(records).rglob("capture.json"):
        value = load_capture(path.parent, frozen_sha)
        usage = value.get("usage")
        require(value.get("complete") is True and isinstance(usage, dict)
                and integer(usage.get("input_tokens"), 1)
                and integer(usage.get("cached_input_tokens"))
                and integer(usage.get("output_tokens"))
                and usage["cached_input_tokens"] <= usage["input_tokens"],
                "incomplete delivery or unknown usage; stop admission")
        calls += 1
        for name in totals:
            totals[name] += usage[name]
    require(calls <= runtime["max_calls"] and totals["input_tokens"] <= runtime["max_input_tokens"]
            and totals["output_tokens"] <= runtime["max_output_tokens"],
            "retained calls exceed frozen usage/call budget; preserve attempts and stop")
    return dict(totals, calls=calls)


def bundle(frozen, records, out, key_out, phase="first-delivery"):
    suite, runtime, frozen_sha = check_freeze(frozen)
    check_record_budget(records, frozen_sha, runtime)
    out, key_out = Path(out).resolve(), Path(key_out).resolve()
    require(not key_out.is_relative_to(out), "condition key must be outside reviewer bundle")
    require(not key_out.exists(), "never overwrite a condition key")
    trials = []
    for case in suite["cases"]:
        for attempt in range(1, runtime["attempts"] + 1):
            for condition in CONDITIONS:
                path = Path(records) / case["id"] / condition / str(attempt) / phase
                require(path.is_dir(), "matrix incomplete; preserve missing attempts, do not substitute")
                value = load_capture(path, frozen_sha)
                require(value["complete"], "incomplete delivery or unknown usage; stop admission")
                require((value["case"], value["attempt"], value["condition"], value["phase"])
                        == (case["id"], attempt, condition, phase), "capture identity mismatch")
                trials.append((case, path, value))
    random.SystemRandom().shuffle(trials)
    out.mkdir(parents=True, exist_ok=False)
    key = {"freeze_sha256": frozen_sha, "phase": phase, "trials": {}}
    for index, (case, path, value) in enumerate(trials):
        label = f"sample-{index + 1:03d}"
        dest = out / label
        dest.mkdir()
        for field in ("task", "context", "checks"):
            shutil.copyfile(Path(frozen) / case[field], dest / f"{field}.md")
        # The common original carries the complete source population/facts;
        # task prose may only describe selected examples. It reveals no arm.
        shutil.copyfile(Path(frozen) / case["fixture"], dest / "original.html")
        shutil.copyfile(path / "index.html", dest / "index.html")
        for name in value["screenshots"]:
            shutil.copyfile(path / name, dest / name)
        # Conditions, skills, traces, scores, builder prose and sources stay out.
        write(dest / "review-template.json", {
            "artifact_sha256": digest(dest / "index.html"),
            "units": [{"id": u["id"], "criterion": u["criterion"], "outcome": "unknown",
                       "finding": "", "evidence": []} for u in case["criteria"]]})
        key["trials"][label] = {"case": case["id"], "condition": value["condition"],
                                "attempt": value["attempt"], "capture_sha256": digest(path / "capture.json")}
    key["bundle_files"] = inventory(out)
    write(key_out, key)
    return key


def assess(frozen, records, review_bundle, key_path):
    suite, runtime, frozen_sha = check_freeze(frozen)
    check_record_budget(records, frozen_sha, runtime)
    key = read(key_path)
    require(key.get("freeze_sha256") == frozen_sha, "review key belongs to another freeze")
    require(key.get("phase") in ("first-delivery", "repair-1", "repair-2"), "invalid review phase")
    root = Path(review_bundle)
    for name, sha in key["bundle_files"].items():
        require(digest(relative_file(root, name)) == sha, "review input drift")
    review = read(root / "review.json")
    require(SHA.fullmatch(review.get("key_sha256", "")) and review["key_sha256"] == digest(key_path),
            "review must bind the unopened sealed condition key digest")
    require(isinstance(review.get("reviewer_id"), str) and review["reviewer_id"], "reviewer identity required")
    require(type(review.get("blind_attested")) is bool, "reviewer must record whether conditions were hidden")
    require(set(review.get("samples", {})) == set(key["trials"]), "review matrix incomplete")
    # Keys/capture contents are cross-checked; duplicated or selectively omitted
    # trials cannot satisfy replication or supply apparent improvement.
    expected = {(c["id"], arm, a) for c in suite["cases"] for arm in CONDITIONS
                for a in range(1, runtime["attempts"] + 1)}
    identities = [(v["case"], v["condition"], v["attempt"]) for v in key["trials"].values()]
    require(len(identities) == len(expected) and set(identities) == expected, "key matrix mismatch")
    totals = {arm: {"target_corrections": 0, "guardrail_failures": 0, "critical_failures": 0}
              for arm in CONDITIONS}
    case_scores, usages, unknown = {}, {arm: {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}
                                      for arm in CONDITIONS}, False
    for label, identity in key["trials"].items():
        case = case_for(suite, identity["case"])
        path = Path(records) / case["id"] / identity["condition"] / str(identity["attempt"]) / key["phase"]
        capture_info = load_capture(path, frozen_sha)
        require(digest(path / "capture.json") == identity["capture_sha256"] and capture_info["complete"],
                "review capture mismatch or incomplete")
        item = review["samples"][label]
        require(item.get("artifact_sha256") == digest(path / "index.html"), "review artifact mismatch")
        units = item.get("units", [])
        require(isinstance(units, list) and len(units) == len(case["criteria"])
                and {u.get("id") for u in units} == {u["id"] for u in case["criteria"]},
                "unit coverage must be complete, without duplicates or per-viewport inflation")
        by_id = {u["id"]: u for u in units}
        failed = 0
        for criterion in case["criteria"]:
            unit = by_id[criterion["id"]]
            outcome = unit.get("outcome")
            require(outcome in ("pass", "fail", "unknown"), "invalid outcome")
            require(isinstance(unit.get("finding"), str) and unit["finding"], "concrete review finding required")
            evidence = unit.get("evidence", [])
            require(isinstance(evidence, list), "evidence must be an array")
            views = set()
            for observation in evidence:
                require(isinstance(observation, dict) and observation.get("kind") == criterion["evidence_kind"],
                        "evidence kind must demonstrate the criterion")
                relative_file(root / label, observation.get("file"))
                view = observation.get("viewport")
                require(view in runtime["viewports"] or (view == "all" and criterion["evidence_kind"] == "bytes"),
                        "unknown viewport")
                views.add(view)
            if outcome != "unknown":
                require(views == set(runtime["viewports"]) or views == {"all"},
                        "a pass/failure needs actual evidence at each frozen viewport")
                if criterion["evidence_kind"] == "bytes":
                    require(case.get("byte_replacements"), "byte criterion needs an executable oracle")
                    expected_bytes = (Path(frozen) / case["fixture"]).read_bytes()
                    for old, new in case["byte_replacements"].items():
                        expected_bytes = expected_bytes.replace(old.encode(), new.encode())
                    actual = "pass" if (path / "index.html").read_bytes() == expected_bytes else "fail"
                    require(outcome == actual, "byte review contradicts executable scope oracle")
            unknown = unknown or outcome == "unknown"
            if outcome == "fail":
                score = totals[identity["condition"]]
                if criterion["severity"] == "critical":
                    score["critical_failures"] += 1
                if criterion["category"] == "target":
                    score["target_corrections"] += 1
                    failed += 1
                else:
                    score["guardrail_failures"] += 1
        case_scores[(case["id"], identity["condition"], identity["attempt"])] = failed
        for name in usages[identity["condition"]]:
            usages[identity["condition"]][name] += capture_info["usage"].get(name, 0)
    baseline, candidate = totals["released"], totals["candidate"]
    regressions = [c["id"] for c in suite["cases"] if
                   sum(case_scores[(c["id"], "candidate", a)] for a in range(1, runtime["attempts"] + 1)) >
                   sum(case_scores[(c["id"], "released", a)] for a in range(1, runtime["attempts"] + 1))]
    holdout_lift = any(c["split"] == "holdout" and
                      sum(case_scores[(c["id"], "candidate", a)] for a in range(1, runtime["attempts"] + 1)) <
                      sum(case_scores[(c["id"], "released", a)] for a in range(1, runtime["attempts"] + 1))
                      for c in suite["cases"])
    if unknown:
        finding = "INCOMPLETE"
    elif candidate["critical_failures"] or candidate["guardrail_failures"] or regressions:
        finding = "REGRESSION"
    elif baseline["target_corrections"] == 0:
        finding = "SATURATED"
    elif candidate["target_corrections"] < baseline["target_corrections"]:
        finding = "IMPROVEMENT_SIGNAL"
    else:
        finding = "NO_MEASURED_IMPROVEMENT"
    reviewer = review["reviewer_id"]
    independent = review["blind_attested"] and reviewer not in {
        suite["task_author"]["id"], runtime["operator_id"], runtime["candidate_author_id"]}
    confirmation = (suite["stage"] == "confirmation" and independent and holdout_lift
                    and finding == "IMPROVEMENT_SIGNAL" and key["phase"] == "first-delivery")
    return {"schema_version": 1, "finding": finding, "freeze_sha256": frozen_sha,
            "phase": key["phase"], "primary_metric": "task-derived corrections before user feedback",
            "totals": totals, "observed_usage": usages, "case_regressions": regressions,
            "holdout_improvement": holdout_lift, "independence_attested": bool(independent),
            "confirmation_signal": bool(confirmation), "release_authorized": False,
            "limitations": ["Identity/blinding attestations require external review; this tool cannot prove them.",
                            "Counts are paired descriptive evidence, not statistical or product-wide causal proof.",
                            "Repair-stage scores never replace first-delivery scores; no release gate is changed."]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    prep = commands.add_parser("freeze")
    prep.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    prep.add_argument("--runtime", type=Path, required=True)
    prep.add_argument("--out", type=Path, required=True)
    record = commands.add_parser("capture")
    for flag in ("frozen", "records", "artifact", "events", "receipt", "stderr"):
        record.add_argument("--" + flag, type=Path, required=True)
    record.add_argument("--case", required=True)
    record.add_argument("--condition", choices=CONDITIONS, required=True)
    record.add_argument("--attempt", type=int, required=True)
    record.add_argument("--phase", choices=("first-delivery", "repair-1", "repair-2"), default="first-delivery")
    record.add_argument("--screenshot", type=Path, action="append", default=[])
    for name in ("bundle", "assess"):
        sub = commands.add_parser(name)
        sub.add_argument("--frozen", type=Path, required=True)
        sub.add_argument("--records", type=Path, required=True)
        sub.add_argument("--out", type=Path, required=True)
        if name == "bundle":
            sub.add_argument("--key-out", type=Path, required=True)
            sub.add_argument("--phase", choices=("first-delivery", "repair-1", "repair-2"), default="first-delivery")
        else:
            sub.add_argument("--bundle", type=Path, required=True)
            sub.add_argument("--key", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            suite = load_suite(args.suite)
            print(f"UX diagnostics valid: {len(suite['cases'])} {suite['stage']} cases; no model called.")
        elif args.command == "freeze":
            print(freeze(args.suite, args.runtime, args.out))
        elif args.command == "capture":
            value = capture(args.frozen, args.records, args.case, args.condition, args.attempt, args.phase,
                            args.artifact, args.events, args.receipt, args.screenshot, stderr=args.stderr)
            print(json.dumps({"complete": value["complete"], "usage": value["usage"]}))
            return 0 if value["complete"] else 2
        elif args.command == "bundle":
            bundle(args.frozen, args.records, args.out, args.key_out, args.phase)
            print("Reviewer bundle created; retain condition key separately.")
        else:
            require(not args.out.exists(), "never overwrite an assessment")
            result = assess(args.frozen, args.records, args.bundle, args.key)
            write(args.out, result)
            print(result["finding"])
        return 0
    except (UXError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
