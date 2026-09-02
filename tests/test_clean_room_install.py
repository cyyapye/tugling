from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import clean_room_install as clean_room


class CleanRoomInstallTest(unittest.TestCase):
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
                '{"type":"item.completed","item":{"type":"command_execution","command":"sed repo-verify/SKILL.md"}}',
                '{"type":"turn.completed","usage":{"input_tokens":11,"cached_input_tokens":7,"output_tokens":3}}',
            ]
        )
        parsed = clean_room.parse_events(events)
        self.assertEqual(parsed["commands"], ["sed repo-verify/SKILL.md"])
        self.assertEqual(parsed["usage"]["input_tokens"], 11)


if __name__ == "__main__":
    unittest.main()
