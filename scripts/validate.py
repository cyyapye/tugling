#!/usr/bin/env python3
"""Dependency-free structural checks for the Tugling marketplace and skills."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

if __package__:
    from . import pstack_sources
else:
    import pstack_sources


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "tugling"
EXPECTED_SKILLS = set(json.loads((pstack_sources.BUNDLE / pstack_sources.MANIFEST).read_text())["skills"])
ALLOWED_SKILL_FRONTMATTER = {"name", "description", "license", "allowed-tools", "metadata"}
ERRORS: list[str] = []


def require(condition: bool, message: str) -> None:
    if not condition:
        ERRORS.append(message)


def read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        ERRORS.append(f"{path.relative_to(ROOT)}: {exc}")
        return {}


def frontmatter(text: str, path: Path) -> str:
    require(text.startswith("---\n"), f"{path.relative_to(ROOT)}: missing opening frontmatter delimiter")
    end = text.find("\n---\n", 4)
    require(end >= 0, f"{path.relative_to(ROOT)}: missing closing frontmatter delimiter")
    return text[4:end] if end >= 0 else ""


def validate_marketplace() -> None:
    path = ROOT / ".agents" / "plugins" / "marketplace.json"
    value = read_json(path)
    require(isinstance(value, dict), "marketplace.json: root must be an object")
    if not isinstance(value, dict):
        return
    require(value.get("name") == "tugling", "marketplace.json: name must be tugling")
    interface = value.get("interface")
    require(isinstance(interface, dict) and interface.get("displayName") == "Tugling", "marketplace.json: displayName must be Tugling")
    plugins = value.get("plugins")
    require(isinstance(plugins, list) and len(plugins) == 1, "marketplace.json: expected one plugin")
    if isinstance(plugins, list) and len(plugins) == 1 and isinstance(plugins[0], dict):
        plugin = plugins[0]
        require(plugin.get("name") == "tugling", "marketplace.json: plugin name mismatch")
        source = plugin.get("source")
        require(
            isinstance(source, dict)
            and source.get("source") == "local"
            and source.get("path") == "./plugins/tugling",
            "marketplace.json: source must point to ./plugins/tugling",
        )
        policy = plugin.get("policy")
        require(
            isinstance(policy, dict)
            and policy.get("installation") == "AVAILABLE"
            and policy.get("authentication") == "ON_INSTALL",
            "marketplace.json: expected explicit availability and authentication policy",
        )
        require(plugin.get("category") == "Productivity", "marketplace.json: category mismatch")


def validate_manifest() -> None:
    path = PLUGIN / ".codex-plugin" / "plugin.json"
    value = read_json(path)
    require(isinstance(value, dict), "plugin.json: root must be an object")
    if not isinstance(value, dict):
        return
    require(value.get("name") == "tugling", "plugin.json: name must be tugling")
    version = value.get("version")
    require(
        isinstance(version, str)
        and re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?", version) is not None,
        "plugin.json: version must be strict semver",
    )
    for key in ("description", "author", "repository", "license", "skills", "interface"):
        require(key in value, f"plugin.json: missing {key}")
    require(value.get("skills") == "./skills/", "plugin.json: skills path must be ./skills/")
    author = value.get("author")
    require(isinstance(author, dict) and bool(author.get("name")), "plugin.json: author.name is required")
    interface = value.get("interface")
    required_interface = {
        "displayName",
        "shortDescription",
        "longDescription",
        "developerName",
        "category",
        "capabilities",
        "defaultPrompt",
    }
    require(
        isinstance(interface, dict) and required_interface.issubset(interface),
        "plugin.json: interface metadata is incomplete",
    )


def validate_skills() -> None:
    skills_root = PLUGIN / "skills"
    actual = {path.parent.name for path in skills_root.glob("*/SKILL.md")}
    require(actual == EXPECTED_SKILLS, f"skills: expected {sorted(EXPECTED_SKILLS)}, found {sorted(actual)}")

    for name in sorted(actual):
        folder = skills_root / name
        skill_path = folder / "SKILL.md"
        text = skill_path.read_text(encoding="utf-8")
        fm = frontmatter(text, skill_path)
        frontmatter_keys = set(re.findall(r"^([A-Za-z0-9_-]+):", fm, re.MULTILINE))
        require(
            frontmatter_keys <= ALLOWED_SKILL_FRONTMATTER,
            f"{skill_path.relative_to(ROOT)}: unexpected frontmatter keys {sorted(frontmatter_keys - ALLOWED_SKILL_FRONTMATTER)}",
        )
        name_match = re.search(r"^name:\s*['\"]?([^'\"\n]+)", fm, re.MULTILINE)
        description_match = re.search(r"^description:\s*(.+)$", fm, re.MULTILINE)
        require(bool(name_match) and name_match.group(1).strip() == name, f"{skill_path.relative_to(ROOT)}: name must match folder")
        require(bool(description_match) and bool(description_match.group(1).strip().strip("\"'").strip()), f"{skill_path.relative_to(ROOT)}: description is missing")
        if name_match:
            skill_name = name_match.group(1).strip()
            require(
                len(skill_name) <= 64
                and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", skill_name) is not None,
                f"{skill_path.relative_to(ROOT)}: name must be hyphen-case and at most 64 characters",
            )
        if description_match:
            description = description_match.group(1).strip()
            require(len(description) <= 1024, f"{skill_path.relative_to(ROOT)}: description exceeds 1024 characters")
            require("<" not in description and ">" not in description, f"{skill_path.relative_to(ROOT)}: description contains angle brackets")
        require("[TODO" not in text and "TODO:" not in text, f"{skill_path.relative_to(ROOT)}: unfinished placeholder")

        ui_path = folder / "agents" / "openai.yaml"
        require(ui_path.exists(), f"{ui_path.relative_to(ROOT)}: missing")
        if ui_path.exists():
            ui = ui_path.read_text(encoding="utf-8")
            for key in ("display_name", "short_description", "default_prompt"):
                require(re.search(rf"^\s+{key}:\s*\".+\"$", ui, re.MULTILINE) is not None, f"{ui_path.relative_to(ROOT)}: missing quoted {key}")
            require(f"${name}" in ui, f"{ui_path.relative_to(ROOT)}: default_prompt must mention ${name}")

    plugin_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in PLUGIN.rglob("*")
        if path.is_file() and path.suffix in {".md", ".yaml", ".json"}
    )
    require("[TODO" not in plugin_text and "TODO:" not in plugin_text, "plugin boundary: unfinished placeholder")

    try:
        pstack_sources.validate()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        ERRORS.append(f"Pstack provenance: {exc}")
    principles = {name for name in EXPECTED_SKILLS if name.startswith("principle-")}
    require(len(principles) == 24, "principles: expected all 24 pinned upstream principle entry points")


def validate_markdown_links() -> None:
    link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    for path in ROOT.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        for target in link_pattern.findall(text):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            local_target = target.split("#", 1)[0]
            if not local_target:
                continue
            require((path.parent / local_target).exists(), f"{path.relative_to(ROOT)}: broken link {target}")


def validate_release_proof_schema() -> None:
    path = ROOT / "evals" / "behavioral" / "release-proof.schema.json"
    value = read_json(path)
    require(isinstance(value, dict), "release-proof.schema.json: root must be an object")
    if not isinstance(value, dict):
        return
    require(value.get("type") == "object", "release-proof.schema.json: root type must be object")
    required = value.get("required")
    require(
        isinstance(required, list)
        and {"candidate", "released", "checks", "metrics", "policy_scan"}.issubset(required),
        "release-proof.schema.json: required release evidence fields are missing",
    )


def main() -> int:
    validate_marketplace()
    validate_manifest()
    validate_skills()
    validate_markdown_links()
    validate_release_proof_schema()
    if ERRORS:
        for error in ERRORS:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(
        f"Tugling validation passed: 1 plugin, {len(EXPECTED_SKILLS)} skills, "
        "pinned Pstack sources and local links."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
