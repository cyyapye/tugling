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

## Add Tugling to a project

1. Keep the project's `AGENTS.md` authoritative.
2. Copy and adapt [`templates/PROJECT_ADAPTER.md`](templates/PROJECT_ADAPTER.md).
3. Point the adapter at the project's canonical verification commands and durable product contracts.
4. Tighten Tugling's generic defaults where the domain requires it; never weaken a project safety rule.

Tugling does not grant permission to merge, deploy, delete, contact people, spend money, or mutate external systems. Those actions still require the authority established by the user, environment, and repository.

## Develop

```bash
make verify
```

`make verify` checks the marketplace and plugin manifests, skill frontmatter and UI metadata, the generic/project boundary, and routing-fixture coverage. Routing fixtures are reviewable test inputs; they are not a substitute for blinded behavioral evaluation when a skill change is consequential.

## Design choices

- Skills before machinery: there is no MCP server, runtime service, or required model configuration.
- Repository rules win: Tugling reads local instructions instead of imposing one stack or language.
- Honest evidence states: local checks, remote checks, and deployed behavior remain distinct.
- Small core, local adapters: financial, healthcare, infrastructure, and product-specific rules stay with their repositories.

## License

MIT. See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
