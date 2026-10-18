# Pstack for Codex

This is Tugling's Codex port of Lauren Tan's Pstack. Keep Pstack's names, methods,
principles, and task playbooks. Read only the skill or playbook relevant to the
request. This adapter takes precedence over Cursor-specific instructions in all
bundled skills, playbooks, role prompts, examples, and helper documentation.

## Scope and completion

Follow the session's instruction hierarchy, permissions, and the user's existing
authorization. Implementation includes required local verification and in-scope
repairs. Advice, a plan, and a checkpoint remain within their requested scope.
No skill grants permission to send messages, spend money, publish, merge, deploy,
delete user data, change global settings, or expand the task. Reuse authorization
already given; otherwise prepare a concrete result before asking at the boundary.
An upstream instruction to open a PR or fix another skill applies only when that
action is in scope. Do not stop approved work for an invented confirmation.

Use repository-native gates. Preserve user edits and report the strongest state
actually established. A green local command does not prove commit completeness,
remote CI, merge, deployment, or certification.

## Harness translations

| Pstack / Cursor term | Codex behavior |
| --- | --- |
| `/name`, run a skill | Invoke `$name`, or read the installed sibling `name/SKILL.md`. Keep the name. |
| `Task`, cloud agent, `poteto-agent`, `comment-sicko` | Use available subagent tools only when delegation is authorized. Preserve the requested role: use [poteto-agent](roles/poteto-agent.md) for playbook-step implementation workers and [comment-sicko](roles/comment-sicko.md) for that review role. General-purpose investigators and reviewers get their routed skill's role prompt, without a poteto-agent wrapper. Pass relevant instruction paths and this adapter; do not invent `subagent_type`, cloud, readonly, or background fields. |
| Models, per-role defaults, `pstack-models.mdc` | Inherit the configured session model and effort. Change them only on explicit user instruction and only to supported values. A same-model panel is not a multi-model evaluation. |
| Parallel design exploration or reviewers | When delegation is unavailable or not authorized, compare alternatives sequentially. Report that limitation when independence or parallelism matters; never claim a swarm, race, or independent review happened. |
| `AskQuestion` | Use the available user-input tool or ask concisely in chat. Infer observable facts from evidence first. |
| Todo list | Use an available plan tool or a short working plan. Keep the playbook's substantive steps; mark an inapplicable step with its reason. |
| `Read`, `Grep`, `Glob`, terminal | Use available file tools and `rg` with repository-native commands. |
| `create-skill` | Use the installed Codex `skill-creator` skill. |
| `control-ui`, `control-cli`, `deslop` | Use available browser/native UI/terminal tools for the same proof, or inspect the diff for unnecessary code. Do not require cursor-team-kit. If the actual surface cannot be exercised, report unverified behavior. |
| `/loop`, watcher/drive, recurring run | Use Codex's native automation when the user asks for future work. For the current task use bounded checks. Do not create a background daemon or keep a task alive by busy polling. |
| `orch`, `watch-pr`, bootstrap helpers | Use native task, worktree, Git and GitHub tools for the workflow. The source helpers are bundled for provenance, not a required runtime. Do not run their bootstrap or install dependencies automatically. |
| `worktree-audit.sh`, worktree cleanup | Use Git's worktree inventory and available Codex chat/attachment state. Do not run the Cursor transcript scanner. Missing activity evidence means unknown, never safe to delete. For managed Codex worktrees, use the native recoverable archive operation when available; preserve needed ignored files first. Untracked files are user work until inspected. |
| Custom Mode, Option+Enter, Alt+Enter | These are Cursor controls. In Codex invoke `$poteto-mode` for the task; do not claim a persistent UI mode was enabled. |
| Origin, Bugbot, Grok Bot, external data source | Use only an available configured integration. An unavailable dependency is an explicit limit, not permission to provision it or pretend success. |

An explicit request for `arena`, `swarm`, or a review panel authorizes that method
within the task, subject to session limits. Ordinary work does not authorize
unbounded fan-out. Keep existing project worktree conventions and isolate
concurrent writes. The parent that receives `poteto-mode` owns the playbook;
delegate its steps, not the entire playbook, to implementation workers. Inspect
and integrate worker results yourself.

## Paths, configuration, and history

Project skills live in `.agents/skills/`; personal skills use the session's
configured Codex skills directory. Repository rules belong in `AGENTS.md` or
the project's existing instructions. Do not create `.cursor` rules or mutate
plugin-cache copies. Installed skills may be read-only; edit the source checkout.

For orchestrate/autopilot state, a Cursor agent or root store is not a Codex path.
Choose a writable task artifact directory under the session's allowed storage,
pass its absolute path to every worker, and keep the playbook's ledger and state
files there. Use a repository's durable-artifact convention only when those files
belong in the requested change; do not invent a system-provided store.

When porting existing skill metadata, translate `disable-model-invocation: true`
to `policy.allow_implicit_invocation: false` in `agents/openai.yaml`. Do not write
Cursor-only `disable-model-invocation`, `paths`, `globs`, `icon`, or `color` fields
into Codex skill frontmatter. Express relevant file scope in the description or
project instructions. For newly authored skills, follow `skill-creator` and the
user's requested invocation policy; preserve existing policy when editing.

For `recall`, `automate-me`, `reflect`, and session pickup, prefer Codex's available
chat/history tools or transcripts the user provided. Inspect only the requested
project/conversation scope. Cursor transcript paths and model-rule files are not
Codex paths. Do not scan unrelated chats, copy raw transcripts into a repository,
or save memory without the user's request. Missing access is missing evidence.

`setup-pstack` keeps its familiar purpose: explain available model/budget options
and apply only changes the user requested through supported Codex controls.
Inherit current settings by default. No global configuration write is required
to use this port.

## Conditional additions

Use Pstack's methods by default. No optional Tugling engineering addition has
established a substantive advantage over this baseline. Retained extension
references are for explicitly requested comparisons or existing project-specific
contracts; do not load them automatically for ordinary tasks.

An addition must earn default inclusion with a concrete Pstack gap and material
improvement on matched fresh tasks, tools, models, and budgets, including repeated
attempts and irrelevant tasks. Extra detail, structural checks, and no-skill
comparisons alone do not establish that advantage.

The [source manifest](upstream/sources.json) records the pinned upstream revision,
file hashes, and adaptations. The [full MIT license](upstream/LICENSE) credits
Lauren Tan. Codex metadata and dormant extension references are maintained by Tugling.
