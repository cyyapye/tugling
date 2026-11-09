# UI setup development cases

These cases exercise the Tugling-authored
[`setup-ui`](../../plugins/tugling/skills/setup-ui/SKILL.md) entry point. They
supplement the existing evidence-helper and style-policy tests; they are not a
release certification matrix or evidence of an advantage over Pstack.

The concrete gap is discoverability and scope: `setup-pstack` configures model
preferences, while UI setup previously required reaching project-setup and
project-evidence references manually. The new command also requires assessing
actual consumer needs and recommending reuse before configuring enforcement.
It delegates profile, capture, and reviewer mechanics to the existing helpers.

## Run a bounded development pass

Follow [the evaluation method](../pstack/method.md). Copy a fixture to an isolated
temporary workspace and expose the current skill bundle there. Supply only the
ordinary request and project files to a fresh agent. Keep this directory's case
criteria, other agent outputs, and the parent observer outside that workspace.
Freeze the package and all project-file hashes before the run. Check every file,
including ignored files, after read-only cases and review the actual reply and
tool trace against the frozen criteria. Do not grade instruction wording.

[`cases.json`](cases.json) contains the authored development requests and criteria.
The Mend House request and [criteria](holdout-criteria.md) were authored by an
independent agent without the candidate. See [initial observations](observations.md)
for the executed cases and their limits. A later
[configured-adopter trial](adopter-observations.md) exercised setup replay, native
lint and browser checks, and an actual independent rendered review.
The later [guided approval trial](wizard-observations.md) exercises the wizard's
decision boundaries, selected implementation, step results, and skipped work.
Earlier observations describe their frozen packages, not this revised flow.
The appointments fixture is a source excerpt, so it cannot establish rendered
usability. The help request checks scope, not automatic skill discovery. Author
fresh tasks without reading the candidate before claiming holdout coverage;
after a held-out task is used to tune instructions it becomes a development case.

For a full setup attempt, use a runnable disposable adopter with its real native
lint and browser commands. Observe a prohibited-style failure and repaired pass,
current-run captures, an actual independent reviewer response, its validation,
and a no-op configuration replay. Missing capabilities remain unverified. The
existing helper's unit tests cannot substitute for that observed skill execution.

Keep raw responses, model/session identities, traces, and source snapshots in
private local artifacts. Record bounded observations and limitations separately;
do not include adopter data or raw transcripts in the repository. No test here
changes approved controller pins, installs the candidate for a user, or publishes
the plugin. `make verify` remains model-free.

## Refreshed Pstack candidate

The 0.10.0 release candidate updates the Pstack base and carries the wizard
forward with native-lint and evidence-input lessons from a configured adopter.
The earlier observations describe their frozen packages, not this revision.
Keep new observations, native failures and environment-recovery attempts
separate. This remains an explicitly invoked Tugling addition; compatibility
checks and one adopter trial do not establish an advantage over Pstack.
