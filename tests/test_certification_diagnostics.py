from __future__ import annotations

import copy
import json
from pathlib import Path
import shlex
import tempfile
import unittest
from unittest import mock

from scripts import certification_jobs as jobs
from scripts import certification_tasks as tasks
from scripts import certification_worker as worker


CASE_ID = "tugling-bounded-noop"


def noop_run(workspace: Path, fault: str | None = None) -> dict:
    harness = tasks.cert.behavioral
    case = next(c for c in harness.read_json(harness.DEFAULT_SUITE)["cases"] if c["id"] == CASE_ID)
    baseline = harness.initialize_fixture(case, workspace)
    harness.install_tugling(workspace)
    commands = [["cat", "docs/test-gaps.md"], ["make", "verify"],
                ["git", "status", "--short", "--untracked-files=all"]]
    if fault == "missing_gate":
        commands.pop(1)
    elif fault == "missing_status":
        commands.pop(2)
    stream = []
    for argv in commands:
        harness.run_command(argv, cwd=workspace, check=True)
        stream.append({"type": "item.completed", "item": {
            "type": "command_execution", "command": shlex.join(argv)}})
    if fault == "unnecessary_change":
        (workspace / "unnecessary.txt").write_text("unrequested work\n")
    stream.append({"type": "turn.completed", "usage": {
        "input_tokens": 200, "output_tokens": 100, "cached_input_tokens": 50}})
    output = {"case_id": CASE_ID, "summary": "The tracked queue is complete.",
        "decisions": [
            {"id": "work_exists", "value": "no", "evidence": ["docs/test-gaps.md"]},
            {"id": "action", "value": "bounded_noop", "evidence": ["completed queue"]},
            {"id": "scope", "value": "tracked_queue_only", "evidence": ["AGENTS.md"]}],
        "commands_run": [shlex.join(argv) for argv in commands],
        "artifacts_inspected": ["docs/test-gaps.md"], "changes_made": [],
        "strongest_proven_state": "LOCAL_PASS" if fault == "wrong_state" else "NOOP",
        "unverified": []}
    run = {"exit_code": 0, "final_output": output, "baseline_head": baseline,
        "final_head": harness.git_output(workspace, "rev-parse", "HEAD"),
        "changed_files": harness.changed_files(workspace)[0],
        "events": harness.parse_jsonl("\n".join(json.dumps(item) for item in stream)),
        "post_run_commands": [], "elapsed_seconds": 1.0}
    run["grade"] = harness.grade_run(case, run)
    return run


