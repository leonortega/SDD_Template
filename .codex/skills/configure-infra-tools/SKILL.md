---
name: configure-infra-tools
description: Configure the repo-local software delivery lab by collecting, explaining, validating, and applying required values for Plane, Gitea runner, Gitea PR automation, PR reviewers and labels, Nexus, monitoring, Azure web/API environments, and Codex client tool config. Use when Codex needs to set up or repair .codex/client-tools.local.json, infra/plane/variables.env, infra/gitea/runner.env, local Docker Compose tool settings, Plane API access, Gitea runner registration, Gitea API access for PR creation/review, Azure DEV/QA/PROD App Service environments for a web app and REST API with SQLite, Azure deployment parameters, or when the user asks how to configure the infra/tools for this project.
---

# Configure Infra Tools

## Overview

Use this skill to configure the local Agentic E2E Development Lab from chat. Codex should inspect current files, identify missing or placeholder values, explain how to obtain each value, ask for only the required values, and apply changes only to ignored local configuration files.

For the full value catalog and retrieval guidance, read `references/configuration-values.md`. Use `scripts/configure_infra_tools.ps1` for deterministic local-file initialization, placeholder auditing, and safe updates.

The configuration topology is:

- Local machine:
  - Plane for ticket management.
  - Gitea for source code repositories.
  - Gitea Actions runner for CI/CD execution.
  - Sonatype Nexus Repository Community Edition for artifacts and container images.
  - Prometheus for app metrics scraping.
  - Grafana for local and Azure dashboards.
- Azure:
  - DEV app runtime, config, and SQLite DB.
  - QA app runtime, config, and SQLite DB.
  - PROD app runtime, config, and SQLite DB.

Configuration has only two phases:

- Pre-start: values required before local infra can start safely.
- Post-start: values obtained from running tools or used to complete implementation, deployment, CI/CD, monitoring, and dashboard flow.

## Safety Rules

- Never print, commit, paste into tickets, or write real tokens/secrets into tracked files.
- Update only these local files unless the user explicitly asks for a tracked template change:
  - `.codex/client-tools.local.json`
  - `infra/plane/variables.env`
  - `infra/gitea/runner.env`
- Keep tracked `.example` files as templates, not secret stores.
- Before any live-service check, remind the user that infra must be running with `.\infra\up.ps1`.
- Do not run `.\infra\up.ps1` automatically. Ask the user whether they want Codex to run it; if they decline, continue with file-based setup and skip live checks.
- If pre-start values are missing or unsafe while local infra is running, ask the user to run `.\infra\down.ps1` or ask whether Codex should run it. Apply the pre-start values only after infra is down, then ask before running `.\infra\up.ps1`.
- Do not use Plane MCP, Docker database access, or direct database queries for Plane client workflow validation. Use the Plane API.
- Redact secret values in all summaries. Refer to the key name and file path only.

## Workflow

### 0. Prerequisite Tools

When a required executable or local tool is missing, do not tell the user to search for installation instructions. Provide the exact install command, official URL, verification command, and any restart/login step from `references/configuration-values.md`.

Check these prerequisites when relevant:

- `git`: required for branch and repository validation.
- `docker`: required for local infra startup, shutdown, and live container checks.
- `az`: required for Azure DEV/QA/PROD validation and deployment.

### 1. Inspect

Run a file-based audit first:

```powershell
.\.codex\skills\configure-infra-tools\scripts\configure_infra_tools.ps1 -Mode Audit
```

Also inspect relevant repo files when needed: `.gitignore`, `.codex/client-tools.example.json`, `infra/plane/variables.env.example`, `infra/gitea/runner.env.example`, `infra/monitoring/prometheus.yml`, and `infra/azure/*.parameters.json`.

### 2. Initialize Missing Local Files

If local files are missing, create them from their tracked examples:

```powershell
.\.codex\skills\configure-infra-tools\scripts\configure_infra_tools.ps1 -Mode InitLocalFiles
```

If the user only wants a preview, pass `-DryRun`.

### 3. Ask for Values

Ask only for values that are missing, placeholders, unsafe defaults, or needed for the requested workflow. Ask step by step, one tool section at a time, and wait for the user to provide the current value before moving to the next missing value. Classify every requested value as pre-start or post-start. For each requested value:

