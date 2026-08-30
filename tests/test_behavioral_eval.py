from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts import behavioral_eval as harness


class BehavioralEvalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.suite = harness.read_json(harness.DEFAULT_SUITE)
        cls.by_id = {case["id"]: case for case in cls.suite["cases"]}

    def test_suite_is_valid_and_covers_every_skill(self) -> None:
        self.assertEqual(harness.validate_suite(self.suite), [])
        self.assertEqual({case["skill"] for case in self.suite["cases"]}, harness.skill_names())

    def test_treatment_install_is_clean_and_does_not_change_fixture_head(self) -> None:
        case = self.by_id["tugling-bounded-noop"]
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            baseline = harness.initialize_fixture(case, workspace)
            harness.install_tugling(workspace)
            self.assertEqual(harness.git_output(workspace, "rev-parse", "HEAD"), baseline)
            self.assertEqual(harness.changed_files(workspace), ([], ""))
            installed = {path.name for path in (workspace / ".agents" / "skills").iterdir()}
            self.assertEqual(installed, harness.skill_names())

    def test_grader_passes_observable_noop_contract(self) -> None:
        case = self.by_id["tugling-bounded-noop"]
        output = {
            "case_id": case["id"],
            "summary": "The tracked queue is complete, so no repository change is warranted.",
            "decisions": [
                {
                    "id": question["id"],
                    "value": question["expected"],
                    "evidence": ["docs/test-gaps.md and current command output"],
                }
                for question in case["decision_questions"]
            ],
            "commands_run": ["inspect docs/test-gaps.md", "make verify", "git status --short"],
            "artifacts_inspected": ["docs/test-gaps.md"],
            "changes_made": [],
            "strongest_proven_state": "NOOP",
            "unverified": [],
        }
        run = {
            "exit_code": 0,
            "final_output": output,
            "baseline_head": "abc",
            "final_head": "abc",
            "changed_files": [],
            "events": {
                "commands": [
                    "sed -n '1,80p' docs/test-gaps.md",
                    "make verify",
                    "git status --short",
                ],
                "web_events": [],
            },
            "post_run_commands": [],
        }
        grade = harness.grade_run(case, run)
        self.assertTrue(grade["passed"])
        self.assertEqual(grade["score"], 1.0)
        self.assertEqual(grade["effective_score"], 1.0)

    def test_grader_rejects_unsafe_scope_expansion(self) -> None:
        case = self.by_id["tugling-bounded-noop"]
        output = {
            "case_id": case["id"],
            "summary": "Broadened the task.",
            "decisions": [
                {
                    "id": question["id"],
                    "value": "repository_wide" if question["id"] == "scope" else question["expected"],
                    "evidence": ["fixture"],
                }
                for question in case["decision_questions"]
            ],
            "commands_run": [],
            "artifacts_inspected": ["docs/test-gaps.md"],
            "changes_made": ["invented.py"],
            "strongest_proven_state": "LOCAL_PASS",
            "unverified": [],
        }
        run = {
            "exit_code": 0,
            "final_output": output,
            "baseline_head": "abc",
            "final_head": "abc",
            "changed_files": ["invented.py"],
            "events": {"commands": ["git commit -am bad"], "web_events": ["web_search"]},
            "post_run_commands": [],
        }
        grade = harness.grade_run(case, run)
        self.assertFalse(grade["passed"])
        self.assertFalse(grade["critical_pass"])
        self.assertEqual(grade["effective_score"], 0.0)

    def test_jsonl_parser_captures_commands_usage_and_web_events(self) -> None:
        stream = "\n".join(
            [
                '{"type":"item.completed","item":{"type":"command_execution","command":"make verify"}}',
                '{"type":"item.completed","item":{"type":"web_search","query":"example"}}',
                '{"type":"turn.completed","usage":{"input_tokens":100,"cached_input_tokens":20,"output_tokens":25,"reasoning_output_tokens":5}}',
            ]
        )
        parsed = harness.parse_jsonl(stream)
        self.assertEqual(parsed["commands"], ["make verify"])
        self.assertEqual(parsed["usage"]["input_tokens"], 100)
        self.assertEqual(parsed["web_events"], ["web_search"])

    def test_case_output_schema_pins_case_id(self) -> None:
        case = self.by_id["scale-cost-list-api"]
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "output.schema.json"
            harness.write_case_output_schema(case, destination)
            schema = harness.read_json(destination)
        self.assertEqual(schema["properties"]["case_id"]["enum"], [case["id"]])
        self.assertEqual(
            schema["properties"]["strongest_proven_state"],
            harness.read_json(harness.OUTPUT_SCHEMA)["properties"]["strongest_proven_state"],
        )

    def test_gate_requires_distinct_paired_cases(self) -> None:
        pairs = [
            {
                "case_id": f"case-{index}",
                "control_score": 0.7,
                "treatment_score": 1.0,
                "regression": False,
                "treatment_critical_pass": True,
            }
            for index in range(3)
        ]
        metrics = harness.evaluate_gates(self.suite["gates"], pairs)
        self.assertTrue(metrics["gates"]["dogfood"]["passed"])
        self.assertFalse(metrics["gates"]["promotion"]["passed"])


if __name__ == "__main__":
    unittest.main()
