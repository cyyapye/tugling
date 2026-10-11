# UX correction diagnostics

Measure consequential corrections needed in the **first delivered interface**,
before user feedback. The agent may review and repair internally before delivering;
that is part of the skill being tested. A later user-feedback repair is a separate,
immutable stage. These local diagnostics neither call a model nor certify a release.
The existing promotion suite and approved controller pins are unchanged.

The three bundled cases reconstruct recurring failures with synthetic facts:
incomplete editing, independent draft removal, useful history, related records,
and precise meanings. Their briefs state the user's task and facts, rather than
enumerating the desired design. The author has seen candidate guidance. They are
**known development cases**, never independently authored or unseen holdouts.
Preserve all earlier studies and their scores; do not rewrite ties into wins.

## Measurement and decisions

Each frozen criterion describes one task-level consequence. Count its failure
once per artifact across widths, with concrete rendered/interaction/storage
evidence. Do not count screenshots as separate samples. Target corrections are
the primary descriptive metric. Critical failures and guardrail failures veto a
favorable result; a target win cannot hide a case-level regression. Taste changes,
new requirements and necessary clarification of missing facts are not corrections.

- `SATURATED`: released has no target corrections, leaving no measurable lift.
- `NO_MEASURED_IMPROVEMENT`: candidate did not reduce released correction burden.
- `IMPROVEMENT_SIGNAL`: fewer target corrections, without guardrail or case regressions.
- `REGRESSION`: candidate loses a critical invariant, guardrail or target case.
- `INCOMPLETE`: a review unit lacks evidence. Missing usage prevents review admission;
  it is retained as unknown, never counted as zero.

A confirmation signal additionally requires three matched attempts, a fresh target
holdout, a candidate-blind external task author, an independent reviewer who
attests blinding, and improvement on that holdout. Identity attestations are
recorded metadata, **not automated proof of independence**. A maintainer must check
their provenance. Paired counts remain descriptive; this small study does not
establish statistical or product-wide causal benefit. No result authorizes release.

For confirmation, have a separate author prepare task/context/fixture/checks and
criteria outside candidate access, with a provenance note and `candidate_aware:
false`. Mark new target cases `holdout`; do not rename observed cases as unseen.
Freeze before admission. Keep the rubric and observer files outside builders'
workspaces. Use the same initial inputs and tools for every arm. Separate author,
candidate author, operator and reviewer identities; the tool rejects several obvious
role collisions but cannot detect false declarations or inferred condition identity.

## Local workflow

`scripts/ux_eval.py` is a measurement layer around completed native runs. Use the
repository's isolated CLI transport and `RunBudget` for paid calls. Do not pass
the advisory suite's multiple-choice questions to builders: supply only task.md,
context.md and index.html plus identical environment instructions. There is no new
paid runner or release path here. Obtain exact-source and usage authority before
admitting a comparison.

```bash
python3 scripts/ux_eval.py validate
python3 -m unittest tests.test_ux_eval
```

Prepare an external runtime.json with model, effort, cli_version, browser_version,
timezone, locale, operator_id, candidate_author_id, attempts (1–3), timeout_seconds
(30–600), repair_rounds (0–2, default zero), max_calls
(cases × three arms × attempts × (1 + repair_rounds), at most 36), positive
max_input_tokens/max_output_tokens, and viewport strings such as `1280x900` and
`390x844`. Include a phone width at most 480px and a desktop width at least 1024px;
two nearby widths on the same surface cannot supply responsive evidence.
`sources` maps released/candidate to full `commit` and `skills_sha256`.
Use exact committed skill trees; independently verify those source bindings.
The capture layer cross-checks producer declarations; it does not authenticate a
CLI or prove which instructions a model read.

Runtime `preflight`, `calibration` and `observer_files` reference relative files
outside Git. Preflight must exercise the builder's full admitted invocation and
sandbox: source reads, a real file edit, and the actual supplied browser opening,
operating, reloading and reading persistence at both widths. A browser-only smoke
can pass while native file tools are unusable. Include Git trust setup and prove
skill discovery/body access separately; materialized files do not prove consumption.
Do not layer an outer sandbox without checking that the CLI's native tool sandbox
can run inside it. Keep hidden study inputs inaccessible while repairing isolation.

Preflight requires `builder_probe` with relative file references `before`,
`source_readback`, `expected`, `after`, `events`, `execution` and `stderr`, all
relative to the runtime file's directory. Retain a synthetic initial source with
a fresh unrendered marker that is absent from the prompt, the builder's exact source
readback, the independently specified expected edit, the actual delivered source,
raw CLI events/stderr and execution/cleanup receipt. The expected edit must change
the source; the actual source must match it. Events must include a successful native
edit tool and exactly one valid usage receipt. Observe the edited artifact in the
browser at both widths. These structural checks bind retained evidence; an operator
must still verify producer identity, source access, invocation parity and the actual
browser observations. They cannot prove a model read a skill from its own claim.
The freezer retains and hashes every probe dependency outside Git.

Calibration must retain actual expected/observed evidence for controls
named valid-alternative, lost-edit, meaning-loss and unprotected-erasure. A receipt's
`passed: true` and control names are required metadata, not a replacement for
examining that evidence. Freeze the **actual observer code** and dependencies;
the preparer copies it, the criteria, fixtures, runtime and evaluator into an
immutable hashed package. A schema/unit-test pass is not browser calibration.
The running evaluator must match the frozen evaluator bytes. Run the retained
evaluator for an existing freeze; a changed grader needs an explicitly labeled
new regrade, rather than silently emitting a new result for the old code digest.