- Name the target key and file.
- Explain how to obtain it from the tool UI, CLI, or local repo.
- State whether the value is required pre-start or post-start.
- If the user says "skip for now", record the value as post-start pending and leave the current placeholder unchanged.

Use `references/configuration-values.md` for exact value-specific instructions.

Use this order unless the user asks for a narrower tool:

1. Plane: ticket management.
2. Gitea: source code repository and PR automation.
3. Gitea Actions runner: CI/CD execution.
4. Sonatype Nexus Repository Community Edition: artifact repository and container image registry.
5. Azure DEV: app runtime, config, and SQLite DB.
6. Azure QA: app runtime, config, and SQLite DB.
7. Azure PROD: app runtime, config, and SQLite DB.
8. Prometheus: scrape app metrics.
9. Grafana: dashboards for local and Azure metrics.

Nexus stays before Azure because CI/CD artifact setup belongs before deployment flow. The current Azure infrastructure does not depend on Nexus because the Bicep deploys App Service resources directly. Prometheus and Grafana stay after Azure because Azure app hostnames are needed for scrape targets and dashboards.

When asking for values, use this format:

```text
Configuring <tool>: <purpose>.
Need: <key> in <file or Azure parameter>.
How to get it: <tool-specific steps>.
Default: <default or "none">.
Phase: <pre-start or post-start>.
Required for: <startup/live validation/deployment/CI/CD/monitoring/dashboards>.
Please paste the value, or say "skip for now".
```

### 4. Apply Confirmed Values

Use the helper script with a JSON object containing only confirmed values. Do not include values that the user has not provided.

Client tool config example:

```powershell
$values = @{
  plane = @{
    baseUrl = "replace-with-plane-base-url"
    apiToken = "<secret>"
    workspaceSlug = "replace-with-plane-workspace-slug"
    projectIdentifier = "replace-with-plane-project-identifier"
    todoState = "replace-with-plane-todo-state"
    inProgressState = "replace-with-plane-in-progress-state"
    reviewState = "replace-with-plane-review-state"
  }
  git = @{
    baseBranch = "replace-with-base-branch"
    branchPrefix = "replace-with-branch-prefix"
    branchPattern = "{prefix}/{ticketKeySlug}-{titleSlug}"
    maxBranchLength = 100
  }
  gitea = @{
    baseUrl = "replace-with-gitea-base-url"
    apiToken = "<secret>"
    owner = "replace-with-gitea-owner"
    repo = "replace-with-gitea-repo"
  }
  pr = @{
    reviewers = "replace-with-reviewers"
    labels = @{
      enabled = $true
      reviewed = "replace-with-reviewed-label"
      needsTests = "replace-with-needs-tests-label"
      needsChanges = "replace-with-needs-changes-label"
    }
  }
} | ConvertTo-Json -Depth 5
.\.codex\skills\configure-infra-tools\scripts\configure_infra_tools.ps1 -Mode SetClientTools -ValuesJson $values
```

Plane env and Gitea runner values use `-Mode SetPlaneEnv` and `-Mode SetGiteaRunner` with flat JSON key/value objects.

### 5. Live Checks

Before live checks, say:

```text
Live validation requires the local infra to be running. Please run .\infra\up.ps1 first, or tell me if you want me to run it.
```

Only run `.\infra\up.ps1` after the user explicitly approves in the current chat. If the user declines, skip live checks and clearly say that only file-based validation was performed.

Useful live checks after infra is running:

- Plane: call `{baseUrl}/api/v1/users/me/` with `X-API-Key`.
- Plane projects: list projects and confirm `workspaceSlug` and `projectIdentifier`.
- Gitea: open or request `http://localhost:3000`, confirm API token access, repository owner/name, collaborators for `pr.reviewers = "all"`, and runner registration when needed.
- Nexus: check `http://localhost:8088`, then validate admin or service credentials for artifact publish or container registry workflows.
- Azure: after deployment, check DEV, QA, and PROD web/API URLs from Bicep outputs.
- Prometheus: check `http://localhost:9090` after Azure outputs are available when Azure targets are configured.
- Grafana: check `http://localhost:3001`.

### 6. Azure DEV/QA/PROD Environment Creation

When the user asks to create Azure environments, deploy `infra/azure/main.bicep` once per environment using `infra/azure/deploy-environments.ps1`.

