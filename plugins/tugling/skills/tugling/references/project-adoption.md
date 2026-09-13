# Adopt Tugling in an existing repository

Read when the user requests a Tugling adapter. Establish the repository's native
workflow first when it also needs bootstrap. Discover its canonical verification
command, exact-revision CI, project-specific invariants, and one synthetic case
that exercises a useful Tugling decision.

## Add the smallest adoption adapter

Prefer these project-owned files:

```text
.tugling/project.json       Machine-readable source, commands, and learning mode
.tugling/dogfood.json       One synthetic external-project behavioral case
.tugling/verification.json  Accepted rules mapped to required native checks
AGENTS.md                   A short Tugling project adapter section
.github/workflows/...       A deterministic pinned-source compatibility check
.gitignore                  Ignored local receipts and correction ledger
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

## Wire deterministic CI

CI should check out the project, check out Tugling at the configured full revision into an isolated subdirectory, and run:

```text
python3 -I <tugling-checkout>/plugins/tugling/scripts/project_contract.py \
  --repo <project-checkout> \
  --source-root <tugling-checkout> \
  --source-mode pinned
```

The project's native CI remains responsible for its build and test gates. The Tugling check verifies the adapter, source pin, dogfood case, instruction paths, and local-learning privacy boundary without calling a model or using the network.

For full adoption, read [native enforcement](project-enforcement.md). Reuse or
add native assertions for accepted rules, declare the required map, and wire one
complete canonical/CI execution path. A configuration-only request may stop at
adapter validation and report the remaining enforcement work. Do not silently
replace an accepted release pin with an unreleased candidate; use an isolated
pilot when candidate setup was authorized.

Run live model dogfood upstream or as an explicit maintainer action, not on every adopter pull request. The external case can be passed to `scripts/behavioral_eval.py project` from a clean local checkout.

## Verify adoption

1. Run the project-contract check from the exact Tugling source named in the adapter.
2. For full adoption, complete the native enforcement reference, including required receipts and known-defect failure proof. Run the repository's canonical local gate unless the user requested configuration-only work and the repository contract permits a narrower proof. Repair in-scope failures and rerun affected checks within existing authorization.
3. Confirm the correction ledger path is ignored and untracked.
4. Confirm the dogfood case is synthetic and contains no project secrets or private records.
5. If pushed, wait for the exact project revision's native and Tugling CI checks.

An adapter validation alone cannot prove bootstrap, native flows, or remote CI.
If the exact source or a required external check is unavailable, complete
independent work and report the missing boundary without inventing a pin or
calling adoption complete.

Report the adopted version and revision, changed setup paths, learning mode,
local and remote evidence, and any required boundary still unverified.
