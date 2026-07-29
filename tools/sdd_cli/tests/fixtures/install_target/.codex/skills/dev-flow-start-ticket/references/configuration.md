# OpenProject Ticket Workflow Configuration

Use `.codex/client-tools.local.json` as the primary local configuration file. Keep `.codex/client-tools.common.json` tracked as the template. Environment variables are optional overrides for client machines or CI.

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
- `OPENROUTER_BASE_URL`
- `OPENROUTER_API_KEY`

## OpenRouter Agent Runtime Configuration

If the delivery workflow uses OpenRouter models such as `openrouter/free` or `openrouter/auto`, add the `openRouter` section to `.codex/client-tools.local.json`:

```json
{
  "openRouter": {
    "baseUrl": "https://api.openrouter.ai/v1",
    "apiKey": "replace-with-openrouter-api-key",
    "defaultChatModel": "openrouter/auto",
    "modelMapping": {
      "chat": {"model": "openrouter/auto", "reasoningEffort": "medium"}
    }
  }
}
```

Keep the API key in ignored `.codex/client-tools.local.json` only and never commit it. This configuration is used by local delivery tools and agent sub-agents that select `openrouter/*` model ids.

- `openRouter.defaultChatModel` is the fallback model for generic Copilot chat and other non-skill interactive sessions.
- `openRouter.modelMapping.chat` can be used to set a specific OpenRouter model preference for chat-driven repo workflows.
- `openRouter.modelMapping.<skillName>` can be used to customize model preferences for specific repo-local skills.

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

```bash
Copy-Item .\.codex\client-tools.common.json .\.codex\client-tools.local.json
```

Set `openProject.apiToken` in `.codex/client-tools.local.json`. The token is sent as the `Authorization: Bearer` header. Never commit real OpenProject tokens or private client URLs. Use OpenProject API only; do not use OpenProject MCP, Docker containers, or direct database access for this workflow.

Resolve the configured in-progress status by name before updating a work package status. The default is `In Progress`.

After the ticket is commented with the branch, create an OpenSpec proposal through `dev-flow-propose-change` (`/opsx:propose`). Use the branch name as the source name; if it contains `/`, replace `/` with `-` for the OpenSpec change id.

Known local defaults:

- `baseUrl`: `http://localhost:8080`
- `projectIdentifier`: `e2eproject`
- `baseBranch`: `dev`
