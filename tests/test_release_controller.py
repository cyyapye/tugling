from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import release_controller as controller


class ReleaseControllerTest(unittest.TestCase):
    """Use actual Git refs and receive hooks; do not mock promotion success."""

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory(prefix="tugling-controller-test-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.repo = self.root / "author"
        self.repo.mkdir()
        self.git(self.repo, "init", "--initial-branch=main", "--template=", ".")
        self.git(self.repo, "config", "user.name", "Synthetic test")
        self.git(self.repo, "config", "user.email", "test@example.invalid")
        for name in ("plugins", ".agents", "scripts", "tests", ".github", "evals"):
            shutil.copytree(controller.ROOT / name, self.repo / name,
                            ignore=shutil.ignore_patterns("__pycache__", "runs", "releases"))
        shutil.copy2(controller.ROOT / "Makefile", self.repo / "Makefile")
        self.approved = self.commit("reviewed controller and stable baseline")
        self.baseline = self.approved
        self.git(self.repo, "branch", "stable", self.baseline)
        (self.repo / "operator-note.md").write_text("synthetic intermediate commit")
        self.intermediate = self.commit("synthetic intermediate revision")
        value = json.loads((controller.ROOT / "evals/releases/v0.4.0/certificate.json").read_text())
        # Synthetic provenance is used only on a disposable local Git remote.
        self.version = controller.gate.plugin_identity(self.repo)["version"]
        self.tag = f"v{self.version}"
        self.certificate = self.repo / f"evals/releases/v{self.version}/certificate.json"
        self.certificate.parent.mkdir(parents=True, exist_ok=True)
        value["version"] = self.version
        value["plugin"] = controller.gate.plugin_identity(self.repo)
        value["matrix"] = {key: item for key, item in controller.gate.validate_matrix().items()
                           if key != "schema_version"}
        value["behavioral"]["released_revision"] = self.baseline
        value["behavioral"]["evaluated_revision"] = self.approved
        value["clean_room"]["revision"] = self.approved
        self.certificate.write_text(json.dumps(value))
        self.candidate = self.commit("synthetic reviewed certificate")
        self.remote = self.root / "remote.git"
        self.git(self.root, "clone", "--bare", str(self.repo), str(self.remote))
        self.digest = hashlib.sha256(self.certificate.read_bytes()).hexdigest()

    def git(self, root: Path, *args: str) -> str:
        # Intentionally keep receive hooks enabled here and on the remote.
        result = subprocess.run(["git", *args], cwd=root, env=controller.git_env(),
                                text=True, capture_output=True, check=True)
        return result.stdout.strip()

    def commit(self, message: str) -> str:
        self.git(self.repo, "add", ".")
        self.git(self.repo, "commit", "--quiet", "-m", message)
        return self.git(self.repo, "rev-parse", "HEAD")

    def update_main(self) -> None:
        self.candidate = self.commit("synthetic candidate change")
        self.git(self.repo, "push", str(self.remote), "main")

    def run_promotion(self, **changes: object) -> dict:
        args = dict(remote=str(self.remote), controller=self.approved, candidate=self.candidate,
                    version=self.version, certificate_digest=self.digest, apply=True)
        args.update(changes)
        return controller.promote(**args)

    def refs(self) -> str:
        return self.git(self.remote, "show-ref")

    def assert_rejected_without_writes(self, pattern: str, **changes: object) -> None:
        before = self.refs()
        with self.assertRaisesRegex(controller.ControllerError, pattern):
            self.run_promotion(**changes)
        self.assertEqual(self.refs(), before)

    def test_real_atomic_promotion_and_idempotent_retry(self) -> None:
        self.assertEqual(self.run_promotion()["state"], "PROMOTED")
        self.assertEqual(self.git(self.remote, "rev-parse", "stable"), self.candidate)
        self.assertEqual(self.git(self.remote, "rev-parse", f"{self.tag}^{{commit}}"), self.candidate)
        before = self.refs()
        self.assertEqual(self.run_promotion()["state"], "ALREADY_PROMOTED")
        self.assertEqual(self.refs(), before)

    def test_read_only_preflight_does_not_create_refs(self) -> None:
        before = self.refs()
        self.assertEqual(self.run_promotion(apply=False)["state"], "READY_FOR_REVIEWED_PROMOTION")
        self.assertEqual(self.refs(), before)

    def test_changed_grader_cannot_approve_itself(self) -> None:
        marker = self.root / "candidate-code-ran"
        (self.repo / "scripts/release_gate.py").write_text(
            f"from pathlib import Path\nPath({str(marker)!r}).touch()\nraise SystemExit(0)\n")
        self.update_main()
        self.assert_rejected_without_writes("grading or release machinery changed")
        self.assertFalse(marker.exists())

    def test_changed_threshold_requires_separate_controller_review(self) -> None:
        matrix_path = self.repo / "evals/behavioral/release-matrix.json"
        value = json.loads(matrix_path.read_text())
        value["minimum_attempts"] = 1
        matrix_path.write_text(json.dumps(value))
        self.update_main()
        self.assert_rejected_without_writes("grading or release machinery changed")

    def test_tampered_certificate_is_not_the_reviewed_certificate(self) -> None:
        value = json.loads(self.certificate.read_text())
        value["created_at"] = "2099-01-01T00:00:00Z"
        self.certificate.write_text(json.dumps(value))
        self.update_main()
        self.assert_rejected_without_writes("manually reviewed digest")

    def test_stale_candidate_and_invalid_input_are_rejected(self) -> None:
        self.assert_rejected_without_writes("exact current main", candidate=self.baseline)
        self.assert_rejected_without_writes("full lowercase commit SHAs", candidate="main")
        self.assert_rejected_without_writes("version or reviewed", version="../../escape")
        self.assert_rejected_without_writes("version or reviewed", certificate_digest="")

    def test_moved_stable_and_conflicting_tag_are_rejected(self) -> None:
        self.git(self.remote, "update-ref", "refs/heads/stable", self.candidate)
        self.assert_rejected_without_writes("stable baseline moved")
        self.git(self.remote, "update-ref", "refs/heads/stable", self.baseline)
        self.git(self.remote, "update-ref", f"refs/tags/{self.tag}", self.baseline)
        self.assert_rejected_without_writes("version tag already exists")

    def test_non_fast_forward_cannot_use_the_stable_lease(self) -> None:
        unrelated = self.git(
            self.remote, "-c", "user.name=Synthetic test", "-c", "user.email=test@example.invalid",
            "commit-tree", self.git(self.remote, "rev-parse", f"{self.candidate}^{{tree}}"),
            "-m", "unrelated stable history",
        )
        self.git(self.remote, "update-ref", "refs/heads/stable", unrelated)
        value = json.loads(self.certificate.read_text())
        value["behavioral"]["released_revision"] = unrelated
        self.certificate.write_text(json.dumps(value))
        self.digest = hashlib.sha256(self.certificate.read_bytes()).hexdigest()
        self.update_main()
        self.assert_rejected_without_writes("git merge-base failed")

    def test_main_movement_after_verification_prevents_publication(self) -> None:
        original_refs = controller.remote_refs

        def moved_main(root: Path, version: str, env: dict[str, str]) -> dict[str, str]:
            self.git(self.remote, "update-ref", "refs/heads/main", self.intermediate)
            return original_refs(root, version, env)

        with mock.patch.object(controller, "remote_refs", side_effect=moved_main):
            with self.assertRaisesRegex(controller.ControllerError, "main moved during verification"):
                self.run_promotion()
        self.assertEqual(self.git(self.remote, "rev-parse", "stable"), self.baseline)
        self.assertNotIn(f"refs/tags/{self.tag}", self.refs())

    def test_symlink_is_rejected_without_following_it(self) -> None:
        (self.repo / "plugins/tugling/escape").symlink_to(self.root / "outside")
        self.update_main()
        self.assert_rejected_without_writes("only regular files")

    def test_candidate_package_is_checked_by_trusted_verifier(self) -> None:
        (self.repo / "plugins/tugling/extra.md").write_text("unreviewed package bytes")
        self.update_main()
        before = self.refs()
        with self.assertRaisesRegex(controller.gate.ReleaseGateError, "current plugin content"):
            self.run_promotion()
        self.assertEqual(self.refs(), before)

    def test_receive_hook_rejection_does_not_partially_move_stable(self) -> None:
        hook = self.remote / "hooks/update"
        hook.write_text('#!/bin/sh\ncase "$1" in refs/tags/*) exit 1;; esac\nexit 0\n')
        hook.chmod(0o755)
        self.assert_rejected_without_writes("git push failed")

    def test_race_on_stable_rejects_the_entire_push(self) -> None:
        original_git = controller.git
        changed = False

        def racing_git(root: Path, *args: str, **kwargs: object) -> bytes:
            nonlocal changed
            if args[0] == "push":
                # Inject a real concurrent ref update after the final read.
                self.git(self.remote, "update-ref", "refs/heads/stable", self.intermediate)
                changed = True
            return original_git(root, *args, **kwargs)

        with mock.patch.object(controller, "git", side_effect=racing_git):
            with self.assertRaisesRegex(controller.ControllerError, "git push failed"):
                self.run_promotion()
        self.assertTrue(changed)
        self.assertEqual(self.git(self.remote, "rev-parse", "stable"), self.intermediate)
        self.assertNotIn(f"refs/tags/{self.tag}", self.refs())

    def test_concurrent_identical_stable_target_converges(self) -> None:
        original_git = controller.git

        def racing_git(root: Path, *args: str, **kwargs: object) -> bytes:
            if args[0] == "push":
                self.git(self.remote, "update-ref", "refs/heads/stable", self.candidate)
            return original_git(root, *args, **kwargs)

        # Git treats an already identical ref as up to date. Completing the
        # absent tag is safe: readback must still prove both requested targets.
        with mock.patch.object(controller, "git", side_effect=racing_git):
            self.assertEqual(self.run_promotion()["state"], "PROMOTED")
        self.assertEqual(self.git(self.remote, "rev-parse", "stable"), self.candidate)
        self.assertEqual(self.git(self.remote, "rev-parse", f"{self.tag}^{{commit}}"), self.candidate)

    def test_git_configuration_injection_is_removed(self) -> None:
        with mock.patch.dict(os.environ, {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.sshCommand",
                                         "GIT_CONFIG_VALUE_0": "untrusted-command", "GIT_TRACE": "1"}):
            env = controller.git_env()
        self.assertNotIn("GIT_CONFIG_COUNT", env)
        self.assertNotIn("GIT_CONFIG_VALUE_0", env)
        self.assertNotIn("GIT_TRACE", env)

    def test_isolated_cli_rejects_wrong_controller_before_network_access(self) -> None:
        poison = self.root / "pythonpath"
        poison.mkdir()
        marker = self.root / "untrusted-import"
        (poison / "json.py").write_text(f"from pathlib import Path\nPath({str(marker)!r}).touch()\n")
        result = subprocess.run(
            [sys.executable, "-I", str(self.repo / "scripts/release_controller.py"),
             "--controller-sha", "0" * 40, "--candidate-sha", self.candidate,
             "--version", self.version, "--certificate-sha256", self.digest],
            env={**os.environ, "PYTHONPATH": str(poison)}, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("not the approved controller SHA", result.stderr)
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
