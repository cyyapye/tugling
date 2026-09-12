# Working on Tugling

Tugling is a portable, skills-only plugin. Keep product rules and stack choices in
adopter repositories; keep reusable workflows in `plugins/tugling/skills/`.

- Use the existing seven skills before adding another entry point. Keep their
  descriptions short and specific; load references only for the relevant mode.
- `make verify` is the local completion gate. It needs Python 3.11+, Git, and Make,
  uses disposable synthetic fixtures, and makes no model calls or production
  changes. Run it, repair failures caused by the requested change, and rerun
  affected tests within the user's existing authorization.
- Use focused unittest cases while iterating. Once the final gate passes, repeat
  it only after a relevant change, failure, or unresolved concern.
- For skill behavior changes, use [CONTRIBUTING.md](CONTRIBUTING.md) and
  [the evaluation guide](evals/behavioral/README.md). Routing/schema checks are
  structural evidence; model behavior requires observed runs. Keep raw model
  output, local paths, credentials, and adopter data out of committed files.
- For changes to evaluators, fixtures, tests, packaging, or release machinery,
  read [the controller boundary](docs/release-controller.md). Local development
  does not update the independently approved controller pins.
- Certification and publication follow [release certification](docs/release-certification.md)
  and [stable promotion](docs/release-controller.md). They need the specified
  commit, usage, and release authority; ordinary implementation does not enable them.

Complete authorized work through its required verification. Report the result,
evidence, and any unverified boundary concisely; distinguish local, remote,
merged, deployed, and certified states.
