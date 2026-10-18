# Reviewed Pstack compatibility evidence for 0.8.0

[pstack-review.json](pstack-review.json) is the sanitized input to reviewed release
certification. It is not a certificate and does not itself approve promotion.
Read the [observations](../../pstack/port-0.8.0-observations.md) and
[release policy](../../../docs/release-certification.md) before approving its digest.

The report records 15 observed builder attempts across 14 distinct tasks on the
same frozen plugin: 14 passed; the original authoring attempt failed three of six
criteria. A later attempt used an explicitly granted skill directory and a longer
timeout, then passed all six criteria. That repeat resolves an environment
restriction for the reviewed scope; it is not a matched performance comparison.
The original failure and its usage remain in the report.

The eight covered areas are discovery/setup, planning scope, repair/regression,
verification honesty, capability fallbacks, history scope, skill authoring and
idle scope. Source and native discovery checks separately covered all 54 names;
these observations do not prove every skill's behavior.

Reviews used separate same-family agents plus a parent trace audit. The tasks
were development checks, not statistical holdouts. Observed usage includes only
builders: 2,093,926 input tokens (including 1,751,424 cached) and 38,482 output
tokens. Author/reviewer cost is not measured here. No advantage over Pstack is
claimed, and optional Tugling additions remain dormant.

Private run, task and review hashes identify the reviewed evidence. They do not
reconstruct its content or independently prove judgment accuracy or completeness.
Maintainer acceptance of the exact report digest owns that trust boundary.
Raw traces, prompts, outputs, private paths and credentials remain outside Git.
