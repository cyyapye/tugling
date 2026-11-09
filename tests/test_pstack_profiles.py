from pathlib import Path
import re
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
            self.assertEqual(len(report["pstack"]["skills"]), 58)
            self.assertNotIn("setup-ui", report["pstack"]["skills"])
            self.assertFalse((base / "setup-ui").exists())
            for relative in (profiles.sources.LICENSE, "poteto-mode/playbooks/eval.md", "poteto-mode/playbooks/investigation.md"):
                self.assertEqual((base / relative).read_bytes(), (profiles.sources.BUNDLE / relative).read_bytes())
            self.assertIn("plan-only request", (base / "architect/SKILL.md").read_text())
            self.assertIn("Opening a PR requires", (base / "poteto-mode/playbooks/authoring-a-skill.md").read_text())
            self.assertIn("Inherit the configured session model", (base / profiles.ADAPTER).read_text())
            self.assertNotIn("extensions/", (base / profiles.ADAPTER).read_text())
            self.assertIn("extensions/repo-verify.md", (enhanced / profiles.ADAPTER).read_text())
            self.assertFalse((enhanced / profiles.EXTENSIONS / "async-safety.md").exists())
            setup = (enhanced / profiles.EXTENSIONS / "project-setup.md").read_text()
            self.assertNotIn("setup-ui", setup)
            for mode in ("Assessment", "Bootstrap", "Adoption", "Enforcement"):
                self.assertIn(f"**{mode}:**", setup)
            for reference in ("project-bootstrap.md", "project-adoption.md", "project-enforcement.md"):
                self.assertIn(f"]({reference})", setup)
            profiles.sources.validate(base)
            profiles.sources.validate(enhanced)

    def test_all_profiles_have_resolvable_links_without_local_entry_points(self):
        with tempfile.TemporaryDirectory() as directory:
            for extension in profiles.TRIGGERS:
                with self.subTest(extension=extension):
                    out = Path(directory) / extension
                    profiles.freeze(profiles.smoke.ROOT, out, extension)
                    for arm in ("pstack", "enhanced"):
                        skills = out / arm / profiles.smoke.package.PLUGIN_RELATIVE / "skills"
                        self.assertFalse((skills / "setup-ui").exists())
                        for path in skills.rglob("*.md"):
                            for link in re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", path.read_text()):
                                if not profiles.urlsplit(link).scheme and not link.startswith(("#", "//")):
                                    self.assertTrue((path.parent / link).exists(),
                                                    f"broken {arm} link: {path}: {link}")


if __name__ == "__main__":
    unittest.main()
