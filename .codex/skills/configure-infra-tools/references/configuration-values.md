# Configuration Values

Use this reference when asking the user for values. Ask for missing or unsafe values only, and explain how to get each value before requesting it.

## Step-by-Step Configuration Order

Configure the full environment in this order unless the user asks for a specific tool:

1. Plane: ticket management.
2. Gitea: source code repository and PR automation.
3. Gitea Actions runner: CI/CD execution.
4. Sonatype Nexus Repository Community Edition: artifact and package repository.
5. Azure DEV: app runtime, config, and SQLite DB.
6. Azure QA: app runtime, config, and SQLite DB.
7. Azure PROD: app runtime, config, and SQLite DB.
8. Prometheus: scrape app metrics.
9. Grafana: dashboards for local and Azure metrics.

Use only two phases:

- Pre-start: values required before local infra can start safely.
- Post-start: values obtained from running tools or used to complete implementation, deployment, CI/CD, monitoring, and dashboard flow.

Nexus stays before Azure because CI/CD artifact setup belongs before deployment flow. This repo uses Nexus for build artifacts/packages, not as the Azure image source. Azure remains App Service runtime/package deployment: the Bicep deploys App Service resources directly and does not configure container image pulls. Prometheus and Grafana stay after Azure because Azure app hostnames are needed for scrape targets and dashboards.

Ask one value at a time. For each value, explain:

- Which tool is being configured.
- Which key or Azure parameter will be updated.
- Where the user can obtain the value.
- Whether a default can be used.
- Whether the value is pre-start or post-start.
- Whether changing the value requires stopping and restarting local infra.

## Prerequisite Tool Installation

When a prerequisite executable is missing, show the user these steps before continuing. Use the official URL plus command and verification command.

### Git for Windows

Required for: repository inspection, branch creation, pushing branches to Gitea, and Gitea owner/repo inference.

Check:

```powershell
git --version
```

Install with WinGet:

```powershell
winget install --id Git.Git -e --source winget
```

Official URL: https://git-scm.com/install/windows

After install: close and reopen PowerShell, then run `git --version`.

### Docker Desktop for Windows

Required for: `.\infra\up.ps1`, `.\infra\down.ps1`, local Plane/Gitea/Nexus/Prometheus/Grafana services, and container-based live checks.

Check:

```powershell
docker --version
docker compose version
```

Install with WinGet:

```powershell
winget install --id Docker.DockerDesktop -e --source winget
```

Official URL: https://docs.docker.com/desktop/setup/install/windows-install/

After install:

```powershell
wsl --update
```

Then start Docker Desktop, wait until it reports that Docker is running, close and reopen PowerShell, and run:

```powershell
docker run hello-world
docker compose version
```

### Azure CLI for Windows

Required for: Azure DEV/QA/PROD validation, `az account show`, Bicep what-if, and Azure deployment.

Check:

```powershell
az version
az account show
```

Install with WinGet:

```powershell
winget install --exact --id Microsoft.AzureCLI
```

Official URL: https://learn.microsoft.com/en-us/cli/azure/install-azure-cli-windows

After install: close and reopen PowerShell, then run:

```powershell
az version
az login
az account show
```

If the user has multiple subscriptions, ask them to select the target subscription and provide the exact command:

```powershell
az account set --subscription "<subscription-id-or-name>"
```

## Codex Client Tool Config

Target file: `.codex/client-tools.local.json`

Tracked template: `.codex/client-tools.example.json`

Required values:

