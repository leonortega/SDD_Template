---
name: configure-infra-tools
description: Configure the repo-local software delivery lab by collecting, explaining, validating, and applying required values for Plane, Gitea runner, Gitea PR automation, PR reviewers and labels, Nexus, monitoring, Azure parameters, and Codex client tool config. Use when Codex needs to set up or repair .codex/client-tools.local.json, infra/plane/variables.env, infra/gitea/runner.env, local Docker Compose tool settings, Plane API access, Gitea runner registration, Gitea API access for PR creation/review, Azure deployment parameters, or when the user asks how to configure the infra/tools for this project.
---

# Configure Infra Tools

## Overview

Use this skill to configure the local Agentic E2E Development Lab from chat. Codex should inspect current files, identify missing or placeholder values, explain how to obtain each value, ask for only the required values, and apply changes only to ignored local configuration files.

For the full value catalog and retrieval guidance, read `references/configuration-values.md`. Use `scripts/configure_infra_tools.ps1` for deterministic local-file initialization, placeholder auditing, and safe updates.

## Safety Rules

- Never print, commit, paste into tickets, or write real tokens/secrets into tracked files.
- Update only these local files unless the user explicitly asks for a tracked template change:
  - `.codex/client-tools.local.json`
  - `infra/plane/variables.env`
  - `infra/gitea/runner.env`
- Keep tracked `.example` files as templates, not secret stores.
- Before any live-service check, remind the user that infra must be running with `.\infra\up.ps1`.
- Do not run `.\infra\up.ps1` automatically. Ask the user whether they want Codex to run it; if they decline, continue with file-based setup and skip live checks.
- Do not use Plane MCP, Docker database access, or direct database queries for Plane client workflow validation. Use the Plane API.
- Redact secret values in all summaries. Refer to the key name and file path only.

## Workflow

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

Ask only for values that are missing, placeholders, unsafe defaults, or needed for the requested workflow. For each requested value:

- Name the target key and file.
- Explain how to obtain it from the tool UI, CLI, or local repo.
- State whether the value is required for file-only setup or only for live validation.
- Accept "skip for now" for optional integrations and leave the current placeholder unchanged.

Use `references/configuration-values.md` for exact value-specific instructions.

### 4. Apply Confirmed Values

Use the helper script with a JSON object containing only confirmed values. Do not include values that the user has not provided.

Client tool config example:

```powershell
$values = @{
  plane = @{
    baseUrl = "http://agentic.lvh.me:8080"
    apiToken = "<secret>"
    workspaceSlug = "e2etest"
    projectIdentifier = "E2EPROJECT"
    todoState = "Todo"
    inProgressState = "In Progress"
    reviewState = "In Review"
  }
  git = @{
    baseBranch = "dev"
    branchPrefix = "feat"
    branchPattern = "{prefix}/{ticketKeySlug}-{titleSlug}"
    maxBranchLength = 100
  }
  gitea = @{
    baseUrl = "http://localhost:3000"
    apiToken = "<secret>"
    owner = "leon"
    repo = "SDD_template"
  }
  pr = @{
    reviewers = "all"
    labels = @{
      enabled = $true
      reviewed = "codex-reviewed"
      needsTests = "needs-tests"
      needsChanges = "needs-changes"
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
- Nexus: check `http://localhost:8088`.
- Grafana: check `http://localhost:3001`.
- Prometheus: check `http://localhost:9090`.

## Required Improvements for This Repo

During setup, explicitly handle these known local findings:

- `.codex/client-tools.local.json` may be missing `plane.inProgressState`; add `In Progress` unless the user chooses another Plane state.
- `.codex/client-tools.local.json` may be missing `plane.reviewState`; add `In Review` unless the user chooses another Plane review state.
- `.codex/client-tools.local.json` may be missing `gitea` and `pr` sections required by implementation and PR review skills; add defaults from `.codex/client-tools.example.json`.
- `.codex/client-tools.local.json` may contain placeholder `gitea.apiToken`; ask for a Gitea API token before PR creation, PR review comments, labels, or reviewer lookup.
- `infra/plane/variables.env` may contain weak local defaults such as `POSTGRES_PASSWORD=plane`, RabbitMQ password `plane`, and MinIO `access-key` / `secret-key`; replace them with generated local secrets when the user agrees.
- `infra/gitea/runner.env` is incomplete while `GITEA_RUNNER_REGISTRATION_TOKEN=replace-with-token-from-gitea`.
- `infra/monitoring/prometheus.yml` contains placeholder Azure targets until real Azure app hostnames exist.

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
