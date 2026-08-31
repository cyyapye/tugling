---
name: screenshot-first-ui
description: Diagnose and verify user-visible interface problems from current screenshots or a running app before proposing pixel tweaks. Use for visual polish, unclear spacing or hierarchy, responsive defects, overflow, misleading affordances, screenshot regressions, or material UI changes that need desktop and mobile evidence. Do not use for branding inspiration or a net-new flow whose product structure is still undefined.
---

# Screenshot First Ui

Treat a screenshot as product evidence, not decoration.

## Inspect before editing

1. Read the repository's interface, accessibility, copy, and visual-test contracts.
2. Inspect the affected state in the running product at the supported desktop and narrow breakpoints when possible.
3. Compare it with the closest established screen or component in the same product.
4. Preserve deterministic, non-sensitive fixtures in captured evidence.

If no screenshot or runnable state is available but the user gives concrete symptoms, make a provisional diagnosis and state what would confirm or overturn it. Ask for visual evidence only when the symptoms do not support a useful category.

## Classify the defect

Choose the primary category before proposing a fix:

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

When the user also asks for implementation:

1. Use the repository's shared components and closest reference screen before adding a new pattern.
2. Capture deterministic current-run screenshots at the supported desktop and narrow breakpoints.
3. Inspect every generated image for hierarchy, clipping, overflow, density, contrast, focus, and misleading affordances.
4. Run functional coverage for the interaction; a screenshot cannot prove behavior.
5. Update a canonical baseline only after the new image is intentionally correct, then rerun without update mode.
6. Use `$repo-verify` for the repository completion gate.

## Handoff

Report the primary defect category, evidence, structural fix, any remaining micro-tweaks, screenshots inspected, functional proof, and the closest product reference used.

Report a requested read-only diagnosis as `ADVISORY`, even when no edit was authorized. Use `NOOP` only when a bounded requested implementation is already satisfied or absent, not merely because the task was diagnostic.
