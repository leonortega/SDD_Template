---
name: configure-azure-environments
description: Configure Azure DEV, QA, and PROD App Service environments for this repo, including Azure CLI validation, Bicep what-if/deploy flow, resource group/location/SKU/runtime choices, SQLite App Service settings, environment outputs, and runtime compatibility warnings.
---

# Configure Azure Environments

Read `.codex/skills/configure-dev-environment/references/azure.md` before asking for values or applying changes.

Use repo scripts under `infra/azure/` for Azure preview and deployment.

Safety:

- Do not store Azure credentials, publish profiles, or environment-specific hostnames in tracked files.
- Run `az account show` before deployment and report subscription context without exposing tokens.
- Use `-WhatIf` first unless the user explicitly asks to deploy directly.

Workflow:

1. Confirm Azure CLI exists and `az account show` succeeds.
2. Ask only for values that differ from defaults.
3. Confirm runtime strategy when app target is .NET 10 and Bicep defaults are `DOTNETCORE|8.0`.
4. Preview with `.\infra\azure\deploy-environments.ps1 -Location eastus -WhatIf`.
5. Deploy only after approval.
6. When `AZURE_CREDENTIALS` is missing, explain how to create the service principal JSON, where to store it in Gitea Actions secrets, official documentation links, and validation commands.
7. Pass Azure output hostnames to `$configure-observability` only when monitoring should be wired.
