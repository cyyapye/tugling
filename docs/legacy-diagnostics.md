# Legacy diagnostic execution and recovery

This page preserves the older questionnaire runtime and recovery design for
explicit diagnostics. It is not the active release acceptance policy.
The former full-matrix certificate is historical evidence and cannot authorize
promotion through the current controller. See [reviewed Pstack certification](release-certification.md).

## Diagnose one legacy case

`diagnose-case.yml` uses the legacy controller, preflight, pinned Luna/medium
runtime, isolated worker and immutable checkpoints. Select one case from
the controller's ten-case suite; the manifest fixes the candidate condition and
trial 1. There is no public-install task or comparison matrix in this mode.

Pushes to `main` and `codex/**` that change this machinery run a free no-op-case
diagnostic against the local fake provider. A manual dispatch with `synthetic=true`
can exercise another reviewed case without account credentials. Synthetic case
diagnostics preserve the actual fake-provider grader verdict; they do not apply
the deliberately assigned scores used by the full recovery test.

A paid diagnostic requires the protected controller tag, current main/stable SHAs,
an enabled certification setting, and a fresh `approve_paid_run=true` approval.
Its selected case is part of that approval and the immutable manifest. It reuses
the existing GitHub API-key secret and shares the paid-certification concurrency
group. The maximum requested thresholds are 100,000 input tokens (including cached
input) and 5,000 output tokens, also bounded by the configured repository ceilings.
These are observed-token thresholds, not hard billing caps: the one in-flight
trial can exceed them, and all reported usage is retained.

This mode uses manifest/receipt schema version 3 with `purpose=case_diagnostic` and
one budget lane. The retained matrix recovery test uses its version 2, 91-task contract.
Setup can recover before durable admission, but once the trial is admitted it
cannot execute again within the dispatch, even after a known infrastructure error.
Missing paid usage remains blocked. A terminal grade is preserved, including a
failure. Another live trial needs another explicitly approved dispatch.

The bounded `case-diagnostic` artifact contains `diagnostic.json`: exact request,
runtime, task identity, admission/result receipts, observed usage, grader verdict,
and failed check names. An aggregator replacement validates and reuses this report
without another model call. The free workflow deliberately loses the first
aggregator after upload to test that recovery. Its success means the diagnostic
report was produced and recovered; inspect `verification_passed` for the actual
fake-provider grade. In paid mode, a separate verdict job reads the saved report
and fails the workflow if the selected case failed verification.

Diagnostic reports are never certificates: they create no attestation, cannot
authorize promotion, and cannot satisfy any part of a different certification run.
A diagnostic verdict does not satisfy the reviewed Pstack release policy.
Use the observed-workflow report and its separate maintainer approval for release.

## Cost, failure, and recovery

The legacy pipeline freezes all 91 task identities in an immutable manifest.
The current release workflow does not call this pipeline. An identity includes the candidate, baseline, controller, CLI, model,
case, condition and trial. `certification-pipeline.yml` runs two serial lanes;
`certification-lane.yml` gives each task a fresh Ubuntu 24.04 job. Each lane has
`max-parallel: 1`; there is no concurrent writer to a lane checkpoint. Recovery
rounds depend on both previous lanes reaching terminal state.

Each lane owns half of the approved input and output thresholds. Usage is checked
**between tasks**, includes cached input, and preserves reported overshoot. There
can be two in-flight tasks, each able to exceed its lane threshold. These remain
**observed-token admission thresholds, not hard billing caps**. Unused allowance
is not borrowed between lanes. Provider billing is authoritative.

Before a model request is allowed, the supervisor uploads an admission checkpoint.
It uploads a new checkpoint immediately after the task, retaining known usage even
when checks fail. The latest checkpoint contains the complete lane history, so
loading state requires a bounded artifact listing and one download per lane rather
than downloading every result separately. Checkpoints are immutable and contain
only fixed identities, verdicts, numeric scores and usage. Conflicting outcomes,
stale generations, unexpected fields, or results without admissions are rejected.

The official action keeps the API key in its proxy and uses `unprivileged-user`.
A trusted supervisor starts the worker as a separate `tugling-worker` Linux user
in a systemd cgroup. The worker has no sudo or capabilities, a read-only controller
checkout, a 4 GiB memory limit without swap, a two-CPU quota, at most 256 processes,
a 1 GiB work tmpfs, and separately bounded `/tmp` and `/var/tmp`. A file-size limit
and supervisor output limit bound logs. The worker service lasts at most five
minutes, while each model task retains its 180-second timeout and each hosted job
has a ten-minute timeout. The entire worker cgroup is stopped on every outcome.
The uploader and GitHub runner remain outside the worker's user and resource
boundary. Numeric peak memory, process count and supervisor outcome are uploaded.

Recovery is limited to two replacement rounds **within the same approved dispatch**.
A saved terminal verification result is never rerun for a better grade. A setup
failure before durable admission can be retried without authorizing another model
call. An interrupted paid attempt with missing usage blocks its lane and prevents
a certificate; it is never assigned zero usage or automatically spent again.
The free synthetic workflow can replay an interrupted model task because every
request stays on loopback and has no billable usage. This distinction is explicit:
free recovery proof does not authorize paid retries with uncertain accounting.

