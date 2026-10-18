# Pstack for Codex 0.8.0 observations, 2026-10-17

The port passed source validation, native discovery, deterministic checks, and
representative local workflow review. Thirteen of fourteen distinct scenarios
completed in the original execution environment. Skill authoring initially
failed to deliver its files in a protected directory; a separately authorized,
narrow directory grant allowed a complete repeat. The original failure remains.
These observations do not certify the release or establish every skill's behavior.

## Frozen candidate and method

- Plugin version: `0.8.0`.
- Plugin SHA256: `3b6d4e9d8941d14861129d1b4d10baa5104a61ce1dd2477943070d818e5e64e4`.
- Upstream: Lauren Tan's Pstack, `cursor/plugins` revision
  `101b274dd991f694e1f7024be2157e5f3adf07de`, with full MIT attribution.
- Live runtime: Codex CLI `0.163.0-alpha.10.2`, `gpt-6-astra`, effort `xhigh`.
- Method: the attributed [Pstack Eval method](method.md), using free-form tasks,
  observer-only criteria, artifact checks, blinded output review, and parent
  command-trace reconciliation. No model self-score decides an outcome.

Every task used a fresh synthetic repository and native local plugin installation
in an isolated home. Only authentication was copied; personal settings and
personal skills were not. The installed package, settings, Git HEAD, and requested
source scope were checked. All attempts used the same frozen plugin bytes.

The seven [core requests](cases.json) were known development cases. A separate
author wrote seven [additional requests](codex-cases.json) and their criteria
without seeing previous cases, outputs, or addition results. They were frozen
before execution and are now known development cases. They use the same small
greeting fixture, so they are not broad project or production evidence.

## Source, installation, and deterministic checks

- Source inventory and attribution passed for all 135 upstream files, including
  the 54 skills, two role prompts, original license, and executable file modes.
  Independent source review was reconciled before freezing the candidate.
- All 54 skills passed the skill-authoring validator.
- Codex CLI `0.153.4` and `0.163.0-alpha.10.2` each installed identical package
  bytes in fresh credential-free homes. Native `skills/list` returned all 54
  enabled, plugin-qualified skills, populated metadata, and no errors.
- `make verify` passed 319 tests and the package, fixture, and release
  configuration checks. Its expected full-catalog certification blocker remains.
- The release CLI passed local fake-API HTTP 400/429 transport checks, without
  provider calls. Workflow lint passed with checksum-verified actionlint `1.7.12`.

The first native-discovery assertion expected unqualified names. The API returned
the correct `tugling:<name>` names. The failed assertion is retained; correcting
the expectation passed on both runtimes without a package change. This is native
API discovery evidence, not visual verification of the desktop command picker.

## Observed workflow outcomes

| Scenario | Reviewed outcome |
| --- | --- |
| Help | Familiar Pstack invocations and usable guidance; no invented persistent mode or settings change. |
| Natural setup discovery | Loaded `setup-pstack` from the request and retained inherited settings. |
| Plan only | Source-grounded phases; preserved explicitly requested current output while noting the documented discrepancy. No implementation or test run. |
| Bug fix | Reproduced the CLI defect, added failing regressions, repaired it, and passed the native gate and real CLI checks. The regressions reject the original source. |
| Direct verification | Distinguished a green unit gate from failing documented CLI behavior and withheld readiness. |
| Architecture fallback | Useful sequential analysis, with no claim of independent delegates, prototypes, or source edits. |
| Unavailable integration | Kept PR, review, and remote CI state unknown; created no watcher or service. |
| Resume work | Used local source and Git evidence, acknowledged unavailable conversation history, and avoided unrelated history access. |
| Compare test approaches | Compared function and subprocess verification with a concrete regression; disclosed sequential execution. |
| Cover CLI inputs | Exercised ten input cases, exposed full-name and blank-input failures, and preserved source. |
| Explain quoted names | Correctly separated shell quoting from the application's truncation defect, with proportional local inspection. |
| Wait for the next request | Returned exactly the requested sentence with zero commands or file changes. |
| Prepare a short session | Ran the real CLI and native gate, retained model/effort settings, and reported the documented defect without persistent setup. |
| Create a reusable verification skill | Original attempt repaired the app but did not deliver the skill, feature map, or saved workflow evidence. The authorized repeat delivered and executed all three. |

No optional Tugling extension or observer-material reads were found in the
reviewed traces. The fixture prohibits delegation, so arena/swarm/architecture
observations establish their sequential fallbacks, not real multi-agent work.

### Authoring failure and repeat

The original authoring response reported that automatic approval rejected writing
the protected `.agents` destination. The retained event log does not independently
expose that approval decision; missing skill, feature-map, and evidence files do
establish incomplete delivery. Passing application tests did not turn it into a
successful authoring task.

The repeat pre-created the exact requested synthetic skill directory and supplied
Codex's supported `--add-dir` option for that directory under the existing
workspace-write sandbox. The scoped grant was separately approved. The task,
criteria, package, model, and effort stayed the same; the environment and timeout
changed. This is a diagnostic repeat, not a matched quality comparison.

The repeat created a usable skill, feature index and document, executable
standard-library helper, and retained successful-run evidence. Command events
show the helper executing against the actual CLI and native gate, followed by
reading the saved evidence. Independent CLI checks included Unicode and repeated
spaces, and the new regression rejected the original implementation. The
generated helper itself does not include a Unicode case.

The builder disclosed that the bundled authoring validator could not import
PyYAML. It did not install a dependency. The parent subsequently ran that same
validator with an available temporary dependency environment and it passed.
Another scenario recovered from a failed shell read caused by zsh's reserved
`path` variable; the failed command remains recorded.

## Review and usage

Separate blinded output reviewers reported:

| Batch | Pass | Fail | Awaiting trace evidence |
| --- | ---: | ---: | ---: |
| Seven core tasks | 13 | 0 | 9 |
| Seven additional tasks | 24 | 3 | 8 |
| Authorized authoring repeat | 5 | 0 | 1 |

These counts are rubric criteria, not tasks. Parent review resolved the 18
trace-dependent criteria using actual reads, command order/results, retained
artifacts, runtime configuration, and tool-event inventories. The three original
authoring failures remain failures. Review inputs and retained delivery hashes
were checked after review. Reviewers were separate same-family agents, not
cross-model or human judges; blinding does not eliminate shared model bias.

The 15 completed builder attempts used 2,093,926 input tokens, including 1,751,424
cached tokens, and 38,482 output tokens. Author and reviewer usage is excluded.
The two seven-task batches each used a 240-second task deadline and admission
thresholds of 1.5 million input / 60,000 output tokens. The one-task authoring
repeat used 360 seconds and 400,000 input / 16,000 output thresholds. Thresholds
are checked between tasks, not hard per-request caps. These are observed costs,
not efficiency or comparative performance claims.

Raw replies, command traces, complete fixtures, failed attempts, identity keys,
and reviewer records remain outside Git. No raw model output, credentials,
adopter data, or private paths are included here.

## Limits and shipping boundary

This establishes representative Codex compatibility for the frozen port. It does
not prove all 54 skills, all 23 playbooks, real delegation, every platform,
production repositories, visual picker behavior, public installation, or an
advantage over Pstack. Optional Tugling guidance remains dormant.

The controlled release matrix still covers 4 of 54 skills. Native discovery and
these observations do not satisfy or replace that gate. Controller changes also
require independent approval, and certification is disabled. No stable ref,
version tag, controller pin, certification setting, or active user plugin was
changed. See [shipping preparation](../../docs/pstack-0.8.0-readiness.md) for the
remaining release requirements.
