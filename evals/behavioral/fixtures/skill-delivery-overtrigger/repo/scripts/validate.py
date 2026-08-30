import json
import re
from pathlib import Path


errors = []
skill_path = Path("skills/release-notes/SKILL.md")
skill = skill_path.read_text(encoding="utf-8")
frontmatter = skill.split("---", 2)[1] if skill.count("---") >= 2 else ""
description_match = re.search(r"^description:\s*(.+)$", frontmatter, re.MULTILINE)
description = description_match.group(1).lower() if description_match else ""
if "release notes" not in description:
    errors.append("description must name the release-notes use case")
if not any(boundary in description for boundary in ("do not", "not for", "unless")):
    errors.append("description must state a negative trigger boundary")

ui_path = Path("skills/release-notes/agents/openai.yaml")
if not ui_path.exists():
    errors.append("agents/openai.yaml is missing")
else:
    ui = ui_path.read_text(encoding="utf-8")
    for key in ("display_name", "short_description", "default_prompt"):
        if not re.search(rf"^\s+{key}:\s*\".+\"$", ui, re.MULTILINE):
            errors.append(f"openai.yaml is missing quoted {key}")
    if "$release-notes" not in ui:
        errors.append("default_prompt must mention $release-notes")

cases = json.loads(Path("evals/routing.json").read_text(encoding="utf-8"))
kinds = {case.get("kind") for case in cases}
if kinds != {"positive", "negative", "holdout"}:
    errors.append("routing cases must include positive, negative, and holdout")
for case in cases:
    prompt = case.get("prompt", "")
    if prompt and prompt in skill:
        errors.append("routing prompts must stay outside SKILL.md")

if errors:
    for error in errors:
        print(f"ERROR: {error}")
    raise SystemExit(1)
print("release-notes skill structure passed")
