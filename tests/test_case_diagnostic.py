from __future__ import annotations

import copy
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts import certification_jobs as jobs
from scripts import certification_tasks as tasks
from scripts import certification_worker as worker
from scripts import certify_release as cert
from test_certification import approved_environment
from test_certification_diagnostics import noop_run


CASE = "tugling-bounded-noop"


def environment():
    return {**approved_environment(), "DIAGNOSTIC_CASE": CASE,
        "GITHUB_WORKFLOW_REF": f"{cert.REPOSITORY}/.github/workflows/diagnose-case.yml@refs/tags/controller-test",
        "MAX_INPUT_TOKENS": "5000000", "MAX_OUTPUT_TOKENS": "500000",
        "APPROVED_INPUT_TOKENS": "100000", "APPROVED_OUTPUT_TOKENS": "5000"}


def plan(synthetic=False):
    return tasks.manifest(cert.authorize(environment()), synthetic=synthetic)


class CaseDiagnosticTest(unittest.TestCase):
    def test_one_candidate_trial_is_bound_to_its_approval_and_manifest(self):
        p = plan()
        self.assertEqual(p["schema_version"], 3)
        self.assertEqual(p["purpose"], "case_diagnostic")
        self.assertEqual(p["lanes"], 1)
        self.assertEqual(p["tasks"], [{"id": "t057", "case_id": CASE,
            "condition": "candidate", "trial": 1, "lane": 0}])
        self.assertEqual(p["request"]["diagnostic_case"], CASE)
        full = tasks.manifest(cert.authorize(approved_environment()))
        self.assertEqual(full["schema_version"], 2)
        self.assertEqual(len(full["tasks"]), 91)
        self.assertNotIn("purpose", full)
        with self.assertRaises(tasks.TaskError):
            tasks.validate_manifest({**p, "lanes": True})
        for changes in ({"tasks": p["tasks"] * 2}, {"purpose": "certification"},
                {"schema_version": 2}, {"lanes": 2},
                {"tasks": [{**p["tasks"][0], "trial": 2}]},
                {"tasks": [{**p["tasks"][0], "condition": "released"}]}):
            bad = {**p, **changes}
            bad["id"] = tasks.digest({k: v for k, v in bad.items() if k != "id"})
            with self.subTest(changes=changes), self.assertRaises(tasks.TaskError):
                tasks.validate_manifest(bad)

    def test_case_approval_rejects_wrong_workflow_scope_and_excessive_limits(self):
        env = environment()
        for key, value in (("DIAGNOSTIC_CASE", ""), ("DIAGNOSTIC_CASE", "public-install"),
                ("DIAGNOSTIC_CASE", "unreviewed-case"), ("GITHUB_WORKFLOW_REF", ""),
                ("GITHUB_WORKFLOW_REF", env["GITHUB_WORKFLOW_REF"].replace("diagnose-case", "certify-release")),
                ("APPROVED_INPUT_TOKENS", "100001"), ("APPROVED_OUTPUT_TOKENS", "5001"),
                ("APPROVE_PAID_RUN", "false"), ("GITHUB_RUN_ATTEMPT", "2")):
            with self.subTest(key=key, value=value), self.assertRaises(cert.CertificationError):
                cert.authorize({**env, key: value})

    def test_only_pre_admission_setup_can_be_recovered(self):
        for synthetic in (False, True):
            with self.subTest(synthetic=synthetic):
                p = plan(synthetic)
                self.assertEqual(tasks.recovery(p, [], 1), p["tasks"])
                admission = tasks.admit(p, [], "t057", 1)
                self.assertEqual(admission["schema_version"], 3)
                self.assertEqual(tasks.recovery(p, [admission], 2), [])
                with self.assertRaises(tasks.TaskError):
                    tasks.admit(p, [admission], "t057", 2)
                infra = tasks.record(p, "t057", 1, "result", state="INFRA_ERROR", evidence=None,
                    usage={"input_tokens": 200, "output_tokens": 100, "cached_input_tokens": 0})
                self.assertEqual(tasks.recovery(p, [admission, infra], 2), [])
                with self.assertRaises(tasks.TaskError):
                    tasks.admit(p, [admission, infra], "t057", 2)
                with tempfile.TemporaryDirectory() as directory, self.assertRaises(tasks.TaskError):
                    jobs.assemble(p, [admission, infra], Path(directory), None)

    def test_preflight_keeps_case_scope_when_the_plugin_is_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "outputs"
            with mock.patch.dict(os.environ, {**environment(), "GITHUB_OUTPUT": str(output)}), \
                    mock.patch("sys.argv", ["certification_jobs", "plan", "--out", str(root / "manifest"),
                        "--policy", str(root / "policy")]), \
                    mock.patch.object(cert.controller, "text_git", return_value="a" * 40), \
                    mock.patch.object(cert, "require_successful_verify") as verified, \
                    mock.patch.object(cert, "prepare_candidate", return_value={"state": "UNCHANGED_PLUGIN"}), \
                    mock.patch.object(cert, "check_public_policy") as policy:
                self.assertEqual(jobs.main(), 0)
            verified.assert_called_once_with("b" * 40)
            policy.assert_called_once()
            p = json.loads((root / "manifest/manifest.json").read_text())
            self.assertEqual(p, plan())
            self.assertIn('lane0=["t057"]', output.read_text())
            self.assertIn('lane1=[]', output.read_text())
            self.assertIn('state=CASE_DIAGNOSTIC', output.read_text())
            with mock.patch.dict(os.environ, {**environment(), "DIAGNOSTIC_CASE": "async-safety-webhook"}), \
                    mock.patch("sys.argv", ["certification_jobs", "admit", "--manifest", str(root / "manifest/manifest.json"),
                        "--out", str(root / "unexpected"), "--task", "t057", "--lane", "0"]), \
                    mock.patch.object(jobs, "load_remote") as read, redirect_stderr(io.StringIO()):
                self.assertEqual(jobs.main(), 1)
                read.assert_not_called()

    def execute(self, p, raw, directory):
        admission = tasks.admit(p, [], "t057", 0)
        with mock.patch.object(cert.clean_room, "resolve_codex",
                return_value=("codex", f"codex-cli {cert.CODEX_VERSION}")), \
                mock.patch.object(cert.runtime, "proxy_arguments", return_value=["--config"]), \
                mock.patch.object(cert, "prepare_candidate"), \
                mock.patch.object(worker, "run_behavioral", return_value=raw) as run:
            result = worker.execute(p, admission, directory, None)
            self.assertEqual(run.call_count, 1)
        return [admission, result]

    def test_native_noop_verdict_survives_checkpoint_and_final_reuse(self):
        for synthetic in (False, True):
            for fault in (None, "wrong_state"):
                with self.subTest(synthetic=synthetic, fault=fault), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    p = plan(synthetic)
                    records = self.execute(p, noop_run(root / "workspace", fault), root)
                    restored = jobs.validate_checkpoint(p, json.loads(json.dumps(jobs.checkpoint(p, records, 0))), 0)
                    with mock.patch.object(cert.gate, "assemble_certificate") as certify:
                        jobs.assemble(p, restored, root / "report", None)
                        certify.assert_not_called()
                    report = json.loads((root / "report/diagnostic.json").read_text())
                    self.assertEqual(report["verification_passed"], fault is None)
                    self.assertEqual(report["failed_checks"], ["evidence_state"] if fault else [])
                    self.assertEqual(report["records"], records)
                    self.assertTrue(report["diagnostic_only"])
                    self.assertFalse(report["certificate_created"])
                    self.assertEqual(report["synthetic_only"], synthetic)
                    self.assertEqual(sorted(p.name for p in (root / "report").iterdir()), ["diagnostic.json"])
                    self.assertIsNone(tasks.admit(p, restored, "t057", 1))
                    self.assertEqual(tasks.recovery(p, restored, 1), [])
                    with mock.patch.object(jobs, "artifact_list", return_value=[{"name": "case-diagnostic"}]), \
                            mock.patch.object(jobs, "artifact_files", return_value={"diagnostic.json": json.dumps(report).encode()}):
                        self.assertTrue(jobs.reuse_final(p, root / "replacement"))
                    self.assertEqual(json.loads((root / "replacement/diagnostic.json").read_text()), report)
                    for change in ({"verification_passed": fault is not None},
                            {"certificate_created": True}, {"diagnostic_only": False},
                            {"manifest_id": "another-run"}, {"private_output": "private"}):
                        with self.subTest(change=change), self.assertRaises(tasks.TaskError):
                            jobs.validate_diagnostic_report(p, {**report, **change})
                    manifest = root / "manifest.json"
                    manifest.write_text(json.dumps(p))
                    with mock.patch.dict(os.environ, environment()), \
                            mock.patch("sys.argv", ["certification_jobs", "diagnostic-verdict", "--manifest", str(manifest),
                                "--out", str(root / "replacement")]), \
                            redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as error:
                        self.assertEqual(jobs.main(), 1 if fault else 0)
                    if fault:
                        self.assertIn("evidence_state", error.getvalue())

    def test_missing_usage_and_budget_overshoot_cannot_complete_diagnostics(self):
        p = plan()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = self.execute(p, noop_run(root / "workspace"), root)
            for usage in (None, {"input_tokens": 100001, "output_tokens": 100, "cached_input_tokens": 0}):
                records = copy.deepcopy(original)
                records[1]["usage"] = usage
                if usage is None:
                    records[1].update(state="TASK_ERROR", evidence=None)
                with self.subTest(usage=usage), self.assertRaises(tasks.TaskError):
                    jobs.assemble(p, records, root / "invalid", None)
            with self.assertRaises(tasks.TaskError):
                jobs.validate_checkpoint(p, jobs.checkpoint(p, original, 0), 1)

    def test_case_approval_cannot_reach_legacy_certification_or_validate_a_certificate(self):
        request = cert.authorize(environment())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(cert.CertificationError, "diagnostic approval"), \
                    mock.patch.object(cert.clean_room, "public_install") as install:
                cert.certify(root, request, root / "policy", root / "out", root / "private",
                             cert.runtime.RunBudget(100000, 5000, 1))
            install.assert_not_called()
            with self.assertRaisesRegex(cert.CertificationError, "diagnostic evidence"):
                cert.validate_artifact(root, request)


if __name__ == "__main__":
    unittest.main()
