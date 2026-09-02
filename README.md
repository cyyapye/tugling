# Tugling

**Tiny tools that pull their weight.**

Tugling is a small, skills-only Codex plugin for agent-led software delivery. It helps an agent turn a request into the smallest complete change, design hot paths with explicit performance and cost budgets, handle retries safely, and prove the real result before calling the work done.

It is intentionally portable. Tugling supplies reusable engineering judgment; each repository keeps its own product rules, commands, architecture, security boundaries, and release authority.

## What ships

| Skill | Job |
| --- | --- |
| `$tugling` | Route a non-trivial repository change from intent to verified handoff. |
| `$delivery-plan` | Produce an executable, repository-grounded implementation plan. |
| `$scale-cost-review` | Review simplicity, cardinality, hot-path performance, and operating cost. |
| `$async-safety` | Design duplicate-safe, replay-safe asynchronous workflows. |
| `$repo-verify` | Use the repository's own gates and report the strongest proven state. |
| `$screenshot-first-ui` | Diagnose the visual defect before reaching for pixel tweaks. |
| `$skill-delivery` | Create or revise a skill with routing cases and validation. |

The shared vocabulary is the [Tugling Twelve](plugins/tugling/skills/tugling/references/principles.md). The [lineage map](docs/lineage.md) shows how Pstack and project hardening practices were condensed into this smaller core.

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
Use $tugling to add this feature. Keep the change small and show me the real verification evidence.
```

The repository is also shaped as a GitHub-backed marketplace. Workspace admins can import `https://github.com/cyyapye/tugling` from the plugin administration UI. See the official [Codex plugin guide](https://developers.openai.com/codex/build-plugins) and [GitHub marketplace sync guide](https://learn.chatgpt.com/docs/enterprise/plugin-management).

## Set up a project

In a new thread opened on the project, start with:

```text
Use $tugling to set up this project. Assess it read-only first, then propose the smallest adapter and pinned CI contract before writing.
```

The intended setup delta is deliberately small:

- a short `Tugling project adapter` section in the existing `AGENTS.md`;
- `.tugling/project.json` with the exact Tugling source, native verification argv, and learning mode;
- one committed synthetic case at `.tugling/dogfood.json`;
- a deterministic CI check that validates the source pin and adapter without calling a model;
- an ignored `.tugling/local/` directory only when local learning is enabled.

The bundled project check is dependency-free:

```bash
python3 /path/to/tugling/plugins/tugling/scripts/project_contract.py \
  --repo /path/to/project \
  --source-root /path/to/tugling \
  --source-mode pinned
```

[`templates/PROJECT_ADAPTER.md`](templates/PROJECT_ADAPTER.md) remains useful when a repository needs a fuller domain adapter. The setup workflow preserves existing project rules and commands instead of replacing them.

## Learn locally, by choice

Learning is off by default. A project may opt into `local` mode, where explicit reusable corrections can be summarized into an ignored, permission-restricted JSONL ledger. Tugling installs no capture hook, records no full transcript, sends no telemetry, and uploads nothing.

The bundled helper can capture, digest, and review those local records. A lesson reaches Tugling only after a person chooses `promote`, rewrites it as a sanitized synthetic case, and the released-versus-candidate evaluation passes without a critical holdout regression.

## Choose an update posture

- `pinned`: use a full commit SHA for an auditable, review-gated project or workspace.
- `stable`: follow Tugling's `stable` branch for evaluated releases.
- `preview`: follow `main` to test changes before stable promotion.

GitHub-backed workspace marketplaces can follow a branch for future syncs or stay fixed to a tag or commit. Project CI should prefer a full SHA; a separate scheduled candidate check may exercise `stable` without silently changing the accepted pin.

Tugling does not grant permission to merge, deploy, delete, contact people, spend money, or mutate external systems. Those actions still require the authority established by the user, environment, and repository.

## Develop

```bash
make verify
```

`make verify` checks the marketplace and plugin manifests, skill frontmatter and UI metadata, the generic/project boundary, routing-fixture coverage, behavioral fixtures, and the dependency-free grader tests.

Use this proof ladder for consequential instruction changes:

1. **Structural:** run `make verify` on every change.
2. **Synthetic dogfood:** run at least three no-Tugling/candidate comparisons and require the dogfood gate.
3. **Project dogfood:** run an external case against a clean project checkout without committing project source or results here.
4. **Promotion:** compare no Tugling, the exact released revision, and the candidate on the full bundled suite; require the release proof before making a broad quality claim.

The live harness pins the model and reasoning effort, isolates every run, records commands, Git state, elapsed time, tokens, source identities, regressions, and plugin permission or hook changes, and grades observable decisions rather than prose style. See [Behavioral evaluation](evals/behavioral/README.md) for commands and limits.

Tugling does not hard-code a model per skill. Pin models in comparable evaluations first; add a recommendation only after repeated evidence shows a meaningful quality, latency, or cost tradeoff for that skill.

## Design choices

- Skills before machinery: there is no MCP server, runtime service, or required model configuration.
- Repository rules win: Tugling reads local instructions instead of imposing one stack or language.
- Local by default: setup and learning do not require a service, account, telemetry stream, or prompt hook.
- Honest evidence states: local checks, remote checks, and deployed behavior remain distinct.
- Small core, local adapters: financial, healthcare, infrastructure, and product-specific rules stay with their repositories.

## License

MIT. See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
