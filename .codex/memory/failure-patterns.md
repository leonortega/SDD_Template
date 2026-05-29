# Failure Pattern Memory

## Ambiguous Ticket Or Stale Lock

- Type: Pattern
- Status: Active
- Source: `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-05-29

If a child skill resolves a ticket key that differs from `.codex/delivery-context.local.json`, stop and report the mismatch. Do not deploy, test, move state, tag, or comment the other ticket. If the lock is stale but durable checkpoints identify a different ticket, stop and ask the user to clear or replace the lock.

## Deployment Lane Conflict

- Type: Pattern
- Status: Active
- Source: `.codex/skills/_shared/delivery-contract.md`, `docs/architecture.md`
- Last verified: 2026-05-29

DEV, QA, E2E QA, PROD, rollback, and hotfix stages are serialized. If `.codex/parallel-delivery.local.json` records another deployment-lane owner, report the owner and wait rather than mutating shared deployment state.

## Blocking PR Labels

- Type: Pattern
- Status: Active
- Source: `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-05-29

QA promotion must stop when a merged PR still has `needs-tests` or `needs-changes`.

## Conflicting Release Manifest Or Tags

- Type: Pattern
- Status: Active
- Source: `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-05-29

Stop when release manifest fields conflict with Plane comments or tags. Validate `release.json` against `.codex/skills/_shared/release.schema.json` when reading or writing it.

## Nexus Unavailable

- Type: Pattern
- Status: Active
- Source: `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-05-29

Nexus is mandatory for DEV, QA, PROD, and rollback promotion. If Nexus is unavailable for promotion, stop instead of rebuilding locally or deploying from local files.

## Main Divergence

- Type: Pattern
- Status: Active
- Source: `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-05-29

Stop if `main` diverges from the intended QA-approved commit. Rollback does not rewrite `main`; after rollback, require a hotfix PR, revert PR, or explicit temporary divergence note with owner and expected resolution.

## Secret Exposure Risk

- Type: Risk
- Status: Active
- Source: `README.md`, `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-05-29

Do not read secrets from Docker containers, mounted volumes, databases, logs, or committed files. Do not store secrets in memory. Tracked examples must remain placeholder-safe.

