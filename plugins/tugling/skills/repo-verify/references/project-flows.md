# Native project flows

Use this adapter to map project rules and user behavior to native checks. Full
project setup declares required coverage; legacy adapters may retain optional
flow selections. Keep the repository's instructions, native test framework, and
canonical completion gate authoritative.

## Discover before mapping

Read the existing tests and their configuration. Identify the behavior asserted,
fixture scope, launch command, readiness check, service ownership, teardown, and
artifact locations. Prefer an existing native command that owns its complete
lifecycle, such as a browser test runner with a configured web server. Map a
small set of important flows; do not duplicate assertions in a second harness.

If an existing command needs a separately managed service, resolve launch,
isolation, health, and cleanup through the repository's native tooling before
mapping it. The adapter does not start detached services, reuse arbitrary running
servers, provision infrastructure, or define a new browser framework.

## Map checks and required rules

Add `"verification": ".tugling/verification.json"` inside `project` in the existing
`.tugling/project.json`. Existing schema-version-1 adapters without this field
continue to work. Use a Tugling source that supports this field; older releases
correctly reject an unknown field, so update an accepted pin only after release
and project review.

The following is a synthetic example. Substitute actual repository commands and
committed source files after reading them:

```json
{
  "schema_version": 1,
  "flows": [
    {
      "id": "dashboard",
      "description": "Open the synthetic dashboard and navigate to a saved item on desktop and mobile.",
      "argv": ["make", "e2e", "E2E_ARGS=e2e/dashboard.spec.ts"],
      "timeout_seconds": 600,
      "sources": ["Makefile", "playwright.config.ts", "e2e/dashboard.spec.ts"],
      "runtime": {
        "owner": "native-command",
        "launch": "Playwright webServer starts the repository dev command on isolated ports.",
        "health": "Playwright waits for the local API readiness URL through the web proxy.",
        "cleanup": "Playwright stops its owned server process group when the check ends."
      }
    }
  ],
  "requirements": [
    {
      "id": "dashboard-workflow",
      "description": "Saved items are reachable within the project's accepted interaction budget.",
      "sources": ["docs/dashboard-workflow.md"],
      "flows": ["dashboard"]
    }
  ]
}
```

Each flow has a unique lowercase id, a concrete behavior description, an argv
array, a timeout from 1 to 3600 seconds, and committed source-file pointers.
There are at most 32 flows. The `runtime` fields are reviewable descriptions of
the native lifecycle, not additional commands or independently verified health
claims. Use `null` for a check that needs no runtime. Source pointers must include
the actual test and any file that defines its runtime lifecycle. Reject missing,
untracked, or symlinked sources. Source presence alone does not prove assertions
are sufficient: inspect test selection, skips, mocks, and screenshot coverage.

`requirements` maps accepted project rules to their authoritative committed
policy sources and enforcing flow IDs. It has 1 to 64 unique lowercase IDs,
nonempty descriptions and sources, and one or more distinct existing flow IDs
per rule. Share a flow when it enforces several rules. Required execution takes
their union in map order and runs each flow once. Declare all accepted rules in
scope, including resource, workflow, component, and artifact rules where relevant.
Do not add unused categories or fictitious limits just to fill a template.

The helper rejects invalid declarations and missing/untracked/symlinked sources.
It cannot determine whether a rule was omitted or a native assertion actually
enforces its description. Review coverage and demonstrate a known defect makes
the native assertion fail through the required entry point. Required empty, omitted, filtered, or
skipped cases must fail in the native runner. Validate individual case membership
and outcomes where ordinary discovery can silently lose tests; counts or files
alone are insufficient. See [native enforcement](../../tugling/references/project-enforcement.md)
for runner integrity, source-launcher trust, and explicit CI revision proof. Existing maps may omit
`requirements` for compatibility; that is not required enforcement, and
`--run-required` refuses an absent or empty declaration.

## Validate, then execute explicitly

The ordinary project-contract command also validates a configured map. It never
executes mapped commands without an execution flag:

