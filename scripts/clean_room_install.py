#!/usr/bin/env python3
"""Verify Tugling packaging, public marketplace installation, and fresh-task discovery."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE = Path(".agents/plugins/marketplace.json")
PLUGIN_RELATIVE = Path("plugins/tugling")
REVISION_RE = re.compile(r"[0-9a-f]{40}")


class CleanRoomError(RuntimeError):
    """The package or clean-room install did not meet its contract."""


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CleanRoomError(f"{path}: {exc}") from exc


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def digest_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if "__pycache__" in relative.parts:
            continue
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def command_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "NO_COLOR": "1",
            "TUGLING_CLEAN_ROOM": "1",
        }
    )
    if extra:
        env.update(extra)
    return env


def run(
    argv: list[str],
    *,
    cwd: Path,
    timeout: int = 120,
    env: dict[str, str] | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            env=env or command_env(),
            stdin=subprocess.DEVNULL,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CleanRoomError(f"command failed to run: {argv!r}: {exc}") from exc
    if check and completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise CleanRoomError(f"command failed ({completed.returncode}): {argv!r}: {detail[-4000:]}")
    return completed


def resolve_codex(explicit: str | None) -> tuple[str, str]:
    candidates: list[str] = []
    for candidate in (
        explicit,
        os.environ.get("TUGLING_CODEX_BIN"),
        shutil.which("codex"),
        "/Applications/ChatGPT.app/Contents/Resources/codex",
        "/Applications/Codex.app/Contents/Resources/codex",
    ):
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    failures: list[str] = []
    for candidate in candidates:
        path = Path(candidate)
        if not path.is_file() or not os.access(path, os.X_OK):
            failures.append(f"{candidate}: not executable")
            continue
        completed = run([str(path), "--version"], cwd=ROOT, timeout=15)
        if completed.returncode == 0:
            version = (completed.stdout or completed.stderr).strip().splitlines()[-1]
            return str(path), version
        failures.append(f"{candidate}: version probe failed")
    raise CleanRoomError(
        "no usable Codex CLI; pass --codex-bin or TUGLING_CODEX_BIN"
        + (f" ({'; '.join(failures)})" if failures else "")
    )


def package_report(source_root: Path) -> dict[str, Any]:
    source_root = source_root.resolve()
    marketplace_path = source_root / MARKETPLACE
    marketplace = read_json(marketplace_path)
    if not isinstance(marketplace, dict) or set(marketplace) != {"name", "interface", "plugins"}:
        raise CleanRoomError("marketplace root fields are invalid")
    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list) or len(plugins) != 1:
        raise CleanRoomError("marketplace must expose exactly one plugin")
    entry = plugins[0]
    if not isinstance(entry, dict) or entry.get("name") != "tugling":
        raise CleanRoomError("marketplace plugin must be named tugling")
    source = entry.get("source")
    if not isinstance(source, dict) or source != {"source": "local", "path": "./plugins/tugling"}:
        raise CleanRoomError("marketplace must point to ./plugins/tugling")

    plugin_root = (source_root / PLUGIN_RELATIVE).resolve()
    try:
        plugin_root.relative_to(source_root)
    except ValueError as exc:
        raise CleanRoomError("plugin path escapes the marketplace root") from exc
    if not plugin_root.is_dir():
        raise CleanRoomError("plugin directory is missing")
    package_paths = [marketplace_path, *plugin_root.rglob("*")]
    symlinks = [
        path.relative_to(source_root).as_posix()
        for path in package_paths
        if path.is_symlink()
    ]
    if symlinks:
        raise CleanRoomError(f"package must not depend on symlinks: {symlinks}")

    manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
    manifest = read_json(manifest_path)
    if not isinstance(manifest, dict):
        raise CleanRoomError("plugin manifest must be an object")
    if manifest.get("name") != "tugling" or manifest.get("skills") != "./skills/":
        raise CleanRoomError("plugin manifest name or skills path is invalid")
    version = manifest.get("version")
    if not isinstance(version, str) or not re.fullmatch(
        r"(?:0|[1-9]\d*)(?:\.(?:0|[1-9]\d*)){2}", version
    ):
        raise CleanRoomError("plugin version must be semantic x.y.z")

    skills_root = plugin_root / "skills"
    skills = sorted(path.parent.name for path in skills_root.glob("*/SKILL.md"))
    if not skills:
        raise CleanRoomError("plugin contains no skills")
    missing_metadata = [
        skill
        for skill in skills
        if not (skills_root / skill / "agents" / "openai.yaml").is_file()
    ]
    if missing_metadata:
        raise CleanRoomError(f"skills lack UI metadata: {missing_metadata}")
    return {
        "name": "tugling",
        "version": version,
        "content_sha256": digest_tree(plugin_root),
        "skills": skills,
    }


def isolated_package_report(source_root: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="tugling-package-smoke-") as directory:
        clean_root = Path(directory) / "marketplace"
        (clean_root / MARKETPLACE.parent).mkdir(parents=True)
        shutil.copy2(source_root / MARKETPLACE, clean_root / MARKETPLACE)
        shutil.copytree(source_root / PLUGIN_RELATIVE, clean_root / PLUGIN_RELATIVE)
        report = package_report(clean_root)
        report["mode"] = "isolated-package"
        return report


def git_output(root: Path, *args: str) -> str:
    return run(["git", *args], cwd=root, check=True).stdout.strip()


def create_live_fixture(root: Path) -> str:
    root.mkdir(parents=True)
    (root / "AGENTS.md").write_text(
        "# Synthetic fixture instructions\n\n"
        "- Inspect only. Do not edit files.\n"
        "- The canonical verification command is `make verify`.\n"
        "- Report only what current repository evidence proves.\n",
        encoding="utf-8",
    )
    (root / "Makefile").write_text(
        '.PHONY: verify\n\nverify:\n\t@echo "synthetic verification passed"\n',
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        "# Clean-room fixture\n\n"
        "This synthetic repository verifies a freshly installed Tugling plugin.\n",
        encoding="utf-8",
    )
    run(["git", "init", "-q"], cwd=root, check=True)
    run(["git", "config", "user.name", "Tugling Clean Room"], cwd=root, check=True)
    run(["git", "config", "user.email", "clean-room@example.invalid"], cwd=root, check=True)
    run(["git", "add", "AGENTS.md", "Makefile", "README.md"], cwd=root, check=True)
    run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-q", "-m", "Synthetic clean-room fixture"],
        cwd=root,
        check=True,
    )
    return git_output(root, "rev-parse", "HEAD")


def write_live_schema(path: Path) -> None:
    write_json(
        path,
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "additionalProperties": False,
            "required": [
                "selected_skill",
                "canonical_verify",
                "verification_order",
                "strongest_proven_state",
                "edited_files",
            ],
            "properties": {
                "selected_skill": {
                    "type": "string",
                    "enum": ["repo-verify", "generic-checklist", "none"],
                },
                "canonical_verify": {
                    "type": "string",
                    "enum": ["make verify", "universal checklist", "unknown"],
                },
                "verification_order": {
                    "type": "string",
                    "enum": ["repository-native-first", "generic-gate-first", "unknown"],
                },
                "strongest_proven_state": {
                    "type": "string",
                    "enum": ["ADVISORY", "LOCAL_PASS", "BLOCKED"],
                },
                "edited_files": {"type": "boolean"},
            },
        },
    )


def parse_events(raw: str) -> dict[str, Any]:
    commands: list[str] = []
    usage = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = event.get("item") if isinstance(event, dict) else None
        if isinstance(item, dict) and item.get("type") == "command_execution":
            command = item.get("command")
            if isinstance(command, str):
                commands.append(command)
        if isinstance(event, dict) and event.get("type") == "turn.completed":
            observed = event.get("usage")
            if isinstance(observed, dict):
                for key in usage:
                    if isinstance(observed.get(key), int):
                        usage[key] = observed[key]
    return {"commands": commands, "usage": usage}


def run_live_discovery(
    *,
    codex_bin: str,
    codex_home: Path,
    auth_home: Path,
    installed_plugin: Path,
    model: str,
    reasoning_effort: str,
    timeout: int,
    scratch: Path,
) -> tuple[dict[str, Any], dict[str, bool]]:
    auth_source = auth_home / "auth.json"
    if auth_source.is_file():
        auth_destination = codex_home / "auth.json"
        shutil.copy2(auth_source, auth_destination)
        auth_destination.chmod(0o600)
    elif not os.environ.get("OPENAI_API_KEY"):
        raise CleanRoomError(f"Codex authentication not found at {auth_source}")

    fixture = scratch / "fixture"
    baseline_head = create_live_fixture(fixture)
    schema = scratch / "live-output.schema.json"
    final_path = scratch / "live-final.json"
    write_live_schema(schema)
    prompt = (
        "Use $repo-verify to inspect this synthetic repository read-only. "
        "Confirm the canonical verification command, but do not run it and do not edit files. "
        "Return the strongest state supported before verification runs."
    )
    argv = [
        codex_bin,
        "exec",
        "--ephemeral",
        "--json",
        "--color",
        "never",
        "--sandbox",
        "read-only",
        "--cd",
        str(fixture),
        "--model",
        model,
        "--config",
        f'model_reasoning_effort="{reasoning_effort}"',
        "--output-schema",
        str(schema),
        "--output-last-message",
        str(final_path),
        prompt,
    ]
    started = time.perf_counter()
    completed = run(
        argv,
        cwd=fixture,
        timeout=timeout,
        env=command_env({"CODEX_HOME": str(codex_home)}),
    )
    elapsed = round(time.perf_counter() - started, 3)
    events = parse_events(completed.stdout)
    final = read_json(final_path) if final_path.is_file() else None
    expected = {
        "selected_skill": "repo-verify",
        "canonical_verify": "make verify",
        "verification_order": "repository-native-first",
        "strongest_proven_state": "BLOCKED",
        "edited_files": False,
    }
    final_head = git_output(fixture, "rev-parse", "HEAD")
    status = git_output(fixture, "status", "--porcelain", "--untracked-files=all")
    installed_skill = installed_plugin / "skills" / "repo-verify" / "SKILL.md"
    skill_read = any(str(installed_skill) in command for command in events["commands"])
    native_ran = any(re.search(r"(^|\s)make\s+verify(\s|$)", command) for command in events["commands"])
    checks = {
        "live_exit_zero": completed.returncode == 0,
        "live_skill_contract": final == expected,
        "live_repository_unchanged": baseline_head == final_head and not status,
        "live_native_gate_not_run": not native_ran,
    }
    return (
        {
            "ran": True,
            "model": model,
            "reasoning_effort": reasoning_effort,
            "elapsed_seconds": elapsed,
            "usage": events["usage"],
            "selected_skill": final.get("selected_skill") if isinstance(final, dict) else None,
            "canonical_verify": final.get("canonical_verify") if isinstance(final, dict) else None,
            "verification_order": (
                final.get("verification_order") if isinstance(final, dict) else None
            ),
            "strongest_proven_state": (
                final.get("strongest_proven_state") if isinstance(final, dict) else None
            ),
            "installed_skill_read_observed": skill_read,
            "repository_unchanged": baseline_head == final_head and not status,
        },
        checks,
    )


def public_install(
    *,
    source: str,
    ref: str,
    expected_root: Path,
    codex_bin: str,
    codex_version: str,
    auth_home: Path,
    live: bool,
    model: str,
    reasoning_effort: str,
    timeout: int,
) -> dict[str, Any]:
    if not REVISION_RE.fullmatch(ref):
        raise CleanRoomError("--ref must be a full 40-character commit SHA")
    expected = package_report(expected_root)
    with tempfile.TemporaryDirectory(prefix="tugling-public-install-") as directory:
        scratch = Path(directory)
        codex_home = scratch / "codex-home"
        codex_home.mkdir(mode=0o700)
        env = command_env({"CODEX_HOME": str(codex_home)})
        added = run(
            [codex_bin, "plugin", "marketplace", "add", source, "--ref", ref],
            cwd=scratch,
            timeout=timeout,
            env=env,
        )
        marketplace_root = codex_home / ".tmp" / "marketplaces" / "tugling"
        resolved = (
            git_output(marketplace_root, "rev-parse", "HEAD")
            if marketplace_root.is_dir()
            else None
        )
        installed = run(
            [codex_bin, "plugin", "add", "tugling@tugling", "--json"],
            cwd=scratch,
            timeout=timeout,
            env=env,
        )
        try:
            install_value = json.loads(installed.stdout)
        except json.JSONDecodeError as exc:
            raise CleanRoomError(f"Codex plugin install did not return JSON: {exc}") from exc
        installed_path_value = install_value.get("installedPath")
        installed_path = Path(installed_path_value) if isinstance(installed_path_value, str) else Path()
        installed_inside_home = False
        if installed_path_value:
            try:
                installed_path.resolve().relative_to(codex_home.resolve())
                installed_inside_home = True
            except ValueError:
                installed_inside_home = False
        installed_report = package_report(marketplace_root) if marketplace_root.is_dir() else None
        installed_plugin_report = (
            {
                "name": read_json(installed_path / ".codex-plugin" / "plugin.json").get("name"),
                "version": read_json(installed_path / ".codex-plugin" / "plugin.json").get("version"),
                "content_sha256": digest_tree(installed_path),
                "skills": sorted(
                    path.parent.name for path in (installed_path / "skills").glob("*/SKILL.md")
                ),
            }
            if installed_path.is_dir()
            else None
        )
        checks = {
            "marketplace_add": added.returncode == 0,
            "plugin_add": installed.returncode == 0,
            "exact_public_revision": resolved == ref,
            "isolated_install_path": installed_inside_home,
            "marketplace_package_matches_candidate": installed_report == expected,
            "installed_plugin_matches_candidate": installed_plugin_report == expected,
        }
        live_report: dict[str, Any] = {"ran": False}
        if live and installed_path.is_dir():
            live_report, live_checks = run_live_discovery(
                codex_bin=codex_bin,
                codex_home=codex_home,
                auth_home=auth_home,
                installed_plugin=installed_path,
                model=model,
                reasoning_effort=reasoning_effort,
                timeout=timeout,
                scratch=scratch,
            )
            checks.update(live_checks)
        proof = {
            "schema_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "passed": all(checks.values()),
            "mode": "public-cli-live" if live else "public-cli",
            "source": {
                "repository": source,
                "requested_revision": ref,
                "resolved_revision": resolved,
            },
            "codex": {"version": codex_version},
            "plugin": expected,
            "live": live_report,
            "checks": checks,
        }
        return proof


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="run the dependency-free package smoke")
    validate.add_argument("--source-root", default=str(ROOT))
    validate.add_argument("--json", action="store_true")

    public = subparsers.add_parser("public", help="install an exact public Git revision")
    public.add_argument("--source", default="cyyapye/tugling")
    public.add_argument("--ref", required=True)
    public.add_argument("--expected-root", default=str(ROOT))
    public.add_argument("--codex-bin")
    public.add_argument("--auth-home", default=os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    public.add_argument("--live", action="store_true")
    public.add_argument("--model", default="gpt-5.4-mini")
    public.add_argument(
        "--reasoning-effort",
        choices=("low", "medium", "high", "xhigh"),
        default="medium",
    )
    public.add_argument("--timeout", type=int, default=900)
    public.add_argument("--out")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        if args.command == "validate":
            report = isolated_package_report(Path(args.source_root))
            if args.json:
                print(json.dumps(report, indent=2, sort_keys=True))
            else:
                print(
                    f"Tugling clean package passed: {report['version']}, "
                    f"{len(report['skills'])} discoverable skills."
                )
            return 0
        if args.timeout < 30:
            raise CleanRoomError("--timeout must be at least 30 seconds")
        codex_bin, codex_version = resolve_codex(args.codex_bin)
        proof = public_install(
            source=args.source,
            ref=args.ref,
            expected_root=Path(args.expected_root),
            codex_bin=codex_bin,
            codex_version=codex_version,
            auth_home=Path(args.auth_home),
            live=args.live,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            timeout=args.timeout,
        )
        if args.out:
            output = Path(args.out).resolve()
            write_json(output, proof)
            print(f"proof: {output}")
        else:
            print(json.dumps(proof, indent=2, sort_keys=True))
        return 0 if proof["passed"] else 2
    except CleanRoomError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
