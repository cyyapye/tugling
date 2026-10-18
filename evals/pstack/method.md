# Pstack evaluation on Codex

Use Lauren Tan's [Pstack Eval playbook](../../plugins/tugling/skills/poteto-mode/playbooks/eval.md)
as the development method. It is copied from [the pinned upstream source](https://github.com/cursor/plugins/blob/101b274dd991f694e1f7024be2157e5f3adf07de/pstack/skills/poteto-mode/playbooks/eval.md)
under its [MIT license](../../plugins/tugling/skills/poteto-mode/references/upstream/LICENSE).
This page supplies Codex execution details, not a competing playbook.

The [first method pilot](method-observations.md) exercised both packages, blinded
review and trace audit. It found a tie on two known tasks and incomplete extension
consumption on the direct verification task; it makes no enhancement claim.

Every workflow now uses Pstack by default. The [addition assessment](additions-assessment.md)
records all remaining candidates, their upstream overlap and evidence gaps.
Optional references are unlinked from normal instructions and retained for
explicit comparisons or existing adopter contracts. The [verification cases](verification-cases.md)
and other retained fixtures preserve useful failures without loading extra guidance.
Run Pstack first. An unresolved baseline failure can justify a matched addition
trial; a task Pstack already solves does not justify more default instructions.

## Frame and freeze

Write three to six concrete success criteria before running. Keep them outside
the builder's workspace and prompt. Give the builder an ordinary user request
and the project inputs a real task would supply. Do not ask it to name the
principles it used, select expected decisions, or grade its own work.

For an enhancement, compare a faithful Pstack port on Codex with the same port
plus that one addition. Keep project inputs, prompt, model, reasoning effort,
tools, deadline and usage admission limits equal. Using the same model isolates
the instruction change; Pstack's separate model-comparison mode can vary models.
Freeze package hashes and inspect their actual diff before admitting calls.
No-skill comparisons and the old decision questionnaire cannot establish an
advantage over Pstack.

The existing runner accepts `--package-root` and `--cases-file`. Its seven
bundled tasks use the greeting CLI and are known development cases, not unseen
holdouts. An external cases file uses the same fixture and outcome checks; a new
project surface needs its own real inputs and independent execution oracle.
Do not relabel a known case as a holdout. Before retaining an enhancement on a
quality claim, obtain fresh tasks authored without seeing the addition, include
an irrelevant task to detect unnecessary work, and repeat matched attempts.

The private profile tool removes optional guidance from both packages, then
adds only the selected extension, its reference dependencies, and a conditional
adapter link to one. Both preserve the upstream catalog, playbooks, full license,
and Codex scope/tool/model translations. Neither changes the shipped plugin.
Inspect `profiles.json` and the directory diff; the tool's hash checks do not
establish that this is the right experiment.

```sh
python3 scripts/pstack_profiles.py --extension repo-verify --out /private/work/packages
diff -ru /private/work/packages/pstack /private/work/packages/enhanced

python3 scripts/pstack_smoke.py --package-root /private/work/packages/pstack \
  --case verification --case bug-fix --model <session-model> \
  --reasoning-effort <session-effort> --out /private/work/first
python3 scripts/pstack_smoke.py --package-root /private/work/packages/enhanced \
  --case verification --case bug-fix --model <session-model> \
  --reasoning-effort <session-effort> --out /private/work/second
```

Alternate arm order across repeated attempts. Preserve every failure, timeout,
and original grade; repair into a new run rather than replacing an unfavorable
attempt. The bounded local development run uses the user's existing model
allowance. The separate release certification authority is unchanged.

## Run and observe

Each task gets a fresh native plugin installation and a neutral project path.
Rubrics, package-condition keys, other outputs, and observer scripts are not
supplied to the builder. The execution environment omits our old evaluation
marker. Ordinary project `tests/` files and upstream skill names are preserved;
sanitization removes experiment labels, not real project vocabulary. This is a
documented adaptation of upstream's literal naming rule.

Codex's workspace-write sandbox is not a read-isolation boundary. Withholding
observer paths does not prove they were inaccessible. Inspect the trace for
unexpected observer reads or identity leakage and invalidate blinding when
found. The agent is instructed to stay within its project and installed skills.

The runner records actual commands, output, elapsed time, usage and resulting
files. The CLI oracle checks multi-word and Unicode names independently of the
delivered tests. A regression must also reject the original implementation.
Read-only tasks must leave even ignored files unchanged. Settings, installed
package bytes and Git HEAD must remain unchanged. These checks supplement
semantic review; a passing Boolean does not prove a playbook was followed.

## Blind review, then reconcile

```sh
python3 scripts/pstack_review.py --run /private/work/first --run /private/work/second \
  --out /private/work/review --key-out /private/work/identity.json
```

The bundler rejects mismatched tasks, runtime, deadlines, usage limits or initial
project files, incomplete runs, and changed retained deliveries. It randomly
labels the packages, strips local paths and model labels, and supplies task,
reply, resulting source and independent checks. Failed checks stay visible.
The condition key, costs and raw skill-read traces remain outside the bundle.
Hash manifests detect accidental drift, not maliciously rewritten evidence.

Give one fresh reviewer only the bundle. It assesses every criterion on both
labels in one pass, with concrete evidence. Prefer a different model family per
Pstack. If unavailable, record same-family review explicitly; never claim
cross-family independence. An attestation cannot prove a reviewer was blind.
The parent independently reads every output and reconciles disagreements before
opening the key. Preserve the bundle's hashes alongside the completed review.

Separately audit raw transcripts: successful skill/adapter/playbook reads,
reproduction and verification order, mutations, extra user interventions, scope,
and unavailable-capability claims. A failed read or the model saying it followed
a skill does not prove that it did. The blind judge should mark trace-only
criteria unverified; the parent's trace audit supplies that distinct evidence.

After revealing the key, report correctness, regressions, user interventions,
latency and token cost alongside the judge and parent assessments. A tie provides
no demonstrated reason to add guidance. A narrow win is a development signal;
confirmation still requires fresh tasks and repeated runs. Do not promote an
extension on extra prose or on a saturated task where Pstack already succeeds.

## Deterministic and release boundaries

`make verify` remains model-free. Its relevant checks cover packaging, provenance,
links, helper behavior, observer isolation, immutable records and matched inputs.
Upstream Bun/TypeScript tests stay bundled with the upstream helper code. The
Codex adapter currently uses native tools instead; if a helper becomes a runnable
feature, reuse its upstream test command rather than recreating the tests.

The [legacy questionnaire](../behavioral/README.md) remains only for historical
diagnostics. The [release policy](release-policy.json) uses reviewed workflow
evidence with preserved failures and explicit limits. New development
uses this method. Neither a local comparison nor a changed evaluator updates
controller pins, certifies the catalog, or authorizes publication.