```text
python3 -I <tugling-checkout>/plugins/tugling/scripts/project_contract.py \
  --repo <project-checkout> --source-root <tugling-checkout> --source-mode pinned
```

Run selected flows from a clean committed project checkout:

```text
python3 -I <tugling-checkout>/plugins/tugling/scripts/project_contract.py \
  --repo <project-checkout> --source-root <tugling-checkout> --source-mode pinned \
  --run-flow dashboard --json
```

Repeat `--run-flow` for additional ids. Selection runs serially, stops on the
first failed command, and has a combined timeout budget of at most two hours.
Native logs stream to stderr; JSON stdout contains the result and receipt path.
Execution currently requires macOS or Linux. The helper bounds the command's
process group and stops owned descendants on failure, timeout, or cancellation.
A successful command that leaves descendants requiring cleanup fails the flow.
Services that detach into another session still require the native runner's
teardown. Never kill unrelated processes or remove shared databases to recover.

Run only reviewed native commands within existing authorization. An argv array
avoids an implicit shell; it does not sandbox the selected program. The program
inherits the caller's environment and its own network and spending behavior.
Use synthetic fixtures and repository-owned isolation; do not copy credentials
or private data into a pilot. The helper itself uses no model, network API,
credential, background service, or scheduled job.

For complete required coverage, run this from a clean committed project checkout:

```text
python3 -I <tugling-checkout>/plugins/tugling/scripts/project_contract.py \
  --repo <project-checkout> --source-root <tugling-checkout> --source-mode pinned \
  --run-required --json
```

This derives the selection from all current requirements and uses the same
serial execution, aggregate timeout, failure, and process cleanup rules. It
never silently reduces the set to fit the time budget. A failed command stops
the run and yields `REQUIRED_FAIL`; all declared checks must succeed for
`REQUIRED_PASS`. An inherited project ancestry guard refuses recursive execution
of the same repository; validation and checks of independent fixture repositories
remain permitted. Map native leaf commands or choose
one outside wrapper for the canonical command, as described in
[project setup](../../tugling/references/project-setup.md).

## Evidence and scope

