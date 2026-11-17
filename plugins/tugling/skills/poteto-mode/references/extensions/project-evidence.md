# Project UI evidence

Use for requested repeatable UI setup or material work in an already configured
project. Keep the project's product rules, approval boundary and native gates
authoritative. The helper packages evidence and can execute approved profile
checks through `run-checks`; it does not itself render a browser, evaluate
accessibility, call an LLM or certify design quality. Native browser commands
remain responsible for actual captures.

## Configure once, inspect for drift

Discover the actual theme/tokens, shared exports, catalogue or reference screen,
product/copy/accessibility rules, supported viewports and native checks. Reuse
what exists. Missing components or rules are a project decision, not permission
to install another UI library. If proposing a new theme or flow requires user
review, make it concrete before seeking approval under that project's contract.

Prepare a JSON profile with this shape, using paths relative to the adopter:

```json
{
  "schemaVersion": 1,
  "project": "Example project",
  "contracts": ["docs/interface.md"],
  "sourceRoots": ["src", "browser-tests"],
  "sourceFiles": ["package.json"],
  "theme": "src/theme.css",
  "components": "src/ui/index.ts",
  "catalogue": "browser-tests/catalogue.tsx",
  "agentGuide": {
    "indexCommand": ["npm", "run", "ui-guide"],
    "queryCommand": ["npm", "run", "ui-guide", "--", "<component or task>"],
    "previewIndex": "/ui/agent-index.json"
  },
  "viewports": ["desktop", "mobile"],
  "references": {"reading": "Approved record detail"},
  "checks": {"browser": ["npm", "test"], "handoff": ["make", "verify"]},
  "criteria": [
    {"id": "meaning", "question": "Can the user infer the action and its scope?"},
    {"id": "fidelity", "question": "Does the result preserve the approved theme and essential qualifications?"}
  ]
}
```

Criteria, viewports, paths and commands belong to the project. The default when
viewports is absent is desktop/mobile, for existing adapters. Include relevant
assets and configuration in source roots/files; a file omitted from this list
cannot be checked for drift. Use narrow source roots excluding dependencies,
generated artifacts, private inputs and evidence output. Source roots include
all regular files, including image/font assets; symlinks are rejected.

`agentGuide` is optional discovery metadata for a project's existing guide. Omit
it when none exists; UI work alone does not require building a generator. When
present, inspect the commands before running them and query the relevant control
or task before coding. Keep its authored guidance, inventory, example sources
and generator covered by `sourceFiles` or `sourceRoots`, with canonical rules in
`contracts`. Guide commands are discovery metadata, not executed by this helper. Profile
`checks` are executed only by the explicit `run-checks` command; inspect their
argv and side effects within existing authorization first.

Run the bundled Python 3.11+ helper by its actual skill path:

```sh
python3 /path/to/poteto-mode/scripts/design_evidence.py --repo /project \
  init --profile /local/reviewed-profile.json
```

This creates only `.tugling/ui.json`. Repeating the same setup is a no-op;
different existing configuration is preserved and reported for explicit review.
It does not install dependencies, rewrite instructions or create CI. When native
enforcement was requested, connect project-owned assertions to normal checks
and demonstrate their failure against the prohibited behavior. Do not claim
enforcement from a profile listing commands.

## Finish requested verification setup

A profile alone is discovery metadata, not a working verification setup. When the
user requests enforcement, follow [UI style enforcement](ui-style-enforcement.md)
to configure the actual project linter and prove a prohibited change fails.
Include its config, dependency manifest and lockfile in source tracking. Run a
browser launch and one real capture before starting a material delivery; if the
runner cannot launch, resolve the supported execution path before claiming the
workflow works. Do not silently omit browser checks.

For requested judge setup, perform the Challenge step on real evidence and
validate the actual response. Preserve the reviewer session and first-look notes,
then repair accepted findings and recapture. A template validates neither reviewer
execution nor defect detection. A seeded-defect demonstration tests a known
capability; keep expected findings hidden from the reviewer and report false
positives and misses. It does not establish general design superiority.

## Install the durable handoff contract

After setup approval, add a project-owned native command (for example
`make ui-handoff`) and a scoped instruction in the adopter's existing `AGENTS.md`
or equivalent. Preserve unrelated instructions exactly. Resolve the helper by a
stable supported project mechanism; do not hardcode an author's plugin-cache or
machine path. Document its dependency and fail visibly if unavailable. Keep the
profile's `checks` limited to underlying native checks: including the wrapper
that calls `run-checks` would recurse. Do not replace the project's normal gate.

Adapt this instruction to the project's actual command and evidence locations:

> Before a completion handoff for a material UI change, or showing a user-facing
> material rendered proposal or prototype before implementation (including from
> scratch directories), follow the project's UI evidence contract and run
> `<native UI handoff command>` against the current
> immutable packet, actual native check receipts, and actual independent review.
> This applies in fresh threads without another setup request. Material changes
> include rendered structure, styling, interactions, states, and domain meaning.
> Mechanical or non-UI changes use focused checks unless they affect these UI
> contracts. Missing, stale, failed or unresolved evidence blocks a verified UI
> completion claim. Report the blocker; do not invent evidence or bypass it.

