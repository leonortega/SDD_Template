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

Plane ticket work starts from Codex chat, not from a user-run command. The repo-local skill at `.codex/skills/plane-start-ticket` guides Codex to list Todo tickets, create or reuse a Git branch, generate OpenSpec-style planning notes, update the Plane ticket description, comment with the branch name, move the ticket to `In Progress`, and create an OpenSpec proposal.

Implementation handoff also starts from chat. The repo-local skill at `.codex/skills/openspec-implement-change` runs `/opsx:apply`, implements the OpenSpec tasks, adds edge-case unit tests, verifies the app and tests, commits with a readable change list, pushes after hooks pass, opens a Gitea PR, invokes `.codex/skills/gitea-pr-review-agent`, moves the Plane ticket to the configured review state, and comments on Plane with the PR link.

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
    "todoState": "Todo",
    "inProgressState": "In Progress",
    "reviewState": "In Review"
  },
  "git": {
    "baseBranch": "dev",
    "branchPrefix": "feat",
    "branchPattern": "{prefix}/{ticketKeySlug}-{titleSlug}",
    "maxBranchLength": 100
  },
  "gitea": {
    "baseUrl": "http://localhost:3000",
    "apiToken": "replace-with-gitea-api-token",
    "owner": "",
    "repo": ""
  },
  "pr": {
    "reviewers": "all",
    "labels": {
      "enabled": true,
      "reviewed": "codex-reviewed",
      "needsTests": "needs-tests",
      "needsChanges": "needs-changes"
    }
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
PLANE_IN_PROGRESS_STATE
PLANE_REVIEW_STATE
GIT_BASE_BRANCH
GIT_BRANCH_PREFIX
GIT_BRANCH_PATTERN
GITEA_BASE_URL
GITEA_API_TOKEN
GITEA_OWNER
GITEA_REPO
PR_REVIEWERS
PR_LABEL_REVIEWED
PR_LABEL_NEEDS_TESTS
PR_LABEL_NEEDS_CHANGES
```

Configuration details:

- `plane.reviewState` is the Plane state used after a PR is created and reviewed. Default: `In Review`.
- `gitea.baseUrl` is the Gitea web/API root. Default: `http://localhost:3000`.
- `gitea.apiToken` is required for PR creation, review comments, labels, and reviewer lookup. Store real tokens only in `.codex/client-tools.local.json` or an environment variable.
- `gitea.owner` and `gitea.repo` can be left empty; the implementation skill infers them from `git remote get-url origin` when possible.
- `pr.reviewers` controls requested reviewers. Use `"all"` to request all repository developers/collaborators from Gitea, excluding the PR author and automation user. Use an explicit JSON array such as `["alice", "bob"]` to request a fixed developer list.
- `pr.labels.enabled` controls whether the review workflow uses labels. When enabled, missing labels are created before use. Defaults are `codex-reviewed`, `needs-tests`, and `needs-changes`.
- `pr.labels.reviewed` is applied after the review agent posts a review for the current PR head SHA.
- `pr.labels.needsTests` is applied when the review finds missing or failing tests.
- `pr.labels.needsChanges` is applied when the review finds actionable defects or blocking issues.

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
    "todoState": "Todo",
    "inProgressState": "In Progress"
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

After Codex comments on the Plane ticket with the branch, it moves the ticket to the configured `inProgressState`. It then creates an OpenSpec proposal with `/opsx:propose` using a change name derived from the branch; branch slashes are converted to dashes for the OpenSpec change id. Re-runs should not duplicate the generated branch comment or repeat the state move when the ticket is already in progress.

After implementation is complete, Codex opens a Gitea PR and invokes the PR review agent immediately. The review agent reviews only that PR, posts one top-level Gitea comment, adds an idempotency marker for the PR head SHA, ensures configured labels exist, and applies the appropriate review labels. It does not run on a timer.

After the PR review comment is posted, Codex moves the Plane ticket to configured `reviewState` and adds a Plane comment using the stable marker `IA generated PR: {prUrl}`. If the configured review state does not exist, Codex stops after PR creation and review instead of guessing another state.

### Gitea PR Setup

Create a Gitea API token for the local agent workflow and store it only in `.codex/client-tools.local.json`:

```json
{
  "gitea": {
    "baseUrl": "http://localhost:3000",
    "apiToken": "gitea_token_...",
    "owner": "leon",
    "repo": "SDD_template"
  },
  "pr": {
    "reviewers": "all",
    "labels": {
      "enabled": true,
      "reviewed": "codex-reviewed",
      "needsTests": "needs-tests",
      "needsChanges": "needs-changes"
    }
  }
}
```

To use a fixed reviewer list instead of all repository developers:

```json
{
  "pr": {
    "reviewers": ["alice", "bob", "carol"]
  }
}
```

If labels are enabled, the review workflow creates missing labels in Gitea before applying them. Disable labels for repositories that do not use PR labels:

```json
{
  "pr": {
    "labels": {
      "enabled": false
    }
  }
}
```

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
