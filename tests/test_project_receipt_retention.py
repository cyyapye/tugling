from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path

import test_project_contract as fixtures


contract = fixtures.contract
HELPER = fixtures.ROOT / "plugins/tugling/scripts/project_contract.py"
NATIVE = '''import pathlib, sys, time
local = pathlib.Path('.tugling/local')
with (local / 'starts').open('a') as output:
    output.write(sys.argv[1] + '\\n')
if sys.argv[1] == 'wait':
    time.sleep(60)
sys.exit(7 if sys.argv[1] == 'fail' else 0)
'''


@unittest.skipUnless(os.name == "posix", "receipt locks require POSIX")
class ReceiptRetentionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.fixture = fixtures.ProjectContractTest()
        self.root = self.fixture.make_project(self.temp.name).resolve()
        (self.root / "native.py").write_text(NATIVE)
        self.config_path = self.root / ".tugling/project.json"
        self.config = json.loads(self.config_path.read_text())
        self.config["project"]["verification"] = ".tugling/verification.json"
        self.mapping = {"schema_version": 1, "flows": [
            {"id": mode, "description": f"Run the {mode} native fixture",
             "argv": [sys.executable, "native.py", mode], "timeout_seconds": 60,
             "sources": ["native.py"], "runtime": None}
            for mode in ("pass", "fail", "wait")]}
        (self.root / ".tugling/verification.json").write_text(json.dumps(self.mapping))
        self.configure()
        self.store = self.root / contract.RECEIPT_DIRECTORY
        self.starts = self.root / ".tugling/local/starts"

    def configure(self, **overrides):
        self.config["project"]["receipt_retention"] = {
            **contract.DEFAULT_RECEIPT_RETENTION, **overrides}
        self.config_path.write_text(json.dumps(self.config))
        self.fixture.run_git(self.root, "add", ".")
        self.fixture.run_git(self.root, "-c", "commit.gpgsign=false", "commit", "-qm", "fixture")

    def argv(self, *args):
        return [sys.executable, "-I", str(HELPER), "--repo", str(self.root),
                "--source-root", str(fixtures.ROOT), "--source-mode", "pinned", "--json", *args]

    def cli(self, *args):
        return subprocess.run(self.argv(*args), capture_output=True, text=True, timeout=20)

    def run_flow(self, mode="pass"):
        result = self.cli("--run-flow", mode)
        self.assertEqual(result.returncode, 1 if mode == "fail" else 0, result.stderr)
        return self.root / json.loads(result.stdout)["flow_verification"]["path"]

    def seed(self, size=10, age=0):
        # The documented managed namespace owns these crash/retention fixtures.
        path = self.store / f"{uuid.uuid4()}.json"
        path.write_bytes(b"x" * size)
        os.utime(path, (time.time() - age, time.time() - age))
        return path

    def cleanup(self):
        result = self.cli("--cleanup-evidence")
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["receipt_cleanup"]

    def test_validation_and_receipt_checks_do_not_run_cleanup(self):
        self.assertEqual(self.cli().returncode, 0)
        self.assertFalse(self.store.exists())
        receipt = self.run_flow()
        os.utime(receipt, (0, 0))
        before = receipt.read_bytes()
        result = self.cli("--check-flow-evidence", str(receipt.relative_to(self.root)))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(receipt.read_bytes(), before)
        self.assertEqual(self.starts.read_text(), "pass\n")

    def test_success_and_failure_runs_automatically_enforce_count(self):
        self.configure(max_files=3)
        receipts = [self.run_flow(mode) for mode in ("pass", "fail", "pass", "fail", "pass")]
        self.assertEqual(set(self.store.glob("*.json")), set(receipts[-3:]))
        self.assertEqual(len(self.starts.read_text().splitlines()), 5)
        self.assertEqual(json.loads(receipts[-2].read_text())["state"], "FLOWS_FAIL")
        self.assertEqual(receipts[-1].stat().st_mode & 0o777, 0o600)

    def test_byte_limit_evicts_oldest_while_count_has_room(self):
        self.configure(max_files=8, max_bytes=2 * contract.MAX_RECEIPT_BYTES)
        self.run_flow()
        old = self.seed(size=240 * 1024, age=20)
        newer = self.seed(size=240 * 1024, age=10)
        self.run_flow()
        self.assertFalse(old.exists())
        self.assertTrue(newer.exists())
        receipts = list(self.store.glob("*.json"))
        self.assertLess(len(receipts), 8)
        self.assertLessEqual(sum(path.stat().st_size for path in receipts), 512 * 1024)

    def test_expiry_and_foreign_legacy_link_and_ledger_preservation(self):
        self.run_flow()
        expired = self.seed(age=8 * 86400)
        recent = self.seed(age=1)
        local = self.root / ".tugling/local"
        foreign = self.store / "notes.json"
        legacy = self.store.parent / f"{uuid.uuid4()}.json"
        ledger = local / "corrections.jsonl"
        outside = self.root.parent / "outside"
        for path in (foreign, legacy, ledger, outside):
            path.write_bytes(b"preserve exactly\n")
        link = self.store / f"{uuid.uuid4()}.json"
        link.symlink_to(outside)
        hardlink = self.store / f"{uuid.uuid4()}.json"
        os.link(outside, hardlink)
        result = self.cleanup()
        self.assertEqual(result["removed_files"], 1)
        self.assertFalse(expired.exists())
        self.assertTrue(recent.exists())
        self.assertTrue(link.is_symlink())
        for path in (foreign, legacy, ledger, outside, hardlink):
            self.assertEqual(path.read_bytes(), b"preserve exactly\n")

    def test_active_run_survives_expiry_and_blocks_capacity_before_native_work(self):
        self.configure(max_files=1)
        process = subprocess.Popen(self.argv("--run-flow", "wait"), stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True)
        try:
            for _ in range(500):
                if self.starts.exists():
                    break
                if process.poll() is not None:
                    self.fail(str(process.communicate()))
                time.sleep(.01)
            self.assertTrue(self.starts.exists())
            receipt = next(self.store.glob("*.json"))
            os.utime(receipt, (0, 0))
            self.assertEqual(self.cleanup()["active_files"], 1)
            self.assertTrue(receipt.exists())
            blocked = self.cli("--run-flow", "pass")
            self.assertEqual(blocked.returncode, 1)
            self.assertIn("active receipts exhaust", blocked.stderr)
            self.assertEqual(self.starts.read_text(), "wait\n")
            process.send_signal(signal.SIGTERM)
            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 1, stderr)
            self.assertEqual(json.loads(stdout)["flow_verification"]["evidence"]["results"][0]["failure"],
                             "interrupted")
            self.run_flow()
            self.assertFalse(receipt.exists())
            self.assertEqual(len(list(self.store.glob("*.json"))), 1)
        finally:
            if process.poll() is None:
                process.terminate()
                process.communicate(timeout=10)

    def test_crashed_writer_releases_lock_and_partial_receipt_expires(self):
        self.run_flow()
        partial = self.seed(size=0, age=8 * 86400)
        holder = subprocess.Popen([sys.executable, "-c",
            "import fcntl,sys,time; f=open(sys.argv[1],'r+'); "
            "fcntl.flock(f,fcntl.LOCK_EX); print('ready',flush=True); time.sleep(60)", str(partial)],
            stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(holder.stdout.readline().strip(), "ready")
            self.assertEqual(self.cleanup()["active_files"], 1)
            self.assertTrue(partial.exists())
            holder.kill()
            holder.wait(timeout=5)
            self.assertEqual(self.cleanup()["removed_files"], 1)
            self.assertFalse(partial.exists())
        finally:
            if holder.poll() is None:
                holder.kill()
                holder.wait(timeout=5)
            holder.stdout.close()

    def test_unmarked_or_corrupt_store_is_preserved_and_rejected(self):
        self.store.mkdir(parents=True)
        foreign = self.seed(age=8 * 86400)
        before = foreign.read_bytes()
        result = self.cli("--run-flow", "pass")
        self.assertEqual(result.returncode, 1)
        self.assertIn("unmarked receipt directory", result.stderr)
        (self.store / ".owner").write_text("someone else's store")
        result = self.cli("--cleanup-evidence")
        self.assertEqual(result.returncode, 1)
        self.assertIn("ownership marker differs", result.stderr)
        self.assertEqual(foreign.read_bytes(), before)
        self.assertFalse(self.starts.exists())

    def test_symlinked_parent_is_rejected_without_writing_outside(self):
        local = self.root / ".tugling/local"
        local.mkdir()
        outside = self.root.parent / "outside"
        outside.mkdir()
        (local / "verification").symlink_to(outside, target_is_directory=True)
        result = self.cli("--run-flow", "pass")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse(self.starts.exists())

    def test_oversized_receipt_is_rejected_before_native_execution(self):
        self.mapping["flows"][0]["argv"].append("x" * contract.MAX_RECEIPT_BYTES)
        (self.root / ".tugling/verification.json").write_text(json.dumps(self.mapping))
        self.configure()
        result = self.cli("--run-flow", "pass")
        self.assertEqual(result.returncode, 1)
        self.assertIn("256 KiB", result.stderr)
        self.assertFalse(self.starts.exists())
        self.assertFalse(self.store.exists())

    def test_directory_scan_is_bounded_without_removing_foreign_files(self):
        self.run_flow()
        for index in range(contract.MAX_RECEIPT_ENTRIES):
            (self.store / f"foreign-{index}").touch()
        result = self.cli("--cleanup-evidence")
        self.assertEqual(result.returncode, 1)
        self.assertIn("bounded scan", result.stderr)
        self.assertEqual(len(list(self.store.glob("foreign-*"))), contract.MAX_RECEIPT_ENTRIES)

    def test_retention_policy_rejects_invalid_and_unbounded_values(self):
        for key, value in (("max_files", True), ("max_files", 257), ("max_bytes", 1),
                           ("max_age_seconds", 0), ("max_age_seconds", 1.5)):
            with self.subTest(key=key, value=value):
                self.configure(**{key: value})
                result = self.cli("--run-flow", "pass")
                self.assertEqual(result.returncode, 1)
                self.assertIn(f"receipt_retention.{key}", result.stderr)
                self.assertFalse(self.starts.exists())
