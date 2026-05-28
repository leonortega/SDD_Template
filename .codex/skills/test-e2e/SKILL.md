---
name: test-e2e
description: Run post-deploy E2E QA for Plane tickets that are already in QA, including "test qa automation", "test qa deploy", "run QA tests", "complete QA", "E2E test a QA ticket", "validate QA and move to Done", and "run ticket-specific website/API QA". Use when Codex needs to inspect ticket expectations, choose or ask for the right website/API test tool, execute scoped QA checks, collect evidence, comment results on Plane, and move the ticket to the configured Done state only when all checks pass.
---

# Test E2E

## Overview

Use this skill after deployment validation has already moved a Plane ticket to QA. Act as a QA expert: test only the website and API behavior implied by the ticket, record evidence, and move the ticket to the configured final state only after every required QA check passes.

This skill is technology-agnostic. Inspect the repository first. Use an established E2E/API test tool when one is already configured; otherwise ask the user to choose before creating or running technology-dependent tests.

Non-interactive context means the run has no available user-response channel, such as cron automation, CI, detached automation, or an explicit "do not ask" instruction.

Read `.codex/skills/_shared/delivery-contract.md` before QA state changes. Use `.codex/skills/_shared/scripts/delivery_tools.ps1 -Mode CheckGitIgnored` before writing evidence, `-Mode NextRcVersion` when deriving RC tags, and `-Mode ValidateReleaseManifest` after updating `release.json`. Enforce the ticket context lock before testing, tagging, publishing evidence, or moving state.

## Configuration

Read `.codex/client-tools.local.json` first. Fall back to `.codex/client-tools.example.json` only for structure and default names, then apply environment variable overrides when present.

Required or defaulted values:

- `plane.baseUrl`, `plane.apiToken`, `plane.workspaceSlug`, `plane.projectIdentifier`
- `plane.qaState`, default `QA`
- `plane.doneState`, default `Done` only when explicitly configured or confirmed
- `gitea.baseUrl`, `gitea.apiToken`, `gitea.owner`, `gitea.repo` when PR/deploy context is needed
- `nexus.baseUrl`, `nexus.username`, `nexus.password`, `nexus.repository` when publishing QA evidence bundles
- source RC version for release candidates, supplied by the user or resolved from an existing annotated tag on the tested commit, using format `vMAJOR.MINOR.PATCH-rc.N`

Optional environment variables override local JSON when present:

- `PLANE_QA_STATE`
- `PLANE_DONE_STATE`
- `GITEA_BASE_URL`
- `GITEA_API_TOKEN`
- `GITEA_OWNER`
- `GITEA_REPO`

Never print, commit, paste into tickets, or write real API tokens, cookies, session values, Nexus credentials, Azure credentials, or other secrets.

## Workflow

### 1. Resolve Context

1. Resolve the Plane ticket from user input, current branch, Gitea PR metadata, deployment comments, commit messages, or a ticket key.
2. Read `.codex/delivery-context.local.json` when present and verify the resolved Plane ticket, QA deployment commit, artifact commit, and evidence path match the locked `ticketKey`. If any value belongs to another ticket, stop before testing or writing evidence.
3. Fetch the Plane ticket with expanded state/project data.
4. Verify the ticket is in `plane.qaState`. If it is not, stop unless the user explicitly asks to test despite the state mismatch.
5. Resolve the project UUID and the configured `plane.doneState` by exact state name before any mutation. If `plane.doneState` is missing or unresolved, stop and ask for configuration.
6. Read ticket description, acceptance criteria, explicit test expectations, generated planning blocks, PR comments, deployment comments, and linked implementation context.

Use Plane API only. Do not use Plane MCP, Docker containers, or direct database access for Plane.

### 2. Scope QA From The Ticket

Build a scoped QA checklist from the ticket only. Include categories only when they are relevant to the delivered change:

- website happy path
- website edge and negative cases
- API happy path
- API edge and negative cases
- accessibility checks
- responsive checks
- deployment/environment checks tied to the ticket

If the ticket's test expectations are weak, complete them in the QA result comment by listing the concrete scenarios you created and executed. Do not broaden into unrelated regression testing unless the ticket explicitly asks for it.

Apply this general QA quality bar before executing tests:

- Define the test oracle: what observable behavior proves the ticket works, what observable behavior proves it is broken, and which source establishes that expectation.
- Translate acceptance criteria into explicit assertions, not just navigation steps or screenshots. A passing test must check status, content, state, side effects, errors, visual state, or data changes as applicable.
- Cover the highest-risk boundary and negative cases implied by the change, even when the ticket only describes the happy path. Keep the scope ticket-specific.
- Verify the delivered environment, artifact, commit, or deployment being tested so a pass cannot accidentally apply to the wrong build.
- Include lightweight performance observations for ticket-relevant paths. Record response time, browser timing, or API latency when the tool exposes it. Treat obvious major regressions as QA failures when the ticket is performance-sensitive or the latency breaks user-observable acceptance criteria; otherwise record them as warnings.
- Treat evidence as data to validate, not decoration. Screenshots, logs, traces, and reports must be checked for contradictions such as blank captures, wrong environment, console errors, failed network calls, stale data, or misleading render artifacts.
- Record any assumptions used to fill gaps in weak requirements. If an assumption materially changes pass/fail meaning, classify the result as blocked or ask for clarification instead of passing by guesswork.
- Prefer automated assertions for repeatable facts and use manual or visual evidence only where automation cannot express the expected behavior reliably.

