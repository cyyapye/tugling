# Skill Delivery

Use Pstack's [Authoring or modifying a skill](../../playbooks/authoring-a-skill.md)
with the [Codex integration](../codex.md). Keep only prose that
changes a decision. The additions here cover reuse, routing, and behavioral proof.

## Reuse before authoring

1. Name the repeated failure or decision to improve, and nearby requests that must
   not trigger the skill.
2. Inspect the nearest existing skill, including Pstack. If it covers the decision,
   use it. For a Codex mismatch, adapt tools, discovery, and authority handling
   without rewriting the engineering method. A new name or shorter summary is
   not an improvement by itself.
3. For copied material, preserve the author and full license, pin the source
   revision and file, and record local changes. Keep platform adaptations separate
   from original guidance. Never claim copied principles as Tugling inventions.
4. Add a local instruction only for a concrete uncovered decision. Prefer a type,
   test, lint, or script when it can enforce the rule. Keep product policy local.

## Codex packaging and routing

- Use the available skill creator; preserve existing entry points and invocation
  policy unless the user requests a change.
- Keep a short, discriminating description with meaningful exclusions. Link
  conditional detail from the mode that needs it; do not load all references.
- Include `SKILL.md`, `agents/openai.yaml`, and reviewable positive, negative, and
  holdout cases. Keep prompts and expected outcomes outside the instruction body.
- Validate frontmatter, UI metadata, local links, scripts, and redistributable
  dependencies. Check that copied references and their license survive installation.

## Evaluate the added decision

For consequential behavior changes, use Pstack's [Eval](../../playbooks/eval.md).
Define observable criteria before tuning wording. Compare the reused upstream
method plus necessary Codex adaptation against the same method with the proposed
Tugling addition, using the same prompts, tools, model settings, and budget.
Keep no-skill and current-release comparisons required by the repository too.

Keep only an addition that improves the target failure without a critical holdout
regression. If that comparison has not run, label the advantage unverified; a
routing/schema pass does not establish model behavior or justify a superiority
claim. Carry authorized implementation through its native gate, and distinguish
an implemented local candidate from a behaviorally accepted or published release.

## Handoff

Report what was reused, its source, the Codex adaptations, the specific added
rule, validation and behavioral results, discarded changes, and remaining proof.
