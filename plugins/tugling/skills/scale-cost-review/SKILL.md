---
name: scale-cost-review
description: Review volume, latency, data-access, and operating-cost risks in hot paths, collections, or recurring workloads. Use for a material scale decision or requested review; skip unrelated isolated edits.
---

# Scale Cost Review

Prevent a design that passes a tiny demo while becoming slow, expensive, or operationally awkward at realistic volume.

## Decisions to resolve

1. **Simplest viable shape**
   - Describe the least machinery that satisfies the outcome.
   - Name what would justify an extra cache, queue, service, index, projection, or dependency.
   - Prefer removing work over accelerating unnecessary work.
2. **Scale envelope**
   - State expected cardinality now, at the next meaningful boundary, and at a plausible growth multiple.
   - Set an interactive latency or batch-completion target, freshness need, consistency tolerance, and downstream rate limit.
3. **Hot-path budget**
   - Count storage and network round trips, fanout, write amplification, memory, and payload size.
   - Keep repository round trips independent of returned row count when set-based queries or bounded batches are available.
   - Reject unbounded scans, unlimited collections, request-time fanout aggregates, and per-record provider calls on a hot path.
4. **Serving shape**
   - Separate canonical write ownership from projections, caches, counters, and read models.
   - Define refresh, invalidation, rebuild, backfill, stale-data behavior, and pagination with stable ordering.
   - Avoid hiding reconciliation, provider reads, or writes inside an interactive read unless the repository explicitly requires and budgets them.
5. **Failure and cost**
   - State partial-success behavior, retries, poison-item handling, backlog limits, and recovery ownership.
   - For recurring work, estimate runs, records read and written, retention, cleanup, and monthly cost. Identify the metric or alarm that catches growth.
6. **Proof**
   - Measure before optimizing.
   - Use a deterministic fixture large enough to cross the first real pagination, batching, or cardinality boundary.
   - Assert query or round-trip budgets where possible and inspect the database plan for correlated scans.
   - Compare before and after latency, query shape, or cost against the same harness.

## Output

Report the chosen shape, accepted budgets, measured evidence, and assumptions that affect the decision. Cover relevant decisions above without imposing a fixed section template.

Report `ADVISORY` when the result is guidance and no accepted readiness boundary is shown to fail. Report `BLOCKED` when the inspected current or proposed design violates an explicit required envelope, or when a requested readiness claim lacks its required scale or query-shape proof. A read-only review can still prove that readiness is blocked.

When implementing, state the accepted envelope before editing and verify the changed path against it. Do not claim performance or savings from architectural intuition alone.
