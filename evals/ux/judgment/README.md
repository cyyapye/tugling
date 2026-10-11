# Evaluate design judgment

Use this review alongside the existing task-correctness and state guardrails.
Its question is whether a first delivery needs consequential UX correction before
the ordinary task is clear and comfortable. Working controls alone do not answer
that question. This is a development method; it neither calls models nor changes
release-controller authority.

## Before building or viewing results

Freeze a short task card with the user, ordinary goal, primary questions, relevant
facts, necessary decisions and supported widths. Ground priority in the user's
work, not the current layout. The builder receives the goal and product facts;
keep the diagnosis, desired layout, review anchors and examples out of its brief.
Do not remove necessary product constraints to make a task harder.

Freeze the rubric and task-specific consequences. Keep observed development
cases separate from untouched holdouts. Selecting cases where released fails is
development screening; retain every screened outcome and do not present the
selected subset as an unbiased estimate of overall benefit.

### Check what the builder must actually decide

Before spending on a new screen, include a short decision-opportunity record in
the task card. Name the intended adopter work, model/effort and repository context.
For each target judgment, distinguish what the brief and product facts specify,
what the working starter already implements, and what the requested change leaves
the builder to decide. Record important differences from the work being improved,
including scope, existing UI patterns, context size and state boundaries.

A starter with clear summaries, action ownership and comparison wording can test
whether a new feature preserves those decisions. That preservation alone does not
show that added guidance improves making them. Choose ordinary feature work that
creates relevant new decisions; keep useful existing behavior and necessary
product facts. Do not deliberately damage a seed, prescribe the preferred remedy,
or increase unrelated coding difficulty to manufacture a released failure.

Freeze task selection, the number of development screens and the stop rule before
new calls. After a saturated screen, retain its regression value and audit coverage
before spending again. Repeated zero-gap screens mean no demonstrated incremental
benefit under the sampled conditions. They do not justify changing severity,
discarding ties, or claiming that all other adopter work is solved.

## Review the first delivery

Randomize sample names/order and remove condition identities, skill instructions,
builder explanations and prior verdicts. Record reviewer exposure honestly.
Render the initial state at desktop and phone widths before exploring. Answer the
task card's questions using only what the interface communicates. Perform the
ordinary task, including its saved result, before reading source for verification.

Inspect the following dimensions. A preferred component, color, section count,
word count or universal click limit is never an oracle.

| Dimension | Consequential failure | Acceptable alternative |
| --- | --- | --- |
| Priority | Optional setup/support information obscures the main answer or corresponding action; finding it requires unrelated navigation or scanning. | Different layouts expose the same main answer clearly; a real blocking exception can take priority. |
| Relationships | Users must infer which value, state, object or action belongs together; the layout implies an incorrect relationship or forces unnecessary memorization. | A table, aligned rows or cards can each preserve meaning; separate views are valid when simultaneous comparison is unnecessary. |
| Copy and disclosure | Repeated sections or explanations compete with the task, conceal a necessary distinction, or make users open detail to learn the main answer. | Necessary scope, uncertainty, accessible names and context across distant views remain, even when repeated. |
| Task effort | An ordinary task requires avoidable context switching, re-entry or unrelated mandatory information; the editor omits a necessary supported term. | A necessary confirmation or genuinely missing required input is not friction to remove. |
| Feedback and recovery | The interface leaves the result/scope of an action unclear, or users cannot predict what preserves, saves, cancels or removes their work. | Equivalent clear action names and recovery patterns receive equal credit. |

For every finding, retain: the user's goal, starting state/width, actions or reading
path, exact observed ambiguity/obstacle, task-grounded consequence, evidence file,
and the smallest correction needed. Include a plausible alternative interpretation
and why the task facts do or do not support it. Do not count generic checklist
noncompliance without a demonstrated consequence.

Classify findings before counting:

- **Critical:** wrong consequential action/meaning, data loss or a violated task
  guardrail. Veto a favorable result.
- **Major:** an ordinary task/answer requires a substantial avoidable search,
  inference, correction or workaround. State the concrete consequence.
- **Minor:** a smaller, observed usability correction that adds avoidable effort
  or uncertainty without substantially impeding the task. State its task effect;
  report separately from the primary consequential correction count.
- **Preference:** a cosmetic or stylistic alternative without an observed task
  effect. Record separately; do not count it as a usability correction.
- **Unknown:** insufficient observation or an ambiguous product requirement.
  Resolve the evidence gap; never turn it into a pass or zero corrections.

Count a root defect once across widths and dimensions. For example, an optional
support panel that pushes the main answer away is one priority correction even
if it also adds excess copy. A screenshot, click and observation are not separate
samples. Record minor findings and raw effort separately rather than inflating
the major count. Repeated minor problems may matter to the user: define their
practical significance and the repetition needed before building, retain their
severity, and report that result separately from major-correction improvement.
Do not relabel them after seeing results or pool preferences into a favorable
score. Do not claim measured human comprehension time from a model's reading or
elapsed tool time.

After independent per-sample findings, compare artifacts on the same task. A
pairwise preference must cite a difference already supported by the observations;
prefer a tie when the difference is cosmetic or uncertain. A pretty screen cannot
offset a critical failure or an incomplete ordinary task.

## Calibrate before spending on more builds

The [synthetic calibration controls](calibration/README.md) provide two valid
layouts and four functional-but-confusing examples with a separate operator key.

Use at least two meaningfully different valid interfaces and deliberately flawed
controls whose buttons and persistence still work. Cover priority, relationships,
copy/disclosure and unnecessary effort; retain existing state/meaning controls.
An independent reviewer receives neutral samples and the task/rubric, without the
author's expected labels. It must accept both valid alternatives and identify the
specific consequential defect in each flawed control. Revealing the key happens
only after review is saved. Disagreement is a calibration failure to investigate,
not permission to rewrite expected labels to match the reviewer.

A deterministic checker may verify artifact hashes, controls, persistence and
review completeness. It cannot establish good hierarchy by counting elements or
reading an author-supplied priority flag. Retain rendered evidence and the actual
review findings. Calibration authored and judged by the same person is weaker;
record it as such, never as independent validation.

## Improvement and historical results

Report consequential first-delivery correction counts per task/attempt, critical
and correctness guardrails, pairwise findings, and separately time/usage. Define
the practical improvement threshold before new builder calls. Require repeated
benefit across representative tasks and a fresh holdout, with no critical or
case-level regression, before claiming a transferable improvement.
If the intended benefit is proactive judgment during ordinary feature work,
include those tasks; an explicit UI-repair brief alone does not represent that use.

Preserve first deliveries, later repairs and prior scores separately. Applying a
new rubric to retained artifacts is a labelled exploratory regrade; it cannot
retroactively become a preregistered confirmation. If the observer changes, replay
all matched artifacts. Both arms passing all relevant checks is saturation, not
proof that the candidate's extra instructions improved design judgment.

This follows the task-specific evaluation, comparison and calibration practices
in [OpenAI's evaluation guidance](https://developers.openai.com/api/docs/guides/evaluation-best-practices).
That guidance does not supply a UX quality oracle or validate this rubric.
