from __future__ import annotations

import copy
import json
import os
import shlex
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, timedelta, timezone

import test_project_contract as fixtures
import test_project_verification as lifecycle


ROOT = fixtures.ROOT
HELPER = ROOT / "plugins/tugling/scripts/project_contract.py"

SERVICE = '''from pathlib import Path

POLL_SECONDS = 10

class API:
    def __init__(self):
        self.requests = 0

    def request(self):
        self.requests += 1

def workload():
    apis = [API(), API()]
    for now in range(600):
        for api in apis:
            if now % POLL_SECONDS == 0:
                api.request()
    return sum(api.requests for api in apis)

def temporary_report(directory):
    owned = Path(directory) / "owned-report"
    try:
        owned.write_text("synthetic report")
        raise RuntimeError("synthetic producer failure")
    finally:
        owned.unlink()
'''

CHECKS = '''import pathlib
import sys
import tempfile
import unittest
from service import temporary_report, workload

class NativeChecks(unittest.TestCase):
    def test_budget(self):
        # The two-client, ten-minute allowance is 500 with half reserved.
        self.assertLessEqual(workload(), 250)

    def test_cleanup(self):
        with tempfile.TemporaryDirectory(dir=".tugling/local") as directory:
            foreign = pathlib.Path(directory) / "foreign"
            foreign.write_text("preserve")
            with self.assertRaises(RuntimeError):
                temporary_report(directory)
            self.assertEqual(foreign.read_text(), "preserve")
            self.assertEqual(sorted(p.name for p in pathlib.Path(directory).iterdir()), ["foreign"])

local = pathlib.Path(".tugling/local")
local.mkdir(exist_ok=True)
with (local / "calls").open("a") as trace:
    trace.write(sys.argv[1] + "\\n")
suite = unittest.TestSuite([NativeChecks("test_" + sys.argv[1])])
result = unittest.TextTestRunner().run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
'''


class RequiredVerificationTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.fixture = fixtures.ProjectContractTest()
        self.root = self.fixture.make_project(directory.name, learning_mode="off").resolve()
        (self.root / "service.py").write_text(SERVICE)
        (self.root / "checks.py").write_text(CHECKS)
        (self.root / "policy.md").write_text(
            "Two clients share 250 requests per 600 seconds after reservations. "
            "Failed report creation removes owned artifacts and preserves foreign files.\n"
        )
        self.mapping = {"schema_version": 1, "flows": [
            {"id": name, "description": description,
             "argv": [sys.executable, "checks.py", name], "timeout_seconds": 5,
             "sources": ["checks.py", "service.py"], "runtime": None}
            for name, description in (("cleanup", "Failed producer preserves only foreign files."),
                                      ("budget", "Aggregate requests stay within the usable allowance."))
        ], "requirements": [
            {"id": "resource-envelope", "description": "Reserve half the shared allowance.",
             "sources": ["policy.md"], "flows": ["budget"]},
            {"id": "artifact-ownership", "description": "Preserve foreign files after producer failure.",
             "sources": ["policy.md"], "flows": ["cleanup"]},
        ]}
        self.map_path = self.root / ".tugling/verification.json"
        self.config_path = self.root / ".tugling/project.json"
        self.config = json.loads(self.config_path.read_text())
        self.config["project"]["verification"] = ".tugling/verification.json"
        self.save()

    def save(self):
        self.map_path.write_text(json.dumps(self.mapping))
        self.config_path.write_text(json.dumps(self.config))
        self.fixture.run_git(self.root, "add", ".")
        self.fixture.run_git(self.root, "-c", "commit.gpgsign=false", "commit", "--allow-empty", "-qm", "required check fixture")

    def argv(self, *args, helper=HELPER):
        return [sys.executable, str(helper), "--repo", str(self.root), "--source-root", str(ROOT),
                "--source-mode", "candidate", "--json", *args]

    def cli(self, *args, helper=HELPER):
        return subprocess.run(self.argv(*args, helper=helper), text=True, capture_output=True, timeout=20)

    def required(self):
        result = self.cli("--run-required")
        self.assertTrue(result.stdout, result.stderr)
        return result, json.loads(result.stdout)["flow_verification"]

    def calls(self):
        path = self.root / ".tugling/local/calls"
        return path.read_text().splitlines() if path.exists() else []

    def test_required_gate_executes_shared_checks_once_in_map_order(self):
        self.mapping["requirements"].append({"id": "combined", "description": "Both policies apply.",
                                            "sources": ["policy.md"], "flows": ["budget", "cleanup"]})
        self.save()
        result, verification = self.required()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(verification["state"], "REQUIRED_PASS")
        self.assertEqual(self.calls(), ["cleanup", "budget"])
        self.assertEqual(verification["evidence"]["requirements"], self.mapping["requirements"])
        self.assertEqual(self.cli("--check-required-evidence", verification["path"]).returncode, 0)
        # A receipt check does not run the test suite again.
        self.assertEqual(self.calls(), ["cleanup", "budget"])

    def test_receipt_reuse_rejects_other_attempt_environment_and_expired_results(self):
        invocation = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "synthetic/project",
                      "GITHUB_WORKFLOW_REF": "synthetic/project/.github/workflows/ci.yml@refs/pull/1/merge",
                      "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_SHA": "a" * 40,
                      "TUGLING_VERIFICATION_ENVIRONMENT": "synthetic-runtime-v1"}
        with patch.dict(os.environ, invocation):
            _, verification = self.required()
            self.assertEqual(self.cli("--check-required-evidence", verification["path"]).returncode, 0)
            for key in invocation:
                with self.subTest(key=key), patch.dict(os.environ, {key: invocation[key] + "changed"}):
                    self.assertEqual(self.cli("--check-required-evidence", verification["path"]).returncode, 1)
            path = self.root / verification["path"]
            original = json.loads(path.read_text())
            for seconds in (-8 * 86400, 3600):
                date = (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()
                path.write_text(json.dumps({**original, "started_at": date, "finished_at": date}))
                self.assertEqual(self.cli("--check-required-evidence", verification["path"]).returncode, 1)
        self.assertEqual(self.calls(), ["cleanup", "budget"])

    def test_duplicate_leaf_commands_fail_before_execution(self):
        self.mapping["flows"][1]["argv"] = self.mapping["flows"][0]["argv"]
        self.save()
        result = self.cli("--run-required")
        self.assertEqual(result.returncode, 1)
        self.assertIn("duplicate native commands", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_verification_budget_is_measured_without_omitting_checks(self):
        self.config["project"]["verification_budget_seconds"] = 1
        checks = self.root / "checks.py"
        checks.write_text("import time\ntime.sleep(0.6)\n" + checks.read_text())
        self.save()
        result, verification = self.required()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(self.calls(), ["cleanup", "budget"])
        self.assertFalse(verification["evidence"]["performance"]["within_budget"])
        self.assertGreater(verification["evidence"]["performance"]["active_seconds"], 1)
        self.assertEqual(self.cli("--check-required-evidence", verification["path"]).returncode, 1)

    def test_receipt_rejects_invalid_or_substituted_timing(self):
        _, verification = self.required()
        path = self.root / verification["path"]
        original = json.loads(path.read_text())
        for value in (True, -1, float("nan"), float("inf"), "1", 999):
            candidate = copy.deepcopy(original)
            candidate["results"][0]["duration_seconds"] = value
            path.write_text(json.dumps(candidate))
            self.assertEqual(self.cli("--check-required-evidence", verification["path"]).returncode, 1)

    def test_verification_budget_rejects_invalid_configuration(self):
        for budget in (True, 0, 7201, "60"):
            self.config["project"]["verification_budget_seconds"] = budget
            self.save()
            self.assertEqual(self.cli("--run-required").returncode, 1)
        self.assertEqual(self.calls(), [])

    def test_actual_resource_defect_fails_required_gate_after_focused_pass(self):
        (self.root / "service.py").write_text(SERVICE.replace("POLL_SECONDS = 10", "POLL_SECONDS = 1"))
        self.save()
        focused = self.cli("--run-flow", "cleanup")
        self.assertEqual(focused.returncode, 0, focused.stderr)
        selected = json.loads(focused.stdout)["flow_verification"]
        self.assertEqual(self.cli("--check-required-evidence", selected["path"]).returncode, 1)
        result, verification = self.required()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(verification["state"], "REQUIRED_FAIL")
        self.assertIn("1200 not less than or equal to 250", result.stderr)
        self.assertEqual(self.cli("--check-required-evidence", verification["path"]).returncode, 1)
        (self.root / "service.py").write_text(SERVICE)
        self.save()
        self.assertEqual(self.required()[0].returncode, 0)

    def test_actual_cleanup_defect_fails_and_stops_before_budget_check(self):
        (self.root / "service.py").write_text(SERVICE.replace("        owned.unlink()", "        pass"))
        self.save()
        result, verification = self.required()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.calls(), ["cleanup"])
        self.assertEqual([row["id"] for row in verification["evidence"]["results"]], ["cleanup"])

    def test_legacy_map_validation_stays_read_only_but_required_mode_refuses_it(self):
        self.mapping.pop("requirements")
        self.save()
        self.assertEqual(self.cli().returncode, 0)
        self.assertEqual(self.cli("--run-required").returncode, 1)
        self.assertFalse((self.root / ".tugling/local").exists())
        self.config["project"].pop("verification")
        self.save()
        self.assertEqual(self.cli().returncode, 0)
        self.assertEqual(self.cli("--run-required").returncode, 1)

    def test_invalid_or_unmapped_requirements_are_rejected_before_execution(self):
        valid = copy.deepcopy(self.mapping["requirements"])
        cases = [None, [], "budget", [valid[0], valid[0]],
                 [{**valid[0], "flows": []}], [{**valid[0], "flows": ["missing"]}],
                 [{**valid[0], "flows": ["budget", "budget"]}],
                 [{**valid[0], "sources": []}], [{**valid[0], "sources": ["missing.md"]}]]
        for requirements in cases:
            with self.subTest(requirements=requirements):
                self.mapping["requirements"] = requirements
                self.save()
                self.assertEqual(self.cli().returncode, 1)
                self.assertEqual(self.cli("--run-required").returncode, 1)
                self.assertFalse((self.root / ".tugling/local").exists())

    def test_selected_receipt_even_for_all_flows_is_not_required_evidence(self):
        selected = self.cli("--run-flow", "cleanup", "--run-flow", "budget")
        self.assertEqual(selected.returncode, 0, selected.stderr)
        path = json.loads(selected.stdout)["flow_verification"]["path"]
        self.assertEqual(self.cli("--check-flow-evidence", path).returncode, 0)
        self.assertEqual(self.cli("--check-required-evidence", path).returncode, 1)

    def test_partial_or_unsuccessful_required_receipt_is_rejected(self):
        _, verification = self.required()
        path = self.root / verification["path"]
        original = json.loads(path.read_text())
        variants = []
        for key, value in (("requirements", []), ("requested_flows", ["cleanup"]),
                           ("results", original["results"][:1]), ("state", "FLOWS_PASS")):
            variants.append({**original, key: value})
        for key, value in (("exit_code", True), ("failure", "skipped"), ("argv", ["true"]),
                           ("forced_cleanup", True), ("id", "cleanup")):
            candidate = copy.deepcopy(original)
            candidate["results"][1][key] = value
            variants.append(candidate)
        for candidate in variants:
            with self.subTest(candidate=candidate):
                path.write_text(json.dumps(candidate))
                self.assertEqual(self.cli("--check-required-evidence", verification["path"]).returncode, 1)

    def test_changed_policy_map_or_helper_invalidates_required_evidence(self):
        for change in ("policy", "map", "helper"):
            with self.subTest(change=change):
                _, verification = self.required()
                helper = HELPER
                if change == "policy":
                    (self.root / "policy.md").write_text("A revised accepted workload.\n")
                    self.save()
                elif change == "map":
                    self.mapping["requirements"][0]["description"] = "Revised requirement."
                    self.save()
                else:
                    helper = self.directory / "different_helper.py"
                    helper.write_text(HELPER.read_text() + "\n# changed helper\n")
                self.assertEqual(self.cli("--check-required-evidence", verification["path"], helper=helper).returncode, 1)

    def test_canonical_command_runs_required_leaf_checks_once(self):
        command = shlex.join(self.argv("--run-required"))
        (self.root / "Makefile").write_text("verify:\n\t" + command + "\n")
        self.config["project"]["canonical_verify"] = ["make", "verify"]
        self.save()
        result = self.cli("--run-native")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), ["cleanup", "budget"])

    def test_required_wrapper_can_run_existing_canonical_command_once(self):
        (self.root / "Makefile").write_text("verify:\n\t" + shlex.join([sys.executable, "checks.py", "cleanup"]) + "\n")
        self.config["project"]["canonical_verify"] = ["make", "verify"]
        self.mapping["flows"][0]["argv"] = ["make", "verify"]
        self.mapping["flows"][0]["sources"].append("Makefile")
        self.save()
        result = subprocess.run([arg for arg in self.argv("--run-required") if arg != "--json"],
                                text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("REQUIRED_PASS", result.stdout)
        self.assertNotIn("canonical gate unexecuted", result.stdout)
        self.assertEqual(self.calls(), ["cleanup", "budget"])

    def test_independent_project_execution_is_allowed_but_project_cycles_fail(self):
        peer = self.fixture.make_project(str(self.directory / "independent"), learning_mode="off").resolve()
        for name in ("service.py", "checks.py", "policy.md"):
            (peer / name).write_bytes((self.root / name).read_bytes())
        peer_config_path = peer / ".tugling/project.json"
        peer_config = json.loads(peer_config_path.read_text())
        peer_config["project"]["verification"] = ".tugling/verification.json"
        peer_config_path.write_text(json.dumps(peer_config))
        peer_map_path = peer / ".tugling/verification.json"
        peer_mapping = copy.deepcopy(self.mapping)

        def save_peer():
            peer_map_path.write_text(json.dumps(peer_mapping))
            self.fixture.run_git(peer, "add", ".")
            self.fixture.run_git(peer, "-c", "commit.gpgsign=false", "commit", "-qm", "peer fixture")

        save_peer()
        self.mapping["flows"][0]["argv"] = [sys.executable, str(HELPER), "--repo", str(peer),
            "--source-root", str(ROOT), "--source-mode", "candidate", "--run-required"]
        self.mapping["flows"][0]["timeout_seconds"] = 15
        self.save()
        result, verification = self.required()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(verification["state"], "REQUIRED_PASS")
        self.assertEqual((peer / ".tugling/local/calls").read_text().splitlines(), ["cleanup", "budget"])
        self.assertEqual(self.calls(), ["budget"])

        # A canonical wrapper must also record its own re-entry without blocking
        # the valid canonical -> required transition in the earlier wiring test.
        peer_native = [sys.executable, str(HELPER), "--repo", str(peer), "--source-root", str(ROOT),
                       "--source-mode", "candidate", "--run-native"]
        peer_config["project"]["canonical_verify"] = peer_native
        peer_config_path.write_text(json.dumps(peer_config))
        save_peer()
        self.mapping["flows"][0]["argv"] = peer_native
        self.save()
        result, verification = self.required()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("recursive native flow execution", result.stderr)
        self.assertEqual(verification["evidence"]["results"][0]["failure"], "command-failed")

        self.mapping["flows"][0]["argv"] = [*peer_native[:-1], "--run-required"]
        self.save()
        peer_mapping["flows"][0]["argv"] = self.argv("--run-required")
        save_peer()
        result, verification = self.required()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(verification["state"], "REQUIRED_FAIL")
        self.assertIn("recursive native flow execution", result.stderr)

    def test_recursive_execution_fails_but_nested_validation_is_allowed(self):
        for mode in (None, "--run-required", "--run-flow", "--run-native"):
            with self.subTest(mode=mode):
                args = [] if mode is None else [mode] + (["cleanup"] if mode == "--run-flow" else [])
                self.mapping["flows"][0]["argv"] = self.argv(*args)
                self.save()
                result, verification = self.required()
                self.assertEqual(result.returncode, 0 if mode is None else 1, result.stderr)
                if mode:
                    self.assertIn("recursive native flow execution", result.stderr)
                    self.assertEqual(verification["state"], "REQUIRED_FAIL")

    def test_required_gate_obeys_aggregate_timeout_budget_before_execution(self):
        self.mapping["flows"].append({**self.mapping["flows"][0], "id": "extra"})
        for flow in self.mapping["flows"]:
            flow["timeout_seconds"] = 3600
        self.mapping["requirements"][0]["flows"].append("extra")
        self.save()
        result = self.cli("--run-required")
        self.assertEqual(result.returncode, 1)
        self.assertIn("7200", result.stderr)
        self.assertFalse((self.root / ".tugling/local").exists())

    def runtime_mode(self, mode, timeout):
        (self.root / "native_check.py").write_text(lifecycle.NATIVE_CHECK)
        self.mapping["flows"][0].update(
            argv=[sys.executable, "native_check.py", mode], timeout_seconds=timeout,
            sources=["native_check.py", "AGENTS.md"], runtime={
                "owner": "native-command", "launch": "Own a synthetic HTTP server.",
                "health": "Read AGENTS.md through HTTP.", "cleanup": "Terminate and wait in finally.",
            },
        )
        self.save()

    def test_required_timeout_and_leak_fail_and_reap_owned_children(self):
        for mode, failure in (("timeout", "timeout"), ("leak", "native-cleanup-incomplete")):
            with self.subTest(mode=mode):
                self.runtime_mode(mode, 1)
                result, verification = self.required()
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(verification["state"], "REQUIRED_FAIL")
                self.assertEqual(verification["evidence"]["results"][0]["failure"], failure)
                lifecycle.ProjectVerificationTest.assert_server_stopped(self)

    def test_required_sigterm_cleans_owned_children_and_records_failure(self):
        self.runtime_mode("timeout", 60)
        process = subprocess.Popen(self.argv("--run-required"), text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            for _ in range(300):
                if (self.root / ".tugling/local/port").exists():
                    break
                if process.poll() is not None:
                    self.fail(process.communicate())
                time.sleep(.01)
            self.assertTrue((self.root / ".tugling/local/port").exists())
            process.send_signal(signal.SIGTERM)
            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 1, stderr)
            verification = json.loads(stdout)["flow_verification"]
            self.assertEqual(verification["state"], "REQUIRED_FAIL")
            self.assertEqual(verification["evidence"]["results"][0]["failure"], "interrupted")
            lifecycle.ProjectVerificationTest.assert_server_stopped(self)
        finally:
            if process.poll() is None:
                process.terminate()
            process.communicate(timeout=10)


if __name__ == "__main__":
    unittest.main()
