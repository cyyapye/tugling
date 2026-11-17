#!/usr/bin/env python3
"""Observe familiar Pstack workflows through an isolated local Codex plugin install.

No model-supplied score or multiple-choice answer is graded. Automated checks
cover artifacts and scope; a reviewer must inspect the retained output and trace.
This local diagnostic cannot generate a release certificate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import selectors
import sys
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

if __package__:
    from . import behavioral_eval as harness, clean_room_install as package, codex_runtime as runtime
else:
    import behavioral_eval as harness
    import clean_room_install as package
    import codex_runtime as runtime


ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evals/pstack/cases.json"
SOURCE = '''import argparse

def greeting(name):
    return f"Hello, {name.split()[0]}!"

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    print(greeting(parser.parse_args().name))
'''
TEST = '''import unittest
from greet import greeting

class GreetingTest(unittest.TestCase):
    def test_single_name(self):
        self.assertEqual(greeting("Ada"), "Hello, Ada!")
'''


def snapshot(root: Path, *, exclude_git: bool = True) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(
                os.readlink(p).encode() if p.is_symlink() else p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if (p.is_file() or p.is_symlink())
            and (not exclude_git or ".git" not in p.relative_to(root).parts)}


def fixture(root: Path) -> None:
    (root / "tests").mkdir(parents=True)
    (root / "greet.py").write_text(SOURCE)
    (root / "tests/test_greeting.py").write_text(TEST)
    (root / "README.md").write_text(
        "# Greeting CLI\n\nRun `python3 greet.py 'Ada Lovelace'`. Expected output is\n"
        "`Hello, Ada Lovelace!`. Preserve the complete name, including internal spaces.\n"
        "The offline standard-library CLI also supports single-word names.\n")
    (root / "Makefile").write_text(".PHONY: verify\nverify:\n\tpython3 -m unittest discover -s tests\n")
    (root / ".gitignore").write_text("__pycache__/\n*.pyc\n")
    (root / "AGENTS.md").write_text(
        "Use `make verify` as the native gate. This project runs offline.\n"
        "Work inside this repository only. Do not delegate, use external services,\n"
        "request approvals, install dependencies, commit, push, merge, or deploy.\n"
        "Inspect installed plugin instructions as needed. Do not inspect unrelated\n"
        "user files, credentials, or chat history. Preserve user-requested scope.\n")
    for args in (["init", "-q"], ["add", "."],
                 ["-c", "user.name=Maintainer", "-c", "user.email=maintainer@example.invalid",
                  "-c", "commit.gpgsign=false", "commit", "-qm", "Initial greeting CLI"]):
        harness.run_command(["git", *args], cwd=root, check=True)


def install(binary: str, home: Path, marketplace: Path, env: dict) -> Path:
    for args in (["marketplace", "add", str(marketplace), "--json"],
                 ["add", "tugling@tugling", "--json"]):
        result = package.run([binary, "plugin", *args], cwd=home.parent, env=env, check=True)
    installed = Path(json.loads(result.stdout)["installedPath"])
    if not installed.resolve().is_relative_to(home.resolve()):
        raise ValueError("plugin installation escaped the isolated Codex home")
    if package.digest_tree(installed) != package.digest_tree(marketplace / package.PLUGIN_RELATIVE):
        raise ValueError("installed plugin differs from the frozen local package")
    return installed


def completed_commands(raw: str) -> list[dict]:
    commands = []
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        item = event.get("item", {})
        if event.get("type") == "item.completed" and item.get("type") == "command_execution":
            commands.append({k: item.get(k) for k in ("command", "exit_code", "aggregated_output")})
    return commands


def bug_oracle(root: Path) -> dict[str, bool]:
    checks = {}
    for name in ("Ada", "Ada Lovelace", "Grace Hopper", "李 明"):
        result = harness.run_command(["python3", "greet.py", name], cwd=root)
        checks[f"cli:{name}"] = result.returncode == 0 and result.stdout.strip() == f"Hello, {name}!"
    result = harness.run_command(["make", "verify"], cwd=root)
    checks["native_gate"] = result.returncode == 0
    # A green native gate alone cannot pass the independent CLI examples above.
    return checks


def load_cases(path: Path) -> list[dict]:
    cases = json.loads(path.read_text())
    if not isinstance(cases, list) or not 1 <= len(cases) <= 7:
        raise ValueError("provide one to seven tasks")
    seen = set()
    for case in cases:
        import re
        name = case.get("id", "")
        if not re.fullmatch(r"[a-z][a-z0-9-]*", name) or name in seen:
            raise ValueError("task ids must be unique slugs")
        seen.add(name)
        if not isinstance(case.get("prompt"), str) or not case["prompt"].strip():
            raise ValueError("task needs an organic prompt")
        rubric = case.get("rubric", [])
        if not 3 <= len(rubric) <= 6 or any(not isinstance(c, str) or not c.strip() for c in rubric):
            raise ValueError("task needs three to six observer-only criteria")
        if case.get("oracle") not in {"unchanged", "greeting"}:
            raise ValueError("unknown observable outcome")
    return cases


def skill_grants(values: list[str], cases: list[dict]) -> dict[str, str]:
    result = {}
    for value in values:
        case, separator, relative = value.partition("=")
        if (not separator or case not in {item["id"] for item in cases} or case in result
                or not re.fullmatch(r"\.agents/skills/[a-z][a-z0-9-]*", relative)):
            raise ValueError("grant must name a selected case and one .agents/skills/<slug> directory")
        result[case] = relative
    return result


def skill_policy(repo: Path, relative: str) -> dict:
    if not re.fullmatch(r"\.agents/skills/[a-z][a-z0-9-]*", relative):
        raise ValueError("invalid fixture skill directory")
    repo = repo.resolve()
    target = repo
    for part in Path(relative).parts:
        target = target / part
        if target.is_symlink():
            raise ValueError("fixture grant cannot traverse a symlink")
    target.mkdir(parents=True, exist_ok=True)
    return {"type": "workspaceWrite", "writableRoots": [str(target)], "networkAccess": False,
            "excludeSlashTmp": False, "excludeTmpdirEnvVar": False}


def skill_arguments(policy: dict) -> list[str]:
    return ["--config", 'sandbox_mode="workspace-write"',
            "--config", "sandbox_workspace_write.writable_roots=" + json.dumps(policy["writableRoots"]),
            "--config", "sandbox_workspace_write.network_access=false",
            "--config", "sandbox_workspace_write.exclude_slash_tmp=false",
            "--config", "sandbox_workspace_write.exclude_tmpdir_env_var=false"]


def sandbox_request(binary: str, request: dict, *, repo: Path, env: dict, artifact: Path) -> dict:
    """One bounded non-model app-server request; preserve protocol even on failure."""
    with (artifact / "preflight-server-stderr.txt").open("w") as stderr, \
         (artifact / "preflight-protocol.jsonl").open("w") as transcript:
        process = subprocess.Popen([binary, *skill_arguments(request["params"]["sandboxPolicy"]),
                                    "app-server", "--stdio"], cwd=repo, env=env,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr)
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        buffered = b""
        def send(value):
            transcript.write(json.dumps({"sent": value}) + "\n"); transcript.flush()
            process.stdin.write(json.dumps(value).encode() + b"\n"); process.stdin.flush()
        def receive(identity):
            nonlocal buffered
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if b"\n" not in buffered:
                    if not selector.select(min(1, max(0, deadline - time.monotonic()))):
                        continue
                    chunk = os.read(process.stdout.fileno(), 65536)
                    if not chunk:
                        raise ValueError("preflight server closed before response")
                    buffered += chunk
                    if len(buffered) > 1024 * 1024:
                        raise ValueError("preflight protocol response too large")
                    continue
                line, buffered = buffered.split(b"\n", 1)
                transcript.write(line.decode() + "\n"); transcript.flush()
                value = json.loads(line)
                if value.get("id") == identity:
                    if "error" in value or "result" not in value:
                        raise ValueError("preflight API rejected request")
                    return value["result"]
            raise ValueError("preflight API timed out")
        try:
            send({"id": 1, "method": "initialize", "params": {
                "clientInfo": {"name": "tugling_fixture_preflight", "version": "1"}}})
            initialized = receive(1)
            package.write_json(artifact / "preflight-initialize.json", initialized)
            send({"method": "initialized", "params": {}})
            send(request)
            return receive(2)
        finally:
            selector.close()
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait()
            process.stdin.close(); process.stdout.close()


def skill_preflight(binary: str, policy: dict, *, repo: Path, home: Path, env: dict, artifact: Path) -> None:
    nonce = ".tugling-preflight-" + uuid.uuid4().hex
    paths = {"target": str(Path(policy["writableRoots"][0]) / nonce),
             "protected_sibling": str(repo / ".agents" / nonce),
             "outside": str(Path.home() / nonce)}
    # The probe itself, including cleanup, runs only inside the requested sandbox.
    probe = """import errno,json,pathlib,sys
