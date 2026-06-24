---
name: quality-test-e2e
description: Run post-deploy E2E QA for configured tickets that are already in QA, including "test qa automation", "test qa deploy", "run QA tests", "complete QA", "E2E test a QA ticket", "validate QA and move to Done", and "run ticket-specific website/API QA". Use when Codex needs to inspect ticket expectations, choose the configured E2E adapter, execute scoped QA checks, collect evidence, comment results through the ticket adapter, and move the ticket to the configured Done state only when all checks pass.
---

# Test E2E

## Overview

Use this skill after deployment validation has already moved a ticket to QA. Act as a QA expert: test only the website and API behavior implied by the ticket, record evidence, and move the ticket to the configured final state only after every required QA check passes.

This skill is technology-agnostic. Inspect the repository first. Use an established E2E/API test tool when one is already configured; otherwise ask the user to choose before creating or running technology-dependent tests.

For rendered website changes, prefer `$quality-frontend-testing-debugging` when the repo has `.codex/skills/quality-frontend-testing-debugging/SKILL.md` and the ticket requires browser-visible validation, responsive layout checks, console health, screenshots, or interaction proof. Keep API and deployment health checks in the repo-native stack path.

When the repository contains `tests/SDDTemplate.E2ETests`, treat it as the reusable deployed-QA regression suite. Implementation records browser E2E expectations and acceptance oracles, but E2E creation and repair are owned by this QA skill unless the user, ticket, or OpenSpec artifacts explicitly made E2E part of implementation PR scope. The suite is executed by the selected-provider QA job against the deployed QA Site/API URLs. The selected deployment adapter defines any temporary QA branch and job names. Create or update reusable tests on the QA branch when the existing suite cannot prove a required acceptance criterion, record the reason in the QA result, and route those test changes through the normal reviewed follow-up path unless the configured QA workflow rule explicitly allows committing them in the QA workflow. This skill still owns QA acceptance: verify the repository E2E evidence bundle, publish final QA evidence, create or verify the RC tag, update release metadata, add the ticket-provider comment, move the ticket to Done only after the QA result is `PASS`, and delete the remote QA trigger branch after durable evidence exists. Local E2E QA is forbidden unless a deployment-related blocker prevents the normal selected-provider E2E path from running or completing and `agentOptimization.maxToolRetries` deploy-fix attempts from `.codex/delivery-policy.json` have failed; the current limit is `2`. Product E2E test failures remain QA failures and are not a local-fallback trigger.

After the evidence bundle is verified, the E2E QA ticket comment is verified, the RC tag is created or verified, release metadata is updated, and the ticket is moved to Done, delete the remote selected-provider QA trigger branch through the repository adapter. The branch is only a temporary evidence trigger; durable evidence is in Nexus, ticket provider, the release manifest, and tags. Keep the branch only when evidence publication, comment verification, RC tagging, or Done-state mutation is incomplete and the branch may need a rerun.

For the current Rancher Desktop lane, the temporary branch is `qa-local/{ticketKey}`. Example cleanup command after durable evidence exists:

```powershell
git push origin --delete qa-local/E2EPROJECT-123
```

Do not delete the branch before Nexus evidence exists, the E2E QA comment is verified, the RC tag is created or verified, release metadata is updated, and the ticket is Done.

Non-interactive context means the run has no available user-response channel, such as cron automation, CI, detached automation, or an explicit "do not ask" instruction.

## Shared Context

Before QA state changes, follow `.codex/skills/_shared/skill-startup.md`, which reads `.codex/project-profile.json`, `.codex/skills/_shared/provider-adapter-contract.md`, `.codex/skills/_shared/delivery-contract.md`, and `docs/context-management.md`, with `docs/deployment.md` as the stage-specific doc. Load selected ticket, artifact, deployment, repository/review, and E2E adapters. Use `.codex/skills/_shared/scripts/delivery_tools.ps1` helpers: `ValidateTicketLock` for `.codex/delivery-context.local.json`, `ValidateDeploymentLane`, `CheckGitIgnored`, `NextRcVersion`, `UpdateReleaseManifest`, `ValidateReleaseManifest`, and `RenderTicketComment -Type E2EQA`.

