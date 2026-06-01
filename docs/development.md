# Development

This repository uses a .NET solution with a Blazor application and xUnit tests.

## Project Shape

- Solution: `SDDTemplate.slnx`
- App: `src/SDDTemplate.Site`
- Tests: `tests/SDDTemplate.Site.Tests`
- Delivery helpers: `tools/SDDTemplate.DeliveryTools`
- OpenSpec changes: `openspec/changes`
- Repo-local Codex workflows: `.codex/skills`

## Technology Stack And Tool Set

The application stack is .NET 10 with ASP.NET Core and Blazor. The site project targets `net10.0` with `Microsoft.NET.Sdk.Web`; tests target `net10.0` with xUnit, `Microsoft.AspNetCore.Mvc.Testing`, `Microsoft.NET.Test.Sdk`, and coverlet coverage collection.

Use official-first research when changing platform behavior, generated templates, tests, or workflow guidance. Prefer Microsoft Learn for .NET, ASP.NET Core, Blazor, Azure App Service, and architecture guidance; Playwright docs for browser automation; Gitea, Sonatype Nexus, Prometheus, and Grafana official docs for their tools. Community sources are allowed only when clearly labeled and not used to override repo policy.

QA automation starts with repo-native tests and PR validation. Browser-visible Blazor behavior should use the Browser plugin and Playwright-style user-visible assertions when configured; one-off evidence belongs under ignored `artifacts/qa/**`, while reusable regression tests belong in the normal test tree through an implementation workflow.

Clean-code and architecture guidance should fit this repository's current size: keep changes small, preserve separation between delivery tooling and application code, avoid broad abstractions until they remove real complexity, and prefer observable behavior tests over implementation-detail tests.

## Common Commands

Build:

```powershell
dotnet build .\SDDTemplate.slnx
```

Run tests:

```powershell
dotnet test .\SDDTemplate.slnx
```

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

Before the first ticket starts, verify the repository tool set and tech stack are configured in `docs/architecture.md`, this file, `docs/deployment.md`, `openspec/config.yaml`, and `.codex/tool-recommendations.example.json`. The ticket-start flow must run or inspect `AuditRecommendedTools` and stop before creating branches, Plane generated blocks, ticket locks, or OpenSpec proposals when stack context is missing or reports `stack-context.*` drift. Use `configure-dev-environment` to complete the docs, OpenSpec context, and recommendation catalog first.

Implementation is complete only when OpenSpec tasks are complete, PR review feedback tasks are complete, behavior is tested, quality gates pass or are handed off to CI as the authority, and a Gitea PR has review-agent coverage.

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

## Agent Workflow Evals

Agent behavior is evaluated separately from product behavior. The default workflow fixtures live in `.codex/agent-evals/workflow-cases.json` and cover ticket start, implementation, PR review, QA promotion, E2E QA, PROD promotion, and rollback.

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
