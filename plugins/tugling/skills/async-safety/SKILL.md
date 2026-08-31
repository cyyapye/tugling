---
name: async-safety
description: Design, implement, or review asynchronous workflows for duplicate delivery, retries, ordering, replay, idempotent transitions, terminal failures, and operator recovery. Use for queues, schedulers, webhooks, background workers, event consumers, batch jobs, and exactly-once-like claims. Do not use when the real risk is a purely synchronous request with no asynchronous state transition.
---

# Async Safety

Make duplicate and delayed delivery ordinary rather than exceptional.

## Advisory mode

When the user asks what an async design needs, answer the concern buckets directly before exploring implementation details:

1. **Trigger and envelope**: producer, transport, consumer, versioned message shape, correlation id, and delivery assumption.
2. **State and idempotency**: canonical state owner, idempotency key, allowed transitions, duplicate behavior, and no-op behavior after an already-applied transition.
3. **Ordering and staleness**: sequence or version rule, out-of-order stance, replay stance, and how current state wins over stale events.
4. **Retry and terminal failure**: classification, budget, backoff, lock or visibility behavior, dead-letter destination, and poison-item handling.
5. **Recovery and observability**: replay or redrive path, operator authority, partial-success semantics, logs, metrics, backlog, freshness, and alarms.
6. **Proof**: tests for duplicate, stale, out-of-order, retryable, terminal, and recovery cases plus runtime evidence when infrastructure is real.

Say `Not applicable` for an irrelevant bucket instead of silently omitting it.

## Implementation mode

1. Read repository instructions, workflow contracts, verification commands, and current infrastructure configuration.
2. Search for existing event types, dedupe stores, transition helpers, retry classifiers, queues, schedulers, metrics, and recovery commands.
3. Keep provider, vendor, and transport payloads at the adapter boundary. Shared workflow state should express domain events and transitions.
4. Assume at-least-once delivery unless a stronger contract is documented and independently enforced.
5. Implement in boundary order: message schema, state and dedupe behavior, producer, consumer, runtime rails, recovery path, docs.
6. Prove duplicate convergence, stale and out-of-order handling, retry exhaustion, terminal failure, and operator recovery with deterministic cases.
7. For deployed rails, distinguish local simulation from applied configuration and a current-run smoke.

## Guardrails

- A dead-letter queue without a safe inspection and replay path is storage, not recovery.
- Do not retry permanent business outcomes as infrastructure failures.
- Do not fail a current smoke from stale logs or old backlog; correlate evidence to the current run.
- Do not claim exactly-once behavior when the implementation provides idempotent at-least-once processing.
- Do not let an async trigger mutate accepted state without the repository's validation and authority boundary.

## Handoff

Report the producer and consumer, transition delta, idempotency and ordering rule, retry and terminal split, recovery path, proof collected, and any runtime rail that remains unverified.

Report read-only design or review work as `ADVISORY`, even when no files were meant to change. Use `NOOP` only when the user requested a bounded implementation and current evidence proves it was already satisfied or absent.