## Workflow Telemetry

Capture UTC start time after resolving the ticket key and before QA evidence checks. Append a `quality-test-e2e` row with `.codex/skills/_shared/scripts/delivery_tools.ps1 -Mode AppendWorkflowTelemetry -TicketKey {ticketKey}` when E2E QA succeeds, blocks, fails, or is skipped idempotently because the verified E2E QA comment and Done state already exist. On resume or idempotent reuse, append another row for the same stage; workflow timing rendering collapses repeated stage rows into earliest start and latest finish. Include `workflowStage=quality-test-e2e`, `agentRole=qa`, `startedUtc`, `finishedUtc`, `retryCount`, and `outcome`.

After the E2E QA ticket comment is verified and before final QA handoff, read the active ticket rows with `.codex/skills/_shared/scripts/delivery_tools.ps1 -Mode ReadWorkflowTelemetry -TicketKey {ticketKey}`, render `.codex/skills/_shared/scripts/delivery_tools.ps1 -Mode RenderTicketComment -Type WorkflowTiming`, then create a ticket provider activity with stable marker `IA generated workflow timing: {ticketKey}`. Send a `comment.raw` activity payload and verify the activity comment starts with the marker after posting. The timing comment must include only status, current route, total elapsed time, and the stage table. Stages that did not run or did not apply must remain visible in the table as `NOT RUN / N/A` with duration `no time`; repeated rows for a stage are collapsed by earliest start and latest finish. Do not include token counts, prompts, raw logs, credential-bearing URLs, noisy tool details, repository workflow job duration, or ticket provider marker-derived timing. If telemetry cannot be written or read, report the workflow timing comment as blocked.

## Configuration

Read `.codex/client-tools.local.json` first. Fall back to `.codex/client-tools.example.json` only for structure and default names, then apply environment variable overrides when present.

Required or defaulted values:

- `selected ticket adapter runtime values`
- `configured QA state`, default `QA`
- `configured Done state`, default `Done` only when explicitly configured or confirmed
- `selected repository/review adapter runtime values` when PR/deploy context is needed
- `nexus.baseUrl`, `nexus.username`, `nexus.password`, `nexus.repository` when publishing QA evidence bundles
- source RC version for release candidates, supplied by the user or resolved from an existing annotated tag on the tested commit, using format `vMAJOR.MINOR.PATCH-rc.N`

Provider-supported environment variables may override local JSON when present. Repository/review overrides include `selected repository/review adapter overrides`.

## Workflow

### 1. Resolve Context

1. Resolve the ticket from user input, current branch, repository PR metadata, deployment comments, repository E2E evidence, commit messages, or a ticket key.
2. Run `ValidateTicketLock` with the resolved ticket, QA deployment commit, artifact commit, and known version values. If the result is invalid, stop before testing or writing evidence.
3. Fetch the ticket with expanded state/project data.
4. Verify the ticket is in `configured QA state`. If it is not, stop unless the user explicitly asks to test despite the state mismatch.
5. Resolve the configured Done state by exact state name before any mutation. If `configured Done state` is missing or unresolved, stop and ask for configuration.
6. Read ticket description, acceptance criteria, explicit test expectations, generated planning blocks, PR comments, deployment comments, and linked implementation context.

Use the selected ticket adapter only. Do not use MCPs, Docker containers, or direct database access for ticket delivery unless the selected adapter explicitly requires it.

### 2. Scope QA From The Ticket

Build a scoped QA checklist from the ticket only. Include categories only when they are relevant to the delivered change:

