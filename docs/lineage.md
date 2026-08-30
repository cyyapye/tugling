# Lineage and boundaries

Tugling is not a Pstack fork and is not a dump of project-local rules. It is a smaller Codex-native layer distilled from two useful sources:

- Pstack's named engineering principles and proof-oriented workflow.
- Keel's unusually strong treatment of uncertainty, evidence, bounded reads, deterministic fixtures, and proof before release.

The source projects remain the authority for their own behavior. Tugling keeps only the parts that should make the same decision in an unrelated repository.

## Skill map

| Concern | Pstack | Keel | Tugling |
| --- | --- | --- | --- |
| End-to-end routing | `poteto-mode` and playbooks | Repository workflow and contributor instructions | `$tugling` |
| Planning and design | `architect`, `arena` | Roadmap, ADR, and bounded implementation-plan conventions | `$delivery-plan` |
| Performance and cost | Perf and hillclimb playbooks, `blast-radius` | Projection-only reads, fixed round-trip budgets, deterministic scale cases | `$scale-cost-review` plus a stricter local adapter |
| Async correctness | Idempotency and boundary principles | Reviewed ingestion, replay-safe proposals, provider-sync boundaries | `$async-safety` plus domain transitions kept locally |
| Verification | `prove-it-works`, `blast-radius`, verification-skill generators, shipping playbooks | `make verify`, visual evidence, exact-revision release proof | `$repo-verify` plus repository release rules |
| UI diagnosis | Visual-parity playbook | `keel-ui-quality` and the canonical UI/copy contract | `$screenshot-first-ui`; product visual language stays local |
| Skill evolution | Skill-authoring and eval playbooks, `reflect` | Repo-local skills and acceptance contracts | `$skill-delivery` |

## Pstack's 21 principles mapped to the Tugling Twelve

Pstack's principle names belong to Pstack. This table records the conceptual condensation rather than reproducing its individual skill files.

| Pstack principle | Tugling destination |
| --- | --- |
| Laziness Protocol | 3. Subtract first; 4. Ship the smallest complete change |
| Foundational Thinking | 2. Model the thing |
| Redesign from First Principles | 2. Model the thing; 6. Explore before costly commitments |
| Subtract Before You Add | 3. Subtract first |
| Minimize Reader Load | 5. Keep it easy to read |
| Outcome-Oriented Execution | 1. Start with the outcome; 4. Ship the smallest complete change |
| Experience First | 1. Start with the outcome |
| Exhaust the Design Space | 6. Explore before costly commitments |
| Build the Lever | 12. Turn lessons into rails |
| Model the Domain | 2. Model the thing |
| Boundary Discipline | 7. Guard every boundary |
| Type System Discipline | 2. Model the thing; 7. Guard every boundary |
| Make Operations Idempotent | 9. Make retries boring |
| Migrate Callers Then Delete Legacy APIs | 4. Ship the smallest complete change |
| Separate Before Serializing Shared State | 10. Work in verifiable slices |
| Prove It Works | 11. Prove the real thing |
| Fix Root Causes | 11. Prove the real thing |
| Sequence Work into Verifiable Units | 10. Work in verifiable slices |
| Guard the Context Window | 10. Work in verifiable slices |
| Never Block on the Human | 10. Progress reversibly within authority, but stop at real approval boundaries |
| Encode Lessons in Structure | 12. Turn lessons into rails |

## What Tugling added or sharpened

The condensation deliberately makes several lessons explicit:

1. **Performance and cost are design inputs.** Cardinality, latency, query shape, fanout, recurring usage, and cleanup ownership are reviewed before implementation.
2. **A bounded no-op is a result.** An invocation or checklist is not proof that work exists.
3. **Verification machinery needs review.** A green result is weak evidence if the same change softened assertions, fixtures, snapshots, coverage, retries, or CI.
4. **Evidence and authority are different.** External facts, model output, and monitoring events should not silently become accepted state.
5. **Unknown stays unknown.** Missing, unavailable, or unreported values do not become zero or success for convenience.
6. **Proof has levels.** Local, remote, merged, deployed, and production-observed states are reported separately.

## What remains project-local

Tugling must not know a project's database, financial arithmetic, privacy classification, design system, cloud provider, release branch, or deployment authority.

For example, Keel should continue to own its financial data model, synthetic-only fixtures, review-before-apply contract, UI language, and exact release gates. Tugling supplies the reusable questions and proof discipline; project adapters supply the answers and stricter invariants.

This boundary prevents a generic plugin update from silently changing product behavior in every repository that uses it.
