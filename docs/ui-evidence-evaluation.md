# UI evidence setup candidate

This 0.9.0 release candidate extends the optional project-setup and screenshot-diagnosis
references. It does not add a default skill entry point or activate release-controller
changes. The stable baseline remains 0.8.0 until separate certification and promotion. It claims deterministic evidence handling,
not better design judgment or one-shot delivery.

## Cases fixed for evaluation

| Case | Observable requirement |
| --- | --- |
| Set up an existing UI project | Read its actual theme/library/contracts; write only its reviewed profile; do not install a new component library or global plugin. |
| Repeat setup after user edits | Preserve existing configuration and identify differences; no silent overwrite. |
| Review a material UI change | Current required states and configured viewports, approved reference, native logs and actual independent response are available. |
| Workstation-only project | Honor its configured viewport; do not invent a mobile requirement. |
| New source or changed font asset after review | Reject the stale packet even when the reviewed images themselves are unchanged. |
| Missing or duplicate observation | Reject incomplete/ambiguous evidence accounting. |
| Punctuation correction | Use focused project checks; no mandatory new review packet or app-wide startup. |
| Backend-only task | Skip UI setup/review and preserve backend verification. |
| New UI concept | Preserve the project's actual concept-approval boundary; a model result is not approval. |

## Guide maintenance cases

The upkeep rule adapts Pstack's existing
[verification-skill maintenance](../plugins/tugling/skills/maintain-verification-skill/SKILL.md)
distinction between stale documentation and product regressions. It applies to
affected UI inputs during delivery; it does not introduce a recurring audit or
another default skill.

| Case | Observable requirement |
| --- | --- |
| Rename a shared document-picker control | Migrate its public API, catalogue inventory and example references; query the resulting guide and verify the changed control. Do not patch generated JSON. |
| Correct guidance that says a failed save clears a form, while the approved implementation retains the draft | Update the canonical rule and authored usage guidance even though links and types pass; keep the correct product behavior and its failure-state example. |
| Use an unchanged existing button on another page | Reuse its guide and contract; leave unaffected guide inputs alone and keep checks proportionate. |
| Repair a backend queue retry | Preserve backend verification; do not start catalogue maintenance. |
| Update a project with handwritten examples and no generator | Maintain the relevant examples and rules through its existing workflow; do not impose the sample guide commands or create a generator. |

These are reviewable routing and completion cases, not observed model outcomes.
Native helper tests cover optional guide metadata, rejection of malformed
commands, no implicit command execution, and review invalidation after authored
guidance changes. They do not prove that an agent notices misleading prose. No
new model comparison has been run for this narrow maintenance amendment; any
claim of behavioral improvement or release readiness still needs the existing
evaluation and release gates.

The helper's native unit tests use synthetic files and one-pixel images. They
prove automation contracts, not rendering, accessibility, review independence or
test success. Run `make verify` for the repository's full local gate.

## Observed development boundary

An adopter trial exposed a review disagreement over failure-state hierarchy.
The candidate reviewer accepted the existing screen; another reviewer proposed
a useful improvement. Ambient instructions also contaminated the nominal
baseline, so the run cannot rank judgment quality. Preserve that limitation;
do not tune a general rule to demand that every failure use a particular phrase.

The adopter's old packet was rejected after its source changed. That is a
separate, deterministic result supporting portable evidence handling. Record
actual end-to-end helper runs and independent forward-testing outside the
public repository. A different viewport in a synthetic fixture is not a real
external-project design pilot.

Before a behavior or release-quality claim, perform the existing consequential
instruction and release evaluation gates with isolated guidance and the exact
candidate revision. Local helper validation does not activate controller pins,
install a plugin, authorize publication or certify an entire product workflow.

## Earlier Pstack-base candidate checks

On the current Pstack base, package/source validation, all 357 local tests,
behavioral/UX suite structure and clean-package validation passed. The complete
`make verify` command remained nonzero at release validation: the existing
review binds the released plugin bytes, which this candidate changes. The old
review was preserved; its identity was not rewritten to claim coverage of new
content. Fresh exact-package observations and the repository's release review
remain outstanding. These results qualify a local candidate for further work,
not a release-ready package.

Independent forward-testing found that a generated first-look mapping could be
modified without rejection. The helper now derives and validates all reviewer
inputs from the packet; synthetic tamper and restoration cases cover that
repair. The adopter's matching local helper was repaired too. This supports an
evidence-integrity claim, not an improvement in the LLM's visual judgment.

## Maintenance amendment checks

Package/source validation, all 360 native tests, behavioral/UX case validation
and clean-package validation passed after adding optional agent-guide metadata
and the upkeep rule. The adopter's existing guide tests and skill structure
checks also passed. Its adapter was accepted by the shared helper, with the
authored guidance, inventory, examples, rules and generator included in source
tracking.

At that stage, `make verify` ended nonzero at release validation: the prior reviewed
package does not match this candidate's plugin content. That report and the
controller pins remain unchanged. No new model comparison, plugin installation,
publication or release certification was performed for this amendment.

## Verification setup trial

A disposable external-project trial exercised the existing Tailwind v4 theme and
workspace component library without installing Tugling globally. Profile setup
created the adapter, repeated without a change, and rejected a conflicting
profile without overwriting it.

The adopter's normal ESLint command used official `@shadcn/lint` 0.2.3 on one
explicitly scoped reference route. A shared-button padding/color/shape probe
failed with five errors across `no-restyle`, `no-arbitrary-values` and
`no-raw-colors`. A correction using component variants and permitted layout
classes passed. This is a scoped enforcement proof, not an app-wide rollout.

A fresh-context reviewer inspected actual desktop/mobile captures without the
hidden scorecard and found both seeded defects: contradictory save-success copy
and disabled recovery. Its original response contained unsupported JSON fields;
the helper rejected it. The same reviewer corrected the schema without changing
its findings, and the helper returned `CHANGES_REQUESTED`. After repairs, actual
lint, 194 unit tests, types, build, two browser scenarios and an additional
Tab/Space/Enter navigation probe passed. A second fresh-context reviewer found
no actionable defects on the repaired evidence; the helper returned
`REVIEW_COMPLETE`. Both first-look records and actual responses were retained.

The second packet's references match its unchanged initial state; they are not
an independent historical-design benchmark. Screen-reader audio and broad
accessibility certification were outside this bounded trial. Detection of two
known defects demonstrates execution and a capability, not general accuracy,
a measured advantage over the released skill, or one-shot delivery.

Native checks also exposed a profile-freezing bug: external documentation links
were treated as local files. The dependency walker now leaves external URLs as
references. The full native run had 359 passing cases and this one error; the
unchanged regression case passed after the repair. Package/source, behavioral
suite structure, UX suite structure and clean-package checks passed. Release
validation remains blocked because the existing review binds different plugin
bytes. Its reviewed report and controller pins were preserved. No release or
publication is claimed by this trial.

## 0.9.0 release preparation

The [exact-package release report](../evals/releases/v0.9.0/README.md) now records
fresh compatibility observations, independent output review and parent trace
reconciliation. The final native gate passed 360 tests; release validation also
accepts the new report against the frozen package. The earlier results above
remain historical evidence, including failures and limitations. These new
compatibility observations do not establish a UI-judgment advantage or turn the
maintenance cases into a measured behavioral comparison. Controller approval,
release certification and stable promotion remain separate.
