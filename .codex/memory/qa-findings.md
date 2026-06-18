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
- Source: `artifacts/qa/E2EPROJECT-2/20260602-215438-bc22889/qa-summary.md`, Azure App Service settings check during E2EPROJECT-2 QA, live DEV/PROD Azure App Service repair on 2026-06-04
- Last verified: 2026-06-04

When E2E QA or live DEV/PROD validation uses separate web and API App Services, verify the live Azure App Service settings before judging UI failures. For E2EPROJECT-2, the API passed directly but the QA site rendered an empty `Api__BaseUrl`, causing browser CRUD calls to target same-origin `/api/clients`. The same pattern later appeared in DEV and PROD: the web apps rendered an empty API base URL and POSTed to the web app's `/api/clients`, returning 404. Setting the expected non-secret mappings (`Api__BaseUrl` on the web app, `Cors__AllowedOrigins__0` and `ConnectionStrings__ClientsDb` on the API app) and restarting the apps allowed CORS preflight and create/delete smoke tests to pass. Future environment checks should inspect rendered `const apiBaseUrl` plus live app settings early when a deployed UI cannot reach a deployed API.

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

## QA Branch Actions Require Workflow On The Pushed Ref

- Type: Pattern
- Status: Active
- Source: Gitea Actions run 91 setup for `qa/E2EPROJECT-2/rerun-current-20260603024107`, failed no-run attempt from `qa/E2EPROJECT-2/rerun-20260603023208`
- Last verified: 2026-06-03

For `qa/{ticketKey}` E2E reruns, push a ref that contains the current `.gitea/workflows/package-deploy.yml` with the `qa/**` trigger and `e2e-qa` job. Pushing an older artifact commit that predates the QA branch workflow can create the remote branch successfully but produce no Gitea Actions run. Use a branch based on current `origin/dev` when the goal is to run the evidence-only QA branch workflow without redeploying.

## Expected Browser Noise In CRUD E2E

- Type: Pattern
- Status: Active
- Source: Gitea Actions runs 91, 92, and 93 for `qa/E2EPROJECT-2/rerun-console-filter-20260603024728`; Nexus evidence `app/787036922b45e595e53e241457ebdb7ff8cc9db8/qa-e2e-evidence.zip`
- Last verified: 2026-06-03

In Playwright CRUD QA flows, expected negative-path browser activity can surface as console or request noise even when the app behavior is correct. For E2EPROJECT-2, an intentional validation POST returned HTTP 400 and Chromium logged `Failed to load resource`, while a successful delete could emit a browser-side `DELETE ... net::ERR_ABORTED` even though API verification confirmed the record was removed. Keep console and request-failure assertions strict, but add narrow allowances around expected validation and delete actions instead of accepting all 400s or all aborted requests.

## Local E2E Diagnostics Use Docker Browser Image

- Type: Decision
- Status: Active
- Source: E2EPROJECT-7 Docker local runner change, `tests/SDDTemplate.E2ETests/run-local-docker.ps1`, `.codex/skills/quality-test-e2e/SKILL.md`
- Last verified: 2026-06-17

For local Playwright diagnosis against deployed QA, use `npm run test:docker` from `tests/SDDTemplate.E2ETests`. The runner uses the pinned `agentic/e2e-ci:playwright-1.57.0-1` image, reads `E2E_SITE_URL`/`E2E_API_URL` or ignored `.codex/client-tools.local.json` QA URLs, and avoids repeated host Chromium installs. Browser/E2E diagnosis stays outside product code; if failures are harness-only, patch tests/workflow/evidence capture rather than adding app-only E2E helpers.
