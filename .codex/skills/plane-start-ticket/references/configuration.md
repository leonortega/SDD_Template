# Plane Ticket Workflow Configuration

Use `.codex/client-tools.local.json` as the primary local configuration file. Keep `.codex/client-tools.example.json` tracked as the template. Environment variables are optional overrides for client machines or CI.

## Defaults

```json
{
  "plane": {
    "baseUrl": "http://agentic.lvh.me:8080",
    "apiToken": "replace-with-plane-api-token",
    "workspaceSlug": "e2etest",
    "projectIdentifier": "E2EPROJECT",
    "todoState": "Todo"
  },
  "git": {
    "baseBranch": "dev",
    "branchPrefix": "feat",
    "branchPattern": "{prefix}/{ticketKeySlug}-{titleSlug}",
    "maxBranchLength": 100
  }
}
```

## Optional Environment Overrides

- `PLANE_BASE_URL`
- `PLANE_API_TOKEN`
- `PLANE_WORKSPACE_SLUG`
- `PLANE_PROJECT_IDENTIFIER`
- `PLANE_TODO_STATE`
- `GIT_BASE_BRANCH`
- `GIT_BRANCH_PREFIX`
- `GIT_BRANCH_PATTERN`

## Supported Branch Patterns

- `{prefix}/{ticketKeySlug}-{titleSlug}`
- `{prefix}/{ticketKeySlug}`
- `{prefix}/{projectKeySlug}/{ticketKeySlug}-{titleSlug}`
- `ticket/{ticketKeySlug}-{titleSlug}`
- `codex/{ticketKeySlug}-{titleSlug}`

Default recommendation:

```text
feat/e2eproject-1-create-files-and-folders-for-a-site
```

## Plane API Setup

Copy the tracked template and edit the ignored local file:

```powershell
Copy-Item .\.codex\client-tools.example.json .\.codex\client-tools.local.json
```

Set `plane.apiToken` in `.codex/client-tools.local.json`. The token is sent as the `X-API-Key` header. Never commit real Plane tokens or client URLs that should remain private. Use Plane API only; do not use Plane MCP, Docker containers, or direct database access for this workflow.

Use the lowercase workspace slug from the Plane URL. Use `work-items` endpoints for tickets. For project-scoped list/detail calls, resolve `projectIdentifier` to a project UUID through `GET /api/v1/workspaces/{workspace_slug}/projects/`.
