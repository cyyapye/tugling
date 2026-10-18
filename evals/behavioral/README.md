# Legacy behavioral diagnostics

New skill development follows the attributed [Pstack evaluation method](../pstack/method.md).
This older runner explicitly tells the model it is being evaluated and asks for
predefined decisions. Its scores are diagnostic history, not blinded Pstack
behavioral evidence or proof of an advantage over Pstack. The fixtures, executable
invariants and historical comparison matrix remain supported for diagnostics; this
transition does not regrade historical runs or update approved controller pins.

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

Required command groups are shared criteria: their source files and commands
must be available in every compared condition. Do not require a no-Tugling
control to read an uninstalled skill. Record installed-skill discovery separately
from the common project-source inspection and decision checks. If a grading
defect is found, preserve the original runs and label corrected regrades; do not
count an impossible control requirement as behavioral lift.

The ignored-support-file case accepts both `git status` and the equivalent
`git --no-optional-locks status` inspection. Adding this shared spelling fixes
command matching; corrected regrades carry no skill-improvement claim.

## CI-safe checks

Ordinary PR and push CI never calls a model. The [maintainer certification
workflow](../../docs/release-certification.md) now validates a reviewed Pstack
workflow report without model calls. These legacy cases remain available through
explicit local runs and [controlled diagnostics](../../docs/legacy-diagnostics.md);
contributor PRs receive no model API key.

```bash
make verify
```

This validates case and fixture structure and unit-tests the grader without
calling a model.

The Pstack port retains the ten cases and their decision criteria, now owned by
four upstream skill names. `catalog-coverage.json` records the 50 names without
questionnaire cases. Local structural validation keeps this diagnostic inventory
accurate. The approved release policy no longer requires a case per skill or
uses the questionnaire score for acceptance. Historical full-matrix proof helpers
retain their original semantics; their output cannot authorize current promotion.

The shared prompt explicitly requests the current skill when installed, otherwise
its recorded legacy name when installed, otherwise the same task without a skill.
This lets both the Pstack port and the released seven-skill package participate
through their own entry points. It tests explicit invocation rather than implicit
discovery.
All conditions receive the same prompt. A no-skill comparison does not measure
an advantage over Pstack; that needs a matched port-without-extension arm.

## Live smoke

For the separate new-project, authorized-repair, and assessment-only cases, see
[project setup diagnostics](../setup/README.md). Their bounded local runner can
pin `gpt-6-astra` without changing the reviewed release policy.

Use an authenticated Codex CLI. Pin the model and reasoning effort so a later
run is comparable:

```bash
python3 scripts/behavioral_eval.py run \
  --case delivery-plan-api-migration \
  --case scale-cost-list-api \
  --case async-safety-webhook \
  --condition both \
  --jobs 3 \
  --model gpt-5.6-luna \
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
case-level candidate regressions, no critical candidate failure, and an average
candidate score of at least 85%.

The historical `promotion` diagnostic compares an exact released revision with the candidate and also keeps
the no-Tugling arm as a sanity check. Provide the released ref and an external
policy-pattern file whose contents are never copied into the report:

```bash
python3 scripts/behavioral_eval.py run \
  --case all \
  --condition all \
  --baseline-ref <released-tag-or-full-sha> \
  --policy-pattern-file /path/outside/tugling/public-policy-patterns.txt \
  --model gpt-5.6-luna \
  --reasoning-effort medium \
  --require-gate promotion
```

The promotion proof requires three attempts over the full bundled suite, an average
candidate score of at least 90%, non-inferior average behavior versus the released
version, no case-level candidate regression, no critical candidate failure, a clean
candidate worktree, distinct released/candidate revisions and plugin content, and
passing privacy and configured policy scans. The suite covers Python CLI and
service work, a TypeScript queue worker, a React responsive UI, and generic
repositories. The output includes `release-proof.json` and `release-proof.md`
beside the behavioral report. The JSON shape is documented by
[`release-proof.schema.json`](release-proof.schema.json).

Before running the promotion comparison, push the clean candidate and exercise the
actual public marketplace path in an empty Codex home:

```bash
python3 scripts/clean_room_install.py public \
  --ref <full-candidate-sha> \
  --codex-bin /path/to/codex \
  --live \
  --model gpt-5.6-luna \
  --reasoning-effort medium \
  --out /private/path/clean-room-proof.json
```

For historical diagnostic reproduction only, run the comparison with
`--attempts 3 --jobs 3` and assemble the legacy schema-1 certificate. This file
cannot authorize active promotion. Keep all generated reports outside Git:

```bash
python3 scripts/release_gate.py assemble \
  --version <version> \
  --behavioral-proof /private/path/release-proof.json \
  --clean-room-proof /private/path/clean-room-proof.json \
  --out /private/path/legacy-certificate.json
```

The certificate binds the public install, exact plugin digest, released baseline,
model settings, breadth matrix, scans, scores, and attempts without copying prompts,
model prose, authentication, or local paths. Every raw attempt remains available
outside the repository; case-level averages keep one stochastic attempt swap from
masquerading as a durable regression or improvement.

## External-project dogfood

Keep project-specific prompts and results outside this repository. Point the
same runner at a clean local checkout and an external case file:

```bash
python3 scripts/behavioral_eval.py project \
  --repo /path/to/project \
  --case-file /path/to/project-case.json \
  --condition candidate \
  --model gpt-5.6-luna \
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
