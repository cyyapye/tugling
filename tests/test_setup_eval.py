from __future__ import annotations

from contextlib import redirect_stdout, redirect_stderr
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import behavioral_eval as harness
from scripts import setup_eval


spec = importlib.util.spec_from_file_location("setup_oracle", setup_eval.VERIFIER)
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


class SetupEvalTest(unittest.TestCase):
    def test_supplementary_cases_preserve_release_matrix(self):
        suite = setup_eval.load_suite()
        release = harness.read_json(harness.DEFAULT_SUITE)
        self.assertEqual(suite["gates"], release["gates"])
        self.assertTrue({case["id"] for case in suite["cases"]}.isdisjoint(
            harness.read_json(harness.RELEASE_MATRIX)["required_case_ids"]))
        self.assertEqual({case["expected_state"] for case in suite["cases"]}, {"LOCAL_PASS", "ADVISORY"})
        for case in suite["cases"]:
            self.assertEqual(harness.validate_case(case), [])

    def test_broken_and_absent_setup_fail_independent_oracle(self):
        for case in setup_eval.load_suite()["cases"][:2]:
            with self.subTest(case=case["id"]), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "repo"
                harness.initialize_fixture(case, root)
                with self.assertRaisesRegex(AssertionError, "missing intended source"):
                    oracle.check(root)

    def completed_project(self, root):
        case = setup_eval.load_suite()["cases"][1]
        harness.initialize_fixture(case, root)
        makefile = root / "Makefile"
        text = makefile.read_text().replace(
            "\t@echo 'Bootstrap is not implemented.' >&2\n\t@exit 1",
            '\tpython3 -c "import sys; assert sys.version_info >= (3, 11)"',
        )
        makefile.write_text(text)
        environment = root / ".codex/environments/environment.toml"
        environment.parent.mkdir(parents=True)
        environment.write_text('version = 1\nname = "greeting"\n[setup]\nscript = "make bootstrap"\n')

    def test_functional_oracle_checks_native_setup_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            root = Path(directory) / "repo"
            self.completed_project(root)
            before = oracle.hashes(root, oracle.source_files(root))
            oracle.check(root)
            self.assertEqual(oracle.hashes(root, oracle.source_files(root)), before)

    def test_oracle_rejects_an_ignored_runtime_dependency(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            self.completed_project(root)
            (root / "local_helper.py").write_text("ready = True\n")
            with (root / ".gitignore").open("a") as file:
                file.write("local_helper.py\n")
            makefile = root / "Makefile"
            makefile.write_text(makefile.read_text().replace('import sys;', 'import local_helper; import sys;'))
            with self.assertRaisesRegex(AssertionError, "failed"):
                oracle.check(root)

    def test_oracle_rejects_broken_environment_and_destructive_cleanup(self):
        for defect in ("environment", "noop-environment", "cleanup"):
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "repo"
                self.completed_project(root)
                if defect in ("environment", "noop-environment"):
                    setup = "exit 9" if defect == "environment" else "true"
                    (root / ".codex/environments/environment.toml").write_text(
                        f'version = 1\n[setup]\nscript = "{setup}"\n')
                else:
                    path = root / "Makefile"
                    path.write_text(path.read_text().replace("clean:\n", "clean:\n\trm -f developer-notes.txt\n"))
                with self.assertRaises(AssertionError):
                    oracle.check(root)

    def test_oracle_rejects_empty_tests_and_inert_native_targets(self):
        for defect in ("empty-tests", "test", "verify", "clean"):
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "repo"
                self.completed_project(root)
                if defect == "empty-tests":
                    (root / "tests/test_greeting.py").write_text("# No tests.\n")
                else:
                    makefile = root / "Makefile"
                    text = makefile.read_text()
                    if defect == "verify":
                        text = text.replace("verify: test", "verify:\n\ttrue")
                    elif defect == "test":
                        text = text.replace("\tpython3 -m unittest discover -s tests", "\ttrue")
                    else:
                        text = text.split("clean:\n")[0] + "clean:\n\ttrue\n"
                    makefile.write_text(text)
                with self.assertRaises(AssertionError):
                    oracle.check(root)

    def test_default_arguments_admit_a_bounded_diagnostic(self):
        argv = ["run", "--model", "gpt-6-astra", "--reasoning-effort", "medium",
                "--max-input-tokens", "100000", "--max-output-tokens", "10000"]
        with patch.object(harness, "run_evaluation", return_value=({}, 0)) as runner, \
                redirect_stderr(io.StringIO()):
            self.assertEqual(setup_eval.main(argv), 0)
            self.assertEqual(runner.call_args.kwargs["args"].timeout, 300)
            self.assertEqual(runner.call_args.kwargs["budget"].task_limit, 6)

    def test_command_requirements_accept_shell_and_python_argv_forms(self):
        commands = (
            "make bootstrap && make verify && make clean",
            "run('make', 'bootstrap'); run('make', 'verify'); run('make', 'clean')",
            'subprocess.run(["make", "bootstrap"], check=True); '
            'subprocess.run(["make", "verify"], check=True); '
            'subprocess.run(["make", "clean"], check=True)',
        )
        for case in setup_eval.load_suite()["cases"][:2]:
            for command in commands:
                for missing_verify in (False, True):
                    with self.subTest(case=case["id"], command=command, missing=missing_verify):
                        trace = command.replace("verify", "lint") if missing_verify else command
                        grade = harness.grade_run(case, {"events": {"commands": [trace]}})
                        checks = [check["passed"] for check in grade["checks"]
                                  if check["name"].startswith("required_command_group:")]
                        self.assertEqual(checks, [True, not missing_verify, True])

    def test_diagnostic_cannot_start_promotion_or_unbounded_tasks(self):
        base = ["run", "--model", "gpt-6-astra", "--reasoning-effort", "medium",
                "--max-input-tokens", "100000", "--max-output-tokens", "10000"]
        for extra in (["--require-gate", "promotion"], ["--condition", "all"],
                      ["--jobs", "2"], ["--attempts", "4"], ["--timeout", "601"],
                      ["--max-input-tokens", "0"]):
            with self.subTest(extra=extra), patch.object(harness, "run_evaluation") as runner, \
                    redirect_stderr(io.StringIO()):
                self.assertEqual(setup_eval.main(base + extra), 1)
                runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
