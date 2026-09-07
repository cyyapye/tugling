# Maintainer-triggered release certification

Ordinary pushes, pull requests, and merges run deterministic checks. They never
receive the certification API key or call a model. The additional runtime check
installs the pinned CLI and sends one request to a local fake API, without account
credentials. Fork contributions can run these checks on standard public runners.
Another free job exercises the full public-install discovery path through the
same pinned Codex Action and privilege removal as certification. Its credential
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
   setup-only mode. Its proxy holds the API credential and the action removes
   runner sudo access. Each model task receives only the loopback proxy address,
   a fresh Codex home, and the case's declared sandbox. Model tool processes do
   not inherit API keys, GitHub tokens, or policy-pattern environment variables.
4. Scan the candidate against the configured public-policy patterns before
   spending. Install the exact public candidate in a fresh home and run the
   existing read-only discovery task. Run all 10 synthetic cases under control,
   released, and candidate conditions, with three attempts per condition.
   This is 90 behavioral tasks plus one installation task, run serially with
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

Token thresholds are checked **between tasks**, using reported input/output usage.
Cached input counts toward the input threshold; reasoning output is already part
of reported output usage and is not added twice. An in-flight task can exceed a
threshold, so this is **not a hard token or dollar cap**. A failed or timed-out
task may have consumed unreported tokens; the run reports incomplete accounting
rather than treating missing usage as zero. Provider billing is authoritative.

A failed installation task reports only the failed check names, CLI exit status,
whether a final output exists, and allowlisted HTTP/API error categories when
the CLI exposes them. Raw messages, model output, and paths stay private. Usage
from a completed task is recorded even when its checks fail; missing usage
remains explicitly unaccounted.

There is one task at a time, at most 91 tasks, a 180-second timeout per model task,
and a 330-minute evaluation-job timeout. Process cleanup kills remaining members
of the Codex process group after success, failure, or timeout, before scratch
directories are removed. Public plugin commands use the same cleanup.
HTTP/stream retries are disabled for the configured proxy provider.
Missing usage, task failure, threshold overshoot,
changed refs, or a failed gate stops certification without a signed success.

Workflow reruns (`run_attempt > 1`) are rejected, including a rerun of only the
attestation job. A new dispatch is a new explicit paid approval. Runs are
serialized and do not resume or mix partial evidence. If signing fails after
evaluation, the uploaded files remain **unattested**; do not promote from them.
Reproduction and recovery use the local harness or a newly approved dispatch.

Only the two bounded JSON files are uploaded, with seven-day retention and a
combined maximum size of 512 KiB per successful run. Raw model output, prompts,
local paths, auth files, and policy expressions are not uploaded. Failed-run
logs expose case progress, controlled failure categories, and known usage only.
The ephemeral runner removes raw evidence when the job ends. Keep long-lived
release evidence and reviewed provenance outside this short-lived artifact store.

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

References: [Codex Action](https://learn.chatgpt.com/docs/github-action),
[automation authentication](https://learn.chatgpt.com/docs/non-interactive-mode),
[GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions),
[artifact attestations](https://docs.github.com/en/actions/concepts/security/artifact-attestations).
