# List serving contract

- The table has 1,000,000 projects and grows by roughly 80,000 per month.
- A page contains at most 50 projects in `(created_at, id)` descending order.
- Interactive p95 target: 200 ms.
- A page may use at most three database round trips, independent of page size.
- GET requests may read projections only. Reconciliation, writes, and provider
  calls run during ingestion or explicit maintenance.
- The deterministic scale case contains at least 120 projects so it crosses two
  page boundaries.
- Cost review covers request-driven reads, projection writes, retained rows,
  cleanup, and the expected monthly request volume.