Planning, recovery selection and final aggregation each have at most three
controller jobs. A replacement coordinator reads the saved state without repeating
model work. If aggregation loses its job after publishing the final artifact, the
replacement validates and reuses that artifact. Artifact provenance must match the
same run, controller commit and source repository; expired or conflicting heads
never fall back to older checkpoints.

`run_attempt > 1`, cross-run evidence reuse and new paid diagnostic dispatches
without fresh approval remain forbidden. The legacy aggregator requires all 91
identities and recomputes its diagnostic comparisons. Its historical schema-1
certificates cannot authorize current promotion. Synthetic manifests produce no
certificate or attestation.

Worker receipts project the evaluator's input, cached-input and output counters
without adding its optional reasoning-token subtotal a second time. Missing or
invalid counters still block admission. Execution failures preserve available
usage plus fixed exit and API error categories; raw error messages stay private.
The free recovery workflow runs the actual behavioral fixtures, CLI, parser and
grader before applying its deliberately synthetic recovery scores. It covers this
usage projection in addition to the public installation path.

Workspace-write evaluations give the CLI a dedicated temporary directory beside
the fixture, within the same disposable, bounded worker scratch space. Linux
sandbox lock files therefore cannot count as repository edits. Only this directory
is added to the sandbox's writable roots; global temporary directories remain
excluded. Trial cleanup removes the runtime directory after stopping descendants.
Free CI runs the pinned CLI against the no-op fixture through the fake provider
and requires its unchanged zero-file change budget to pass. Actual fixture edits
still fail that check; no runtime paths are ignored by the grader.

Manifest and task-receipt schema version 2 require a `checks` map on every
behavioral result. It retains each controller-defined grader check name and a
boolean verdict, including failed decisions, required command groups, evidence
state and change limits. Missing, duplicate, foreign or non-boolean check data is
rejected. Grader detail strings, assistant answers and command output are omitted.
The final `VERIFICATION_FAILED` error includes the candidate's failed check names,
case and trial. Scores, critical verdicts and promotion thresholds are unchanged;
these diagnostics do not turn failed verification into success or authorize a retry.

For example, in `tugling-bounded-noop`, `required_command_group:1` identifies missing
native-gate command evidence, `required_command_group:2` identifies missing Git-status
command evidence, and `evidence_state` identifies an incorrect reported proof state.
The exact required command alternatives and expected state remain in the
controller-owned `evals/behavioral/cases.json` rubric. Older receipts cannot be
backfilled with check verdicts they did not retain; inspect them with their original
controller revision. A new manifest and controller pin are required for version 2.
Synthetic runs preserve the fake provider's real check booleans alongside the
deliberately assigned recovery scores; neither is live behavioral certification.

Artifacts retain data for seven days. A checkpoint is bounded to 2 MiB (normally
far smaller), and the final two certificate JSON files retain their combined
512 KiB limit. Raw model output, prompts, local paths, API keys, auth files and
private policy expressions never enter checkpoint or telemetry artifacts. Failed
or expired evidence remains incomplete. Keep reviewed release evidence outside
this short-lived store.

## Release boundary

Diagnostics do not authorize release. Use the separately reviewed report and
[active certification workflow](release-certification.md), followed by protected
[stable promotion](release-controller.md). Paid diagnostic authority is specific
to the approved case and dispatch; it is not a release requirement.

## Verification

Run `make verify` and `actionlint`. Tests use actual disposable Git remotes for
freshness, package changes, and frozen-ruler rejection, and synthetic usage for
budget/failure cases. They never call a model or create real attestations.

`python3 -I scripts/check_codex_ci.py --codex-bin /path/to/codex` exercises the
real pinned CLI against a local fake Responses endpoint, including isolated auth,
model/effort selection, and disabled request retries. It also checks the public
plugin commands exist. GitHub runs this check on Linux on each push and PR.
These checks prove the diagnostic integration contract, not live model behavior.
Any paid diagnostic still needs its own exact authorization and budget.

`Verify / worker-isolation` deliberately exhausts a worker's memory and process
limits, triggers a timeout, and checks that the worker cannot signal its supervisor
or write the controller checkout. A final worker must still start successfully.
The numeric proof is uploaded on failure as well as success. This is a Linux
integration check; local Python tests do not establish those operating-system
boundaries.

`diagnose-recovery.yml` runs the full 91-task free recovery test when its controller
or workflow changes on `main` or a `codex/**` branch, and supports manual dispatch.
It uses the same workflow, official proxy, pinned CLI and isolated workers with a
loopback synthetic provider. It kills one synthetic worker during a task, simulates
job failure after another task's result upload, and preserves a failing candidate
verification. It also fails the first aggregator after its artifact upload, so a
replacement must validate and reuse the saved final result. The final
`recovery-diagnostic` artifact must prove the missing task
was recovered, the uploaded task was not repeated, all 91 results remain present,
and the failed verification was preserved. No certification secret is passed and
no certificate or attestation is generated.

The older `diagnose-runtime.yml` remains a diagnostic for the historical
single-host setup; it is not proof of the new isolation or recovery workflow.
A passing free test does not establish live model quality or identify the cause of
a historical runner disconnect. Retaining the runner does not make its matrix an
active release requirement.

References: [Codex Action](https://learn.chatgpt.com/docs/github-action),
[automation authentication](https://learn.chatgpt.com/docs/non-interactive-mode),
[GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions),
[artifact attestations](https://docs.github.com/en/actions/concepts/security/artifact-attestations).
