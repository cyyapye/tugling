from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import clean_room_install as clean_room


class CleanRoomInstallTest(unittest.TestCase):
    def test_moving_alias_requires_an_exact_expected_commit_and_no_live_task(self) -> None:
        for ref, revision, live in (("stable", None, False), ("main", "a" * 40, False),
                                    ("stable", "a" * 40, True), ("a" * 40, "b" * 40, False)):
            with self.subTest(ref=ref, revision=revision, live=live), \
                 mock.patch.object(clean_room, "run") as run:
                with self.assertRaisesRegex(clean_room.CleanRoomError, "exact SHA"):
                    clean_room.public_install(source="cyyapye/tugling", ref=ref, expected_revision=revision,
                        expected_root=clean_room.ROOT, codex_bin="synthetic", codex_version="synthetic",
                        auth_home=Path("/synthetic/no-auth"), live=live, model="", reasoning_effort="", timeout=120)
                run.assert_not_called()

    def test_free_exact_revision_install_does_not_inherit_credentials_or_user_configuration(self) -> None:
        observed = []
        def network_boundary(argv, *, cwd, timeout, env):
            observed.append(env)
            raise RuntimeError("synthetic network boundary")
        with mock.patch.dict(os.environ, {"GH_TOKEN": "synthetic-github-token",
                 "OPENAI_API_KEY": "synthetic-provider-key", "HOME": "/synthetic/user-home",
                 "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_VALUE_0": "synthetic-user-config"}), \
             mock.patch.object(clean_room, "run", side_effect=network_boundary), \
             mock.patch.object(clean_room, "run_live_discovery") as model:
            with self.assertRaisesRegex(RuntimeError, "synthetic network boundary"):
                clean_room.public_install(source="cyyapye/tugling", ref="a" * 40,
                    expected_root=clean_room.ROOT, codex_bin="synthetic", codex_version="synthetic",
                    auth_home=Path("/synthetic/auth"), live=False, model="", reasoning_effort="", timeout=120)
            model.assert_not_called()
        self.assertEqual(len(observed), 1)
        for key in ("GH_TOKEN", "OPENAI_API_KEY", "GIT_CONFIG_COUNT", "GIT_CONFIG_VALUE_0"):
            self.assertNotIn(key, observed[0])
        self.assertNotEqual(observed[0]["HOME"], "/synthetic/user-home")
        self.assertEqual(observed[0]["GIT_CONFIG_GLOBAL"], os.devnull)

    def test_public_install_rejects_marketplace_or_cache_mode_drift_with_identical_bytes(self) -> None:
        original = clean_room.package_report(clean_room.ROOT)
        for damaged in (None, "marketplace", "cache"):
            def install(argv, *, cwd, timeout, env):
                home = Path(env["CODEX_HOME"])
                marketplace = home / ".tmp/marketplaces/tugling"
                cache = home / "plugins/tugling"
                if argv[2] == "marketplace":
                    for relative in (clean_room.MARKETPLACE, clean_room.PLUGIN_RELATIVE):
                        target = marketplace / relative
                        target.parent.mkdir(parents=True, exist_ok=True)
                        if (clean_room.ROOT / relative).is_dir():
                            shutil.copytree(clean_room.ROOT / relative, target)
                        else:
                            shutil.copy2(clean_room.ROOT / relative, target)
                    if damaged == "marketplace":
                        path = next(p for p in (marketplace / clean_room.PLUGIN_RELATIVE).rglob("*")
                                    if p.is_file() and p.stat().st_mode & 0o111)
                        path.chmod(0o644)
                        self.assertEqual(clean_room.package_report(marketplace), original)
                    return subprocess.CompletedProcess(argv, 0, "", "")
                shutil.copytree(clean_room.ROOT / clean_room.PLUGIN_RELATIVE, cache)
                if damaged == "cache":
                    path = next(p for p in cache.rglob("*") if p.is_file() and p.stat().st_mode & 0o111)
                    path.chmod(0o644)
                    self.assertEqual(clean_room.digest_tree(cache), original["content_sha256"])
                return subprocess.CompletedProcess(argv, 0, json.dumps({"installedPath": str(cache)}), "")
            with self.subTest(damaged=damaged), mock.patch.object(clean_room, "run", side_effect=install), \
                 mock.patch.object(clean_room, "git_output", return_value="a" * 40):
                proof = clean_room.public_install(source="cyyapye/tugling", ref="a" * 40,
                    expected_root=clean_room.ROOT, codex_bin="synthetic", codex_version="synthetic",
                    auth_home=Path("/synthetic/auth"), live=False, model="", reasoning_effort="", timeout=120)
                self.assertEqual(proof["passed"], damaged is None)
                if damaged:
                    check = "marketplace_package_matches_candidate" if damaged == "marketplace" else "installed_plugin_matches_candidate"
                    self.assertFalse(proof["checks"][check])

    def test_isolated_package_contains_the_complete_discoverable_plugin(self) -> None:
        direct = clean_room.package_report(clean_room.ROOT)
        isolated = clean_room.isolated_package_report(clean_room.ROOT)
        self.assertEqual(isolated["name"], "tugling")
        self.assertEqual(isolated["version"], direct["version"])
        self.assertEqual(isolated["content_sha256"], direct["content_sha256"])
        self.assertEqual(isolated["skills"], direct["skills"])
        self.assertEqual(isolated["mode"], "isolated-package")

    def test_package_rejects_a_marketplace_path_outside_the_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marketplace = root / ".agents" / "plugins" / "marketplace.json"
            marketplace.parent.mkdir(parents=True)
            marketplace.write_text(
                json.dumps(
                    {
                        "name": "tugling",
                        "interface": {"displayName": "Tugling"},
                        "plugins": [
                            {
                                "name": "tugling",
                                "source": {"source": "local", "path": "../outside"},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(clean_room.CleanRoomError, "marketplace must point"):
                clean_room.package_report(root)

    def test_event_parser_records_skill_read_commands_and_usage(self) -> None:
        events = "\n".join(
            [
                '{"type":"item.completed","item":{"type":"command_execution","command":"sed principle-prove-it-works/SKILL.md"}}',
                '{"type":"turn.completed","usage":{"input_tokens":11,"cached_input_tokens":7,"output_tokens":3}}',
            ]
        )
        parsed = clean_room.parse_events(events)
        self.assertEqual(parsed["commands"], ["sed principle-prove-it-works/SKILL.md"])
        self.assertEqual(parsed["usage"]["input_tokens"], 11)


if __name__ == "__main__":
    unittest.main()
