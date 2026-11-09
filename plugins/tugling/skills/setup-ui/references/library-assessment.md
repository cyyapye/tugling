# Assess the project's UI library

Judge completeness against the project's actual user journeys and supported
surfaces. A catalogue of exported names or a generic component checklist cannot
establish that the library serves those needs.

## Establish current evidence

Find the canonical product/design rules, theme definitions, shared exports,
component implementations, rendered catalogue or reference screens, consumer
routes, and native verification. Read any existing assessment and compare its
source revision and conclusions with current usage. Completed candidates are
not new work merely because they appear in an old report.

Trace representative journeys through their real components and meaningful
states. Cover loading, empty, error, disabled, selection, keyboard/focus, and
responsive behavior where those states apply. In a large project, prioritize
high-use controls and important journeys, then state the inspected boundary and
what remains unknown. Static code can establish wiring and reuse; it cannot
prove rendered usability or accessible interaction.

Record a compact needs-to-coverage map. For each relevant pattern, identify the
current implementation and consumers, necessary variants/states, evidence, and
any gap. Distinguish:

- a missing capability that existing journeys need;
- an existing component that pages do not use;
- a missing variant or extension point in a suitable component;
- inconsistent tokens or unsupported consumer overrides;
- missing documentation, catalogue examples, or verification;
- an intentional local pattern with no stable shared contract.

Use rendered evidence to investigate visual differences before recommending a
visual unification. Keep an unresolved difference explicit when that evidence is
unavailable. Do not replace the project's library or add a framework to fill an
imagined completeness checklist.

## Find the smallest useful reuse boundary

Search for repeated interaction structure, state handling, accessibility wiring,
and styling across actual consumers. Class strings are leads, not an extraction
oracle. Inspect the smaller primitives inside a tempting page-sized composite.

Before recommending a new component, check whether a current primitive, variant,
or composition already solves the need. Name the independent consumers and their
shared inputs, states, and behavior. Preserve differences in domain meaning,
authorization, copy, data fetching, and actions. Visual resemblance does not make
an owner dashboard, patient flow, and operator console the same component.

Choose ownership from the repository's rules: generic UI library, shared domain
layer, app-local component, or private helper. Repetition inside one implementation
may justify a private helper without creating a public cross-app API. Do not
enforce a fixed consumer count when clearer evidence establishes a reusable
contract, but identify speculation and avoid abstracting a one-off possibility.

For each actionable recommendation, include:

- current source locations and consumers, plus rendered evidence when relevant;
- the unmet need or duplication and why an existing component is insufficient;
- reuse, extend, extract, or keep-local decision and the proposed ownership;
- a concrete API/variant or composition boundary, including preserved differences;
- expected user/maintenance benefit, effort, migration risk, and verification path.

Rank by demonstrated impact and reuse, confidence, and cost of changing callers.
A recommendation to reuse an existing primitive may outrank a new abstraction.
Keep weak candidates in a clearly labeled watchlist or close them with reasons.
Do not manufacture candidates when the existing library covers the inspected needs.

## Record the result

During setup, propose updating the existing assessment or the project's canonical
document location, and write it once that change is approved. Keep one
authoritative recommendation list and link to component rules,
examples, and tests. State what was inspected and what was only inferred.
For assessment-only requests, give the same evidence-backed result in the reply
unless the user requested a saved report. In the setup wizard, present concrete
recommendations for selection and implement the approved subset; assessment alone
does not authorize refactoring consumers. Preserve deferred and declined decisions.
