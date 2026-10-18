# Pstack port test audit

The test suite should protect shipped behavior and the integrity of its evidence.
It should not require a new Tugling vocabulary or reward resemblance to a prompt.

| Tests or checks | Decision | Reason |
| --- | --- | --- |
| 205 declarative routing cards and their positive/negative/holdout quotas | Remove | These came from the retired seven-entry-point design, followed by generated cards for all 54 names. Most Pstack skills require explicit invocation. Checking card shape, repeated explicit prompts, and generic negative prompts does not observe routing. The known cards were not unseen holdouts. |
| Minimum 40-character description heuristic | Remove | Length cannot establish a useful trigger. Keep the supported name, nonempty description, and maximum-length constraints. |
| Single-adopter name blacklist | Remove | One historical project name is not a portable data-boundary check. Keep the separate privacy scanner, configured release-policy scan, and their executable tests. |
| Enforcement prompt phrase blacklist test | Remove | Repeating case constants and forbidding a few words cannot establish scope adherence or prevent answer leakage. Review prompts separately from the independent mutation oracle. |
| Packaging, source hashes, full license, catalog, and relative links | Keep | These protect the attributed upstream port and a complete installation. |
| Ten existing behavioral fixtures | Keep as regression diagnostics | Migration, scale, retries, repository truth, bounded completion, authoring, UI, and optional adoption still have corresponding shipped workflows. Historical case IDs preserve evidence continuity; they are not public skill names. Their multiple-choice scores do not establish a faithful Pstack experience or an advantage over Pstack. |
| Project contract, verification, retention, learning, setup, enforcement, and UX tests | Keep | They exercise executable helpers and dormant references retained for existing integrations or explicit comparisons. Removing their public entry points did not remove that code. These checks do not justify making an extension the default. |
| Process cleanup, usage accounting, evaluator, release, and controller tests | Keep | They prevent misleading evidence, leaked processes, unbounded work, and unauthorized publication. They remain relevant regardless of skill vocabulary. |
| Pending catalog coverage | Keep as an explicit release blocker | A structural port is not observed behavior. Representative smoke runs do not waive untested entry points or silently change the approved release matrix. |
| Questionnaire as the normal development quality gate | Retire | Use Pstack's organic-task, hidden-rubric and blinded-review method. Keep legacy assertions only for supported diagnostics and the controlled release matrix. |
| Explicit invocation across renamed release catalogs | Correct | All arms receive the same prompt: use the current entry point when installed, otherwise its explicit legacy alias, otherwise work without the skill. Requesting only the new name had bypassed the released seven-name catalog. Reconstructed install tests protect the mapping; they do not prove model routing. Case IDs, verdict criteria and promotion thresholds are unchanged. |
| Regression check based only on a changed test file | Strengthen | Execute the delivered regression against the original implementation; a comment-only test change cannot pass. |
| Matched package, record integrity and observer separation checks | Add | Protect equal starting inputs and budgets, retain failed outcomes, detect altered deliveries, and keep model/condition metadata out of the blinded review bundle. These checks do not grade skill quality. |
| All other addition failure cases after retiring automatic loading | Keep | Migration, lease/retry recovery, scale limits, UI diagnosis, skill overtriggering, setup lifecycle and correction privacy remain useful inputs. The [assessment](pstack/additions-assessment.md) records their upstream owners and gaps; historical questionnaires are not fresh holdouts. |
| Verification failure cases after retiring the extra guidance's automatic loading | Keep | Ignored commit inputs, green-but-incomplete checks, ineffective regressions and bounded completion still test useful Pstack outcomes. Keep their fixtures and history; they do not require the Tugling extension to be active. |

The [observed check](pstack/observations.md) exercises the familiar Pstack experience through a fresh local
marketplace installation and actual Codex tasks. It observes skill/playbook
loading, usable outputs, native verification, plan-only scope, and unavailable
capability handling. It is a local compatibility diagnostic, not certification,
public installation evidence, a Pstack comparison, or proof of all 54 skills.

Changes here modify controller-owned files. They do not update approved controller
pins. The release matrix, thresholds, and publication authority remain separate.

The [Pstack evaluation method](pstack/method.md) is now the development path.
The local adapter adds private package profiles and blinded review bundles around
the existing runner. Upstream helper unit tests remain bundled; they are reused
if those helpers become active Codex runtime features, not rewritten in Python.
