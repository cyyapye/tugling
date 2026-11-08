---
name: setup-ui
description: "Guide project UI setup through assessment, approval, implementation, and verification. Cover the component library, native style checks, browser evidence, and independent rendered review; not routine screen edits or model preferences."
---

# Set up UI delivery

Read the [Codex adapter](../poteto-mode/references/codex.md). This is a
Tugling-authored entry point; reuse the existing project workflows below.

## Resolve the requested outcome

- **Setup** (including a bare `$setup-ui`): guide the user through the ordered
  steps below, requesting approval for proposed changes before applying them.
- **Assessment or recommendations only:** inspect and advise without changing
  files, dependencies, settings, or CI. Write a report only when requested.
- **Help:** explain how to invoke the skill; do not start setup.

Infer scope from the request and project. In a monorepo, identify the UI surfaces
and report which are covered. Reuse existing assessment reports, adapters,
catalogues, and native checks. A single-screen fix uses the existing workflow;
it does not trigger a project-wide audit. Model preferences belong to
[`setup-pstack`](../setup-pstack/SKILL.md).

## Guide the user through setup

Start with a short itinerary: inspect the project, configure approved checks,
implement selected UI improvements, then verify and review the result. Before
each step, explain its purpose, what will happen, and whether it changes files.
After each step, show the result, evidence or remaining uncertainty, and what
comes next. Use clear progress such as "Step 2 of 4: verification setup" without
making the user approve read-only inspection or acknowledge every progress update.

Before changing lint rules/configuration, dependencies, verification wiring,
components, variants, consumers, or other persistent project files, prepare a
concrete proposal with current versus proposed behavior, affected paths, tradeoffs,
and the checks that will prove it. Draft a patch or API example outside the project
when useful; do not apply it while asking permission. Offer approval of all or a
named subset, revision, or skipping the step. Wait for an explicit decision;
silence, a default selection, or a reviewer's agreement is not approval.

Reuse approval already given for the specific changes; do not ask again for their
implementation, necessary verification, or repairs within that agreed behavior.
A bare setup request is not blanket approval to change existing policy or UI.
Record selected and skipped items in the conversation and existing report when
authorized. Proceed with independent approved work while a decision is pending;
do not cross its boundary or imply the pending work is complete. A skipped step
must remain skipped on replay unless the user changes that decision.

## Step 1: inspect and assess

Use [library assessment](references/library-assessment.md) to map actual screen
needs to the available tokens, primitives, compositions, and verification.
Inspect consumers as well as exports. Examine relevant rendered examples when
available; label source-only conclusions and unavailable visual evidence.

Inspect without changing project files. Present the coverage map and initial
findings in the reply; include a refresh of the existing inventory or extraction
report in the later change proposal. Keep product rules in their canonical files
and link them rather than creating another design system or backlog. A new or
small project may need no component library or extractions; report that result.

Rank recommendations with concrete source evidence, consumer needs, proposed
ownership/API, expected benefit, effort, and regression risk. Distinguish reuse,
variant extension, extraction, and keep-local decisions. Show what already works,
the gaps, and the bounded surfaces inspected before moving to verification setup.

## Step 2: approve, configure, and prove the checks

For setup, follow [project UI evidence](../poteto-mode/references/extensions/project-evidence.md)
and [UI style enforcement](../poteto-mode/references/extensions/ui-style-enforcement.md).
These references own the profile schema, native lint integration, browser
capture, evidence packaging, and independent reviewer response protocol.

Show the existing lint and verification setup and the exact proposed additions
or changes, including enabled rules, enforcement scope, dependencies/lockfiles,
profile, native commands/CI, and report updates that are actually needed. Explain
what new failures existing consumers may encounter. Get approval for this batch,
then implement only the selected changes. If nothing needs changing, say so and
verify the existing setup without manufacturing a proposal.

