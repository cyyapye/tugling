---
name: tugling
description: Set up Tugling for a repository or carry a non-trivial repository change or bounded tracked-queue task from intent through verified handoff. Use when explicitly invoked, when adopting Tugling, or when the user asks to design, implement, fix, refactor, optimize, ship multi-step work, or complete the next checklist or backlog item even when current evidence may produce a no-op. Do not use for a simple factual answer, read-only status request, or trivial edit that does not need orchestration.
---

# Tugling

Deliver the smallest complete change the repository can honestly prove.

## Authority order

Resolve conflicts in this order:

1. The user's current request and explicit constraints.
2. System permissions and approval boundaries.
3. Root and path-specific repository instructions such as `AGENTS.md`.
4. Current code, configuration, tests, CI, runbooks, and durable product docs.
5. Tugling's defaults.

Tugling never grants permission to merge, deploy, delete, spend, contact people, or mutate an external system.

## Set up a project

When the user asks to install, adopt, configure, or set up Tugling for a repository, open and read [references/project-setup.md](references/project-setup.md) before giving setup advice. Do not reconstruct that contract from project files or general memory. Start with read-only discovery, preserve existing project instructions, and make the adapter and CI files the smallest reviewable delta. Setup is not permission to change product code.

## Learn from a correction

When the user explicitly corrects a repeatable engineering decision and the project has enabled local learning, read [references/learning-loop.md](references/learning-loop.md). Do not capture ordinary preferences, secrets, private data, full transcripts, or one-off product decisions. Nothing leaves the project automatically.

## Load the principles

For non-trivial implementation work, read [references/principles.md](references/principles.md) before choosing the design. Apply principles proportionally. In the final handoff, name only a principle that changed a material decision and state that decision.

## Route the work

Use the smallest focused skill that owns the main risk:

- `$delivery-plan` when the user asks for a plan or the work crosses meaningful boundaries.
- `$scale-cost-review` for hot paths, collections, aggregates, background jobs, third-party fanout, or recurring cost.
- `$async-safety` for queues, schedulers, webhooks, retries, replay, ordering, or state transitions.
- `$screenshot-first-ui` when a visible defect is unclear or a material UI change needs current-run visual proof.
- `$skill-delivery` when the artifact being created or revised is a reusable skill.
- `$repo-verify` before claiming an implemented change is ready.

Do not invoke every skill by default. One small change may need only repository instructions and `$repo-verify`.
For a bounded no-op, run the relevant native check and inspect repository status directly; do not load `$repo-verify` unless the verification contract is ambiguous or failing.

## Workflow

1. Restate the observable outcome, invariants, explicit non-goals, and external actions that are or are not authorized.
2. Read repository instructions and inspect current state before proposing new structure.
3. Search for existing code, contracts, helpers, tests, and docs that should be reused or consolidated.
4. Choose a plan proportional to reversibility and risk. Resolve product or architecture ambiguity before editing.
5. Implement the smallest complete slice. Preserve unrelated user changes and avoid speculative compatibility layers.
6. Verify with the repository's native gates and a proof channel matched to the changed behavior.
7. Report the outcome first, then evidence, strongest proven state, and residual risk.

## Honest stop conditions

- If current evidence suggests the requested behavior already exists or the tracked queue is empty, `NOOP` requires both of these current-run proofs:
  1. run the repository's native command that validates the bounded condition or queue; reading the source file alone is not a substitute
  2. run `git status --short --untracked-files=all` and confirm no change was needed
  The state name is part of the proof: report this outcome as `NOOP`, never `LOCAL_PASS`, even though the native validation command passed.
  Do not invent work to justify the invocation or relabel the no-op as an implementation pass.
- If the user requested diagnosis or review only, do not implement a fix.
- If a missing decision would materially change the product or expand authority, stop and ask for it after exhausting safe read-only checks.
- If verification is blocked, report the exact unverified boundary. Do not translate an inconclusive check into success.

## Handoff

Keep the final report compact:

1. user-visible or operator-visible outcome
2. material design decisions and any principle that changed them
3. verification commands and real artifacts inspected
4. strongest proven state: no-op, local, remote, merged, deployed, or observed in production
5. remaining risk or next approval, if any
