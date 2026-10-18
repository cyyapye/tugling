# Retained verification failure cases

Verification uses Pstack's `principle-prove-it-works` and its existing playbooks
by default. The Tugling verification reference has no automatic loading links.
Its text remains dormant input for explicit `pstack_profiles.py --extension
repo-verify` comparisons; keeping it does not recommend it for normal tasks.

Preserve these useful failure mechanisms and their executable fixtures:

| Failure mechanism | Retained evidence or fixture | Observable outcome for a future comparison |
| --- | --- | --- |
| A local helper exists but is ignored and absent from the commit, so CI cannot reproduce a green local run | [Ignored support file fixture](../behavioral/fixtures/repo-verify-ignored-support-file), including the post-initialization helper | Establish what is actually in the commit, diagnose the local/CI mismatch, preserve the intended test, and avoid claiming remote readiness from local evidence. |
| A green unit suite misses the documented user behavior | `verification` in [the Pstack cases](cases.json) and the greeting CLI in [the runner](../../scripts/pstack_smoke.py) | Exercise the actual CLI, detect the multi-word defect, report the narrow scope of the green test, and leave source unchanged during diagnosis. |
| A changed test file adds no effective regression | `bug-fix` in [the Pstack cases](cases.json), with the original-implementation check in [the runner](../../scripts/pstack_smoke.py) | The delivered regression fails against the original implementation and passes with the repair; the real CLI also produces the correct output. |
| Work is already complete but the agent invents changes or keeps searching | [Bounded no-op fixture](../behavioral/fixtures/tugling-bounded-noop) | Inspect the stated work and native gate, preserve the unchanged repository, and report the bounded result with actual evidence. |

These are known development/regression cases, not unseen holdouts. Keep the
legacy fixtures, case IDs, historical scores and controlled release matrix.
For a new comparison, use the [Pstack evaluation method](method.md): provide an
organic task, keep criteria outside the builder context, and inspect actual
commands and artifacts. Do not give builders the legacy decision questionnaire
or expected answers. Review old fixture instructions for answer leakage before
reusing them as an organic task.

Test Pstack first. Reintroduce the smallest additional guidance only after a
concrete gap and meaningful improvement on matched fresh tasks, including an
irrelevant task and repeated attempts. Confirm the addition was actually read;
the [pilot](method-observations.md) found that installing it did not always mean
it was consumed. Keep reviewer-family and routing limitations explicit.
