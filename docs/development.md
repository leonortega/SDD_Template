# Development

This repository uses a .NET solution with a Blazor application and xUnit tests.

## Project Shape

- Solution: `SDDTemplate.slnx`
- Web app: `src/SDDTemplate.Site`
- REST API: `src/SDDTemplate.Api`
- Data layer: `src/SDDTemplate.Data`
- Tests: `tests/SDDTemplate.Site.Tests`
- Delivery helpers: `tools/SDDTemplate.DeliveryTools`
- OpenSpec changes: `openspec/changes`
- Repo-local Codex workflows: `.codex/skills`

## Technology Stack And Tool Set

The application stack is .NET 10 with ASP.NET Core, Minimal APIs, EF Core, and Blazor. The site and API projects target `net10.0` with `Microsoft.NET.Sdk.Web`; the data project targets `net10.0` with EF Core and owns entities, DbContext, migrations, and database setup. Tests target `net10.0` with xUnit, `Microsoft.AspNetCore.Mvc.Testing`, `Microsoft.NET.Test.Sdk`, and coverlet coverage collection.

Use official-first research when changing platform behavior, generated templates, tests, or workflow guidance. Prefer OpenAI official skill catalogs/docs for Codex skills, Microsoft Learn for .NET, ASP.NET Core, Blazor, Azure App Service, and architecture guidance; Playwright docs for browser automation; Gitea, Sonatype Nexus, Prometheus, and Grafana official docs for their tools. `skills.sh`, `skills`, marketplace pages, and README command examples may be used as repository/path discovery sources, but their install commands must not be executed. Community sources are allowed only when clearly labeled and not used to override repo policy.

QA automation starts with repo-native tests and PR validation. Browser-visible Blazor behavior should use the Browser plugin and Playwright-style user-visible assertions when configured; one-off evidence belongs under ignored `artifacts/qa/**`, while reusable regression tests belong in the normal test tree through an implementation workflow. The reusable deployed-QA browser/API regression suite lives under `tests/SDDTemplate.E2ETests`; it is intentionally aimed at deployed QA apps, not local dev servers, and runs remotely from Gitea Actions through a ticket-specific `qa/{ticketKey}` branch after QA deployment. QA Done requires acceptance criteria proven by executable assertions against the deployed QA artifact. Smoke checks, screenshots, logs, and traces are supporting evidence only; the QA record must map criteria to assertions and cover relevant user workflow, API/backend effect, independent state, validation/boundary, error-handling, environment-correctness, and evidence-integrity scenarios.

Clean-code and architecture guidance should fit this repository's current size: keep changes small, preserve separation between delivery tooling and application code, avoid broad abstractions until they remove real complexity, and prefer observable behavior tests over implementation-detail tests. Blazor web UI changes should preserve accessible, responsive, user-visible behavior. Pages that depend on inline page scripts must either disable enhanced navigation for their entry links or move the behavior into Blazor-managed components so routed navigation and hard refresh behave the same way. ASP.NET Core REST/API endpoint changes, including minimal APIs such as `/health` and `/metrics`, should use clear route shape, validation, safe error responses, and integration tests. Security-sensitive changes should account for secrets, authorization, dependency risk, scanner evidence, and OWASP-aligned review.

When the recommendation audit finds missing skills or guidance for detected tools, frameworks, environments, test frameworks, code standards, security, QA, or architecture, agents must use `project-guidance-discover` first. `project-guidance-discover` builds a `project-guidance-search-plan` from detected signals, checks repo-local workflow sources, researches OpenAI official sources, then official tool repositories/docs and technology-owner sources, then `skills.sh`, `skills`, marketplace, or command-example leads, and finally clearly labeled community sources when no stronger source exists. It shows suggested missing skills and guidance with `sourceKind`, and asks whether the user wants to add additional desired items. Only after that confirmation may `project-guidance-acquire` copy the final confirmed skill items into `.codex/skills/`; non-skill guidance stays in `.codex/tool-recommendations.local.json`. Use `project-guidance-mapper` to decide which repo-local workflow skills, installed expert skills, tools, references, practices, and standards apply to config, ticket start, planning, implementation, review, QA, deploy, rollback, hotfix, and retrospective steps.

