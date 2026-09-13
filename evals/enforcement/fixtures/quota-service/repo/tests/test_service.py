from pathlib import Path
import tempfile
import unittest

from quota_sync import collect_samples, render_report


class ServiceTests(unittest.TestCase):
    def test_shared_request_budget(self):
        calls = collect_samples()
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(count > 0 for count in calls))
        self.assertLessEqual(sum(calls), 90)

    def test_idle_workload_makes_no_calls(self):
        self.assertEqual(collect_samples(tenants=0), [])

    def test_report_cleanup_after_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            foreign = Path(directory) / "developer-notes.txt"
            foreign.write_text("preserve")
            with self.assertRaisesRegex(RuntimeError, "synthetic rendering failure"):
                render_report(directory, fail_after_write=True)
            self.assertEqual(foreign.read_text(), "preserve")
            self.assertEqual(sorted(p.name for p in Path(directory).iterdir()), [foreign.name])

    def test_report_cleanup_after_success(self):
        with tempfile.TemporaryDirectory() as directory:
            foreign = Path(directory) / "developer-notes.txt"
            foreign.write_text("preserve")
            self.assertEqual(render_report(directory), "ready")
            self.assertEqual(foreign.read_text(), "preserve")
            self.assertEqual(sorted(p.name for p in Path(directory).iterdir()), [foreign.name])

    def test_report_preserves_preexisting_file(self):
        with tempfile.TemporaryDirectory() as directory:
            existing = Path(directory) / "quota-report.tmp"
            existing.write_text("foreign report")
            with self.assertRaises(FileExistsError):
                render_report(directory)
            self.assertEqual(existing.read_text(), "foreign report")
