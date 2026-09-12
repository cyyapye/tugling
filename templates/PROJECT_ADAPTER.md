# Tugling project adapter

Use this as an optional source of project-specific facts for `AGENTS.md`. Keep
only rules that affect this repository, replace placeholders, and omit sections
that do not apply. Link existing authority instead of copying it. Move specialized
details to scoped instructions or docs with a clear condition for reading them.

## Local work and completion

- Bootstrap and supported runtime: `<native command and prerequisite source>`
- Run the smallest real flow: `<dev or CLI command and expected behavior>`
- Focused checks and canonical completion gate: `<native commands>`
- Safe local operations within a setup/implementation request: `<disposable fixtures, isolated services, in-scope test repairs>`
- Worktree isolation and cleanup: `<native ownership and teardown commands>`
- Read only when relevant: `<document path and the decision it informs>`

## Authority and scope

- Canonical repository and branch ownership: `<paths and branch rules>`
- Actions needing authority beyond routine local work: `<project-specific boundaries; reuse authorization already given>`
- Sources of durable product intent: `<specs, ADRs, product docs, runbooks>`

## Product and data invariants

- Canonical state owner: `<database, service, or source>`
- Values and transitions that must never be inferred: `<unknown, unavailable, rejected, deleted, accepted>`
- External evidence boundary: `<what observations may propose versus directly change>`
- Sensitive-data and fixture rules: `<classification, redaction, synthetic-data requirements>`
- Numeric and time representation: `<money, probability, precision, timezone>`

## Read and write paths

- Interactive read budget: `<round trips, latency, projection rules, forbidden hidden work>`
- Collection bounds: `<pagination, maximum cardinality, deterministic scale fixture>`
- Write and review boundary: `<validation, authorization, idempotency, audit>`

## Asynchronous work

- Delivery assumption: `<at least once or another documented contract>`
- Idempotency and ordering key: `<key and stale-event rule>`
- Retryable versus terminal failures: `<classification>`
- Recovery path: `<redrive, replay, operator command, rollback>`

## Interface contract

- Product reference screens or components: `<paths or routes>`
- Copy and visual-language authority: `<document path>`
- Required responsive, accessibility, and screenshot evidence: `<commands and artifacts>`

## Verification and release

- Additional proof for behavior the native gate does not cover: `<flow, profile, stored value, screenshot, or runtime smoke when needed>`
- Remote and deployed gates: `<CI, preview, exact revision, production observation>`
- Evidence labels used by the project: `<for example LOCAL_PASS, REMOTE_PASS, DEPLOYED_PASS>`
