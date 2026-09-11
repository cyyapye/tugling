# Attested, reviewed stable promotion

`promote-stable.yml` consumes the two signed files from a successful
[certification run](release-certification.md). It verifies provenance, waits for
maintainer approval, atomically publishes `stable` and the version tag, and checks
a fresh public installation in the same workflow. Promotion never calls a model.
Ordinary push and PR checks remain deterministic and credential-free.

The workflow stays disabled while `TUGLING_RELEASE_CONTROLLER_SHA` or
`TUGLING_CERTIFICATION_CONTROLLER_SHA` is unset. Merging this code does not approve
a controller, enable paid certification, or publish a plugin release.

## Evidence and execution boundaries

The workflow uses four separate standard GitHub-hosted Ubuntu jobs:

1. **Preflight:** use the tag-restricted `tugling-release-policy` environment and
   check out the independently pinned promotion controller. Mint a short-lived
   policy App token for this repository and check the full protection settings,
   including bypass actors, before candidate work or human approval. Download the exact certification artifact and
   verify both files with `gh attestation verify`. Check the certificate against
   the candidate package, exact main/stable refs, and the successful latest push
   `Verify` run. Write the release identity, certificate digest, and observed
   usage to the workflow summary for the maintainer to review.
2. **Candidate verification:** check out the exact candidate with `contents: read`
   and `persist-credentials: false`, and run `make verify`.
3. **Promotion:** wait for approval in `tugling-stable`, then start a fresh runner
   with `contents: write`. Check out only the pinned controller and mint a fresh
   policy App token from this environment's protected secret. Independently
   download and verify the evidence again, check protection settings including
   bypass actors, and require the maintainer's recorded approval for this run.
   Candidate jobs do not supply executable code, caches, or authorization outputs
   to this job. Publish only after all checks pass.
4. **Canary:** start a fresh runner with `contents: read`. Install Codex CLI
   `0.153.4`, then install `tugling@tugling` through the public **stable alias** in
   a fresh home without account credentials. Require the marketplace revision,
   installed package content, and annotated version tag to match the exact
   promoted commit. Read stable/tag refs again after installation.

The certificate and envelope must each have a valid GitHub Actions attestation
from `cyyapye/tugling/.github/workflows/certify-release.yml` at the separately
approved certification controller SHA, using a GitHub-hosted runner. Verification
pins both signer and source digests, the controller tag ref, and the signed
invocation URL for the exact run and first attempt. The entire certification
workflow must have completed successfully; reruns, fork workflows, expired or
ambiguous artifacts, and unsuccessful signing jobs are rejected.

The signed envelope binds the certificate digest, exact candidate SHA, exact
stable baseline, controller SHA, run/attempt, reviewed model/runtime, complete
91-task matrix, and observed usage. The reviewing maintainer supplies the
certificate digest separately. The controller compares the certificate with
regular package files extracted from Git objects. **An ancestor's certificate
cannot certify a later commit**, even when the plugin content is unchanged.
Committed legacy certificates are historical records and cannot authorize this
promotion path. Never commit an external certificate to manufacture a new release
candidate after certification.

The controller owns `Makefile`, `.github/**`, `.agents/**`, `scripts/**`,
`tests/**`, and `evals/**` except `evals/releases/**`. Both approved controllers'
ruler files must match the candidate exactly, and both must be ancestors of the
candidate. Changes to evaluators, fixtures, tests, thresholds, workflow pins, or
release policy need separate review and new controller pins. Passing tests from
the changed candidate does not provide that independent approval.

## GitHub protection settings

[release-policy.json](../.github/release-policy.json) contains the administrative
API payloads. Configure these settings independently of CI; the workflow only
reads them and fails closed on drift:

| Control | Enforced behavior |
| --- | --- |
| Stable integrity ruleset | Prevent deletion and non-fast-forward updates to `stable`, with no bypass actors |
| Immutable release refs ruleset | Prevent updates and deletion of existing `v*` and `controller-*` tags, with no bypass actors |
| Controller approval ruleset | Only repository administrators can create new `controller-*` tags |
| `tugling-stable` environment | Require approval by `cyyapye`, disable administrator bypass, and admit only `controller-*` **tags** |
| `tugling-release-policy` environment | Admit only `controller-*` **tags** for the preflight policy credential; disable administrator bypass |