paths=json.loads(sys.argv[1]); results={}
for name,filename in paths.items():
 path=pathlib.Path(filename)
 try:
  stream=path.open('x')
 except OSError as error:
  results[name]={'written':False,'errno':error.errno}
 else:
  try:
   with stream: stream.write('fixture-only sandbox probe')
   results[name]={'written':True,'readback':path.read_text()=='fixture-only sandbox probe'}
  finally: path.unlink()
print(json.dumps(results,sort_keys=True))
"""
    request = {"id": 2, "method": "command/exec", "params": {
        "command": [sys.executable, "-c", probe, json.dumps(paths)], "cwd": str(repo),
        "timeoutMs": 10000, "sandboxPolicy": policy}}
    package.write_json(artifact / "preflight-request.json", request)
    config = (home / "config.toml").read_bytes()
    package.write_json(artifact / "preflight-provenance.json", {
        "binary": binary, "cwd": str(repo), "codex_home": str(home), "model_calls": 0,
        "config_sha256": hashlib.sha256(config).hexdigest(), "requested_policy": policy,
        "builder_extra_arguments": skill_arguments(policy)})
    try:
        rendered = subprocess.run([binary, *skill_arguments(policy), "debug", "prompt-input"],
                                  cwd=repo, env=env, capture_output=True, text=True, timeout=20)
        # Retain build-local resolved environment, not unrelated prompt instructions.
        contexts = []
        if rendered.returncode == 0:
            for item in json.loads(rendered.stdout):
                for part in item.get("content", []):
                    text = part.get("text", "")
                    if "<environment_context>" in text:
                        contexts.append(text)
        package.write_json(artifact / "preflight-resolved-environment.json", {
            "exit_code": rendered.returncode, "stderr": rendered.stderr, "contexts": contexts})
        if rendered.returncode != 0 or len(contexts) != 1:
            raise ValueError("cannot retain build-local sandbox configuration resolution")
        match = re.search(r"<filesystem>.*?</filesystem>", contexts[0], re.DOTALL)
        if not match:
            raise ValueError("resolved environment lacks filesystem policy")
        filesystem = ET.fromstring(match.group())
        entries = filesystem.findall("./permission_profile/file_system/entry")
        writes = {entry.findtext("path") for entry in entries
                  if entry.get("access") == "write" and entry.find("path") is not None}
        reads = {entry.findtext("path") for entry in entries if entry.get("access") == "read"}
        special_writes = {entry.findtext("special") for entry in entries
                          if entry.get("access") == "write" and entry.find("special") is not None}
        if (writes != {str(repo.resolve()), policy["writableRoots"][0]}
                or str(repo.resolve() / ".agents") not in reads
                or special_writes - {":tmpdir", ":slash_tmp"}):
            raise ValueError("resolved sandbox scope differs from fixture policy")
        response = sandbox_request(binary, request, repo=repo, env=env, artifact=artifact)
        package.write_json(artifact / "preflight-result.json", response)
        if response.get("exitCode") != 0 or response.get("stderr"):
            raise ValueError("sandbox preflight command failed")
        result = json.loads(response["stdout"])
        if (set(result) != set(paths) or result["target"] != {"written": True, "readback": True}
                or any(result[key].get("written") is not False or result[key].get("errno") not in (1, 13)
                       for key in ("protected_sibling", "outside"))):
            raise ValueError("sandbox preflight did not prove narrow fixture access")
        if (home / "config.toml").read_bytes() != config:
            raise ValueError("sandbox preflight changed isolated configuration")
    except Exception as error:
        package.write_json(artifact / "preflight-failure.json", {"error": str(error)})
        raise


def run_case(case: dict, args, binary: str, marketplace: Path) -> dict:
    artifact = args.out / case["id"]
    artifact.mkdir()
    # The builder sees only project-shaped paths. Observer files and other
    # deliveries are never placed in its working directory or supplied prompt.
    with tempfile.TemporaryDirectory(prefix="greeting-") as directory:
        live = Path(directory)
        repo = live / "greeting-cli"
        try:
            return observe_case(case, args, binary, marketplace, artifact, repo, live)
        finally:
            if repo.exists():
                shutil.copytree(repo, artifact / "workspace", symlinks=True)
            package.write_json(artifact / "files.json", snapshot(artifact))


def observe_case(case: dict, args, binary: str, marketplace: Path,
                 artifact: Path, repo: Path, live: Path) -> dict:
    fixture(repo)
    before = snapshot(repo)
    head = harness.git_output(repo, "rev-parse", "HEAD")
    (artifact / "prompt.txt").write_text(case["prompt"] + "\n")
    with tempfile.TemporaryDirectory(prefix="studio-") as directory:
        home = Path(directory) / "home"
        harness.prepare_isolated_codex_home(home)
        env = harness.command_env()
        env.pop("TUGLING_BEHAVIORAL_EVAL", None)
        env["CODEX_HOME"] = str(home)
        installed = install(binary, home, marketplace, env)
        # Codex registers an authorized checkout as trusted at startup. Prepare
        # that same fixture-only entry before comparing settings byte for byte.
        with (home / "config.toml").open("a") as config:
            config.write(f'\n[projects.{json.dumps(str(repo))}]\ntrust_level = "trusted"\n')
        config_before = (home / "config.toml").read_bytes()
        (artifact / "config-before.toml").write_bytes(config_before)
        grant = getattr(args, "skill_directory_grants", {}).get(case["id"])
        extra = []
        if grant:
            if runtime.proxy_arguments():
                raise ValueError("fixture grant preflight requires direct local runtime, not proxy mode")
            policy = skill_policy(repo, grant)
            skill_preflight(binary, policy, repo=repo, home=home,
                            env=runtime.child_environment(env), artifact=artifact)
            extra = skill_arguments(policy)
        argv = [binary, "exec", "--ephemeral", "--ignore-rules", "--json", "--color", "never",
                "--sandbox", "workspace-write", "--cd", str(repo), "--model", args.model,
                "--config", f'model_reasoning_effort="{args.reasoning_effort}"',
                "--config", 'web_search="disabled"',
                "--output-last-message", str(live / "reply.md"), *runtime.proxy_arguments(), *extra,
                case["prompt"]]
        # Keep this fresh home's generated plugin registration. Ignoring user
        # config here would turn a native install check into a different path.
        package.write_json(artifact / "builder-argv.json", argv)
        started = time.monotonic()
        try:
            result = runtime.run_process(argv, cwd=repo, env=runtime.child_environment(env),
                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=args.timeout)
        except subprocess.TimeoutExpired as exc:
            result = subprocess.CompletedProcess(argv, 124,
                exc.stdout.decode() if isinstance(exc.stdout, bytes) else exc.stdout or "",
                exc.stderr.decode() if isinstance(exc.stderr, bytes) else exc.stderr or "")
        (artifact / "events.jsonl").write_text(result.stdout)
        (artifact / "stderr.txt").write_text(result.stderr)
        if (live / "reply.md").is_file() and not (live / "reply.md").is_symlink():
            shutil.copy2(live / "reply.md", artifact / "final.md")
        (artifact / "config-after.toml").write_bytes((home / "config.toml").read_bytes())
        parsed = harness.parse_jsonl(result.stdout)
        commands = completed_commands(result.stdout)
        package.write_json(artifact / "commands.json", commands)
        checks = {
            "exit_zero": result.returncode == 0,
            "final_present": (artifact / "final.md").is_file() and bool((artifact / "final.md").read_text().strip()),
            "same_head": harness.git_output(repo, "rev-parse", "HEAD") == head,
            "settings_unchanged": (home / "config.toml").read_bytes() == config_before,
            "installed_package_unchanged": package.digest_tree(installed) == package.digest_tree(marketplace / package.PLUGIN_RELATIVE),
            "no_cursor_config": not (repo / ".cursor").exists(),
            "no_web_events": not parsed["web_events"],
            "no_symlinks": not any(p.is_symlink() for p in repo.rglob("*")),
        }
        after = snapshot(repo)
        if case["oracle"] == "greeting" and checks["no_symlinks"]:
            checks.update(bug_oracle(repo))
            checks["regression_test_added"] = any(
                name.startswith("tests/") and after.get(name) != before.get(name) for name in after)
            # Run the delivered regression against the original implementation.
            # Merely changing a test file cannot satisfy this check.
            with tempfile.TemporaryDirectory(prefix="greeting-") as directory:
                original = Path(directory) / "cli"
                shutil.copytree(repo, original, symlinks=True)
                (original / "greet.py").write_text(SOURCE)
                result_original = harness.run_command(["make", "verify"], cwd=original)
                checks["regression_rejects_original"] = result_original.returncode != 0
        elif case["oracle"] == "unchanged":
            checks["repository_unchanged"] = before == after
        report = {"id": case["id"], "checks": checks, "automated_checks_passed": all(checks.values()),
                  "rubric": case["rubric"], "usage": parsed["usage"],
                  "prompt_sha256": hashlib.sha256(case["prompt"].encode()).hexdigest(),
                  "initial_files": before,
                  "redactions": [str(repo), str(home), str(live), str(marketplace)],
                  "elapsed_seconds": round(time.monotonic() - started, 2),
                  "command_count": len(commands)}
        package.write_json(artifact / "result.json", report)
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--codex-bin")
    parser.add_argument("--model", required=True)
    parser.add_argument("--reasoning-effort", required=True)
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--skill-directory-grant", action="append", default=[],
                        metavar="CASE=.agents/skills/SLUG")
    parser.add_argument("--cases-file", type=Path, default=CASES)
    parser.add_argument("--package-root", type=Path, default=ROOT,
                        help="marketplace checkout to freeze and install")
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--max-input-tokens", type=int, default=1500000)
    parser.add_argument("--max-output-tokens", type=int, default=60000)
    args = parser.parse_args()
    args.out = args.out.resolve()
    if args.out.is_relative_to(ROOT) or args.out.exists():
        parser.error("use a new private output directory outside the repository")
    if not 30 <= args.timeout <= 600:
        parser.error("timeout must be between 30 and 600 seconds")
    cases = load_cases(args.cases_file)
    if set(args.case) - {case["id"] for case in cases}:
        parser.error("unknown case")
    cases = [case for case in cases if not args.case or case["id"] in args.case]
    args.skill_directory_grants = skill_grants(args.skill_directory_grant, cases)
    budget = runtime.RunBudget(args.max_input_tokens, args.max_output_tokens, len(cases))
    binary, version = package.resolve_codex(args.codex_bin)
    args.out.mkdir(mode=0o700, parents=True)
    summary = {"mode": "local-marketplace-pstack-smoke", "codex_version": version,
               "model": args.model, "reasoning_effort": args.reasoning_effort,
               "package": package.package_report(args.package_root), "results": [],
               "cases": cases, "timeout_seconds": args.timeout,
               "admission_limits": {"input_tokens": args.max_input_tokens,
                                    "output_tokens": args.max_output_tokens, "tasks": len(cases)},
               "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "semantic_review_complete": False, "certification": False}
    with tempfile.TemporaryDirectory(prefix="library-") as directory:
        marketplace = Path(directory)
        (marketplace / package.MARKETPLACE.parent).mkdir(parents=True)
        shutil.copy2(args.package_root / package.MARKETPLACE, marketplace / package.MARKETPLACE)
        shutil.copytree(args.package_root / package.PLUGIN_RELATIVE, marketplace / package.PLUGIN_RELATIVE)
        package.write_json(args.out / "summary.json", summary)
        for case in cases:
            budget.begin()
            result = run_case(case, args, binary, marketplace)
            summary["results"].append(result)
            package.write_json(args.out / "summary.json", summary)
            budget.record(result["usage"])
            summary["usage"] = budget.report()
            package.write_json(args.out / "summary.json", summary)
            print(f"{case['id']}: automated checks {'PASS' if result['automated_checks_passed'] else 'FAIL'}; review required", flush=True)
            if not result["automated_checks_passed"]:
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
