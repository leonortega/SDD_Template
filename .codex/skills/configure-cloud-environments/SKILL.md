---
name: configure-cloud-environments
description: Configure Azure DEV, QA, and PROD App Service environments for this repo, including deployment topology discovery from deployable projects, appsettings-to-App-Service mapping, Bicep what-if/deploy flow, per-app package/deploy workflow updates, resource group/location/SKU/runtime choices, SQLite App Service settings, environment outputs, and runtime compatibility warnings.
---

# Configure Azure Environments

## Overview

Configure Azure DEV, QA, and PROD App Service environments for ticket-gated deployment validation and handoff. This skill owns Deployment Topology Review: detect deployable apps, keep `infra/deployment/apps.json` aligned, map `appsettings*.json` keys through `infra/deployment/configuration.json`, and keep Bicep plus package/deploy workflow surfaces synchronized.

This skill is Azure-only. Rancher Desktop local Kubernetes setup is handled by `configure-dev-environment` Rancher Desktop local lab routing, `.codex/providers/deploy.rancher-desktop.md`, and `.gitea/workflows/rancher-local-deploy.yml`.

## Shared Context

Read `.codex/skills/configure-dev-environment/references/azure.md` before asking for values or applying changes.

Use repo scripts under `infra/azure/` for Azure preview and deployment. Use `infra/deployment/apps.json` as the tracked deployable app manifest and `infra/deployment/configuration.json` as the tracked deployable configuration mapping.

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
6. Compare discovered keys with `infra/deployment/configuration.json`. Add mappings for new keys, report removed keys as drift, and keep additional deploy-time settings such as API `ConnectionStrings__ClientsDb`.
7. Infer known non-secret values between apps, such as web `Api__BaseUrl` pointing to the API app URL, API `Cors__AllowedOrigins__0` pointing to the web app URL, API SQLite `ConnectionStrings__ClientsDb` pointing to `/home/data/app.db`, and environment name values.
8. For unknown or secret-bearing values, ask the developer in chat for the mapping choice or give exact steps to create the needed Gitea secret, Azure App Service setting, or Azure CLI lookup. Never ask for raw secret values in chat and never write real secrets or environment hostnames into tracked `appsettings*.json`.
9. Require CI to fail closed when `deployment-config.json` cannot be built, a required mapping is `manualRequired`, or live App Service settings do not match expected values.
10. Ensure Azure provisioning applies these settings on first deploy through explicit App Service appsettings resources, not only through package-time configuration repair.
11. Smoke checks must verify browser-facing topology: rendered web pages must contain the expected API base URL and API preflight must allow the matching web origin.
12. Keep `infra/azure/main.bicep`, `.gitea/workflows/package-deploy.yml`, `.gitea/workflows/README.md`, configure audits, and tests synchronized with the manifest and `deployment-config.json` artifact.
13. Ask only for values that differ from defaults.
14. Preview with `.\infra\azure\deploy-environments.ps1 -Location westcentralus -WhatIf` (or the explicitly requested region).
15. Deploy only after approval.
16. When `AZURE_CREDENTIALS` is missing, explain how to create the service principal JSON, where to store it in Gitea Actions secrets, official documentation links, and validation commands.
17. When PROD deployment is enabled, verify the Gitea Actions secret names for every manifest app exist. Infer their non-secret values from Azure deployment outputs or `az webapp list`, then configure only after confirming the values.
18. Pass Azure output hostnames to `$configure-observability` only when monitoring should be wired.

## Output

Report Azure CLI validation, Deployment Topology Review status, what-if/deploy status, configured non-secret values, missing per-app secrets, and ticket handoff blockers without exposing credentials.

## Failure Rules

- Stop when Azure CLI, subscription context, or required user values are missing.
- Stop when validation, deployment configuration generation, live App Service setting verification, or what-if output shows unsafe environment drift.
- Stop before deploying or changing PROD settings without explicit user approval.
