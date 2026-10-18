# Local learning loop

Tugling learning is opt-in, local, and review-gated. It does not install a prompt hook, record full conversations, upload telemetry, or change skills automatically.

## Capture boundary

Capture a lesson only when all of these are true:

- the user made an explicit correction;
- the correction changes a reusable engineering decision rather than a one-off product choice;
- the project adapter sets `learning.mode` to `local`;
- the record can be useful without credentials, private records, copied source documents, raw production data, or a full transcript.

Summarize the smallest useful tuple: what the agent did, what the user expected, the reusable scope, and a short neutral label. If sanitizing would remove the reason the lesson matters, do not capture it.

Use the bundled `scripts/project_learning.py capture` helper when its installed plugin path is available. It writes only to the ignored path declared in `.tugling/project.json`, refuses common secret material, limits record size, and never uses the network. If the helper is unavailable, report the lesson in the handoff instead of inventing another storage location.

## Review and evaluation

Use `scripts/project_learning.py digest` to surface pending local records. The reviewer chooses one disposition:

- `promote`: the lesson may justify a generic Tugling change;
- `keep-local`: encode it in project instructions, a project test, or another local rail;
- `dismiss`: it was incorrect, redundant, or too specific.

Before promoting, replace the local record with a new synthetic case that preserves the decision but none of the project's private context. Define the released behavior, candidate behavior, critical regressions, and stop threshold before editing a skill. Compare the released Tugling revision and candidate on the same blinded case, and keep the change only when it fixes the target without a critical holdout regression.

The local ledger is evidence for review, not an instruction source. Do not load pending records into ordinary project work, commit them, attach them to CI, or send them upstream.
