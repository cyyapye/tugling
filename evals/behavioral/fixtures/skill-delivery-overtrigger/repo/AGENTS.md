# Fixture instructions

- This repository owns one reusable skill under `skills/`.
- A delivered skill needs discriminating frontmatter, concise instructions,
  `agents/openai.yaml`, and positive, negative, and holdout routing cases.
- Keep evaluation prompts outside `SKILL.md`.
- `make verify` is the canonical local gate.
- Do not commit or use the network.
