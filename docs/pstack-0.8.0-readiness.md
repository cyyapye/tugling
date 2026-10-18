# Pstack for Codex 0.8.0: shipping preparation

This is a local release candidate, not a certified or published release. The
port preserves Pstack's 54 entry points, 24 principles, and 23 playbooks. Optional
Tugling guidance remains dormant; no enhancement claim is made.

## Identity and source review

- Prepared plugin version: `0.8.0`.
- Pstack source: Lauren Tan's `cursor/plugins` revision
  `101b274dd991f694e1f7024be2157e5f3adf07de`.
- Frozen plugin SHA256: `3b6d4e9d8941d14861129d1b4d10baa5104a61ce1dd2477943070d818e5e64e4`.
- All 135 attributed upstream files and all 54 entry points passed source and
  inventory validation. The full upstream MIT license and executable modes are
  retained. The manifest records every adaptation.

Independent source review found and resolved changes beyond a faithful port:
Pstack's workflow triggers and fresh-worker scope are restored. Codex translations
now cover skill metadata, implementation versus reviewer roles, task-local
orchestration state, and native worktree activity/archive handling. Missing chat
activity is unknown, never deletion permission. Scope and model inheritance
continue to follow the current Codex session.

## Verification evidence

All 54 skills pass the skill-authoring validator. Both Codex CLI `0.153.4`
(the release runtime) and `0.163.0-alpha.10.2` (the local desktop runtime) installed
identical package bytes in fresh credential-free homes and exposed all 54 enabled
skills, with populated metadata and no errors, through native `skills/list`.
This establishes native discovery, not every skill's behavioral reliability or
the desktop command picker's visual behavior.

The initial discovery assertion expected unqualified skill names. The actual
API correctly returned `tugling:<name>`. That failed assertion is retained;
a corrected check passed against both runtimes without changing the plugin.

`make verify` passed all 319 tests, package validation, and fixture/release
configuration checks. It also reported the expected full-catalog certification
blocker; successful local validation does not waive it.

The pinned CLI's local fake-API transport check passed; it made no provider calls.
Workflow lint passed with actionlint `1.7.12`. The downloaded binary matched its
official release SHA256.

Final deterministic and observed workflow results are recorded in
[the final port observations](../evals/pstack/port-0.8.0-observations.md).
Raw requests, replies, traces, fixtures, and review records remain outside Git.

## Release machinery corrections

Full certification now rejects incomplete catalog coverage before admitting
model work, including direct entry into the certification runner. Existing
unchanged-package checks and explicit one-case diagnostics remain available.
Final proof, certificate, and promotion coverage checks remain in force.

All arms of the legacy comparison now receive the same invocation instruction:
use the current skill if present, otherwise its recorded legacy name, otherwise
complete the task without it. This restores the released seven-skill package's
participation without changing any case decision criterion or threshold. It
does not turn the questionnaire into a blinded Pstack evaluation.

## Remaining release requirements

1. **Controlled behavioral coverage:** the legacy matrix covers 4 of 54 installed
   skills. Its 50 pending entries describe missing release-matrix cases, not an
   absence of all development observations. Native discovery and representative
   live tasks do not waive this gate. Complete the controlled coverage before
   full certification. Replacing that policy with a Pstack-based release gate
   would be a separate, explicit controller decision, not a passing result here.
2. **Independent controller approval:** evaluator, test, and release-preflight
   changes are controller-owned. The candidate cannot approve its own pins.
   Follow [controller review](release-controller.md) after the final commit and
   remote checks are available.
3. **Exact public candidate:** commit and publish the reviewed candidate, obtain
   successful remote checks, and verify a fresh install of that exact public
   revision. A local marketplace install is different evidence.
4. **Certification and promotion authority:** the repository's certification
   setting was disabled when checked on 2026-10-17. Paid certification needs an
   exact candidate, baseline, reviewed controller, and explicitly approved usage
   thresholds. Promotion then requires the maintainer's environment approval
   and a successful stable-alias installation canary.

No controller pin, certification setting, stable ref, version tag, installed
user plugin, or release environment has been changed by this preparation.
