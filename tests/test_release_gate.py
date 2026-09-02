from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import release_gate as gate


class ReleaseGateTest(unittest.TestCase):
    def proofs(self, root: Path, *, attempts: int = 3) -> tuple[Path, Path]:
        matrix = gate.validate_matrix()
        plugin = gate.plugin_identity()
        candidate_revision = "b" * 40
        behavioral = {
            "passed": True,
            "candidate": {
                "revision": candidate_revision,
                "version": plugin["version"],
                "plugin_content_sha256": plugin["content_sha256"],
            },
            "released": {"revision": "a" * 40, "version": "0.3.0"},
            "reproducibility": {
                "model": "model-test",
                "reasoning_effort": "medium",
                "conditions": matrix["conditions"],
                "attempts": attempts,
                "case_ids": matrix["required_case_ids"],
            },
            "metrics": {
                "released_regressions": 0,
                "gates": {"promotion": {"passed": True}},
            },
            "per_case": [
                {"case_id": case_id, "attempt": attempt}
                for case_id in matrix["required_case_ids"]
                for attempt in range(1, attempts + 1)
            ],
            "plugin_surface_changes": {
                "permissions_changed": False,
                "hooks_changed": False,
            },
            "privacy_scan": {"passed": True},
            "policy_scan": {
                "configured": True,
                "passed": True,
                "pattern_file_sha256": "c" * 64,
            },
        }
        clean = {
            "passed": True,
            "mode": "public-cli-live",
            "source": {
                "repository": "cyyapye/tugling",
                "requested_revision": candidate_revision,
                "resolved_revision": candidate_revision,
            },
            "codex": {"version": "codex-test"},
            "plugin": plugin,
            "live": {
                "ran": True,
                "model": "model-test",
                "reasoning_effort": "medium",
                "selected_skill": "repo-verify",
                "verification_order": "repository-native-first",
                "installed_skill_read_observed": False,
                "repository_unchanged": True,
            },
        }
        behavioral_path = root / "behavioral.json"
        clean_path = root / "clean.json"
        behavioral_path.write_text(json.dumps(behavioral), encoding="utf-8")
        clean_path.write_text(json.dumps(clean), encoding="utf-8")
        return behavioral_path, clean_path

    def test_matrix_requires_full_language_and_surface_breadth(self) -> None:
        matrix = gate.validate_matrix()
        self.assertGreaterEqual(matrix["minimum_attempts"], 3)
        self.assertTrue(
            {"python-cli", "python-service", "typescript-worker", "react-ui"}.issubset(
                matrix["project_types"]
            )
        )

    def test_certificate_assembles_and_verifies_from_matching_proofs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            behavioral, clean = self.proofs(root)
            certificate = gate.assemble_certificate(
                version=gate.plugin_identity()["version"],
                behavioral_path=behavioral,
                clean_room_path=clean,
            )
            self.assertTrue(certificate["passed"])
            certificate_path = root / "certificate.json"
            certificate_path.write_text(json.dumps(certificate), encoding="utf-8")
            verified = gate.verify_certificate(path=certificate_path)
            self.assertEqual(verified["plugin"], gate.plugin_identity())

    def test_certificate_rejects_fewer_than_three_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            behavioral, clean = self.proofs(root, attempts=2)
            certificate = gate.assemble_certificate(
                version=gate.plugin_identity()["version"],
                behavioral_path=behavioral,
                clean_room_path=clean,
            )
            self.assertFalse(certificate["passed"])
            self.assertFalse(certificate["checks"]["minimum_attempts"])


if __name__ == "__main__":
    unittest.main()
