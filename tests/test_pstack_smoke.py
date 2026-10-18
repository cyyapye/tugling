from pathlib import Path
import json
import tempfile
from types import SimpleNamespace
import subprocess
import unittest
from unittest.mock import patch

from scripts import pstack_smoke as smoke


class PstackSmokeTest(unittest.TestCase):
    def test_independent_cli_examples_reject_the_green_but_broken_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            smoke.fixture(repo)
            before = smoke.bug_oracle(repo)
            self.assertTrue(before["native_gate"])
            self.assertTrue(before["cli:Ada"])
            self.assertFalse(before["cli:Ada Lovelace"])
            path = repo / "greet.py"
            path.write_text(path.read_text().replace("name.split()[0]", "name"))
            self.assertTrue(all(smoke.bug_oracle(repo).values()))

    def test_scope_snapshot_includes_ignored_untracked_files(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            smoke.fixture(repo)
            before = smoke.snapshot(repo)
            (repo / "ignored.pyc").write_text("unauthorized artifact")
            after = smoke.snapshot(repo)
            self.assertNotEqual(before, after)
            self.assertIn("ignored.pyc", after)
            self.assertFalse(any(name.startswith(".git/") for name in after))

    def test_trace_retains_failed_commands_without_counting_started_events_twice(self):
        command = {"type": "command_execution", "command": "cat missing/SKILL.md"}
        rows = [{"type": "item.started", "item": command},
                {"type": "item.completed", "item": {**command, "exit_code": 1, "aggregated_output": "missing"}},
                {"type": "turn.completed", "usage": {"input_tokens": 12}}]
        commands = smoke.completed_commands("\n".join(json.dumps(row) for row in rows))
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0]["exit_code"], 1)
        self.assertEqual(commands[0]["aggregated_output"], "missing")

    def test_install_rejects_an_unisolated_path_before_reading_the_package(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(smoke.package, "run") as run, patch.object(smoke.package, "digest_tree") as digest:
                run.return_value.stdout = json.dumps({"installedPath": str(root / "outside")})
                with self.assertRaisesRegex(ValueError, "escaped"):
                    smoke.install("codex", root / "home", root / "marketplace", {})
                digest.assert_not_called()

    def test_delivery_is_separated_from_observers_and_regression_must_reject_original(self):
        case = next(c for c in smoke.load_cases(smoke.CASES) if c["id"] == "bug-fix")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            market = root / "library"
            plugin = market / smoke.package.PLUGIN_RELATIVE
            plugin.mkdir(parents=True)
            (plugin / "content").write_text("same installed instructions")

            def prepare(home):
                home.mkdir()

            def install(binary, home, marketplace, env):
                (home / "config.toml").write_text("")
                return plugin

            for real_regression in (False, True):
                out = root / str(real_regression)
                out.mkdir()
                args = SimpleNamespace(out=out, model="configured-model", reasoning_effort="high", timeout=30)

                def execute(argv, **kwargs):
                    repo = kwargs["cwd"]
                    self.assertFalse(repo.is_relative_to(out))
                    self.assertNotIn("TUGLING_BEHAVIORAL_EVAL", kwargs["env"])
                    self.assertNotIn("synthetic", (repo / "AGENTS.md").read_text())
                    self.assertFalse(any(repo.rglob("*rubric*")))
                    (repo / "greet.py").write_text(smoke.SOURCE.replace("name.split()[0]", "name"))
                    addition = '\n    def test_full_name(self):\n        self.assertEqual(greeting("Ada Lovelace"), "Hello, Ada Lovelace!")\n'
                    with (repo / "tests/test_greeting.py").open("a") as stream:
                        stream.write(addition if real_regression else "\n# Added coverage\n")
                    Path(argv[argv.index("--output-last-message") + 1]).write_text("Repaired the CLI.")
                    usage = {"input_tokens": 100, "cached_input_tokens": 0, "output_tokens": 20}
                    return subprocess.CompletedProcess(argv, 0, json.dumps({"type": "turn.completed", "usage": usage}), "")

                with patch.object(smoke.harness, "prepare_isolated_codex_home", prepare), \
                     patch.object(smoke, "install", install), \
                     patch.object(smoke.runtime, "run_process", execute):
                    result = smoke.run_case(case, args, "codex", market)
                self.assertEqual(result["checks"]["regression_rejects_original"], real_regression)
                self.assertEqual(result["automated_checks_passed"], real_regression)
                artifact = out / case["id"]
                self.assertTrue((artifact / "workspace/greet.py").is_file())
                actual = smoke.snapshot(artifact)
                actual.pop("files.json")
                self.assertEqual(actual, json.loads((artifact / "files.json").read_text()))


if __name__ == "__main__":
    unittest.main()
