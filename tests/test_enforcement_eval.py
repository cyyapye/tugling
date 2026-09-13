from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("enforcement_oracle", ROOT / "evals/enforcement/verify_enforcement.py")
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


RUNNER = '''import json
import os
from pathlib import Path
import unittest

def cases(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from cases(item)
        else:
            yield item

suite = unittest.defaultTestLoader.discover('tests')
actual = sorted(case.id() for case in cases(suite))
expected = json.loads(Path('required-tests.json').read_text())
if os.environ.get('TEST_ARGS'):
    raise SystemExit('Required execution cannot be selected')
if actual != expected:
    raise SystemExit('Missing native test identity')
result = unittest.TextTestRunner().run(suite)
raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)
'''

WRAPPER = '''import json
import os
from pathlib import Path
import subprocess
import sys

source = Path(os.environ['REVIEWED_SOURCE']).resolve()
helper = source / 'plugins/tugling/scripts/project_contract.py'
def git(*args):
    return subprocess.check_output(['git', '--no-replace-objects', '-C', str(source), *args], text=True).strip()

pin = json.loads(Path('.tugling/project.json').read_text())['tugling']['revision']
if Path(git('rev-parse', '--show-toplevel')).resolve() != source:
    raise SystemExit('Not the actual Git root')
if git('rev-parse', 'HEAD') != pin or git('status', '--porcelain=v1', '--untracked-files=all'):
    raise SystemExit('Source identity mismatch')
relative = str(helper.relative_to(source))
if helper.is_symlink() or git('ls-files', '--error-unmatch', '--', relative) != relative:
    raise SystemExit('Helper must be tracked source')
body = subprocess.check_output(['git', '--no-replace-objects', '-C', str(source), 'show', 'HEAD:' + relative])
if helper.read_bytes() != body:
    raise SystemExit('Helper bytes differ')
raise SystemExit(subprocess.call([sys.executable, '-I', str(helper), '--repo', '.',
                                 '--source-root', str(source), '--source-mode', 'pinned', '--run-required']))
'''

WORKFLOW = '''name: Native
on: [push, pull_request]
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha || github.sha }}
          persist-credentials: false
          path: project
      - uses: actions/checkout@v4
        with:
          repository: example/tugling
          ref: REVIEWED_SOURCE_SHA
          path: tugling
      - name: Verify checked-out identity
        working-directory: project
        env:
          EXPECTED_REVISION: ${{ github.event.pull_request.head.sha || github.sha }}
        run: |
          test "$(git rev-parse HEAD)" = "$EXPECTED_REVISION"
      - name: Required native gate
        working-directory: project
        env:
          REVIEWED_SOURCE: ${{ github.workspace }}/tugling
        run: make verify
'''


class EnforcementEvalTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="tugling-enforcement-selftest-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name).resolve()
        self.project = self.directory / "project"
        oracle.prepare(self.project)
        self.source = self.directory / "reviewed-source"
        helper = self.source / oracle.HELPER
        helper.parent.mkdir(parents=True)
        shutil.copy2(ROOT / oracle.HELPER, helper)
        manifest = self.source / "plugins/tugling/.codex-plugin/plugin.json"
        manifest.parent.mkdir()
        manifest.write_text(json.dumps({"name": "tugling", "version": "0.0.0"}))
        oracle.initialize(self.source)
        self.hook = {"schema_version": 1, "source_root": str(self.source),
                     "gate": {"argv": ["make", "verify"], "env": {"REVIEWED_SOURCE": "{source}"}},
                     "ci": {"workflow": ".github/workflows/verify.yml", "checkout_step": 0,
                            "source_checkout_step": 1, "identity_step": 2,
                            "gate_step": 3, "pr_revision": "head"}}

    def complete(self):
        """A small independent reference setup for exercising the oracle itself."""
        root = self.project
        with (root / "AGENTS.md").open("a") as file:
            file.write("\n## Tugling project adapter\n\nUse the required `make verify` gate.\n")
        (root / "checks.py").write_text(RUNNER)
        (root / "gate.py").write_text(WRAPPER)
        (root / "required-tests.json").write_text(json.dumps(sorted(
            "test_service.ServiceTests." + name
            for name in oracle.methods((oracle.FIXTURE / oracle.TEST_FILE).read_text()))))
        makefile = root / "Makefile"
        makefile.write_text(makefile.read_text().replace("verify: test", "verify:\n\t$(PYTHON) gate.py"))
        self.workflow = WORKFLOW.replace("REVIEWED_SOURCE_SHA", oracle.git(self.source, "rev-parse", "HEAD"))
        (root / ".github/workflows/verify.yml").write_text(self.workflow)
        tugling = root / ".tugling"
        tugling.mkdir()
        mapping = {"schema_version": 1, "flows": [{
            "id": "native", "description": "Shared provider quota and owned report cleanup.",
            "argv": ["python3", "checks.py"], "timeout_seconds": 10,
            "sources": ["checks.py", "required-tests.json", "quota_sync.py", "tests/test_service.py"],
            "runtime": None}], "requirements": [
            {"id": rule, "description": description, "sources": ["README.md"], "flows": ["native"]}
            for rule, description in (("quota", "Three active tenants share ninety provider calls."),
                                      ("cleanup", "Reports remove only owned files on success and failure."))]}
        (tugling / "checks.json").write_text(json.dumps(mapping))
        (tugling / "dogfood.json").write_text(json.dumps({
            "schema_version": 1, "data_policy": "synthetic-only", "case": {
                "id": "offline-quota", "skill": "tugling", "sandbox": "read-only", "minimum_score": 1.0,
                "expected_state": "ADVISORY", "max_changed_files": 0,
                "prompt": "Assess the synthetic project's native verification boundary without editing any files.",
                "decision_questions": [{"id": "scope", "question": "What scope applies?",
                                        "options": ["advisory", "implementation"], "expected": "advisory"}]}}))
        (tugling / "project.json").write_text(json.dumps({
            "schema_version": 1, "tugling": {
                "repository": "https://github.com/example/tugling", "channel": "pinned",
                "revision": oracle.git(self.source, "rev-parse", "HEAD"), "version": "0.0.0"},
            "project": {"adapter": "AGENTS.md", "instructions": ["AGENTS.md"],
                        "canonical_verify": ["make", "verify"], "verification": ".tugling/checks.json",
                        "ci_workflow": ".github/workflows/verify.yml", "dogfood_case": ".tugling/dogfood.json"},
            "learning": {"mode": "off", "local_path": ".tugling/local/corrections.jsonl"}}))
        oracle.commit(root)

    def test_original_fixture_has_real_native_cases_and_permits_focused_iteration(self):
        oracle.command(self.project, ["make", "verify"])
        names = oracle.methods((self.project / oracle.TEST_FILE).read_text())
        self.assertEqual(len(names), 5)
        path = self.project / "quota_sync.py"
        path.write_text(path.read_text().replace("POLL_SECONDS = 30", "POLL_SECONDS = 1"))
        oracle.command(self.project, ["make", "test", "TEST_ARGS=tests.test_service.ServiceTests.test_idle_workload_makes_no_calls"])
        self.assertNotEqual(oracle.command(self.project, ["make", "verify"], success=False)["returncode"], 0)

    def test_oracle_accepts_complete_real_setup_and_preserves_caller(self):
        self.complete()
        before = oracle.tree_snapshot(self.project)
        result = oracle.verify(self.project, self.hook)
        self.assertEqual(result["state"], "LOCAL_ENFORCEMENT_PASS")
        self.assertIn("ignored_nested_source_rejected_before_execution", result["checks"])
        self.assertIn("focused_pass_full_required_fail", result["checks"])
        self.assertEqual(result["ci"]["local_identity_controls"], 4)
        self.assertFalse(result["ci"]["hosted_ci_executed"])
        self.assertEqual(oracle.tree_snapshot(self.project), before)

    def test_missing_or_noop_adapter_does_not_count_as_enforcement(self):
        with self.assertRaisesRegex(AssertionError, "command failed"):
            oracle.verify(self.project, self.hook)
        self.complete()
        (self.project / "gate.py").write_text("# No-op gate.\n")
        oracle.commit(self.project)
        with self.assertRaisesRegex(AssertionError, "receipts"):
            oracle.verify(self.project, self.hook)

    def test_file_presence_only_and_allowed_skips_fail_real_mutation_controls(self):
        self.complete()
        path = self.project / "checks.py"
        path.write_text(RUNNER.replace("if actual != expected:", "if not Path('tests/test_service.py').is_file():"))
        oracle.commit(self.project)
        with self.assertRaisesRegex(AssertionError, "accepted missing-case"):
            oracle.verify(self.project, self.hook)
        path.write_text(RUNNER.replace(" and not result.skipped", ""))
        oracle.commit(self.project)
        with self.assertRaisesRegex(AssertionError, "accepted skipped-case"):
            oracle.verify(self.project, self.hook)

    def test_environment_or_command_line_selection_cannot_hide_a_real_failure(self):
        self.complete()
        path = self.project / "checks.py"
        path.write_text(RUNNER.replace(
            "    raise SystemExit('Required execution cannot be selected')",
            "    suite = unittest.TestSuite()"))
        oracle.commit(self.project)
        with self.assertRaisesRegex(AssertionError, "selection bypassed"):
            oracle.verify(self.project, self.hook)

    def test_automatic_inventory_rebaseline_is_not_a_pass(self):
        self.complete()
        path = self.project / "checks.py"
        path.write_text(RUNNER.replace("    raise SystemExit('Missing native test identity')",
                                      "    Path('required-tests.json').write_text(json.dumps(actual))"))
        oracle.commit(self.project)
        with self.assertRaisesRegex(AssertionError, "re-baselined"):
            oracle.verify(self.project, self.hook)

    def test_helper_source_is_checked_before_it_can_execute(self):
        self.complete()
        path = self.project / "gate.py"
        path.write_text(WRAPPER[:WRAPPER.index("pin = ")] + WRAPPER[WRAPPER.index("raise SystemExit(subprocess.call"):])
        oracle.commit(self.project)
        with self.assertRaisesRegex(AssertionError, "ignored nested helper"):
            oracle.verify(self.project, self.hook)

    def test_ci_checks_real_identity_and_explicit_pr_revision(self):
        self.complete()
        path = self.project / ".github/workflows/verify.yml"
        for defective, reason in ((self.workflow.replace("ref: ${{ github.event.pull_request.head.sha || github.sha }}", "ref: ${{ github.sha }}"),
                                    "intended pull_request"),
                                   (self.workflow.replace('test "$(git rev-parse HEAD)" = "$EXPECTED_REVISION"', "git status --short"),
                                    "mismatched"),
                                   (self.workflow.replace("        run: |", "        continue-on-error: true\n        run: |"),
                                    "unconditional")):
            with self.subTest(reason=reason):
                path.write_text(defective)
                oracle.commit(self.project)
                with self.assertRaisesRegex(AssertionError, reason):
                    oracle.check_ci(self.hook, self.project, self.source)

    def test_assessment_snapshot_catches_ignored_output_and_source_changes(self):
        before = oracle.tree_snapshot(self.project)
        self.assertEqual(oracle.tree_snapshot(self.project), before)
        local = self.project / ".tugling/local"
        local.mkdir(parents=True)
        (local / "unexpected.json").write_text("{}")
        self.assertNotEqual(oracle.tree_snapshot(self.project), before)

    def test_setup_must_preserve_assertions_and_product_implementation(self):
        self.complete()
        path = self.project / oracle.TEST_FILE
        path.write_text(path.read_text().replace("self.assertLessEqual(sum(calls), 90)", "self.assertTrue(True)"))
        with self.assertRaisesRegex(oracle.Inconclusive, "semantic review"):
            oracle.verify(self.project, self.hook)

    def test_clean_git_status_does_not_prove_helper_bytes(self):
        self.complete()
        path = self.project / "gate.py"
        # Keep exact revision, true root, tracked-path and clean-status checks.
        # Only tracked-byte comparison is absent in this deliberately weak guard.
        path.write_text(WRAPPER.replace("if helper.read_bytes() != body:", "if False:"))
        oracle.commit(self.project)
        with self.assertRaisesRegex(AssertionError, "mismatched helper"):
            oracle.verify(self.project, self.hook)

    def test_source_import_control_rejects_a_launcher_without_isolation(self):
        self.complete()
        self.assertEqual(oracle.check_source_import(self.hook, self.project, self.source),
                         "isolated_helper_passed")
        (self.project / "gate.py").write_text(WRAPPER.replace("[sys.executable, '-I', str(helper)",
                                                            "[sys.executable, str(helper)"))
        oracle.commit(self.project)
        with self.assertRaisesRegex(AssertionError, "ignored source module executed"):
            oracle.check_source_import(self.hook, self.project, self.source)

    def test_replacement_source_control_requires_forced_raw_object_reads(self):
        self.complete()
        oracle.check_replacement_source(self.hook, self.project, self.source)
        (self.project / "gate.py").write_text(WRAPPER.replace("'--no-replace-objects', ", ""))
        oracle.commit(self.project)
        with self.assertRaisesRegex(AssertionError, "Git replacement helper"):
            oracle.check_replacement_source(self.hook, self.project, self.source)

    def test_reviewer_cannot_choose_an_unrelated_gate(self):
        self.complete()
        path = self.project / ".tugling/project.json"
        config = json.loads(path.read_text())
        config["project"]["canonical_verify"] = ["python3", "-c", "pass"]
        path.write_text(json.dumps(config))
        oracle.commit(self.project)
        with self.assertRaisesRegex(AssertionError, "neither canonical"):
            oracle.verify(self.project, self.hook)

    def test_unsupported_ci_configuration_is_inconclusive_not_a_failed_setup(self):
        self.complete()
        path = self.project / ".github/workflows/verify.yml"
        for workflow, reason in ((self.workflow.replace("${{ github.event.pull_request.head.sha || github.sha }}", "${{ matrix.revision }}"),
                                  "unsupported workflow expression"),
                                 (self.workflow.replace("runs-on: ubuntu-latest", "runs-on: windows-latest"), "Linux runner")):
            with self.subTest(reason=reason):
                path.write_text(workflow)
                oracle.commit(self.project)
                with self.assertRaisesRegex(oracle.Inconclusive, reason):
                    oracle.check_ci(self.hook, self.project, self.source)

    def test_explicit_merge_identity_is_labelled_and_rejects_mismatches(self):
        self.complete()
        path = self.project / ".github/workflows/verify.yml"
        path.write_text(self.workflow.replace("${{ github.event.pull_request.head.sha || github.sha }}", "${{ github.sha }}"))
        oracle.commit(self.project)
        self.hook["ci"]["pr_revision"] = "merge"
        result = oracle.check_ci(self.hook, self.project, self.source)
        self.assertEqual(result["pull_request_identity"], "merge")
        self.assertEqual(result["local_identity_controls"], 4)

    def test_ci_sibling_checkouts_execute_combined_identity_and_real_gate(self):
        self.complete()
        path = self.project / ".github/workflows/verify.yml"
        text = self.workflow.split("      - name: Required native gate\n")[0]
        text = text.replace("          EXPECTED_REVISION:", "          REVIEWED_SOURCE: ${{ github.workspace }}/tugling\n          EXPECTED_REVISION:")
        text = text.replace('          test "$(git rev-parse HEAD)" = "$EXPECTED_REVISION"',
                            '          test "$(git rev-parse HEAD)" = "$EXPECTED_REVISION"\n          make verify')
        path.write_text(text)
        oracle.commit(self.project)
        self.hook["ci"]["gate_step"] = 2
        self.assertEqual(oracle.check_ci(self.hook, self.project, self.source)["local_identity_controls"], 4)

    def test_ci_requires_an_enabled_actual_gate_and_its_workflow_environment(self):
        self.complete()
        path = self.project / ".github/workflows/verify.yml"
        variants = (
            (self.workflow.replace("        run: make verify", "        run: 'true'"), "receipts"),
            (self.workflow.split("      - name: Required native gate\n")[0], "gate step is missing"),
            (self.workflow.replace("  test:\n", "  test:\n    if: false\n"), "job is disabled"),
            (self.workflow + "    if: false\n", "job is disabled"),
            (self.workflow.replace("  test:\n", "  test:\n    continue-on-error: true\n"), "unconditional"),
            (self.workflow + "    continue-on-error: true\n", "unconditional"),
            (self.workflow.replace("      - name: Required native gate\n", "      - name: Required native gate\n        if: false\n"), "step is disabled"),
            (self.workflow.replace("      - name: Required native gate\n", "      - name: Required native gate\n        continue-on-error: true\n"), "unconditional"),
            (self.workflow.replace("          REVIEWED_SOURCE: ${{ github.workspace }}/tugling\n", ""), "CI required gate failed"),
            (self.workflow.replace("          repository: example/tugling\n", ""), "repository differs"),
            (self.workflow.replace("repository: example/tugling", "repository: example/other"), "repository differs"),
            (self.workflow.replace("on: [push, pull_request]", "on: [workflow_dispatch]"), "automatically"),
            (self.workflow.replace("on: [push, pull_request]", "on: [push, pull_request_target]"), "privileged"),
            (self.workflow.replace("permissions:\n  contents: read\n", "permissions: write-all\n"), "write-all"),
            (self.workflow.replace("        run: make verify", "        run: make verify || true"), "swallowed"),
            (self.workflow.replace("        run: make verify", "        run: make verify | cat"), "swallowed"),
            (self.workflow.replace("        run: make verify", "        run: make verify || test \"$GITHUB_EVENT_NAME\" = push"), "failure for push"),
        )
        for workflow, reason in variants:
            with self.subTest(reason=reason):
                path.write_text(workflow)
                oracle.commit(self.project)
                with self.assertRaisesRegex(AssertionError, reason):
                    oracle.check_ci(self.hook, self.project, self.source)

    def test_ci_honors_trailing_job_environment_and_permission_override(self):
        self.complete()
        workflow = self.workflow.replace("          REVIEWED_SOURCE: ${{ github.workspace }}/tugling\n", "")
        workflow = workflow.replace("permissions:\n  contents: read\n", "permissions: write-all\n")
        workflow += ("    env:\n      REVIEWED_SOURCE: ${{ github.workspace }}/tugling\n"
                     "    permissions:\n      contents: read\n")
        (self.project / ".github/workflows/verify.yml").write_text(workflow)
        oracle.commit(self.project)
        result = oracle.check_ci(self.hook, self.project, self.source)
        self.assertEqual(result["fresh_required_receipts"], 2)
        self.assertTrue(result["native_failure_propagated"])

    def test_ci_runs_the_declared_sh_interpreter(self):
        self.complete()
        workflow = self.workflow.replace("        run: make verify",
                                         '        shell: sh\n        run: |\n          test "$0" = sh\n          make verify')
        (self.project / ".github/workflows/verify.yml").write_text(workflow)
        oracle.commit(self.project)
        self.assertEqual(oracle.check_ci(self.hook, self.project, self.source)["native_failure_events"],
                         ["pull_request", "push"])

    def assert_stopped(self, pid):
        for _ in range(100):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            status = Path(f"/proc/{pid}/stat")
            if status.exists() and status.read_text().split()[2] == "Z":
                return
            time.sleep(0.02)
        self.fail(f"oracle left its owned child running: {pid}")

    def test_sigterm_cleans_native_helper_child_and_owned_scratch_only(self):
        self.complete()
        # The real helper creates another process group for this native flow.
        # Ignoring TERM makes its three-second forced cleanup path observable.
        (self.project / "checks.py").write_text(
            "import os, signal, time\nfrom pathlib import Path\n"
            "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
            "Path('.tugling/local/leaf.pid').write_text(str(os.getpid()))\n"
            "time.sleep(30)\n")
        oracle.commit(self.project)
        marker = self.directory / "scratch.path"
        worker = self.directory / "cancel_worker.py"
        worker.write_text(
            "import importlib.util, json, tempfile\nfrom pathlib import Path\n"
            f"spec = importlib.util.spec_from_file_location('oracle', {str(ROOT / 'evals/enforcement/verify_enforcement.py')!r})\n"
            "oracle = importlib.util.module_from_spec(spec); spec.loader.exec_module(oracle)\n"
            f"with oracle.cancellation_scope(), tempfile.TemporaryDirectory(prefix='cancel-owned-', dir={str(self.directory)!r}) as directory:\n"
            "    scratch = Path(directory) / 'project'\n"
            f"    oracle.copy_source(Path({str(self.project)!r}), scratch)\n"
            f"    Path({str(marker)!r}).write_text(str(scratch))\n"
            f"    oracle.command(scratch, ['make', 'verify'], extra={{'REVIEWED_SOURCE': {str(self.source)!r}}})\n")
        unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True)
        process = subprocess.Popen([sys.executable, str(worker)], stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, start_new_session=True)
        leaf = None
        try:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if marker.exists():
                    scratch = Path(marker.read_text())
                    pidfile = scratch / ".tugling/local/leaf.pid"
                    if pidfile.exists():
                        leaf = int(pidfile.read_text())
                        break
                self.assertIsNone(process.poll(), "oracle worker exited before native execution")
                time.sleep(0.02)
            self.assertIsNotNone(leaf, "native child did not start within the fixture budget")
            process.terminate()
            self.assertEqual(process.wait(timeout=10), 128 + signal.SIGTERM)
            self.assert_stopped(leaf)
            self.assertFalse(scratch.parent.exists(), "cancellation retained owned scratch files")
            self.assertIsNone(unrelated.poll(), "oracle cancellation stopped an unrelated process")
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
            process.wait(timeout=5)
            # On a regression, clean only the specifically observed native group.
            if leaf is not None:
                try:
                    os.killpg(leaf, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            unrelated.terminate()
            unrelated.wait(timeout=5)

    def test_command_cleans_child_even_when_its_launcher_exits_successfully(self):
        script = "import subprocess, sys; p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); print(p.pid)"
        result = oracle.command(self.project, [sys.executable, "-c", script])
        self.assertEqual(result["returncode"], 0)
        self.assertTrue(result["forced_cleanup"])
        pid = int(result["output"].strip())
        self.assert_stopped(pid)

    def test_case_prompts_keep_advisory_boundary_and_do_not_supply_mutation_hints(self):
        cases = json.loads((ROOT / "evals/enforcement/cases.json").read_text())["cases"]
        self.assertEqual([case["expected_state"] for case in cases], ["LOCAL_PASS", "ADVISORY"])
        self.assertEqual(cases[1]["max_changed_files"], 0)
        for phrase in ("TEST_ARGS", "untracked spoof", "missing-case", "skipped-case", "identity inventory"):
            self.assertNotIn(phrase, cases[0]["prompt"])


if __name__ == "__main__":
    unittest.main()
