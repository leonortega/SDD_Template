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

## Multi-App QA Requires Live App-To-App Settings

- Type: Pattern
- Status: Active
- Source: `artifacts/qa/E2EPROJECT-2/20260602-215438-bc22889/qa-summary.md`, Azure App Service settings check during E2EPROJECT-2 QA
- Last verified: 2026-06-02

When E2E QA validates a topology with separate web and API App Services, verify the live Azure App Service settings before judging UI failures. For E2EPROJECT-2, the API passed directly but the QA site rendered an empty `Api__BaseUrl`, causing browser CRUD calls to target same-origin `/api/clients`. Setting the expected non-secret mappings (`Api__BaseUrl` on the web app and `Cors__AllowedOrigins__0` on the API app) and restarting the apps allowed the UI E2E flow to pass. Future QA runs should check these mappings early when a deployed UI cannot reach a deployed API.

## PowerShell Non-2xx API Bodies In QA Scripts

- Type: Pattern
- Status: Active
- Source: `artifacts/qa/E2EPROJECT-2/20260602-215438-bc22889/generated-tests/live-api-qa.ps1`
- Last verified: 2026-06-02

In PowerShell-based QA scripts, `Invoke-WebRequest` non-2xx response bodies may be available through `ErrorDetails.Message` instead of `Exception.Response.GetResponseStream()`. When asserting validation errors such as HTTP 400 problem details, prefer `ErrorDetails.Message` first, then fall back to response content or stream APIs. This avoids false QA failures where the API returned the expected validation body but the harness lost it.

## Rendered UI QA Should Use Frontend Debugging Guidance

- Type: Pattern
- Status: Active
- Source: Codex thread `019e83fb-7f1d-7f42-a1fa-b57bc4541947`, project-guidance mapper cleanup
- Last verified: 2026-06-02

For rendered website or Blazor UI QA, map to frontend/browser testing guidance in addition to API/deployment checks. Browser-visible validation should cover rendered content, console/network health, screenshots, traces, and interaction proof when the ticket changes UI behavior.

