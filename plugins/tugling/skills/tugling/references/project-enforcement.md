# Enforce native project rules

Use when full Tugling adoption or explicit rule enforcement is requested. Reuse
the [adoption adapter](project-adoption.md) and preserve accepted project policies.
Configuration-only and assessment requests keep their narrower scope.

## Make accepted rules executable

For full setup in a new or existing project, read the
[native flow contract](../../repo-verify/references/project-flows.md). Reuse or
add assertions in the project's native test framework, then map each accepted
rule to the commands that enforce it. The model selects and reviews coverage
during setup; subsequent gates execute ordinary programs without a model judge.
Do not invent a universal resource budget or impose a particular UI library.

Use the applicable project evidence:

| Project rule | Native failure proof |
| --- | --- |
| Efficient user workflow | Exercise the smallest valid submission and routine automatic updates; assert required decisions and review exceptions. |
| Shared UI implementation | Architecture/lint checks reject bypassing the project's shared components; browser evidence covers behavior and responsive layout. |
| Performance and operating cost | Exercise actual query/API/worker paths at the accepted aggregate workload, including idle and failure activity; compare counts and latency to project limits with headroom. |
| Artifact capacity and ownership | Exercise success, failure, cancellation, and expiry; assert owned count/bytes stay bounded and active/foreign artifacts survive cleanup. |

Inspect the actual assertions, test discovery, skips, and lifecycle ownership.
A command named `check-budget` or a formula copied from the implementation is
insufficient proof. Every declared rule needs an existing flow; one flow can
cover several rules. Reuse policy sources, tests, and runners rather than adding
a parallel assertion framework. Record exclusions and unresolved coverage in
the project contract; do not silently omit an accepted rule to obtain a pass.

Demonstrate that a relevant known defect fails through the required entry point
in an isolated synthetic checkout, then restore the good implementation and
show it passes. Include a focused-pass/full-required-fail case when distinct
checks exist. Configure native completion to account for the reviewed required test set, not
just whichever cases discovery still finds. Where omission can exit successfully,
compare stable individual case identities and outcomes against a committed,
reviewed inventory; include runner variants and explicit existing exclusions.
File presence and a total count cannot detect deleting or replacing one case in
a nonempty file. Inventory refresh is a separate maintainer action, never part
of required execution. This proves membership, not assertion quality: inspect
changed assertions as well.

Keep focused iteration available, but reject selection and reporter overrides at
the required entry point. Filters, skip/only markers, environment variables, and
runner arguments must not narrow required execution or replace its accounting.
Exercise the real native runner with a removed case, a skipped case, and a filter
that would otherwise return success. Preserve established platform exclusions
explicitly instead of adding retries or silently accepting missing coverage.

For a configuration-only request, add only the authorized adapter/configuration
and report missing assertions or integration as incomplete enforcement. A
read-only assessment does not authorize edits. Full setup authorizes test and
build/CI wiring; changing product behavior still needs task authority.

## Wire the canonical gate and CI

Validate the adapter with the reviewed Tugling source:

```text
python3 -I <tugling-checkout>/plugins/tugling/scripts/project_contract.py \
  --repo <project-checkout> \
  --source-root <tugling-checkout> \
  --source-mode pinned
```

This command validates the adapter, source pin, dogfood case, map, instruction
paths, and local-learning privacy boundary. It does not execute native checks.

Wire `--run-required` into the repository's canonical command and its ordinary
unprivileged CI job. Preserve unrelated build/test gates. Choose one execution
direction: canonical command → required helper → native leaf commands; or
required helper → an existing self-contained canonical command, with the helper
outside that command. Do not wire both directions or run the same suite twice.
The inherited execution guard rejects recursive native helper calls.

Use a project-owned launcher before executing a helper from a supplied source
checkout. Verify the supplied directory is the actual Git root, its revision is
the reviewed pin, and its tracked contents are clean. Reject symlinked helpers,
index skip/assume flags, and helper bytes that differ from that commit's Git blob.
An ignored nested directory can inherit a parent's clean Git identity while
containing an untracked replacement helper. Validation inside that replacement
runs too late; source validation must precede its execution. Reuse an existing
launcher that establishes this boundary rather than adding a second wrapper.

Bind the helper's imported code as well as its main file. Launch this single-file,
standard-library Python helper with `-I` for validation, execution, and receipt
checks. An ignored adjacent `json.py` can execute during import even when the
helper bytes and Git status are correct. Demonstrate that such a module never
executes; either reject the contaminated source first or isolate the import path
and validate the real result. Apply the same boundary to other runtimes' module
paths and startup hooks when they can substitute code from a supplied source.

When `make verify` owns the required gate, route it through that launcher to
`--run-required` and map independent native leaf commands. When the required
helper wraps an already self-contained `make verify`, keep the launcher outside
that canonical command.

Merge with the existing build targets; preserve one execution direction. For local iteration,
run the leaf commands while editing; required execution binds evidence to a
clean committed project checkout. Use an isolated checkout when unrelated work
is dirty; preserve that work instead of committing or discarding it for the gate.

CI checks out the project and the accepted Tugling revision into **sibling**
directories, or uses an explicitly ignored source directory. An untracked nested
checkout makes the project dirty and is refused. Select the intended project revision explicitly in CI and assert `git rev-parse
HEAD` against that expected identity before execution. A pull-request checkout
may default to a synthetic merge commit: use the PR head when claiming head
verification, or label merge-commit evidence as such. Preserve useful existing
merge checks without presenting them as proof for different source bytes.

Run the same canonical command
with the reviewed source path, so a missing declaration or failed check exits
nonzero. Execute the required gate in each CI job; do not reuse an old local
receipt as evidence that this job ran. Required checks must not be optional,
allowed to fail, or conditionally skipped for relevant changes.

Inspect the hosted required-check configuration before claiming merge enforcement.
If changing branch protection needs separate authority, finish the local/CI
implementation and report that remaining boundary. The helper does not configure
or attest hosted protections. Do not silently change a project's accepted source
pin to an unreleased candidate; exercise candidate setup in an isolated checkout.

Run live model dogfood upstream or as an explicit maintainer action, not on every adopter pull request. The external case can be passed to `scripts/behavioral_eval.py project` from a clean local checkout.

## Verify enforcement

Before calling setup complete:

1. Run the project-contract check from the exact Tugling source named in the adapter.
2. Run the repository's canonical local gate and complete required coverage; inspect a `REQUIRED_PASS` receipt plus the known-defect failure proof. For configuration-only work, state the narrower proof and outstanding enforcement.
3. Confirm `.tugling/local/` is ignored and untracked even when correction learning is off. Use the project's bounded artifact cleanup policy for retained evidence.
4. Confirm the dogfood case is synthetic and contains no project secrets or private records.
5. If pushed, wait for the exact project revision's native and Tugling CI checks.
6. For a setup change intended to prevent recurrence, validate first-time setup
   from untouched source before testing a repeat no-op. A clean repeat on a
   manually corrected setup does not prove the first setup was complete.

Report the Tugling version and revision, adapter paths, learning mode, rule-to-test
coverage, local/remote/merge enforcement evidence, and unresolved boundaries.
When later features introduce or change a rule, workload, resource, or cleanup
path, update its policy, native assertion, and required map in the same change.