- navigation/rendering: page, route, component, and state render correctly
- user workflow: the intended user action can be completed end to end
- API/backend effect: changed behavior reaches the deployed backend when the feature depends on data, services, persistence, jobs, or integrations
- state verification: created, changed, removed, or computed state is observable from an independent source, not only the initiating UI
- validation and boundaries: changed business rules include valid, invalid, and boundary inputs
- error handling: expected failures show correct UI/API errors and do not corrupt state
- environment correctness: browser and API calls target the configured QA service URLs, not localhost, mocks, stale DEV endpoints, or accidental same-origin fallbacks
- evidence integrity: screenshots, traces, logs, API summaries, and reports are checked for blank captures, console errors, failed network calls, wrong environment, stale data, or other contradictions
- accessibility checks when forms, navigation, labels, focus, keyboard flow, or semantics changed
- responsive checks when layout or viewport behavior changed

If the ticket's test expectations are weak, complete them in the QA result comment by listing the concrete scenarios you created and executed. Do not broaden into unrelated regression testing unless the ticket explicitly asks for it. If an acceptance criterion cannot be converted into an observable oracle, classify the QA result as blocked or `FAIL`; do not pass by assumption.

Use these QA result classifications:

- `PASS`: every required ticket-scoped assertion passed and every acceptance criterion is proven.
- `PASS WITH GAPS`: the deployed artifact appears usable but a non-blocking evidence weakness, warning, or assumption remains; record the gap and keep the ticket in QA until the gap is resolved or explicitly accepted as non-blocking in the ticket.
- `FAIL`: a required assertion failed, a required oracle is missing, evidence is contradictory, the wrong artifact/environment was tested, or a product defect was found.

Only `PASS` can move the ticket to `configured Done state`.

Apply this general QA quality bar before executing tests:

- Define the test oracle: what observable behavior proves the ticket works, what observable behavior proves it is broken, and which source establishes that expectation.
- Build an acceptance-to-assertion map before testing. Every acceptance criterion must list the scenario category, assertion, tool, expected observable result, and evidence location.
- Translate acceptance criteria into explicit assertions, not just navigation steps or screenshots. A passing test must check status, content, state, side effects, errors, visual state, or data changes as applicable.
- Treat screenshots, traces, logs, and HTTP 200 smoke checks as supporting evidence only. They cannot prove acceptance unless tied to executable assertions.
- Cover the highest-risk boundary and negative cases implied by the change, even when the ticket only describes the happy path. Keep the scope ticket-specific.
- Verify the delivered environment, artifact, commit, or deployment being tested so a pass cannot accidentally apply to the wrong build.
- Include lightweight performance observations for ticket-relevant paths. Record response time, browser timing, or API latency when the tool exposes it. Treat obvious major regressions as QA failures when the ticket is performance-sensitive or the latency breaks user-observable acceptance criteria; otherwise record them as warnings.
- Treat evidence as data to validate, not decoration. Screenshots, logs, traces, and reports must be checked for contradictions such as blank captures, wrong environment, console errors, failed network calls, stale data, or misleading render artifacts.
- For deployed multi-app topologies, verify configured cross-service browser calls use the intended configured service URL from the deployment configuration rather than an accidental same-origin fallback such as `/api/*` on the web app.
- Record any assumptions used to fill gaps in weak requirements. If an assumption materially changes pass/fail meaning, classify the result as blocked or ask for clarification instead of passing by guesswork.
- Prefer automated assertions for repeatable facts and use manual or visual evidence only where automation cannot express the expected behavior reliably.

### 3. Select Tools

Inspect the repo before choosing tools:

- E2E configs, package manifests, lockfiles, test folders, CI workflows, browser-test artifacts
- API specs, OpenAPI/Swagger files, Postman collections, k6 scripts, REST Assured or language-native integration tests
- Existing helper APIs, fixtures, auth setup, seeded users, environment variable conventions

