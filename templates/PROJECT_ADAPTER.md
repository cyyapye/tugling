# Tugling project adapter

Use this as a starting section for a repository's `AGENTS.md` or equivalent contributor contract. Replace the angle-bracketed prompts with project facts and remove sections that do not apply. The repository contract overrides Tugling whenever it is stricter or more specific.

## Authority and scope

- Canonical repository and branch ownership: `<paths and branch rules>`
- Actions that require explicit approval: `<merge, deploy, delete, spend, contact, migration, or other boundaries>`
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

- Fast iteration commands: `<focused lint, type, unit, integration, or browser commands>`
- Canonical local gate: `<command>`
- Required second proof channel: `<real command, flow, profile, stored value, screenshot, or runtime smoke>`
- Remote and deployed gates: `<CI, preview, exact revision, production observation>`
- Evidence labels used by the project: `<for example LOCAL_PASS, REMOTE_PASS, DEPLOYED_PASS>`
- Cleanup command: `<how to leave the repository and local services clean>`
