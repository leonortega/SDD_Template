# OpenProject Sprint And Backlog Grooming

Manage OpenProject work packages through sprint and backlog grooming workflows.

## Scope

This skill covers sprint planning, backlog refinement, work package hierarchy management, and status reporting within OpenProject.

## Work Package Hierarchy

```
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