Self-review is allowed so the sole maintainer can dispatch a release and then
explicitly approve it after reviewing the preflight summary. This is a human
approval step, not a two-person review requirement. The agent must not approve
this environment automatically.

These public-repository controls are available on GitHub Free. They protect ref
integrity and the reviewed workflow's approval boundary. They do **not** make the
workflow an exclusive release identity: another write-enabled workflow or a
repository writer can still create a version tag or fast-forward stable. Pins,
workflow review, and permission to administer settings remain trust roots.
`CODEOWNERS` identifies policy owners but does not itself enforce PR approval.
An exclusive machine identity would need a separately configured GitHub App and
stricter actor restrictions; this workflow does not claim that isolation.

To configure a new repository, review the checked-in payloads, create the three
rulesets with `POST /repos/cyyapye/tugling/rulesets`, create/update the environment
with `PUT /repos/cyyapye/tugling/environments/tugling-stable`, and create its tag
policy with `POST .../deployment-branch-policies`. Read all settings back before
activation. Preserve unrelated settings; do not create duplicate named rulesets.
Both preflight and the writer require visible bypass-actor data. GitHub requires
**write access to the ruleset** to reveal `bypass_actors`; `contents: write` and
`write-all` on the built-in `GITHUB_TOKEN` do not supply that administration
permission. An omitted field is an access failure, not evidence of an empty list
or a changed policy. The guard reports `PROTECTION_ACCESS_MISSING` separately and
continues to reject observed bypass changes.

### Policy App setup

Create a private GitHub App under `cyyapye`, installed only on `cyyapye/tugling`.
Grant repository **Administration: read and write**, plus GitHub's automatic
Metadata read permission. Leave webhooks, user authorization, account access,
and all other optional permissions disabled. Administration write can change
rulesets; GitHub does not provide a read-only permission for this visibility.
Our integration uses it only for ruleset GET requests. It is not a release writer
and must not be added to any ruleset bypass list.

Store its client ID in the repository variable `TUGLING_POLICY_APP_CLIENT_ID`.
Store the same private key as the environment secret
`TUGLING_POLICY_APP_PRIVATE_KEY` in **both** `tugling-release-policy` and
`tugling-stable`. Do not create a repository-wide copy. Create the audit
environment with no required reviewers, administrator bypass disabled, and the
same single `controller-*` tag policy as the release environment. Preflight can
then detect configuration errors before requesting the existing human release
approval. Read back the two environment scopes before installing the secrets.

The pinned official `actions/create-github-app-token` action scopes each token
to `tugling` and Administration write, masks it, and revokes it at job cleanup.
The normal workflow token continues to read evidence and publish refs. The App
token is passed only to ruleset reads and removed from child-process environments.
Candidate verification and the installation canary receive neither the private
key nor the App token. No App credentials are available to PR or ordinary push
checks. Key rotation updates the two protected secret copies together.

App creation and these credentials do not activate revised controller code.
After merging, the changed workflow and guards still require separate controller
review and pin updates. An existing certificate remains bound to its original
candidate and controller; this infrastructure change does not extend it.

## Controller activation and release review

After independent review of the final merged controller commit and successful
native/remote verification:

1. Create a new protected `controller-*` tag at that commit. Never move an old
   controller tag. Set the separately reviewed full SHAs in
   `TUGLING_RELEASE_CONTROLLER_SHA` and `TUGLING_CERTIFICATION_CONTROLLER_SHA`.
   Neither variable is supplied by a candidate job or updated from CI.
2. Obtain a successful certification for a new plugin version with separately
   approved API credentials and token thresholds. Download both sanitized JSON
   files and review the certificate's checks, scores, identity, and usage.
   Calculate the SHA256 of the original `certificate.json` bytes.
3. Dispatch `promote-stable.yml` from the promotion controller tag, supplying
   `candidate_sha`, `version` without `v`, `certification_run_id`, and
   `certificate_sha256`. The candidate must still be exact current main.
4. Review the preflight summary and candidate verification. Approve the waiting
   `tugling-stable` environment in GitHub. Require the entire workflow, including
   the inline canary, to complete successfully before reporting install success.

The certification artifact has seven-day retention. Missing or expired evidence
fails closed. Keep reviewed release evidence and its attestation bundles outside
that short-lived artifact store. This workflow does not automatically reconstruct
missing certificates or authorize additional model charges.

## State transitions and recovery

