---
name: screenshot-first-ui
description: Design and verify defined UI flows, clickable proposals, or implementations using desktop/mobile evidence. Use for hierarchy, editing, disclosure, or visual defects; skip branding, undefined product flows, and isolated exact-copy edits.
---

# Screenshot First Ui

Treat a screenshot as product evidence, not decoration.

Apply this workflow while designing an existing or defined flow, including a clickable proposal, and while implementing an approved design. Check whether the delivered interface lets the user understand and complete the task; preserve the product's decisions and shared patterns.

## Inspect before editing

1. Read the repository's interface, accessibility, copy, and visual-test contracts.
2. Inspect the affected state in the running product at the supported desktop and narrow breakpoints when possible.
3. Compare it with the closest established screen or component in the same product.
4. Preserve deterministic, non-sensitive fixtures in captured evidence.

If no screenshot or runnable state is available but the user gives concrete symptoms, make a provisional diagnosis and state what would confirm or overturn it. Ask for visual evidence only when the symptoms do not support a useful category.

## Carry the task through the interface

Identify the user's main questions, ordinary actions, and the values or objects those actions change. Reconcile them with the existing capabilities and product facts before arranging the screen. A readable fact, an imported source, and an editable input are different capabilities; do not silently defer an ordinary task or treat a missing product decision as a layout choice.

Trace each ordinary task through the initial view, expanded detail, editing, and saved result:

- **Answer before detail.** Preserve the main answer in the initial or collapsed view. A section heading should describe what opening it reveals; remove a repeated summary when it adds no decision-relevant information. Keep exceptions or uncertainty visible when they change the answer.
- **Action beside its subject.** Place an edit action with the value or group it owns. Use a short visible label when nearby context supplies the object, and an accessible name that distinguishes repeated controls. Avoid placing an action between unrelated values where its scope becomes ambiguous.
- **Complete the supported input.** When offering another representation or mode, provide the fields needed to enter it and verify save and reopen. Keep independent choices independent. Preserve the product's conversion, precision, unknown-value and validation rules rather than inventing them from the layout.
- **Show the meaning of a change.** Distinguish a difference from an ordinary amount; express direction and units according to the product contract. Handle zero, unavailable comparisons, and percentage versus percentage-point changes explicitly where relevant.

Before delivery, remove redundant labels, explanations and repeated answers from this reading path. Retain wording that establishes scope, uncertainty or accessible meaning. Evaluate the consequence for this task; a preferred layout or shorter label alone is not a reason to redesign an established pattern.

## Classify the defect

For a reported or observed defect, choose the primary category before proposing a fix:

- **Measure**: line length, wrapping, or content width destabilizes the composition.
- **Wrapper alignment**: sections do not share outer rails, centering, or maximum width.
- **Hierarchy**: headings, labels, values, metadata, or actions compete for attention.
- **Repeated surfaces**: unnecessary cards, borders, badges, bands, or dividers flatten the page.
- **Vertical rhythm**: spacing does not express relationships between groups.
- **Responsive behavior**: the narrow layout is merely wrapped, clipped, reordered poorly, or horizontally scrolls unintentionally.
- **Interaction semantics**: hover, cursor, chevron, selected state, or button styling promises behavior that does not exist.
- **State and copy**: loading, empty, success, warning, or error language misstates the user's situation or required action.

Name secondary categories only when they change fix order.

## Fix in the right order

1. Restore the structural contract: wrapper, information hierarchy, grouping, interaction semantics, or responsive composition.
2. Remove unnecessary surfaces and copy.
3. Adjust tokens such as padding, gap, font size, or line height only after the structure is sound.

Several failed spacing nudges are evidence that spacing is probably not the primary defect.

## Verify a material change

For a material implementation or clickable proposal:

1. Use the repository's shared components and closest reference screen before adding a new pattern.
2. Capture deterministic current-run screenshots at the supported desktop and narrow breakpoints.
3. Inspect every generated image for hierarchy, clipping, overflow, density, contrast, focus, and misleading affordances.
4. Walk the affected ordinary task through its initial view, editing, save or cancel, and reopened result where applicable. Inspect the reading path as well as functional coverage; working controls alone do not prove clear priority or ownership.
5. Update a canonical baseline only after the new image is intentionally correct, then rerun without update mode.
6. Complete the repository's native gate for the delivered artifact; use `$repo-verify` if its contract is unclear, failing, or needs a readiness review. For a prototype, state which saves, sources, or host behavior are simulated. Prototype proof does not establish production behavior.

## Handoff

Report the user task or primary defect, the change, screenshots inspected, interaction proof, closest product reference used, and remaining uncertainty.

Report a requested read-only diagnosis as `ADVISORY`, even when no edit was authorized. Use `NOOP` only when a bounded requested implementation is already satisfied or absent, not merely because the task was diagnostic.