- `plane.baseUrl`: Plane web/API base URL. Template value is `replace-with-plane-base-url`. Get the real value from the browser URL used to open Plane.
- `plane.apiToken`: Plane personal access token. In Plane, log in, open Profile Settings, open Personal Access Tokens, create a token for the local agent workflow, copy it once, and store it only in local config or a local secret store.
- `plane.workspaceSlug`: Lowercase workspace slug from the Plane URL. Template value is `replace-with-plane-workspace-slug`.
- `plane.projectIdentifier`: Plane project key shown on tickets. Template value is `replace-with-plane-project-identifier`.
- `plane.todoState`: State name used for tickets ready to start. Template value is `replace-with-plane-todo-state`.
- `plane.inProgressState`: State name used after the agent starts work. Template value is `replace-with-plane-in-progress-state`.
- `plane.reviewState`: State name used after implementation opens and reviews a PR. Template value is `replace-with-plane-review-state`.
- `git.baseBranch`: Git base branch for ticket branches. Template value is `replace-with-base-branch`.
- `git.branchPrefix`: Branch prefix. Template value is `replace-with-branch-prefix`.
- `git.branchPattern`: Branch pattern. Must include `{ticketKeySlug}`. Default: `{prefix}/{ticketKeySlug}-{titleSlug}`.
- `git.maxBranchLength`: Maximum generated branch length. Default: `100`.
- `gitea.baseUrl`: Gitea web/API URL. Template value is `replace-with-gitea-base-url`.
- `gitea.apiToken`: Gitea personal access token used for PR creation, reviewer lookup, review comments, and labels. Create it in Gitea user settings and store it only in local config or a local secret store.
- `gitea.owner`: Repository owner. Needed when it cannot be inferred from `git remote get-url origin`.
- `gitea.repo`: Repository name. Needed when it cannot be inferred from `git remote get-url origin`.
- `pr.reviewers`: Either `"all"` or a JSON array of Gitea usernames. Template value is `replace-with-reviewers`.
- `pr.labels.enabled`: Whether the PR review workflow should create/apply labels. Default: `true`.
- `pr.labels.reviewed`: Label applied after the review agent posts a review. Template value is `replace-with-reviewed-label`.
- `pr.labels.needsTests`: Label applied when tests are missing or failing. Template value is `replace-with-needs-tests-label`.
- `pr.labels.needsChanges`: Label applied when actionable defects or blocking issues are found. Template value is `replace-with-needs-changes-label`.

Validation guidance:

- Confirm the local file has `plane.inProgressState`; add `In Progress` if missing and the user has no different state name.
- Confirm the local file has `plane.reviewState`; add `In Review` if missing and the user has no different review state name.
- Confirm the local file has `gitea` and `pr` sections; add defaults from `.codex/client-tools.example.json` when missing.
- Do not print `plane.apiToken` or `gitea.apiToken`.
- Use Plane API `GET /api/v1/users/me/` with the `X-API-Key` header only after infra is running.

Step-by-step prompts:

- Ask for `plane.apiToken` only if missing or placeholder.
  - How to get it: open Plane at `http://agentic.lvh.me:8080`, log in, open Profile Settings, choose Personal Access Tokens, create a token for local automation, and copy it once.
  - Phase: post-start.
  - Required for: listing tickets, starting tickets, moving ticket state, and live validation.
- Ask for `plane.workspaceSlug` if it is missing or set to `replace-with-plane-workspace-slug`.
  - How to get it: copy the lowercase slug from the Plane workspace URL path.
  - Phase: post-start.
  - Required for: all Plane project and ticket API calls.
- Ask for `plane.projectIdentifier` if it is missing or set to `replace-with-plane-project-identifier`.
  - How to get it: use the prefix before the dash in Plane ticket keys.
  - Phase: post-start.
  - Required for: resolving project-scoped tickets and states.

## Gitea PR Automation

Target file: `.codex/client-tools.local.json`

Required for implementation handoff and PR review:

- `gitea.apiToken`: Generate in Gitea user settings. The token needs repository access sufficient to create pull requests, read collaborators, create labels, apply labels, and create issue/PR comments.
- `gitea.owner` and `gitea.repo`: Needed when the Git origin URL is not parseable or when the local remote is unusual.
- `pr.reviewers`: Use `"all"` by default. Use an explicit list only when the project wants a fixed reviewer set, for example `["alice", "bob"]`.
- `pr.labels`: Leave enabled by default. The review agent creates missing labels before applying them.

Validation guidance:

- Treat `replace-with-gitea-api-token` as incomplete.
- If `pr.reviewers` is `"all"`, live validation should call the Gitea collaborators endpoint after infra is running and confirm at least one reviewer can be resolved.
- If `pr.reviewers` is an array, live validation should confirm each username exists in Gitea when practical.
- If labels are enabled, live validation may list repository labels and report which configured labels are missing; the review workflow can create them later.
- Do not create labels during configuration unless the user explicitly asks for live mutation.

Step-by-step prompts:

