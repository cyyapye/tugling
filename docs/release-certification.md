# Maintainer-triggered Pstack release certification

`certify-release.yml` certifies a reviewed Codex compatibility report, the exact
candidate package, and a fresh public installation. It makes no model calls and
needs no model API key or token allowance. Ordinary push and PR checks remain
deterministic. The older questionnaire and recovery runner remain available only
for [explicit diagnostics](legacy-diagnostics.md).

Certification produces two attested JSON files. It does not merge, publish refs,
move `stable`, approve a release environment, or change controller pins.

## What the review establishes

The controller-owned [policy](../evals/pstack/release-policy.json) requires observed
workflows across discovery/setup, planning scope, repair/regression, verification
honesty, capability fallbacks, history scope, skill authoring, and idle scope.
The candidate supplies a bounded, sanitized report at
`evals/releases/v<version>/pstack-review.json`.

The report binds the exact package content, upstream revision, runtime, frozen
attempt inventory, private evidence hashes, rubric counts, observed builder usage,
blind review and parent trace audit. It preserves failed attempts. A failed
environment attempt can be resolved only by a later passing attempt with the same
scenario, runtime, task digest, areas and criteria count, using the explicitly
granted skill directory. The original failure remains failed. Behavioral failures
cannot be relabeled as successful or erased by an automatic retry.

The report must disclose same-family review, development tasks rather than
holdouts, incomplete catalog behavior coverage, no enhancement claim, and usage
limited to builders. A directory-granted repeat also discloses its environment
and longer timeout. These are compatibility observations, not a claim that every
one of the 54 skills works in every setting or that Tugling outperforms Pstack.

**Maintainer approval of the exact report digest is the semantic trust boundary.**
The validator checks identity, schema, consistency, required observations and
limits. Private evidence hashes do not independently prove that runs happened,
that their judgments are correct, or that no attempt was omitted. Review the
underlying evidence before approving its sanitized summary. A changed report
needs a newly approved digest; changed package bytes need matching observations.
Executable modes are checked against the independently approved controller and
preserved during extraction, separately from the historical content hash.

## Configure and authorize

After independent review of the final merged controller commit, configure:

| Setting | Purpose |
| --- | --- |
| `TUGLING_CERTIFICATION_CONTROLLER_SHA` | Full independently approved controller commit SHA |
| `TUGLING_CERTIFICATION_ENABLED=true` | Enable manual reviewed certification |
| `TUGLING_PUBLIC_POLICY_PATTERNS` secret | Existing configured public-content scan patterns |

The promotion pin `TUGLING_RELEASE_CONTROLLER_SHA` is approved separately.
Merging the code does not approve either pin or enable certification. Existing
API-key and token-ceiling settings are used only by explicitly authorized legacy
diagnostics; this workflow neither reads nor spends them.

Dispatch `certify-release.yml` from a protected `controller-*` tag whose commit
matches the certification pin. Supply:

- `candidate_sha`: exact current `main` SHA.
- `baseline_sha`: exact current `stable` SHA.
- `review_sha256`: SHA256 of the original committed report bytes.
- `approve_reviewed_evidence=true`: acceptance of that report and its stated limits.

Only first-attempt manual runs in `cyyapye/tugling` qualify. The controller checkout
must be clean and match the pin. Candidate code cannot approve or update the pins.

## Execution and attestation

The first fresh GitHub-hosted runner:

1. Requires the latest push `Verify` run for exact current main to have succeeded.
2. Fetches the candidate and baseline; requires the reviewed controller ancestry,
   exact controller-owned files, a new package version and absent version tag.
3. Reads the fixed report from Git objects, checks its approved digest and package
   identity, validates source attribution against the controller's reviewed
   inventory, checks executable modes, and scans public package content.
4. Installs Codex CLI `0.153.4` and the exact public candidate in a fresh home
   without account credentials. Checks marketplace and installed package bytes and
   executable modes. This installation does not invoke a model.
5. Rechecks main and stable freshness and writes `certificate.json` and
   `certification.json`, both schema version 2.

A separate fresh runner reauthorizes the same dispatch, rechecks successful CI,
refs, controller files, source inventory, modes and exact approved report, and
validates both artifact files before signing them with GitHub Actions attestations.
It does not rerun a model or accept a candidate script as a validator.

The certificate binds the compatibility report, policy digest, package and exact
candidate/baseline. The envelope binds the certificate's original byte digest,
report digest, controller, repository, run and first attempt. Both are uploaded
under `certification-<candidate>-<run>-<attempt>` with seven-day retention.
Raw model output, private paths, credentials and adopter data stay outside Git
and these artifacts.

## Promotion and verification

Review the complete successful workflow and the two signed files, then follow
[stable promotion](release-controller.md). Active promotion accepts only schema 2;
legacy certificates cannot authorize it. The maintainer supplies the certificate
digest separately and must approve the protected `tugling-stable` environment.
Successful publication also requires a fresh stable-alias installation canary.

Run `make verify` and `actionlint` for controller changes. Tests use disposable
Git repositories and synthetic evidence to exercise rejection, report integrity,
failed-attempt preservation, exact public-install boundaries, artifact provenance,
atomic publication and recovery. They make no model calls and do not create real
GitHub attestations. Passing them does not approve a controller or a release.
