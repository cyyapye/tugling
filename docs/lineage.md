# Pstack for Codex: reuse, interface, and evidence

Tugling is a Codex port of Lauren Tan's Pstack. Pstack supplies the
engineering methods and the user-facing vocabulary. Codex adaptations translate
the harness. A Tugling addition must address a concrete missing decision and
demonstrate an advantage over the reused method.

## Why the interface changed

The former seven entry points mixed a branded router, delivery phases, specialist
risks, a UI technique, and skill-authoring machinery. They reflected Tugling's
implementation history rather than a coherent set of user intentions. Keeping
them would make Pstack users learn replacement names without an established
benefit. Existing tests and migration convenience did not justify that cost.

The public catalog now preserves all 54 names from the pinned Pstack revision,
including `poteto-mode`, `poteto-help`, `how`, `why`, `architect`, `arena`, and
the 24 `principle-*` skills. Pstack's task playbooks remain under `poteto-mode`.
There is no newly invented seven-part taxonomy and no competing Tugling menu.
Codex invocation uses `$name` instead of Cursor's `/name`.

## Former entry points

| Previous invocation | Current entry and retained addition |
| --- | --- |
| `$tugling` | `$poteto-mode`; project setup and completion references are dormant |
| `$delivery-plan` | `$architect` and the Multi-phase plan playbook; the additional planning checklist is dormant |
| `$scale-cost-review` | `$architect`, Perf issue and `$benchmark-checklist`; the extra budget checklist is dormant |
| `$async-safety` | `$principle-make-operations-idempotent` and state/concurrency principles; the extra checklist is dormant |
| `$repo-verify` | `$principle-prove-it-works`; use Pstack by default. The Tugling reference is dormant comparison material, with no automatic loading. |
| `$screenshot-first-ui` | Experience First and Feature/Bug fix; use Visual parity only for equivalence. The additional diagnostic taxonomy is dormant |
| `$skill-delivery` | Authoring a skill and Eval, with Codex skill-creator; the additional checklist is dormant |

The [assessment of all additions](../evals/pstack/additions-assessment.md) also
covers the learning ledger and native enforcement machinery. None has established
a substantive advantage over Pstack. Automatic links have been removed from all
entry points, playbooks and the adapter. Existing project-specific contracts and
explicit comparison runs can still use the retained references and helpers.

The old names are intentionally removed from discovery. This is a breaking
interface change in the development checkout, not a published migration. A user
request in ordinary language still goes to the relevant playbook.

## Source and attribution

The source is [Pstack by Lauren Tan](https://github.com/cursor/plugins/tree/101b274dd991f694e1f7024be2157e5f3adf07de/pstack)
at commit `101b274dd991f694e1f7024be2157e5f3adf07de`, inspected on 2026-10-17.
The [manifest](../plugins/tugling/skills/poteto-mode/references/upstream/sources.json)
records original paths, original and distributed hashes, per-file adaptations,
and an inventory of locally authored metadata and extensions. The full
[MIT license](../plugins/tugling/skills/poteto-mode/references/upstream/LICENSE)
ships inside the isolated skill install. [Third-party notices](../THIRD_PARTY_NOTICES.md)
also reproduce it. Pstack's principles are not Tugling inventions.

Most method text is retained. The [Codex adapter](../plugins/tugling/skills/poteto-mode/references/codex.md)
is loaded by every entry point and governs tool, model, history, path, scope, and
delegation translations, including examples and referenced role instructions.
This follows the upstream approach of keeping one method catalog with a harness
adapter, rather than replacing its names for each host.

Explicit invocation policy follows upstream; `setup-pstack` remains available
for natural requests. Setup and help are adapted directly to avoid teaching
Cursor keyboard shortcuts or writing Cursor model rules in Codex. Models inherit
the current session. A missing integration or independent reviewer is reported
as missing, not simulated and claimed as executed.

Upstream helper sources are included for traceability but their bootstraps are
not a runtime dependency. The adapter uses available native task, worktree,
automation, GitHub, browser, and terminal tools. It does not provision a bot,
install a daemon, change global configuration, or authorize external writes.

## Evidence and maintenance

All ten existing behavioral cases and their decision criteria remain. They now
exercise four upstream entry points. The other 50 are explicitly declared in the
[coverage record](../evals/behavioral/catalog-coverage.json). This declaration
allows local development checks; it does not waive full coverage for release.
Both release-proof generation and independent certificate verification reject
an incompletely covered installed catalog. Controller changes still require
independent review and approved pins before release use.

Source hashes, metadata and isolated-install checks establish structure. The
[test audit](../evals/test-audit.md) removes the old declarative routing cards.
The [Pstack experience smoke](../evals/pstack/README.md) observes familiar workflows
through native local plugin installation. Observed model runs establish only the
behaviors actually exercised.
Neither establishes a broad improvement over Pstack. Keep each addition
provisional until a matched comparison of Codex-adapted Pstack with and without
that addition shows material improvement without critical holdout regressions.

The verification addition did not earn default inclusion in the
[method pilot](../evals/pstack/method-observations.md). Its automatic links were
removed from the proof principle and shared adapter. The unlinked reference is
retained for explicit comparison profiles, and the [failure cases](../evals/pstack/verification-cases.md)
remain as evaluation inputs. This is a default-policy decision under limited
evidence, not a claim that the addition can never help.

For an upstream update, inspect the diff at a new exact revision, preserve names,
port only necessary platform differences, record changes and hashes, and run
the relevant behavioral cases. Do not update from a moving branch automatically.
Run `python3 scripts/pstack_sources.py --upstream-root /path/to/cursor-plugins`
to compare source hashes with that pinned checkout, then `make verify`.

Product rules, stack choices, domain policy, and release authority stay in adopter
repositories. Reuse first; new prose and new entry points must earn their place.
