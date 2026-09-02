from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import behavioral_eval as harness


class BehavioralEvalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.suite = harness.read_json(harness.DEFAULT_SUITE)
        cls.by_id = {case["id"]: case for case in cls.suite["cases"]}

    def test_suite_is_valid_and_covers_every_skill(self) -> None:
        self.assertEqual(harness.validate_suite(self.suite), [])
        self.assertEqual({case["skill"] for case in self.suite["cases"]}, harness.skill_names())

    def test_candidate_install_is_clean_and_does_not_change_fixture_head(self) -> None:
        case = self.by_id["tugling-bounded-noop"]
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            baseline = harness.initialize_fixture(case, workspace)
            harness.install_tugling(workspace)
            self.assertEqual(harness.git_output(workspace, "rev-parse", "HEAD"), baseline)
            self.assertEqual(harness.changed_files(workspace), ([], ""))
            installed = {path.name for path in (workspace / ".agents" / "skills").iterdir()}
            self.assertEqual(installed, harness.skill_names())

    def test_fixture_preparation_and_independent_post_commands_are_green(self) -> None:
        fixture_integrity_cases = {
            "async-safety-typescript-worker",
            "screenshot-first-mobile-overflow",
        }
        for case in (
            candidate
            for candidate in self.suite["cases"]
            if candidate["id"] in fixture_integrity_cases
        ):
            with self.subTest(case=case["id"]), tempfile.TemporaryDirectory() as directory:
                workspace = Path(directory) / "workspace"
                harness.initialize_fixture(case, workspace)
                results = harness.run_post_commands(case, workspace)
                self.assertTrue(
                    all(result["exit_code"] == 0 for result in results),
                    results,
                )

    def test_changed_files_preserves_first_modified_path(self) -> None:
        case = self.by_id["skill-delivery-overtrigger"]
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            harness.initialize_fixture(case, workspace)
            path = workspace / "evals" / "routing.json"
            path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            files, status = harness.changed_files(workspace)
        self.assertEqual(files, ["evals/routing.json"])
        self.assertTrue(status.startswith(" M evals/routing.json"))

    def test_image_arguments_are_terminated_before_prompt(self) -> None:
        argv = ["codex", "exec"]
        images = [Path("desktop.png"), Path("mobile.png")]
        harness.append_prompt_and_images(argv, images, "Inspect both screenshots")
        self.assertEqual(
            argv,
            [
                "codex",
                "exec",
                "--image",
                "desktop.png",
                "mobile.png",
                "--",
                "Inspect both screenshots",
            ],
        )

    def test_isolated_codex_home_copies_only_auth(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "auth.json").write_text('{"token":"synthetic"}\n', encoding="utf-8")
            (source / "config.toml").write_text("model = 'example'\n", encoding="utf-8")
            (source / "skills").mkdir()
            destination = root / "isolated"
            harness.prepare_isolated_codex_home(destination, source)
            self.assertEqual(
                {path.name for path in destination.iterdir()},
                {"auth.json"},
            )
            self.assertEqual(
                (destination / "auth.json").read_text(encoding="utf-8"),
                '{"token":"synthetic"}\n',
            )

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
        comparisons = [
            {
                "case_id": f"case-{index}",
                "control_score": 0.7,
                "released_score": None,
                "candidate_score": 1.0,
                "candidate_vs_control": 0.3,
                "candidate_vs_released": None,
                "control_regression": False,
                "released_regression": None,
                "candidate_critical_pass": True,
            }
            for index in range(3)
        ]
        metrics = harness.evaluate_gates(self.suite["gates"], comparisons)
        self.assertTrue(metrics["gates"]["dogfood"]["passed"])
        self.assertFalse(metrics["gates"]["promotion"]["passed"])

    def test_release_regressions_are_aggregated_per_case(self) -> None:
        comparisons = [
            {
                "case_id": "case-1",
                "attempt": 1,
                "control_score": 0.0,
                "released_score": 1.0,
                "candidate_score": 0.0,
                "candidate_vs_control": 0.0,
                "candidate_vs_released": -1.0,
                "control_regression": False,
                "released_regression": True,
                "candidate_critical_pass": True,
            },
            {
                "case_id": "case-1",
                "attempt": 2,
                "control_score": 0.0,
                "released_score": 0.0,
                "candidate_score": 1.0,
                "candidate_vs_control": 1.0,
                "candidate_vs_released": 1.0,
                "control_regression": False,
                "released_regression": False,
                "candidate_critical_pass": True,
            },
        ]
        metrics = harness.evaluate_gates(self.suite["gates"], comparisons)
        self.assertEqual(metrics["released_attempt_regressions"], 1)
        self.assertEqual(metrics["released_regressions"], 0)
        self.assertEqual(metrics["released_case_aggregates"][0]["delta"], 0.0)

    def test_promotion_allows_noninferior_behavior_with_no_critical_failures(self) -> None:
        comparisons = []
        for index in range(10):
            comparisons.append(
                {
                    "case_id": f"case-{index}",
                    "attempt": 1,
                    "control_score": 0.0,
                    "released_score": 1.0,
                    "candidate_score": 1.0,
                    "candidate_vs_control": 1.0,
                    "candidate_vs_released": 0.0,
                    "control_regression": False,
                    "released_regression": False,
                    "candidate_critical_pass": True,
                }
            )
        metrics = harness.evaluate_gates(self.suite["gates"], comparisons)
        self.assertTrue(metrics["gates"]["promotion"]["passed"])

    def test_conditions_preserve_legacy_alias_and_add_release_comparison(self) -> None:
        self.assertEqual(harness.conditions_for("treatment"), ["candidate"])
        self.assertEqual(harness.conditions_for("both"), ["control", "candidate"])
        self.assertEqual(
            harness.conditions_for("all"),
            ["control", "released", "candidate"],
        )

    def test_parser_accepts_bounded_parallel_jobs(self) -> None:
        args = harness.build_parser().parse_args(
            [
                "run",
                "--case",
                "delivery-plan-api-migration",
                "--jobs",
                "3",
                "--model",
                "model-test",
                "--reasoning-effort",
                "medium",
            ]
        )
        self.assertEqual(args.jobs, 3)

    def test_released_baseline_cannot_resolve_to_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(harness.EvalError, "candidate revision"):
                harness.resolve_release_baseline("HEAD", Path(directory))

    def test_distinct_released_baseline_is_materialized_with_exact_identity(self) -> None:
        current = harness.git_output(harness.ROOT, "rev-parse", "HEAD")
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(
                harness,
                "repository_identity",
                return_value={
                    "revision": "f" * 40,
                    "plugin_content_sha256": "0" * 64,
                },
            ):
                baseline = harness.resolve_release_baseline("HEAD", Path(directory))
            self.assertEqual(baseline["revision"], current)
            self.assertTrue((Path(baseline["skills"]) / "tugling" / "SKILL.md").is_file())
            self.assertNotEqual(
                baseline["plugin_content_sha256"],
                "0" * 64,
            )

    def test_policy_scan_records_only_pattern_digest_when_clean(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pattern_file = Path(directory) / "patterns.txt"
            pattern_file.write_text(
                f"runtime-only-{Path(directory).name}\n",
                encoding="utf-8",
            )
            report = harness.policy_scan(pattern_file)
        self.assertTrue(report["configured"])
        self.assertTrue(report["passed"])
        self.assertEqual(report["pattern_count"], 1)
        self.assertNotIn("patterns", report)

    def test_release_proof_requires_clean_distinct_source_and_scans(self) -> None:
        candidate = {
            "revision": "b" * 40,
            "version": "0.4.0",
            "worktree_dirty": False,
            "content_sha256": "c" * 64,
            "plugin_content_sha256": "d" * 64,
        }
        released = {
            "revision": "a" * 40,
            "ref": "v0.2.1",
            "worktree_dirty": False,
            "version": "0.2.1",
            "plugin_content_sha256": "e" * 64,
        }
        summary = {
            "run_id": "synthetic-proof",
            "created_at": "2026-08-30T00:00:00+00:00",
            "candidate_identity": candidate,
            "released_identity": released,
            "codex_version": "codex-test",
            "model": "model-test",
            "reasoning_effort": "medium",
            "conditions": ["control", "released", "candidate"],
            "attempts": 3,
            "case_ids": harness.read_json(harness.RELEASE_MATRIX)["required_case_ids"],
            "metrics": {
                "candidate_average": 1.0,
                "candidate_vs_control": 0.5,
                "candidate_vs_released": 0.2,
                "released_regressions": 0,
                "gates": {"promotion": {"passed": True}},
            },
        }
        proof = harness.release_proof(
            summary=summary,
            comparisons=[],
            results=[],
            policy={"configured": True, "passed": True},
            privacy={"passed": True},
            surface={
                "permissions_changed": False,
                "hooks_changed": False,
                "changed_plugin_paths": [],
            },
        )
        self.assertTrue(proof["passed"])
        summary["candidate_identity"] = {**candidate, "worktree_dirty": True}
        dirty = harness.release_proof(
            summary=summary,
            comparisons=[],
            results=[],
            policy={"configured": True, "passed": True},
            privacy={"passed": True},
            surface={
                "permissions_changed": False,
                "hooks_changed": False,
                "changed_plugin_paths": [],
            },
        )
        self.assertFalse(dirty["passed"])
        self.assertFalse(dirty["checks"]["candidate_worktree_clean"])


if __name__ == "__main__":
    unittest.main()
