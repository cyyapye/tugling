from __future__ import annotations

import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts import behavioral_eval, pstack_sources


class PstackSourcesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bundle = self.root / "pstack"
        shutil.copytree(pstack_sources.BUNDLE, self.bundle)

    def test_pinned_bundle_passes(self) -> None:
        self.assertEqual(pstack_sources.validate(self.bundle), len(json.loads((self.bundle / pstack_sources.MANIFEST).read_text())["files"]))

    def test_changed_source_fails_even_when_all_links_still_resolve(self) -> None:
        path = self.bundle / "principle-prove-it-works/SKILL.md"
        path.write_text(path.read_text() + "\nTrust the self-report.\n")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            pstack_sources.validate(self.bundle)

    def test_missing_license_and_unrecorded_copy_fail(self) -> None:
        license_path = self.bundle / pstack_sources.LICENSE
        original = license_path.read_bytes()
        license_path.unlink()
        with self.assertRaisesRegex(ValueError, "missing"):
            pstack_sources.validate(self.bundle)
        license_path.write_bytes(original)
        (self.bundle / "unrecorded.md").write_text("untracked upstream guidance")
        with self.assertRaisesRegex(ValueError, "inventory"):
            pstack_sources.validate(self.bundle)

    def test_adaptation_requires_a_record(self) -> None:
        path = self.bundle / pstack_sources.MANIFEST
        manifest = json.loads(path.read_text())
        item = next(item for item in manifest["files"] if item["path"] == "architect/SKILL.md")
        item["changes"] = []
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "undocumented adaptation"):
            pstack_sources.validate(self.bundle)

    def test_manifest_cannot_escape_bundle(self) -> None:
        path = self.bundle / pstack_sources.MANIFEST
        manifest = json.loads(path.read_text())
        manifest["files"][0]["path"] = "../outside.md"
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "invalid source path"):
            pstack_sources.validate(self.bundle)

    def test_isolated_skill_install_keeps_sources_license_and_local_links(self) -> None:
        workspace = self.root / "project"
        (workspace / ".git/info").mkdir(parents=True)
        behavioral_eval.install_tugling(workspace)
        skills = workspace / ".agents/skills"
        bundle = skills
        self.assertEqual(pstack_sources.validate(bundle), pstack_sources.validate())
        self.assertEqual(len(list(skills.rglob("SKILL.md"))), 54)
        for path in skills.rglob("*.md"):
            for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", path.read_text()):
                if target.startswith(("https://", "http://", "#")):
                    continue
                with self.subTest(path=path.relative_to(skills), target=target):
                    resolved = (path.parent / target.split("#", 1)[0]).resolve()
                    self.assertTrue(resolved.is_relative_to(skills.resolve()))
                    self.assertTrue(resolved.exists())


if __name__ == "__main__":
    unittest.main()
