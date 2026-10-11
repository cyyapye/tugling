"""Synthetic calibration of the measurement layer; no model/browser claims."""

import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from scripts import ux_eval as ux


class UXEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inputs = self.root / "inputs"
        shutil.copytree(ux.DEFAULT_SUITE.parent, self.inputs)
        self.suite = ux.read(self.inputs / "cases.json")
        self.suite["cases"] = [self.suite["cases"][0], self.suite["cases"][2]]
        ux.write(self.inputs / "cases.json", self.suite)
        # Synthetic probe data tests admission; it does not claim a real CLI run.
        probe = self.root / "probe"
        probe.mkdir()
        for name, body in (("before", "<!-- unread marker -->Before"),
                           ("source_readback", "<!-- unread marker -->Before"),
                           ("expected", "<!-- unread marker -->After"),
                           ("after", "<!-- unread marker -->After"), ("stderr", "")):
            (probe / name).write_text(body)
        (probe / "events").write_text(json.dumps({"type": "item.completed", "item": {
            "type": "file_change", "status": "completed", "changes": [{"kind": "update"}]}}) + "\n"
            + json.dumps({"type": "turn.completed", "usage": {
                "input_tokens": 100, "cached_input_tokens": 20, "output_tokens": 10}}) + "\n")
        ux.write(probe / "execution", {"exit_code": 0, "timed_out": False, "cleanup_complete": True})
        ux.write(self.root / "preflight.json", {"passed": True, "synthetic_test_only": True,
            "builder_probe": {name: "probe/" + name for name in ux.PROBE_FILES}})
        (self.root / "stderr.txt").write_text("")
        ux.write(self.root / "calibration.json", {
            "passed": True, "synthetic_test_only": True,
            "controls": ["valid-alternative", "lost-edit", "meaning-loss", "unprotected-erasure"]})
        self.runtime = {"model": "synthetic-test", "effort": "test", "cli_version": "test",
                        "browser_version": "test", "timezone": "America/Los_Angeles", "locale": "en-US",
                        "operator_id": "test-operator", "candidate_author_id": "test-skill-author",
                        "attempts": 1, "timeout_seconds": 240, "max_calls": 6,
                        "max_input_tokens": 100000, "max_output_tokens": 10000,
                        "viewports": ["1280x900", "390x844"],
                        "preflight": "preflight.json", "calibration": "calibration.json",
                        "observer_files": ["observer.py"],
                        "sources": {"released": {"commit": "a" * 40, "skills_sha256": "a" * 64},
                                    "candidate": {"commit": "b" * 40, "skills_sha256": "b" * 64}}}
        (self.root / "observer.py").write_text("# Synthetic evaluator test; no browser is exercised.\n")
        ux.write(self.root / "runtime.json", self.runtime)
        self.frozen, self.records = self.root / "frozen", self.root / "records"
        self.key, self.review_bundle = self.root / "key.json", self.root / "review"

    def freeze(self):
        ux.write(self.root / "runtime.json", self.runtime)
        ux.write(self.inputs / "cases.json", self.suite)
        return ux.freeze(self.inputs / "cases.json", self.root / "runtime.json", self.frozen)

    def capture(self, case, arm, attempt=1, phase="first-delivery", usage=True, feedback=False):
        sha = ux.digest(self.frozen / "freeze.json")
        artifact = self.root / "deliverable.html"
        if case == "exact-copy":
            fixture = self.frozen / ux.case_for(ux.read(self.frozen / "suite.json"), case)["fixture"]
            artifact.write_bytes(fixture.read_bytes().replace(b"Save drfat", b"Save draft"))
        else:
            artifact.write_text("<!doctype html><button>Save</button>")
        events = self.root / "events.jsonl"
        events.write_text(json.dumps({"type": "turn.completed", "usage": {
            "input_tokens": 100, "cached_input_tokens": 20, "output_tokens": 10}}) + "\n" if usage else "")
        fixture = ux.case_for(ux.read(self.frozen / "suite.json"), case)["fixture"]
        receipt = {"freeze_sha256": sha, "model": self.runtime["model"], "effort": self.runtime["effort"],
                   "case": case, "condition": arm, "attempt": attempt, "phase": phase,
                   "exit_code": 0, "timed_out": False, "cleanup_complete": True,
                   "user_feedback_received": feedback,
                   "runtime_sha256": ux.digest(self.frozen / "runtime.json"),
                   "fixture_sha256": ux.digest(self.frozen / fixture),
                   "skills_sha256": None if arm == "control" else self.runtime["sources"][arm]["skills_sha256"]}
        ux.write(self.root / "receipt.json", receipt)
        return ux.capture(self.frozen, self.records, case, arm, attempt, phase,
                          artifact, events, self.root / "receipt.json", stderr=self.root / "stderr.txt")

    def matrix(self, phase="first-delivery"):
        for case in self.suite["cases"]:
            for arm in ux.CONDITIONS:
                for attempt in range(1, self.runtime["attempts"] + 1):
                    self.capture(case["id"], arm, attempt, phase)

    def review(self, failures=(), unknown=(), phase="first-delivery", reviewer="test-independent-reviewer"):
        ux.bundle(self.frozen, self.records, self.review_bundle, self.key, phase)
        key = ux.read(self.key)
        review = {"reviewer_id": reviewer, "blind_attested": True,
                  "key_sha256": ux.digest(self.key), "samples": {}}
        for label, identity in key["trials"].items():
            case = ux.case_for(self.suite, identity["case"])
            item = ux.read(self.review_bundle / label / "review-template.json")
            for unit in item["units"]:
                criterion = next(u for u in case["criteria"] if u["id"] == unit["id"])
                trial = (identity["condition"], unit["id"])
                unit["outcome"] = "unknown" if trial in unknown else "fail" if trial in failures else "pass"
                unit["finding"] = "Synthetic calibration observation, not a model finding."
                evidence = []
                for view in (["all"] if criterion["evidence_kind"] == "bytes" else self.runtime["viewports"]):
                    name = unit["id"] + "-" + view + ".json"
                    ux.write(self.review_bundle / label / name, {"synthetic_test_only": True,
                                                              "observation": unit["outcome"]})
                    evidence.append({"kind": criterion["evidence_kind"], "viewport": view, "file": name})
                unit["evidence"] = evidence
            review["samples"][label] = item
        ux.write(self.review_bundle / "review.json", review)
        return review

    def result(self):
        return ux.assess(self.frozen, self.records, self.review_bundle, self.key)

    def test_bundled_cases_are_development_not_transfer_proof(self):
        suite = ux.load_suite(ux.DEFAULT_SUITE)
        self.assertEqual(suite["stage"], "development")
        self.assertTrue(suite["task_author"]["candidate_aware"])
        self.assertTrue(all(c["split"] == "development" for c in suite["cases"]))

    def test_ceiling_tie_cannot_establish_improvement(self):
        self.freeze(); self.matrix(); self.review()
        result = self.result()
        self.assertEqual(result["finding"], "SATURATED")
        self.assertFalse(result["confirmation_signal"])
        self.assertFalse(result["release_authorized"])
        self.assertEqual(result["observed_usage"]["candidate"]["input_tokens"], 200)
        self.assertEqual(result["observed_usage"]["candidate"]["cached_input_tokens"], 40)

    def test_actual_correction_reduction_is_descriptive_in_development(self):
        self.freeze(); self.matrix()
        self.review(failures=[("released", "complete-editor")])
        result = self.result()
        self.assertEqual(result["finding"], "IMPROVEMENT_SIGNAL")
        self.assertEqual(result["totals"]["released"]["target_corrections"], 1)
        self.assertFalse(result["confirmation_signal"])

    def test_meaning_loss_or_erasure_scope_vetoes_apparent_win(self):
        for bad in ("cancel-and-validation",):
            with self.subTest(bad=bad):
                self.freeze(); self.matrix()
                self.review(failures=[("released", "complete-editor"), ("candidate", bad)])
                self.assertEqual(self.result()["finding"], "REGRESSION")
                shutil.rmtree(self.frozen); shutil.rmtree(self.records); shutil.rmtree(self.review_bundle)
                self.key.unlink()

    def test_lost_edit_is_a_critical_failure_even_when_other_target_improves(self):
        self.freeze(); self.matrix()
        self.review(failures=[("released", "complete-editor"), ("released", "task-priority"),
                             ("candidate", "independent-addition")])
        self.assertEqual(self.result()["finding"], "REGRESSION")

    def test_unknown_outcomes_are_incomplete_not_pass(self):
        self.freeze(); self.matrix(); self.review(unknown=[("candidate", "complete-editor")])
        self.assertEqual(self.result()["finding"], "INCOMPLETE")

    def test_missing_usage_is_retained_unknown_and_prevents_bundle(self):
        self.freeze(); self.matrix()
        trial = self.records / "shift-plan/candidate/1/first-delivery"
        shutil.rmtree(trial)
        value = self.capture("shift-plan", "candidate", usage=False)
        self.assertFalse(value["complete"])
        self.assertIsNone(value["usage"])
        with self.assertRaisesRegex(ux.UXError, "unknown usage"):
            ux.bundle(self.frozen, self.records, self.review_bundle, self.key)

    def test_overwrites_and_post_feedback_first_delivery_rejected(self):
        self.freeze(); self.capture("shift-plan", "candidate")
        with self.assertRaises(FileExistsError):
            self.capture("shift-plan", "candidate")
        with self.assertRaisesRegex(ux.UXError, "precede user feedback"):
            self.capture("shift-plan", "released", feedback=True)

    def test_repair_does_not_replace_original_and_needs_predecessor(self):
        self.runtime.update(repair_rounds=2, max_calls=18)
        self.freeze()
        with self.assertRaisesRegex(ux.UXError, "first delivery"):
            self.capture("shift-plan", "candidate", phase="repair-1")
        self.matrix()
        original = ux.digest(self.records / "shift-plan/candidate/1/first-delivery/capture.json")
        self.matrix("repair-1")
        self.assertEqual(original, ux.digest(self.records / "shift-plan/candidate/1/first-delivery/capture.json"))
        self.review(failures=[("candidate", "complete-editor")])
        self.assertEqual(self.result()["finding"], "REGRESSION")

    def test_unbudgeted_feedback_cannot_admit_repair(self):
        self.freeze(); self.capture("shift-plan", "candidate")
        with self.assertRaisesRegex(ux.UXError, "frozen call budget"):
            self.capture("shift-plan", "candidate", phase="repair-1")

    def test_partially_missing_usage_is_unknown_not_assumed_zero(self):
        self.freeze(); self.capture("shift-plan", "candidate")
        trial = self.records / "shift-plan/candidate/1/first-delivery"
        shutil.rmtree(trial)
        event = {"type": "turn.completed", "usage": {"input_tokens": 100, "output_tokens": 10}}
        (self.root / "events.jsonl").write_text(json.dumps(event) + "\n")
        value = ux.capture(self.frozen, self.records, "shift-plan", "candidate", 1, "first-delivery",
                           self.root / "deliverable.html", self.root / "events.jsonl", self.root / "receipt.json",
                           stderr=self.root / "stderr.txt")
        self.assertIsNone(value["usage"])
        self.assertFalse(value["complete"])

    def test_anonymized_bundle_excludes_arm_sources_prose_and_traces(self):
        self.freeze(); self.matrix(); self.review()
        files = [p.name for p in self.review_bundle.rglob("*") if p.is_file()]
        self.assertNotIn("events.jsonl", files)
        self.assertNotIn("producer-receipt.json", files)
        self.assertNotIn("runtime.json", files)
        self.assertNotIn("key.json", files)
        self.assertTrue((self.review_bundle / "sample-001/checks.md").is_file())

    def test_blind_reviewer_receives_complete_common_original_source_facts(self):
        self.freeze(); self.matrix(); self.review()
        for label, identity in ux.read(self.key)["trials"].items():
            case = ux.case_for(ux.read(self.frozen / "suite.json"), identity["case"])
            original = self.review_bundle / label / "original.html"
            self.assertEqual(original.read_bytes(), (self.frozen / case["fixture"]).read_bytes())
            self.assertNotEqual(original.read_bytes(), (self.review_bundle / label / "index.html").read_bytes())

    def test_original_source_fact_tampering_invalidates_blind_review(self):
        self.freeze(); self.matrix(); self.review()
        original = self.review_bundle / "sample-001/original.html"
        original.write_text(original.read_text() + "Changed immutable source facts")
        with self.assertRaisesRegex(ux.UXError, "review input drift"):
            self.result()

    def test_key_cannot_be_inside_reviewer_bundle(self):
        self.freeze(); self.matrix()
        with self.assertRaisesRegex(ux.UXError, "outside"):
            ux.bundle(self.frozen, self.records, self.review_bundle, self.review_bundle / "key.json")

    def test_freeze_rejects_post_admission_observer_or_input_changes(self):
        self.freeze()
        checks = self.frozen / "inputs/shift-plan/checks.md"
        checks.write_text(checks.read_text() + "Changed rule")
        with self.assertRaisesRegex(ux.UXError, "drift"):
            self.capture("shift-plan", "candidate")

    def test_running_evaluator_must_match_the_frozen_code(self):
        self.freeze()
        changed = self.root / "changed-evaluator.py"
        changed.write_text(Path(ux.__file__).read_text() + "\n# Changed judging rule\n")
        with mock.patch.object(ux, "__file__", str(changed)):
            with self.assertRaisesRegex(ux.UXError, "running evaluator differs"):
                ux.check_freeze(self.frozen)

    def test_nested_freeze_named_dependency_cannot_change_undetected(self):
        (self.root / "helpers").mkdir()
        ux.write(self.root / "helpers/freeze.json", {"required": "original"})
        self.runtime["observer_files"].append("helpers/freeze.json")
        self.freeze()
        dependency = self.frozen / "observers/helpers/freeze.json"
        self.assertIn("observers/helpers/freeze.json", ux.read(self.frozen / "freeze.json")["files"])
        ux.write(dependency, {"required": "changed"})
        with self.assertRaisesRegex(ux.UXError, "drift"):
            ux.check_freeze(self.frozen)

    def test_two_desktop_or_two_phone_widths_cannot_supply_responsive_evidence(self):
        for views in (["1280x900", "1280x901"], ["360x800", "390x844"]):
            with self.subTest(views=views):
                self.runtime["viewports"] = views
                with self.assertRaisesRegex(ux.UXError, "phone width"):
                    self.freeze()

    def test_zero_input_usage_is_incomplete_like_the_native_budget(self):
        self.freeze(); self.capture("shift-plan", "candidate")
        shutil.rmtree(self.records)
        (self.root / "events.jsonl").write_text(json.dumps({"type": "turn.completed", "usage": {
            "input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 10}}) + "\n")
        value = ux.capture(self.frozen, self.records, "shift-plan", "candidate", 1, "first-delivery",
                           self.root / "deliverable.html", self.root / "events.jsonl", self.root / "receipt.json",
                           stderr=self.root / "stderr.txt")
        self.assertFalse(value["complete"])
        self.assertIsNone(value["usage"])

    def test_over_budget_attempt_is_preserved_but_cannot_enter_review(self):
        self.runtime["max_input_tokens"] = 99
        self.freeze()
        value = self.capture("shift-plan", "candidate")
        self.assertFalse(value["complete"])
        self.assertFalse(value["within_frozen_budget"])
        self.assertEqual(value["usage"]["input_tokens"], 100)
        self.assertTrue((self.records / "shift-plan/candidate/1/first-delivery/events.jsonl").is_file())
        with self.assertRaisesRegex(ux.UXError, "incomplete"):
            ux.bundle(self.frozen, self.records, self.review_bundle, self.key)
        with self.assertRaisesRegex(ux.UXError, "incomplete"):
            self.capture("shift-plan", "released")

    def test_full_matrix_usage_cannot_bypass_budget_at_assessment(self):
        self.freeze(); self.matrix(); self.review(failures=[("released", "complete-editor")])
        with mock.patch.object(ux, "check_freeze", return_value=(
                self.suite, dict(self.runtime, max_input_tokens=1, max_output_tokens=1),
                ux.digest(self.frozen / "freeze.json"))):
            with self.assertRaisesRegex(ux.UXError, "exceed frozen"):
                self.result()

    def test_repairs_share_the_frozen_usage_budget_with_first_delivery(self):
        self.runtime.update(repair_rounds=1, max_calls=12, max_input_tokens=699)
        self.freeze(); self.matrix()
        value = self.capture("shift-plan", "candidate", phase="repair-1")
        self.assertFalse(value["complete"])
        self.assertEqual(value["usage"]["input_tokens"], 100)

    def test_frozen_observer_preserves_relative_dependency_layout(self):
        (self.root / "helpers").mkdir()
        (self.root / "helpers/control.py").write_text("EXPECTED = 'retained'\n")
        self.runtime["observer_files"].append("helpers/control.py")
        self.freeze()
        self.assertEqual((self.frozen / "observers/helpers/control.py").read_text(), "EXPECTED = 'retained'\n")
        self.assertTrue((self.frozen / "observers/observer.py").is_file())

    def test_review_input_or_capture_tampering_rejected(self):
        self.freeze(); self.matrix(); self.review()
        path = self.records / "shift-plan/candidate/1/first-delivery/index.html"
        path.write_text("different artifact")
        with self.assertRaisesRegex(ux.UXError, "drift"):
            self.result()

    def test_missing_or_duplicate_unit_cannot_inflate_sample_count(self):
        self.freeze(); self.matrix(); review = self.review()
        sample = next(v for v in review["samples"].values() if len(v["units"]) > 1)
        sample["units"][1] = copy.deepcopy(sample["units"][0])
        ux.write(self.review_bundle / "review.json", review)
        with self.assertRaisesRegex(ux.UXError, "coverage"):
            self.result()

    def test_render_screenshot_cannot_prove_storage_persistence(self):
        self.freeze(); self.matrix(); review = self.review()
        sample = next(v for v in review["samples"].values() if len(v["units"]) > 1)
        unit = next(u for u in sample["units"] if u["id"] == "independent-addition")
        unit["evidence"][0]["kind"] = "render"
        ux.write(self.review_bundle / "review.json", review)
        with self.assertRaisesRegex(ux.UXError, "evidence kind"):
            self.result()

    def test_single_width_cannot_supply_two_width_pass(self):
        self.freeze(); self.matrix(); review = self.review()
        sample = next(v for v in review["samples"].values() if len(v["units"]) > 1)
        sample["units"][0]["evidence"].pop()
        ux.write(self.review_bundle / "review.json", review)
        with self.assertRaisesRegex(ux.UXError, "each frozen viewport"):
            self.result()

    def test_builder_or_reviewer_scope_claim_cannot_override_bytes(self):
        self.freeze(); self.matrix(); review = self.review()
        item = next(v for v in review["samples"].values() if len(v["units"]) == 1)
        item["units"][0]["outcome"] = "fail"
        ux.write(self.review_bundle / "review.json", review)
        with self.assertRaisesRegex(ux.UXError, "scope oracle"):
            self.result()

    def test_missing_attempt_cannot_be_selected_away(self):
        self.freeze(); self.matrix()
        shutil.rmtree(self.records / "shift-plan/released/1/first-delivery")
        with self.assertRaisesRegex(ux.UXError, "matrix incomplete"):
            ux.bundle(self.frozen, self.records, self.review_bundle, self.key)

    def test_counterbalanced_schedule_and_three_attempt_confirmation(self):
        self.suite["stage"] = "confirmation"
        self.suite["task_author"] = {"id": "test-external-author", "candidate_aware": False,
                                      "evidence": "author.md"}
        (self.inputs / "author.md").write_text("Synthetic test identity only; no actual independence claim.")
        self.suite["cases"][0]["split"] = "holdout"
        self.runtime.update(attempts=3, max_calls=18)
        self.freeze(); self.matrix()
        schedule = ux.read(self.frozen / "schedule.json")
        first = [v["condition"] for v in schedule if v["case"] == "shift-plan"]
        self.assertEqual(first, ["control", "released", "candidate", "released", "candidate", "control",
                                 "candidate", "control", "released"])
        self.review(failures=[("released", "complete-editor")])
        result = self.result()
        self.assertTrue(result["confirmation_signal"])
        self.assertEqual(result["totals"]["released"]["target_corrections"], 3)
        self.assertFalse(result["release_authorized"])

    def test_candidate_aware_confirmation_or_no_fresh_target_holdout_rejected(self):
        self.suite["stage"] = "confirmation"
        ux.write(self.inputs / "cases.json", self.suite)
        with self.assertRaisesRegex(ux.UXError, "candidate-blind"):
            ux.load_suite(self.inputs / "cases.json")

    def test_operator_review_does_not_become_independent_confirmation(self):
        self.freeze(); self.matrix()
        self.review(failures=[("released", "complete-editor")], reviewer="test-operator")
        self.assertFalse(self.result()["independence_attested"])

    def test_declared_calibration_must_include_supported_alternative(self):
        ux.write(self.root / "calibration.json", {"passed": True, "controls": ["lost-edit"]})
        with self.assertRaisesRegex(ux.UXError, "alternatives"):
            self.freeze()

    def test_browser_only_preflight_cannot_admit_builders(self):
        ux.write(self.root / "preflight.json", {"passed": True, "browser_operations": ["open", "save", "reload"]})
        with self.assertRaisesRegex(ux.UXError, "source-read and artifact-edit"):
            self.freeze()
        self.assertFalse(self.frozen.exists())

    def test_preflight_must_retain_real_nonempty_edit_and_source_readback(self):
        for name, body, message in (("after", "<!-- unread marker -->Before", "exact nonempty"),
                                    ("expected", "<!-- unread marker -->Before", "exact nonempty"),
                                    ("source_readback", "Guessed from rendered text", "readback")):
            with self.subTest(name=name):
                path = self.root / "probe" / name
                original = path.read_text(); path.write_text(body)
                with self.assertRaisesRegex(ux.UXError, message):
                    self.freeze()
                path.write_text(original)

    def test_failed_edit_tool_or_missing_usage_blocks_preflight(self):
        events = self.root / "probe/events"
        original = events.read_text()
        for body, message in ((original.replace('"completed", "changes"', '"failed", "changes"'), "native edit tool"),
                              (original.splitlines()[0] + "\n", "usage missing")):
            with self.subTest(message=message):
                events.write_text(body)
                with self.assertRaisesRegex(ux.UXError, message):
                    self.freeze()
        events.write_text(original)

    def test_preflight_dependencies_are_retained_and_hashed(self):
        self.freeze()
        receipt = ux.read(self.frozen / "preflight.json")
        for name in ux.PROBE_FILES:
            path = self.frozen / receipt["builder_probe"][name]
            self.assertEqual(path.read_bytes(), (self.root / "probe" / name).read_bytes())
            self.assertIn(path.relative_to(self.frozen).as_posix(), ux.read(self.frozen / "freeze.json")["files"])
        path.write_text("Changed producer evidence")
        with self.assertRaisesRegex(ux.UXError, "drift"):
            ux.check_freeze(self.frozen)

    def failed_write_capture(self, *, recovered=False, native_denial=True):
        self.freeze(); self.capture("shift-plan", "candidate")
        shutil.rmtree(self.records)
        artifact = self.root / "deliverable.html"
        fixture = self.frozen / ux.case_for(ux.read(self.frozen / "suite.json"), "shift-plan")["fixture"]
        artifact.write_bytes(fixture.read_bytes() + (b"<!-- recovered edit -->" if recovered else b""))
        events = self.root / "events.jsonl"
        usage = events.read_text()
        events.write_text(json.dumps({"type": "item.completed", "item": {
            "type": "file_change", "status": "failed", "changes": [{"kind": "update", "path": str(artifact)}]}})
            + "\n" + usage)
        (self.root / "stderr.txt").write_text(f"Failed to write file {artifact}\n" if native_denial
                                              else "Failed to find expected lines in patch\n")
        return ux.capture(self.frozen, self.records, "shift-plan", "candidate", 1, "first-delivery",
                          artifact, events, self.root / "receipt.json", stderr=self.root / "stderr.txt")

    def test_successful_turn_with_denied_unchanged_artifact_is_incomplete(self):
        value = self.failed_write_capture()
        self.assertFalse(value["complete"])
        self.assertTrue(value["unresolved_artifact_write_failure"])
        self.assertEqual(value["usage"]["input_tokens"], 100)
        self.assertEqual((self.records / "shift-plan/candidate/1/first-delivery/stderr.txt").read_text(),
                         (self.root / "stderr.txt").read_text())
        with self.assertRaisesRegex(ux.UXError, "incomplete"):
            ux.bundle(self.frozen, self.records, self.review_bundle, self.key)
        with self.assertRaisesRegex(ux.UXError, "incomplete"):
            self.capture("shift-plan", "released")

    def test_recovered_edit_is_not_rejected_for_an_earlier_denial(self):
        value = self.failed_write_capture(recovered=True)
        self.assertTrue(value["complete"])
        self.assertFalse(value["unresolved_artifact_write_failure"])

    def test_ordinary_patch_miss_is_not_a_runtime_denial(self):
        self.assertTrue(self.failed_write_capture(native_denial=False)["complete"])

    def failed_repair_capture(self, phase, *, recovered=False):
        self.runtime.update(repair_rounds=2, max_calls=18)
        self.freeze(); self.capture("shift-plan", "candidate")
        if phase == "repair-2":
            self.capture("shift-plan", "candidate", phase="repair-1", feedback=True)
        artifact = self.root / "deliverable.html"
        if recovered:
            artifact.write_bytes(artifact.read_bytes() + b"<!-- successful repair -->")
        events = self.root / "events.jsonl"
        events.write_text(json.dumps({"type": "item.completed", "item": {
            "type": "file_change", "status": "failed", "changes": [{"kind": "update", "path": str(artifact)}]}})
            + "\n" + events.read_text())
        (self.root / "stderr.txt").write_text(f"Failed to write file {artifact}\n")
        receipt = ux.read(self.root / "receipt.json")
        receipt.update(phase=phase, user_feedback_received=True)
        ux.write(self.root / "receipt.json", receipt)
        return ux.capture(self.frozen, self.records, "shift-plan", "candidate", 1, phase,
                          artifact, events, self.root / "receipt.json", stderr=self.root / "stderr.txt")

    def test_denied_first_repair_of_changed_delivery_is_incomplete(self):
        value = self.failed_repair_capture("repair-1")
        self.assertFalse(value["complete"])
        self.assertTrue(value["unresolved_artifact_write_failure"])
        self.assertEqual(value["usage"]["input_tokens"], 100)
        with self.assertRaisesRegex(ux.UXError, "incomplete"):
            self.capture("shift-plan", "released")

    def test_denied_second_repair_of_changed_delivery_is_incomplete(self):
        value = self.failed_repair_capture("repair-2")
        self.assertFalse(value["complete"])
        self.assertTrue(value["unresolved_artifact_write_failure"])

    def test_recovered_repair_is_not_rejected_for_earlier_denial(self):
        value = self.failed_repair_capture("repair-1", recovered=True)
        self.assertTrue(value["complete"])
        self.assertFalse(value["unresolved_artifact_write_failure"])

    def test_different_commit_with_identical_skills_is_not_a_candidate(self):
        self.runtime["sources"]["candidate"]["skills_sha256"] = "a" * 64
        with self.assertRaisesRegex(ux.UXError, "skill content"):
            self.freeze()

    def test_symlink_fixture_cannot_read_external_data(self):
        fixture = self.inputs / self.suite["cases"][0]["fixture"]
        fixture.unlink(); fixture.symlink_to(self.root / "runtime.json")
        with self.assertRaisesRegex(ux.UXError, "symlink"):
            ux.load_suite(self.inputs / "cases.json")


if __name__ == "__main__":
    unittest.main()