Before running Azure commands, configure Azure one environment at a time: DEV, then QA, then PROD. For each environment, ask for resource group, location, App Service SKU, runtime stack, and SQLite database file name only when the default is not acceptable. If `az` is missing, provide the Azure CLI WinGet install command, official Microsoft Learn URL, verification command, `az login`, and `az account set` guidance from `references/configuration-values.md`.

1. Confirm Azure CLI is installed and `az account show` succeeds.
2. State the active subscription name/id and tenant id.
3. Ask for confirmation before creating or changing Azure resources unless the user already explicitly asked to create them in the current turn.
4. Ask only for values that differ from defaults:
   - Location: default `eastus`.
   - Resource groups: default `rg-agentic-dev`, `rg-agentic-qa`, `rg-agentic-prod`.
   - App Service plan SKU: default `B1` / `Basic`.

Use this preview command first unless the user explicitly asks to deploy directly:

```powershell
.\infra\azure\deploy-environments.ps1 -Location eastus -WhatIf
```

After approval, create/update all three environments:

```powershell
.\infra\azure\deploy-environments.ps1 -Location eastus
```

The template creates, per environment:

- One Linux App Service plan.
- One Linux Web App tagged `role=web`.
- One Linux REST API App tagged `role=rest-api`.
- REST API app settings for SQLite:
  - `DATABASE_PROVIDER=sqlite`
  - `SQLITE_DB_PATH=/home/data/app.db`
  - `WEBSITES_ENABLE_APP_SERVICE_STORAGE=true`
- Web app settings pointing to the REST API URL:
  - `REST_API_BASE_URL`
  - `VITE_API_BASE_URL`
  - `NEXT_PUBLIC_API_BASE_URL`

After deployment, capture the Bicep outputs for each environment and update `infra/monitoring/prometheus.yml` Azure targets if the user wants monitoring pointed at the new app hostnames. Do not store publish profiles, Azure credentials, or deployment secrets in tracked files.

Do not configure Prometheus Azure targets or Grafana Azure dashboards until Azure DEV, QA, and PROD outputs are available.

## Required Improvements for This Repo

During setup, explicitly handle these known local findings:

- `.codex/client-tools.local.json` may be missing `plane.inProgressState`; add `In Progress` unless the user chooses another Plane state.
- `.codex/client-tools.local.json` may be missing `plane.reviewState`; add `In Review` unless the user chooses another Plane review state.
- `.codex/client-tools.local.json` may be missing `gitea` and `pr` sections required by implementation and PR review skills; add defaults from `.codex/client-tools.example.json`.
- `.codex/client-tools.local.json` may contain placeholder `gitea.apiToken`; ask for a Gitea API token before PR creation, PR review comments, labels, or reviewer lookup.
- `infra/plane/variables.env` may contain weak local defaults such as `POSTGRES_PASSWORD=plane`, RabbitMQ password `plane`, and MinIO `access-key` / `secret-key`; replace them with generated local secrets when the user agrees.
- `infra/gitea/runner.env` is incomplete while `GITEA_RUNNER_REGISTRATION_TOKEN=replace-with-token-from-gitea`.
- `infra/monitoring/prometheus.yml` contains placeholder Azure targets until real Azure app hostnames exist.
- `infra/azure/main.bicep` should create DEV, QA, and PROD-compatible App Service resources for both a web app and REST API. Use the tracked parameter files and `infra/azure/deploy-environments.ps1` for repeatable creation.
- Grafana uses default local credentials unless changed by the user; if dashboards will be shared or exposed beyond localhost, ask the user to rotate the admin password.
- Nexus needs post-start service account or admin credentials when CI/CD publish workflows are enabled.

## Secret Generation

Prefer PowerShell-native generation on Windows:

```powershell
[guid]::NewGuid().ToString()
[Convert]::ToHexString([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32)).ToLower()
```

Use OpenSSL or `uuidgen` only when available. Never echo generated values back to the user unless they explicitly need to paste them into a local UI, and redact them in summaries.

## Completion Summary

End with:

- Files created or updated, without secret values.
- Values still missing or intentionally skipped.
- Whether validation was file-only or included live checks.
- Reminder to run `.\infra\up.ps1` if live services were not started.
