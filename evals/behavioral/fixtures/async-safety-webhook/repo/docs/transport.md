# Delivery contract

The provider uses at-least-once delivery. Every event has a globally unique
`event_id`, an `account_id`, and a monotonically increasing `account_version`.
Retries preserve `event_id`. Delivery order is not guaranteed.

Canonical state records the highest accepted account version and processed
event IDs. An event older than canonical state is acknowledged as a no-op.
Schema and authorization failures are permanent outcomes. Timeouts and
temporary storage failures are retryable with a bounded budget.

Exhausted items enter a dead-letter queue. Recovery is complete only when an
operator can inspect the reason, correct a safe precondition, and redrive the
specific item with an audit record.
