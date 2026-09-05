from __future__ import annotations

import copy
import json
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import zipfile

from scripts import release_evidence as evidence
from scripts import release_protection as protection
from scripts import promote_release as promotion


class ReleaseEvidenceTest(unittest.TestCase):
    """Stub the remote provider boundary; never claim synthetic signatures are real."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="tugling-provenance-test-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.pin, self.candidate, self.baseline = "a" * 40, "b" * 40, "c" * 40
        self.run_id = "123"
        self.run = {"id": 123, "run_attempt": 1, "event": "workflow_dispatch",
            "path": ".github/workflows/certify-release.yml", "head_sha": self.pin,
            "head_branch": "controller-test", "status": "completed", "conclusion": "success",
            "repository": {"full_name": "cyyapye/tugling"},
            "head_repository": {"full_name": "cyyapye/tugling"}}
        self.artifact = {"id": 456, "name": f"certification-{self.candidate}-123-1", "expired": False,
                         "size_in_bytes": 10000, "workflow_run": {"id": 123, "head_sha": self.pin}}
        cert = evidence.certification
        self.certificate = cert.gate.read_json(cert.ROOT / "evals/releases/v0.4.0/certificate.json")
        self.certificate["behavioral"].update(evaluated_revision=self.candidate, released_revision=self.baseline)
        self.certificate["clean_room"].update(revision=self.candidate, codex_version=f"codex-cli {cert.CODEX_VERSION}")
        for section in ("behavioral", "clean_room"):
            self.certificate[section].update(model=cert.MODEL, reasoning_effort=cert.EFFORT)
        self.envelope = {"schema_version": 1, "state": "CERTIFIED", "repository": "cyyapye/tugling",
            "controller_sha": self.pin, "candidate_sha": self.candidate, "baseline_sha": self.baseline,
            "run_id": "123", "run_attempt": 1, "input_limit": 1000, "output_limit": 1000,
            "created_at": "2026-09-05T00:00:00Z", "model": cert.MODEL,
            "reasoning_effort": cert.EFFORT, "codex_version": f"codex-cli {cert.CODEX_VERSION}",
            "usage": {"completed_tasks": 91, "task_limit": 91, "input_limit": 1000, "output_limit": 1000,
                "input_tokens": 100, "output_tokens": 50, "cached_input_tokens": 25,
                "in_flight_or_unaccounted_task": False, "accounting": "between-tasks-not-hard-billing-cap"}}
        self.source = self.root / "source"
        self.source.mkdir()
        cert.gate.write_json(self.source / "certificate.json", self.certificate)
        self.digest = cert.gate.file_digest(self.source / "certificate.json")
        self.envelope["certificate_sha256"] = self.digest
        self.verified = [{"verificationResult": {"statement": {"predicate": {"runDetails": {
            "metadata": {"invocationId": "https://github.com/cyyapye/tugling/actions/runs/123/attempts/1"}}}}}}]
        self.commands = []

    def api(self, path):
        if path == "actions/runs/123":
            return copy.deepcopy(self.run)
        if path == "actions/runs/123/artifacts?per_page=100":
            return {"total_count": 1, "artifacts": [copy.deepcopy(self.artifact)]}
        raise AssertionError(path)

    def gh(self, *args, output=None):
        self.commands.append(args)
        if output is not None:
            with zipfile.ZipFile(output, "w") as bundle:
                bundle.write(self.source / "certificate.json", "certificate.json")
                bundle.writestr("certification.json", json.dumps(self.envelope))
            return b""
        return json.dumps(self.verified).encode()

    def fetch(self, **changes):
        scratch = self.root / "download"
        scratch.mkdir(exist_ok=True)
        with mock.patch.object(evidence, "api", side_effect=self.api), \
             mock.patch.object(evidence, "gh", side_effect=self.gh):
            return evidence.fetch_verified(run_id="123", pin=self.pin, candidate=self.candidate,
                                           digest=changes.get("digest", self.digest), scratch=scratch)

    def test_two_verified_files_bind_exact_candidate_run_and_reviewed_digest(self):
        path, envelope = self.fetch()
        self.assertEqual(path.read_bytes(), (self.source / "certificate.json").read_bytes())
        self.assertEqual(envelope["candidate_sha"], self.candidate)
        verifications = [args for args in self.commands if args[:2] == ("attestation", "verify")]
        self.assertEqual(len(verifications), 2)
        for args in verifications:
            for flag, expected in (("--repo", "cyyapye/tugling"),
                    ("--signer-workflow", "cyyapye/tugling/.github/workflows/certify-release.yml"),
                    ("--signer-digest", self.pin), ("--source-digest", self.pin),
                    ("--source-ref", "refs/tags/controller-test")):
                self.assertEqual(args[args.index(flag) + 1], expected)
            self.assertIn("--deny-self-hosted-runners", args)
        self.assertEqual({path.name for path in path.parent.iterdir()}, {"certificate.json", "certification.json"})

    def test_wrong_workflow_fork_controller_event_attempt_or_incomplete_run_is_rejected(self):
        changes = [("path", ".github/workflows/other.yml"), ("head_sha", "d" * 40),
                   ("head_branch", "main"), ("event", "pull_request"), ("run_attempt", 2),
                   ("conclusion", "failure"), ("status", "in_progress"),
                   ("head_repository", {"full_name": "someone/fork"}), ("id", 124)]
        for key, value in changes:
            with self.subTest(key=key), self.assertRaises(evidence.EvidenceError):
                evidence.require_run({**self.run, key: value}, "123", self.pin)

    def test_expired_or_substituted_artifact_is_rejected_before_download(self):
        for changes in ({"expired": True}, {"size_in_bytes": evidence.MAX_ARCHIVE_BYTES + 1},
                        {"workflow_run": {"id": 124, "head_sha": self.pin}}, {"name": "other"}):
            with self.subTest(changes=changes):
                original = self.artifact
                self.artifact = {**original, **changes}
                with self.assertRaises(evidence.EvidenceError):
                    self.fetch()
                self.artifact = original
        self.assertEqual(self.commands, [])

    def test_failed_crypto_verification_stops_before_reading_json(self):
        (self.source / "certificate.json").write_text("deliberately not JSON")
        original = self.gh

        def reject(*args, output=None):
            if output is None:
                raise evidence.EvidenceError("synthetic verifier rejection")
            return original(*args, output=output)

        with mock.patch.object(self, "gh", side_effect=reject), \
             mock.patch.object(evidence.certification, "validate_artifact") as validate:
            with self.assertRaisesRegex(evidence.EvidenceError, "verifier rejection"):
                self.fetch()
            validate.assert_not_called()

    def test_attestation_from_another_run_or_attempt_is_not_accepted(self):
        self.verified[0]["verificationResult"]["statement"]["predicate"]["runDetails"]["metadata"][
            "invocationId"] = "https://github.com/cyyapye/tugling/actions/runs/123/attempts/2"
        with self.assertRaisesRegex(evidence.EvidenceError, "different certification run or attempt"):
            self.fetch()

    def test_reviewed_digest_cannot_be_substituted_by_signed_evidence(self):
        with self.assertRaisesRegex(evidence.EvidenceError, "maintainer-reviewed digest"):
            self.fetch(digest="f" * 64)

    def test_signed_envelope_for_another_candidate_is_rejected(self):
        self.envelope["candidate_sha"] = "d" * 40
        with self.assertRaises(evidence.certification.CertificationError):
            self.fetch()

    def test_rerun_started_during_download_invalidates_evidence(self):
        original = self.api
        calls = 0

        def rerun(path):
            nonlocal calls
            result = original(path)
            if path == "actions/runs/123":
                calls += 1
                if calls == 2:
                    result["run_attempt"] = 2
            return result

        with mock.patch.object(self, "api", side_effect=rerun):
            with self.assertRaisesRegex(evidence.EvidenceError, "first-attempt"):
                self.fetch()

    def test_archive_path_escape_symlink_extra_file_and_zip_bomb_are_rejected(self):
        for case in ("escape", "symlink", "extra", "oversize"):
            with self.subTest(case=case):
                archive = self.root / f"{case}.zip"
                with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
                    name = "../certificate.json" if case == "escape" else "certificate.json"
                    info = zipfile.ZipInfo(name)
                    if case == "symlink":
                        info.create_system = 3
                        info.external_attr = (stat.S_IFLNK | 0o777) << 16
                    bundle.writestr(info, "x" * (300 * 1024 if case == "oversize" else 1))
                    bundle.writestr("certification.json", "{}")
                    if case == "extra":
                        bundle.writestr("raw-model-output.json", "private")
                with self.assertRaises(evidence.EvidenceError):
                    evidence.unpack(archive, self.root / f"unpack-{case}")
                self.assertFalse((self.root / f"unpack-{case}").exists())


class ReleaseProtectionTest(unittest.TestCase):
    def setUp(self):
        policy = json.loads(protection.POLICY.read_text())
        self.rulesets = [{**item, "id": index} for index, item in enumerate(policy["rulesets"], 1)]
        self.environment = {"name": "tugling-stable", "id": 44, "can_admins_bypass": False,
            "deployment_branch_policy": {"protected_branches": False, "custom_branch_policies": True},
            "protection_rules": [{"type": "required_reviewers", "prevent_self_review": False,
                                  "reviewers": [{"type": "User", "reviewer": {"id": 4515813}}]}]}
        self.deployment = {"total_count": 1, "branch_policies": [{"name": "controller-*", "type": "tag"}]}
        self.reviews = [{"state": "approved", "user": {"id": 4515813}, "environments": [{"id": 44}]}]

    def api(self, path):
        if path == "":
            return {"visibility": "public"}
        if path == "rulesets?per_page=100":
            return self.rulesets
        if path.startswith("rulesets/"):
            return self.rulesets[int(path.split("/")[-1]) - 1]
        if path == "environments/tugling-stable":
            return self.environment
        if path.startswith("environments/tugling-stable/deployment-branch-policies"):
            return self.deployment
        if path == "actions/runs/123/approvals":
            return self.reviews
        raise AssertionError(path)

    def test_read_only_preflight_and_writer_both_check_configured_controls(self):
        with mock.patch.object(protection.evidence, "api", side_effect=self.api):
            protection.require_protections()
            protection.require_protections(writer=True)
            protection.require_approval("123", self.environment)

    def test_disabled_ruleset_exclusion_or_bypass_blocks_writer(self):
        for changes in ({"enforcement": "disabled"}, {"rules": [{"type": "deletion"}]},
                        {"conditions": {"ref_name": {"include": ["refs/heads/stable"], "exclude": ["~ALL"]}}},
                        {"bypass_actors": [{"actor_type": "Integration", "actor_id": 15368, "bypass_mode": "always"}]}):
            with self.subTest(changes=changes):
                original = self.rulesets[0]
                self.rulesets[0] = {**original, **changes}
                with mock.patch.object(protection.evidence, "api", side_effect=self.api), \
                     self.assertRaises(evidence.EvidenceError):
                    protection.require_protections(writer=True)
                self.rulesets[0] = original

    def test_reader_hidden_bypass_actors_must_be_verified_with_writer_permission(self):
        for item in self.rulesets:
            del item["bypass_actors"]
        with mock.patch.object(protection.evidence, "api", side_effect=self.api):
            protection.require_protections()
            with self.assertRaisesRegex(evidence.EvidenceError, "bypass actors"):
                protection.require_protections(writer=True)

    def test_approval_bypass_missing_reviewer_or_unprotected_dispatch_ref_is_rejected(self):
        for field, value in (("can_admins_bypass", True), ("protection_rules", []),
                             ("deployment_branch_policy", None)):
            with self.subTest(field=field):
                original = copy.deepcopy(self.environment)
                self.environment[field] = value
                with mock.patch.object(protection.evidence, "api", side_effect=self.api), \
                     self.assertRaises(evidence.EvidenceError):
                    protection.require_protections(writer=True)
                self.environment = original
        self.deployment["branch_policies"][0]["type"] = "branch"
        with mock.patch.object(protection.evidence, "api", side_effect=self.api), \
             self.assertRaises(evidence.EvidenceError):
            protection.require_protections(writer=True)

    def test_unapproved_wrong_reviewer_or_other_environment_cannot_publish(self):
        for reviews in ([], [{"state": "rejected", "user": {"id": 4515813}, "environments": [{"id": 44}]}],
                        [{"state": "approved", "user": {"id": 1}, "environments": [{"id": 44}]}],
                        [{"state": "approved", "user": {"id": 4515813}, "environments": [{"id": 45}]}]):
            self.reviews = reviews
            with mock.patch.object(protection.evidence, "api", side_effect=self.api), \
                 self.assertRaisesRegex(evidence.EvidenceError, "no maintainer approval"):
                protection.require_approval("123", self.environment)

    def test_writer_reverifies_evidence_and_never_trusts_preflight_outputs(self):
        request = {"controller": "a" * 40, "certification_controller": "a" * 40,
                   "candidate": "b" * 40, "version": "0.5.0", "certificate_digest": "c" * 64, "run_id": "123"}
        with mock.patch.object(promotion.protection, "require_protections", return_value=self.environment), \
             mock.patch.object(promotion.protection, "require_approval") as approval, \
             mock.patch.object(promotion.evidence, "fetch_verified", side_effect=evidence.EvidenceError("rejected")), \
             mock.patch.object(promotion.controller, "promote") as write:
            with self.assertRaises(evidence.EvidenceError):
                promotion.verify_and_promote(request, apply=True)
            approval.assert_called_once()
            write.assert_not_called()


if __name__ == "__main__":
    unittest.main()
