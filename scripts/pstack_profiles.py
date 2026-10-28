#!/usr/bin/env python3
"""Freeze private Pstack-only and single-extension Codex packages for comparison.

Never edits the shipped plugin. Both packages retain the same Codex mechanics,
upstream playbooks, entry points, metadata and license. Only optional guidance
and its routing are varied. The resulting diff is for operator review.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
from urllib.parse import urlsplit

if __package__:
    from . import pstack_sources as sources, pstack_smoke as smoke
else:
    import pstack_sources as sources
    import pstack_smoke as smoke

EXTENSIONS = "poteto-mode/references/extensions"
ADAPTER = "poteto-mode/references/codex.md"
TRIGGERS = {
    "repo-verify": "For repository readiness, commit content, or changed tests/CI",
    "async-safety": "For queues, webhooks, or workers where ordering and recovery affect durable state",
    "scale-cost-review": "For prospective scale, data-access, or operating-cost risks",
    "screenshot-first-ui": "For existing screen hierarchy, responsive overflow, or misleading affordances",
    "skill-delivery": "For reusable skill authoring, provenance, or routing cases",
}
# Preserve scope translations that share a paragraph with optional guidance.
RETAIN = {
    "architect/SKILL.md": "For a plan-only request, stop at the design and verification plan without changing code.",
    "poteto-mode/playbooks/multi-phase-plan.md": "A plan-only request remains read-only.",
    "poteto-mode/playbooks/authoring-a-skill.md": "Opening a PR requires that action to be in the user's requested scope.",
    ADAPTER: "Use repository-native gates. Preserve user edits and report the strongest state\nactually established. A green local command does not prove commit completeness,\nremote CI, merge, deployment, or certification.",
}


def refresh_manifest(bundle: Path) -> None:
    path = bundle / sources.MANIFEST
    manifest = json.loads(path.read_text())
    for item in manifest["files"]:
        sha = sources.digest(bundle / item["path"])
        if sha != item["sha256"]:
            item["changes"].append("Omit optional Tugling guidance while preserving Codex scope translations.")
            item["sha256"] = sha
    manifest["local_files"] = [dict(item, sha256=sources.digest(bundle / item["path"]))
                                for item in manifest["local_files"] if (bundle / item["path"]).exists()]
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    sources.validate(bundle)


def freeze(source: Path, out: Path, extension: str) -> dict:
    source, out = source.resolve(), out.resolve()
    if extension not in TRIGGERS:
        raise ValueError("unsupported extension profile")
    if out.exists() or out.is_relative_to(smoke.ROOT) or out.is_relative_to(source):
        raise ValueError("use a new private output directory outside the source repository")
    bundle = source / smoke.package.PLUGIN_RELATIVE / "skills"
    sources.validate(bundle)
    source_report = smoke.package.package_report(source)
    out.mkdir(parents=True, mode=0o700)
    base = out / "pstack"
    (base / smoke.package.MARKETPLACE.parent).mkdir(parents=True)
    shutil.copy2(source / smoke.package.MARKETPLACE, base / smoke.package.MARKETPLACE)
    shutil.copytree(source / smoke.package.PLUGIN_RELATIVE, base / smoke.package.PLUGIN_RELATIVE)
    base_skills = base / smoke.package.PLUGIN_RELATIVE / "skills"
    shutil.rmtree(base_skills / EXTENSIONS)
    adapter = base_skills / ADAPTER
    text = adapter.read_text()
    start, end = text.index("## Conditional additions"), text.index("The [source manifest]")
    adapter.write_text(text[:start] + text[end:])
    for path in base_skills.rglob("*.md"):
        relative = path.relative_to(base_skills).as_posix()
        blocks = path.read_text().split("\n\n")
        rendered = []
        for block in blocks:
            if "extensions/" in block and "](" in block:
                if relative in RETAIN:
                    rendered.append(RETAIN[relative])
            elif block != "## Codex additions":
                rendered.append(block)
        path.write_text("\n\n".join(rendered))
    refresh_manifest(base_skills)
    enhanced = out / "enhanced"
    shutil.copytree(base, enhanced)
    target = enhanced / smoke.package.PLUGIN_RELATIVE / "skills"
    needed, pending = set(), [bundle / EXTENSIONS / f"{extension}.md"]
    while pending:
        path = pending.pop().resolve()
        if path in needed:
            continue
        if not path.is_file() or not path.is_relative_to((bundle / EXTENSIONS).resolve()):
            raise ValueError("extension dependency escaped its source directory")
        needed.add(path)
        for link in re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", path.read_text()):
            # Web documentation is a reference, not a local extension to copy.
            if urlsplit(link).scheme or link.startswith("//"):
                continue
            linked = (path.parent / link).resolve()
            if linked.is_relative_to((bundle / EXTENSIONS).resolve()):
                pending.append(linked)
        dest = target / path.relative_to(bundle)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
    with (target / ADAPTER).open("a") as stream:
        stream.write(f"\n{TRIGGERS[extension]}, read [{extension}](extensions/{extension}.md).\n")
    manifest = json.loads((target / sources.MANIFEST).read_text())
    original = json.loads((bundle / sources.MANIFEST).read_text())
    names = {path.relative_to(bundle).as_posix() for path in needed}
    manifest["local_files"].extend(item for item in original["local_files"] if item["path"] in names)
    (target / sources.MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n")
    refresh_manifest(target)
    before, after = smoke.snapshot(base), smoke.snapshot(enhanced)
    changed = sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))
    allowed = {f"plugins/tugling/skills/{name}" for name in names | {ADAPTER, sources.MANIFEST}}
    if set(changed) != allowed:
        raise ValueError("unexpected difference between packages")
    report = {"source": source_report, "extension": extension, "changed_paths": changed,
              "pstack": smoke.package.package_report(base),
              "enhanced": smoke.package.package_report(enhanced), "certification": False}
    smoke.package.write_json(out / "profiles.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=smoke.ROOT)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--extension", choices=TRIGGERS, required=True)
    args = parser.parse_args()
    freeze(args.source, args.out, args.extension)
    print("Private matched packages frozen. Inspect profiles.json and the package diff before running.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
