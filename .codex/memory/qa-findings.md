# QA Findings Memory

## Health Endpoint Contract

- Type: Fact
- Status: Active
- Source: `docs/development.md`
- Last verified: 2026-05-29

The `/health` endpoint is part of the deployment contract. It must return HTTP 200 with JSON field `status` equal to `ok`. It must not expose secrets, connection strings, tokens, host internals, or detailed exception data.

## QA Evidence

- Type: Fact
- Status: Active
- Source: `README.md`, `docs/context-management.md`, `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-05-29

E2E QA evidence is a durable checkpoint. QA handoff context must include ticket, state, branch/OpenSpec change, PR, commit SHA, artifact path, validation commands, QA evidence, blockers, risks, assumptions, context findings, docs updated, and next action.

## QA Deployment Marker

- Type: Fact
- Status: Active
- Source: `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-05-29

Use `IA generated QA deployment: {commitSha}` as the stable marker for QA deployment idempotency.

## E2E QA Marker

- Type: Fact
- Status: Active
- Source: `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-05-29

Use `IA generated E2E QA: {ticketKey}` as the stable marker for E2E QA idempotency.

## QA Bug Marker

- Type: Fact
- Status: Active
- Source: `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-05-29

Use `IA generated QA bug: {parentTicketKey}` when creating a linked Plane bug from failed QA evidence.

