# Pstack method pilot, 2026-10-17

The [Pstack evaluation method](method.md) was exercised end to end on two known
development tasks, with one attempt per package per task. Both packages passed
the independent artifact checks, blinded output review, and the parent's separate
trace audit. No outcome advantage was observed for the added guidance.

## Comparison and identity

The baseline was the faithful Codex port with optional Tugling guidance removed.
The other package added the repository-verification extension, its referenced
dependencies, and one conditional adapter link. This is an isolated extension
profile, not the entire shipped candidate or a release comparison. The profile
uses adapter routing; it does not restore every extra entry-point link from the
full candidate. Both packages retained all 54 entry points, the same upstream
playbooks and Codex mechanics, and the original license.

- Pstack source revision: `101b274dd991f694e1f7024be2157e5f3adf07de`.
- Baseline package SHA256: `0f9099f685f74a01a3297076c6a82e7d1145aee7dcb3b9a34a5bf95806a92830`.
- Extension package SHA256: `be0d573a890c0ef6a26f8d22049e7ded0d8573d3972a26ba28cb171847c5a7f8`.
- Runner SHA256: `cac67a34722f707118468f12d8b190e189c89244cd25a5f433501bb98d2b3394`.
- Runtime: Codex CLI `0.163.0-alpha.10.2`, `gpt-6-astra`, effort `xhigh`.
- Per-package admission limits: two calls, 500,000 input and 20,000 output tokens,
  four minutes per call. These are between-call usage limits, not hard billing caps.

## Observed outcomes

| Task | Pstack on Codex | With verification addition |
| --- | --- | --- |
| Repair full-name truncation | Reproduced the CLI defect, added failing regressions, made the one-line repair, verified CLI and native gate | Same substantive result |
| Assess documented CLI behavior without repair | Found the multi-word defect despite the green single-word unit test; left source unchanged and withheld readiness | Same substantive result |

The independent runner also checked Unicode and multi-word CLI inputs and ran
the delivered regressions against the original implementation. Both rejected
the original code. Package bytes, settings and Git HEAD remained unchanged.
Neither task needed another user intervention.

The fresh reviewer received randomly labeled outputs, source and independent
checks, with the identity key and raw traces withheld. It reported a tie: eight
criterion assessments passed and six required trace evidence. The parent read
both outputs independently before opening the key and agreed. The review input
hashes still matched afterward. This was same-model-family review; no
cross-family independence is claimed.

The subsequent trace audit confirmed actual full-body reads of the requested
Pstack skills, adapter and bug-fix playbook; CLI reproduction before edits; failing
regressions before the source fix; and successful verification afterward. The
six trace-only assessments passed on this separate evidence. No observer-file
read was observed in the completed command or file-change events inspected.

The addition itself was read during the bug-fix task. It was **not read during
the direct verification task**, despite the conditional adapter link. That task
does not measure the effect of consuming the extension's instructions. This is a
routing observation to investigate on fresh tasks, not evidence that the
extension's content is unnecessary in every repository.

## Cost and limits

| Package | Input tokens (cached subset) | Output tokens | Task seconds, bug fix / verification |
| --- | --- | --- | --- |
| Pstack on Codex | 308,606 (258,816) | 3,571 | 53.19 / 40.27 |
| With verification addition | 313,296 (234,240) | 3,485 | 89.87 / 41.47 |

These four builder calls consumed 621,902 input and 7,056 output tokens. The
separate review call is not included in those builder totals. One fixed-order
attempt per condition cannot establish a reliable cost or latency difference.

This pilot validates the local execution/review workflow and finds no benefit
on these already-solved tasks. The cases are simple, known, and not independent
holdouts; there is no evidence here of catalog-wide reliability or a material
Tugling advantage. No addition is promoted on this result. A confirmation study
needs relevant fresh tasks, the intended routing, repeated counterbalanced runs,
and explicit reporting of reviewer independence. Raw deliveries, traces, keys
and review records remain outside Git. This is not release certification.
