from __future__ import annotations

import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from scripts import pstack_release as reviewed
from tests import pstack_release_fixtures as fixtures


class ReviewedEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.plugin = reviewed.gate.plugin_identity()
        self.report = fixtures.report(self.plugin)

    def test_report_validates_workflow_areas_without_per_skill_questionnaires(self):
        self.assertEqual(len(self.plugin["skills"]), 54)
        value = reviewed.validate_report(self.report, self.plugin)
        self.assertEqual(len(value["attempts"]), 8)
        self.assertEqual(value["scope"], "codex-port-compatibility")

    def resolved_failure(self):
        original = self.report["attempts"][-1]
        repeat = copy.deepcopy(original)
        repeat.update(id="authorized-repeat", environment="scoped-skill-directory", timeout_seconds=360)
        original.update(outcome="failed", failure_kind="environment", resolved_by=repeat["id"],
                        criteria={"passed": 0, "failed": 1})
        self.report["attempts"].append(repeat)
        self.report["evidence_sets"][0]["attempt_ids"].append(repeat["id"])
        self.report["limitations"].extend(sorted(reviewed.EXTRA_LIMITATIONS))
        return original, repeat

    def test_environment_repeat_retains_the_failed_attempt_and_changed_context(self):
        original, repeat = self.resolved_failure()
        value = reviewed.validate_report(self.report, self.plugin)
        self.assertEqual(value["attempts"][-2]["outcome"], "failed")
        self.assertEqual(value["attempts"][-1]["environment"], "scoped-skill-directory")
        self.assertNotEqual(original["timeout_seconds"], repeat["timeout_seconds"])

    def test_human_promotion_summary_preserves_failures_and_usage_limits(self):
        self.resolved_failure()
        summary = reviewed.review_summary(reviewed.validate_report(self.report, self.plugin))
        self.assertEqual(summary["outcomes"], {"passed": 8, "failed": 1})
        self.assertEqual(summary["criteria"], {"passed": 8, "failed": 1})
        self.assertEqual(summary["builder_usage"], {"input_tokens": 900, "cached_input_tokens": 450, "output_tokens": 90})
        self.assertEqual(summary["preserved_failures"][0]["resolved_by"], "authorized-repeat")
        self.assertIn("builder-usage-only", summary["limitations"])

    def test_missing_failure_resolution_or_false_pass_is_rejected(self):
        self.resolved_failure()
        for change in (lambda r: r["attempts"][-2].update(resolved_by=None),
                       lambda r: r["attempts"][-2].update(outcome="passed"),
                       lambda r: r["attempts"][-1].update(task_sha256="f" * 64),
                       lambda r: r["attempts"][-1].update(environment="workspace-write"),
                       lambda r: r["attempts"][-2].update(failure_kind="behavior"),
                       lambda r: r["attempts"].pop(-2),
                       lambda r: r["limitations"].remove("repeat-used-longer-timeout")):
            value = copy.deepcopy(self.report)
            change(value)
            with self.subTest(value=value["attempts"][-1]["id"]), self.assertRaises(reviewed.ReviewedReleaseError):
                reviewed.validate_report(value, self.plugin)

    def test_missing_unknown_stale_private_and_incomplete_evidence_is_rejected(self):
        changes = [lambda r: r.update(raw_output="private"), lambda r: r.update(method="questionnaire"),
            lambda r: r.update(scope="enhancement"), lambda r: r["plugin"].update(content_sha256="e" * 64),
            lambda r: r["attempts"][0].update(evidence_sha256="bad"),
            lambda r: r["attempts"][0].update(areas=["unknown"]),
            lambda r: r["attempts"].pop(), lambda r: r["runtimes"][0].update(model="/Users/private/model"),
            lambda r: r["attempts"][0].update(environment="danger-full-access"),
            lambda r: r["attempts"][0].update(timeout_seconds=0),
            lambda r: r["review"].update(unresolved_criteria=1),
            lambda r: r["attempts"][0]["usage"].update(input_tokens=0),
            lambda r: r["attempts"][0]["usage"].update(cached_input_tokens=101)]
        for index, change in enumerate(changes):
            value = copy.deepcopy(self.report)
            change(value)
            with self.subTest(index=index), self.assertRaises(reviewed.ReviewedReleaseError):
                reviewed.validate_report(value, self.plugin)

    def test_missing_successful_workflow_area_is_rejected(self):
        self.report["attempts"][0]["areas"] = self.report["attempts"][1]["areas"]
        with self.assertRaisesRegex(reviewed.ReviewedReleaseError, "workflow areas"):
            reviewed.validate_report(self.report, self.plugin)

    def test_duplicate_json_fields_and_symlink_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            path.write_text('{"schema_version":1,"schema_version":2}')
            with self.assertRaises(reviewed.ReviewedReleaseError):
                reviewed.read_json(path)
            alias = Path(directory) / "alias.json"
            alias.symlink_to(path)
            with self.assertRaises(reviewed.ReviewedReleaseError):
                reviewed.read_json(alias)

    def test_certificate_requires_free_exact_public_install_and_current_policy(self):
        request = fixtures.request()
        install = fixtures.install(self.plugin, request["candidate_sha"])
        for change in (lambda r: r.update(mode="public-cli-live"), lambda r: r["live"].update(ran=True),
                       lambda r: r["source"].update(resolved_revision="e" * 40),
                       lambda r: r["checks"].pop("plugin_add"),
                       lambda r: r["checks"].update(exact_public_revision=False)):
            value = copy.deepcopy(install)
            change(value)
            with self.assertRaises(reviewed.ReviewedReleaseError):
                reviewed.assemble_certificate(request, self.report, value)
        certificate = reviewed.assemble_certificate(request, self.report, install)
        certificate["policy_sha256"] = "e" * 64
        with self.assertRaises(reviewed.ReviewedReleaseError):
            reviewed.verify_certificate(certificate)

    def test_dispatch_needs_exact_report_approval_but_no_model_budget(self):
        env = {"GITHUB_REPOSITORY": "cyyapye/tugling", "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_RUN_ATTEMPT": "1", "CERTIFICATION_ENABLED": "true", "APPROVE_REVIEWED_EVIDENCE": "true",
            "CONTROLLER_SHA": "a" * 40, "WORKFLOW_SHA": "a" * 40, "GITHUB_SHA": "a" * 40,
            "GITHUB_REF_NAME": "controller-test", "GITHUB_REF": "refs/tags/controller-test",
            "GITHUB_WORKFLOW_REF": "cyyapye/tugling/.github/workflows/certify-release.yml@refs/tags/controller-test",
            "CANDIDATE_SHA": "b" * 40, "BASELINE_SHA": "c" * 40, "GITHUB_RUN_ID": "123", "REVIEW_SHA256": "d" * 64}
        self.assertEqual(reviewed.authorize(env), fixtures.request())
        for field, value in (("APPROVE_REVIEWED_EVIDENCE", "false"), ("CERTIFICATION_ENABLED", "false"),
                             ("GITHUB_RUN_ATTEMPT", "2"), ("REVIEW_SHA256", ""),
                             ("GITHUB_REF", "refs/heads/main"), ("WORKFLOW_SHA", "b" * 40),
                             ("GITHUB_WORKFLOW_REF", "other")):
            with self.subTest(field=field), self.assertRaises(reviewed.ReviewedReleaseError):
                reviewed.authorize({**env, field: value})

    def test_verify_must_be_latest_successful_push_on_exact_main(self):
        valid = {"head_sha": "b" * 40, "head_branch": "main", "event": "push",
                 "status": "completed", "conclusion": "success"}
        for changes in ({}, {"head_sha": "c" * 40}, {"head_branch": "codex/test"},
                        {"event": "pull_request"}, {"status": "in_progress"}, {"conclusion": "failure"}):
            body = io.BytesIO(json.dumps({"workflow_runs": [{**valid, **changes}]}).encode())
            with self.subTest(changes=changes), mock.patch.object(reviewed.legacy, "urlopen", return_value=body) as fetch:
                if changes:
                    with self.assertRaises(reviewed.legacy.CertificationError):
                        reviewed.legacy.require_successful_verify("b" * 40)
                else:
                    reviewed.legacy.require_successful_verify("b" * 40)
                self.assertIn("branch=main", fetch.call_args.args[0].full_url)

    def test_certification_does_not_admit_model_work_and_writes_two_bound_files(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "evidence"
            request = fixtures.request()
            with mock.patch.object(reviewed.legacy, "require_fresh_refs"), \
                 mock.patch.object(reviewed.legacy, "check_public_policy"), \
                 mock.patch.object(reviewed, "validate_sources"), \
                 mock.patch.object(reviewed.clean_room, "resolve_codex", return_value=("synthetic", "codex-cli 0.153.4")), \
                 mock.patch.object(reviewed.clean_room, "public_install", return_value=fixtures.install(self.plugin, request["candidate_sha"])) as install, \
                 mock.patch.object(reviewed.legacy.behavioral, "run_evaluation") as model:
                reviewed.certify(reviewed.ROOT, request, self.report, Path(directory) / "patterns", output)
                model.assert_not_called()
                self.assertIs(install.call_args.kwargs["live"], False)
                self.assertEqual(install.call_args.kwargs["model"], "")
            self.assertEqual({p.name for p in output.iterdir()}, {"certificate.json", "certification.json"})
            certificate = reviewed.validate_artifact(output, request, package_source_root=reviewed.ROOT)
            self.assertFalse(certificate["clean_room"]["model_called"])
            self.assertEqual(certificate["review_sha256"], request["review_sha256"])


class CandidateReviewTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="tugling-reviewed-source-test-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        for name in ("plugins", ".agents"):
            shutil.copytree(reviewed.ROOT / name, self.repo / name)
        self.git("init", "--initial-branch=main", "--template=", ".")
        self.git("config", "user.name", "Synthetic review")
        self.git("config", "user.email", "synthetic@example.invalid")
        self.report = fixtures.report(reviewed.gate.plugin_identity(self.repo))
        self.path = self.repo / f"evals/releases/v{self.report['plugin']['version']}/pstack-review.json"
        reviewed.gate.write_json(self.path, self.report)
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", "synthetic reviewed candidate")
        self.request = fixtures.request(candidate=self.git("rev-parse", "HEAD"))
        self.request["review_sha256"] = reviewed.gate.file_digest(self.path)

    def git(self, *args):
        return reviewed.controller.text_git(self.repo, *args)

    def test_report_is_read_from_exact_git_object_not_mutated_worktree(self):
        self.path.write_text('{"injected":"worktree replacement"}')
        value = reviewed.read_candidate_report(self.repo, self.request, self.report["plugin"]["version"])
        self.assertEqual(value, self.report)

    def test_unapproved_digest_and_missing_fixed_path_fail_before_model_work(self):
        request = {**self.request, "review_sha256": "f" * 64}
        with self.assertRaisesRegex(reviewed.ReviewedReleaseError, "approved review digest"):
            reviewed.read_candidate_report(self.repo, request, self.report["plugin"]["version"])
        with self.assertRaisesRegex(reviewed.ReviewedReleaseError, "fixed regular"):
            reviewed.read_candidate_report(self.repo, self.request, "99.0.0")

    def test_candidate_cannot_invent_its_own_attribution_inventory(self):
        inventory = self.repo / "plugins/tugling/skills" / reviewed.pstack_sources.MANIFEST
        inventory.write_text(inventory.read_text() + "\n")
        with self.assertRaisesRegex(reviewed.ReviewedReleaseError, "reviewed controller"):
            reviewed.validate_sources(self.repo, self.report)

    def test_materialization_preserves_reviewed_executable_files(self):
        output = self.root / "data"
        reviewed.controller.materialize_data(self.repo, self.request["candidate_sha"], output)
        original = {p.relative_to(self.repo): bool(p.stat().st_mode & 0o111)
                    for p in (self.repo / "plugins").rglob("*") if p.is_file()}
        self.assertTrue(any(original.values()))
        for path, executable in original.items():
            self.assertEqual(bool((output / path).stat().st_mode & 0o111), executable)


if __name__ == "__main__":
    unittest.main()