Each run writes a new permission-restricted JSON receipt under the ignored,
untracked `.tugling/local/verification/managed-v1/` directory. This storage is independent
of whether correction learning is enabled. It contains the project commit,
config/map/helper digests, Tugling identity and checkout cleanliness, selected commands, exit results,
cleanup outcome, timestamps, and whether the worktree stayed clean. It does not
store command logs, secret values, application data, or screenshots. Only the
public execution context listed below is recorded, never an environment dump.
Required receipts also contain the complete requirement-to-flow declaration.
Native reports and screenshots remain in the project's existing artifact paths;
inspect them when required by the project. Helper execution automatically bounds
inactive receipts by age, count and bytes; see [receipt retention](../../tugling/references/project-enforcement.md#automatic-receipt-retention)
for defaults and project overrides. Archive needed evidence before expiry.
Receipt checks remain read-only; nothing uploads automatically.

To check a receipt against the current clean checkout:

```text
python3 -I <tugling-checkout>/plugins/tugling/scripts/project_contract.py \
  --repo <project-checkout> --source-root <tugling-checkout> --source-mode pinned \
  --check-flow-evidence .tugling/local/verification/managed-v1/<run-id>.json --json
```

`FLOWS_PASS` proves only the selected native commands exited successfully for
that clean commit and their owned process groups finished. It does not prove
every feature, screenshot quality, the canonical gate, remote CI, deployment,
or absence of behavior outside the tests. Dependencies and ignored runtime
inputs still follow the native repository's trust contract. This editable local
receipt is a freshness and scope aid, not a signed release attestation.

Check complete required evidence with:

```text
python3 -I <tugling-checkout>/plugins/tugling/scripts/project_contract.py \
  --repo <project-checkout> --source-root <tugling-checkout> --source-mode pinned \
  --check-required-evidence .tugling/local/verification/managed-v1/<run-id>.json --json
```

This requires a `REQUIRED_PASS` receipt, the exact current requirements and
complete ordered flow set, matching clean project/config/map/helper identity,
and one successful matching result for every command. A selected receipt is
insufficient even when it happens to name all flows. `REQUIRED_PASS` proves the
declared native checks ran successfully; it cannot certify undeclared behavior,
assertion quality, hosted CI, or release readiness. A receipt remains valid only within its retention age and matching execution
context. Checking it does not rerun tests or prove a new CI job.

`--run-native` invokes the canonical command; it is mutually exclusive with flow
execution and receipt checking. That legacy command result alone is not a
required receipt. Use existing canonical wiring to avoid duplicate checks. A
focused flow pass cannot replace a required canonical gate or raise the overall
readiness state by itself. Recheck receipts
before citing them after a commit, map, config, or helper change. Failed, stale,
dirty, incomplete, and missing evidence never become a pass.

## CI and adoption

Validation-only CI verifies adapter compatibility. Full enforcement also runs
`--run-required` through the canonical command or one outside wrapper in the
existing unprivileged native test job. Execute it during every relevant CI run,
without optional failure or skipped required coverage. Keep the Tugling checkout
outside the project or explicitly ignored so verification sees a clean revision.
Hosted branch rules must require the job before claiming it blocks merges; the
helper does not inspect or configure those settings. Do not execute contributor-defined commands
with maintainer secrets or through a privileged pull-request trigger. No model
evaluation or paid certification is part of this adapter.

Pilot against a clean isolated adopter checkout, use its native desktop/mobile
checks, inspect required artifacts, and verify owned services are gone. Report
the tested commit and selected/required scope separately from the canonical gate and
remote status. Keep adopter source, raw logs, local paths, and private evidence
out of the reusable plugin and its release certificate.

## CI execution cost and receipt reuse

Use one native execution owner for each revision and environment. Other jobs may
validate its complete required receipt; do not bolt a second full enforcement
suite onto an existing full CI suite. The helper rejects identical argv arrays
under different selected flow IDs. It cannot detect overlapping wrapper commands
or duplication across workflows: inspect the expanded native commands and CI DAG.
Keep PR-head, merge-candidate and post-merge revisions distinct.

Receipts bind the OS, architecture, Python version, and a digest of the optional
`TUGLING_VERIFICATION_ENVIRONMENT` label. Set that non-secret label to the project's
pinned runtime/toolchain or image identity in both producer and validator jobs.
On GitHub Actions, receipts additionally bind repository, workflow ref, run ID,
attempt and event SHA. Download the exact named artifact from that same run;
never search for the latest successful artifact. A partial rerun with an older
producer receipt fails: rerun the complete workflow. Copies across checkouts are
supported when all identities match. Editable receipts remain evidence, not
cryptographic attestations; native source review and artifact provenance remain
required. Environment labels are declarations, not sandbox measurements.

Make receipt consumers cancellation-aware. On GitHub Actions, `if: ${{ !cancelled() }}`
still runs after a failed producer; explicitly require the producer's successful
result before validating evidence. An unconditional `always()` job can survive
workflow cancellation, wait for a scarce runner, and hold the concurrency slot
needed by its replacement. Keep bounded cleanup with the owning job, and verify
superseded runs release their slot without executing another native suite.

A project may set `project.verification_budget_seconds` to an integer from 1 to
7200. Required execution measures total native command time, records a sorted
`performance.slowest_flows` list, and fails if the complete run exceeds the budget.
It does not omit checks, raise deadlines, or stop successful checks early to fit.
Receipt validation recomputes the summary and rejects invalid timing, expired or
future timestamps, environment changes, and another CI invocation. Projects
without a budget still receive timings. Queue/setup time is separate and must be
measured from the CI provider; this helper measures active native verification.

Establish budgets from a recorded baseline and tighten them after measured
improvements. Preserve native case membership, assertions, and first-pass results.
Before adding concurrency, prove separate mutable databases, ports, temporary
files and owned cleanup, and account for host CPU/memory capacity. Runner counts,
capacity provisioning, sharding and project fixtures stay in the adopter repo.
