# Azure Environment Configuration

Owns:

- `infra/azure/main.bicep`.
- `infra/azure/dev.parameters.json`.
- `infra/azure/qa.parameters.json`.
- `infra/azure/prod.parameters.json`.
- `infra/azure/deploy-environments.ps1`.
- DEV/QA/PROD App Service runtime and outputs.

## Defaults

- Resource groups: `rg-agentic-dev`, `rg-agentic-qa`, `rg-agentic-prod`.
- Location: `eastus`.
- SKU/tier: `B1` / `Basic`.
- SQLite path: `/home/data/app.db`.
- Current Bicep runtime defaults may be `DOTNETCORE|8.0`; for a .NET 10 app, ask whether to use a .NET 10 runtime when available or self-contained deployment.

## Prompting

Ask only for values that differ from defaults:

- Subscription/tenant context when deployment is requested.
- Resource group names.
- Location.
- App Service plan SKU/tier.
- Web/API runtime stack.
- SQLite database file name.

For PROD, warn that SQLite is appropriate only for low-concurrency single-instance workloads. Recommend Azure SQL or another managed database if PROD needs higher write concurrency, backups, or multi-instance scale-out.

## Gitea Actions Azure Login Secret

The package/deploy workflow uses `azure/login@v2` with `secrets.AZURE_CREDENTIALS`.

Official docs:

- Azure service principals with Azure CLI: https://learn.microsoft.com/en-us/cli/azure/azure-cli-sp-tutorial-1
- Azure Login with client secret: https://learn.microsoft.com/en-us/azure/developer/github/connect-from-azure-secret
- `az ad sp create-for-rbac`: https://learn.microsoft.com/en-us/cli/azure/ad/sp

Create a least-privilege service principal scoped to the DEV/QA/PROD resource groups. Prefer `Website Contributor` for App Service ZIP deployment instead of subscription-wide `Contributor`.

Safe local output path:

- `.codex/azure-login.local.json`
- Ensure this file is ignored before writing it.

Example:

```powershell
$subscriptionId = '<subscription-id>'
$scopes = @(
  "/subscriptions/$subscriptionId/resourceGroups/rg-agentic-dev",
  "/subscriptions/$subscriptionId/resourceGroups/rg-agentic-qa",
  "/subscriptions/$subscriptionId/resourceGroups/rg-agentic-prod"
)

az ad sp create-for-rbac `
  --name 'sp-sdd-template-gitea-actions' `
  --role 'Website Contributor' `
  --scopes $scopes `
  --json-auth |
  Out-File .codex/azure-login.local.json -Encoding utf8NoBOM
```

Store the complete JSON file contents as the Gitea Actions secret `AZURE_CREDENTIALS`. Do not paste the JSON into chat or tracked files.

## Gitea Actions App Service Secrets

The package/deploy workflow deploys DEV and QA from the same Nexus ZIP artifact. Store these values as Gitea Actions secrets:

- `AZURE_DEV_RESOURCE_GROUP`
- `AZURE_DEV_WEBAPP_NAME`
- `AZURE_DEV_WEBAPP_URL`
- `AZURE_QA_RESOURCE_GROUP`
- `AZURE_QA_WEBAPP_NAME`
- `AZURE_QA_WEBAPP_URL`

Use the Bicep deployment outputs for the web app names and URLs. Keep real Azure hostnames out of tracked files except placeholder-safe documentation.

Validation without exposing the secret:

```powershell
$cred = Get-Content .codex/azure-login.local.json -Raw | ConvertFrom-Json
az ad sp show --id $cred.clientId --query "{appId:appId,displayName:displayName,accountEnabled:accountEnabled}" -o json
az role assignment list --scope "/subscriptions/$($cred.subscriptionId)/resourceGroups/rg-agentic-dev" --query "[?principalName=='$($cred.clientId)'].{role:roleDefinitionName,scope:scope}" -o json
```

Smoke-test with an isolated Azure CLI profile so the user's active login is not replaced:

```powershell
$cred = Get-Content .codex/azure-login.local.json -Raw | ConvertFrom-Json
$tmp = Join-Path $env:TEMP ('az-sp-test-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $tmp | Out-Null
try {
  $env:AZURE_CONFIG_DIR = $tmp
  az login --service-principal --username $cred.clientId --password $cred.clientSecret --tenant $cred.tenantId --output none
  az account set --subscription $cred.subscriptionId
  az webapp show --resource-group rg-agentic-dev --name '<dev-web-app-name>' --query "{name:name,state:state}" -o json
} finally {
  Remove-Item Env:\AZURE_CONFIG_DIR -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
}
```

## Commands

Preview first unless the user explicitly asks to deploy directly:

```powershell
az account show
.\infra\azure\deploy-environments.ps1 -Location eastus -WhatIf
```

Deploy after approval:

```powershell
.\infra\azure\deploy-environments.ps1 -Location eastus
```

## Validation

- Report the active subscription name/id and tenant without exposing tokens.
- After deployment, check each output URL.
- Keep environment-specific Azure hostnames out of tracked files.
- Pass Azure outputs to observability only when the user wants monitoring wired to the new hostnames.
