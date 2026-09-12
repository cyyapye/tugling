# Project setup diagnostics

These supplementary synthetic cases exercise new-project bootstrap, an explicitly
authorized repair despite an older ask-first convention, and assessment-only scope.
They use the existing behavioral runner, command trace, Git checks, and decision
grader. The implementation cases also run an independent functional oracle from
outside the agent's checkout. It snapshots intended source without ignored files,
executes the prepared local-environment command, requires it to notice a failing
native bootstrap, repeats bootstrap, tests a real
CLI with different names, requires nonempty unittest coverage and native gates
that catch a broken CLI, and checks that repeated cleanup removes owned bytecode
while preserving source and unrelated user files.

Command fragments recognize both shell and Python argv spellings. They are
supporting trace evidence; inspect successful raw execution as well as the score
and independent oracle before making a behavioral claim.

The fixtures deliberately specify an offline standard-library Python CLI. This
keeps a setup failure distinct from network, provider, or dependency access. It
does not establish browser/UI bootstrap, real Codex app discovery, or adoption CI.
The CLI sandbox protects `.codex/`, so these cases explicitly request a prepared
`codex-environment.toml` in a writable location. Passing proves its contents and
commands, not installation in the final `.codex/environments/environment.toml`
location. A separate forward test in a writable isolated workspace can exercise
that final path with the oracle's default arguments. An unrequested sandbox
workaround or a blocked installation must not be scored as completed setup.
The oracle uses Python 3.11+ for native TOML parsing.

Validate cases and test the oracle without model calls:

```bash
python3 scripts/setup_eval.py validate
python3 -m unittest discover -s tests -p 'test_setup_eval.py'
```

For an explicitly scoped local Astra comparison using the contributor's own
authenticated Codex CLI and model allowance:

```bash
python3 scripts/setup_eval.py run \
  --condition both --attempts 1 --jobs 1 \
  --model gpt-6-astra --reasoning-effort medium \
  --max-input-tokens 1500000 --max-output-tokens 40000 \
  --timeout 300 --require-gate dogfood \
  --out /private/tmp/tugling-astra-setup-diagnostic
```

Use an empty output directory. The runner admits at most 24 tasks per invocation
and one task at a time. Token thresholds are checked between tasks; an in-flight
task can exceed a threshold, so these are not hard billing caps. Raw per-task
evidence remains available after a failed run; no result is a fabricated pass.
Runtime failures and missing usage stop further tasks. No task is automatically
retried. `--keep-workspaces` retains synthetic artifacts for inspection.

The three distinct control/candidate pairs use the existing dogfood thresholds.
One attempt is exploratory; use repeated runs and independent review before
claiming improvement. Compare completion, critical regressions, commands, tokens,
and elapsed time; smaller prompts alone do not prove better results.

These diagnostics cannot run promotion and do not change the frozen 10-case,
91-task release matrix, its model, or any controller pin. Use the existing bundled
cases as holdouts for asynchronous safety, bounded no-ops, UI proof, and native
verification. Follow the normal reviewed controller procedure before shipping
changes to these diagnostics or using them as release evidence.
