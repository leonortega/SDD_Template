---
name: project-guidance-mapper
description: Map repository delivery workflow steps to repo-local skills and project guidance. Use when Codex needs to choose skills, tools, MCP/plugin guidance, references, practices, standards, and installed expert skills for config infra, first ticket setup, OpenSpec proposal/design/tasks/spec, implementation, review, QA, deploy, rollback, hotfix, retrospective, or discovered stack/tool guidance.
---

# Project Guidance Mapper

## Overview

Use this skill to choose the right repo-local workflow skills and supporting project guidance for a workflow step. Prefer repo-local workflow skills first, then add installed expert skills and local catalog guidance discovered under `.codex/tool-recommendations.local.json`.

Use it for config infra, first-ticket setup, planning, implementation, review, QA, deploy, rollback, hotfix, status, retrospective, and handoff questions.

## Shared Context

Read `.codex/skills/_shared/delivery-contract.md` and `docs/context-management.md` before mapping any step that can affect a ticket, validation gate, deployment lane, QA evidence, or handoff. Use `pipeline-status` when the current workflow state is unclear.

## Mapping Rules

- Read `.codex/skills/` to verify which skills are actually present.
- Prefer the ignored installed-skill runtime index when present and fresh for exact `SKILL.md` paths; fall back to scanning `.codex/skills/` when the index is missing or stale.
- Read `.codex/tool-recommendations.local.json` when it exists. Prefer recommendations whose `usedInSteps` includes the current step, then verify listed skill targets still exist under `.codex/skills`.
- Use `project-guidance-discover` when the user asks for project recommendations, base-code setup, first-ticket preflight, or missing expert skills/guidance.
- Use `project-guidance-acquire` only after `project-guidance-discover` produces the final confirmed list.
- When a step uses, confirms, or infers a guidance item, persist that mapping with `MapProjectGuidanceStep` so the recommendation receives the current step in `usedInSteps`.
- If a recommendation has no `usedInSteps`, infer fit from `type`, `requires`, `researchTopics`, `tags`, `purpose`, and current workflow context; then persist the inferred step only after it is used or confirmed.
- Use tool/framework expert guidance, MCPs, plugins, and IDE/tool availability as supporting context for implementation, review, QA, deploy, and security; do not let them override the repo delivery contract.
- Keep Plane ticket delivery on repo-local skills and the configured Plane API; do not recommend Plane MCP for ticket delivery.

## Workflow

- Config infra: `configure-dev-environment`, then focused configure skills; add project guidance discovery for missing guidance findings.
- First ticket setup: `plane-start-ticket`; if stack context or guidance coverage is missing, stop and route to `configure-dev-environment` plus `project-guidance-discover`.
- Planning: `openspec-propose`, `openspec-explore`, or repo ticket skills; include expert guidance for affected technologies and standards.
- Implementation: `implement-ticket`; include stack expert skills and practices such as ASP.NET Core, Blazor, REST/API, security, clean code, architecture, or test quality when present.
- PR review: `gitea-pr-review-agent`; include relevant expert guidance for code, security, API, UI, QA, and maintainability review.
- Review feedback: `pr-review-feedback-loop`; include the same expert guidance used for the affected code.
- Post-merge deployment: `post-merge-deploy`, then `deploy-to-qa`; include Nexus, Azure, release, and observability guidance.
- E2E QA: `test-e2e`; include `frontend-testing-debugging` when present for rendered UI checks, plus Browser plugin guidance, Playwright guidance, and test-quality practices.
- PROD promotion: `deploy-to-prod`; include release, rollback, Azure, Nexus, and monitoring guidance.
- Rollback: `rollback-prod`; include rollback, artifact lineage, Azure, Nexus, and incident guidance.
- Hotfix: `hotfix-prod`; include security, test-quality, release, and rollback guidance.
- Status: `pipeline-status`.
- Parallel work: `parallel-ticket-coordinator`.
- Retrospective and workflow improvement: `delivery-retrospective-audit`; route durable guidance improvements back through configure docs/tests.

## Local Mapping State

Use `.codex/tool-recommendations.local.json` as the local source for learned step mappings. It keeps the recommendation catalog shape, including source, target, validation, accepted/dismissed ids, `notRecommended`, and recommendation-level `usedInSteps`.

The installed-skill runtime index is separate, derived state. It contains only installed skill names, descriptions, scopes, exact paths, and cache fingerprints. Do not store non-skill guidance, acquisition decisions, accepted/dismissed state, or standards in the installed-skill index.

To persist a confirmed mapping:

```powershell
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode MapProjectGuidanceStep -ValuesJson '{"workflowStep":"implementation","recommendationIds":["openai-aspnet-core-skill","dotnet-assertion-quality-skill"],"primarySkills":["implement-ticket"],"supportingSkills":["aspnet-core","assertion-quality"],"why":"Ticket implementation touched ASP.NET Core code and xUnit tests.","nextAction":"Use these guidance items for similar implementation steps."}'
```

Only persist mappings after a step is actually chosen, confirmed, or used. Do not let the local mapping override the active ticket, delivery contract, validation gates, or current repo contents.

## Output

When asked to map guidance, answer with:

- `workflowStep`
- `primarySkills`
- `supportingSkills`
- `guidanceRecommendations`
- `toolingRecommendations`
- `missingUsefulGuidance`
- `why`
- `nextAction`
- `localMappingUpdated`

If the workflow step is unclear, inspect current Plane/OpenSpec/Git state through the responsible status skill before choosing a mutation skill.

## Failure Rules

- Stop and use `pipeline-status` when the current ticket, branch, PR, artifact, or deployment state is ambiguous.
- Stop before recommending a mutation skill when required validation or handoff evidence is missing.
- Stop before using an expert skill that is not present in `.codex/skills` unless `project-guidance-discover` has proposed it and the user has confirmed the next step.
- Do not route around the delivery contract, ticket context lock, review gates, QA gates, or explicit PROD-promotion rule.