- Ask for `gitea.apiToken` only if missing or placeholder.
  - How to get it from UI: open Gitea at `http://localhost:3000`, log in, open user Settings, choose Applications, generate a token with repository, issue/PR, user, and organization read scopes, then copy it once.
  - How to get it from API when acceptable: use a user-authenticated Gitea API token creation endpoint or personal access token UI. Do not have Codex retrieve or generate this token from a Docker container, database, mounted volume, or logs.
  - Phase: post-start.
  - Required for: creating PRs, reading collaborators, adding comments, creating/applying labels, and PR review automation.
- Ask for `gitea.owner` and `gitea.repo` only if they cannot be inferred from `git remote get-url origin`.
  - How to get it: use the Gitea repository URL `http://localhost:3000/{owner}/{repo}`.
  - Phase: post-start.
  - Required for: all Gitea API calls.
- Ask for `pr.reviewers` only when `"all"` is not acceptable.
  - How to get it: use Gitea usernames from repository collaborators or organization members.
  - Phase: post-start.
  - Required for: reviewer assignment during PR creation.

## Plane Docker Env

Target file: `infra/plane/variables.env`

Tracked template: `infra/plane/variables.env.example`

Required local values:

- `DOMAIN_NAME`: Local Plane domain. Template value is `replace-with-plane-domain`.
- `LISTEN_HTTP_PORT`: Local HTTP port. Default: `8080`.
- `SITE_ADDRESS`: Public site address for Plane. Template value is `replace-with-plane-site-address`.
- `WEB_URL`: Plane web URL. Template value is `replace-with-plane-web-url`.
- `CORS_ALLOWED_ORIGINS`: Must include `WEB_URL`.
- `MACHINE_SIGNATURE`: Local machine signature. Generate with `[guid]::NewGuid().ToString()` or `openssl rand -hex 16`.
- `POSTGRES_PASSWORD`: Local Postgres password. Replace `plane` or placeholders with a generated local secret.
- `FOLLOWER_POSTGRES_URI`: Must contain the same Postgres password.
- `RABBITMQ_DEFAULT_PASS`: Local RabbitMQ password. Replace `plane` or placeholders with a generated local secret.
- `AMQP_URL`: Must contain the same RabbitMQ password and vhost.
- `SECRET_KEY`: Plane application secret. Generate a 32-byte hex secret.
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`: Local MinIO credentials. Replace `access-key`, `secret-key`, and placeholders.
- `SILO_HMAC_SECRET_KEY`, `AES_SECRET_KEY`, `LIVE_SERVER_SECRET_KEY`, `PI_INTERNAL_SECRET`: Generate local secrets if placeholders or weak defaults are present.

Post-start values:

- Provider API keys such as `OPENAI_API_KEY`, `CLAUDE_API_KEY`, `GROQ_API_KEY`, `COHERE_API_KEY`, and custom LLM settings. Ask only if the user wants Plane PI or AI features.
- OAuth integration values for GitHub, GitLab, and Slack. Ask only if enabling those integrations.

Validation guidance:

- Do not change tracked templates unless the user asks to improve defaults.
- Update dependent URI values when passwords change.
- Do not start infra automatically. Ask first before running `.\infra\up.ps1`.

## Gitea Runner

Target file: `infra/gitea/runner.env`

Tracked template: `infra/gitea/runner.env.example`

Required values:

- `GITEA_INSTANCE_URL`: URL visible from the runner container. Default: `http://gitea:3000`.
- `GITEA_RUNNER_REGISTRATION_TOKEN`: Registration token from Gitea. Get it from the Gitea admin/settings area for Actions runners after Gitea is running.
- `GITEA_RUNNER_NAME`: Runner name. Template value is `replace-with-runner-name`.

Validation guidance:

- Treat `replace-with-token-from-gitea` as incomplete.
- Runner token retrieval requires Gitea to be running; remind the user to run `.\infra\up.ps1` or ask whether Codex should run it.

Step-by-step prompts:

- Ask for `GITEA_RUNNER_REGISTRATION_TOKEN` only if missing or placeholder.
  - How to get it from UI: open Gitea at `http://localhost:3000`, open Site Administration or repository Actions runner settings, create/copy a runner registration token for the repository or instance.
  - How to get it from API when acceptable: use Gitea's supported admin/repository runner-token API with user-provided credentials or token. Do not have Codex retrieve or generate this token from a Docker container, database, mounted volume, or logs.
  - Phase: post-start.
  - Required for: registering the runner container.
