# Azure Environment Configuration

Owns:

- `infra/deployment/apps.json`.
- `infra/deployment/configuration.json`.
- `infra/deployment/configuration.schema.json`.
- `infra/azure/main.bicep`.
- `infra/azure/dev.parameters.json`.
- `infra/azure/qa.parameters.json`.
- `infra/azure/prod.parameters.json`.
- `python -m tools.sdd_cli azure deploy-environments`.
- DEV/QA/PROD App Service runtime and outputs.
- Deployment Topology Review for deployable apps and `appsettings*.json` to App Service setting mappings.
- Deployment configuration drift prevention through the generated `deployment-config.json` Nexus artifact.

## Defaults

- Resource groups: `rg-agentic-dev`, `rg-agentic-qa`, `rg-agentic-prod`.
- Location: `westcentralus` (default). Use a different location only when explicitly required.
- SKU/tier: `B1` / `Basic`.
- SQLite path: `/home/data/app.db`.
- Runtime stack: `DOTNETCORE|10.0`.
- Manifest app ids: lowercase app ids from `infra/deployment/apps.json`; current defaults are `site` and `api`.

## Prompting

Ask only for values that differ from defaults:

- Subscription/tenant context when deployment is requested.
- Resource group names.
- Location.
- App Service plan SKU/tier.
- Runtime stack.
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

```bash
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

## Deployment Topology Review

Run this review when changes touch deployable projects, `Program.cs`, `appsettings*.json`, Azure infrastructure, or the package/deploy workflow.

- Detect deployable projects by `Microsoft.NET.Sdk.Web` under `src/**`.
- Classify selected UI projects as `web` and endpoint-only projects as `api`.
- Keep `infra/deployment/apps.json` aligned with app id, project path, role, artifact name, health path, deploy order, and dependencies.
- Flatten appsettings keys into App Service settings using double underscores.
- Infer known values between apps, including `Api__BaseUrl`, `Cors__AllowedOrigins__0`, and `ConnectionStrings__ClientsDb`.
- Record mappings in `infra/deployment/configuration.json` and generate `deployment-config.json` during packaging.
- Apply inferred app-to-app settings during initial Azure provisioning with explicit App Service appsettings resources, then apply and verify the same values again from `deployment-config.json` during package deployment.
- Smoke checks should validate the rendered web configuration and browser path: the clients page must render the expected API base URL and the API must accept CORS preflight from the matching web origin.
- Use placeholder-safe mappings or exact manual setup instructions for unknown values. In chat, ask the developer for the mapping choice or tell them where to create the Gitea secret or find the Azure value; never ask for raw secret values.
- CI deploys fail closed when a required discovered appsetting is unmapped, marked `manualRequired`, missing from live App Service settings, or mismatched.
- Removed keys are drift findings only; do not automatically delete live App Service settings without an explicit operator request.

## Gitea Actions App Service Secrets

The package/deploy workflow deploys DEV and QA from the same Nexus ZIP artifact on ticket-gated `dev` pushes. PROD promotion downloads the QA-approved artifact by commit SHA and does not rebuild. A ticket-gated `main` push is valid only when `main` points to the exact QA-approved packaged commit; otherwise use explicit PROD dispatch with `artifact_commit_sha`. Store these values as Gitea Actions secrets:

- `AZURE_DEV_RESOURCE_GROUP`
- `AZURE_DEV_SITE_APP_NAME`
- `AZURE_DEV_SITE_APP_URL`
- `AZURE_DEV_API_APP_NAME`
- `AZURE_DEV_API_APP_URL`
- `AZURE_QA_RESOURCE_GROUP`
- `AZURE_QA_SITE_APP_NAME`
- `AZURE_QA_SITE_APP_URL`
- `AZURE_QA_API_APP_NAME`
- `AZURE_QA_API_APP_URL`
- `AZURE_PROD_RESOURCE_GROUP`
- `AZURE_PROD_SITE_APP_NAME`
- `AZURE_PROD_SITE_APP_URL`
- `AZURE_PROD_API_APP_NAME`
- `AZURE_PROD_API_APP_URL`

Use the Bicep deployment outputs for app names and URLs. Keep real Azure hostnames out of tracked files except placeholder-safe documentation.

Validation without exposing the secret:

```bash
$cred = Get-Content .codex/azure-login.local.json -Raw | ConvertFrom-Json
az ad sp show --id $cred.clientId --query "{appId:appId,displayName:displayName,accountEnabled:accountEnabled}" -o json
az role assignment list --scope "/subscriptions/$($cred.subscriptionId)/resourceGroups/rg-agentic-dev" --query "[?principalName=='$($cred.clientId)'].{role:roleDefinitionName,scope:scope}" -o json
```

Smoke-test with an isolated Azure CLI profile so the user's active login is not replaced:

```bash
$cred = Get-Content .codex/azure-login.local.json -Raw | ConvertFrom-Json
$tmp = Join-Path $env:TEMP ('az-sp-test-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $tmp | Out-Null
try {
  $env:AZURE_CONFIG_DIR = $tmp
  az login --service-principal --username $cred.clientId --password $cred.clientSecret --tenant $cred.tenantId --output none
  az account set --subscription $cred.subscriptionId
  az webapp show --resource-group rg-agentic-dev --name '<dev-site-app-name>' --query "{name:name,state:state}" -o json
} finally {
  Remove-Item Env:\AZURE_CONFIG_DIR -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
}
```

## Commands

Preview first unless the user explicitly asks to deploy directly:

```bash
az account show
python -m tools.sdd_cli azure deploy-environments --location westcentralus --what-if
```

Deploy after approval:

```bash
python -m tools.sdd_cli azure deploy-environments --location westcentralus
```

## Validation

- Report the active subscription name/id and tenant without exposing tokens.
- After deployment, check each output URL.
- Deployment validation must include every manifest app `/health` endpoint for DEV, QA, and PROD. PROD success requires web page smoke and all app `/health` checks to pass.
- Multi-app validation must also check rendered `Api__BaseUrl` on the web app and CORS preflight from the web origin to the API app.
- Keep environment-specific Azure hostnames out of tracked files.
- Pass Azure outputs to observability only when the user wants monitoring wired to the new hostnames.
