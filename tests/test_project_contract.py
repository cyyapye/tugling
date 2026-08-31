from __future__ import annotations

import importlib.util
import json
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {relative}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


contract = load_module("project_contract", "plugins/tugling/scripts/project_contract.py")
learning = load_module("project_learning", "plugins/tugling/scripts/project_learning.py")


class ProjectContractTest(unittest.TestCase):
    def run_git(self, root: Path, *args: str) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=root,
            text=True,
            capture_output=True,
            check=True,
        )
        return completed.stdout.strip()

    def make_project(self, directory: str, *, learning_mode: str = "local") -> Path:
        root = Path(directory) / "project"
        (root / ".github" / "workflows").mkdir(parents=True)
        (root / ".tugling").mkdir()
        (root / "AGENTS.md").write_text(
            "# Project instructions\n\n## Tugling project adapter\n\nRun `make verify`.\n",
            encoding="utf-8",
        )
        (root / ".github" / "workflows" / "tugling.yml").write_text(
            "name: Tugling\n",
            encoding="utf-8",
        )
        (root / ".gitignore").write_text(".tugling/local/\n", encoding="utf-8")
        dogfood = {
            "schema_version": 1,
            "data_policy": "synthetic-only",
            "case": {
                "id": "project-boundary",
                "skill": "tugling",
                "sandbox": "read-only",
                "minimum_score": 0.8,
                "expected_state": "ADVISORY",
                "max_changed_files": 0,
                "prompt": "Review this synthetic project boundary and choose the documented verification command without changing files.",
                "decision_questions": [
                    {
                        "id": "verify",
                        "question": "Which gate is canonical?",
                        "options": ["make_verify", "invent_command"],
                        "expected": "make_verify",
                        "critical": True,
                    }
                ],
            },
        }
        (root / ".tugling" / "dogfood.json").write_text(
            json.dumps(dogfood, indent=2) + "\n",
            encoding="utf-8",
        )
        identity = contract.source_identity(ROOT)
        config = {
            "schema_version": 1,
            "tugling": {
                "repository": "https://github.com/example/tugling",
                "channel": "pinned",
                "revision": identity["revision"],
                "version": identity["version"],
            },
            "project": {
                "adapter": "AGENTS.md",
                "instructions": ["AGENTS.md"],
                "canonical_verify": ["git", "status", "--short"],
                "ci_workflow": ".github/workflows/tugling.yml",
                "dogfood_case": ".tugling/dogfood.json",
            },
            "learning": {
                "mode": learning_mode,
                "local_path": ".tugling/local/corrections.jsonl",
            },
        }
        (root / ".tugling" / "project.json").write_text(
            json.dumps(config, indent=2) + "\n",
            encoding="utf-8",
        )
        self.run_git(root, "init", "-q")
        self.run_git(root, "config", "user.name", "Tugling Test")
        self.run_git(root, "config", "user.email", "test@example.invalid")
        self.run_git(root, "add", ".")
        self.run_git(
            root,
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-q",
            "-m",
            "fixture",
        )
        return root

    def test_valid_pinned_project_contract_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            report = contract.validate_project(
                root=root,
                config_path=Path(".tugling/project.json"),
                source_root=ROOT,
                source_mode="pinned",
                run_native=True,
            )
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["learning"]["mode"], "local")
        self.assertEqual(report["dogfood"]["questions"], 1)
        self.assertEqual(report["native_verification"]["exit_code"], 0)

    def test_pinned_source_cannot_silently_be_a_different_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            path = root / ".tugling" / "project.json"
            config = json.loads(path.read_text(encoding="utf-8"))
            config["tugling"]["revision"] = "0" * 40
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(contract.ContractError, "revision mismatch"):
                contract.validate_project(
                    root=root,
                    config_path=Path(".tugling/project.json"),
                    source_root=ROOT,
                    source_mode="pinned",
                )

    def test_local_correction_ledger_must_not_be_tracked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            local = root / ".tugling" / "local"
            local.mkdir()
            (local / "corrections.jsonl").write_text("{}\n", encoding="utf-8")
            self.run_git(root, "add", "-f", ".tugling/local/corrections.jsonl")
            with self.assertRaisesRegex(contract.ContractError, "must never be committed"):
                contract.validate_project(
                    root=root,
                    config_path=Path(".tugling/project.json"),
                    source_root=ROOT,
                    source_mode="pinned",
                )

    def test_local_learning_capture_digest_and_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            record = learning.capture(
                root=root,
                summary="The verifier overstated a local result.",
                observed="It reported a remote pass after only local checks.",
                expected="Keep local and remote evidence states distinct.",
                scope="Repository verification handoffs.",
            )
            path = root / ".tugling" / "local" / "corrections.jsonl"
            self.assertTrue(path.is_file())
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            digest = learning.digest_markdown(learning.read_records(path))
            self.assertIn(record["id"], digest)
            reviewed = learning.review(
                root=root,
                record_id=record["id"],
                decision="keep-local",
                note="The repository already has the stricter release vocabulary.",
            )
            self.assertEqual(reviewed["review"]["decision"], "keep-local")
            self.assertIn("No pending corrections", learning.digest_markdown(learning.read_records(path)))

    def test_local_learning_refuses_secret_like_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            with self.assertRaisesRegex(learning.LearningError, "secret material"):
                learning.capture(
                    root=root,
                    summary="Do not copy sk-abcdefghijklmnopqrstuvwxyz into a lesson.",
                    observed="A token was copied.",
                    expected="Keep credentials out.",
                    scope="Local capture.",
                )


if __name__ == "__main__":
    unittest.main()
