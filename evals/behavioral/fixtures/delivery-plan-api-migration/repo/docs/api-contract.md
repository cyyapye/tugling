# Account lookup contract

`lookup_by_username(username)` is public and used by the checked-in CLI plus a
separately deployed reporting integration. That integration cannot migrate in
the same deployment as this repository.

The replacement, `lookup_by_id(account_id)`, must be added before callers move.
The old API may be removed only after repository callers, contract telemetry,
and the external integration confirm migration. Until removal, rollback means
returning callers to the old path without reversing stored data.

The migration needs contract coverage for both APIs and an integration check of
the CLI boundary. A unit-only helper test is insufficient evidence for callers.
