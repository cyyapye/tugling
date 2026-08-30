---
name: skill-delivery
description: Create or revise a reusable Codex skill with focused routing, concise instructions, UI metadata, positive and negative cases, structural validation, and proportional behavioral evaluation. Use when the user asks to add, update, extract, generalize, harden, or evaluate a skill. Do not use for one-off prompt writing that is not intended to become an installed skill.
---

# Skill Delivery

A first draft is not automatically a trusted skill. Deliver the smallest instruction set that demonstrably changes the intended decisions without attracting unrelated work.

## Workflow

1. **Name the behavior**
   - Record the request the skill should handle, the decision it should improve, and similar requests that must not trigger it.
   - Gather at least one realistic positive case, one negative case, and one holdout or edge case.
2. **Inspect the nearest skill**
   - Reuse or narrow an existing skill when ownership already exists.
   - Do not create a catchall to avoid choosing a boundary.
3. **Draft with the available skill creator**
   - Initialize the standard folder and `agents/openai.yaml`.
   - Keep frontmatter discriminating and the body limited to non-obvious guidance that changes behavior.
   - Put conditional detail in a linked reference only when it would otherwise burden every invocation.
4. **Add evaluation cases**
   - Keep positive, negative, and holdout prompts outside the instruction body.
   - Define observable pass criteria and critical regressions before tuning wording.
5. **Validate structure**
   - Check folder and skill names, frontmatter, required UI metadata, links, unfinished placeholders, and any scripts.
6. **Evaluate proportionally**
   - For a low-risk narrow skill, review routing cases and run structural validation.
   - For a demonstrated behavioral failure or consequential workflow, compare baseline and candidate on the same blinded prompts. Change one decision rule at a time and reject a candidate that improves training cases while regressing holdouts.
7. **Promote and report**
   - Keep only the winning version.
   - Record what changed, cases run, result, and any runtime evaluation that did not run.

## Completion gate

A delivered skill needs, at minimum:

- `SKILL.md`
- `agents/openai.yaml`
- reviewable positive, negative, and holdout cases
- a passing structural validator
- an explicit statement of whether behavioral evaluation ran

It is not complete for a consequential behavior correction until the candidate improves the target failure without a critical holdout regression.

## Guardrails

- Do not turn one project's domain rule into a universal skill requirement.
- Do not restate generic agent ability or system policy.
- Do not require a fixed sequence when several approaches are safe.
- Do not use evaluation prompts inside the skill; keep candidates blind to the scorecard.
- Do not claim runtime or behavioral proof from frontmatter validation alone.

## Handoff

Report the skill path, trigger boundary, cases added, validator result, behavioral baseline and final result when run, kept decision change, discarded changes, and remaining uncertainty.
