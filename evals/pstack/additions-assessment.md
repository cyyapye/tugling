# Default to Pstack

Assessment date: 2026-10-17. None of the remaining Tugling additions has
established a substantive advantage over the same Pstack methods on Codex.
Remove their automatic loading from entry points, playbooks and the adapter.
Keep the references and useful failure cases for explicit evaluation and existing
adopter contracts. Absence of demonstrated benefit is enough to withhold default
inclusion; it does not prove an addition can never help.

## Source assessment

| Addition | Pstack or Codex baseline | What the addition contributes | Decision and retained failure cases |
| --- | --- | --- | --- |
| Delivery planning | [Architect](../../plugins/tugling/skills/architect/SKILL.md), [Multi-phase plan](../../plugins/tugling/skills/poteto-mode/playbooks/multi-phase-plan.md), sequencing and proof principles | Another plan contract covering scope, migration, failure, budgets and proof | Substantial overlap; no matched benefit. Retain [API migration](../behavioral/fixtures/delivery-plan-api-migration), including compatible caller migration and plan-only scope. |
| Completion and bounded no-op | Poteto-mode, [Prove It Works](../../plugins/tugling/skills/principle-prove-it-works/SKILL.md), Codex scope/authorization adapter | Status labels and prescribed command evidence for no-op | Status vocabulary is not an outcome advantage. Retain [bounded completion](../behavioral/fixtures/tugling-bounded-noop). |
| Scale and cost | Architect, [Perf issue](../../plugins/tugling/skills/poteto-mode/playbooks/perf-issue.md), [Benchmark checklist](../../plugins/tugling/skills/benchmark-checklist/SKILL.md) | Explicit prospective cardinality, query, recurring-cost and retention checklist | Plausible specificity, unproven lift. Retain [list endpoint budget](../behavioral/fixtures/scale-cost-list-api); future cases should cross real pagination/batching limits and include recurring idle work. |
| Async safety | [Idempotency](../../plugins/tugling/skills/principle-make-operations-idempotent/SKILL.md), state modeling, shared-state separation and proof | Explicit ordering, retry classification, leases, dead-letter recovery and runtime configuration checks | Plausible specificity, unproven lift. Retain [webhook](../behavioral/fixtures/async-safety-webhook), [TypeScript worker](../behavioral/fixtures/async-safety-typescript-worker), and [retry/lease interaction](../behavioral/fixtures/async-safety-retry-lease-proof). |
| UI diagnosis | [Experience First](../../plugins/tugling/skills/principle-experience-first/SKILL.md), Feature/Bug fix, native UI tools; Visual parity for equivalence only | Defect taxonomy and structural-before-spacing fix order | More detailed vocabulary is not proof of better diagnosis. Retain [mobile overflow](../behavioral/fixtures/screenshot-first-mobile-overflow) and [UX development cases](../ux/README.md), including hierarchy, misleading affordances and exact-copy constraints. |
| Skill delivery | [Authoring a skill](../../plugins/tugling/skills/poteto-mode/playbooks/authoring-a-skill.md), [Eval](../../plugins/tugling/skills/poteto-mode/playbooks/eval.md), native Codex skill-creator | Repeats reuse, metadata, provenance, routing and behavioral-check advice | Preserve this repository's attribution and evaluation requirements locally. No need for an extra global workflow. Retain [overtriggering](../behavioral/fixtures/skill-delivery-overtrigger) and installed-skill/source integrity checks. |
| Project bootstrap, adoption and enforcement | Poteto-mode, [Figure It Out](../../plugins/tugling/skills/figure-it-out/SKILL.md), native project commands and Codex setup tools | Custom adapter, pinned helper, rule map, receipts, discovery inventory and cleanup machinery | Distinct executable capabilities, but no matched evidence that imposing them improves ordinary setup. Keep existing helper tests and [setup](../setup/README.md)/[enforcement](../enforcement/README.md) cases; ordinary setup does not require this integration. |
| Local learning | [Reflect](../../plugins/tugling/skills/reflect/SKILL.md), [Encode Lessons in Structure](../../plugins/tugling/skills/principle-encode-lessons-in-structure/SKILL.md), Codex history and explicit memory authority | Persistent local correction ledger and review dispositions | An additional storage/review system, not an established improvement in learning. Retain [project helper tests](../../tests/test_project_contract.py) for privacy, capture and review behavior; keep native reflection as the default. |

