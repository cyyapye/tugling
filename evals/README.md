# Evaluations

`routing.json` records one positive, one negative, and one holdout prompt for every shipped skill. `make verify` checks coverage and schema.

[`behavioral/`](behavioral/README.md) contains seven synthetic, executable cases plus a dependency-free control/treatment runner and deterministic grader. It can also dogfood Tugling against a clean external project checkout while keeping project prompts and results outside this repository.

Routing fixtures make trigger intent reviewable; they do not claim model behavior. Structural checks, live synthetic comparisons, project dogfood, and the full promotion gate are deliberately separate proof levels.
