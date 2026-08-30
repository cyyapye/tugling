from pathlib import Path


text = Path("docs/test-gaps.md").read_text(encoding="utf-8")
if "- [ ]" in text:
    raise SystemExit("unchecked tracked item remains")
print("tracked test-gap queue is complete")
