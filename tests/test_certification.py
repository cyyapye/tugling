from __future__ import annotations

import argparse
from contextlib import redirect_stdout, redirect_stderr
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from scripts import certify_release as cert


def approved_environment() -> dict[str, str]:
    return {
        "GITHUB_REPOSITORY": cert.REPOSITORY, "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_RUN_ATTEMPT": "1", "GITHUB_RUN_ID": "12345",
        "CERTIFICATION_ENABLED": "true", "APPROVE_PAID_RUN": "true",
        "CONTROLLER_SHA": "a" * 40, "WORKFLOW_SHA": "a" * 40,
        "GITHUB_SHA": "a" * 40, "GITHUB_REF": "refs/tags/controller-test",
        "GITHUB_REF_NAME": "controller-test",
        "CANDIDATE_SHA": "b" * 40, "BASELINE_SHA": "c" * 40,
        "MAX_INPUT_TOKENS": "2000", "MAX_OUTPUT_TOKENS": "2000",
        "APPROVED_INPUT_TOKENS": "1000", "APPROVED_OUTPUT_TOKENS": "1000",
    }


class CertificationRuntimeTest(unittest.TestCase):
    def test_dispatch_approval_is_explicit_bounded_and_not_reusable(self):
        env = approved_environment()
        self.assertEqual(cert.authorize(env)["input_limit"], 1000)
        for key, value in (
            ("GITHUB_REPOSITORY", "someone/fork"), ("GITHUB_EVENT_NAME", "pull_request"),
            ("GITHUB_RUN_ATTEMPT", "2"), ("CERTIFICATION_ENABLED", ""),
            ("APPROVE_PAID_RUN", "false"), ("CONTROLLER_SHA", ""),
            ("WORKFLOW_SHA", "d" * 40), ("CANDIDATE_SHA", "main"), ("BASELINE_SHA", "stable"),
            ("APPROVED_INPUT_TOKENS", "2001"), ("MAX_OUTPUT_TOKENS", ""),
            ("APPROVED_OUTPUT_TOKENS", "0"), ("APPROVED_INPUT_TOKENS", "-1"),
            ("APPROVED_INPUT_TOKENS", "1e3"), ("GITHUB_RUN_ID", "123\nanything"),
            ("GITHUB_SHA", "d" * 40), ("GITHUB_REF", "refs/heads/main"),
            ("GITHUB_REF_NAME", "main"),
        ):
            with self.subTest(key=key, value=value), self.assertRaises(cert.CertificationError):
                cert.authorize({**env, key: value})

    def test_token_thresholds_preserve_actual_overshoot_and_stop_new_tasks(self):
        budget = cert.runtime.RunBudget(100, 50, 3)
        budget.begin()
        budget.record({"input_tokens": 80, "output_tokens": 20, "cached_input_tokens": 60})
        budget.begin()
        with self.assertRaises(cert.runtime.BudgetError):
            budget.record({"input_tokens": 30, "output_tokens": 5, "cached_input_tokens": 0})
        self.assertEqual(budget.report()["input_tokens"], 110)
        self.assertEqual(budget.report()["completed_tasks"], 2)
        with self.assertRaises(cert.runtime.BudgetError):
            budget.begin()
        for usage in ({}, {"input_tokens": 0, "output_tokens": 0, "cached_input_tokens": 0},
                      {"input_tokens": 1, "output_tokens": -1, "cached_input_tokens": 0},
                      {"input_tokens": 1, "output_tokens": 1, "cached_input_tokens": 2}):
            with self.subTest(usage=usage), self.assertRaises(cert.runtime.BudgetError):
                cert.runtime.RunBudget(100, 50, 3).record(usage)

    def test_proxy_never_copies_auth_or_exposes_credential_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "auth.json").write_text('{"synthetic":"private"}')
            with mock.patch.dict(os.environ, {"TUGLING_CODEX_PROXY_URL": "http://127.0.0.1:12345/v1"}):
                cert.behavioral.prepare_isolated_codex_home(root / "isolated", source)
                self.assertEqual(list((root / "isolated").iterdir()), [])
                env = cert.runtime.child_environment({"PATH": "/bin", "HOME": str(root),
                    "OPENAI_API_KEY": "synthetic", "GH_TOKEN": "synthetic",
                    "GITHUB_TOKEN": "synthetic", "POLICY_PATTERNS": "synthetic"})
                self.assertEqual(set(env), {"PATH", "HOME"})
            for address in ("https://api.openai.com/v1", "http://evil.invalid/v1",
                            "http://127.0.0.1:70000/v1", "http://127.0.0.1:0/v1"):
                with mock.patch.dict(os.environ, {"TUGLING_CODEX_PROXY_URL": address}):
                    with self.assertRaises(ValueError):
                        cert.runtime.proxy_arguments()

    def test_timeout_kills_the_tool_descendant_before_it_can_write(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "late-write"
            child = f"import time; from pathlib import Path; time.sleep(1); Path({str(marker)!r}).touch()"
            parent = f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',{child!r}]); time.sleep(20)"
            with self.assertRaises(subprocess.TimeoutExpired):
                cert.runtime.run_process([sys.executable, "-c", parent], text=True,
                                         capture_output=True, timeout=0.25)
            time.sleep(1.1)
            self.assertFalse(marker.exists())

    def test_candidate_source_cannot_replace_the_ruler(self):
        harness = cert.behavioral
        before = harness.ROOT, harness.FIXTURES, harness.OUTPUT_SCHEMA, harness.RELEASE_MATRIX
        with cert.candidate_source(Path("/synthetic/candidate")):
            self.assertEqual(harness.ROOT, Path("/synthetic/candidate"))
            self.assertEqual((harness.FIXTURES, harness.OUTPUT_SCHEMA, harness.RELEASE_MATRIX), before[1:])
        self.assertEqual(harness.ROOT, before[0])

    def test_budgeted_harness_stops_before_second_task_after_missing_usage(self):
        harness = cert.behavioral
        suite = harness.read_json(harness.DEFAULT_SUITE)
        with tempfile.TemporaryDirectory() as directory:
            args = argparse.Namespace(codex_bin="synthetic", out=directory, condition="candidate",
                attempts=3, jobs=1, model=cert.MODEL, reasoning_effort=cert.EFFORT,
                timeout=180, keep_workspaces=False, baseline_ref=None, policy_pattern_file=None,
                require_gate=None)
            with mock.patch.object(harness, "resolve_codex", return_value=("synthetic", "synthetic")), \
                 mock.patch.object(harness, "run_condition", return_value={"exit_code": 0,
                    "events": {"usage": {}}}) as run, redirect_stderr(io.StringIO()):
                with self.assertRaises(cert.runtime.BudgetError):
                    harness.run_evaluation(suite=suite, cases=suite["cases"][:1], args=args,
                                           budget=cert.runtime.RunBudget(1000, 1000, 3))
                self.assertEqual(run.call_count, 1)


class CertificationGitTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="tugling-cert-test-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.repo = self.root / "author"
        self.repo.mkdir()
        self.git(self.repo, "init", "--initial-branch=main", "--template=", ".")
        self.git(self.repo, "config", "user.name", "Synthetic certification")
        self.git(self.repo, "config", "user.email", "cert@example.invalid")
        for name in (".agents", ".github", "plugins", "scripts", "tests", "evals"):
            shutil.copytree(cert.ROOT / name, self.repo / name,
                            ignore=shutil.ignore_patterns("__pycache__", "runs", "releases"))
        shutil.copy2(cert.ROOT / "Makefile", self.repo / "Makefile")
        manifest = json.loads((self.repo / "plugins/tugling/.codex-plugin/plugin.json").read_text())
        major, minor, patch = map(int, manifest["version"].split("."))
        self.candidate_version = f"{major}.{minor}.{patch + 1}"
        self.baseline = self.commit("synthetic approved controller")
        self.git(self.repo, "branch", "stable")
        self.git(self.root, "clone", "--bare", str(self.repo), str(self.root / "remote.git"))
        self.remote = self.root / "remote.git"
        self.request = {**cert.authorize(approved_environment()), "controller_sha": self.baseline,
                        "candidate_sha": self.baseline, "baseline_sha": self.baseline}

    def git(self, root, *args):
        return cert.controller.text_git(root, *args)

    def commit(self, message):
        self.git(self.repo, "add", ".")
        self.git(self.repo, "commit", "--quiet", "-m", message)
        return self.git(self.repo, "rev-parse", "HEAD")

    def publish(self):
        self.request["candidate_sha"] = self.commit("synthetic candidate")
        self.git(self.repo, "push", str(self.remote), "main")

    def change_plugin(self):
        manifest = self.repo / "plugins/tugling/.codex-plugin/plugin.json"
        value = json.loads(manifest.read_text())
        value["version"] = self.candidate_version
        manifest.write_text(json.dumps(value))
        self.publish()

    def prepare(self):
        return cert.prepare_candidate(self.root / "candidate", self.request, remote=str(self.remote))

    def test_unchanged_plugin_does_not_require_model_work(self):
        (self.repo / "operator-note.md").write_text("synthetic documentation change")
        self.publish()
        before = self.git(self.remote, "show-ref")
        self.assertEqual(self.prepare()["state"], "UNCHANGED_PLUGIN")
        self.assertEqual(self.git(self.remote, "show-ref"), before)

    def test_changed_plugin_uses_exact_candidate_without_writing_remote_refs(self):
        self.change_plugin()
        before = self.git(self.remote, "show-ref")
        plan = self.prepare()
        self.assertEqual(plan["state"], "CERTIFICATION_REQUIRED")
        self.assertEqual(plan["plugin"]["version"], self.candidate_version)
        self.assertEqual(self.git(self.root / "candidate", "rev-parse", "HEAD"), self.request["candidate_sha"])
        self.assertEqual(self.git(self.remote, "show-ref"), before)

    def test_candidate_cannot_replace_its_own_grader(self):
        marker = self.root / "executed"
        (self.repo / "scripts/behavioral_eval.py").write_text(
            f"from pathlib import Path; Path({str(marker)!r}).touch()")
        self.publish()
        with self.assertRaisesRegex(cert.controller.ControllerError, "separately review"):
            self.prepare()
        self.assertFalse(marker.exists())

    def test_stale_dispatch_and_symlink_are_rejected(self):
        old_candidate = self.request["candidate_sha"]
        self.change_plugin()
        self.request["candidate_sha"] = old_candidate
        with self.assertRaisesRegex(cert.CertificationError, "moved"):
            self.prepare()
        shutil.rmtree(self.root / "candidate")
        (self.repo / "plugins/tugling/escape").symlink_to(self.root / "outside")
        self.publish()
        with self.assertRaisesRegex(cert.CertificationError, "regular files"):
            self.prepare()

    def test_existing_version_is_rejected_before_model_work(self):
        (self.repo / "plugins/tugling/skills/repo-verify/SKILL.md").write_text(
            (self.repo / "plugins/tugling/skills/repo-verify/SKILL.md").read_text() + "\nSynthetic change.\n")
        self.publish()
        with self.assertRaisesRegex(cert.CertificationError, "new, unpublished release version"):
            self.prepare()

    def test_full_orchestration_counts_all_conditions_and_withholds_failed_certificate(self):
        # Substitute only the model-task boundary. Real Git identities, scans,
        # full matrix aggregation, gates, assembly and artifact validation run.
        self.change_plugin()
        self.prepare()
        candidate = self.root / "candidate"
        patterns = self.root / "policy.txt"
        patterns.write_text("synthetic-private-sentinel-" + str(time.time_ns()))
        version = f"codex-cli {cert.CODEX_VERSION}"

        def installed(**kwargs):
            return {"passed": True, "mode": "public-cli-live",
                "source": {"repository": cert.REPOSITORY, "requested_revision": kwargs["ref"],
                           "resolved_revision": kwargs["ref"]},
                "plugin": cert.gate.plugin_identity(kwargs["expected_root"]),
                "codex": {"version": version}, "live": {"ran": True, "model": cert.MODEL,
                    "reasoning_effort": cert.EFFORT, "repository_unchanged": True,
                    "selected_skill": "repo-verify", "verification_order": "repository-native-first",
                    "installed_skill_read_observed": True,
                    "usage": {"input_tokens": 10, "output_tokens": 1, "cached_input_tokens": 0}}}

        before = self.git(self.remote, "show-ref")
        for candidate_score in (1.0, 0.8):
            with self.subTest(candidate_score=candidate_score):
                calls = []

                def model_task(**kwargs):
                    condition = kwargs["condition"]
                    score = {"control": 0.8, "released": 0.9, "candidate": candidate_score}[condition]
                    calls.append((kwargs["case"]["id"], condition, kwargs["attempt"]))
                    return {"case_id": kwargs["case"]["id"], "condition": condition,
                        "attempt": kwargs["attempt"], "exit_code": 0, "elapsed_seconds": 0.1,
                        "final_output": {"synthetic": True},
                        "events": {"usage": {"input_tokens": 10, "output_tokens": 1,
                                              "cached_input_tokens": 0}},
                        "grade": {"effective_score": score, "score": score,
                                  "critical_pass": True, "passed": True}}

                private = self.root / f"private-{candidate_score}"
                private.mkdir()
                output = self.root / f"output-{candidate_score}"
                budget = cert.runtime.RunBudget(1000, 1000, 91)
                with mock.patch.dict(os.environ, {"TUGLING_CODEX_PROXY_URL": "http://127.0.0.1:12345/v1"}), \
                     mock.patch.object(cert.clean_room, "resolve_codex", return_value=("synthetic", version)), \
                     mock.patch.object(cert.behavioral, "resolve_codex", return_value=("synthetic", version)), \
                     mock.patch.object(cert.clean_room, "public_install", side_effect=installed), \
                     mock.patch.object(cert.behavioral, "run_condition", side_effect=model_task), \
                     redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                    if candidate_score == 1.0:
                        cert.certify(candidate, self.request, patterns, output, private, budget)
                        cert.validate_artifact(output, self.request)
                        certificate = cert.gate.read_json(output / "certificate.json")
                        self.assertEqual(certificate["plugin"]["version"], self.candidate_version)
                    else:
                        with self.assertRaisesRegex(cert.CertificationError, "promotion gate"):
                            cert.certify(candidate, self.request, patterns, output, private, budget)
                        self.assertFalse(output.exists())
                cases = cert.gate.validate_matrix()["required_case_ids"]
                self.assertEqual(set(calls), {(case, condition, attempt) for case in cases
                    for condition in ("control", "released", "candidate") for attempt in (1, 2, 3)})
                self.assertEqual(len(calls), 90)
                self.assertEqual(budget.report()["completed_tasks"], 91)
        self.assertEqual(self.git(self.remote, "show-ref"), before)


class CertificationArtifactTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="tugling-artifact-test-")
        self.addCleanup(self.directory.cleanup)
        self.output = Path(self.directory.name)
        self.request = cert.authorize(approved_environment())
        self.certificate = cert.gate.read_json(cert.ROOT / "evals/releases/v0.4.0/certificate.json")
        self.certificate["behavioral"]["evaluated_revision"] = self.request["candidate_sha"]
        self.certificate["behavioral"]["released_revision"] = self.request["baseline_sha"]
        self.certificate["clean_room"]["revision"] = self.request["candidate_sha"]
        self.certificate["clean_room"]["codex_version"] = f"codex-cli {cert.CODEX_VERSION}"
        for section in ("behavioral", "clean_room"):
            self.certificate[section]["model"] = cert.MODEL
            self.certificate[section]["reasoning_effort"] = cert.EFFORT
        self.envelope = {"schema_version": 1, "state": "CERTIFIED", **self.request,
            "created_at": "2026-09-05T00:00:00+00:00",
            "model": cert.MODEL, "reasoning_effort": cert.EFFORT,
            "codex_version": f"codex-cli {cert.CODEX_VERSION}",
            "usage": {"completed_tasks": 91, "task_limit": 91, "input_limit": 1000,
                "output_limit": 1000, "input_tokens": 100, "output_tokens": 100,
                "cached_input_tokens": 50, "in_flight_or_unaccounted_task": False,
                "accounting": "between-tasks-not-hard-billing-cap"}}
        self.write()

    def write(self):
        cert.gate.write_json(self.output / "certificate.json", self.certificate)
        self.envelope["certificate_sha256"] = cert.gate.file_digest(self.output / "certificate.json")
        cert.gate.write_json(self.output / "certification.json", self.envelope)

    def test_matching_synthetic_artifact_is_validated_without_attesting(self):
        cert.validate_artifact(self.output, self.request)

    def test_tampering_stale_identity_or_missing_tasks_cannot_be_attested(self):
        for key, value in (("candidate_sha", "d" * 40), ("run_id", "999"),
                           ("controller_sha", "e" * 40), ("model", "different-model")):
            with self.subTest(key=key):
                original = self.envelope[key]
                self.envelope[key] = value
                self.write()
                with self.assertRaises(cert.CertificationError):
                    cert.validate_artifact(self.output, self.request)
                self.envelope[key] = original
        self.envelope["usage"]["completed_tasks"] = 90
        self.write()
        with self.assertRaises(cert.CertificationError):
            cert.validate_artifact(self.output, self.request)
        self.envelope["usage"]["completed_tasks"] = 91
        self.write()
        (self.output / "certificate.json").write_text("{}")
        with self.assertRaises(cert.CertificationError):
            cert.validate_artifact(self.output, self.request)

    def test_raw_extra_artifacts_are_rejected(self):
        (self.output / "events.jsonl").write_text("synthetic raw model output")
        with self.assertRaises(cert.CertificationError):
            cert.validate_artifact(self.output, self.request)


if __name__ == "__main__":
    unittest.main()
