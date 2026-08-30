# The Tugling Twelve

These principles are a decision vocabulary, not a ceremony. Apply only the ones that materially change the work. When naming one, state the decision it changed. Repository instructions may tighten these defaults and always remain authoritative.

## 1. Start with the outcome

Define the user-visible or operator-visible result and the observable finish condition before choosing implementation machinery. Prefer the result over implementation convenience.

## 2. Model the thing

Name the entities, ownership, states, transitions, and invariants before scattering logic. Use data structures, schemas, and types to make invalid states difficult to express.

## 3. Subtract first

Remove obsolete paths, duplicated concepts, and unnecessary surfaces before adding another layer. Deletion is a design option, not cleanup reserved for later.

## 4. Ship the smallest complete change

Choose the least code and infrastructure that fully solves the problem. Complete includes migration, proof, and required documentation; it does not mean preserving throwaway compatibility forever.

## 5. Keep it easy to read

Minimize layers, hidden state, branches, and concepts a maintainer must remember at once. A local abstraction is useful only when it removes more cognitive load than it adds.

## 6. Explore before costly commitments

For novel or hard-to-reverse boundaries, compare a few meaningfully different designs or prototypes before settling. Skip the ceremony when precedent and reversibility make the decision cheap.

## 7. Guard every boundary

Validate external input where it enters, keep provider and transport details at adapters, and preserve missing or uncertain information instead of inventing certainty. Evidence may inform a decision without owning the accepted state.

## 8. Budget the hot path

State the expected cardinality, latency, round trips, fanout, rate limits, growth, and operating cost. Keep interactive reads and recurring work bounded; avoid per-item storage or network calls when set-based work or projections fit.

## 9. Make retries boring

Assume duplicate, delayed, replayed, and out-of-order delivery. Define the idempotency key, allowed transitions, stale-event behavior, retry budget, terminal failures, and recovery path so retries converge safely.

## 10. Work in verifiable slices

End each bounded unit with a check before opening the next. Isolate writers instead of coordinating shared mutable state. When current evidence proves no change is needed, an explicit no-op is a valid result. Progress reversibly within existing authority; stop at a real approval boundary.

## 11. Prove the real thing

Reproduce before fixing, trace the root cause, and verify the artifact or behavior the user actually depends on. Keep local checks, remote checks, and deployed evidence distinct. Changed tests or judging machinery cannot be their own only proof.

## 12. Turn lessons into rails

When a lesson recurs, encode it in the cheapest durable structure: a type, test, lint, script, fixture, checklist, runbook, or focused skill. Prefer a rerunnable lever over advice that must be remembered.