Use an established tool when the repo clearly already has one. For this repository's committed QA E2E suite, run the configured E2E tool remotely through repository workflow against deployed QA URLs; do not start local web servers for QA acceptance. Local configured E2E tool execution is only allowed after 2 failed deploy-fix attempts for a deployment-related blocker that prevents the configured remote QA workflow from running or completing. The local fallback must use `npm run test:docker` from `tests/SDDTemplate.E2ETests`, target deployed QA URLs with `E2E_SITE_URL` and `E2E_API_URL`, and never target localhost.

For any deployed browser E2E failure, the configured browser diagnostic or E2E tool is the first diagnostic source before source-code changes. Reproduce the failing user flow against the real QA URL, inspect console, network, websocket, DOM readiness, screenshots, and trace/video evidence, and classify the failure as product defect, E2E harness issue, deployment/environment issue, or workflow gate gap. Do not change app code to add E2E-only JavaScript, hidden hooks, test ids, bypasses, timing shims, or configured E2E tool-specific behavior. If the failure is a harness issue, update only the E2E tests, evidence capture, or workflow. If the failure is a real product defect, route to implementation and require a product-valid fix.

Tool choice is secondary to the evidence contract. The configured E2E tool, API tests, Postman/Newman, k6, repo-native integration tests, or manual browser evidence are acceptable only when the resulting QA record proves the same ticket-scoped assertions against the deployed QA artifact.

If no tool is configured, or several valid technology-dependent choices exist, ask the user before proceeding. Present concrete choices with a recommendation:

- Website: configured E2E tool for cross-browser E2E, traces, screenshots, and web-first assertions; Cypress when already used or team-preferred; Selenium when existing infrastructure depends on it.
- API: existing repo-native integration tests when configured; Postman/Newman when collections exist or tool-neutral API checks are preferred; k6 for performance/load-oriented QA; REST Assured or another language-native API test tool when the repo already uses that stack.

In non-interactive contexts, stop with `tool choice required` instead of guessing.

### 4. Execute QA

Prefer repeatable automated checks. Use browser automation for websites and request-level checks for APIs.

For this repository, execute QA in this order:

1. Verify the QA deployment target metadata and deployed QA URLs.
2. Push the selected-provider QA trigger branch from current `dev` using the branch pattern declared by the selected deployment adapter.
3. Verify repository workflow created the selected-provider E2E run declared by the selected deployment adapter.
4. Use the selected repository workflow evidence as the normal QA execution result.
5. If a deployment-related blocker prevents that remote run from starting or completing, attempt to fix the deploy/remote QA path up to `agentOptimization.maxToolRetries` from `.codex/delivery-policy.json`, currently `2`.
6. Only after those 2 deploy-fix attempts fail, run local fallback with `npm run test:docker` against `E2E_SITE_URL` and `E2E_API_URL`.

The QA summary for any local fallback must include the deployment blocker, both failed deploy-fix attempts, the local fallback command, tested QA URLs, and evidence.

For website E2E:

- Prefer user-visible locators, accessible names, roles, and stable test ids over brittle CSS/XPath selectors.
- Keep tests independent and able to run alone.
- Use explicit assertions that reflect user-observable behavior.
- Capture screenshots or traces for meaningful proof, especially failures and completed critical paths.
- For visually blank or intentionally empty pages, assert the computed `html`/`body` background color, body dimensions, visible text, page title, and screenshot pixel/background result so transparent or tool-rendered black captures are not accepted as valid visual evidence without an explicit note.
- Check responsive behavior when the ticket changes layout or UI flow.
- Check accessibility basics when forms, navigation, labels, focus, or keyboard flows are involved.

For API E2E:

- Assert status codes, response shape, key fields, error bodies, and side effects implied by the ticket.
- Include valid, invalid, missing-field, boundary, unauthorized, and not-found cases only when relevant to the ticket.
- Redact secrets and sensitive request/response content from logs and comments.

If a failure is clearly product behavior, report it as QA failure. If a failure is tooling, environment, missing credentials, missing test data, or unreachable QA infrastructure, classify it separately and do not move the ticket to Done.

