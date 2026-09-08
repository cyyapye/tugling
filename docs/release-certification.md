# Maintainer-triggered release certification

Ordinary pushes, pull requests, and merges run deterministic checks. They never
receive the certification API key or call a model. The additional runtime check
installs the pinned CLI and sends one request to a local fake API, without account
credentials. Fork contributions can run these checks on standard public runners.
Another free job exercises the full public-install discovery path through the
pinned Codex Action and proxy. Its credential
is a fixed synthetic string and its upstream is a local fake API. It checks a
synthetic tool call, successful response, and reported usage, not live model quality.
For pull requests, this installation check uses the contributor's exact public
head revision, including contributions from forks.

`certify-release.yml` is a separate, manually dispatched workflow. It produces
sanitized, attested evidence for a reviewed release candidate. It cannot merge,
push, move `stable`, or create a version tag. No paid GitHub plan is required for
this public repository. OpenAI API usage is a separate maintainer expense.

## Activation and spending authority

The workflow is disabled by missing configuration. Merging this implementation
does not configure secrets, enable paid runs, or authorize a usage allowance.

Before enabling certification, review the exact controller commit independently
of its own test results. Create an immutable, protected `controller-*` tag at that
commit and configure these repository settings:

| Setting | Purpose |
| --- | --- |
| Variable `TUGLING_CERTIFICATION_CONTROLLER_SHA` | Full SHA of the separately approved workflow and evaluators |
| Variable `TUGLING_CERTIFICATION_ENABLED` | Set to `true` only after runtime, credential, policy, and cost review |
| Variable `TUGLING_CERTIFICATION_MAX_INPUT_TOKENS` | Approved ceiling on a dispatch's input-token threshold, including cached input |
| Variable `TUGLING_CERTIFICATION_MAX_OUTPUT_TOKENS` | Approved ceiling on a dispatch's output-token threshold |
| Secret `TUGLING_CERTIFICATION_API_KEY` | Dedicated OpenAI API credential for this project's certification runs |
| Secret `TUGLING_PUBLIC_POLICY_PATTERNS` | Maintainer-reviewed, newline-separated public-policy regular expressions |

There is no default token allowance. Each new dispatch must supply the exact
current `main` and `stable` SHAs, explicit positive input/output thresholds within
the configured ceilings, and `approve_paid_run=true`. Dispatch the workflow from
the reviewed controller tag, not a candidate-selected workflow. GitHub restricts
manual dispatch to writers; the official Codex Action also checks write access.
The workflow is deliberately restricted to `cyyapye/tugling`; a fork must review
and configure its own copy and credentials to run paid certification.

The certification controller pin is separate from
`TUGLING_RELEASE_CONTROLLER_SHA`. Enabling certification does not enable promotion.
Repository configuration and permission to change workflows remain administrative
trust roots. A checked-in guard cannot stop a repository administrator from
deliberately replacing it. Protect those controls before activation.

## What a run proves

1. Before model setup, require a fresh, explicitly approved dispatch, the exact
   reviewed controller, a successful latest push `Verify` run for the candidate,
   unchanged judging machinery, and current main/stable refs. Reject symlinks,
   submodules, oversized source trees, changed hooks/permissions, or a reused
   release version. Source trees are limited to 2,000 files and 16 MiB each.
2. If plugin content is unchanged, return `UNCHANGED_PLUGIN` before accessing the
   API credential. No behavioral certificate or attestation is created. A change
   only to release tooling can therefore complete without a paid run.
3. Install Codex CLI `0.153.4` through the SHA-pinned official Codex Action in
   setup-only mode. Its proxy holds the API credential outside the separate
   unprivileged worker. Each model task receives only the loopback proxy address,
   a fresh Codex home, and the case's declared sandbox. Model tool processes do
   not inherit API keys, GitHub tokens, or policy-pattern environment variables.
4. Scan the candidate against the configured public-policy patterns before
   spending. Install the exact public candidate in a fresh home and run the
   existing read-only discovery task. Run all 10 synthetic cases under control,
   released, and candidate conditions, with three attempts per condition.
   This is 90 behavioral tasks plus one installation task, in two serial lanes with
   `gpt-5.6-luna` and medium reasoning. The model name is an API alias, not an
   immutable backend snapshot; all three arms use the same configured name.
