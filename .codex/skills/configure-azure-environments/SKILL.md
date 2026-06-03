---
name: configure-azure-environments
description: Configure Azure DEV, QA, and PROD App Service environments for this repo, including deployment topology discovery from deployable projects, appsettings-to-App-Service mapping, Bicep what-if/deploy flow, per-app package/deploy workflow updates, resource group/location/SKU/runtime choices, SQLite App Service settings, environment outputs, and runtime compatibility warnings.
---

# Configure Azure Environments

## Overview

Configure Azure DEV, QA, and PROD App Service environments for ticket-gated deployment validation and handoff. This skill owns Deployment Topology Review: detect deployable apps, keep `infra/deployment/apps.json` aligned, map `appsettings*.json` keys to Azure App Service settings, and keep Bicep plus package/deploy workflow surfaces synchronized.

## Shared Context

Read `.codex/skills/configure-dev-environment/references/azure.md` before asking for values or applying changes.

Use repo scripts under `infra/azure/` for Azure preview and deployment. Use `infra/deployment/apps.json` as the tracked deployable app manifest.

Apply `.codex/skills/_shared/delivery-contract.md` and `docs/context-management.md` before changing deployment behavior or recording durable configuration findings.

Safety:

- Do not store Azure credentials, publish profiles, or environment-specific hostnames in tracked files.
- Run `az account show` before deployment and report subscription context without exposing tokens.
- Use `-WhatIf` first unless the user explicitly asks to deploy directly.

## Workflow

1. Confirm Azure CLI exists and `az account show` succeeds.
2. Run Deployment Topology Review whenever changes touch `src/**.csproj`, `src/**/Program.cs`, `src/**/appsettings*.json`, `infra/deployment/**`, `infra/azure/**`, or `.gitea/workflows/package-deploy.yml`.
3. Detect deployable apps under `src/**` using `Microsoft.NET.Sdk.Web`; classify Blazor/Razor projects as `web`, Minimal/API endpoint projects as `api`, and preserve explicit overrides in `infra/deployment/apps.json`.
4. Record each app id, project path, role, artifact name, health path, deploy order, and dependencies in `infra/deployment/apps.json`. Use lowercase app ids; derive Gitea secret names as `AZURE_{ENV}_{APPID}_APP_NAME` and `AZURE_{ENV}_{APPID}_APP_URL`.
5. Flatten `appsettings*.json` keys into Azure App Service setting names with `:` and arrays converted to `__`, such as `Api:BaseUrl` -> `Api__BaseUrl` and `Cors:AllowedOrigins[0]` -> `Cors__AllowedOrigins__0`.
6. Infer known non-secret values between apps, such as web `Api__BaseUrl` pointing to the API app URL, API `Cors__AllowedOrigins__0` pointing to the web app URL, and API SQLite `ConnectionStrings__ClientsDb` pointing to `/home/data/app.db`.
7. For unknown or secret-bearing values, add placeholder-safe mapping or report the exact DEV/QA/PROD value names required. Never write real secrets or environment hostnames into tracked `appsettings*.json`.
8. Keep `infra/azure/main.bicep`, `.gitea/workflows/package-deploy.yml`, `.gitea/workflows/README.md`, and configure audits synchronized with the manifest.
9. Ask only for values that differ from defaults.
10. Preview with `.\infra\azure\deploy-environments.ps1 -Location eastus -WhatIf`.
11. Deploy only after approval.
12. When `AZURE_CREDENTIALS` is missing, explain how to create the service principal JSON, where to store it in Gitea Actions secrets, official documentation links, and validation commands.
13. When PROD deployment is enabled, verify the Gitea Actions secret names for every manifest app exist. Infer their non-secret values from Azure deployment outputs or `az webapp list`, then configure only after confirming the values.
14. Pass Azure output hostnames to `$configure-observability` only when monitoring should be wired.

## Output

Report Azure CLI validation, Deployment Topology Review status, what-if/deploy status, configured non-secret values, missing per-app secrets, and ticket handoff blockers without exposing credentials.

## Failure Rules

- Stop when Azure CLI, subscription context, or required user values are missing.
- Stop when validation or what-if output shows unsafe environment drift.
- Stop before deploying or changing PROD settings without explicit user approval.