### 5. Test And Evidence Retention

Classify generated tests before deciding where to save them:

- Reusable regression tests belong in the repository's normal test structure. Create or update them during QA when existing coverage cannot prove acceptance, then route them through the normal reviewed follow-up path unless the configured QA workflow rule explicitly allows committing them in the QA workflow.
- One-off exploratory QA scripts, ad hoc generated tests, screenshots, traces, logs, and reports belong in the QA evidence bundle.
- Never stage or commit `artifacts/qa/**`; this path is for ignored run evidence only.
- During QA, do not promote one-off generated scripts directly into committed regression tests. If the exploratory check should become permanent coverage, create a scoped implementation or follow-up ticket so it receives normal review and PR validation.

Collect evidence in a stable per-run local folder:

```text
artifacts/qa/{ticketKey}/{runId}/
├─ qa-summary.md
├─ test-plan.md
├─ results/
│  ├─ junit.xml
│  ├─ report.html
│  └─ api-results.json
├─ screenshots/
├─ traces/
├─ logs/
└─ generated-tests/
```

Use a deterministic `runId` such as UTC `yyyyMMdd-HHmmss` plus a short commit SHA when available.

Useful evidence includes:

- screenshots for UI paths
- computed visual-state JSON for blank/empty pages, including background color and console errors
- a screenshot note or normalized screenshot when a capture tool renders a transparent page differently than a normal browser viewport
- configured browser automation traces or videos when available
- API request/response summaries with sensitive data removed
- test logs
- HTML, JSON, JUnit, or CLI reports
- console or network error summaries when relevant
- generated one-off QA scripts that explain how the evidence was produced

Create `qa-summary.md` with the result, tested URLs, selected tools, commit/artifact, scenario categories, acceptance-to-assertion map, evidence inventory, gaps, assumptions, and failure classification. Create `test-plan.md` with the derived checklist, especially when the ticket's original test expectations were weak.

Prefer durable links in ticket comments. Use this evidence publication order:

1. Commit reusable tests to the repo only when the configured QA workflow rule explicitly allows it; otherwise preserve the generated test changes as QA evidence and create or route a reviewed follow-up implementation workflow for permanent regression coverage.
2. When the selected repository E2E job has already run the committed suite, verify the Nexus bundle at `app/{commitSha}/qa-e2e-evidence.zip` and prefer reusing it as supporting evidence instead of rerunning the same test without cause. Also verify any QA observability evidence required by the selected deployment adapter.
3. Save all run evidence locally under `artifacts/qa/{ticketKey}/{runId}/`.
4. Zip the run folder as `qa-evidence.zip`.
5. Upload `qa-evidence.zip` to Nexus when Nexus config is available, using a path like:

```text
qa/{ticketKey}/{runId}/qa-evidence.zip
```

6. Add the Nexus evidence URL to the ticket comment.
7. If Nexus is unavailable but ticket provider attachments are configured and safe, attach evidence to ticket provider.
8. If neither Nexus nor ticket provider attachments are available, include local evidence paths in the ticket comment and clearly label them as local-only fallback evidence.
9. Use `UpdateReleaseManifest` after QA passes, adding source RC version, QA evidence URL, QA result, QA timestamp, tested URLs, and the E2E scenario summary while preserving existing artifact, checksum, PR, ticket, DEV, and QA deployment fields.
10. Use `CreateArtifactPointer` to create `artifact-pointer.json` for the approved RC, then upload the pointer to `app/qa-approved/latest.json` and `app/rc/{sourceRcVersion}/artifact-pointer.json`; also upload the updated release manifest to `app/rc/{sourceRcVersion}/release.json`. These version paths are metadata aliases only; do not duplicate ZIP files there.

Do not move a ticket to `configured Done state` until the evidence link or fallback evidence path has been written to ticket provider. If evidence upload fails after tests pass, comment the upload failure, leave the ticket in QA, and report the blocking evidence publication issue.