- Ask for `GITEA_RUNNER_NAME` when it is missing or set to `replace-with-runner-name`.
  - How to choose it: use a stable local machine name that identifies this runner in Gitea Actions.
  - Phase: pre-start.
  - Required for: runner registration display and troubleshooting.

## Nexus

Compose file: `infra/nexus/compose.yml`

Local URL: `http://localhost:8088`

Nexus service startup uses Compose defaults pre-start. Nexus CI/CD values are post-start because they are obtained after the Nexus UI is running.

Default strategy for this repo:

- Use Nexus for build artifacts/packages published by Gitea Actions.
- Promote the same artifact to Azure DEV, QA, and PROD.
- Deploy to Azure App Service runtime apps using package/ZIP deployment or another App Service package deploy mechanism.
- Do not configure Azure to pull container images from Nexus in the default workflow.
- Do not require a Nexus Docker hosted registry unless the user explicitly changes the architecture to container-image deployment.

Step-by-step prompts:

- Ask for Nexus admin or service account username during the post-start Nexus step.
  - How to get it: open Nexus at `http://localhost:8088`; use the supported first-login or password-reset flow, then create a service account for automation. Ask the user to provide the username. Do not have Codex read the initial admin password from Docker containers, mounted volumes, databases, or logs.
  - Phase: post-start.
  - Required for: pushing artifacts/packages or configuring repositories.
- Ask for Nexus service account password or token during the post-start Nexus step.
  - How to get it: create or reset the service account credential in Nexus security settings.
  - Phase: post-start.
  - Required for: CI/CD publish jobs.
- Ask for repository names during the post-start Nexus step.
  - Defaults: create hosted package/artifact repositories as needed for the app stack, for example `raw-hosted`, `nuget-hosted`, `npm-hosted`, or `maven-releases`.
  - Phase: post-start.
  - Required for: wiring Gitea Actions publish steps.

Gitea Actions settings for Option A:

- Store Nexus service credentials as Gitea Actions secrets, not tracked files.
- Typical secret names:
  - `NEXUS_URL`
  - `NEXUS_USERNAME`
  - `NEXUS_PASSWORD`
  - `NEXUS_REPOSITORY`
- Build the deployable artifact once, publish it to Nexus, then deploy or promote that same artifact to Azure environments.

Azure settings for Option A:

- Keep `infra/azure/main.bicep` using runtime stacks such as `DOTNETCORE|8.0`.
- Do not set App Service container image settings, registry URL, registry username, or registry password.
- Azure deployment credentials are separate from Nexus credentials and should be configured through Azure-supported auth for CI/CD.

Do not write Nexus credentials into tracked files. Prefer Gitea Actions secrets, local secret storage, or ignored local config if a future local file is added.

## Monitoring

Files:

- `infra/monitoring/prometheus.yml`
- `infra/monitoring/prometheus.local.yml`
- `infra/monitoring/grafana/provisioning/datasources/prometheus.yml`
- `infra/monitoring/grafana/provisioning/dashboards/dashboards.yml`
- `infra/monitoring/grafana/dashboards/local-infra-health.json`
- `infra/monitoring/grafana/dashboards/azure-app-health.json`

Runtime mount setting:

- `PROMETHEUS_CONFIG_FILE` in `infra/plane/variables.env`
- Tracked default: `./prometheus.yml`
- Local value after Azure targets exist: `./prometheus.local.yml`

Local URLs:

