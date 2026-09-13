# First-time native enforcement diagnostic

This supplementary fixture tests a complete first setup on an offline Python
service. Its resource is a shared third-party request quota, not a database.
Five existing unittest cases cover the aggregate workload, idle calls, report
cleanup on success and failure, and preservation of a pre-existing foreign file.
They share a file so file-presence checks cannot stand in for case coverage.
The original Make target permits focused `TEST_ARGS` during iteration.

The setup prompt in `cases.json` supplies the product task and authority, without
the oracle's specific mutation or implementation hints. Run the model only on a
copy of `fixtures/quota-service/repo` and the reviewed installed candidate;
keep the oracle, reference setup in the self-tests, and invocation bindings
outside that model workspace and candidate source. Freeze these controls before
observing first-setup results. Do not repair a failed first setup and score the
repaired tree as if the model created it independently.

These diagnostics make no model calls and do not change the release matrix,
controller pins, or promotion thresholds. A real installed-plugin task must be
run separately with existing authorization and bounded usage/time. Preserve the
original output outside reusable source. Compare first setup with first setup;
a no-op on an already corrected tree is a different outcome.

## Run the independent local oracle

Prepare a new disposable Git project:

```sh
python3 evals/enforcement/verify_enforcement.py prepare --out /absolute/new-project
```

After the setup task, a reviewer reads its adapter, entrypoint, and workflow and
writes an invocation JSON **outside the project**. This binds discovered native
commands without forcing setup implementation filenames:

```json
{
  "schema_version": 1,
  "source_root": "/absolute/reviewed-candidate",
  "gate": {
    "argv": ["make", "verify"],
    "env": {"TUGLING_SOURCE": "{source}"}
  },
  "ci": {
    "workflow": ".github/workflows/verify.yml",
    "checkout_step": 0,
    "identity_step": 1,
    "pr_revision": "head"
  }
}
```

`{source}` is replaced in argv or environment bindings for the normal and
untrusted-source controls; `{repo}` is also available. Choose the actual
caller-selectable source setting exposed by the finished project. The optional
`config` field selects an alternative adapter path; it defaults to
`.tugling/project.json`. The trusted helper validates this adapter and complete
required receipts. The selected gate must be the declared canonical command or
an outer required wrapper whose mapped native flows execute that command.

CI indices select the project checkout and the actual executable identity
assertion among workflow steps, starting at zero. Declare `pr_revision` as `head`
or `merge` from the reviewed project/workflow contract; the task does not impose
one universal PR identity. Explicit merge-commit evidence is labelled as such
and cannot establish exact-head verification. The optional `source_checkout_step`
identifies the exact-pinned Tugling checkout when a run block uses it. The oracle
reproduces the real sibling checkout paths, so a combined identity assertion and
native gate executes normally with no mocked verification command.
The small stdlib reader
supports ordinary step mappings, step-local environment variables, run blocks,
and `github.event.pull_request.head.sha || github.sha` expressions. It executes
that code for matching and mismatched pull-request and push revisions. Unsupported
workflow syntax or a missing runner returns `ORACLE_INCONCLUSIVE` (exit 2), not
evidence the setup failed. An observed failed criterion returns `ORACLE_FAIL`
(exit 1). Adapt an unsupported binding only after independent review, without
changing the frozen criterion or coaching the setup task.

```sh
python3 evals/enforcement/verify_enforcement.py verify \
  --repo /absolute/completed-project --invocation /absolute/reviewer-invocation.json
```

The oracle snapshots intended source only into disposable committed projects.
Each regression is committed before execution so a generic dirty-check refusal
cannot masquerade as catching a defect. It requires:

- A passing good native gate and complete helper-validated required receipt.
- Failure for excessive actual fake-provider calls and disabled owned cleanup.
- Failure after removing or skipping one existing case while its file remains.
- A real focused pass on a broken project alongside required failure; environment
  and Make command-line selection cannot turn that failure into completion.
- No automatic inventory rebaseline during gate execution.
- Rejection of an ignored nested untracked helper and changed tracked helper
  before either writes its execution marker. The tracked-byte mutation uses
  `assume-unchanged` only in the disposable source clone, whose Git status must
  remain clean. A clean-status check alone cannot satisfy this control; the
  wrapper must reject the index flag or verify the actual tracked helper bytes.
- Explicit CI revision selection and executable identity assertions that reject
  a different checked-out commit, followed by a restored good gate.

Unittest has no reporter plugin override in this fixture. Selection controls
exercise its actual public narrowing interface; stack-specific reporter overrides
need a separate native-runner case, such as the Keel pilot. Inventory checks do
not establish the quality of arbitrary new assertions. Original product bytes
are preserved. A removed existing case fails; changed test bodies require
independent semantic review and return `ORACLE_INCONCLUSIVE`, since additional
assertions can strengthen a test without changing its required identity.

All commands run offline with a credential-free environment, bounded output and
timeouts. Source snapshots are capped at 2,000 files and 16 MiB each. Disposable
trees and logs are owned by the oracle's temporary context and removed on exit.
The caller project must remain unchanged. The result is **local native and CI
identity-control proof**; it does not claim GitHub execution, merge protection,
model improvement, elapsed-time improvement, certification, or release promotion.

## Assessment-only holdout

Save `snapshot --repo PROJECT` JSON outside the project before the advisory task.
Then run `assess --repo PROJECT --before SNAPSHOT.json`. It compares all project
files, including ignored outputs, plus Git head/status. A clean result proves
zero file/Git changes, while the task's response and commands still need review
to establish that it did not run setup or touch external state.

## Deterministic evaluator checks

```sh
python3 -m unittest discover -s tests -p 'test_enforcement_eval.py'
```

The tests build an independent small adapter using the real Tugling helper and
exercise correct and deliberately weak setups. No model output, adopter data,
provider access, or paid certification is needed. These evaluator changes remain
subject to the separate [controller review boundary](../../docs/release-controller.md).
