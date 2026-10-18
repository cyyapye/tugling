# Local Pstack experience observations, 2026-10-17

Seven single-attempt scenarios passed the automatic artifact checks and a parent
agent's review of completed command events, actual output, and resulting files.
This is observed local compatibility evidence, not independent human review or
release certification. No plugin instruction changes were needed for these runs.

The [runner](../../scripts/pstack_smoke.py) installed the frozen package through
Codex's local marketplace commands into a fresh home for each task. All 54 skill
directories matched the source package. Successful reads of the relevant installed
skills, Codex adapter, and playbooks were observed in the traces.

| Scenario | Observed outcome |
| --- | --- |
| Help | Familiar mode and setup invocations, a usable plan-only prompt, and no invented persistent Cursor mode or settings change. |
| Natural setup request | Loaded `setup-pstack` without an explicit skill token. Inherited settings stayed unchanged; unavailable controls and unverified menu details were stated. |
| Reply-only plan | Loaded the multi-phase planning playbook and returned two source-grounded phases. No plan file, implementation, test run, commit, or PR. |
| CLI bug fix | Loaded the bug-fix playbook, reproduced truncation, added two failing regressions, made a one-line repair, and verified the same CLI and native gate. Independent multi-word and Unicode examples passed. |
| Direct verification | The existing unit test passed, but actual CLI assertions exposed the documented behavior failure. The response withheld readiness and left source unchanged. |
| Architecture fallback | Compared the requested boundaries against actual source, preferred the smaller design, and disclosed sequential analysis without independent model review. No prototype or source edit. |
| Unavailable PR integration | Loaded Babysit in check mode, inspected local evidence, and kept PR existence, reviews, remote CI, and merge state unknown. No service or watcher was created. |

Runtime was Codex CLI `0.163.0-alpha.10.2`, `gpt-6-astra`, effort `xhigh`.
The plugin remained version `0.7.0`; its content SHA256 was
`a252737cfb4fc42a20bc5c01f8da90987580d448b756f35cec65b11b3d0115b4`.
The seven reviewed tasks used 990,998 input tokens (802,560 cached) and 12,688 output
tokens. These figures describe this run, not a performance or efficiency claim.

Two earlier help diagnostics stopped on a settings-byte comparison. A captured
before/after diff and read-only command trace identified Codex's automatic
fixture trust registration. The harness now prepares that same isolated project
entry before capturing settings; it still rejects subsequent settings changes.
Those original failed records remain separate from the seven-task run and are
not retrospectively relabeled passes. Raw output, workspaces, and reviews remain
outside the repository; authentication homes were removed after each task.

This does not establish behavior of every public skill, GUI picker behavior,
public marketplace installation, comparative improvement over Pstack, or release
readiness. The full-catalog release blocker and controller approval requirements
remain in force.
