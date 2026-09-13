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
the native assertion fail through the required entry point. Required empty or
skipped suites must fail in the native runner. Existing maps may omit
`requirements` for compatibility; that is not required enforcement, and
`--run-required` refuses an absent or empty declaration.

## Validate, then execute explicitly

The ordinary project-contract command also validates a configured map. It never
executes mapped commands without an execution flag:

```text
python3 <tugling-checkout>/plugins/tugling/scripts/project_contract.py \
  --repo <project-checkout> --source-root <tugling-checkout> --source-mode pinned
```

Run selected flows from a clean committed project checkout:

```text
python3 <tugling-checkout>/plugins/tugling/scripts/project_contract.py \
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
python3 <tugling-checkout>/plugins/tugling/scripts/project_contract.py \
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
untracked `.tugling/local/verification/` directory. This storage is independent
of whether correction learning is enabled. It contains the project commit,
config/map/helper digests, Tugling identity and checkout cleanliness, selected commands, exit results,
cleanup outcome, timestamps, and whether the worktree stayed clean. It does not
store command logs, environment variables, application data, or screenshots.
Required receipts also contain the complete requirement-to-flow declaration.
Native reports and screenshots remain in the project's existing artifact paths;
inspect them when required by the project. Remove old local receipts through an
explicitly scoped cleanup when no longer needed; nothing uploads automatically.

To check a receipt against the current clean checkout:

```text
python3 <tugling-checkout>/plugins/tugling/scripts/project_contract.py \
  --repo <project-checkout> --source-root <tugling-checkout> --source-mode pinned \
  --check-flow-evidence .tugling/local/verification/<run-id>.json --json
```

`FLOWS_PASS` proves only the selected native commands exited successfully for
that clean commit and their owned process groups finished. It does not prove
every feature, screenshot quality, the canonical gate, remote CI, deployment,
or absence of behavior outside the tests. Dependencies and ignored runtime
inputs still follow the native repository's trust contract. This editable local
receipt is a freshness and scope aid, not a signed release attestation.

Check complete required evidence with:

```text
python3 <tugling-checkout>/plugins/tugling/scripts/project_contract.py \
  --repo <project-checkout> --source-root <tugling-checkout> --source-mode pinned \
  --check-required-evidence .tugling/local/verification/<run-id>.json --json
```

This requires a `REQUIRED_PASS` receipt, the exact current requirements and
complete ordered flow set, matching clean project/config/map/helper identity,
and one successful matching result for every command. A selected receipt is
insufficient even when it happens to name all flows. `REQUIRED_PASS` proves the
declared native checks ran successfully; it cannot certify undeclared behavior,
assertion quality, hosted CI, or release readiness. A receipt can remain valid
on the same clean commit; checking it does not rerun tests or prove a new CI job.

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
