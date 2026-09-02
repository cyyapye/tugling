# Runtime contract

The queue invokes `handle_export_message` at least once. The checked-in
production rail is `config/queue.json`; it retries a retryable failure after 60
seconds, with at most three retries before the item enters the dead-letter
queue.

`process_export` claims a durable five-minute lease before writing the export.
A crashed worker cannot release that lease. Another attempt may reclaim the job
only after all 300 seconds have elapsed.

The worker test replaces `process_export` with a mock and asserts that a
retryable error requests another delivery. The lease test calls the store in
isolation and proves reclamation after 300 seconds. No current test drives the
actual queue consumer, processor, durable store, retry schedule, and lease clock
together.