The instruction is durable project routing, not automatic invocation of a
Pstack skill. Preserve explicit Pstack invocation policy and existing approvals.
Neither this file nor the helper intercepts messages or prevents an agent from
ignoring instructions. Status updates and blocked handoffs remain possible;
they must not claim the UI gate passed.

The adopter owns criteria, supported viewports, task-specific required states,
commands, source coverage and evidence retention. Keep each run's packet, check
receipts, captures and reviewer artifacts immutable and separate from the next
run; do not overwrite a failed run. Bind the wrapper to explicit current inputs,
not a convenient old passing packet. Exclude evidence output from source roots.
Include the wrapper, instruction, harness and relevant configuration in source
coverage so changing the gate invalidates old evidence.

Prove the native entry point fails for missing evidence, changed source/evidence,
and unresolved reviewer findings, and passes for the current complete evidence.
Use disposable copies for negative probes, preserving real receipts and user
work. Replay setup without duplicating instructions or resetting approved policy.
An inspection of these files establishes wiring only; automatic invocation in a
fresh thread requires an observed run, not a routing/schema assertion.

## Use for a delivery

1. **Discover:** inspect the adapter, relevant sources and current render. Select
   the closest approved composition for the task; recheck affected paths.
2. **Define:** record the task, domain meaning, approved pattern or exact proposal
   approval, shared components, and states needed to understand the change. Keep
   ordinary and relevant incomplete/exception scenarios separate.
