# Native project flows

Use this optional adapter when a repository needs a durable mapping from user
behavior to its existing checks. Keep the repository's instructions, native
test framework, and canonical completion gate authoritative.

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

## Optional map

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

## Validate, then execute explicitly

The ordinary project-contract command also validates a configured map. It never
executes mapped commands without `--run-flow`:

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

## Evidence and scope

Each run writes a new permission-restricted JSON receipt under the ignored,
untracked `.tugling/local/verification/` directory. This storage is independent
of whether correction learning is enabled. It contains the project commit,
config/map/helper digests, Tugling identity and checkout cleanliness, selected commands, exit results,
cleanup outcome, timestamps, and whether the worktree stayed clean. It does not
store command logs, environment variables, application data, or screenshots.
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

Keep `--run-native` for the canonical gate; it is mutually exclusive with flow
execution and receipt checking. A focused flow pass cannot replace a required
canonical gate or raise the overall readiness state by itself. Recheck receipts
before citing them after a commit, map, config, or helper change. Failed, stale,
dirty, incomplete, and missing evidence never become a pass.

## CI and adoption

Keep ordinary adapter CI on validation only. A repository may explicitly run
mapped flows in its existing unprivileged native test job, under the same trust
and fixture rules as those tests. Do not execute contributor-defined commands
with maintainer secrets or through a privileged pull-request trigger. No model
evaluation or paid certification is part of this adapter.

Pilot against a clean isolated adopter checkout, use its native desktop/mobile
checks, inspect required artifacts, and verify owned services are gone. Report
the tested commit and selected flow scope separately from the canonical gate and
remote status. Keep adopter source, raw logs, local paths, and private evidence
out of the reusable plugin and its release certificate.
