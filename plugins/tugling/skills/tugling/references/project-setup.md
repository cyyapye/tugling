# Project setup

Set up Tugling as a thin adapter over a repository's existing engineering contract. The repository remains authoritative; setup should expose its commands and invariants, not replace them.

## 1. Assess without writing

Inspect only what is needed to answer these questions:

- Which root and path-specific instruction files govern work?
- What is the canonical local verification command, and which focused commands shorten iteration?
- Which CI workflow proves the committed revision?
- Which product, data, security, interface, performance, and release rules are genuinely project-specific?
- Is there a clean synthetic scenario that can dogfood the highest-value Tugling decision?
- Which actions still require explicit authority?

Report missing or conflicting facts before proposing files. Do not run installation scripts, mutate a personal marketplace, or edit the repository during this assessment unless the user already authorized setup implementation.

## 2. Propose the smallest adapter

Prefer these project-owned files:

```text
.tugling/project.json       Machine-readable source, commands, and learning mode
.tugling/dogfood.json       One synthetic external-project behavioral case
AGENTS.md                   A short Tugling project adapter section
.github/workflows/...       A deterministic pinned-source compatibility check
.gitignore                  The local correction ledger path
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

## 3. Wire deterministic CI

CI should check out the project, check out Tugling at the configured full revision into an isolated subdirectory, and run:

```text
python3 <tugling-checkout>/plugins/tugling/scripts/project_contract.py \
  --repo <project-checkout> \
  --source-root <tugling-checkout> \
  --source-mode pinned
```

The project's native CI remains responsible for its build and test gates. The Tugling check verifies the adapter, source pin, dogfood case, instruction paths, and local-learning privacy boundary without calling a model or using the network.

Run live model dogfood upstream or as an explicit maintainer action, not on every adopter pull request. The external case can be passed to `scripts/behavioral_eval.py project` from a clean local checkout.

## 4. Verify setup

Before calling setup complete:

1. Run the project-contract check from the exact Tugling source named in the adapter.
2. Run the repository's canonical local gate unless the user requested configuration-only work and the repository contract permits a narrower proof.
3. Confirm the correction ledger path is ignored and untracked.
4. Confirm the dogfood case is synthetic and contains no project secrets or private records.
5. If pushed, wait for the exact project revision's native and Tugling CI checks.

Report the Tugling version and revision, adapter paths, learning mode, local and remote evidence, and any update channel that remains intentionally unverified.
