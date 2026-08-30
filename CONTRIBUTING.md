# Contributing

Keep Tugling small, portable, and evidence-led.

1. Start with a real repeated failure or decision that the current skill mishandles.
2. Put product, vendor, language, and deployment-specific policy in a project adapter unless it generalizes cleanly.
3. Change the narrowest skill that owns the decision.
4. Add positive and negative routing fixtures for changed trigger behavior.
5. Run `make verify`.
6. For consequential instruction changes, compare the current and proposed skill on blinded holdout prompts before promotion.

A longer skill is not automatically a better skill. Prefer one instruction that changes a decision over a catalog of generic advice.
