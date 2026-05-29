# Development

This repository uses a .NET solution with a Blazor application and xUnit tests.

## Project Shape

- Solution: `SDDTemplate.slnx`
- App: `src/SDDTemplate.Site`
- Tests: `tests/SDDTemplate.Site.Tests`
- Delivery helpers: `tools/SDDTemplate.DeliveryTools`
- OpenSpec changes: `openspec/changes`
- Repo-local Codex workflows: `.codex/skills`

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

Implementation is complete only when OpenSpec tasks are complete, behavior is tested, quality gates pass or are handed off to CI as the authority, and a Gitea PR has review-agent coverage.

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

The audit checks non-OpenSpec, non-configure skills by default for standard delivery contract sections and core terms such as validation, ticket context, and handoff behavior. Use `-IncludeConfigure`, `-IncludeOpenSpec`, or `-AllSkills` to broaden the scope. Treat failures as review findings: either update the skill or document why that skill intentionally uses a different shape.

Use `-FailOnFindings` when the audit is part of a hard quality gate.

## Context Findings

Every implementation must finish with a Context Findings Review. Durable findings update the matching file under `docs/` in the same PR. If there are no durable findings, the PR body and Plane handoff comment must state `Docs: no durable context changes`.