### 3. Select Tools

Inspect the repo before choosing tools:

- E2E configs, package manifests, lockfiles, test folders, CI workflows, browser-test artifacts
- API specs, OpenAPI/Swagger files, Postman collections, k6 scripts, REST Assured or language-native integration tests
- Existing helper APIs, fixtures, auth setup, seeded users, environment variable conventions

Use an established tool when the repo clearly already has one.

If no tool is configured, or several valid technology-dependent choices exist, ask the user before proceeding. Present concrete choices with a recommendation:

- Website: Playwright recommended for cross-browser E2E, traces, screenshots, and web-first assertions; Cypress when already used or team-preferred; Selenium when existing infrastructure depends on it.
- API: existing repo-native integration tests when configured; Postman/Newman when collections exist or tool-neutral API checks are preferred; k6 for performance/load-oriented QA; REST Assured or another language-native API test tool when the repo already uses that stack.

In non-interactive contexts, stop with `tool choice required` instead of guessing.

### 4. Execute QA

Prefer repeatable automated checks. Use browser automation for websites and request-level checks for APIs.

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

- Reusable regression tests belong in the repository's normal test structure and should be committed through a follow-up implementation workflow when appropriate.
- One-off exploratory QA scripts, ad hoc generated tests, screenshots, traces, logs, and reports belong in the QA evidence bundle.
- Never stage or commit `artifacts/qa/**`; this path is for ignored run evidence only.

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
- Playwright/Cypress/Selenium traces or videos when available
- API request/response summaries with sensitive data removed
- test logs
- HTML, JSON, JUnit, or CLI reports
- console or network error summaries when relevant
- generated one-off QA scripts that explain how the evidence was produced

Create `qa-summary.md` with the result, tested URLs, selected tools, commit/artifact, scenario list, evidence inventory, and failure classification. Create `test-plan.md` with the derived checklist, especially when the ticket's original test expectations were weak.

Prefer durable links in Plane comments. Use this evidence publication order:

1. Commit reusable tests to the repo only when they are intended to become part of regression coverage.
2. Save all run evidence locally under `artifacts/qa/{ticketKey}/{runId}/`.
3. Zip the run folder as `qa-evidence.zip`.
4. Upload `qa-evidence.zip` to Nexus when Nexus config is available, using a path like:

```text
qa/{ticketKey}/{runId}/qa-evidence.zip
```

5. Add the Nexus evidence URL to the Plane comment.
6. If Nexus is unavailable but Plane attachments are configured and safe, attach evidence to Plane.
7. If neither Nexus nor Plane attachments are available, include local evidence paths in the Plane comment and clearly label them as local-only fallback evidence.
8. Update `app/{commitSha}/release.json` in Nexus after QA passes, adding source RC version, QA evidence URL, QA result, QA timestamp, tested URLs, and the E2E scenario summary. Preserve existing artifact, checksum, PR, ticket, DEV, and QA deployment fields.

Do not move a ticket to `plane.doneState` until the evidence link or fallback evidence path has been written to Plane. If evidence upload fails after tests pass, comment the upload failure, leave the ticket in QA, and report the blocking evidence publication issue.

Do not publish secrets, cookies, authorization headers, raw tokens, private credentials, or sensitive payloads in evidence. Redact or discard unsafe evidence before zipping or commenting.

### 6. QA Release Candidate Marker

Before moving a ticket to `plane.doneState`, establish a release-candidate marker for the exact tested artifact commit:

1. Resolve the tested commit SHA from the QA deployment comment, PR metadata, Nexus artifact path, or user input.
2. Verify the tested commit's `release.json.planeTicketKey` matches the locked/resolved ticket key before deriving or pushing an RC tag.
3. Resolve the source RC version from user input, an existing annotated tag on that commit, or deterministic auto-increment. Use format `vMAJOR.MINOR.PATCH-rc.N`.
4. If no RC version is supplied and no matching tag exists, derive the next RC:
   - find the latest final SemVer tag `vMAJOR.MINOR.PATCH`,
   - default to the next patch version for new QA candidates,
   - if RC tags already exist for that version, use the next `rc.N`,
   - if the ticket or release notes specify a target final version, use that version instead of next patch.
   If version derivation is ambiguous, stop after recording QA evidence and ask for the RC version; do not move the ticket to Done.
5. Verify the RC tag is annotated and points to the tested commit. If the tag is missing, create it on the tested commit only after every QA scenario passes and evidence is published.
6. Push the RC tag only after the QA result comment is ready and the tag target has been verified.
7. Include the source RC version in the E2E QA Plane comment.
8. Update the Nexus release manifest so `release.json` records `artifact commit -> source RC version -> pending final PROD version`.

