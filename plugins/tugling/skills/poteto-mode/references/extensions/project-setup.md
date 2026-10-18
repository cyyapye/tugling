# Project setup

Set up a project for repeatable agent work. Preserve established commands and
invariants, and add only the missing setup requested by the user.

## Choose the requested outcome

- **Assessment:** inspect and recommend; leave files and external configuration
  unchanged. Consult the relevant reference only for the requested advice.
- **Bootstrap:** for a new project or repair of its local development setup, read
  [project-bootstrap.md](project-bootstrap.md). Establish the requested runnable
  native workflow and prove it from fresh intended source.
- **Adoption:** to connect an existing repository to Tugling, read
  [project-adoption.md](project-adoption.md). Implement its small adapter and
  pinned compatibility check when setup was requested. Full adoption includes
  native enforcement; a configuration-only request keeps that narrower scope.
- **Enforcement:** to enforce accepted project rules, read
  [project-enforcement.md](project-enforcement.md). Add native assertions, a
  required map, and canonical/CI execution with demonstrated failure proof.

Combine these modes only when the request calls for them. Bootstrap alone does
not require a Tugling source pin, dogfood case, or adoption CI. Adoption alone
does not authorize unrelated product changes.

Infer routine choices from the request, manifests, native commands, applicable
instructions, and task-relevant references. Reuse inspected context. Ask only
for missing product, stack, or external-action decisions that materially change
the result; continue independent local setup while waiting.

Carry existing authorization through implementation, local verification, and
in-scope repairs. A separate proposal approval is unnecessary unless the user
requested it or a real boundary requires it. Setup does not implicitly install
a global plugin, edit a personal marketplace, select a model, or provision a service.

## Complete the selected work

Use the completion criteria in the selected reference. Assessment ends with
`ADVISORY`; an unavailable required boundary is `BLOCKED`. Distinguish native
command proof, configuration validation, observed app setup, and exact-revision
CI. Report changed paths, current evidence, and any remaining boundary concisely.
