# Quota service

An offline Python 3.11+ example of a scheduled integration. Its fake provider
counts requests without sockets, clocks, credentials, or external dependencies.
Three tenants share 120 provider requests in a ten-minute window; reserve 30 for
other activity, leaving **90 requests** for this workload. Every active tenant
must receive samples. An idle workload makes no provider calls.

Report rendering uses one owned temporary file. Success and failure both remove
that file and preserve unrelated files in the caller's directory. A pre-existing
file at the proposed temporary path is never overwritten or deleted.

`make verify` is the current native completion command. `make test
TEST_ARGS='tests.test_service.ServiceTests.test_idle_workload_makes_no_calls'`
runs a focused case during iteration. These commands require only Python, Make,
and Git. CI uses ordinary unprivileged pull-request checks. There is no database,
deployment, package installation, or hosted account setup.