## Common Commands

Build:

```powershell
dotnet build .\SDDTemplate.slnx
```

Run tests:

```powershell
dotnet test .\SDDTemplate.slnx
```

Prepare remote QA E2E tests after a ticket reaches QA:

```powershell
git switch -c qa/E2EPROJECT-123 origin/dev
# add or update reusable tests under tests/SDDTemplate.E2ETests
git push origin qa/E2EPROJECT-123
```

The `qa/{ticketKey}` branch workflow runs the committed Playwright suite remotely against `AZURE_QA_SITE_APP_URL` and `AZURE_QA_API_APP_URL`. Local runs are only for test authoring or diagnostics, not the official QA E2E gate. After the remote evidence exists and the QA workflow records Plane Done plus the RC/release metadata, delete the remote `qa/{ticketKey}` branch; it is only a temporary trigger, not the durable audit record.

Verify formatting:

```powershell
dotnet format --verify-no-changes
```

Start local delivery infrastructure:

```powershell
.\infra\up.ps1
```

Stop local delivery infrastructure:

```powershell
.\infra\down.ps1
```

## Implementation Workflow

Feature work starts from a Plane ticket and normally creates an OpenSpec proposal before implementation. Agents should read the Plane ticket, active OpenSpec artifacts, the ticket context lock, relevant code, relevant tests, and quality-gate configuration before editing.

Before the first ticket starts, verify the repository tool set and tech stack are configured in `docs/architecture.md`, this file, `docs/deployment.md`, `openspec/config.yaml`, and the tracked `.codex/tool-recommendations.example.json` template. The ticket-start flow must run or inspect `AuditRecommendedTools` and stop before creating branches, Plane generated blocks, ticket locks, or OpenSpec proposals when stack context is missing or reports `stack-context.*` drift. Use `configure-dev-environment` to complete the docs, OpenSpec context, and recommendation catalog template first. After project guidance discovery is confirmed, ignored `.codex/tool-recommendations.local.json` may store the current project recommendations and `usedInSteps` so `project-guidance-mapper` can reuse the same verified skills and guidance for repeated implementation, review, QA, deployment, rollback, hotfix, and retrospective steps.

Implementation is complete only when OpenSpec tasks are complete, PR review feedback tasks are complete, behavior is tested, quality gates pass or are handed off to CI as the authority, and a Gitea PR has review-agent coverage.

Ticket start now includes a readiness gate before branch, Plane state, ticket-lock, or OpenSpec mutation. Tickets are classified as `ready`, `enrichable`, or `blocked`. Enrichable tickets keep moving only after the managed Plane block records concrete acceptance criteria, affected areas, validation expectations, risks, and definition of done. Blocked tickets stop before mutation when the product or technical intent is still too vague.

OpenSpec `tasks.md` must include a compact Review Workload Forecast for ticketed work. The forecast records estimated changed lines, `400-line budget risk`, whether chained PRs are recommended, whether a decision is needed before apply, the delivery strategy, and suggested work units. High-risk or oversized work must record a split plan or `size:exception` before implementation begins. Work-unit commits keep code, tests, and docs for the same deliverable behavior together.

Delivery depth is risk-adaptive but gates are not optional. Low-risk changes may use compact planning and review summaries. High-risk changes, including auth, persistence, migrations, deployment workflows, secrets, public APIs, `/health`, release manifests, rollback/hotfix, or large diffs, require full workload handling and adversarial review.