Bind an approved `.tugling/ui.json` to the actual themes, components, catalogue or reference
screens, product contracts, supported viewports, and native commands. Track the
relevant configuration, dependency lockfiles, assets, and authored guide inputs.
Reuse a generated guide if one exists; setup does not require inventing one.
Check the evidence helper's actual file selection as well as the profile: adding
a path to configuration does not prove that the helper hashes it. Include the
lint, build, browser harness, dependency and image/font inputs that can change the
reviewed result. Use the project's supported platform for screenshot baselines;
functional browser checks on another platform do not establish pixel equivalence.

Map accepted project rules to actual lint errors. Existing overrides are audit
evidence, not automatically approved exceptions. When current consumers conflict
with a rule, explain the gap and the bounded enforcement scope; do not blanket
allow violations or redesign screens just to pass. Preserve legitimate component
extension points and unsupported-stack boundaries.

Prove a prohibited style fails through the normal lint command, repair the
disposable probe, and prove valid composition passes. Restore the probe without
touching user work. Show the actual rule/file/error and passing control, the
changed paths, and the enforced versus unsupported scope. Existing product
violations go into step 3; they do not authorize weakening rules or changing UI.
Where the project requires shared controls, exercise a prohibited raw control
and an inline restyle as well as an allowed variant and layout placement. Keep
those requirements project-owned. A helper-only assertion is not native lint
enforcement, and a JSX rule does not establish CSS or rendered correctness.
If no runnable way to drive the app exists, propose the missing verification
work and, once approved, use
[`create-verification-skill`](../create-verification-skill/SKILL.md).

## Step 3: approve and implement UI improvements

Present the ranked recommendations as selectable, concrete changes. For each
item or coherent small batch, show the consumers and proposed reuse/extraction
boundary or variant API, preserved behavior, affected paths, risks, and proof
plan. Include source-backed defects found during setup, without treating all
recommendations as mandatory prerequisites for verification.

Ask which changes to implement unless the user has already authorized them.
After approval, implement the selected items, update affected consumers and
canonical documentation/catalogue examples, and run the relevant native checks.
Show each batch's before/after behavior, diff or rendered evidence, test results,
and unresolved limits before proposing another batch. Keep declined or deferred
items as recommendations; do not silently include them in an approved refactor.
If there are no justified improvements or the user skips them, report that and
continue with verification of the retained scope.

## Step 4: verify, review, and replay

Explain the browser journeys, viewports, and independent rendered review about
to run. Execute the native browser workflow and capture real current-run evidence
for the resulting approved state. Show native results and representative captures
before reporting the independent review's findings.

Delegate the packaged evidence to a fresh-context reviewer following the
generated first-look instructions. Preserve the actual response and reviewer
identity, validate it with the existing helper, and adjudicate findings against
project contracts. A reviewer finding is evidence, not user authorization. Repair
regressions within an already approved change and recapture; route newly proposed
lint/policy changes or product fixes back through the relevant approval step.
Show unresolved or declined findings without converting the review to a pass.
A configured profile or response template is not an executed review. If a
required browser or independent reviewer is unavailable, complete independent
work and report that boundary as unverified.
Give the reviewer read-only access to the packet and exactly the project
contracts it references. It saves unaided screen notes before reading those
contracts, the brief or reference screens. Capture transient and recovery states
after their defining condition has settled; a screenshot taken while a request
is still pending cannot prove the resulting failure or saved state.

Replay setup to confirm it preserves approved configuration and skipped decisions,
and reports only real drift; do not repeat approvals for unchanged work. Run the
project's appropriate final gate. Show native results separately from the advisory
review, including failures, skipped checks, and unavailable evidence. Keep model settings,
plugin installation, publication, and deployment within the user's stated scope.

## Handoff

Report what was approved, implemented, verified, skipped, or remains pending,
separating library recommendations from checks actually configured and executed.
Include coverage limits, changed paths, native results, screenshot/reviewer
evidence, and unresolved findings. Incomplete or declined setup is partial, not
a completed step. A working
verification setup does not establish library completeness, universal defect
detection, or release approval. An assessment-only result does not claim setup.
