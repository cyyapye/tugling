#!/usr/bin/env python3
"""Independent functional oracle for the synthetic offline greeting project."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
from pathlib import Path
import py_compile
import shutil
import subprocess
import tempfile
import tomllib


def command(root: Path, argv: list[str]) -> str:
    result = subprocess.run(argv, cwd=root, text=True, capture_output=True, timeout=30, check=False)
    if result.returncode:
        raise AssertionError(f"{argv!r} failed: {result.stderr[-2000:]} {result.stdout[-2000:]}")
    return result.stdout


def source_files(root: Path) -> list[Path]:
    names = command(root, ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"])
    files = []
    for name in sorted(set(names.split("\0")) - {""}):
        path = root / name
        if path.is_symlink() or root.resolve() not in path.resolve().parents:
            raise AssertionError("source snapshots require regular in-repository files")
        if path.is_file():
            files.append(Path(name))
    return files


def hashes(root: Path, files: list[Path]) -> dict[str, str]:
    return {str(path): hashlib.sha256((root / path).read_bytes()).hexdigest() for path in files}


def check(root: Path, environment_file: str = ".codex/environments/environment.toml") -> None:
    files = source_files(root)
    for required in ("AGENTS.md", "Makefile", ".gitignore", environment_file):
        if Path(required) not in files:
            raise AssertionError(f"missing intended source: {required}")
    # Copy intended source only. Ignored dependencies cannot make this check pass.
    with tempfile.TemporaryDirectory(prefix="tugling-bootstrap-oracle-") as directory:
        fresh = Path(directory).resolve() / "fresh"
        fresh.mkdir()
        for relative in files:
            target = fresh / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / relative, target)
            shutil.copymode(root / relative, target)
        before = hashes(fresh, files)
        sentinel = fresh / "developer-notes.txt"
        sentinel.write_text("Keep this user-owned file.\n", encoding="utf-8")
        command(fresh, ["git", "init", "-q"])
        config = tomllib.loads((fresh / environment_file).read_text())
        setup = config.get("setup", {}).get("script")
        if config.get("version") != 1 or not isinstance(setup, str) or not setup.strip():
            raise AssertionError("local environment needs version 1 and a setup script")
        # A valid-looking config with a no-op setup must not pass. Make its native
        # bootstrap fail in this disposable snapshot and require setup to notice.
        makefile = fresh / "Makefile"
        original_makefile = makefile.read_bytes()
        try:
            with makefile.open("a") as file:
                file.write("\n.PHONY: bootstrap\nbootstrap:\n\t@exit 73\n")
            result = subprocess.run(["sh", "-eu", "-c", setup], cwd=fresh,
                                    capture_output=True, text=True, timeout=30, check=False)
            if result.returncode == 0:
                raise AssertionError("environment setup ignored a failing native bootstrap")
        finally:
            makefile.write_bytes(original_makefile)
        command(fresh, ["sh", "-eu", "-c", setup])
        for _ in range(2):
            command(fresh, ["make", "bootstrap"])
        for name in ("Ada", "Jo Chen"):
            actual = command(fresh, ["python3", "-m", "hello_world", "--name", name]).strip()
            if actual != f"Hello, {name}!":
                raise AssertionError(f"incorrect greeting for {name!r}: {actual!r}")
        command(fresh, ["python3", "-c", "import unittest; s = unittest.defaultTestLoader.discover('tests'); "
                       "assert s.countTestCases() > 0, 'No unittest cases discovered'"])
        command(fresh, ["make", "dev"])
        command(fresh, ["make", "test"])
        command(fresh, ["make", "verify"])
        origin = command(fresh, ["python3", "-c", "import importlib.util; "
                         "s = importlib.util.find_spec('hello_world'); "
                         "print(s.origin or importlib.util.find_spec('hello_world.__main__').origin)"]).strip()
        module = Path(origin).resolve()
        if fresh not in module.parents or module.relative_to(fresh) not in files:
            raise AssertionError("CLI must come from intended project source")
        original_module = module.read_bytes()
        try:
            module.write_bytes(b"raise RuntimeError('synthetic CLI regression')\n" + original_module)
            for target in ("test", "verify"):
                result = subprocess.run(["make", target], cwd=fresh, capture_output=True,
                                        text=True, timeout=30, check=False)
                if result.returncode == 0:
                    raise AssertionError(f"native {target} ignored a broken CLI")
        finally:
            module.write_bytes(original_module)
        owned_cache = Path(importlib.util.cache_from_source(str(module)))
        py_compile.compile(str(module), cfile=str(owned_cache), doraise=True)
        cache_sentinel = owned_cache.parent / "developer-notes.txt"
        cache_sentinel.write_text("Keep this unrelated cache content.\n")
        for _ in range(2):
            command(fresh, ["make", "clean"])
        if owned_cache.exists():
            raise AssertionError("cleanup left known project bytecode")
        if not cache_sentinel.is_file() or cache_sentinel.read_text() != "Keep this unrelated cache content.\n":
            raise AssertionError("cleanup damaged unrelated cache contents")
        if not sentinel.is_file() or sentinel.read_text() != "Keep this user-owned file.\n":
            raise AssertionError("cleanup damaged user-owned files")
        if hashes(fresh, files) != before:
            raise AssertionError("bootstrap or cleanup changed intended source")
        command(fresh, ["make", "bootstrap"])
        command(fresh, ["make", "verify"])
        if hashes(fresh, files) != before:
            raise AssertionError("setup cannot be repeated without changing source")
    print("Fresh-source bootstrap, repeatability, real CLI behavior, native gates, and cleanup passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment-file", choices=(".codex/environments/environment.toml", "codex-environment.toml"),
                        default=".codex/environments/environment.toml")
    args = parser.parse_args()
    check(Path.cwd(), args.environment_file)