Do not publish secrets, cookies, authorization headers, raw tokens, private credentials, or sensitive payloads in evidence. Redact or discard unsafe evidence before zipping or commenting.

### 6. QA Release Candidate Marker

Before moving a ticket to `configured Done state`, establish a release-candidate marker for the exact tested artifact commit:

1. Resolve the tested commit SHA from the QA deployment comment, PR metadata, Nexus artifact path, or user input.
2. Verify the tested commit's `release.json.ticketKey` matches the locked/resolved ticket key before deriving or pushing an RC tag.
3. Resolve the source RC version from user input, an existing annotated tag on that commit, or deterministic auto-increment. Use format `vMAJOR.MINOR.PATCH-rc.N`.
4. If no RC version is supplied and no matching tag exists, derive the next RC:
   - find the latest final SemVer tag `vMAJOR.MINOR.PATCH`,
   - default to the next patch version for new QA candidates,
   - if RC tags already exist for that version, use the next `rc.N`,
   - if the ticket or release notes specify a target final version, use that version instead of next patch.
   If version derivation is ambiguous, stop after recording QA evidence and ask for the RC version; do not move the ticket to Done.
5. Verify the RC tag is annotated and points to the tested commit. If the tag is missing, create it on the tested commit only after every QA scenario passes and evidence is published.
6. Push the RC tag only after the QA result comment is ready and the tag target has been verified.
7. Include the source RC version in the E2E QA ticket comment.
8. Update the Nexus release manifest so `release.json` records `artifact commit -> source RC version -> pending final PROD version`.
9. Upload human-readable Nexus aliases for the QA-approved artifact: `app/qa-approved/latest.json`, `app/rc/{sourceRcVersion}/artifact-pointer.json`, and `app/rc/{sourceRcVersion}/release.json`. Each pointer must name the source RC version, artifact commit SHA, canonical `app/{commitSha}/` path, release manifest path, primary ticket, included ticket list, and creation timestamp.

The RC tag is the human release-candidate identifier for the QA-approved artifact set. It must not replace the immutable Nexus identity under `app/{commitSha}/` from `deployable-apps.json` and each per-app ZIP/checksum pair.

### 7. Git And Hook Policy

Respect the repo's hooks when QA creates files:

- Before writing evidence, verify `artifacts/qa/**` or a broader `artifacts/` rule is ignored by Git. If it is not ignored, stop and route to workflow maintenance before generating screenshots, traces, logs, reports, or ZIP evidence.
- `gitleaks protect --staged --redact` scans staged files. Keep raw QA evidence ignored under `artifacts/qa/**` and do not stage it.
- The commit message hook requires messages to start with a ticket key, an OpenSpec id, or `[SDD]`.
- Commit reusable ticket-specific tests with the ticket key only when the configured QA workflow rule explicitly allows committing them in the QA workflow, for example:

```text
E2EPROJECT-123: add E2E regression tests
```

- Use `[SDD]` only for repo workflow or QA platform maintenance, for example:

```text
[SDD] Add QA automation baseline
```

- One-off generated tests stay in `artifacts/qa/{ticketKey}/{runId}/generated-tests/` and are uploaded as evidence, not committed.
- Reusable tests must reference secrets through environment variables or test configuration placeholders. Never hardcode real credentials, tokens, cookies, connection strings, or private payloads.
- If reusable tests require new repo config, stage only intentional source/config files and leave screenshots, logs, reports, traces, videos, and ZIP evidence untracked.

### 8. Ticket Provider Result And QA Branch Cleanup

Before commenting, read existing comments when the API allows it. Use this stable marker:

```text
IA generated E2E QA: {ticketKey}
```

Do not duplicate a QA result comment with the same marker and same tested commit/artifact unless the user explicitly asks for a fresh run.

