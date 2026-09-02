# Queued export fixture

The export worker uses a durable lease to keep concurrent deliveries from
running the same export. Existing tests cover retry routing and lease expiry
separately.
