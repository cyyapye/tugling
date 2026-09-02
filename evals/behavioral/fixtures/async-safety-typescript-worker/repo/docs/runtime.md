# Runtime contract

The broker redelivers a failed message after 1, 2, and 4 seconds and moves it to `export-failures` after the third failed receive. The durable job lease expires after 60 seconds. Operators can inspect the dead-letter queue, but this fixture has no checked-in redrive operation.

The production worker acquires the durable lease before calling the processor. A process crash can occur after lease acquisition and before completion is recorded.