3. **Implement:** compose the existing library and tokens. Application policy and
   data ownership stay in the application. Reuse existing authorization for
   ordinary repairs; new concepts follow the project's actual approval rules.
   Maintain affected catalogue and guide inputs in the same change, following
   [the upkeep rules below](#maintain-the-design-system-with-the-change).
4. **Verify:** run native behavior/style/accessibility checks required by the
   project; capture current-run images at configured viewports. Review intentional
   visual changes before updating baselines, then replay with updates disabled.
5. **Challenge:** for material rendered review, delegate a fresh-context reviewer
   the generated instructions and evidence. Grant read-only access to the packet
   and its exact referenced project contract files: the helper hashes those
   contracts but does not copy them into the packet. Preserve the first-look
   order; permission to read contracts does not mean reading them before the
   unaided notes. Preserve actual responses. Start with unaided interpretation
   before the brief or later disclosure supplies context.
   Adjudicate disagreements using the product contract and native evidence; do
   not automatically accept every model finding or treat silence as proof.
6. **Gate:** run the installed native UI handoff command on that exact source,
   packet, actual native receipts and independent review before claiming verified
   completion. After a relevant change, recapture and rerun affected checks and
   review in a new evidence set; an old passing result does not cover new work.
   Apply the same gate before presenting a material rendered proposal or
   prototype, not just before handing off implemented code.

One bounded review is normally enough for a small repair. A clean result may
justify no application changes. Mechanical edits keep focused verification;
backend-only changes do not acquire this workflow. If independent review cannot
run, say so; self-review is not an independent pass. Preserve unresolved issues
and the project's handoff gate even when a reviewer reports no findings.

## Maintain the design system with the change

The agent changing a shared control, approved composition or usage rule owns its
affected documentation and examples before handoff. Read the project's adapter
to locate those inputs; do not assume another project uses the same files or
generator.

- Update approved rules, when-to-use guidance, inventory entries, examples and
  required states when the change affects them. Remove or migrate obsolete
  references when a control is renamed or removed. Check prose against current
  behavior even when its links and types still pass.
- Edit the authoritative inputs. When the project generates a guide, regenerate
  it through the project command. Do not hand-edit generated JSON or copy a
  second set of APIs, tokens or rules into the guide. Record an approved design correction in the
  canonical rules; do not turn a local exception into a universal rule.
- When a guide exists, query the affected entry after updating its inputs.
  Inspect the matching rendered example when appearance or behavior changed, and run the relevant
  native checks. Missing-reference checks cannot prove that guidance is true;
  the required rendered review still applies to material changes.

Reuse that leaves the component contract and guidance unchanged needs no guide
edit. Mechanical copy fixes keep focused checks; backend-only work does not
trigger catalogue maintenance. Preserve synthetic-only and approval rules from
the project. In the handoff, identify the affected inputs and checks, or briefly
state why no design-system update was needed. Keep publication and plugin release
separate from local implementation.

## Package review evidence

The brief is JSON with `id`, `task`, `meaning`, `scope` (`review`,
`approved-pattern` or `new-concept`), `patternBasis`, `requiredStates`,
`components`, `checks`, and `images`. Each check contains `command` and
`evidence` (a native log path); each image contains `id`, `role` (`screen` or
`reference`), `state`, `viewport` and `path`. Paths are relative to the brief
or absolute. Every required state needs a screen at every configured viewport,
plus at least one approved reference. Required states are task-specific, not a
fixed checklist of every possible state. Use synthetic or permitted sanitized
evidence; keep raw packets and reviewer output outside public source control.

```sh
python3 /path/to/poteto-mode/scripts/design_evidence.py --repo /project \
  prepare --brief /local/task.json --out /local/new-packet
python3 /path/to/poteto-mode/scripts/design_evidence.py --repo /project \
  check --packet /local/new-packet --review /local/new-packet/review.json
```

`prepare` copies images/logs and records configured source hashes. `check` rejects
missing/duplicate image or criterion coverage, unknown evidence, inconsistent
findings, modified evidence and changed source. It returns `CHANGES_REQUESTED`
or `INCOMPLETE` with nonzero status for reported problems/questions.
`REVIEW_COMPLETE` only means a complete response reports no open issues on the
unchanged packet. None of these statuses proves reviewer independence, image
provenance, native test success or human approval. The hashes detect accidental
drift; they are not signatures. Never fabricate a response or edit a negative
review into a pass. Keep reviewer identity/session and native receipts alongside
the packet. Recapture and use a new packet after changes.

## Execute and check the handoff

After inspecting the approved profile commands, run them through the helper to
preserve native execution receipts, then prepare and review the packet:

```sh
python3 /path/to/poteto-mode/scripts/design_evidence.py --repo /project \
  run-checks --out /local/new-check-run
# Capture actual required states, prepare a new packet, and obtain fresh review.
python3 /path/to/poteto-mode/scripts/design_evidence.py --repo /project \
  handoff --packet /local/new-packet --review /local/new-packet/review.json \
  --checks /local/new-check-run --review-record /local/reviewer-record.json
```

Run `run-checks` before `prepare`. Each brief check must reference the exact
resulting `native-N.log` from that checks directory as its `evidence`, and its
`command` must be the exact Python `shlex.join(argv)` encoding of the corresponding
profile command argv. Do not substitute a descriptive command label or unrelated
log. The handoff compares these command strings and native log hashes with the
packet's check evidence.

`run-checks` executes profile check argv without a shell and records exit status,
stdout/stderr and source identity before/after. A failed check or source drift
fails the run. Use actual resulting logs in the brief, not authored success text.
`handoff` combines response validation with current source/Git identity, command
coverage, successful native receipts and their log hashes, plus a reviewer record
bound to the exact packet and response. Preserve actual reviewer session evidence,
first-look notes and transcript from the fresh reviewer execution. Never invent
session IDs, notes or transcripts to satisfy a schema, or relabel self-review as
independent. Session differences and matching hashes establish recorded linkage,
not authenticated independence, real pixels, truthful logs or design quality.
Missing reviewer access is a reported blocker, not a fabricated pass.

Non-Git scratch proposals use exact configured source hashes and the returned
`sourceFingerprint`, with `gitHead: null`; Git-backed work also binds the current
HEAD. Track the proposal's actual HTML, assets, configuration and other rendering
inputs in its profile. A scratch location does not exempt a material proposal
from review, and hashes cannot establish freshness for omitted inputs.

`--checks` names the directory containing the generated `receipt.json`. The
reviewer record has these exact fields; compute hashes from the retained actual
artifacts and use the packet's fingerprint, not the illustrative placeholders:

```json
{
  "packetFingerprint": "<packet fingerprint>",
  "reviewSha256": "<SHA-256 of actual review response bytes>",
  "authorSession": "<actual implementation session>",
  "reviewerSession": "<actual fresh reviewer session>",
  "firstLookNotes": {"path": "first-look.txt", "sha256": "<SHA-256>"},
  "transcript": {"path": "reviewer-transcript.jsonl", "sha256": "<SHA-256>"}
}
```

Evidence paths are relative to and contained within the record's directory.
Inspect the actual reviewer execution/tool results before constructing this
record. Distinct session labels alone prove nothing about who inspected what.
`HANDOFF_EVIDENCE_COMPLETE` means the linked evidence passes these consistency
checks, not an independently authenticated or certified UX verdict.

The native wrapper must propagate nonzero status. Do not hide a failure with an
unconditional successful exit, stale fallback, or a changed criterion. Changes
to accepted policy need the project's approval; repair and rereview under the
existing authorization when within scope. A passing local gate does not grant
publication, deployment, financial writes or release authority.

## Evaluation boundary

Automation can be tested deterministically: missing viewport, changed source,
changed image, duplicate observation, invalid reference and idempotent setup.
Better LLM judgment needs separate observed comparisons on the same evidence.
Before such a comparison, isolate the guidance each reviewer may access;
ambient project instructions can contaminate a purported baseline. Record
false positives, missed defects and disagreements. Do not claim one-shot design,
cross-project quality, or a behavioral improvement from structural checks.