The separate [verification assessment](method-observations.md) already found a
tie on two known tasks. Its [failure cases](verification-cases.md) remain useful.
Legacy scores compare against no skill or older Tugling, often with prescribed
answers; they do not establish advantage over Pstack. Existing fixtures are known
development cases, not fresh holdouts.

## Observed baseline probes

A separate author, without reading the additions or prior answers, created three
offline tasks and froze their success criteria before the runs. Each builder got
a fresh native install of the default package, an ordinary read-only request,
and project inputs. Criteria and observer records stayed outside its workspace.
The author supplied real browser captures for the UI task. These are development
probes; after this run they are known cases.

| Probe | Observed Pstack behavior | Boundary |
| --- | --- | --- |
| Delayed reward worker completes after a lease is reclaimed | Reproduced 200 credited points for a 100-point job; identified the missing generation/status guard; recommended an atomic transition and checked duplicate/rollback cases | The recommendation preserves expired-job recovery. No production fix was implemented. |
| First page performs work for every tenant project | Observed 2,401 calls and 3,600 transferred rows for 25 cards; exercised two page-first designs across 36 result/budget checks, including 12,000 projects | Preserved tenant scope, ordering and zero-count projects. Production latency remained unverified. |
| Access settings obscure the primary task | Identified the dominant promotion, enabled-but-disabled-looking Save, emphasized Delete and phone overflow; proposed four focused changes | Initial JSONL did not prove image viewing. A separate run received both captures as native CLI image inputs, but omitted explicit preservation of deletion confirmation. No redesign was implemented. |

The first anonymous artifact review found 15 criteria satisfied and UI capture
use unverified. The parent's command audit confirmed the worker and endpoint
observations, successful installed skill/adapter reads, unchanged repositories,
and no optional extension reads. The image-input repeat addresses the UI input
observability gap without changing guidance. The original attempt remains in the
record. An earlier malformed image invocation exited before a model task started;
it is retained separately. A minor precision issue also remains in the endpoint
reply: it described a proposed `ProjectCard` shape as an existing type, while the
source returns dictionaries.

The separate review of the image-input repeat found five criteria satisfied and
one failed: it recommended separating Delete from Save without explicitly saying
to preserve the existing confirmation dialog. Keep that failure. The reply did
not recommend removing confirmation, and the repository stayed unchanged, so
this is an omission in the recommendation rather than an observed destructive
change. The original UI reply did explicitly preserve confirmation. This
inconsistency remains a useful future comparison case; the dormant UI checklist
does not itself specify confirmation preservation, and no advantage for it was
established. The parent verified native image-input delivery and the unchanged
review bundles separately from the reviewer's content assessment.

Package SHA256: `3f1bc725e3717ad316422fb676ee4e4f078e998a41beb3c303f530f0470306da`.
Runtime: Codex CLI `0.163.0-alpha.10.2`, `gpt-6-astra`, effort `xhigh`.
The first three calls used a 900,000-input/30,000-output admission limit; the
image-input repeat used 300,000/10,000. Each call had a 240-second deadline.
These are between-call admission limits, not hard billing caps. Four completed
builder calls consumed 507,165 input and 11,774 output tokens. Task seconds were
93.22 for the worker, 137.55 for the endpoint, and 70.26/45.26 for the two UI runs.
Author/reviewer usage is not included in these builder totals.

These probes screen for a concrete Pstack gap; they are not paired extension
trials or evidence of equal reliability, lower cost, or superiority. The review
used the same model family, with a separate parent trace audit. No new default
guidance is justified by these outcomes. Planning, completion, authoring, setup
and learning were assessed from source overlap and existing evidence, without
fresh live trials in this round. Raw inputs, deliveries, image hashes, traces,
review bundles and original outcomes remain outside Git. Full-catalog release
certification remains a separate unmet boundary.

## What remains active

Keep the attributed 54-skill Pstack catalog and playbooks, full MIT license and
source inventory. Keep necessary Codex translations for invocation, native tools,
model inheritance, paths, unavailable integrations, scope and authorization.
These make the same methods executable on this host; they are not competing
engineering methods. Existing adopter instructions continue to govern their repos.

## Evidence needed to restore an addition

Follow the [Pstack evaluation method](method.md). Establish a concrete baseline
failure first. Compare the smallest relevant addition on identical inputs with
hidden criteria, actual execution evidence and blinded review. Require a material
outcome improvement on repeated fresh tasks and an irrelevant task without added
work or scope regressions. Confirm the addition was actually read. Preserve all
attempts and report overhead. Source overlap alone cannot prove equivalence;
a plausible gap or a single narrow win cannot justify default inclusion.