Keep the marker as the first line by itself. Use `RenderTicketComment -Type E2EQA` with the resolved QA data, scenario summary, evidence links, and notes to format the readable Markdown body.

The comment must include:

- ticket key and current state
- tested QA URL and API base URL when applicable
- commit, PR, artifact, or deployment reference when available
- source RC version
- RC tag URL or tag name and the verified tag target commit
- release lineage: `artifact commit -> source RC version -> pending final PROD version`
- selected test tool and why
- acceptance criteria covered
- scenario categories used
- executable assertions executed
- scenarios executed
- pass/fail result
- gaps, assumptions, or blocked criteria
- Nexus evidence URL, ticket provider attachment link, or local fallback evidence path
- report links, screenshots, traces, or logs included in the evidence bundle
- defects, blockers, or environment/tooling issues found
- completed test expectations when the original ticket expectations were weak

Move the ticket to `configured Done state` only after:

- the ticket was in `configured QA state` or the user explicitly overrode the state check,
- the QA result is `PASS`, not `PASS WITH GAPS`,
- every required ticket-scoped QA scenario passed,
- every acceptance criterion is mapped to at least one explicit assertion or is removed from scope by explicit ticket evidence,
- the QA result includes the test oracle, explicit assertions, risk-based negative or boundary checks where applicable, and any assumptions used to fill weak requirements,
- the QA result includes API/backend-effect, state-verification, validation/boundary, error-handling, and environment-correctness checks whenever the delivered change makes those categories relevant,
- evidence was validated against the assertions and does not contradict the pass result,
- the source RC version was recorded and any RC tag used for PROD promotion points to the tested commit,
- evidence was collected and published to Nexus, attached to ticket provider, or documented as a local-only fallback,
- the QA result comment was added or confirmed idempotently present.

If any required QA scenario fails, add the result comment and leave the ticket in `configured QA state`.

After the verified E2E QA comment and Done-state mutation succeed, delete the selected-provider QA trigger branch through the repository adapter. Use the branch pattern declared by the selected deployment adapter and verify the remote ref is gone.

Then verify the remote ref is gone. Do not delete the branch before Nexus evidence exists, release metadata is updated, the RC tag is created or verified, and ticket provider is Done.

Before reporting final QA handoff, append the `quality-test-e2e` telemetry row, read workflow telemetry, render `RenderTicketComment -Type WorkflowTiming`, and create or patch the `IA generated workflow timing: {ticketKey}` ticket comment. If the timing marker already exists for the ticket, patch that comment instead of creating a duplicate.

If the ticket is already in Done or has QA evidence but only a noncanonical QA marker is present, such as `IA generated QA evidence: {ticketKey}`, do not skip finalization. Repair or add the canonical `IA generated E2E QA: {ticketKey}` marker, verify the workflow timing marker, and continue to the OpenSpec archival handoff.

### 9. OpenSpec Archival Handoff

After every required QA scenario passes, evidence is published, the E2E QA comment is present, and the ticket has been moved to `configured Done state`, check whether the completed ticket is linked to an active OpenSpec change.

Run all OpenSpec CLI checks in this section with process environment `OPENSPEC_TELEMETRY=0`, then run `openspec list --json` and `openspec status --change "<change>" --json` before invoking `$dev-flow-archive-change`.

Resolve the OpenSpec change id from, in order:

- explicit user input
- ticket description or generated planning blocks
- repository PR title, body, labels, branch name, or comments
- local `openspec/changes/*` entries that clearly reference the ticket key

If exactly one active OpenSpec change is linked to the completed ticket, invoke `$dev-flow-archive-change` for that change. Do not reimplement archive movement or spec sync inside this skill.

If multiple active OpenSpec changes match, or no clear linked change can be resolved, do not guess. Add the unresolved archival handoff to the completion summary and leave the OpenSpec change active until the user selects the change.

If `$dev-flow-archive-change` reports incomplete artifacts, incomplete tasks, spec sync warnings, or needs user confirmation, stop the archival handoff and report the exact blocker. Do not undo the QA pass or move the ticket back from Done.

