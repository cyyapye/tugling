#!/usr/bin/env python3
"""Dependency-free structural checks for the Tugling marketplace and skills."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "tugling"
EXPECTED_SKILLS = {
    "async-safety",
    "delivery-plan",
    "repo-verify",
    "scale-cost-review",
    "screenshot-first-ui",
    "skill-delivery",
    "tugling",
}
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
        name_match = re.search(r"^name:\s*['\"]?([^'\"\n]+)", fm, re.MULTILINE)
        description_match = re.search(r"^description:\s*(.+)$", fm, re.MULTILINE)
        require(bool(name_match) and name_match.group(1).strip() == name, f"{skill_path.relative_to(ROOT)}: name must match folder")
        require(bool(description_match) and len(description_match.group(1).strip()) >= 40, f"{skill_path.relative_to(ROOT)}: description is missing or too vague")
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
    for project_name in ("keel",):
        require(project_name not in plugin_text.lower(), f"plugin boundary: found project-specific name {project_name}")
    require("[TODO" not in plugin_text and "TODO:" not in plugin_text, "plugin boundary: unfinished placeholder")

    principles = (skills_root / "tugling" / "references" / "principles.md").read_text(encoding="utf-8")
    headings = re.findall(r"^##\s+\d+\.", principles, re.MULTILINE)
    require(len(headings) == 12, f"principles: expected 12 numbered principles, found {len(headings)}")


def validate_routing_cases() -> None:
    path = ROOT / "evals" / "routing.json"
    value = read_json(path)
    require(isinstance(value, list), "evals/routing.json: root must be an array")
    if not isinstance(value, list):
        return

    seen_ids: set[str] = set()
    coverage = {name: set() for name in EXPECTED_SKILLS}
    for index, case in enumerate(value):
        require(isinstance(case, dict), f"evals/routing.json[{index}]: case must be an object")
        if not isinstance(case, dict):
            continue
        case_id = case.get("id")
        skill = case.get("skill")
        kind = case.get("kind")
        prompt = case.get("prompt")
        should_trigger = case.get("should_trigger")
        require(isinstance(case_id, str) and case_id not in seen_ids, f"evals/routing.json[{index}]: id must be unique")
        if isinstance(case_id, str):
            seen_ids.add(case_id)
        require(skill in EXPECTED_SKILLS, f"evals/routing.json[{index}]: unknown skill {skill}")
        require(kind in {"positive", "negative", "holdout"}, f"evals/routing.json[{index}]: invalid kind")
        require(isinstance(prompt, str) and len(prompt) >= 20, f"evals/routing.json[{index}]: prompt is too short")
        require(isinstance(should_trigger, bool), f"evals/routing.json[{index}]: should_trigger must be boolean")
        if skill in coverage and kind in {"positive", "negative", "holdout"}:
            coverage[skill].add(kind)
    for skill, kinds in sorted(coverage.items()):
        require(kinds == {"positive", "negative", "holdout"}, f"evals/routing.json: {skill} lacks positive, negative, or holdout coverage")


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


def main() -> int:
    validate_marketplace()
    validate_manifest()
    validate_skills()
    validate_routing_cases()
    validate_markdown_links()
    if ERRORS:
        for error in ERRORS:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"Tugling validation passed: 1 plugin, {len(EXPECTED_SKILLS)} skills, 12 principles, 21 routing cases.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
