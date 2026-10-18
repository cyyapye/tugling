# Tugling

**Pstack, adapted for Codex.**

Tugling brings [Pstack](https://github.com/cursor/plugins/tree/101b274dd991f694e1f7024be2157e5f3adf07de/pstack) by Lauren Tan to Codex with its familiar skill names and playbooks. Pstack is the default for every workflow. Optional Tugling guidance must demonstrate a substantive advantage before it becomes part of normal use.

It is intentionally portable. Tugling supplies reusable engineering judgment; each repository keeps its own product rules, commands, architecture, security boundaries, and release authority.

## Pstack, adapted for Codex

Start with `$poteto-mode` and describe the task. Use `$poteto-help` to choose a
focused skill. The port preserves Pstack's 54 skill names, 24 principles, and
task playbooks so existing users can carry their habits into Codex.

| What you want | Familiar entry point |
| --- | --- |
| Carry a task through the appropriate playbook | `$poteto-mode` |
| Understand how code works or why it was designed that way | `$how`, `$why`, `$teach` |
| Design the shape before implementation | `$architect`, `$arena` |
| Review a change and its effects outside the diff | `$interrogate`, `$blast-radius` |
| Verify behavior and measurements | `$principle-prove-it-works`, `$tdd`, `$benchmark-checklist`, `$create-verification-skill` |
| Write clearly and learn from completed work | `$technical-writing`, `$unslop`, `$reflect` |
| Find a workflow or inspect model preferences | `$poteto-help`, `$setup-pstack` |

The full catalog is in
[`poteto-help`](plugins/tugling/skills/poteto-help/SKILL.md). Explicit invocation
policy follows upstream. Codex uses `$name` where Cursor uses `/name`.

The [Codex adapter](plugins/tugling/skills/poteto-mode/references/codex.md) maps
tools, model inheritance, history, worktrees, and authorization. Tool-dependent
workflows report missing capabilities; Cursor cloud agents, external bot services,
and helper bootstraps are not required or automatically provisioned.

The [addition assessment](evals/pstack/additions-assessment.md) records the
upstream overlap, possible gaps, and evidence for each former addition. None has
earned default inclusion. Their references and useful failure cases remain for
explicit evaluations and existing project contracts. They are not automatically
loaded by skills, playbooks, or the shared adapter.

The [reuse decisions](docs/lineage.md), [source manifest](plugins/tugling/skills/poteto-mode/references/upstream/sources.json),
and [MIT attribution](THIRD_PARTY_NOTICES.md) distinguish Pstack's work from the
Codex port. The earlier [verification cases](evals/pstack/verification-cases.md)
remain part of the evaluation record.

Version 0.8.0 is a local release candidate; see the
[shipping preparation and remaining requirements](docs/pstack-0.8.0-readiness.md).
The existing ten behavioral cases cover four
upstream entry points; the [coverage record](evals/behavioral/catalog-coverage.json)
explicitly lists the remaining 50. Certification rejects incomplete catalog
coverage even when local structural checks and the existing smoke suite pass.

## Install locally

```bash
git clone https://github.com/cyyapye/tugling.git
cd tugling
make verify
codex plugin marketplace add "$(pwd)"
codex plugin add tugling@tugling
```

Start a new Codex thread so the installed skills are discovered, then try:

```text
Use $poteto-mode to add this feature. Keep the change small and show me the real verification evidence.
```

The repository is also shaped as a GitHub-backed marketplace. Workspace admins can import `https://github.com/cyyapye/tugling` from the plugin administration UI. See the official [Codex plugin guide](https://developers.openai.com/codex/build-plugins) and [GitHub marketplace sync guide](https://learn.chatgpt.com/docs/enterprise/plugin-management).

## Set up a project

Describe the desired native workflow using the familiar entry point:

```text
Use $poteto-mode to set up this Python CLI project. Reuse its conventions, provide a runnable command and native verification, and prove the requested workflow from a fresh checkout.
```

Pstack supplies the method; the repository owns its stack, commands, CI and
completion contract. Generic setup does not require a Tugling adapter, receipt
system, learning ledger, or extra CI gate. For advice only, request an assessment
without implementation.

## Existing Tugling adapters

The retained [adoption](plugins/tugling/skills/poteto-mode/references/extensions/project-adoption.md),
[native enforcement](plugins/tugling/skills/poteto-mode/references/extensions/project-enforcement.md),
and [learning](plugins/tugling/skills/poteto-mode/references/extensions/learning-loop.md)
references document existing opt-in helpers. Use them when explicitly maintaining
that integration or evaluating it against Pstack. Existing repository contracts
still apply; this default change does not migrate or remove adopter files.

The dependency-free project check remains available:

```bash
python3 /path/to/tugling/plugins/tugling/scripts/project_contract.py \
  --repo /path/to/project \
  --source-root /path/to/tugling \
  --source-mode pinned
```

The [software factory roadmap](docs/software-factory-roadmap.md) records a proposed
product direction. Its additional machinery still needs evidence against the
Pstack baseline before becoming the default for new projects.

## Choose an update posture

- `pinned`: use a full commit SHA for an auditable, review-gated project or workspace.
- `stable`: follow Tugling's `stable` branch for evaluated releases.
- `preview`: follow `main` to test changes before stable promotion.

GitHub-backed workspace marketplaces can follow a branch for future syncs or stay fixed to a tag or commit. Project CI should prefer a full SHA; a separate scheduled candidate check may exercise `stable` without silently changing the accepted pin.

Tugling does not grant permission to merge, deploy, delete, contact people, spend money, or mutate external systems. Those actions still require the authority established by the user, environment, and repository.

## Develop

Development requires Python 3.11+, Git, and Make. Select the checked-in [`tugling` local environment](.codex/environments/environment.toml) when creating a Codex worktree. Its setup checks Git and Make, then selects a supported `python3` from `PATH` or an existing macOS Homebrew installation. It exports the selected interpreter's directory for setup and subsequent app actions, reports the interpreter, and runs `make verify`. If no supported Python is installed, setup fails with the version requirement; it does not install packages. The environment also provides **Verify** (`make verify`) and **Test** (`make test`) actions in the app.

You can run the same verification from a terminal:

```bash
make verify
```

`make verify` checks marketplace and plugin manifests, skill metadata, pinned Pstack sources and attribution, local links, behavioral fixtures, and executable helper and evaluator tests. The [test audit](evals/test-audit.md) explains which obsolete checks were removed. The separate [Pstack experience smoke](evals/pstack/README.md) uses a fresh local marketplace install and observed Codex tasks.

It also reconstructs the marketplace package in an empty directory and validates the release matrix and any committed release certificate. It never calls a model or requires credentials.

Use this proof ladder for consequential instruction changes:

1. **Structural:** run `make verify` on every change.
2. **Pstack method:** use ordinary tasks, hidden criteria, blinded review and actual execution evidence. Compare Pstack on Codex with and without one addition using matched inputs and budgets; see the attributed [evaluation method](evals/pstack/method.md).
3. **Confirmation:** repeat matched runs on fresh tasks and real project work before claiming an advantage. Keep project source and results outside this repository. Known smoke cases are not unseen holdouts.
4. **Public install:** install the exact pushed revision from GitHub into an empty Codex home and confirm a fresh read-only task loads the installed skill.
5. **Promotion:** compare no Tugling, the exact released revision, and the candidate three times on the full bundled suite; require a sanitized release certificate before moving `stable`.

The local runner freezes package identities, records commands, Git state, elapsed time and tokens, and checks actual artifacts. A separate blinded review assesses quality; the parent audits successful skill reads and execution order. The [older decision questionnaire](evals/behavioral/README.md) remains a legacy regression diagnostic and part of the independently controlled release matrix. Its scores do not establish an advantage over Pstack.

Stable promotion is intentionally separate from ordinary CI. The optional [release certification workflow](docs/release-certification.md) runs only after a maintainer explicitly enables it and approves a reviewed commit and token thresholds. It uses a dedicated API credential, the full behavioral matrix, and a separate attestation job. Ordinary PRs, pushes, and merges make no model calls; their real-CLI transport check uses a local fake API. Certification does not promote a release.

Promotion verifies both CI-attested evidence files for the exact candidate and approved certification run, waits for maintainer environment approval, and atomically publishes `stable` plus an immutable version tag. A fresh runner then installs through the public `stable` alias and checks the exact promoted commit without calling a model. The writer executes only the independently pinned controller and rechecks provenance and GitHub protection settings. Missing controller pins keep promotion disabled. See [Release controller](docs/release-controller.md) for activation, protection boundaries, and recovery. Adopter repositories keep deterministic, model-free CI.

Tugling does not hard-code a model per skill. Pin models in comparable evaluations first; add a recommendation only after repeated evidence shows a meaningful quality, latency, or cost tradeoff for that skill.

The instructions follow OpenAI's [Astra guidance](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra): precise descriptions, conditional references, completion within existing authorization, and proportional verification. These remain portable defaults. Astra-specific evaluation uses `gpt-6-astra` explicitly; it does not change a project's model or the separately reviewed release certification runtime.

## Design choices

- Skills before machinery: there is no MCP server, runtime service, or required model configuration.
- Repository rules win: Tugling reads local instructions instead of imposing one stack or language.
- Local by default: setup and learning do not require a service, account, telemetry stream, or prompt hook.
- Honest evidence states: local checks, remote checks, and deployed behavior remain distinct.
- Small core, local adapters: financial, healthcare, infrastructure, and product-specific rules stay with their repositories.

## License

MIT. See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
