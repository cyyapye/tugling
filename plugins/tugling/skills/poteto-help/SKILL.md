---
name: poteto-help
description: "Guides users through pstack setup, $poteto-mode, and picking the skill, playbook, or principle for a task. Type $poteto-help with a question."
---

Read the [Codex adapter](../poteto-mode/references/codex.md) once per session before applying this skill. It governs tool, model, scope, and path translations below.


# Poteto help

Answer the user's question about pstack, hand them a prompt they can send, and link the file the answer came from. For a help question, don't start the work. The user asked how, and a pstack run spends real tokens, so let them send the prompt.

A message that asks for work, such as "use pstack to fix this bug", is not a help question. Read [`poteto-mode`](../poteto-mode/SKILL.md), do the work under it, and carry the requested work through its checks.

This file maps questions to the skills and guide pages that hold the answers. Those files own the details. Read the file you route to before you quote it, and trust it when it disagrees with this map. Link the installed Codex-adapted file when available. Upstream guide links are pinned references; identify them as Cursor documentation and apply the Codex adapter before giving platform instructions.

## Find out what they need

Infer the need from the message and the conversation. A named situation, such as "which skill reviews a PR?", goes straight to its section. If the need is still unclear, ask one multiple-choice question with these options, then answer only the section they pick:

- Get set up
- Start a task with `$poteto-mode`
- Pick a skill for a situation
- Fix a run that went wrong
- Make pstack my own

## Get set up and start a task

This is Tugling's Codex port of Pstack. The familiar skill names are unchanged;
Codex uses `$name` invocation. Start with `$poteto-mode` and describe the goal and
how to tell it is done. It selects the playbook and loads the needed skills.

Use `$setup-pstack` only when the user wants to inspect or change supported model
and budget choices. Current Codex settings are inherited by default. There is no
required setup wizard, Cursor rule, or Custom Mode keyboard shortcut.

For a help request, explain the choice without starting the work. A request to
do work is authorization to proceed within its stated scope. Read the linked
skill before recommending its behavior. The Codex adapter documents capabilities
that depend on available tools; do not imply Cursor cloud agents or a Grok Bot
connection comes with this plugin.

## Pick a skill

The default answer is `$poteto-mode`, which runs most of the others when its steps need them. Name a skill directly when the user wants more or less of something than the playbook gives. Read the skill before you recommend it, and give one example prompt.

| The user wants to | Skill |
|---|---|
| Do any non-trivial task with rigor | [`$poteto-mode`](../poteto-mode/SKILL.md) |
| Check that the agent understood their goal and the problem before it starts | [`$in-your-own-words`](../in-your-own-words/SKILL.md) |
| Aim a task higher before starting: more expert, more outcome-focused, not overspecified | [`$sharpen`](../sharpen/SKILL.md) |
| Know how code works now, or where new code should live | [`$how`](../how/SKILL.md) |
| Know why code is shaped this way, or where a number came from | [`$why`](../why/SKILL.md) |
| Understand a change or subsystem, explained plainly | [`$teach`](../teach/SKILL.md) |
| Catch up on their own recent work on a topic | [`$recall`](../recall/SKILL.md) |
| Catch up on what changed in this chat since their last message, in a few plain sentences and small visuals, with enough context to decide each action item | [`$ketchup`](../ketchup/SKILL.md) |
| Know what a small diff could break outside itself | [`$blast-radius`](../blast-radius/SKILL.md) |
| Settle types and module shape before code that crosses a function boundary | [`$architect`](../architect/SKILL.md) |
| Get several attempts at one brief, merged into the best one | [`$arena`](../arena/SKILL.md) |
| Run parallel checks over slices, or race available workers | [`$swarm`](../swarm/SKILL.md) |
| Have different models review a diff and try to break it | [`$interrogate`](../interrogate/SKILL.md) |
| Fix a bug test-first when a cheap local test exists | [`$tdd`](../tdd/SKILL.md) |
| Apply TypeScript rules to `.ts` or `.tsx` work | [`$typescript-best-practices`](../typescript-best-practices/SKILL.md) |
| Strip comments before review, using a reviewer that didn't write them | [`$no-comments`](../no-comments/SKILL.md) |
| Clean AI tells out of prose | [`$unslop`](../unslop/SKILL.md) |
| Write docs, an RFC, a README, a PR description, or a commit message to a standard | [`$technical-writing`](../technical-writing/SKILL.md) |
| Hear the last reply again in plain words | [`$bro`](../bro/SKILL.md) |
| Give agents a scripted way to drive the app and prove behavior | [`$create-verification-skill`](../create-verification-skill/SKILL.md) |
| Bring a verification skill and its feature map back in line with the app | [`$maintain-verification-skill`](../maintain-verification-skill/SKILL.md) |
| Vet a performance number before reporting or acting on it | [`$benchmark-checklist`](../benchmark-checklist/SKILL.md) |
| Run a large or cross-cutting change, or one to review after stepping away | [`$figure-it-out`](../figure-it-out/SKILL.md) |
| Keep a decision log during a run, and review it afterward | [`$show-me-your-work`](../show-me-your-work/SKILL.md) |
| Inspect or change supported Codex model and reasoning settings | [`$setup-pstack`](../setup-pstack/SKILL.md) |
| Turn their own working habits into a personal mode skill | [`$automate-me`](../automate-me/SKILL.md) |
| Turn what a finished task taught into skill edits | [`$reflect`](../reflect/SKILL.md) |
| Stop agents from repeating the same mistakes in this repo | [`$correct`](../correct/SKILL.md) |
| Build a page whose buttons wake a Grok Bot over a webhook | [`$make-bot-ui`](../make-bot-ui/SKILL.md) |
| Find their way around pstack | `$poteto-help` |

