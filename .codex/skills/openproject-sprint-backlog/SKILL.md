# OpenProject Sprint And Backlog Grooming

Manage OpenProject work packages through sprint and backlog grooming workflows.

## Overview

Use this skill for ticketed sprint planning, backlog refinement, work package
hierarchy management, and status reporting on OpenProject, per the shared
delivery contract.

## Shared Context

Read `.codex/skills/_shared/delivery-contract.md` and
`docs/conventions/context-management.md` before grooming. Verify the active
ticket and sprint state against live OpenProject data before moving or
estimating work packages.

## Scope

This skill covers sprint planning, backlog refinement, work package hierarchy management, and status reporting within
OpenProject.

## Work Package Hierarchy

```text
Epic (parent)
 └─ Feature (story)
     └─ Task (child work package)
```

- **Epics**: Large bodies of work spanning multiple sprints
- **Features**: User-facing functionality (story points estimated)
- **Tasks**: Technical breakdown items (hours estimated)

## Estimation Norms

- Features: Fibonacci sequence (1, 2, 3, 5, 8, 13)
- Tasks: Hours (1h–16h, beyond that split into subtasks)
- Default activity mapping:
  - Specification → `dev-flow-propose-change`, `dev-flow-start-ticket`
  - Development → `dev-flow-implement-ticket`
  - Testing → `dev-ops-deploy-qa`
  - Management → `dev-ops-deploy-prod`, `dev-ops-post-merge-deploy`
  - Support → `dev-ops-rollback-prod`, `dev-ops-hotfix-prod`

## Status Reporting

Use the `render-openproject-comment` CLI tool to generate status comments:

```bash
python -m tools.sdd_cli dev-flow render-openproject-comment \
  --ticket-key PROJ-123 \
  --stage deploy-qa \
  --status PASS \
  --summary "QA deployment completed successfully"
```

## Sprint Workflow

1. **Planning**: Move To Do items to In Progress, assign story points
2. **Execution**: Daily status updates via OpenProject comments
3. **Review**: Move to status matching configured `reviewStatus`
4. **QA**: Move to status matching configured `qaStatus`
5. **Done**: Close work package when acceptance criteria met

## References

- OpenProject API adapter: `.codex/skills/openproject-sprint-backlog/references/openproject-api.md`
- OpenProject MCP: `openproject` server in `.vscode/mcp.json`
- OpenProject built-in MCP: `{baseUrl}/mcp` (Enterprise 17.2+)

## Workflow

Follow the Sprint Workflow steps above (planning, execution, review, QA, done)
and use the `render-openproject-comment` CLI for status comments. Keep every
move and estimate within the active ticket's acceptance criteria.

## Output

Report the work packages created/updated, estimation applied, sprint board
state, validation of the grooming rules, and the handoff to the next delivery
stage.

## Failure Rules

- Stop and confirm before changing work packages outside the active ticket scope.
- Stop if OpenProject is unreachable or the configured statuses/activities are missing.
- Do not estimate or move work packages without matching configured workflow statuses.
