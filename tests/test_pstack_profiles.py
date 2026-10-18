from pathlib import Path
import tempfile
import unittest

from scripts import pstack_profiles as profiles


class PstackProfilesTest(unittest.TestCase):
    def test_profiles_preserve_upstream_and_scope_with_only_one_extension_delta(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "packages"
            report = profiles.freeze(profiles.smoke.ROOT, out, "repo-verify")
            prefix = profiles.smoke.package.PLUGIN_RELATIVE / "skills"
            base, enhanced = out / "pstack" / prefix, out / "enhanced" / prefix
            self.assertFalse((base / profiles.EXTENSIONS).exists())
            self.assertEqual(report["pstack"]["skills"], report["enhanced"]["skills"])
            self.assertEqual(len(report["pstack"]["skills"]), 54)
            for relative in (profiles.sources.LICENSE, "poteto-mode/playbooks/eval.md", "poteto-mode/playbooks/investigation.md"):
                self.assertEqual((base / relative).read_bytes(), (profiles.sources.BUNDLE / relative).read_bytes())
            self.assertIn("plan-only request", (base / "architect/SKILL.md").read_text())
            self.assertIn("Opening a PR requires", (base / "poteto-mode/playbooks/authoring-a-skill.md").read_text())
            self.assertIn("Inherit the configured session model", (base / profiles.ADAPTER).read_text())
            self.assertNotIn("extensions/", (base / profiles.ADAPTER).read_text())
            self.assertIn("extensions/repo-verify.md", (enhanced / profiles.ADAPTER).read_text())
            self.assertFalse((enhanced / profiles.EXTENSIONS / "async-safety.md").exists())
            profiles.sources.validate(base)
            profiles.sources.validate(enhanced)


if __name__ == "__main__":
    unittest.main()
