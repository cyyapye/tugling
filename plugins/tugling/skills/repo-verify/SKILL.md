---
name: repo-verify
description: Verify readiness with repository-native checks and commit evidence. Use for verification requests, failing or unclear gates, or changes to tests and CI; preserve the project's completion contract.
---

# Repo Verify

Prefer repository truth over a universal checklist.

## Resolve the contract

1. Read root and path-specific repository instructions.
2. Inspect the changed files and classify the affected surfaces.
3. Find the canonical commands in the build files, test docs, package scripts, and CI workflows.
4. Use the narrowest relevant check while iterating, then return to the canonical completion gate unless the repository or task justifies a narrower final gate.

Reuse current evidence for unchanged files and commands. Once required checks pass,
repeat or broaden them only after a relevant change, failure, or unresolved risk.

When the project declares a verification map or the user asks to map real user
flows to native checks, read [references/project-flows.md](references/project-flows.md).
Review whether changed project rules have native assertions and required mappings.
Run the complete declared requirements through the canonical gate or
`--run-required`, without duplicating execution. Map validation and selected-flow
receipts cannot satisfy required verification. Check required evidence against the
current clean commit before citing it; report uncovered rules or missing required
results as a readiness gap. A required pass alone does not prove remote CI or deployment.

## Review verification integrity

Inspect any changed judging machinery before trusting its result:

- tests and assertions
- mocks and fixtures
- snapshots and golden files
- coverage thresholds
- retries and timeouts
- test selection, skips, focused cases, and sharding
- CI workflows and deployment gates

Classify the change as increasing, preserving, or reducing assurance. A modified test harness or CI workflow cannot be its own only proof when independence matters.

## Run and repair

1. Run the chosen repository-native command.
2. Summarize failures by surface and probable changed-scope cause.
3. If the user authorized implementation, apply the smallest in-scope fix and rerun the focused check before the full gate.
4. Add a proof channel when the existing checks leave a material behavior unproven: real CLI invocation, stored-value readback, integration path, browser flow, screenshot inspection, profile, migration replay, or deployed smoke. Required project evidence still applies.
5. If code was pushed as part of the authorized task, inspect relevant remote checks to terminal state. Do not infer remote success from local success.

When a module or support file exists locally but CI cannot find it, check repository state before changing code:

```text
git status --short --untracked-files=all
git ls-files <path>
git show HEAD:<path>
git check-ignore -v <path>
```

On-disk presence is not proof that a file exists in the commit.

## Evidence states

Report the strongest state actually proven:

- `NOOP`: the bounded requested work was shown to be already satisfied or absent, the relevant check passed, and repository status confirms no change was needed.
- `LOCAL_PASS`: required local gate and the behavior proof appropriate to the change passed. Existing native checks may supply both; a second harness is unnecessary when they already prove the outcome.
- `REMOTE_PASS`: relevant checks passed for the exact pushed revision.
- `MERGED_PASS`: post-merge checks passed for the merged revision.
- `DEPLOYED_PASS`: the exact revision was deployed and a current-run smoke passed.
- `BLOCKED`: a required readiness boundary is unmet or inconclusive. A narrower green command does not override missing commit content, invalid judging machinery, or another failed matched proof channel.

Repositories may use stricter names or additional states. Never collapse a lower state into a higher one.

When readiness concerns a commit, `LOCAL_PASS` requires the files that made the local gate pass to exist in that commit. A test that succeeds only because of an ignored or untracked support file is evidence for `BLOCKED`, not `LOCAL_PASS`.

Before handing off, reconcile the evidence-state field with every readiness decision and the prose summary. If any required boundary is blocked or a decisive commit-content check remains incomplete, emit `BLOCKED`; never describe the commit as blocked while labeling the overall state `LOCAL_PASS`.

## Guardrails

- Do not skip a failure silently or weaken an assertion merely to get green.
- Do not regenerate snapshots without inspecting the changed artifact.
- Do not inflate retries or timeouts without proving that flakiness, rather than a defect, is the cause.
- Use current-run evidence; stale logs and old artifacts are context, not proof.
- Local verification does not authorize a push, merge, deployment, or external mutation.

## Handoff

Lead with readiness state. List commands, artifacts inspected, verification-integrity findings, fixed failures, remote or deployed evidence, and the exact remaining blocker or unverified boundary.