PR review feedback has two timed loops owned by the repo-local `pr-review-feedback-loop` skill. The AI review loop runs immediately after PR creation and after every feedback fix; every AI finding becomes a `## PR Review Feedback` task in the active OpenSpec `tasks.md` before the PR is ready for human review. Human PR review happens later and reconnects only when the operator manually resumes the ticket, such as `automatically continue this ticket` or `continue E2EPROJECT-123`. Do not carry this local delivery behavior in external `openspec-*` skills.

Feedback batches use Plane markers `IA generated PR feedback detected: {headSha}:{feedbackBatchId}` and `IA generated PR feedback fixes: {headSha}:{feedbackBatchId}`. The batch id is derived from sorted source ids, so late human comments on the same PR head are processed as a new batch instead of being skipped by an earlier fix. Plane remains `In Review` while late human feedback fixes are applied; ambiguous or conflicting human comments block handoff until clarified.

## Quality Gates

Gitea PR validation is the source of truth. Local hooks and local commands are fast feedback, not a replacement for PR validation.

The default validation surface is:

- restore
- format verification
- release build
- tests with coverage
- coverage threshold, default `80%`
- dependency vulnerability audit
- secret scan
- Trivy filesystem scan for high and critical findings

The `/health` endpoint is part of the deployment contract. It must return HTTP 200 with JSON field `status` equal to `ok` and must not expose secrets, connection strings, tokens, host internals, or detailed exception data.

## Agent Retrospective Quality Lane

Use `.codex/skills/delivery-retrospective-audit` to inspect recent delivery evidence and propose agent or workflow improvements after QA bugs, review misses, CI/tooling blockers, deployment blockers, or repeated process friction.

Retrospectives are read-only by default. Apply durable workflow changes only when the evidence shows a repeated pattern, a high-severity gap, direct drift from `.codex/skills/_shared/delivery-contract.md`, or a missing deterministic check for an already-required rule. The audit must not mutate Plane state, deploy, promote, tag, or create recurring automations unless the user explicitly requests that separate action.

After a successful PROD deployment, `deploy-to-prod` automatically runs `delivery-retrospective-audit` in read-only `post-prod-ticket-release` mode. The audit writes sanitized learning evidence to ignored `.codex/agent-evals/results.local.json` and records a compact Plane marker, but it does not block or undo PROD success. Later retrospectives can use those results to identify repeated findings, eval coverage gaps, and recommended follow-up improvements.

## Agent Workflow Evals

Agent behavior is evaluated separately from product behavior. The default workflow fixtures live in `.codex/agent-evals/workflow-cases.json` and cover ticket start, implementation, PR review, QA promotion, E2E QA, PROD promotion, post-PROD retrospective learning evidence, and rollback.

Use these evals when changing delivery skills, adding new agent roles, changing model routing, or investigating repeated agent failures. Each case checks route selection, tool selection, argument precision, mutation gates, stop conditions, and handoff fields. New agent roles or routing complexity should be backed by eval evidence that the existing workflow struggled or became ambiguous.

Local eval output belongs in ignored `.codex/agent-evals/results.local.json`.

## Skill Contract Audit

Run the shared skill-contract audit after changing delivery skills or during retrospective hardening:

```powershell
.\.codex\skills\_shared\scripts\audit_skill_contracts.ps1
```

The audit checks non-OpenSpec, non-configure skills by default for standard delivery contract sections and core terms such as validation, ticket context, and handoff behavior. Normal process validation must use the default scope and exclude `openspec-*` skills because they are external/vendor skills updated by their upstream owner. Use `-IncludeConfigure` only when configure skills are part of the change; reserve `-IncludeOpenSpec` or `-AllSkills` for explicit external-skill maintenance.

Use `-FailOnFindings` when the audit is part of a hard quality gate.

## Context Findings

Every implementation must finish with a Context Findings Review. Durable findings update the matching file under `docs/` in the same PR. If there are no durable findings, the PR body and Plane handoff comment must state `Docs: no durable context changes`.