5. Use controller-owned fixtures, schemas, Python graders, scans, thresholds,
   and certificate assembly. The candidate provides plugin content and Git
   identity. Candidate copies of evaluation scripts are never imported or run.
   Existing promotion thresholds and full-matrix requirements are preserved.
6. Recheck main/stable freshness after the evaluation. Publish only
   `certificate.json` and `certification.json` after every gate passes. The latter
   binds the former's digest to the candidate SHA, baseline SHA, controller SHA,
   GitHub run/attempt, model configuration, and observed usage.
7. A separate fresh job with attestation permission validates those identities
   and package contents and attests both files. It has no API credential and no
   repository write permission. GitHub provenance identifies the controller
   workflow revision; the attested envelope separately identifies the candidate.

An attestation establishes where those bytes were produced. The reviewed graders
and their evidence establish what was checked; a signature alone does not prove
behavioral quality or authorize promotion.

Changing the certification model requires a separately reviewed controller commit,
protected controller tag, and updated controller pins before dispatch. Historical
certificates retain the model they actually used. The first approved live Luna
certification must pass this same full matrix and every existing promotion gate;
local checks and the fake API transport check do not establish live model quality.

## Cost, failure, and recovery

The controller freezes all 91 task identities in an immutable manifest before
spending. An identity includes the candidate, baseline, controller, CLI, model,
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

`run_attempt > 1`, cross-run evidence reuse and new paid dispatches without fresh
approval remain forbidden. If attestation fails, the successful evaluation
checkpoints and unsigned certificate remain available for inspection. Promotion
still requires the complete successful workflow and both verified attestations.

The independent aggregation job requires all 91 exact task identities, recomputes
the existing comparisons and promotion gates, repeats freshness and policy checks,
and assembles the existing certificate format. Leaf worker jobs tolerate execution
failure so recovery can run; **only this complete aggregation and the separate
attestation job can establish certification success**. Synthetic manifests cannot
produce certificates.

Worker receipts project the evaluator's input, cached-input and output counters
without adding its optional reasoning-token subtotal a second time. Missing or
invalid counters still block admission. Execution failures preserve available
usage plus fixed exit and API error categories; raw error messages stay private.
The free recovery workflow runs the actual behavioral fixtures, CLI, parser and
grader before applying its deliberately synthetic recovery scores. It covers this
usage projection in addition to the public installation path.

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

## Review and promotion handoff

Download the two files from a successful certification run. Verify both with
`gh attestation verify --repo cyyapye/tugling --signer-workflow
cyyapye/tugling/.github/workflows/certify-release.yml --signer-digest
<approved-controller-sha> --deny-self-hosted-runners <file>`, and compare the envelope's
candidate/baseline/run values with the intended release. Review the complete
workflow conclusion as well as the certificate's scores, checks, and usage.

The [promotion controller](release-controller.md) downloads and verifies both
attested files independently in its preflight and write jobs. Supply the successful
certification run ID, exact candidate, version, and reviewed certificate digest
when dispatching from the approved promotion controller tag. It requires the
protected release environment's explicit maintainer approval and runs a free
stable-alias installation canary after publication. No certificate is committed
back into the candidate, and no promotion phase calls a model.

Leave the controller pins unset until the merged machinery and GitHub protections
have been independently reviewed. Certification spending still requires the
separate configuration and per-dispatch approval described above.

## Verification

Run `make verify` and `actionlint`. Tests use actual disposable Git remotes for
freshness, package changes, and frozen-ruler rejection, and synthetic usage for
budget/failure cases. They never call a model or create real attestations.

`python3 -I scripts/check_codex_ci.py --codex-bin /path/to/codex` exercises the
real pinned CLI against a local fake Responses endpoint, including isolated auth,
model/effort selection, and disabled request retries. It also checks the public
plugin commands exist. GitHub runs this check on Linux on each push and PR.
These checks prove the integration contract, not a successful paid certification;
the first live run remains a separate activation check with an approved budget.

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
a historical runner disconnect. Full paid certification remains a separately
approved activation check after reviewed controller pins have been refreshed.

References: [Codex Action](https://learn.chatgpt.com/docs/github-action),
[automation authentication](https://learn.chatgpt.com/docs/non-interactive-mode),
[GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions),
[artifact attestations](https://docs.github.com/en/actions/concepts/security/artifact-attestations).
