# Design-judgment calibration controls

These six self-contained, synthetic interfaces support the
[judgment review](../README.md). They share the same task, facts, contact editor
and browser storage. Two use different valid layouts; four deliberately make
an otherwise working task harder. They are rubric controls, not builder tasks
or evidence of skill improvement.

The operator can read `expected.json`. Keep it, this README, the descriptive
filenames and this source directory away from the independent reviewer. Prepare
a fresh review bundle outside Git:

1. Copy each HTML file to a randomly named sample directory as `index.html`.
   Retain the name mapping and SHA256 hashes separately from the reviewer.
2. Include only `task.md`, `facts.json` and the judgment rubric alongside samples.
   Freeze the rubric, expected labels and sample hashes before review.
3. Open every sample in fresh browser storage at 1440×900 and 360×800. Capture
   the initial viewport, the Battery desk editor, the save attempt, reload and
   the reopened editor. Keep viewport captures from moving keyboard focus.
4. Perform the task using the visible interface. If saving requires extra work,
   retain the first failed attempt and that work; do not conceal it in a setup
   script. Read the reopened channel/address as well as browser storage.
5. Have the reviewer inspect rendered states and task observations before source,
   save per-sample findings and accept equivalent layouts. Reveal the key only
   after that review is saved.

All samples must preserve the three station identities and staffing counts.
After the task, only Battery desk's contact becomes SMS / +1 202 555 0176.
The storage key is `repair-clinic-v1`. Use a fresh isolated origin/context per
sample so they cannot share saved edits. No network or account is needed.

Calibration succeeds only when both valid alternatives are accepted and each
flawed control's consequential problem is identified, with complete supporting
observations at both widths. Investigate discrepancies without rewriting the
expected labels to fit the review. Successful button clicks or exact storage
alone do not establish good design. Passing these deliberately clear controls
does not establish sensitivity to every subtle or unfamiliar UX problem.

Retain screenshots, observations, reviewer exposure and findings outside Git.
Do not commit raw model output or call these controls an independently authored
holdout. Local `make verify` checks repository integrity, not reviewer judgment.
