# Reviewed release controller

The release workflow separates candidate execution from repository write authority.
This is the first release-hardening slice: live model evidence is still produced
and reviewed manually. CI-generated attestations, protected release refs, an
environment approval gate, and post-promotion installation canaries remain separate
work. Do not enable unattended promotion based on this change.

## Execution and ownership

`promote-stable.yml` must run from the exact commit recorded in the repository
variable `TUGLING_RELEASE_CONTROLLER_SHA`. An unset pin, malformed pin, or different
workflow revision fails before candidate execution. There is no default to `main`,
`stable`, or a dispatch-supplied controller. The write job repeats the pin comparison.

The workflow runs on separate standard GitHub-hosted Ubuntu runners:

1. Authorize the controller revision and validate dispatch inputs.
2. Check out the exact candidate with `contents: read` and
   `persist-credentials: false`, then run its native `make verify`.
3. Check out only the reviewed controller with `persist-credentials: false`.
   Run its Python controller with isolated imports and `contents: write`.

The third job receives only dispatch inputs, not scripts, artifacts, caches, or
output values from the candidate job. It fetches objects into a fresh bare Git
repository, extracts only regular package and certificate files into a temporary
directory, and never checks out the candidate or executes candidate scripts.
Git hooks, system/global Git configuration, and inherited Git configuration
environment variables are disabled. All Actions are pinned to full commit SHAs.

The controller reuses its own `release_gate.py`, `clean_room_install.py`, and
release matrix. The certificate must match both the extracted package and the
SHA256 explicitly supplied by the reviewing maintainer. The current certificate
format binds evaluated plugin content, with an evaluated revision that must be an
ancestor of the candidate; it is not yet an attested full-commit CI certificate.
A digest verifies which bytes were reviewed, not whether claimed model runs happened.

## Controller review and bootstrap

The reviewed controller commit owns `Makefile`, `.github/**`, `.agents/**`,
`scripts/**`, `tests/**`, and `evals/**` except `evals/releases/**`. Promotion rejects
added, removed, or changed files in these paths compared with the pinned controller.
This includes fixture changes, thresholds, evaluators, tests, and action pins.
Changes require an explicit review of the new machinery and a separate controller
pin update. Passing candidate-controlled tests is not that review.

The repository pin and GitHub workflow permissions are administrative trust roots.
The pin check is enforced by the reviewed workflow, not by GitHub independently:
someone able to introduce arbitrary write-enabled workflows or edit settings can
bypass it. `CODEOWNERS` requests review; required review must be configured in
GitHub. Protect workflow changes, controller tags, `stable`, and version tags,
and configure the release environment approval before enabling automated releases.
These controls are available on GitHub Free for this public repository.

For the initial migration, leave `TUGLING_RELEASE_CONTROLLER_SHA` unset. This
intentionally makes the replacement promotion workflow fail closed until the
controller has been reviewed and the remaining release controls are configured.
The currently published `stable` and version tags do not move when this PR merges.

When release activation is authorized:

1. Review the exact controller commit after `make verify` and remote checks pass.
   Review changed judging machinery separately from its own test result.
2. Create an immutable, protected `controller-*` tag at that commit and record
   its full 40-character SHA in `TUGLING_RELEASE_CONTROLLER_SHA` through repository
   settings. Do not derive this variable from a candidate job or update it from CI.
3. Dispatch `promote-stable.yml` using that controller tag as the workflow ref.
   The `candidate_sha` input is the exact current `main` commit; `version` is the
   manifest version without `v`; `certificate_sha256` is the digest of the reviewed
   certificate **from that candidate commit**. GitHub dispatch refs are branch or
   tag names, so the separate SHA comparison prevents ref drift.

For example, inspect the certificate with `git show` and calculate its digest
without serializing or reformatting it:

```bash
git show <candidate-sha>:evals/releases/v<version>/certificate.json | shasum -a 256
```

Controller tags are not plugin version tags. Never move an existing controller
tag when approving a new revision; create a new one and explicitly update the pin.

## State transitions and recovery

Before writing, the controller requires the exact current `main`, matching reviewed
certificate bytes, a matching frozen ruler, and ancestor relationships for both the
evaluated revision and stable baseline. It reads live `main`, `stable`, and the
requested version tag again immediately before deciding whether to write.

- New release: `stable` must still equal the certificate's baseline and the tag
  must not exist. Create an annotated tag and push `stable` plus tag atomically.
  A lease on the expected stable SHA rejects a concurrent different stable target
  after the ancestry check. It is not permission to rewind stable.
- Completed retry: if the tag and `stable` already resolve to the requested
  candidate, report `ALREADY_PROMOTED` without changing refs.
- Identical concurrent target: Git may treat an already identical stable ref as
  up to date; creating the missing tag converges safely to the same requested pair.
- Stale baseline, moved main, conflicting tag, invalid data, or changed ruler:
  fail without writing. Re-evaluate and review the appropriate new candidate.
- Receive rejection: the atomic push leaves both refs unchanged by this request.
- Lost response or failed readback: report an unconfirmed outcome. Inspect both
  refs before retrying the same request; do not delete tags or force a rollback.

The final `main` read is a freshness check, not a transaction lock on `main`.
The Git transaction covers `stable` and the version tag. Each successful write is
followed by live readback of stable and the peeled annotated tag. This proves ref
publication, not successful installation; the future canary must run in the same
workflow because a `GITHUB_TOKEN` push does not trigger another push workflow.

## Verification and cost

Run `make verify`. Controller integration tests use disposable local Git remotes
and actual atomic pushes to test successful publication, duplicate convergence,
tampering, changed graders and thresholds, symlinks, stale refs, concurrent ref
updates, and server-side tag rejection. No test pushes to GitHub or calls a model.
An independent `actionlint` pass should also check the changed workflow syntax.

Jobs are bounded to 2/10/10 minutes. Extracted candidate data is limited to 2,000
files and 16 MiB; individual Git commands time out after 120 seconds. No workflow
artifacts, shared caches, larger runners, paid GitHub features, or live model runs
are added by this slice. Later certification remains promotion-only and needs a
separate model usage budget and short artifact retention within free storage.

GitHub references: [workflow security](https://docs.github.com/en/actions/reference/security/secure-use),
[branch and tag rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository),
[public runner billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions).
