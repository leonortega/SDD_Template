# Agentic E2E Development Lab

This project defines a local end-to-end software delivery lab for testing AI agents across a realistic development workflow.

The core idea is simple:

- Local Docker Compose runs the software delivery platform.
- Azure runs only the application environments.
- The same build artifact is promoted across DEV, QA, and PROD.

## Architecture

```text
Local machine
├─ Plane
│  └─ ticket management
├─ Gitea
│  └─ source code repository
├─ Gitea Actions runner
│  └─ CI/CD execution
├─ Sonatype Nexus Repository Community Edition
│  └─ artifact repository / container image registry
├─ Dozzle
│  └─ local container logs
├─ Prometheus
│  └─ scrape app metrics
└─ Grafana
   └─ dashboards for local + Azure metrics

Azure
├─ DEV
│  └─ app runtime + config + optional DB
├─ QA
│  └─ app runtime + config + optional DB
└─ PROD
   └─ app runtime + config + optional DB
```

## Repository Layout

```text
infra/
├─ compose.yml
├─ plane/
│  ├─ compose.yml
│  └─ variables.env
├─ gitea/
│  ├─ compose.yml
│  └─ runner.env
├─ nexus/
│  └─ compose.yml
├─ monitoring/
│  ├─ compose.yml
│  ├─ prometheus.yml
│  └─ grafana/
└─ azure/
   ├─ main.bicep
   ├─ dev.parameters.json
   ├─ qa.parameters.json
   └─ prod.parameters.json
```

Use `compose.yml` consistently for Docker Compose files.

## Delivery Flow

```text
1. Create ticket in Plane
2. Agent reads ticket
3. Agent creates branch in Gitea
4. Agent changes code
5. Agent opens PR in Gitea
6. Gitea Actions runs build/tests
7. CI publishes artifact/image to Nexus
8. CI deploys to Azure DEV
9. Agent validates DEV
10. Same artifact is promoted to QA
11. Agent validates QA
12. Same artifact is promoted to PROD
13. Agent checks metrics/logs
14. Agent updates Plane ticket
```

## Chat-Driven Ticket Workflow

Plane ticket work starts from Codex chat, not from a user-run command. The repo-local skill at `.codex/skills/plane-start-ticket` guides Codex to list Todo tickets, create or reuse a Git branch, generate OpenSpec-style planning notes, update the Plane ticket description, and comment with the branch name.

Example chat requests:

```text
List Plane Todo tickets
Start the next Plane Todo ticket
Start E2EPROJECT-1
```

The workflow uses the Plane API. It must never use Plane MCP, Docker containers, or direct database access for Plane.

### Client Tool Configuration

Copy the tracked template to a local ignored file and adjust it for the client environment:

```powershell
Copy-Item .\.codex\client-tools.example.json .\.codex\client-tools.local.json
```

Default configuration:

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

Supported branch patterns:

```text
{prefix}/{ticketKeySlug}-{titleSlug}
{prefix}/{ticketKeySlug}
{prefix}/{projectKeySlug}/{ticketKeySlug}-{titleSlug}
ticket/{ticketKeySlug}-{titleSlug}
codex/{ticketKeySlug}-{titleSlug}
```

Default branch example:

```text
feat/e2eproject-1-create-files-and-folders-for-a-site
```

Optional environment variables override local config when present:

```text
PLANE_BASE_URL
PLANE_API_TOKEN
PLANE_WORKSPACE_SLUG
PLANE_PROJECT_IDENTIFIER
PLANE_TODO_STATE
GIT_BASE_BRANCH
GIT_BRANCH_PREFIX
GIT_BRANCH_PATTERN
```

### Plane API Setup

Register a Plane API key before using the chat workflow:

1. Log in to Plane.
2. Open Profile Settings.
3. Open Personal Access Tokens.
4. Click Add personal access token.
5. Add a clear title and description for this local agent workflow.
6. Choose an expiry according to the client security policy.
7. Copy the generated key once and store it only in `.codex/client-tools.local.json` or a local secret store.

Plane API requests authenticate with the `X-API-Key` header. Do not commit the key, paste it into tickets, or store it in tracked config.

Set the Plane API connection in the ignored `.codex/client-tools.local.json` file:

```json
{
  "plane": {
    "baseUrl": "http://agentic.lvh.me:8080",
    "apiToken": "plane_api_...",
    "workspaceSlug": "e2etest",
    "projectIdentifier": "E2EPROJECT",
    "todoState": "Todo"
  }
}
```

Optional environment variables can override local JSON config for company-managed machines or CI, but they are not required for local use.

Quick read-only token check using the local JSON config:

```powershell
$config = Get-Content .\.codex\client-tools.local.json | ConvertFrom-Json
Invoke-RestMethod `
  -Uri "$($config.plane.baseUrl)/api/v1/users/me/" `
  -Headers @{ "X-API-Key" = $config.plane.apiToken }
```

Token storage depends on the client environment. Never commit real Plane tokens or credential-bearing client settings.

Reference: [Plane API authentication](https://developers.plane.so/api-reference/introduction).

Use the lowercase workspace slug from the Plane URL. Plane's current API uses `work-items` endpoints for tickets; the older `issues` endpoints are deprecated. For project-scoped calls, resolve `projectIdentifier` to the project UUID by listing projects in the workspace.

## Local Platform

The local platform is managed from a single Docker Compose entrypoint:

```powershell
docker compose --env-file .\infra\plane\variables.env -f .\infra\compose.yml up -d
```

Or use the helper script:

```powershell
.\infra\up.ps1
```

Before first run, create local environment files from the examples:

```powershell
Copy-Item .\infra\plane\variables.env.example .\infra\plane\variables.env
Copy-Item .\infra\gitea\runner.env.example .\infra\gitea\runner.env
```

The real `.env` files are intentionally ignored because they contain local secrets and registration tokens.

## Azure Environments

Azure should contain only the minimum resources needed to host the application environments.

Use one resource group per environment:

```text
rg-agentic-dev
rg-agentic-qa
rg-agentic-prod
```

Each environment contains:

- App runtime
- Environment configuration
- Optional database
- Monitoring integration

## Key Principle

```text
Local tools manage the delivery workflow.
Azure hosts only DEV, QA, and PROD runtime resources.
Nexus stores the exact build artifact promoted between environments.
```