- Dozzle: `http://localhost:8888`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3001`

Known placeholders:

- `replace-dev-web.azurewebsites.net`
- `replace-dev-api.azurewebsites.net`
- `replace-qa-web.azurewebsites.net`
- `replace-qa-api.azurewebsites.net`
- `replace-prod-web.azurewebsites.net`
- `replace-prod-api.azurewebsites.net`

Ask for Azure app hostnames only after Azure apps exist. Until then, report these as expected placeholders, not blocking local infra startup.

Do not configure Prometheus Azure targets or Grafana Azure dashboards until Azure DEV, QA, and PROD outputs are available.

Use `infra/monitoring/prometheus.yml` only as the tracked placeholder-safe template. Store real Azure hostnames in ignored `infra/monitoring/prometheus.local.yml`. Keep `infra/monitoring/prometheus.local.yml` out of commits.

Prometheus step-by-step prompts:

- Ask whether to use a local Prometheus runtime config file once Azure hostnames exist.
  - Default tracked value: `PROMETHEUS_CONFIG_FILE=./prometheus.yml`.
  - Local runtime value: `PROMETHEUS_CONFIG_FILE=./prometheus.local.yml`.
  - How to set it: update ignored `infra/plane/variables.env`, then recreate Prometheus so Docker applies the mount.
  - Phase: pre-start for the mount source, post-start for target content.
  - Required for: using real Azure targets without exposing hostnames in tracked files.
- Ask for local app metrics targets only when an app exposes metrics outside the default Prometheus target.
  - How to get it: use the Docker Compose service name and metrics port, for example `api:8080`, and confirm the app serves `/metrics`.
  - Phase: post-start.
  - Required for: local app metrics scraping.
- Ask for Azure app metrics hostnames after Azure deployment.
  - How to get it: use Bicep outputs `webAppUrl` and `apiAppUrl`, then remove `https://` to get Prometheus target hostnames.
  - Phase: post-start.
  - Required for: Azure app metrics scraping.
- Ask for a non-default metrics path only if the app does not expose `/metrics`.
  - How to get it: read the app's metrics middleware/configuration.
  - Phase: post-start.
  - Required for: Prometheus scrape configuration.

Useful command to set Azure targets:

```powershell
$values = @{
  targets = @(
    "<dev-web-host>.azurewebsites.net",
    "<dev-api-host>.azurewebsites.net",
    "<qa-web-host>.azurewebsites.net",
    "<qa-api-host>.azurewebsites.net",
    "<prod-web-host>.azurewebsites.net",
    "<prod-api-host>.azurewebsites.net"
  )
} | ConvertTo-Json -Depth 5
.\.codex\skills\configure-infra-tools\scripts\configure_infra_tools.ps1 -Mode SetPrometheusAzureTargets -ValuesJson $values
```

Useful Prometheus validation:

```powershell
docker inspect agentic-prometheus --format '{{range .Mounts}}{{println .Source "=>" .Destination}}{{end}}'
Invoke-RestMethod -Uri 'http://localhost:9090/api/v1/targets'
```

Grafana step-by-step prompts:

- Ask whether to rotate the default Grafana admin password.
  - Default local credentials: username `admin`, password `admin`.
  - How to change it: set `GF_SECURITY_ADMIN_PASSWORD` in `infra/monitoring/compose.yml` or rotate it in the Grafana UI at `http://localhost:3001`.
  - Phase: pre-start when changing Compose before startup, otherwise post-start when rotating in the UI.
  - Required for: any shared or non-local dashboard use.
- Ask whether dashboards should include Azure metrics.
  - How to get values: use Prometheus job `azure-apps` after Azure app hostnames are configured; use Azure Monitor workspace/query credentials only if the user explicitly wants direct Azure Monitor dashboards.
  - Phase: post-start.
  - Required for: Azure dashboard panels beyond Prometheus-scraped `/metrics`.
- Ask for dashboard import JSON only if the user has a preferred dashboard.
  - How to get it: export JSON from Grafana dashboard settings or provide a dashboard ID from Grafana.com.
  - Phase: post-start.
  - Required for: custom dashboard setup.

Default repo-managed dashboards:

- `Local Infra Health`: checks `up{job="prometheus"}`.
- `Azure App Health`: checks `up{job="azure-apps"}`.

Useful Grafana validation:

```powershell
Invoke-RestMethod -Uri 'http://localhost:3001/api/health'
docker logs --since 2m agentic-grafana 2>&1 | Select-String -Pattern 'provisioning.dashboard|finished to provision dashboards|level=error'
```

## Azure

Files:

- `infra/azure/main.bicep`
- `infra/azure/dev.parameters.json`
- `infra/azure/qa.parameters.json`
- `infra/azure/prod.parameters.json`
- `infra/azure/deploy-environments.ps1`

Current parameters:

- `environmentName`: fixed per file as `dev`, `qa`, or `prod`.
- `location`: defaults to the resource group location.
- `projectName`: defaults to `agentic-e2e`.
- `appServicePlanSkuName`: defaults to `B1`.
- `appServicePlanSkuTier`: defaults to `Basic`.
- `webRuntimeStack`: defaults to `DOTNETCORE|8.0`.
- `apiRuntimeStack`: defaults to `DOTNETCORE|8.0`.
- `sqliteDatabaseFileName`: defaults to `app.db`.

