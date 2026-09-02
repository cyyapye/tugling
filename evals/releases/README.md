# Tugling release certificates

Each `v<version>/certificate.json` is a sanitized, deterministic promotion input. It records the exact evaluated plugin digest, released baseline, public-install proof, fresh-task discovery result, model settings, case matrix, aggregate scores, and scan digests.

Raw behavioral outputs, blinded keys, authentication, project prompts, local correction ledgers, and temporary paths never belong here. A certificate is accepted only when it still matches the current plugin content and the evaluated revision is an ancestor of the exact `main` SHA being promoted.

The `Promote stable` workflow is manual. It re-runs `make verify`, verifies the certificate against the current `stable` baseline, requires a fast-forward from `stable` to the exact current `main` SHA, then atomically updates `stable` and creates the new immutable version tag.
