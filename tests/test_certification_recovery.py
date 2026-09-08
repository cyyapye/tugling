from __future__ import annotations

import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

from scripts import certification_tasks as tasks
from scripts import certification_jobs as jobs
from scripts import certification_sandbox as sandbox
from scripts import certification_worker as worker


def plan(synthetic=False):
    return tasks.manifest({"repository": tasks.cert.REPOSITORY, "run_id": "12345", "run_attempt": 1,
        "candidate_sha": "a" * 40, "baseline_sha": "b" * 40, "controller_sha": "c" * 40,
        "input_limit": 5_000_000, "output_limit": 500_000}, synthetic=synthetic)


def outcome(p, task_id="t003", attempt=0, passed=True, state="RESULT", usage=True):
    value = {"input_tokens": 200, "output_tokens": 100, "cached_input_tokens": 0} if usage else None
    evidence = {"score": 1.0 if passed else 0.0, "critical_pass": passed,
                "passed": passed, "elapsed_seconds": 1.0} if state == "RESULT" else None
    if task_id == "t000" and state == "RESULT":
        raw = {"passed": True, "checks": {}, "plugin": tasks.cert.gate.plugin_identity(),
               "live": {"ran": True, "repository_unchanged": True, "selected_skill": "repo-verify",
                        "verification_order": "repository-native-first", "installed_skill_read_observed": True}}
        evidence = tasks.clean_evidence(raw, p)
        evidence["checks"] = {k: True for k in evidence["checks"]}
        evidence["passed"] = True
    return tasks.record(p, task_id, attempt, "result", state=state, usage=value, evidence=evidence)


def artifact(p, name, identity=1):
    return {"id": identity, "name": name, "expired": False, "size_in_bytes": 1024,
            "workflow_run": {"id": int(p["request"]["run_id"]),
                "head_sha": p["request"]["controller_sha"],
                "repository_id": 123, "head_repository_id": 123}}


class ArtifactRecoveryTest(unittest.TestCase):
    def test_artifacts_must_come_from_the_same_run_commit_and_repository(self):
        p = plan()
        good = artifact(p, "checkpoint")
        with mock.patch.object(jobs, "github_json", return_value={"total_count": 1, "artifacts": [good]}):
            self.assertEqual(jobs.artifact_list(p), [good])
        for field, value in (("id", 999), ("head_sha", "d" * 40),
                             ("head_repository_id", 999), ("repository_id", None)):
            bad = copy.deepcopy(good)
            bad["workflow_run"][field] = value
            with self.subTest(field=field), mock.patch.object(jobs, "github_json",
                    return_value={"total_count": 1, "artifacts": [bad]}), self.assertRaises(tasks.TaskError):
                jobs.artifact_list(p)

    def test_latest_checkpoint_loads_once_and_never_falls_back(self):
        p = plan()
        prefix = f"checkpoint-{p['id'][:16]}-lane1-"
        old, latest = artifact(p, prefix + "1"), artifact(p, prefix + "2", 2)
        records = [tasks.admit(p, [], "t003", 0), outcome(p, passed=False)]
        data = {"checkpoint.json": json.dumps(jobs.checkpoint(p, records, 1)).encode()}
        with mock.patch.object(jobs, "artifact_list", return_value=[latest, old]), \
                mock.patch.object(jobs, "artifact_files", return_value=data) as download:
            self.assertEqual(jobs.load_remote(p, (1,)), records)
            download.assert_called_once_with(p, latest, {"checkpoint.json"})
        for heads in ([latest, latest, old], [dict(latest, expired=True), old],
                      [dict(latest, size_in_bytes=jobs.MAX_CHECKPOINT_BYTES + 1), old]):
            with mock.patch.object(jobs, "artifact_list", return_value=heads), \
                    mock.patch.object(jobs, "artifact_files") as download, self.assertRaises(tasks.TaskError):
                jobs.load_remote(p, (1,))
            download.assert_not_called()

    def test_archive_rejects_extra_paths_symlinks_and_expansion(self):
        p = plan()
        def zipped(entries):
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for name, data in entries:
                    archive.writestr(name, data)
            return stream.getvalue()
        link = zipfile.ZipInfo("checkpoint.json")
        link.create_system = 3
        link.external_attr = 0o120777 << 16
        cases = [([("checkpoint.json", "{}")], True),
                 ([("../checkpoint.json", "{}")], False),
                 ([("checkpoint.json", "{}"), ("private.txt", "private")], False),
                 ([(link, "/private/target")], False),
                 ([("checkpoint.json", "x" * (jobs.MAX_CHECKPOINT_BYTES + 1))], False)]
        for entries, valid in cases:
            with self.subTest(valid=valid), mock.patch("subprocess.run",
                    return_value=mock.Mock(returncode=0, stdout=zipped(entries))):
                if valid:
                    self.assertEqual(jobs.artifact_files(p, artifact(p, "test"), {"checkpoint.json"}),
                                     {"checkpoint.json": b"{}"})
                else:
                    with self.assertRaises(tasks.TaskError):
                        jobs.artifact_files(p, artifact(p, "test"), {"checkpoint.json"})

    def test_aggregator_restart_validates_saved_final_identity(self):
        p = plan(True)
        records = []
        for task in p["tasks"]:
            attempt = 1 if task["id"] == "t002" else 0
            records.extend([tasks.record(p, task["id"], attempt, "admission"),
                            outcome(p, task["id"], attempt, passed=task["id"] != "t003")])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            jobs.assemble(p, records, root / "original", None)
            report = json.loads((root / "original/recovery-diagnostic.json").read_text())
            with mock.patch.object(jobs, "artifact_list", return_value=[artifact(p, "recovery-diagnostic")]):
                for changed in (report, dict(report, manifest_id="another-run"),
                                dict(report, completed_tasks=90), dict(report, passed=False)):
                    with mock.patch.object(jobs, "artifact_files",
                            return_value={"recovery-diagnostic.json": json.dumps(changed).encode()}):
                        if changed == report:
                            self.assertTrue(jobs.reuse_final(p, root / "replacement"))
                        else:
                            with self.assertRaises(tasks.TaskError):
                                jobs.reuse_final(p, root / "replacement")


