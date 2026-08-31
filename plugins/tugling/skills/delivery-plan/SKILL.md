---
name: delivery-plan
description: Create or revise an executable implementation plan grounded in the current repository. Use when the user asks for a plan, rollout plan, migration plan, chunking strategy, or wants a feature, fix, refactor, or infrastructure change scoped before coding. Do not trigger for implementation-only work whose product contract and boundaries are already settled.
---

# Delivery Plan

Produce a plan another engineer or agent can execute without reopening its core decisions.

## Ground first

1. Read root and path-specific repository instructions.
2. Inspect current code, verification commands, CI, durable product docs, and relevant architecture decisions.
3. Search for existing implementations, utilities, data models, and plans before proposing new ones.
4. Treat current code and configuration as implementation truth when an old plan has drifted. A plan is not a current-state record.

## Plan contract

Include only sections that change execution, but cover these decisions:

1. **Outcome and boundary**: observable goal, invariants, in-scope work, explicit non-goals, and required approvals.
2. **Current state and reuse**: what exists, what will be extended, and what duplication will be removed or avoided.
3. **Interfaces and ownership**: callers, contracts, data or state owners, external boundaries, and migration or compatibility strategy.
4. **Failure behavior**: invalid input, partial success, rollback, retry, stale data, and operator recovery where relevant.
5. **Scale and cost**: cardinality, latency, round trips, fanout, recurring workload, retention, and cost envelope when the path can grow. Use `$scale-cost-review` for a full review.
6. **Execution slices**: ordered units that each end in an observable check.
7. **Proof matrix**: map each material risk to a unit, integration, end-to-end, screenshot, profile, runtime smoke, or manual review channel.
8. **Definition of done**: exact commands, artifacts, remote or deployed evidence, docs updates, and cleanup state required.

For a non-trivial bug, state what should fail before the fix and why that failure proves the intended defect. For infrastructure-backed work, separate local correctness from applied and runtime proof.

## Output rules

- Return the plan in conversation unless the user requested a plan file or the repository requires one.
- Use concrete paths and commands when the repository establishes them; do not invent conventions.
- Prefer a small complete beachhead over a broad roadmap disguised as one change.
- Flag blocked product decisions separately from implementation details.
- Do not make implementation edits unless the user also asked to build.
- Report plan-only or design-only work as `ADVISORY`, even when a repository check was run. Reserve `LOCAL_PASS` for an implemented change whose local completion gate passed.
