---
name: tugling
description: Set up a project or carry multi-step repository work through verification. Use for Tugling adoption, project bootstrap, or delivery across engineering boundaries; skip simple explanations and isolated trivial edits.
---

# Tugling

Deliver the smallest complete change the repository can honestly prove.

## Continue within the request

System and developer instructions and environment permissions govern execution.
Within those limits, the user's request and existing authorization take precedence
over repository guidance and skill defaults. Use current project code, commands,
and applicable instructions to resolve implementation facts.

Treat a request to implement or set up as permission to finish that work, including
routine local verification and in-scope repairs. Resolve reversible details from
context and continue to the requested finish condition. Ask only when a missing
decision materially changes the outcome, scope, or authority; keep independent
work moving while waiting. An assessment-only request remains assessment-only.

Tugling supplies no additional authority to merge, deploy, delete, spend, contact
people, or mutate external systems. Reuse authorization already established for
the action. When permission is missing, prepare the concrete, reviewable result
before asking. If a skill instruction causes a pause, identify its file and exact
instruction and explain the remaining boundary.

## Load only what changes the work

- For project setup, adoption, or native rule enforcement, read [project setup](references/project-setup.md).
  It distinguishes assessment, adoption, bootstrap, and enforcement, including their completion criteria.
- For a material design tradeoff, consult the relevant [principles](references/principles.md).
- For an explicit repeatable correction in a project with local learning enabled,
  read [the learning loop](references/learning-loop.md).

Use a focused skill when its decision is needed and it is available:

- `$delivery-plan`: a requested plan or unresolved work across meaningful boundaries.
- `$scale-cost-review`: a design or change with a material volume, latency, or cost risk.
- `$async-safety`: duplicate delivery, retry, ordering, or recovery across asynchronous state.
- `$screenshot-first-ui`: a visible defect or material UI change needing visual proof.
- `$skill-delivery`: creation or revision of a reusable skill.
- `$repo-verify`: readiness, an unclear or failing verification contract, or changed judging machinery.

For straightforward work with a clear native gate, run that gate directly.
Read applicable project instructions and task-relevant sources; reuse context
already inspected. Do not load every skill, principle, or project document.

## Finish with evidence

Define completion from the user's requested outcome and the repository's contract.
For implementation, carry the change through the required local checks, inspect
the affected behavior, and repair in-scope failures. Use focused checks while
iterating; complete required final gates. Broaden or repeat testing only for new
changes, failures, or unresolved risks. Scale additional proof to the behavior.

For a bounded implementation that needs no change, `NOOP` requires the relevant
native validation command and `git status --short --untracked-files=all` proving
that no change was needed. Reading a queue or source file alone is insufficient.
Use `ADVISORY` for requested advice and `BLOCKED` for an unmet required boundary.
Never report a no-op as `LOCAL_PASS` or infer remote, merged, or deployed success
from local checks. Preserve unrelated user changes.

Lead the handoff with the outcome, then the material decision, current evidence,
strongest proven state, and any remaining boundary. Mention a principle only if
it changed a decision; avoid a fixed report template for simple work.
