# Pstack for Codex 0.8.0: shipping preparation

This is a reviewed source candidate, not yet a certified or published release. The
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

Before the release-policy revision, `make verify` passed all 319 tests, package
validation, and fixture/release configuration checks. Remote verification of
`740f3054bd28546e2f904f74ca15b5e4fc58b3d9` passed all four jobs. Those results precede
the new controller implementation. The completed revised local gate passed all
340 tests in 385.6 seconds, plus package, fixture and release-policy validation;
actionlint also passed. Independent non-author review returned `PASS+NOTES` after
46 focused evidence, protection, installation and real-Git checks, with no
unresolved implementation finding. These local checks do not prove a live
GitHub attestation or promotion.

The pinned CLI's local fake-API transport check passed; it made no provider calls.
Workflow lint passed with actionlint `1.7.12`. The downloaded binary matched its
official release SHA256.

Final deterministic and observed workflow results are recorded in
[the final port observations](../evals/pstack/port-0.8.0-observations.md).
Raw requests, replies, traces, fixtures, and review records remain outside Git.

The first public candidate, `833dd2d919f7a7e72c6c334673f5bd2a4833bbd7`,
is recorded in [PR #37](https://github.com/cyyapye/tugling/pull/37). A fresh
credential-free installation of that exact revision passed with the frozen
package hash above. Remote runtime, isolation, and synthetic installation checks
also passed. Remote `make verify` exposed one stale baseline test: it assumed
every archived commit contained the removed `tugling` skill. Before committing
the port, that test had inspected the older `HEAD`, masking its stale assumption.
The failure was reproduced locally and the assertion was replaced with a
comparison of every materialized skill name and byte content against the
requested Git revision. Plugin bytes are unchanged. The PR records verification
of the updated candidate; the original failed run remains visible.

## Reviewed release policy

The maintainer approved replacing the legacy questionnaire and per-skill catalog
gate with Pstack's observed-workflow approach. Its ten-case inventory covers four
of the 54 current skills; extending it to every entry point did not establish an
advantage over reviewing representative delivered work. That inventory remains
useful diagnostic data, not the new release acceptance rule.

The [0.8.0 review report](../evals/releases/v0.8.0/pstack-review.json) preserves
15 attempts across 14 distinct tasks: 14 passed, and the original failed authoring
attempt remains recorded alongside its separately authorized environment repeat.
It covers eight workflow areas and binds the frozen plugin above. It discloses
same-family review, development tasks rather than holdouts, builder-only usage,
and incomplete catalog behavior coverage. It makes no enhancement claim.

The new controller validates the exact maintainer-approved report, source
attribution, package bytes and executable modes, successful exact-main CI, and a
fresh credential-free public installation. Certification makes no model calls.
Independent controller pins, signed artifacts, the protected human approval,
atomic stable/tag publication and the installation canary remain required.

All arms of the retained legacy comparison receive the same invocation instruction:
use the current skill if present, otherwise its recorded legacy name, otherwise
complete the task without it. This preserves useful diagnostic failure cases; it
does not turn the questionnaire into a blinded Pstack evaluation.

## Remaining release requirements

1. **Final remote verification:** require successful checks for the revised
   machinery's published commit. Local verification and independent review passed;
   source-policy approval does not approve an exact controller pin.
2. **Exact public candidate:** publish the final reviewed source, require successful
   remote checks, and verify a fresh public installation of that exact revision.
3. **Independent activation:** approve the final merged controller commit, create
   its protected controller tag, update both controller pins, accept the exact
   report digest and explicitly enable reviewed certification. The candidate
   cannot approve its own pins. Follow [controller review](release-controller.md).
4. **Certification and promotion:** run exact-candidate certification, review its
   signed evidence, then approve the protected `tugling-stable` environment and
   require the stable-alias installation canary to succeed.

The policy revision itself changes no controller pin, certification setting,
stable ref, version tag, installed user plugin, or release environment.
