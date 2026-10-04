from __future__ import annotations

import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / ".codex/environments/environment.toml"


class LocalEnvironmentTest(unittest.TestCase):
    def run_setup(self, *, current_supported=False, fallback=False, gate_exit=0):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            current = root / "bin"
            homebrew = root / "homebrew-bin"
            intel = root / "intel-bin"
            for folder in (current, homebrew, intel):
                folder.mkdir()

            def executable(path, body):
                path.write_text("#!/bin/sh\n" + body)
                path.chmod(0o755)

            supported = f'exec {shlex.quote(sys.executable)} "$@"\n'
            unsupported = "printf \"ModuleNotFoundError: No module named 'tomllib'\\n\" >&2\nexit 1\n"
            executable(current / "python3", supported if current_supported else unsupported)
            if fallback:
                executable(homebrew / "python3", supported)
            executable(current / "git", "exit 0\n")
            executable(current / "make", (
                '[ "$1" = verify ] || exit 88\n'
                'command -v python3 > selected-python.txt\n'
                'python3 -c "import sys, tomllib; sys.exit(sys.version_info < (3, 11))" || exit 89\n'
                f"exit {gate_exit}\n"
            ))

            # Map conventional macOS installation locations into the fixture;
            # execute the checked-in setup script, preserving its decisions.
            script = tomllib.loads(CONFIG.read_text())["setup"]["script"]
            script = script.replace("/opt/homebrew/bin", str(homebrew))
            script = script.replace("/usr/local/bin", str(intel))
            result = subprocess.run(
                ["/bin/sh", "-eu", "-c", script], cwd=root,
                env={**os.environ, "PATH": str(current)},
                capture_output=True, text=True, timeout=15,
            )
            selected = root / "selected-python.txt"
            selection = selected.read_text().strip() if selected.exists() else None
            return result, selection, str(current / "python3"), str(homebrew / "python3")

    def test_preserves_supported_python_on_path(self):
        result, selected, current, _ = self.run_setup(current_supported=True, fallback=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(selected, current)

    def test_unsupported_python_uses_installed_homebrew_python(self):
        result, selected, _, homebrew = self.run_setup(fallback=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(selected, homebrew)

    def test_missing_supported_python_fails_before_native_gate(self):
        result, selected, _, _ = self.run_setup()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Python 3.11+", result.stderr)
        self.assertIsNone(selected)

    def test_setup_preserves_native_gate_failure(self):
        result, selected, current, _ = self.run_setup(current_supported=True, gate_exit=7)
        self.assertEqual(result.returncode, 7)
        self.assertEqual(selected, current)


if __name__ == "__main__":
    unittest.main()
