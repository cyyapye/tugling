# Project setup

Set up Tugling as a thin adapter over a repository's existing engineering contract. The repository remains authoritative; setup should expose its commands and invariants, not replace them.

## 1. Assess without writing

Inspect only what is needed to answer these questions:

- Which root and path-specific instruction files govern work?
- What is the canonical local verification command, and which focused commands shorten iteration?
- Which CI workflow proves the committed revision?
- Which product, data, security, interface, performance, cost, artifact, and release rules apply, and where are their accepted limits recorded?
- Which native assertions enforce those rules today, and which can silently skip or omit them?
- Is there a clean synthetic scenario that can dogfood the highest-value Tugling decision?
- Which actions still require explicit authority?

Report missing or conflicting facts before proposing files. Do not run installation scripts, mutate a personal marketplace, or edit the repository during this assessment unless the user already authorized setup implementation.

## 2. Propose the smallest adapter

Prefer these project-owned files:

```text
.tugling/project.json       Machine-readable source, commands, and learning mode
.tugling/verification.json  Accepted rules mapped to required native checks
.tugling/dogfood.json       One synthetic external-project behavioral case
AGENTS.md                   A short Tugling project adapter section
<native tests/build files>  Existing assertions and canonical verification target
.github/workflows/...       Pinned-source validation and required native execution
.gitignore                  The .tugling/local/ evidence and correction directory
```

Do not copy generic Tugling skills into the project. Do not duplicate all existing instructions inside `AGENTS.md`; link to the authoritative files and add only the routing facts Tugling needs.

Use this configuration shape:

```json
{
  "schema_version": 1,
  "tugling": {
    "repository": "https://github.com/OWNER/tugling",
    "channel": "pinned",
    "revision": "FULL_40_CHARACTER_COMMIT",
    "version": "RELEASE_VERSION"
  },
  "project": {
    "adapter": "AGENTS.md",
    "instructions": ["AGENTS.md"],
    "canonical_verify": ["make", "verify"],
    "verification": ".tugling/verification.json",
    "ci_workflow": ".github/workflows/tugling.yml",
    "dogfood_case": ".tugling/dogfood.json"
  },
  "learning": {
    "mode": "off",
    "local_path": ".tugling/local/corrections.jsonl"
  }
}
```

Use an argv array for verification so CI never evaluates a shell string. A pinned channel requires the exact released commit. A stable channel follows the maintained stable branch and sets `revision` to `null`. A preview channel follows the default development branch and also sets `revision` to `null`. Prefer pinned for regulated, sensitive, or exact-revision workflows.

The dogfood file must declare `data_policy` as `synthetic-only` and contain one behavioral case compatible with Tugling's external-project evaluator. Keep real source data, user records, transcripts, credentials, and private prompts out of it.

## 3. Make accepted rules executable

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
checks exist. Configure the native runner to fail when required tests are
missing or skipped; the helper can observe a process exit, not infer assertions
from its name. Keep test changes reviewable and preserve required local artifacts.

For a configuration-only request, add only the authorized adapter/configuration
and report missing assertions or integration as incomplete enforcement. A
read-only assessment does not authorize edits. Full setup authorizes test and
build/CI wiring; changing product behavior still needs task authority.

## 4. Wire the canonical gate and CI

Validate the adapter with the reviewed Tugling source:

```text
python3 <tugling-checkout>/plugins/tugling/scripts/project_contract.py \
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

For example, when `make verify` owns the required gate:

```make
.PHONY: verify verify-required
verify: verify-required

verify-required:
	@test -n "$(TUGLING_SOURCE)" || { echo "Set TUGLING_SOURCE to the reviewed checkout" >&2; exit 1; }
	python3 "$(TUGLING_SOURCE)/plugins/tugling/scripts/project_contract.py" \
	  --repo . --source-root "$(TUGLING_SOURCE)" --source-mode pinned --run-required
```

Merge this dependency into the existing target. Map its independent native
commands, never `make verify` itself in this arrangement. For local iteration,
run the leaf commands while editing; required execution binds evidence to a
clean committed project checkout. Use an isolated checkout when unrelated work
is dirty; preserve that work instead of committing or discarding it for the gate.

CI checks out the project and the accepted Tugling revision into **sibling**
directories, or uses an explicitly ignored source directory. An untracked nested
checkout makes the project dirty and is refused. Run the same canonical command
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

## 5. Verify setup

Before calling setup complete:

1. Run the project-contract check from the exact Tugling source named in the adapter.
2. Run the repository's canonical local gate and complete required coverage; inspect a `REQUIRED_PASS` receipt plus the known-defect failure proof. For configuration-only work, state the narrower proof and outstanding enforcement.
3. Confirm `.tugling/local/` is ignored and untracked even when correction learning is off. Use the project's bounded artifact cleanup policy for retained evidence.
4. Confirm the dogfood case is synthetic and contains no project secrets or private records.
5. If pushed, wait for the exact project revision's native and Tugling CI checks.

Report the Tugling version and revision, adapter paths, learning mode, rule-to-test
coverage, local/remote/merge enforcement evidence, and unresolved boundaries.
When later features introduce or change a rule, workload, resource, or cleanup
path, update its policy, native assertion, and required map in the same change.
