---
name: repo-verify
description: Verify a repository change with its native commands, review the integrity of changed tests and CI, fix in-scope failures when authorized, and report the strongest proven state. Use when the user asks to run checks, validate readiness, make a change merge-ready, investigate failing local verification, or confirm work is complete. Do not use a generic gate when the repository already defines one.
---

# Repo Verify

Prefer repository truth over a universal checklist.

## Resolve the contract

1. Read root and path-specific repository instructions.
2. Inspect the changed files and classify the affected surfaces.
3. Find the canonical commands in the build files, test docs, package scripts, and CI workflows.
4. Use the narrowest relevant check while iterating, then return to the canonical completion gate unless the repository or task justifies a narrower final gate.

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
4. Match a second proof channel to the risk: real CLI invocation, stored-value readback, integration path, browser flow, screenshot inspection, profile, migration replay, or deployed smoke.
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
- `LOCAL_PASS`: canonical local gate and matched local artifact proof passed.
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