Resource model:

- Create one resource group per environment by default:
  - DEV: `rg-agentic-dev`
  - QA: `rg-agentic-qa`
  - PROD: `rg-agentic-prod`
- Deploy the same Bicep template to each resource group.
- Each environment contains one Linux App Service plan, one Linux Web App, and one Linux REST API App.
- The REST API uses SQLite through app settings:
  - `DATABASE_PROVIDER=sqlite`
  - `SQLITE_DB_PATH=/home/data/app.db`
  - `WEBSITES_ENABLE_APP_SERVICE_STORAGE=true`
- The Web App receives REST API URL app settings:
  - `REST_API_BASE_URL`
  - `VITE_API_BASE_URL`
  - `NEXT_PUBLIC_API_BASE_URL`

SQLite guidance:

- Treat SQLite on App Service as a simple/small-environment data store, not a high-concurrency production database.
- Keep the SQLite file under `/home` so it uses App Service persistent storage.
- Do not mount or store SQLite in Blob Storage.
- If PROD needs higher write concurrency, backups, or multi-instance scale-out, recommend migrating to Azure SQL or another managed database before increasing scale.

Ask for:

- Azure subscription or tenant context if the user wants deployment commands.
  - How to get it: run `az account show` locally or open Azure Portal, then confirm the subscription name/id and tenant.
  - Phase: post-start.
  - Required for: live deployment.
- Resource group names if they differ from `rg-agentic-dev`, `rg-agentic-qa`, and `rg-agentic-prod`.
  - How to choose them: use one group per environment, usually `rg-<project>-<env>`.
  - Phase: post-start.
  - Required for: deployment.
- Location if `eastus` is not acceptable.
  - How to choose it: use the Azure region closest to users or required by policy, for example `eastus`, `westus2`, or `eastus2`.
  - Phase: post-start.
  - Required for: resource group creation.
- SKU/tier if `B1`/`Basic` is not acceptable.
  - How to choose it: use Basic for always-on low-cost workloads; move to Standard/Premium when scale, slots, or production features are needed.
  - Phase: post-start.
  - Required for: App Service plan creation.
- Runtime stack if `DOTNETCORE|8.0` is not correct for the web app or REST API.
  - How to get it: match the application framework and Azure App Service supported runtime stack.
  - Phase: post-start.
  - Required for: App Service startup.
- SQLite database file name if `app.db` is not acceptable.
  - How to choose it: use a stable file name under `/home/data`; do not include secrets.
  - Phase: post-start.
  - Required for: API database configuration.

Per-environment prompts:

- DEV:
  - Ask whether to use defaults: resource group `rg-agentic-dev`, location `eastus`, SKU `B1`/`Basic`, SQLite path `/home/data/app.db`.
  - Required for: developer integration and early validation.
- QA:
  - Ask whether to use defaults: resource group `rg-agentic-qa`, location `eastus`, SKU `B1`/`Basic`, SQLite path `/home/data/app.db`.
  - Required for: pre-production validation.
- PROD:
  - Ask whether to use defaults: resource group `rg-agentic-prod`, location `eastus`, SKU `B1`/`Basic`, SQLite path `/home/data/app.db`.
  - Required for: production runtime.
  - Before accepting SQLite for PROD, remind the user that SQLite is best for low-concurrency single-instance workloads and ask whether that is acceptable.

Useful preview command:

```powershell
az account show
.\infra\azure\deploy-environments.ps1 -Location eastus -WhatIf
```

Useful create/update command after approval:

```powershell
.\infra\azure\deploy-environments.ps1 -Location eastus
```

Validation guidance:

- Run `az account show` before deployment and report the active subscription without exposing tokens.
- Use `-WhatIf` first unless the user explicitly asked to deploy directly.
- After deployment, check each output URL with `Invoke-WebRequest`; a default App Service landing page is acceptable before app packages are deployed.
- Update ignored `infra/monitoring/prometheus.local.yml` Azure targets only when the user asks to wire monitoring to the new hostnames.
- Keep tracked `infra/monitoring/prometheus.yml` placeholder-safe and free of environment-specific Azure hostnames.
- Run Azure commands only when the user asks for Azure validation, planning, or deployment.