If a skill directory next to this one is missing from the table, read its frontmatter and route by its description. The `principle-*` directories are covered under principles below.

Close calls:

- `$how` explains what the code does. `$why` explains the reasons. `$teach` runs one or both and explains the result plainly.
- `$arena` gives every worker the same brief and merges the best parts. `$swarm` splits work into slices or a race and returns one report.
- `$architect` settles the design and continues when implementation is requested. A plan-only request or "with checkpoint" stops at the design.
- `$interrogate` reviews the diff. `$blast-radius` looks for breakage outside the diff and proves the one fact that makes the change safe.
- `$recall` rebuilds context across recent chats. `$ketchup` covers only this chat since the user's last message. Resuming one specific chat or branch is the Session pickup playbook.
- `$figure-it-out` designs one rigorous run. The Orchestrate playbook runs a program that spans days and many PRs. The Autonomous run playbook drives one task to a finish condition.

Not in pstack:

- `/deslop`, `control-cli`, and `control-ui` ship in the `cursor-team-kit` plugin.
- `/loop` and `/create-skill` are Cursor built-ins.
- pstack has no `/orchestrate` skill. Orchestrate is a `$poteto-mode` playbook. If the slash menu shows `/orchestrate`, another plugin provides it.

## Playbooks and principles

Playbooks are step lists inside `$poteto-mode`, not skills, so they have no slash command. Inside `$poteto-mode`, describing the task picks one, and these phrases name one directly:

- "babysit this pr" or "check on pr 123" runs Babysit. It drives the PR to merge-ready and stops there. It doesn't merge unless the user asks to merge, land, or ship.
- "land the stack" runs Shipping.
- "take over this branch" runs Session pickup.
- "pause safely" runs Pause safely.
- "full autopilot on this queue" runs Autopilot-full. "stack them, don't ship" runs Autopilot-stack.
- "run the eval playbook" runs Eval.

Invoke `$poteto-mode` when this specific playbook is intended. The Playbooks section of [`poteto-mode`](../poteto-mode/SKILL.md) lists every playbook and when it applies. [Guide page 6](https://github.com/cursor/plugins/blob/101b274dd991f694e1f7024be2157e5f3adf07de/pstack/docs/guide/06-verify-and-ship.md) covers opening, babysitting, and landing a PR.

pstack has no planning skill. Codex plan-only requests keep their read-only scope. For work that spans phases or stacked PRs, asking `$poteto-mode` for a plan runs the [Multi-phase plan playbook](../poteto-mode/playbooks/multi-phase-plan.md), which writes the plan and doesn't implement it. For a design question, the Prototype playbook or `$architect` settles it in code first.

Principles are one-rule skills that `$poteto-mode` reads and cites in its replies. The user rarely invokes one. They steer with the names instead, as in "apply prove it works. show me the real output." Typing `$principle-<name>` still loads one on demand. [Guide page 8](https://github.com/cursor/plugins/blob/101b274dd991f694e1f7024be2157e5f3adf07de/pstack/docs/guide/08-principles.md) lists them.

## Fix a run that went wrong

| Symptom | Fix |
|---|---|
| The mode stopped applying after a few turns | Invoke `$poteto-mode` for the new task; do not assume a persistent Cursor mode in Codex. |
| A question got treated as the next step of the last task | Say "new task", or say the turn doesn't need the mode. |
| A new model choice had no effect | Check whether the supported Codex control actually applied the setting and whether it affects this chat or future chats. No Cursor model rule is written. |
| Runs cost more than expected | Reduce unnecessary fan-out and use supported model/effort choices through `$setup-pstack`; do not guess per-role cost savings. |
| A skill didn't load on its own | Only `$setup-pstack` loads from the user's words. The others load when the user types them or when `$poteto-mode` runs them, and it doesn't run every skill. |
| Parallel agents overwrote each other | Use isolated worktrees for authorized concurrent writers. |
| An overnight run moved but finished nothing | A requested Codex automation needs a check that can pass or fail, not only a duration. See [guide page 7](https://github.com/cursor/plugins/blob/101b274dd991f694e1f7024be2157e5f3adf07de/pstack/docs/guide/07-overnight.md). |
| The reply claims success from a green build | Ask for the real command, flow, stored value, or profile. That's the prove-it-works principle. |

For a run that drifts, [`references/prompting.md`](references/prompting.md) has one-line steers. [Guide page 10](https://github.com/cursor/plugins/blob/101b274dd991f694e1f7024be2157e5f3adf07de/pstack/docs/guide/10-recipes-and-pitfalls.md) has more pitfalls and the recipes worth copying.

## Make pstack my own

- [`$automate-me`](../automate-me/SKILL.md) drafts a personal mode skill from the user's own history, to use alongside `$poteto-mode`.
- [`$reflect`](../reflect/SKILL.md) after a session turns its lessons into skill edits the user approves.
- `$poteto-mode write a skill for <workflow>` runs the authoring playbook. The eval playbook tests a skill change blind.
- Repair a misbehaving skill separately when that repair is authorized.

[Guide page 9](https://github.com/cursor/plugins/blob/101b274dd991f694e1f7024be2157e5f3adf07de/pstack/docs/guide/09-make-it-yours.md) covers each of these.

## Reply

Lead with the answer. Give at most one example prompt in a code block, adapted from [`references/recipes.md`](references/recipes.md) when one fits, then the link to that file. Keep it short unless the user asked for the whole map.
