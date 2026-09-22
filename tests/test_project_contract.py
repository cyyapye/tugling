from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
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

    def add_flow_runner(self, root: Path) -> None:
        (root / "flow_runner.py").write_text(
            """import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

mode, flow_id = sys.argv[1:3]
local = Path('.tugling/local')
local.mkdir(parents=True, exist_ok=True)

def record(event, **extra):
    row = {'event': event, 'flow': flow_id, 'pid': os.getpid(),
           'time': time.monotonic(), **extra}
    descriptor = os.open(local / 'events.jsonl', os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(descriptor, (json.dumps(row, sort_keys=True) + '\\n').encode())
    finally:
        os.close(descriptor)

record('start')
if mode == 'sleep':
    time.sleep(float(sys.argv[3]))
elif mode == 'fail':
    time.sleep(float(sys.argv[3]))
    record('finish')
    raise SystemExit(int(sys.argv[4]))
elif mode == 'tree':
    pidfile = Path(sys.argv[3])
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
    pidfile.write_text(str(child.pid))
    time.sleep(30)
elif mode == 'term-handler':
    marker = Path(sys.argv[3])
    blocked = signal.SIGTERM in signal.pthread_sigmask(signal.SIG_BLOCK, set())
    record('signal-mask', sigterm_blocked=blocked)
    def terminated(signum, frame):
        marker.write_text('received')
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, terminated)
    while True:
        time.sleep(.05)
else:
    raise SystemExit('unknown mode')
record('finish')
""",
            encoding="utf-8",
        )

    def flow(self, flow_id: str, *args: str, depends_on: list[str] | None = None,
             timeout: int = 10) -> dict[str, object]:
        flow: dict[str, object] = {
            "id": flow_id,
            "description": f"Synthetic real-process holdout for {flow_id}.",
            "argv": [sys.executable, "flow_runner.py", *args],
            "timeout_seconds": timeout,
            "sources": ["flow_runner.py"],
            "runtime": None,
        }
        if depends_on is not None:
            flow["depends_on"] = depends_on
        return flow

    def configure_flows(
        self,
        root: Path,
        flows: list[dict[str, object]],
        *,
        max_parallel: int | None = None,
        required: list[str] | None = None,
        budget: int | None = None,
    ) -> None:
        self.add_flow_runner(root)
        mapping: dict[str, object] = {"schema_version": 1, "flows": flows}
        if max_parallel is not None:
            mapping["execution"] = {"max_parallel": max_parallel}
        if required is not None:
            mapping["requirements"] = [{
                "id": "synthetic-rule",
                "description": "All synthetic scheduler holdouts pass.",
                "sources": ["AGENTS.md"],
                "flows": required,
            }]
        (root / ".tugling" / "checks.json").write_text(
            json.dumps(mapping, indent=2) + "\n", encoding="utf-8")
        config_path = root / ".tugling" / "project.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["project"]["verification"] = ".tugling/checks.json"
        if budget is not None:
            config["project"]["verification_budget_seconds"] = budget
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        self.run_git(root, "add", ".")
        self.run_git(root, "-c", "commit.gpgsign=false", "commit", "-qm", "add scheduler holdout")

    def validate(self, root: Path, **kwargs: object) -> dict[str, object]:
        return contract.validate_project(
            root=root,
            config_path=Path(".tugling/project.json"),
            source_root=ROOT,
            source_mode="pinned",
            **kwargs,
        )

    def assert_process_stopped(self, pid: int) -> None:
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            time.sleep(.02)
        self.fail(f"owned process still exists: {pid}")

    def receipt(self, root: Path, report: dict[str, object]) -> tuple[Path, dict[str, object]]:
        flow_verification = report["flow_verification"]
        self.assertIsInstance(flow_verification, dict)
        path = root / flow_verification["path"]
        return path, json.loads(path.read_text(encoding="utf-8"))

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

    def test_scheduler_defaults_to_serial_and_parallelism_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            self.configure_flows(root, [
                self.flow("one", "sleep", "one", ".18"),
                self.flow("two", "sleep", "two", ".18"),
            ])
            serial = self.validate(root, run_flows=["one", "two"])
            _, receipt = self.receipt(root, serial)
            self.assertEqual(receipt["execution_plan"]["max_parallel"], 1)
            one, two = receipt["results"]
            self.assertGreaterEqual(two["started_offset_seconds"], one["finished_offset_seconds"])

        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            self.configure_flows(root, [
                self.flow("one", "sleep", "one", ".25"),
                self.flow("two", "sleep", "two", ".25"),
                self.flow("three", "sleep", "three", ".25"),
            ], max_parallel=2)
            parallel = self.validate(root, run_flows=["one", "two", "three"])
            _, receipt = self.receipt(root, parallel)
            one, two, three = receipt["results"]
            self.assertLess(two["started_offset_seconds"], one["finished_offset_seconds"])
            self.assertGreaterEqual(three["started_offset_seconds"],
                                    min(one["finished_offset_seconds"], two["finished_offset_seconds"]))
            contract.validate_execution_timing(receipt["results"], receipt["execution_plan"])

    def test_dependencies_are_ordered_and_required_selection_includes_transitive_closure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            self.configure_flows(root, [
                self.flow("foundation", "sleep", "foundation", ".12"),
                self.flow("middle", "sleep", "middle", ".12", depends_on=["foundation"]),
                self.flow("leaf", "sleep", "leaf", ".05", depends_on=["middle"]),
                self.flow("independent", "sleep", "independent", ".2"),
            ], max_parallel=3, required=["leaf"])
            report = self.validate(root, run_required=True)
            _, receipt = self.receipt(root, report)
            self.assertEqual(receipt["requested_flows"], ["foundation", "middle", "leaf"])
            foundation, middle, leaf = receipt["results"]
            self.assertGreaterEqual(middle["started_offset_seconds"], foundation["finished_offset_seconds"])
            self.assertGreaterEqual(leaf["started_offset_seconds"], middle["finished_offset_seconds"])
            events = [json.loads(line) for line in
                      (root / ".tugling/local/events.jsonl").read_text().splitlines()]
            self.assertNotIn("independent", {event["flow"] for event in events})

    def test_map_rejects_invalid_parallelism_dependencies_cycles_and_duplicate_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory).resolve()
            self.add_flow_runner(root)
            base = self.flow("one", "sleep", "one", ".01")
            path = root / ".tugling" / "checks.json"
            path.write_text(json.dumps({"schema_version": 1, "flows": [base]}))
            self.run_git(root, "add", ".")
            self.run_git(root, "-c", "commit.gpgsign=false", "commit", "-qm", "track map fixture")
            invalid = [
                ({"schema_version": 1, "flows": [base], "execution": {"max_parallel": 0}}, "integer from 1 to 8"),
                ({"schema_version": 1, "flows": [base], "execution": {"max_parallel": True}}, "integer from 1 to 8"),
                ({"schema_version": 1, "flows": [
                    self.flow("one", "sleep", "one", ".01", depends_on=["missing"])]}, "distinct existing flows"),
                ({"schema_version": 1, "flows": [
                    self.flow("one", "sleep", "one", ".01", depends_on=["one"])]}, "depend on itself"),
                ({"schema_version": 1, "flows": [
                    self.flow("one", "sleep", "one", ".01", depends_on=["two", "two"]),
                    self.flow("two", "sleep", "two", ".01")]}, "distinct existing flows"),
                ({"schema_version": 1, "flows": [
                    self.flow("one", "sleep", "one", ".01", depends_on=["two"]),
                    self.flow("two", "sleep", "two", ".01", depends_on=["one"])]}, "must not contain cycles"),
                ({"schema_version": 1, "flows": [base, {**base, "id": "two"}]}, "duplicate native commands"),
            ]
            for mapping, reason in invalid:
                with self.subTest(reason=reason):
                    path.write_text(json.dumps(mapping), encoding="utf-8")
                    with self.assertRaisesRegex(contract.ContractError, reason):
                        contract.validate_verification_map(root, ".tugling/checks.json")

    def test_selected_flow_requires_its_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            self.configure_flows(root, [
                self.flow("first", "sleep", "first", ".01"),
                self.flow("second", "sleep", "second", ".01", depends_on=["first"]),
            ], max_parallel=2)
            with self.assertRaisesRegex(contract.ContractError, "explicitly include their dependencies"):
                self.validate(root, run_flows=["second"])
            self.assertFalse((root / ".tugling/local/events.jsonl").exists())

    def test_failure_stops_siblings_reaps_descendants_and_never_starts_dependents(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            child_pid = root / ".tugling/local/tree-child.pid"
            dependent_marker = root / ".tugling/local/dependent.marker"
            flows = [
                self.flow("failure", "fail", "failure", ".15", "7"),
                self.flow("tree", "tree", "tree", str(child_pid)),
                self.flow("dependent", "term-handler", "dependent", str(dependent_marker),
                          depends_on=["failure"]),
            ]
            self.configure_flows(root, flows, max_parallel=2)
            report = self.validate(root, run_flows=["failure", "tree", "dependent"])
            _, receipt = self.receipt(root, report)
            self.assertEqual(report["status"], "FAIL")
            self.assertEqual({row["id"] for row in receipt["results"]}, {"failure", "tree"})
            failures = {row["id"]: row["failure"] for row in receipt["results"]}
            self.assertEqual(failures["failure"], "command-failed")
            self.assertEqual(failures["tree"], "cancelled-after-failure")
            self.assertFalse(dependent_marker.exists())
            self.assert_process_stopped(int(child_pid.read_text()))

    def test_timeout_and_global_budget_stop_dependents_and_reap_owned_groups(self) -> None:
        for mode in ("timeout", "budget"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = self.make_project(directory)
                pidfile = root / f".tugling/local/{mode}-child.pid"
                marker = root / f".tugling/local/{mode}-dependent.marker"
                first = self.flow("first", "tree", "first", str(pidfile), timeout=1 if mode == "timeout" else 10)
                dependent = self.flow("dependent", "term-handler", "dependent", str(marker), depends_on=["first"])
                self.configure_flows(root, [first, dependent], max_parallel=2,
                                     required=["dependent"], budget=1 if mode == "budget" else None)
                started = time.monotonic()
                report = self.validate(root, run_required=True)
                elapsed = time.monotonic() - started
                _, receipt = self.receipt(root, report)
                self.assertLess(elapsed, 5)
                self.assertEqual(report["status"], "FAIL")
                self.assertEqual(receipt["results"][0]["failure"],
                                 "budget-exceeded" if mode == "budget" else "timeout")
                self.assertFalse(marker.exists())
                self.assert_process_stopped(int(pidfile.read_text()))

    def test_sigterm_cancellation_reaches_child_handler_without_inherited_signal_mask(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            marker = root / ".tugling/local/term.marker"
            dependent = root / ".tugling/local/dependent.marker"
            self.configure_flows(root, [
                self.flow("active", "term-handler", "active", str(marker)),
                self.flow("dependent", "term-handler", "dependent", str(dependent), depends_on=["active"]),
            ], max_parallel=2)
            command = [sys.executable, "-I", str(ROOT / "plugins/tugling/scripts/project_contract.py"),
                       "--repo", str(root), "--source-root", str(ROOT), "--source-mode", "pinned",
                       "--run-flow", "active", "--run-flow", "dependent", "--json"]
            process = subprocess.Popen(command, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       text=True, start_new_session=True)
            events_path = root / ".tugling/local/events.jsonl"
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if events_path.exists() and "signal-mask" in events_path.read_text():
                    break
                self.assertIsNone(process.poll(), "helper exited before cancellation control")
                time.sleep(.02)
            else:
                process.kill()
                self.fail("active child did not install its SIGTERM handler")
            process.terminate()
            stdout, stderr = process.communicate(timeout=8)
            self.assertEqual(process.returncode, 1, stderr)
            self.assertTrue(marker.exists(), "scheduler did not deliver SIGTERM to the active child")
            self.assertFalse(dependent.exists(), "scheduler started a dependent after cancellation")
            events = [json.loads(line) for line in events_path.read_text().splitlines()]
            mask = next(row for row in events if row["event"] == "signal-mask")
            self.assertFalse(mask["sigterm_blocked"], "launch guard leaked its parent signal mask")
            report = json.loads(stdout)
            failures = {row["id"]: row["failure"] for row in report["flow_verification"]["evidence"]["results"]}
            self.assertEqual(failures, {"active": "interrupted"})

    def test_receipt_validation_rejects_timing_plan_order_and_omission_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            self.configure_flows(root, [
                self.flow("one", "sleep", "one", ".08"),
                self.flow("two", "sleep", "two", ".08"),
            ])
            report = self.validate(root, run_flows=["one", "two"])
            path, original = self.receipt(root, report)
            relative = str(path.relative_to(root))
            variants = []
            changed = json.loads(json.dumps(original))
            changed["results"].reverse()
            variants.append((changed, "mismatched command"))
            changed = json.loads(json.dumps(original))
            changed["results"].pop()
            variants.append((changed, "complete successful selection"))
            changed = json.loads(json.dumps(original))
            changed["execution_plan"]["max_parallel"] = 2
            variants.append((changed, "complete successful selection"))
            changed = json.loads(json.dumps(original))
            changed["results"][1]["started_offset_seconds"] = changed["results"][0]["started_offset_seconds"]
            changed["results"][1]["duration_seconds"] = round(
                changed["results"][1]["finished_offset_seconds"] - changed["results"][1]["started_offset_seconds"], 3)
            variants.append((changed, "bounded parallel execution plan"))
            changed = json.loads(json.dumps(original))
            changed["results"][0]["duration_seconds"] += .1
            variants.append((changed, "duration differs"))
            for evidence, reason in variants:
                with self.subTest(reason=reason):
                    path.write_text(json.dumps(evidence), encoding="utf-8")
                    with self.assertRaisesRegex(contract.ContractError, reason):
                        self.validate(root, check_evidence=relative)
            path.write_text(json.dumps(original), encoding="utf-8")
            checked = self.validate(root, check_evidence=relative)
            self.assertEqual(checked["flow_verification"]["state"], "FLOWS_PASS")

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