class RecoveryProtocolTest(unittest.TestCase):
    def test_usage_projection_never_defaults_missing_or_invalid_counters(self):
        good = {"input_tokens": 200, "cached_input_tokens": 50, "output_tokens": 100}
        self.assertEqual(tasks.usage_evidence({**good, "reasoning_output_tokens": 25}), good)
        for value in (None, {}, {**good, "input_tokens": True}, {**good, "input_tokens": 0},
                      {**good, "cached_input_tokens": 201}, {**good, "output_tokens": -1},
                      {key: item for key, item in good.items() if key != "output_tokens"}):
            with self.subTest(value=value):
                self.assertIsNone(tasks.usage_evidence(value))

    def test_execution_diagnostics_keep_only_bounded_public_categories(self):
        p = plan()
        receipt = outcome(p, state="TASK_ERROR", usage=False)
        diagnostics = tasks.cert.runtime.failure_diagnostics(json.dumps({"type": "turn.failed",
            "error": {"code": "invalid_json_schema", "message": "synthetic-private-message"}}))
        detail = {"stage": "evaluation", "category": "CodexExitError", "exit_code": 1,
                  "timed_out": False, "diagnostics": diagnostics}
        tasks.validate_record(p, dict(receipt, evidence=detail))
        self.assertNotIn("synthetic-private-message", json.dumps(detail))
        for changed in (dict(detail, exit_code=True), dict(detail, stderr="private"),
                        dict(detail, diagnostics={**diagnostics, "message": "private"}),
                        dict(detail, diagnostics={**diagnostics, "api_error_codes": ["private"]}),
                        dict(detail, diagnostics={**diagnostics, "http_statuses": [True]})):
            with self.subTest(detail=changed), self.assertRaises(tasks.TaskError):
                tasks.validate_record(p, dict(receipt, evidence=changed))

    def test_worker_preserves_real_parser_usage_and_failed_verification(self):
        p = plan()
        events = tasks.cert.behavioral.parse_jsonl(json.dumps({"type": "turn.completed", "usage": {
            "input_tokens": 200, "cached_input_tokens": 50, "output_tokens": 100,
            "reasoning_output_tokens": 25}}))
        for exit_code, expected_state in ((0, "RESULT"), (1, "TASK_ERROR")):
            with self.subTest(exit_code=exit_code), tempfile.TemporaryDirectory() as directory, \
                    mock.patch.object(tasks.cert.clean_room, "resolve_codex",
                        return_value=("codex", f"codex-cli {tasks.cert.CODEX_VERSION}")), \
                    mock.patch.object(tasks.cert.runtime, "proxy_arguments", return_value=["--config"]), \
                    mock.patch.object(tasks.cert, "prepare_candidate"), \
                    mock.patch.object(tasks.cert.behavioral, "resolve_release_baseline",
                        return_value={"skills": directory}), \
                    mock.patch.object(tasks.cert.behavioral, "run_condition", return_value={
                        "events": events, "exit_code": exit_code, "timed_out": False,
                        "elapsed_seconds": 1.0, "grade": {
                            "effective_score": 0.0, "critical_pass": False, "passed": False}}):
                result = worker.execute(p, tasks.admit(p, [], "t003", 0), Path(directory), None)
                self.assertEqual(result["state"], expected_state)
                self.assertEqual(result["usage"], {
                    "input_tokens": 200, "cached_input_tokens": 50, "output_tokens": 100})
                if expected_state == "RESULT":
                    self.assertFalse(result["evidence"]["passed"])
                records = [tasks.admit(p, [], "t003", 0), result]
                self.assertEqual(tasks.accounting(p, records)["unaccounted_attempts"], 0)
                self.assertIsNotNone(tasks.admit(p, records, "t005", 0))

    def test_freeze_all_91_distinct_tasks_and_runtime(self):
        p = plan()
        tasks.validate_manifest(p)
        self.assertEqual(len(p["tasks"]), 91)
        self.assertEqual(len({tasks.digest(t) for t in p["tasks"]}), 91)
        for key, value in (("model", "another-model"), ("tasks", p["tasks"][:-1]), ("max_attempts", 99)):
            modified = {**p, key: value}
            modified["id"] = tasks.digest({k: v for k, v in modified.items() if k != "id"})
            with self.subTest(key=key), self.assertRaises(tasks.TaskError):
                tasks.validate_manifest(modified)

    def test_every_trial_and_condition_is_required_even_after_recovery(self):
        p = plan(True)
        records = []
        for t in p["tasks"]:
            attempt = 1 if t["id"] == "t002" else 0
            records.extend([tasks.record(p, t["id"], attempt, "admission"),
                            outcome(p, t["id"], attempt, passed=t["id"] != "t003")])
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            jobs.assemble(p, records, destination, None)
            report = json.loads((destination / "recovery-diagnostic.json").read_text())
            self.assertTrue(report["passed"])
            self.assertFalse((destination / "certificate.json").exists())
            broken = [r if r["task_id"] != "t050" or r["kind"] == "admission"
                      else outcome(p, "t050", state="TASK_ERROR") for r in records]
            with self.assertRaises(tasks.TaskError):
                jobs.assemble(p, broken, destination, None)
            for missing in ("t000", "t002", "t050", "t090"):
                with self.subTest(missing=missing), self.assertRaises(tasks.TaskError):
                    jobs.assemble(p, [r for r in records if r["task_id"] != missing], destination, None)

    def test_terminal_verification_failure_is_never_retried(self):
        p = plan()
        records = [tasks.admit(p, [], "t003", 0), outcome(p, passed=False)]
        self.assertIsNone(tasks.admit(p, records, "t003", 1))
        self.assertNotIn("t003", [t["id"] for t in tasks.recovery(p, records, 1)])
        self.assertFalse(tasks.accepted(records)["t003"]["evidence"]["passed"])

    def test_uploaded_result_survives_loss_and_aggregator_restart(self):
        p = plan()
        records = [tasks.admit(p, [], "t006", 0), outcome(p, "t006")]
        encoded = json.dumps(jobs.checkpoint(p, records, 0))
        restored = jobs.validate_checkpoint(p, json.loads(encoded), 0)
        self.assertEqual(restored, records)
        self.assertIsNone(tasks.admit(p, restored, "t006", 1))
        self.assertNotIn("t006", [t["id"] for t in tasks.recovery(p, restored, 1)])

    def test_missing_paid_usage_blocks_lane_but_is_never_zero(self):
        p = plan()
        records = [tasks.admit(p, [], "t002", 0)]
        with self.assertRaisesRegex(tasks.TaskError, "ACCOUNTING_BLOCKED"):
            tasks.admit(p, records, "t004", 0)
        self.assertIsNotNone(tasks.admit(p, records, "t003", 0))
        self.assertEqual(tasks.accounting(p, records)["unaccounted_attempts"], 1)
        self.assertNotIn("t002", [t["id"] for t in tasks.recovery(p, records, 1)])

    def test_safe_setup_retries_and_synthetic_worker_loss_are_bounded(self):
        p = plan(True)
        records = [tasks.admit(p, [], "t002", 0)]
        self.assertIn("t002", [t["id"] for t in tasks.recovery(p, records, 1)])
        self.assertIsNotNone(tasks.admit(p, records, "t002", 1))
        with self.assertRaises(tasks.TaskError):
            tasks.admit(p, records, "t002", 3)
        with self.assertRaises(tasks.TaskError):
            tasks.recovery(p, records, 3)
        # With no durable admission, no paid model request was authorized.
        self.assertIn("t002", [t["id"] for t in tasks.recovery(plan(), [], 1)])

    def test_lane_budgets_are_disjoint_and_keep_reported_overshoot(self):
        p = plan()
        records = [tasks.admit(p, [], "t003", 0), outcome(p)]
        records[1]["usage"]["input_tokens"] = p["request"]["input_limit"] // 2 + 1
        with self.assertRaisesRegex(tasks.TaskError, "BUDGET_BLOCKED"):
            tasks.admit(p, records, "t005", 0)
        self.assertIsNotNone(tasks.admit(p, records, "t004", 0))
        self.assertEqual(tasks.accounting(p, records)["input_tokens"], 2_500_001)

    def test_replay_stale_generations_and_conflicting_outcomes_fail_closed(self):
        p = plan()
        admission = tasks.admit(p, [], "t003", 0)
        with self.assertRaises(tasks.TaskError):
            tasks.admit(p, [admission], "t003", 0)
        with self.assertRaises(tasks.TaskError):
            tasks.recovery(p, [tasks.record(p, "t003", 1, "admission")], 1)
        with self.assertRaises(tasks.TaskError):
            tasks.accepted([outcome(p), outcome(p, attempt=1, passed=False)])
        with self.assertRaises(tasks.TaskError):
            tasks.accounting(p, [outcome(p)])

    def test_receipt_validation_rejects_tampered_identity_private_fields_and_nan(self):
        p = plan()
        original = outcome(p)
        tasks.validate_record(p, original)
        changes = [dict(original, manifest_id="another-run"), dict(original, task_id="unknown"),
                   dict(original, private="never-publish"), dict(original, usage={}),
                   dict(original, attempt=True)]
        for key, value in (("score", float("nan")), ("critical_pass", "true"), ("score", 99),
                           ("private_path", "/private/synthetic")):
            altered = copy.deepcopy(original)
            altered["evidence"][key] = value
            changes.append(altered)
        for changed in changes:
            with self.subTest(changed=changed), self.assertRaises(tasks.TaskError):
                tasks.validate_record(p, changed)

    def test_corrupt_and_cross_lane_checkpoints_are_rejected(self):
        p = plan()
        r = [tasks.admit(p, [], "t003", 0), outcome(p)]
        good = jobs.checkpoint(p, r, 1)
        self.assertEqual(jobs.validate_checkpoint(p, good, 1), r)
        for changed in (dict(good, generation=99), dict(good, records=r+r), dict(good, lane=0)):
            with self.assertRaises(tasks.TaskError):
                jobs.validate_checkpoint(p, changed, 1)

    def test_incomplete_or_failed_execution_can_never_assemble_a_paid_certificate(self):
        p = plan()
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            for records in ([], [tasks.admit(p, [], "t003", 0), outcome(p, state="TASK_ERROR")]):
                with self.assertRaises(tasks.TaskError):
                    jobs.assemble(p, records, destination, None)
                self.assertFalse((destination / "certificate.json").exists())

    def test_linux_boundary_enforces_limits_outside_the_runner_user(self):
        argv = sandbox.command("tugling-test", Path("/work"), ["python3", "task.py"], Path("/env"))
        for setting in ("User=tugling-worker", "MemoryMax=4G", "MemorySwapMax=0", "CPUQuota=200%",
                        "TasksMax=256", "NoNewPrivileges=yes", "ProtectSystem=strict", "LimitFSIZE=16M",
                        "KillMode=control-group", "RuntimeMaxSec=300", "CapabilityBoundingSet="):
            self.assertIn("--property=" + setting, argv)


if __name__ == "__main__":
    unittest.main()
