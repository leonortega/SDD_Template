# OpenProject Ticket Workflow Configuration

Use `.codex/client-tools.local.json` as the primary local configuration file. Keep `.codex/client-tools.example.json` tracked as the template. Environment variables are optional overrides for client machines or CI.

## Defaults

```json
{
  "openProject": {
    "baseUrl": "http://localhost:8080",
    "apiToken": "replace-with-openproject-api-token",
    "projectIdentifier": "e2eproject",
    "todoStatus": "Todo",
    "inProgressStatus": "In Progress"
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

- `OPENPROJECT_BASE_URL`
- `OPENPROJECT_API_TOKEN`
- `OPENPROJECT_PROJECT_IDENTIFIER`
- `OPENPROJECT_TODO_STATUS`
- `OPENPROJECT_IN_PROGRESS_STATUS`
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

## OpenProject API Setup

Copy the tracked template and edit the ignored local file:

```powershell
Copy-Item .\.codex\client-tools.example.json .\.codex\client-tools.local.json
```

Set `openProject.apiToken` in `.codex/client-tools.local.json`. The token is sent as the `Authorization: Bearer` header. Never commit real OpenProject tokens or private client URLs. Use OpenProject API only; do not use OpenProject MCP, Docker containers, or direct database access for this workflow.

Resolve the configured in-progress status by name before updating a work package status. The default is `In Progress`.

After the ticket is commented with the branch, create an OpenSpec proposal through `dev-flow-propose-change` (`/opsx:propose`). Use the branch name as the source name; if it contains `/`, replace `/` with `-` for the OpenSpec change id.

Known local defaults:

- `baseUrl`: `http://localhost:8080`
- `projectIdentifier`: `e2eproject`
- `baseBranch`: `dev`
