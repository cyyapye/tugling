# Software factory setup roadmap

Decision date: 2026-09-16. Status: direction accepted; implementation milestones pending.

Repeatable software factory setup is the intended product outcome. Keel will be
its first reference implementation. Design the reusable boundaries now, prove
the workflow on Keel, then reproduce it on a fresh project before packaging it.
This document is the durable record of that direction and the place to resume
planning. It does not change shipped behavior or authorize a release.

## Intended experience

The target request is:

> Use Tugling to set up this project's software factory.

Tugling inspects the repository, reuses its native tooling, configures missing
pieces, and proves a bounded delivery from an accepted task through implementation,
verification, review, authorized delivery, and a health check. It reports which
stages are operational and which require a connection or material decision.
Product goals, acceptance criteria, and spending and release authority remain
explicit inputs.

Setup must work for both new projects and adoption into existing repositories.
Its lifecycle includes assessment, configuration, verification, safe reruns,
upgrades, and diagnosis of drift. Reruns preserve developer edits and avoid
duplicate resources. Cleanup and recovery affect only resources the setup owns.

The pattern spans the software lifecycle: product intent and acceptance, coding,
testing and review, delivery, observation, and feedback into new work. Each stage
needs its own evidence. A verified preview does not establish production readiness
or ongoing unattended operation.

## Ownership and tool choices

| Part | Responsibility | Initial home |
| --- | --- | --- |
| Setup and upgrades | Inspect conventions, select a supported setup, configure it, verify it, and repair drift | Tugling's existing skill entry points and focused helper scripts |
| Project configuration | Product rules, native commands, acceptance criteria, release authority, environment bindings, and health signals | The adopter repository |
| Task execution | One worker owns one bounded task; additional reviewers address relevant risks | Codex using project instructions and Tugling |
| Persistent coordination | Backlog, dependencies, scheduling, ownership, retries, budgets, and completion notifications | An existing coordinator or a companion, if the pilot demonstrates the need |

Use Codex and repository-native CI/CD as the initial execution baseline. OpenClaw
remains a coordinator candidate; selection is open. A coordinator comparison must
show useful completed work and reduced supervision under comparable conditions.
No candidate's superiority or unattended reliability is established by this plan.

Keep coordinator integration replaceable without building a framework for every
available tool. Create a companion only for demonstrated persistent-runtime needs;
its packaging and hosting model remain open. Tugling continues to own portable
engineering guidance, while stack and deployment policy stay with each project.

## Minimum factory contract to define

The first milestone must specify these responsibilities and the evidence exchanged
between them, before choosing a new configuration schema:

- **Work and context:** task identity, intended outcome, acceptance criteria,
  dependencies, relevant source and instructions, and bounded ownership.
- **Execution:** isolated checkout and resource ownership; native bootstrap, run,
  verification, and cleanup commands; concurrency, attempt, time, and usage limits.
- **Acceptance and delivery:** required tests and reviews, release authority,
  target environment, exact source revision, and post-delivery health checks.
- **Operation:** durable state where required, retry and restart recovery, duplicate
  prevention, blockers, last activity, and meaningful completion or failure notices.
- **Proof:** inspectable command results and artifact references tied to the task,
  attempt, and revision. Distinguish configured, attempted, passed, merged,
  delivered, and observed states; worker-reported success alone is insufficient.

Reuse the existing [project setup workflow](../plugins/tugling/skills/tugling/references/project-setup.md),
[bootstrap contract](../plugins/tugling/skills/tugling/references/project-bootstrap.md),
[native flow verification](../plugins/tugling/skills/repo-verify/references/project-flows.md),
and [project adapter](../templates/PROJECT_ADAPTER.md). Version any configuration
extension deliberately; the current adapter schema is not a complete factory
schema. Avoid introducing a second test or application runtime harness.

## Milestones and acceptance evidence

| Milestone | Deliverable | Acceptance evidence | State |
| --- | --- | --- | --- |
| M1: Minimum contract | Map the responsibilities above onto Keel's existing workflow; define one bounded pilot task, limits, and required evidence | Reviewed task and contract, identified integration gaps, and explicit completion criteria | Next |
| M2: Keel reference implementation | A task proceeds through implementation, independent review, CI, protected preview delivery, and a health check | Revision-linked evidence for the full path, a failed check and repair, an interrupted run and recovery, and a record of manual interventions | Pending |
| M3: Fresh-project reproduction | Apply the setup to a clean project using one supported setup based on Keel's stack | Fresh-checkout bootstrap and first verified delivery; repeated setup preserves edits and avoids duplicates; cleanup and subsequent bootstrap work; any manual rescue becomes an explicit setup gap | Pending |
| M4: Reusable release | Package proven reusable instructions and helpers in Tugling; introduce a companion only if justified | Setup and upgrade checks, actionable diagnostics, a supported-scope declaration, and evidence from another project before broader support claims | Pending |

The first supported setup should follow Keel's TypeScript/Cloudflare environment.
Support for another stack requires its own reproduction evidence. The pilot must
respect Keel's native verification, synthetic-data boundary, and release rules.
It does not expand production authority.

Keep Keel's implementation, runbooks, task records, and appropriately sanitized
pilot evidence in Keel. Link their durable locations here as milestones advance.
Reusable fixtures committed to Tugling must be synthetic and project-independent;
raw adopter runs, credentials, and private data stay outside this repository.

## Success measures

Record these from the first pilot so automation can be compared with its baseline:

- Elapsed time from a new repository to its first verified delivery, with waiting
  time and active setup time distinguishable.
- Number and nature of human decisions, manual handoffs, and rescue steps.
- Model usage, execution/hosting cost where available, and maintenance effort per
  accepted outcome. Preserve missing measurements as unknown.
- Successful completion and recovery across the declared cases, including failed
  checks, interruptions, and repeated setup.
- Accurate status and notifications: completion points to evidence; a stalled,
  unavailable, or blocked operation remains visible.

Agent count is an execution setting. Accepted outcomes, reliability, and reduced
human effort determine whether adding coordination is worthwhile.

## Resume here

The next action is **M1: define the minimum contract against Keel's current
workflow and select its first bounded pilot task**. Refresh Keel's instructions,
native commands, CI/CD, and health checks before specifying the implementation.
No coordinator selection or separate product repository is required to begin M1.

Keep this document as the source of truth for reusable product direction. When a
milestone completes, update its state and add the evidence link and any resulting
decision here. Record project-specific execution detail in the adopter repository.

Open decisions to resolve through the milestones are the configuration extension,
whether persistent coordination earns its setup and maintenance cost, and the
supported setup and upgrade boundaries. The first reference implementation and
fresh-project reproduction should supply that evidence.

The workflow was informed by the [OpenAI software factory account](https://newsletter.pragmaticengineer.com/p/openai-software-factory)
and [Harness engineering](https://openai.com/index/harness-engineering/).
