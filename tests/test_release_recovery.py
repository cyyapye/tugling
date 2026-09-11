from __future__ import annotations

import copy
import json
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlsplit

from scripts import record_release_recovery as recovery


class ReleaseRecoveryTest(unittest.TestCase):
    """Exercise provider transitions; signatures and public installs are separate live proof."""

    def setUp(self):
        self.candidate = "b" * 40
        self.review = {"state": "READY_FOR_REVIEWED_PROMOTION", "controller_sha": "a" * 40,
            "certification_controller_sha": "a" * 40, "candidate_sha": self.candidate,
            "version": "0.5.0", "certificate_sha256": "c" * 64, "certification_run_id": "123",
            "certification_run_attempt": 1}
        self.run = {"id": 456, "run_attempt": 1, "event": "workflow_dispatch", "status": "completed",
            "conclusion": "failure", "path": ".github/workflows/promote-stable.yml",
            "repository": {"full_name": "cyyapye/tugling"}, "head_repository": {"full_name": "cyyapye/tugling"},
            "head_branch": "controller-test", "head_sha": "a" * 40}
        self.jobs = {"total_count": 2, "jobs": [
            {"id": 11, "name": "preflight", "status": "completed", "conclusion": "success"},
            {"id": 12, "name": "verify-candidate", "status": "completed", "conclusion": "success"}]}
        self.request = {"controller": "a" * 40, "certification_controller": "a" * 40,
            "candidate": self.candidate, "version": "0.5.0", "certificate_digest": "c" * 64, "run_id": "123"}
        self.proof = {"state": "RECOVERY_VERIFIED", "request": self.request,
            "source_promotion_run_id": "456", "original_ci_conclusion": "failure",
            "execution_environment": "local-operator-verification"}
        self.deployments, self.statuses, self.writes = [], [], []
        self.refs = f"{self.candidate}\trefs/heads/stable\n{'d' * 40}\trefs/tags/v0.5.0\n{self.candidate}\trefs/tags/v0.5.0^{{}}"

    def api(self, path):
        if path == "actions/runs/456":
            return copy.deepcopy(self.run)
        if path == "actions/runs/456/jobs?per_page=100":
            return copy.deepcopy(self.jobs)
        if path.startswith("deployments?"):
            query = parse_qs(urlsplit(path).query)
            self.assertEqual(query["sha"], [self.candidate])
            self.assertEqual(query["environment"], ["tugling-stable"])
            self.assertEqual(query["task"], ["tugling:recovery"])
            return copy.deepcopy(self.deployments)
        if path == "deployments/99/statuses?per_page=100":
            return copy.deepcopy(self.statuses)
        raise AssertionError(path)

    def post(self, path, payload):
        self.writes.append((path, copy.deepcopy(payload)))
        if path == "deployments":
            value = {**payload, "id": 99, "sha": self.candidate}
            self.deployments.append(value)
            return value
        if path == "deployments/99/statuses":
            self.statuses.insert(0, payload)
            return payload
        raise AssertionError(path)

    def intent(self, lines=None):
        log = "2026-09-10T04:19:02Z " + json.dumps(self.review) if lines is None else lines
        with mock.patch.object(recovery.evidence, "api", side_effect=self.api), \
             mock.patch.object(recovery.evidence, "gh", return_value=log.encode()):
            return recovery.recovery_intent("456")

    def record(self):
        with mock.patch.object(recovery.evidence, "api", side_effect=self.api), \
             mock.patch.object(recovery, "post", side_effect=self.post), \
             mock.patch.object(recovery.controller, "text_git", return_value=self.refs):
            return recovery.record_recovery(self.proof)

    def test_intent_comes_from_the_original_successful_preflight(self):
        request, run = self.intent()
        self.assertEqual(request, self.request)
        self.assertEqual(run["conclusion"], "failure")

    def test_wrong_source_fork_controller_or_rerun_is_rejected(self):
        for changes in ({"run_attempt": 2}, {"conclusion": "success"}, {"head_branch": "main"},
                        {"path": ".github/workflows/other.yml"}, {"head_sha": "e" * 40},
                        {"head_repository": {"full_name": "someone/fork"}}):
            original = self.run
            self.run = {**original, **changes}
            with self.subTest(changes=changes), self.assertRaises(recovery.evidence.EvidenceError):
                self.intent()
            self.run = original

    def test_missing_or_ambiguous_release_identity_is_rejected(self):
        line = "2026-09-10T04:19:02Z " + json.dumps(self.review)
        for log in ("no identity", line + "\n" + line):
            with self.subTest(log=log), self.assertRaisesRegex(recovery.evidence.EvidenceError, "unambiguous"):
                self.intent(log)
        self.jobs["jobs"][1]["conclusion"] = "failure"
        with self.assertRaisesRegex(recovery.evidence.EvidenceError, "candidate checks"):
            self.intent()

    def test_unpublished_release_cannot_be_recorded_or_written(self):
        with mock.patch.object(recovery, "recovery_intent", return_value=(self.request, self.run)), \
             mock.patch.object(recovery.promotion.protection, "require_protections", return_value={}), \
             mock.patch.object(recovery.promotion.protection, "require_approval"), \
             mock.patch.object(recovery.evidence, "fetch_verified", return_value=(mock.Mock(), {})), \
             mock.patch.object(recovery.promotion.certification, "require_successful_verify"), \
             mock.patch.object(recovery.controller, "promote",
                 return_value={"state": "READY_FOR_REVIEWED_PROMOTION"}) as transaction, \
             mock.patch.object(recovery.promotion, "canary") as install:
            with self.assertRaisesRegex(recovery.evidence.EvidenceError, "already published"):
                recovery.verify_recovery("456")
            self.assertIs(transaction.call_args.kwargs["apply"], False)
            self.assertNotIn("token", transaction.call_args.kwargs)
            install.assert_not_called()

    def test_records_a_separate_recovery_and_duplicate_attempt_converges(self):
        self.assertEqual(self.record()["state"], "RECOVERY_RECORDED")
        self.assertEqual(len(self.writes), 2)
        self.assertEqual(self.writes[0][0], "deployments")
        self.assertEqual(self.writes[0][1]["ref"], self.candidate)
        self.assertFalse(self.writes[1][1]["auto_inactive"])
        self.assertIn("original CI attempt remains failed", self.writes[1][1]["description"])
        self.assertEqual(self.record()["state"], "RECOVERY_ALREADY_RECORDED")
        self.assertEqual(len(self.writes), 2)

    def test_lost_create_response_is_recovered_without_a_duplicate_record(self):
        original = self.post

        def lost(path, payload):
            original(path, payload)
            raise recovery.evidence.EvidenceError("response lost")

        with mock.patch.object(self, "post", side_effect=lost), \
             self.assertRaisesRegex(recovery.evidence.EvidenceError, "response lost"):
            self.record()
        self.assertEqual(len(self.deployments), 1)
        self.assertEqual(self.record()["state"], "RECOVERY_RECORDED")
        self.assertEqual([path for path, _ in self.writes], ["deployments", "deployments/99/statuses"])

    def test_moved_stable_or_duplicate_metadata_cannot_claim_success(self):
        self.refs = self.refs.replace(f"{self.candidate}\trefs/heads/stable", f"{'e' * 40}\trefs/heads/stable")
        with self.assertRaises(recovery.promotion.controller.ControllerError):
            self.record()
        self.assertEqual(self.writes, [])
        self.deployments = [{"payload": {"source_promotion_run_id": "456"}}] * 2
        with self.assertRaisesRegex(recovery.evidence.EvidenceError, "duplicate recovery"):
            self.record()
        self.assertEqual(self.writes, [])


if __name__ == "__main__":
    unittest.main()
