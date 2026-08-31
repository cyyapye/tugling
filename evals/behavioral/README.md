# Behavioral evaluation

This suite asks a narrower question than `make verify`: does installing Tugling
change observable engineering decisions without causing unsafe side effects?

Each case has a synthetic Git repository, a prompt, hidden expected decisions,
and executable invariants. The live runner can create three isolated copies:

- `control`: no Tugling skills are present.
- `released`: skills are materialized from an exact released Git revision.
- `candidate`: the current Tugling skills are exposed from `.agents/skills`.

All conditions receive the same prompt and structured-output schema. Grading
uses the final decisions, the actual Codex JSONL command events, the resulting
Git state, and independent post-run commands. Generated reports also include a
blinded A/B artifact, elapsed time, and token usage. A single run is exploratory
evidence, not a statistically stable model claim.

## CI-safe checks

```bash
make verify
```

This validates case and fixture structure and unit-tests the grader without
calling a model.

## Live smoke

Use an authenticated Codex CLI. Pin the model and reasoning effort so a later
run is comparable:

```bash
python3 scripts/behavioral_eval.py run \
  --case delivery-plan-api-migration \
  --case scale-cost-list-api \
  --case async-safety-webhook \
  --condition both \
  --model gpt-5.4-mini \
  --reasoning-effort medium \
  --require-gate dogfood
```

The runner is opt-in and never runs from `make verify` or the default GitHub
workflow. It uses ephemeral Codex sessions and a private temporary Codex home
that copies authentication but excludes user configuration and global skills.
It also ignores execution-policy files, forbids network use in the prompt, and
grants only the case's declared sandbox. The temporary home is removed with the
run workspace. The runner does not bypass approvals or the sandbox.

The dogfood gate needs at least three no-Tugling/candidate comparisons, no
candidate regressions, no critical candidate failure, and an average candidate
score of at least 85%.

Promotion compares an exact released revision with the candidate and also keeps
the no-Tugling arm as a sanity check. Provide the released ref and an external
policy-pattern file whose contents are never copied into the report:

```bash
python3 scripts/behavioral_eval.py run \
  --case all \
  --condition all \
  --baseline-ref <released-tag-or-full-sha> \
  --policy-pattern-file /path/outside/tugling/public-policy-patterns.txt \
  --model gpt-5.4-mini \
  --reasoning-effort medium \
  --require-gate promotion
```

The promotion proof requires all eight cases, an average candidate score of at
least 90%, measurable improvement over the released version, no candidate
regression, a clean candidate worktree, distinct released/candidate revisions
and plugin content, and passing privacy and configured policy scans. The output
includes `release-proof.json` and `release-proof.md` beside the behavioral
report. The JSON shape is documented by
[`release-proof.schema.json`](release-proof.schema.json).

## External-project dogfood

Keep project-specific prompts and results outside this repository. Point the
same runner at a clean local checkout and an external case file:

```bash
python3 scripts/behavioral_eval.py project \
  --repo /path/to/project \
  --case-file /path/to/project-case.json \
  --condition candidate \
  --model gpt-5.4-mini \
  --reasoning-effort medium
```

The project command clones the checked-out commit into a temporary directory,
adds Tugling only to that clone, and records the exact source revision. It does
not include uncommitted source-repository files.

## What the gates do not prove

- Structural checks do not prove model behavior.
- One no-Tugling/candidate comparison does not prove a durable causal lift.
- Synthetic cases do not replace product-specific acceptance criteria.
- Local model runs do not prove remote checks, merge, deployment, or production
  behavior.

Use repeated runs, blinded review, and project dogfood before making a broad
quality claim or assigning models per skill.
