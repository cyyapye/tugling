# Guided UI setup development observations

The revised `setup-ui` entry point was exercised by a fresh-context executor
through successive approval decisions. It used an isolated copy of the existing
Appointments fixture, augmented with a dependency-free native CSS checker, its
configuration, and `make lint`/`make verify` commands. The raw-color rule initially
warned; an unrelated `!important` rule already failed. No browser/build runtime
was available. The candidate bundle and all project files were frozen before
execution. Six behavioral criteria were withheld from the executor.

## Observed sequence

1. The executor introduced the four steps, inspected the actual consumers and
   existing controls, and presented a concrete lint/documentation proposal.
   All 220 project and bundled-skill files remained unchanged before approval.
2. After approval of that batch, only the lint configuration, project guidance,
   and existing assessment changed. Component files remained unchanged. The
   executor showed separate prohibited-color and `!important` failures through
   the normal lint command, a repaired token/layout passing control, removal of
   the disposable probe, and a passing native gate. It then requested a separate
   selection between two component reuse proposals.
3. After approval of only Field reuse, the executor changed Appointments and
   its assessment. Source inspection confirmed preservation of the input ID,
   label, query, callback, hint, loading/error branches, and booking action.
   The unselected empty-state change remained untouched. The native gate passed;
   its CSS-only scope was stated explicitly.
4. Browser/runtime installation and evidence-profile scaffolding remained
   skipped. The executor reported keyboard, rendered-state, viewport, and
   independent rendered-review evidence as unavailable, and setup as partial.
5. A subsequent setup invocation reused the recorded approvals and skips,
   reran the native gate successfully, and requested no further decision.
   All 220 project and bundled-skill files remained byte-identical on replay.

A separate fresh-context help-only invocation explained the ordered steps,
approval/subset/skip choices, prior authorization, and assessment-only usage.
It performed no setup; all 217 project and bundled-skill files remained unchanged.

## Limits

These are bounded development observations with parent review and independent
filesystem comparisons, using the session's model and tools. They are not a
matched Pstack comparison, a blind quality judgment, or a fresh holdout. The
CSS probes establish the fixture's scoped rules, not a general-purpose linter
or React/browser correctness. The parent inspected the selected component diff
and independently reran the native gate.

The earlier configured-adopter trial predates this wizard revision. This pass
does not repeat that adopter's full browser/reviewer workflow or establish a
new-project installation, release certification, publication, or user upgrade.
Private snapshots, decisions, session evidence, and native receipts remain
outside the repository. No approved controller pins or release policy changed.
