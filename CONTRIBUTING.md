# Contributing

Keep Tugling small, portable, and evidence-led.

1. Start with a real repeated failure or decision that the current skill mishandles. Check Pstack first; reuse its method with pinned provenance and full attribution before writing an equivalent. See the [reuse comparison](docs/lineage.md).
2. Put product, vendor, language, and deployment-specific policy in a project adapter unless it generalizes cleanly.
3. Change the narrowest skill that owns the decision.
4. Test changed invocation behavior with observed Codex runs. Preserve Pstack's explicit invocation policy; declarative prompt cards are not routing evidence. See the [evaluation audit](evals/test-audit.md).
5. Run `make verify`.
6. For consequential instruction changes, follow [Pstack's Eval method on Codex](evals/pstack/method.md): organic tasks, hidden criteria, blinded output review and observed execution. Compare the same Codex-adapted Pstack method with and without one addition, on matched development and fresh holdout tasks. The legacy decision questionnaire is a regression diagnostic, not the development quality gate.
7. For a release, separately satisfy the existing three-attempt, full-matrix released-versus-candidate promotion gate with a configured public-policy scan. This controlled legacy gate does not substitute for the Pstack comparison or fresh project evidence behind a quality claim.
8. For that release, install the exact public candidate through a fresh Codex home and prove a new read-only task loads the installed skill.
9. Keep raw runs, authentication, local paths, and project prompts outside the repository. Only the sanitized release certificate belongs in the release record.
10. Follow the [release-controller review procedure](docs/release-controller.md) before changing grading, tests, packaging policy, or release machinery. A candidate cannot authorize its own controller update.

PR checks need no API key and spend no model tokens. Maintainers may use the
separately enabled [certification workflow](docs/release-certification.md) for the
full release evaluation; each run needs explicit commit and usage approval.
Contributors running the live suite locally use their own model allowance.

A longer skill is not automatically a better skill. Default to Pstack while an
addition's advantage is unproven; conditional automatic loading still requires
evidence. Preserve useful failure cases for future comparisons. Prefer one
instruction that changes a decision over a catalog of generic advice.