class CertificationDiagnosticsTest(unittest.TestCase):
    def setUp(self):
        self.plan = tasks.manifest({"repository": tasks.cert.REPOSITORY, "run_id": "12345",
            "run_attempt": 1, "candidate_sha": "a" * 40, "baseline_sha": "b" * 40,
            "controller_sha": "c" * 40, "input_limit": 5_000_000, "output_limit": 500_000})
        self.task = next(t for t in self.plan["tasks"] if t["case_id"] == CASE_ID
                         and t["condition"] == "candidate" and t["trial"] == 1)

    def execute_saved_run(self, raw, directory):
        with mock.patch.object(tasks.cert.clean_room, "resolve_codex",
                return_value=("codex", f"codex-cli {tasks.cert.CODEX_VERSION}")), \
                mock.patch.object(tasks.cert.runtime, "proxy_arguments", return_value=["--config"]), \
                mock.patch.object(tasks.cert, "prepare_candidate"), \
                mock.patch.object(worker, "run_behavioral", return_value=raw):
            admission = tasks.admit(self.plan, [], self.task["id"], 0)
            return admission, worker.execute(self.plan, admission, Path(directory), None)

    def test_noop_subchecks_survive_worker_checkpoint_and_recovery(self):
        faults = {None: set(), "missing_gate": {"required_command_group:1"},
            "missing_status": {"required_command_group:2"}, "wrong_state": {"evidence_state"},
            "unnecessary_change": {"change_budget"}}
        for fault, expected_failed in faults.items():
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as directory:
                raw = noop_run(Path(directory) / "workspace", fault)
                self.assertEqual({c["name"] for c in raw["grade"]["checks"] if not c["passed"]},
                                 expected_failed)
                # Free synthetic data tests projection without exposing arbitrary details.
                for check in raw["grade"]["checks"]:
                    check["detail"] = "synthetic-private-model-output"
                admission, result = self.execute_saved_run(raw, directory)
                self.assertEqual(result["state"], "RESULT")
                self.assertEqual(result["evidence"]["passed"], fault is None)
                checkpoint = jobs.checkpoint(self.plan, [admission, result], self.task["lane"])
                restored = jobs.validate_checkpoint(self.plan, json.loads(json.dumps(checkpoint)), self.task["lane"])
                saved = tasks.accepted(restored)[self.task["id"]]
                self.assertEqual({name for name, passed in saved["evidence"]["checks"].items() if not passed},
                                 expected_failed)
                self.assertNotIn("synthetic-private-model-output", json.dumps(checkpoint))
                self.assertEqual(tasks.accounting(self.plan, restored)["input_tokens"], 200)
                self.assertEqual(tasks.accounting(self.plan, restored)["unaccounted_attempts"], 0)
                self.assertIsNone(tasks.admit(self.plan, restored, self.task["id"], 1))
                self.assertNotIn(self.task["id"], [t["id"] for t in tasks.recovery(self.plan, restored, 1)])
                expected = [{"task": self.task["id"], "case": CASE_ID, "trial": 1,
                             "checks": sorted(expected_failed)}] if expected_failed else []
                self.assertEqual(tasks.failed_candidate_checks(self.plan, restored), expected)

    def test_projection_rejects_missing_duplicate_foreign_and_non_boolean_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = noop_run(Path(directory) / "workspace")
            checks = raw["grade"]["checks"]
            for invalid in (checks[:-1], checks[:-1] + [checks[0]],
                    checks[:-1] + [{"name": "synthetic-private-name", "passed": False}],
                    checks[:-1] + [{**checks[-1], "passed": 1}],
                    checks[:-1] + [{**checks[-1], "name": []}], None):
                with self.subTest(checks=invalid):
                    malformed = {**raw, "grade": {**raw["grade"], "checks": invalid}}
                    with self.assertRaises(tasks.TaskError):
                        tasks.behavioral_evidence(CASE_ID, malformed)
                    admission, result = self.execute_saved_run(malformed, directory)
                    self.assertEqual(result["state"], "TASK_ERROR")
                    self.assertEqual(result["evidence"], {"stage": "evaluation", "category": "TaskError"})
                    self.assertEqual(tasks.accounting(self.plan, [admission, result])["unaccounted_attempts"], 0)
                    self.assertEqual(result["usage"]["input_tokens"], 200)

    def test_receipts_require_the_complete_current_case_rubric(self):
        with tempfile.TemporaryDirectory() as directory:
            _, receipt = self.execute_saved_run(noop_run(Path(directory) / "workspace"), directory)
        checks = receipt["evidence"]["checks"]
        for invalid in ({name: value for name, value in checks.items() if name != "evidence_state"},
                {**checks, "synthetic-private-name": False}, {**checks, "evidence_state": 1},
                {**checks, "evidence_state": {"passed": False, "detail": "private"}}):
            with self.subTest(checks=invalid), self.assertRaises(tasks.TaskError):
                tasks.validate_record(self.plan, {**receipt, "evidence": {**receipt["evidence"], "checks": invalid}})
        legacy = copy.deepcopy(receipt)
        legacy["schema_version"] = 1
        del legacy["evidence"]["checks"]
        with self.assertRaises(tasks.TaskError):
            tasks.validate_record(self.plan, legacy)
        legacy_plan = {**self.plan, "schema_version": 1}
        legacy_plan["id"] = tasks.digest({key: value for key, value in legacy_plan.items() if key != "id"})
        with self.assertRaises(tasks.TaskError):
            tasks.validate_manifest(legacy_plan)


if __name__ == "__main__":
    unittest.main()
