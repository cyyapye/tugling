#!/usr/bin/env python3
"""Check the bundled Pstack inventory and provenance without network or model calls."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "plugins/tugling/skills"
MANIFEST = "poteto-mode/references/upstream/sources.json"
LICENSE = "poteto-mode/references/upstream/LICENSE"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_path(root: Path, value: str) -> Path:
    relative = PurePosixPath(value)
    if not value or relative.is_absolute() or ".." in relative.parts or "\\" in value:
        raise ValueError(f"invalid source path: {value!r}")
    path = root / value
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"missing or unsafe source file: {value}")
    return path


def validate(bundle: Path = BUNDLE, upstream_root: Path | None = None) -> int:
    manifest = json.loads((bundle / MANIFEST).read_text())
    if manifest.get("schema_version") != 2 or manifest.get("license") != "MIT":
        raise ValueError("unsupported Pstack source manifest")
    if manifest.get("repository") != "https://github.com/cursor/plugins":
        raise ValueError("unexpected Pstack source repository")
    revision = manifest.get("revision", "")
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Pstack source revision must be a full SHA")
    if upstream_root is not None:
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=upstream_root, text=True
        ).strip()
        if head != revision:
            raise ValueError("upstream checkout does not match the pinned revision")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("Pstack source inventory is empty")
    seen: set[str] = set()
    sources: set[str] = set()
    for item in files:
        name, source = item["path"], item["upstream_path"]
        if name in seen or source in sources:
            raise ValueError(f"duplicate Pstack source entry: {name}")
        seen.add(name)
        sources.add(source)
        if not source.startswith("pstack/") or ".." in PurePosixPath(source).parts:
            raise ValueError(f"invalid upstream path: {source}")
        for field in ("sha256", "upstream_sha256"):
            if not re.fullmatch(r"[0-9a-f]{64}", item.get(field, "")):
                raise ValueError(f"invalid {field}: {name}")
        changes = item.get("changes")
        if not isinstance(changes, list) or any(not isinstance(c, str) or not c.strip() for c in changes):
            raise ValueError(f"invalid adaptation record: {name}")
        if item["sha256"] != item["upstream_sha256"] and not changes:
            raise ValueError(f"undocumented adaptation: {name}")
        if digest(safe_path(bundle, name)) != item["sha256"]:
            raise ValueError(f"bundled source hash mismatch: {name}")
        if upstream_root is not None and digest(safe_path(upstream_root, source)) != item["upstream_sha256"]:
            raise ValueError(f"upstream source hash mismatch: {source}")
        if name == LICENSE and (source != "pstack/LICENSE" or changes or item["sha256"] != item["upstream_sha256"]):
            raise ValueError("Pstack license must be an unchanged upstream copy")
    copied_skills = sorted(Path(item["path"]).parent.name for item in files if item["path"].endswith("/SKILL.md"))
    actual_skills = sorted(path.parent.name for path in bundle.glob("*/SKILL.md"))
    if manifest.get("skills") != copied_skills or actual_skills != copied_skills:
        raise ValueError("Pstack entry points must match the attributed upstream catalog")
    local_files = manifest.get("local_files")
    if not isinstance(local_files, list):
        raise ValueError("missing Codex adaptation inventory")
    for item in local_files:
        name = item["path"]
        if name in seen:
            raise ValueError(f"duplicate local source entry: {name}")
        seen.add(name)
        if digest(safe_path(bundle, name)) != item.get("sha256"):
            raise ValueError(f"local adaptation hash mismatch: {name}")
    actual = {p.relative_to(bundle).as_posix() for p in bundle.rglob("*") if p.is_file() or p.is_symlink()}
    if actual != seen | {MANIFEST} or LICENSE not in seen:
        raise ValueError("Pstack inventory must cover every bundled file and its license")
    return len(files)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-root", type=Path)
    args = parser.parse_args()
    try:
        count = validate(upstream_root=args.upstream_root)
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Pstack provenance failed: {exc}\n")
    print(f"Pstack provenance passed: {count} files, pinned source and full license")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