The RC tag is the human release-candidate identifier for the QA-approved artifact. It must not replace the immutable Nexus identity `app/{commitSha}/app.zip`.

### 7. Git And Hook Policy

Respect the repo's hooks when QA creates files:

- Before writing evidence, verify `artifacts/qa/**` or a broader `artifacts/` rule is ignored by Git. If it is not ignored, stop and route to workflow maintenance before generating screenshots, traces, logs, reports, or ZIP evidence.
- `gitleaks protect --staged --redact` scans staged files. Keep raw QA evidence ignored under `artifacts/qa/**` and do not stage it.
- The commit message hook requires messages to start with a Plane ticket key, an OpenSpec id, or `[SDD]`.
- Commit reusable ticket-specific tests with the ticket key when available, for example:

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

### 8. Plane Result

Before commenting, read existing comments when the API allows it. Use this stable marker:

```text
IA generated E2E QA: {ticketKey}
```

Do not duplicate a QA result comment with the same marker and same tested commit/artifact unless the user explicitly asks for a fresh run.

The comment must include:

- ticket key and current state
- tested QA URL and API base URL when applicable
- commit, PR, artifact, or deployment reference when available
- source RC version
- RC tag URL or tag name and the verified tag target commit
- release lineage: `artifact commit -> source RC version -> pending final PROD version`
- selected test tool and why
- scenarios executed
- pass/fail result
- Nexus evidence URL, Plane attachment link, or local fallback evidence path
- report links, screenshots, traces, or logs included in the evidence bundle
- defects, blockers, or environment/tooling issues found
- completed test expectations when the original ticket expectations were weak

Move the ticket to `plane.doneState` only after:

- the ticket was in `plane.qaState` or the user explicitly overrode the state check,
- every required ticket-scoped QA scenario passed,
- the QA result includes the test oracle, explicit assertions, risk-based negative or boundary checks where applicable, and any assumptions used to fill weak requirements,
- evidence was validated against the assertions and does not contradict the pass result,
- the source RC version was recorded and any RC tag used for PROD promotion points to the tested commit,
- evidence was collected and published to Nexus, attached to Plane, or documented as a local-only fallback,
- the QA result comment was added or confirmed idempotently present.

If any required QA scenario fails, add the result comment and leave the ticket in `plane.qaState`.

### 9. OpenSpec Archival Handoff

After every required QA scenario passes, evidence is published, the E2E QA comment is present, and the ticket has been moved to `plane.doneState`, check whether the completed ticket is linked to an active OpenSpec change.

Resolve the OpenSpec change id from, in order:

- explicit user input
- Plane ticket description or generated planning blocks
- Gitea PR title, body, labels, branch name, or comments
- local `openspec/changes/*` entries that clearly reference the ticket key

If exactly one active OpenSpec change is linked to the completed ticket, invoke `$openspec-archive-change` for that change. Do not reimplement archive movement or spec sync inside this skill.

If multiple active OpenSpec changes match, or no clear linked change can be resolved, do not guess. Add the unresolved archival handoff to the completion summary and leave the OpenSpec change active until the user selects the change.

If `$openspec-archive-change` reports incomplete artifacts, incomplete tasks, spec sync warnings, or needs user confirmation, stop the archival handoff and report the exact blocker. Do not undo the QA pass or move the Plane ticket back from Done.

## Failure Rules

- Missing Plane API config: stop before Plane reads or mutations.
- Missing or placeholder `plane.doneState`: stop and ask for configuration.
- Ticket not in `plane.qaState`: stop unless the user explicitly overrides.
- Ticket context lock mismatch: stop before testing, evidence publication, RC tagging, or state movement.
- Tool choice is ambiguous: ask the user before technology-dependent tests.
- Non-interactive ambiguous tool choice: stop with `tool choice required`.
- QA evidence path is not ignored by Git: stop before generating evidence.
- RC version cannot be supplied or derived: comment available evidence, leave ticket in QA, and ask for the RC version.
- QA test failure: comment evidence and do not move the ticket to Done.
- Product defect after QA: invoke `file-qa-bug`; do not fix product code inside this skill unless the user changes the task.
- Missing evidence upload support: include local evidence paths or links in the Plane comment.
- Secrets in logs or screenshots: redact or discard the evidence before commenting.

## Practice References

When creating or repairing tool-specific tests, prefer official documentation and current repo conventions over memory:

- Playwright best practices: `https://playwright.dev/docs/best-practices`
- Playwright test agents and skills: `https://playwright.dev/docs/test-agents` and `https://playwright.dev/agent-cli/skills`
- Cypress best practices and AI skills: `https://docs.cypress.io/app/core-concepts/best-practices` and `https://docs.cypress.io/app/tooling/ai-skills`
- Postman/Newman CLI: `https://learning.postman.com/docs/reference/newman-cli/command-line-integration-with-newman`