Do not report the QA workflow as fully complete while exactly one linked active OpenSpec change remains unarchived. The final handoff must include either `OpenSpec archived: <archive path>` or `OpenSpec archive blocker: <reason>`.

### 10. Durable Learning Capture Gate

Before final handoff, apply `.codex/memory/retrieval-policy.md#update-process` to every blocker, environment repair, QA harness fix, deployment finding, and recurring workflow lesson discovered during the QA run.

- If the finding is authoritative project or deployment knowledge, update the matching `docs/` file.
- If the finding changes enforceable workflow behavior, update `.codex/skills/_shared/delivery-contract.md` plus affected skills and tests.
- If the finding is reusable but non-authoritative workflow knowledge, update the targeted `.codex/memory/` file.
- If nothing reusable was discovered, explicitly record `Memory updated: none`.

ticket comments, QA evidence, and final chat summaries do not satisfy this gate by themselves. Do not report the QA run as complete until the final handoff can state `Memory updated: <files>` or `Memory updated: none`.

## Output

Report the ticket, QA environment, scenarios tested, validation assertions, evidence path or URL, RC version, ticket status/comment updates, OpenSpec archive path or explicit archive blocker, `Memory updated: <files>` or `Memory updated: none`, and any blockers or residual risk.

## Failure Rules

- Missing selected ticket adapter config: stop before ticket-provider reads or mutations.
- Missing or placeholder `configured Done state`: stop and ask for configuration.
- Ticket not in `configured QA state`: stop unless the user explicitly overrides.
- Ticket context lock mismatch: stop before testing, evidence publication, RC tagging, or state movement.
- Tool choice is ambiguous: ask the user before technology-dependent tests.
- Non-interactive ambiguous tool choice: stop with `tool choice required`.
- QA evidence path is not ignored by Git: stop before generating evidence.
- Local E2E QA before 2 failed deploy-fix attempts: stop and trigger or repair the configured remote QA workflow first.
- Product E2E test failure: classify as QA failure; do not switch to local fallback.
- Local fallback targeting localhost or missing `E2E_SITE_URL` / `E2E_API_URL`: fail closed and do not move the ticket to Done.
- RC version cannot be supplied or derived: comment available evidence, leave ticket in QA, and ask for the RC version.
- Missing acceptance-to-assertion mapping: comment the gap and leave the ticket in QA.
- Screenshot-only, trace-only, log-only, page-load-only, or smoke-only evidence: classify as `PASS WITH GAPS` or `FAIL` and do not move the ticket to Done.
- Data-changing ticket without independent state/API verification when such verification is possible: classify as `PASS WITH GAPS` or `FAIL` and do not move the ticket to Done.
- Validation-changing ticket without relevant invalid or boundary cases: classify as `PASS WITH GAPS` or `FAIL` and do not move the ticket to Done.
- Wrong artifact, wrong QA URL, localhost, stale DEV endpoint, mock endpoint, or accidental same-origin fallback: fail closed and do not move the ticket to Done.
- QA test failure: comment evidence and do not move the ticket to Done.
- Product defect after QA: invoke `dev-flow-file-qa-bug`; do not fix product code inside this skill unless the user changes the task.
- E2E failure without configured browser diagnostic tool or configured Browser/E2E diagnostic classification: stop before app-code changes and record the missing classification.
- Proposed app-code change that exists only for configured E2E tool/E2E: stop; update the E2E harness or workflow instead.
- Missing evidence upload support: include local evidence paths or links in the ticket comment.
- Secrets in logs or screenshots: redact or discard the evidence before commenting.

## Practice References

When creating or repairing tool-specific tests, prefer official documentation and current repo conventions over memory:

- selected E2E adapter documentation and best practices
- selected browser or API testing tool documentation
- selected non-browser API testing tool documentation when API QA is required