- **New release:** require current main, the certified stable baseline, and an
  absent version tag. Verify ancestry, create an annotated version tag, and push
  stable plus tag atomically with a lease on the exact previous stable SHA.
- **Completed retry:** when stable and the annotated tag already resolve to the
  requested candidate, return `ALREADY_PROMOTED` without writes and run the canary.
  The evidence must still be available and main must still match for a full rerun.
- **Concurrent identical target:** an already identical stable ref can converge
  by creating the absent version tag. A different stable target rejects the push.
- **Stale/conflicting refs, changed rulers, bad provenance, or policy drift:**
  stop without publication. Do not silently switch to a different candidate.
- **Receive rejection:** the atomic push leaves both refs unchanged by this
  request. There is no fallback to two separate pushes.
- **Lost response or failed readback:** report `PROMOTION_BLOCKED_OR_UNCONFIRMED`.
  Inspect stable and the peeled tag before retrying the same intent.
- **Installation failure:** leave published refs in place, fail the workflow,
  and report `PROMOTED_CANARY_FAILED`. A CLI setup failure also leaves the canary
  job failed. Fix the runtime/network issue and rerun only the failed canary job;
  that job verifies the same published pair and does not download certificates,
  write refs, or call a model. If stable has since moved, do not reinstall or
  overwrite the newer release. A product defect needs a new version and evidence.

Only `PROMOTED_AND_INSTALL_VERIFIED` proves the fresh stable-alias installation.
It does not claim a new live model evaluation; paid behavioral/discovery proof
comes from the preceding certification. The final main read is a freshness check,
not a transaction lock on main. Atomicity covers stable and the version tag.
The canary is inline because a `GITHUB_TOKEN` push does not trigger another push
workflow. There is no automatic rollback, tag deletion, model rerun, or retry loop.

### Record an operator recovery

A successful local recovery does not update an Actions-created deployment.
Preserve the failed attempt and append a separate verified recovery record with:

```sh
python3 -I scripts/record_release_recovery.py \
  --promotion-run-id ORIGINAL_FAILED_RUN \
  --codex-bin /absolute/path/to/pinned/codex \
  --out /absolute/path/to/recovery.json
```

The default is read-only. The command reconstructs the exact release identity
from the original run's successful preflight log, verifies its human approval,
checks both original attestations and the current full policy, requires the
publication controller's `ALREADY_PROMOTED` result, and performs a fresh free
stable-alias installation. Thus main must still match the candidate and the
original certification artifacts must remain available. A log or artifact that
has expired, a rerun, changed refs, or failed installation blocks reporting.

After reviewing that result, the authorized operator can repeat with `--apply`.
Every invocation verifies again; a JSON success flag from disk is never accepted
as proof. This writes only deployment metadata for the exact candidate under
task `tugling:recovery`, explicitly labeled `local-operator-verification`. It does
not publish refs, approve an environment, or start certification. The original
failed deployment is neither overwritten nor marked inactive. Sequential retries
reuse the matching recovery record, including after a lost create response;
ambiguous duplicates require inspection. Concurrent operators should not run it
for the same intent. The final ref read is a freshness check, not a transaction
lock on subsequent publication.

## Verification and limits

Run `make verify` and `actionlint`. Tests use real disposable Git remotes and
atomic pushes for publication, races, duplicate convergence, and canary recovery.
Provider-boundary tests inject API/verified-result fixtures to test policy and
unsafe archives; these synthetic fixtures do not prove a real CI attestation.
Use the real pinned CLI for the free public installation smoke and the actual
installed App for an independent ruleset-visibility check. Unit fixtures do not
prove the GitHub credential configuration. New live attested releases remain
separate maintainer-approved certification and promotion operations.

Each promotion job is limited to ten minutes. Git/CLI requests time out after
120 seconds. Candidate package extraction is capped at 2,000 files and 16 MiB;
each evidence file at 256 KiB and its archive at 600 KiB. Promotion uses standard
public runners, no shared caches, no model/API credentials, and no paid GitHub
features. GitHub CLI provides cryptographic verification against Sigstore's
trusted roots; policy checks inspect only successfully verified statements.

References: [GitHub attestation verification](https://cli.github.com/manual/gh_attestation_verify),
[repository rulesets API](https://docs.github.com/en/rest/repos/rules),
[GitHub App tokens in Actions](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/making-authenticated-api-requests-with-a-github-app-in-a-github-actions-workflow),
[environment protection](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments).
