import json
from pathlib import Path
import tempfile
import unittest

from scripts import pstack_review as review, pstack_smoke as smoke


class PstackReviewTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_record(self, name, *, failed=False):
        root = self.root / name
        folder = root / "verification"
        smoke.fixture(folder / "workspace")
        case = next(c for c in smoke.load_cases(smoke.CASES) if c["id"] == "verification")
        usage = {"input_tokens": 100, "output_tokens": 20, "cached_input_tokens": 0}
        result = {"id": case["id"], "rubric": case["rubric"], "usage": usage,
                  "checks": {"repository_unchanged": not failed},
                  "initial_files": smoke.snapshot(folder / "workspace"),
                  "redactions": ["/private/tmp/secret-operator/greeting-cli"]}
        (folder / "final.md").write_text("model-x found a CLI defect in /private/tmp/secret-operator/greeting-cli/greet.py")
        smoke.package.write_json(folder / "result.json", result)
        smoke.package.write_json(folder / "files.json", smoke.snapshot(folder))
        summary = {"cases": [case], "results": [result], "model": "model-x",
                   "reasoning_effort": "high", "codex_version": "1", "timeout_seconds": 60,
                   "runner_sha256": "frozen", "usage": usage,
                   "admission_limits": {"tasks": 1, "input_tokens": 1000, "output_tokens": 100},
                   "package": {"content_sha256": name}}
        smoke.package.write_json(root / "summary.json", summary)
        return root

    def test_matched_bundle_withholds_identity_but_retains_failed_checks(self):
        left, right = self.run_record("baseline"), self.run_record("enhanced", failed=True)
        out, key = self.root / "review", self.root / "key.json"
        mapping = review.bundle([left, right], out, key)
        text = "\n".join(p.read_text() for p in out.rglob("*") if p.is_file())
        for hidden in ("model-x", "secret-operator", str(left), str(right), "content_sha256"):
            self.assertNotIn(hidden, text)
        self.assertIn('"repository_unchanged": false', text)
        self.assertEqual(set(mapping["samples"]), {"A", "B"})
        self.assertEqual(mapping["bundle_files"], smoke.snapshot(out))

    def test_retained_source_tampering_blocks_bundle(self):
        root = self.run_record("first")
        (root / "verification/workspace/greet.py").write_text("changed after delivery")
        with self.assertRaisesRegex(ValueError, "delivery changed"):
            review.bundle([root], self.root / "review", self.root / "key.json")

    def test_mismatched_model_or_project_blocks_comparison(self):
        for field in ("model", "initial_files"):
            left, right = self.run_record(field + "-left"), self.run_record(field + "-right")
            summary = json.loads((right / "summary.json").read_text())
            if field == "model":
                summary[field] = "different-model"
            else:
                result = summary["results"][0]
                result[field] = {"different": "input"}
                folder = right / "verification"
                smoke.package.write_json(folder / "result.json", result)
                (folder / "files.json").unlink()
                smoke.package.write_json(folder / "files.json", smoke.snapshot(folder))
            smoke.package.write_json(right / "summary.json", summary)
            with self.assertRaisesRegex(ValueError, "unmatched"):
                review.bundle([left, right], self.root / (field + "-review"), self.root / (field + "-key"))

    def test_missing_attempt_and_key_in_bundle_are_rejected(self):
        root = self.run_record("first")
        out = self.root / "review"
        with self.assertRaisesRegex(ValueError, "separate key"):
            review.bundle([root], out, out / "key.json")
        summary = json.loads((root / "summary.json").read_text())
        summary["results"] = []
        smoke.package.write_json(root / "summary.json", summary)
        with self.assertRaisesRegex(ValueError, "incomplete run"):
            review.bundle([root], out, self.root / "key.json")


if __name__ == "__main__":
    unittest.main()
