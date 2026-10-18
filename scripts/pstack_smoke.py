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
        argv = [binary, "exec", "--ephemeral", "--ignore-rules", "--json", "--color", "never",
                "--sandbox", "workspace-write", "--cd", str(repo), "--model", args.model,
                "--config", f'model_reasoning_effort="{args.reasoning_effort}"',
                "--config", 'web_search="disabled"',
                "--output-last-message", str(live / "reply.md"), *runtime.proxy_arguments(),
                case["prompt"]]
        # Keep this fresh home's generated plugin registration. Ignoring user
        # config here would turn a native install check into a different path.
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
