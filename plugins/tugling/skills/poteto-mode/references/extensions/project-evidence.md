# Project UI evidence

Use for requested repeatable UI setup or material work in an already configured
project. Keep the project's product rules, approval boundary and native gates
authoritative. This helper packages evidence; it does not execute commands,
render a browser, evaluate accessibility, call an LLM or certify design quality.

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

## Use for a delivery

1. **Discover:** inspect the adapter, relevant sources and current render. Select
   the closest approved composition for the task; recheck affected paths.
2. **Define:** record the task, domain meaning, approved pattern or exact proposal
   approval, shared components, and states needed to understand the change. Keep
   ordinary and relevant incomplete/exception scenarios separate.
3. **Implement:** compose the existing library and tokens. Application policy and
   data ownership stay in the application. Reuse existing authorization for
   ordinary repairs; new concepts follow the project's actual approval rules.
4. **Verify:** run native behavior/style/accessibility checks required by the
   project; capture current-run images at configured viewports. Review intentional
   visual changes before updating baselines, then replay with updates disabled.
5. **Challenge:** for material rendered review, delegate a fresh-context reviewer
   the generated instructions and evidence. Preserve actual responses. Start with
   unaided interpretation before the brief or later disclosure supplies context.
   Adjudicate disagreements using the product contract and native evidence; do
   not automatically accept every model finding or treat silence as proof.

One bounded review is normally enough for a small repair. A clean result may
justify no application changes. Mechanical edits keep focused verification;
backend-only changes do not acquire this workflow. If independent review cannot
run, say so; self-review is not an independent pass. Preserve unresolved issues
and the project's handoff gate even when a reviewer reports no findings.

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

## Evaluation boundary

Automation can be tested deterministically: missing viewport, changed source,
changed image, duplicate observation, invalid reference and idempotent setup.
Better LLM judgment needs separate observed comparisons on the same evidence.
Before such a comparison, isolate the guidance each reviewer may access;
ambient project instructions can contaminate a purported baseline. Record
false positives, missed defects and disagreements. Do not claim one-shot design,
cross-project quality, or a behavioral improvement from structural checks.
