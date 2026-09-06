from __future__ import annotations

import json
import os
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import test_project_contract as fixtures


contract = fixtures.contract
ROOT = fixtures.ROOT
HELPER = ROOT / "plugins/tugling/scripts/project_contract.py"

# A real native check owns its server, readiness request, and teardown. Deliberately
# broken variants exercise the adapter's process cleanup and proof boundaries.
NATIVE_CHECK = '''import http.client
import http.server
import pathlib
import socketserver
import subprocess
import sys
import time

local = pathlib.Path(".tugling/local")
local.mkdir(exist_ok=True)
mode = sys.argv[1]
if mode == "serve":
    # TCPServer avoids HTTPServer's unrelated reverse-DNS lookup during bind.
    server = socketserver.TCPServer(("127.0.0.1", 0), http.server.SimpleHTTPRequestHandler)
    (local / "port").write_text(str(server.server_address[1]))
    server.serve_forever()
(local / "port").unlink(missing_ok=True)
child = subprocess.Popen([sys.executable, __file__, "serve"])
(local / "pid").write_text(str(child.pid))
if mode == "leak":
    sys.exit(0)
try:
    if mode == "timeout":
        time.sleep(60)
    for _ in range(200):
        if (local / "port").exists():
            break
        time.sleep(.01)
    connection = http.client.HTTPConnection("127.0.0.1", int((local / "port").read_text()), timeout=2)
    connection.request("GET", "/AGENTS.md")
    response = connection.getresponse()
    assert response.status == 200 and b"Tugling project adapter" in response.read()
    connection.close()
    if mode == "mutate":
        pathlib.Path("AGENTS.md").write_text("changed during verification")
    if mode == "fail":
        sys.exit(7)
finally:
    child.terminate()
    child.wait(timeout=2)
'''


class ProjectVerificationTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.fixture = fixtures.ProjectContractTest()
        self.root = self.fixture.make_project(self.directory.name, learning_mode="off").resolve()
        (self.root / "native_check.py").write_text(NATIVE_CHECK)
        self.map_path = self.root / ".tugling/verification.json"
        self.mapping = {"schema_version": 1, "flows": [{
            "id": "dashboard", "description": "Read a synthetic dashboard through the native server.",
            "argv": [sys.executable, "native_check.py", "pass"], "timeout_seconds": 5,
            "sources": ["native_check.py", "AGENTS.md"],
            "runtime": {"owner": "native-command", "launch": "native_check.py starts HTTPServer",
                        "health": "HTTP GET /AGENTS.md", "cleanup": "finally terminates and waits for the server"},
        }]}
        config_path = self.root / ".tugling/project.json"
        config = json.loads(config_path.read_text())
        config["project"]["verification"] = ".tugling/verification.json"
        config_path.write_text(json.dumps(config))
        self.save_map()
        self.commit()

    def save_map(self):
        self.map_path.write_text(json.dumps(self.mapping))

    def commit(self):
        self.fixture.run_git(self.root, "add", ".")
        self.fixture.run_git(self.root, "-c", "commit.gpgsign=false", "commit", "-qm", "native verification fixture")

    def mode(self, mode, timeout=5):
        self.mapping["flows"][0]["argv"][-1] = mode
        self.mapping["flows"][0]["timeout_seconds"] = timeout
        self.save_map()
        self.commit()

    def cli(self, *args):
        return subprocess.run([sys.executable, str(HELPER), "--repo", str(self.root),
                               "--source-root", str(ROOT), "--source-mode", "pinned", "--json", *args],
                              text=True, capture_output=True, timeout=20)

    def run_flow(self):
        completed = self.cli("--run-flow", "dashboard")
        self.assertIn(completed.returncode, (0, 1), completed.stderr)
        self.assertTrue(completed.stdout, completed.stderr)
        return completed, json.loads(completed.stdout)["flow_verification"]

    def assert_server_stopped(self):
        pid = int((self.root / ".tugling/local/pid").read_text())
        for _ in range(100):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            # Linux may retain an orphan zombie until its init reaps it. A zombie
            # owns no listening socket and cannot continue executing the check.
            status = Path(f"/proc/{pid}/stat")
            if status.exists() and status.read_text().split()[2] == "Z":
                return
            time.sleep(.02)
        self.fail(f"owned server still running: {pid}")

    def test_validation_is_read_only_and_execution_is_opt_in(self):
        completed = self.cli()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertIsNone(report["flow_verification"])
        self.assertFalse((self.root / ".tugling/local").exists())

    def test_real_native_lifecycle_saves_private_commit_bound_evidence(self):
        completed, result = self.run_flow()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(result["state"], "FLOWS_PASS")
        evidence = result["evidence"]
        self.assertEqual(evidence["project_revision"], self.fixture.run_git(self.root, "rev-parse", "HEAD"))
        self.assertEqual(evidence["requested_flows"], ["dashboard"])
        self.assertTrue(evidence["worktree_unchanged"])
        path = self.root / result["path"]
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertNotIn("stdout", path.read_text())
        checked = self.cli("--check-flow-evidence", result["path"])
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assert_server_stopped()
        self.assertEqual(self.fixture.run_git(self.root, "status", "--porcelain"), "")

    def test_failed_native_check_cannot_pass_or_be_reused(self):
        self.mode("fail")
        completed, result = self.run_flow()
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(result["evidence"]["results"][0]["exit_code"], 7)
        self.assertEqual(self.cli("--check-flow-evidence", result["path"]).returncode, 1)
        self.assert_server_stopped()

    def test_repeated_runs_keep_distinct_receipts_and_clean_up_each_server(self):
        _, first = self.run_flow()
        completed, second = self.run_flow()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertNotEqual(first["path"], second["path"])
        self.assertTrue((self.root / first["path"]).is_file())
        self.assertEqual(self.cli("--check-flow-evidence", first["path"]).returncode, 0)
        self.assert_server_stopped()

    def test_timeout_reaps_owned_descendants_and_preserves_failure(self):
        self.mode("timeout", timeout=1)
        completed, result = self.run_flow()
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(result["evidence"]["results"][0]["failure"], "timeout")
        self.assertTrue(result["evidence"]["results"][0]["forced_cleanup"])
        self.assert_server_stopped()

    def test_successful_exit_with_leaked_server_is_a_failure(self):
        self.mode("leak")
        completed, result = self.run_flow()
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(result["evidence"]["results"][0]["failure"], "native-cleanup-incomplete")
        self.assert_server_stopped()

    def test_sigterm_cancellation_cleans_up_and_records_interruption(self):
        self.mode("timeout", timeout=60)
        process = subprocess.Popen([sys.executable, str(HELPER), "--repo", str(self.root),
            "--source-root", str(ROOT), "--run-flow", "dashboard", "--json"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            for _ in range(300):
                if (self.root / ".tugling/local/port").exists():
                    break
                time.sleep(.01)
            self.assertTrue((self.root / ".tugling/local/port").exists())
            process.send_signal(signal.SIGTERM)
            output, error = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 1, error)
            evidence = json.loads(output)["flow_verification"]["evidence"]
            self.assertEqual(evidence["results"][0]["failure"], "interrupted")
            self.assert_server_stopped()
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()

    def test_mutation_during_check_cannot_claim_commit_pass(self):
        self.mode("mutate")
        completed, result = self.run_flow()
        self.assertEqual(completed.returncode, 1)
        self.assertFalse(result["evidence"]["worktree_unchanged"])

    def test_dirty_or_untracked_project_is_rejected_before_execution(self):
        for path in ("AGENTS.md", "untracked.txt"):
            with self.subTest(path=path):
                target = self.root / path
                previous = target.read_text() if target.exists() else None
                target.write_text((previous or "") + "\nchanged\n")
                completed = self.cli("--run-flow", "dashboard")
                self.assertEqual(completed.returncode, 1)
                self.assertIn("clean committed project", completed.stderr)
                self.assertFalse((self.root / ".tugling/local").exists())
                target.write_text(previous) if previous is not None else target.unlink()

    def test_stale_commit_receipt_is_rejected(self):
        _, result = self.run_flow()
        (self.root / "AGENTS.md").write_text((self.root / "AGENTS.md").read_text() + "\nNew contract.\n")
        self.commit()
        completed = self.cli("--check-flow-evidence", result["path"])
        self.assertEqual(completed.returncode, 1)
        self.assertIn("stale", completed.stderr)

    def test_missing_result_cannot_be_relabelled_a_pass(self):
        _, result = self.run_flow()
        path = self.root / result["path"]
        evidence = json.loads(path.read_text())
        evidence["results"] = []
        path.write_text(json.dumps(evidence))
        self.assertEqual(self.cli("--check-flow-evidence", result["path"]).returncode, 1)

    def test_missing_untracked_or_symlinked_source_is_rejected(self):
        for name in ("missing.py", "untracked.py", "link.py"):
            with self.subTest(name=name):
                target = self.root / name
                if name == "untracked.py":
                    target.write_text("pass")
                elif name == "link.py":
                    target.symlink_to(self.root / "native_check.py")
                    self.fixture.run_git(self.root, "add", name)
                self.mapping["flows"][0]["sources"] = [name]
                self.save_map()
                self.assertEqual(self.cli().returncode, 1)

    def test_evidence_directory_cannot_escape_through_symlink(self):
        outside = Path(self.directory.name) / "outside"
        outside.mkdir()
        (self.root / ".tugling/local").mkdir()
        (self.root / ".tugling/local/verification").symlink_to(outside, target_is_directory=True)
        completed = self.cli("--run-flow", "dashboard")
        self.assertEqual(completed.returncode, 1)
        self.assertIn("symlinks", completed.stderr)
        self.assertEqual(list(outside.iterdir()), [])

    def test_ignored_wildcard_filename_cannot_borrow_another_files_tracking(self):
        # The literal name is ignored; ordinary Git pathspec matching would find
        # the committed AGENTS.md and incorrectly accept this uncommitted source.
        (self.root / "A*").write_text("pass")
        (self.root / ".gitignore").write_text((self.root / ".gitignore").read_text() + "\n/A*\n!AGENTS.md\n")
        self.mapping["flows"][0]["sources"] = ["A*"]
        self.save_map()
        completed = self.cli()
        self.assertEqual(completed.returncode, 1)
        self.assertIn("must be committed", completed.stderr)

    def test_index_flags_cannot_hide_uncommitted_native_code(self):
        self.fixture.run_git(self.root, "update-index", "--assume-unchanged", "native_check.py")
        (self.root / "native_check.py").write_text("raise SystemExit(0)")
        self.assertEqual(self.fixture.run_git(self.root, "status", "--porcelain"), "")
        completed = self.cli("--run-flow", "dashboard")
        self.assertEqual(completed.returncode, 1)
        self.assertIn("assume-unchanged", completed.stderr)
        self.assertFalse((self.root / ".tugling/local").exists())

    def test_unknown_and_duplicate_flow_ids_do_not_execute(self):
        for selected in (("unknown",), ("dashboard", "dashboard")):
            completed = self.cli(*(arg for flow_id in selected for arg in ("--run-flow", flow_id)))
            self.assertEqual(completed.returncode, 1)
            self.assertFalse((self.root / ".tugling/local").exists())

    def test_selection_stops_after_first_failure(self):
        self.mode("fail")
        second = {**self.mapping["flows"][0], "id": "second", "argv": ["missing-executable"]}
        self.mapping["flows"].append(second)
        self.save_map()
        self.commit()
        completed = self.cli("--run-flow", "dashboard", "--run-flow", "second")
        self.assertEqual(completed.returncode, 1)
        evidence = json.loads(completed.stdout)["flow_verification"]["evidence"]
        self.assertEqual(evidence["requested_flows"], ["dashboard", "second"])
        self.assertEqual([result["id"] for result in evidence["results"]], ["dashboard"])


if __name__ == "__main__":
    unittest.main()
