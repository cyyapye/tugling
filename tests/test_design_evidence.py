"""Synthetic evidence only: structural checks are not rendered-review proof."""
import base64
import copy
import types
import json
from pathlib import Path
import tempfile
import unittest


HELPER = Path(__file__).resolve().parents[1] / "plugins/tugling/skills/poteto-mode/scripts/design_evidence.py"
evidence = types.ModuleType("design_evidence")
evidence.__file__ = str(HELPER)
exec(compile(HELPER.read_text(), str(HELPER), "exec"), evidence.__dict__)
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a1ioAAAAASUVORK5CYII=")


class DesignEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.root = self.base / "project"
        self.root.mkdir()
        (self.root / "src").mkdir()
        (self.root / "src/ui.ts").write_text("synthetic UI")
        (self.root / "src/font.woff2").write_bytes(b"synthetic asset")
        (self.root / "contract.md").write_text("Synthetic project contract")
        self.profile = {"schemaVersion": 1, "project": "Synthetic", "contracts": ["contract.md"],
                        "sourceRoots": ["src"], "sourceFiles": ["contract.md"],
                        "theme": "src/ui.ts", "components": "src/ui.ts", "catalogue": "src/ui.ts",
                        "references": {"reading": "Synthetic record"}, "checks": {"native": ["synthetic-test"]},
                        "criteria": [{"id": "meaning", "question": "Is the meaning clear?"}]}
        self.profile_path = self.base / "profile.json"
        self.write(self.profile_path, self.profile)
        evidence.initialize(self.root, self.profile_path)
        (self.base / "screen.png").write_bytes(PNG)
        (self.base / "native.log").write_text("Synthetic log; not runtime verification")
        self.brief = {"id": "record", "task": "Review a record", "meaning": "Record and source are distinct",
                      "scope": "review", "patternBasis": "Synthetic reference", "requiredStates": ["ordinary"],
                      "components": ["Record"], "checks": [{"command": "synthetic-test", "evidence": "native.log"}],
                      "images": [{"id": "wide", "role": "screen", "state": "ordinary", "viewport": "desktop", "path": "screen.png"},
                                 {"id": "narrow", "role": "screen", "state": "ordinary", "viewport": "mobile", "path": "screen.png"},
                                 {"id": "reference", "role": "reference", "state": "approved", "viewport": "desktop", "path": "screen.png"}]}
        self.brief_path = self.base / "brief.json"
        self.packet = self.base / "packet"
        self.review_path = self.base / "review.json"

    def write(self, path, value):
        path.write_text(json.dumps(value))

    def package(self):
        self.write(self.brief_path, self.brief)
        return evidence.prepare(self.root, self.brief_path, self.packet)

    def review(self):
        result = self.package()
        review = {"packetFingerprint": result["fingerprint"], "reviewer": "Synthetic unit test",
                  "firstLook": [{"image": i["id"], "inference": "Synthetic interpretation", "questions": []}
                                for i in self.brief["images"] if i["role"] == "screen"],
                  "observations": [{"image": i["id"], "observation": "Synthetic observation"} for i in self.brief["images"]],
                  "criteria": [{"id": "meaning", "outcome": "acceptable", "evidence": ["wide"], "explanation": "Synthetic conclusion"}],
                  "findings": [], "questions": []}
        self.write(self.review_path, review)
        return review

    def check(self):
        return evidence.check(self.root, self.packet, self.review_path)

    def test_complete_packet_is_advisory(self):
        self.review()
        result = self.check()
        self.assertEqual(result["status"], "REVIEW_COMPLETE")
        self.assertTrue(result["advisory"])

    def test_same_setup_preserves_file(self):
        target = self.root / evidence.PROFILE
        before = target.stat().st_mtime_ns
        self.assertEqual(evidence.initialize(self.root, self.profile_path)["status"], "UNCHANGED")
        self.assertEqual(target.stat().st_mtime_ns, before)

    def test_changed_setup_preserves_user_configuration(self):
        self.profile["project"] = "Changed"
        self.write(self.profile_path, self.profile)
        with self.assertRaisesRegex(ValueError, "Existing profile differs"):
            evidence.initialize(self.root, self.profile_path)
        self.assertEqual(evidence.read_json(self.root / evidence.PROFILE)["project"], "Synthetic")

    def test_custom_viewport_project(self):
        self.profile["viewports"] = ["workstation"]
        self.write(self.root / evidence.PROFILE, self.profile)
        self.brief["images"] = [self.brief["images"][0], self.brief["images"][2]]
        for item in self.brief["images"]:
            item["viewport"] = "workstation"
        self.review()
        self.assertEqual(self.check()["status"], "REVIEW_COMPLETE")

    def test_missing_mobile_does_not_leave_partial_packet(self):
        self.brief["images"].pop(1)
        with self.assertRaisesRegex(ValueError, "Missing current screen"):
            self.package()
        self.assertFalse(self.packet.exists())

    def test_missing_reference(self):
        self.brief["images"].pop()
        with self.assertRaisesRegex(ValueError, "Missing approved reference"):
            self.package()

    def test_non_image_rejected(self):
        (self.base / "screen.png").write_text("not a screenshot")
        with self.assertRaisesRegex(ValueError, "Expected PNG"):
            self.package()

    def test_code_and_asset_drift(self):
        self.review()
        for file in ["src/ui.ts", "src/font.woff2"]:
            with self.subTest(file=file):
                path = self.root / file
                before = path.read_bytes()
                path.write_bytes(b"changed")
                with self.assertRaisesRegex(ValueError, "Project source changed"):
                    self.check()
                path.write_bytes(before)

    def test_new_source_is_not_ignored(self):
        self.review()
        (self.root / "src/new.ts").write_text("new source")
        with self.assertRaisesRegex(ValueError, "Project source changed"):
            self.check()

    def test_changed_packaged_evidence(self):
        self.review()
        for file in ["images/wide.png", "check-1.log"]:
            with self.subTest(file=file):
                path = self.packet / file
                before = path.read_bytes()
                path.write_bytes(b"changed")
                with self.assertRaisesRegex(ValueError, "Evidence changed"):
                    self.check()
                path.write_bytes(before)

    def test_reviewer_inputs_cannot_redirect_first_look_or_change_instructions(self):
        self.review()
        for file in ["first-look.json", "reviewer.md", "response-template.json"]:
            with self.subTest(file=file):
                path = self.packet / file
                before = path.read_bytes()
                if file == "first-look.json":
                    content = evidence.read_json(path)
                    content[0]["path"] = "stale.png"
                    self.write(path, content)
                elif file.endswith(".json"):
                    content = evidence.read_json(path)
                    content["reviewer"] = "Changed instructions"
                    self.write(path, content)
                else:
                    path.write_text("Use an older screenshot")
                with self.assertRaisesRegex(ValueError, "Reviewer input changed"):
                    self.check()
                path.write_bytes(before)

    def test_review_coverage_is_exact(self):
        original = self.review()
        for key in ["firstLook", "observations", "criteria"]:
            for duplicate in [False, True]:
                review = copy.deepcopy(original)
                review[key].append(review[key][0]) if duplicate else review[key].pop()
                self.write(self.review_path, review)
                with self.assertRaisesRegex(ValueError, "missing, duplicate or unknown"):
                    self.check()

    def test_unknown_image_reference(self):
        review = self.review()
        review["criteria"][0]["evidence"] = ["absent"]
        self.write(self.review_path, review)
        with self.assertRaisesRegex(ValueError, "Unknown image evidence"):
            self.check()

    def test_findings_and_uncertainties_do_not_pass(self):
        review = self.review()
        review["criteria"][0]["outcome"] = "uncertain"
        review["questions"] = ["Meaning unclear"]
        self.write(self.review_path, review)
        self.assertEqual(self.check()["status"], "INCOMPLETE")
        review["questions"] = []
        review["criteria"][0]["outcome"] = "problem"
        with self.assertRaisesRegex(ValueError, "Problem lacks finding"):
            self.write(self.review_path, review)
            self.check()
        review["findings"] = [{"criterion": "meaning", "image": "wide", "severity": "material",
                               "location": "Heading", "problem": "Wrong scope", "correction": "Correct scope"}]
        self.write(self.review_path, review)
        self.assertEqual(self.check()["status"], "CHANGES_REQUESTED")

    def test_source_path_escape_and_symlink(self):
        for name in ["../profile.json", str(self.profile_path)]:
            self.profile["sourceFiles"] = [name]
            with self.assertRaisesRegex(ValueError, "inside project"):
                evidence.source_files(self.root, self.profile)
        self.profile["sourceFiles"] = ["contract.md"]
        (self.root / "src/linked").symlink_to(self.base / "native.log")
        with self.assertRaisesRegex(ValueError, "symlink"):
            evidence.source_files(self.root, self.profile)

    def test_packet_cannot_hash_itself_or_overwrite_prior_evidence(self):
        self.write(self.brief_path, self.brief)
        with self.assertRaisesRegex(ValueError, "outside source roots"):
            evidence.prepare(self.root, self.brief_path, self.root / "src/packet")
        self.package()
        with self.assertRaisesRegex(ValueError, "new packet directory"):
            self.package()

    def test_packet_tamper_detected(self):
        self.review()
        packet = evidence.read_json(self.packet / "packet.json")
        packet["brief"]["task"] = "Changed"
        self.write(self.packet / "packet.json", packet)
        with self.assertRaisesRegex(ValueError, "Packet was modified"):
            self.check()


if __name__ == "__main__":
    unittest.main()