```bash
python3 scripts/ux_eval.py freeze --suite /private/study/cases.json \
  --runtime /private/study/runtime.json --out /private/study/frozen
```

Follow frozen schedule.json for serial, counterbalanced admission. Reserve equal
time for reporting. Stop on incomplete delivery, missing usage, observer/runtime
failure or cleanup failure; preserve failed attempts. Admission token limits are
checked **between calls**, not hard in-flight billing caps. Never replace a timed-out
attempt with a favorable retry or pool a changed runtime under the original freeze.

Immediately after the completed CLI call, before external feedback, capture the
saved index.html, raw events.jsonl, native stderr and a producer receipt. The receipt records
freeze_sha256, runtime_sha256, fixture_sha256, skills_sha256 (null for control),
model, effort, case, condition, attempt, phase, exit_code, timed_out,
cleanup_complete and user_feedback_received. First delivery requires the last
field to be false. Hashes must bind the actual source/admission records. The tool
extracts usage from exactly one completed-turn event, preserves unknowns and
refuses overwrites. Zero input tokens are invalid like the native `RunBudget`.
A completed turn and zero CLI exit code do not prove native tools worked. A failed
native file-change event plus a matching artifact write denial in stderr and an
source unchanged from the phase's input is retained as incomplete and stops further
admission. First delivery compares the original fixture; a repair compares its
immediately preceding retained artifact. Ordinary
patch misses and recovered edits do not trigger that boundary. Inspect source-read
and other runtime failures independently; this narrow diagnostic is not a complete
classifier of every CLI or sandbox failure.
All retained phases share the frozen usage/call limits; an overshooting attempt
is preserved as incomplete and cannot enter review or admit another capture.
Review and assessment independently recheck the cumulative retained budget.
They recompute completion and usage from retained raw events and the producer
receipt, rejecting contradictory capture summaries. A hashed artifact-path
binding preserves native write-denial matching after the artifact is copied;
repairs use the verified preceding artifact as their input. This checks retained
consistency without authenticating the external producer. A partially written
trial, including one interrupted by a screenshot-copy error, blocks subsequent
admission and review; preserve its raw evidence rather than assigning zero usage.
Screenshots are optional at capture; actual review evidence
at both widths remains mandatory.

```bash
python3 scripts/ux_eval.py capture --frozen /private/study/frozen \
  --records /private/study/records --case shift-plan --condition candidate \
  --attempt 1 --artifact /private/trial/index.html \
  --events /private/trial/events.jsonl --stderr /private/trial/stderr.txt \
  --receipt /private/trial/receipt.json
```

After all frozen trials are captured, create randomized reviewer samples. Keep the
key away from the reviewer. Give them its **digest**, not its contents. The bundle
contains delivered working HTML, the identical common original HTML with its
complete source population/facts, original task/context, observer procedure, review
criteria and optional screenshots. It excludes arm identities, skills, runtime,
builder prose, traces and scores. Presentation may reveal authorship accidentally;
reviewers must record any exposure rather than claim perfect blinding.

```bash
python3 scripts/ux_eval.py bundle --frozen /private/study/frozen \
  --records /private/study/records --out /private/study/review \
  --key-out /private/study/condition-key.json
```

The reviewer writes review.json in the bundle root with reviewer_id,
blind_attested, key_sha256 and samples keyed by sample labels. Copy each sample's
review-template.json into that map. Record each unit's outcome (pass/fail/unknown),
a concrete finding and evidence entries with kind, viewport and relative file.
Use saved browser observations/PNG/storage readbacks in the sample directory.
Storage criteria require storage evidence; screenshots cannot establish reload
persistence. Evidence must cover every frozen width; byte comparisons use `all`.
The exact-copy case additionally has an executable byte oracle that rejects a
contradictory reviewer scope claim. Supported equivalent labels and layouts get
equal credit. Assert the outcome of an action, not just successful tool execution.

```bash
python3 scripts/ux_eval.py assess --frozen /private/study/frozen \
  --records /private/study/records --bundle /private/study/review \
  --key /private/study/condition-key.json --out /private/study/first-result.json
```

Capture budgeted external-feedback repairs as repair-1 and repair-2, requiring the preceding
stage. Review each in a fresh bundle/key and score separately. Report actual feedback
rounds and time from retained producer receipts; absent repair data is unknown,
not zero effort. Freeze the feedback policy before calls and give arms equivalent
task-grounded feedback. A repaired pass never changes the first-delivery score or
satisfies its improvement gate. This tool supports at most two recorded repairs;
it does not prescribe a universal two-round design process.

If an observer is defective, preserve its frozen version, original findings and
all artifacts. Correct it under a new version and replay **all** matched artifacts,
labeling regrades; do not selectively change an arm's score. Reviewed outcome
quality, process compliance, installed-skill discovery and resources are separate
proofs. Keep raw studies, paths, credentials and adopter data outside Git.

Evaluator/fixture changes require the separate [controller review](../../docs/release-controller.md).
`make verify` validates these development cases and measurement tests without
models; it does not activate a controller, certify UX improvement or promote a skill.
