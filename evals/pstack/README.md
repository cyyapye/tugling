# Familiar Pstack experience on Codex

For development comparisons and skill-quality claims, follow the attributed
[Pstack evaluation method](method.md). This smoke runner is its execution adapter.

See the [2026-10-17 observations](observations.md) for the first reviewed run and
its limits.

The [0.8.0 observations](port-0.8.0-observations.md) record the final port review.
The additional [Codex compatibility requests](codex-cases.json) cover scoped
history, local verification-skill authoring, arena/swarm fallbacks, explanation,
idle scope, and task-only setup. They were independently authored before their
first run and are now known development cases, not fresh holdouts.

This is a local compatibility smoke test. It installs the frozen current package
through `codex plugin marketplace add` and `codex plugin add` in a fresh Codex home
for each task. It copies authentication only, retains the generated plugin
registration, and removes the temporary home afterward. No personal skills or
user configuration are copied. The harness marks only the synthetic checkout as
trusted in that temporary home before capturing settings. Codex otherwise adds
that same project entry at startup, causing a byte-comparison false alarm.
The published marketplace and the user's active
plugin installation are not changed.

The seven tasks cover help, natural setup discovery, reply-only planning, a CLI
bug fix, direct verification, sequential architecture analysis, and an unavailable
PR integration. These are test scenarios, not new skill entry points. Every task
gets a fresh synthetic repository and a normal free-form prompt. There are no
multiple-choice answers or model-reported grades.

```sh
python3 scripts/pstack_smoke.py \
  --codex-bin /path/to/codex \
  --model <configured-model> --reasoning-effort <configured-effort> \
  --out /private/tmp/pstack-smoke-new-run
```

Use `--case <id>` to investigate one scenario. The runner is sequential, has a
four-minute deadline per task by default, and admits at most seven tasks. Default
usage thresholds are 1.5 million input and 60,000 output tokens, checked between
tasks; a running task can exceed them. Missing usage or a failed automated check
stops new tasks. Nothing calls a model from `make verify`.

Use `--cases-file evals/pstack/codex-cases.json` for the additional requests.
The authoring task's generic greeting oracle verifies the application repair;
it does not establish completion of the generated skill. Inspect the skill,
feature map, retained evidence, permitted paths, and actual workflow execution
separately. A protected `.agents` directory can prevent delivery: preserve that
failure, and treat a separately authorized directory grant as a changed execution
environment, not a retroactive pass or a reason to bypass the sandbox.

Builders work in neutral temporary project paths. Rubrics and observer records
stay outside their workspaces; the environment has no evaluation marker. Each
delivery is copied and hashed before its temporary project is removed. Native
workspace-write permissions do not prevent all host reads; trace review must
check for observer leakage. Normal project test files remain ordinary inputs.

Raw prompts, final answers, command events, stderr, and resulting workspaces stay
in the private output directory. Never commit them or authentication. Automatic
checks verify installation identity, unchanged settings/package/HEAD, unchanged
repositories on advisory tasks, and independently execute several CLI examples
and the native gate after the bug fix. The added regression must also fail against
the original implementation. Advisory cases use a writable sandbox, so
unchanged source is an observed decision rather than a forced read-only outcome.

Review the original `events.jsonl`, `commands.json`, `final.md`, and workspace for
each case against its observer-only `rubric`. Confirm successful skill/adapter/playbook
reads, useful answers, reproduction before the fix, no prohibited actions, and
honest unavailable-capability reporting. A path mentioned in a failed command or
an answer is not proof a skill loaded. Do not equate automatic checks with a
semantic pass: `semantic_review_complete` remains false until a separate review.

Preserve failed runs. Any repair gets a new output directory. A representative
smoke does not establish all 54 skills, GUI command-picker behavior, public install,
an advantage over Pstack, release approval, or certification. The separate
behavioral matrix and its catalog blocker remain unchanged.
