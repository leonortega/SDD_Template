# Configuration Values

Use this reference when asking the user for values. Ask for missing or unsafe values only, and explain how to get each value before requesting it.

## Codex Client Tool Config

Target file: `.codex/client-tools.local.json`

Tracked template: `.codex/client-tools.example.json`

Required values:

- `plane.baseUrl`: Plane web/API base URL. Default for this repo is `http://agentic.lvh.me:8080`. Get it from the browser URL used to open Plane.
- `plane.apiToken`: Plane personal access token. In Plane, log in, open Profile Settings, open Personal Access Tokens, create a token for the local agent workflow, copy it once, and store it only in local config or a local secret store.
- `plane.workspaceSlug`: Lowercase workspace slug from the Plane URL. For example, in `/e2etest/...`, use `e2etest`.
- `plane.projectIdentifier`: Plane project key shown on tickets, such as `E2EPROJECT`.
- `plane.todoState`: State name used for tickets ready to start. Default: `Todo`.
- `plane.inProgressState`: State name used after the agent starts work. Default: `In Progress`.
- `plane.reviewState`: State name used after implementation opens and reviews a PR. Default: `In Review`.
- `git.baseBranch`: Git base branch for ticket branches. Default in this repo: `dev`.
- `git.branchPrefix`: Branch prefix. Default: `feat`.
- `git.branchPattern`: Branch pattern. Must include `{ticketKeySlug}`. Default: `{prefix}/{ticketKeySlug}-{titleSlug}`.
- `git.maxBranchLength`: Maximum generated branch length. Default: `100`.
- `gitea.baseUrl`: Gitea web/API URL. Default: `http://localhost:3000`.
- `gitea.apiToken`: Gitea personal access token used for PR creation, reviewer lookup, review comments, and labels. Create it in Gitea user settings and store it only in local config or a local secret store.
- `gitea.owner`: Repository owner. Leave empty to infer from `git remote get-url origin` when possible.
- `gitea.repo`: Repository name. Leave empty to infer from `git remote get-url origin` when possible.
- `pr.reviewers`: Either `"all"` or a JSON array of Gitea usernames. `"all"` means list repository collaborators/developers from Gitea and request all except the PR author and automation user.
- `pr.labels.enabled`: Whether the PR review workflow should create/apply labels. Default: `true`.
- `pr.labels.reviewed`: Label applied after the review agent posts a review. Default: `codex-reviewed`.
- `pr.labels.needsTests`: Label applied when tests are missing or failing. Default: `needs-tests`.
- `pr.labels.needsChanges`: Label applied when actionable defects or blocking issues are found. Default: `needs-changes`.

Validation guidance:

- Confirm the local file has `plane.inProgressState`; add `In Progress` if missing and the user has no different state name.
- Confirm the local file has `plane.reviewState`; add `In Review` if missing and the user has no different review state name.
- Confirm the local file has `gitea` and `pr` sections; add defaults from `.codex/client-tools.example.json` when missing.
- Do not print `plane.apiToken` or `gitea.apiToken`.
- Use Plane API `GET /api/v1/users/me/` with the `X-API-Key` header only after infra is running.

## Gitea PR Automation

Target file: `.codex/client-tools.local.json`

Required for implementation handoff and PR review:

- `gitea.apiToken`: Generate in Gitea user settings. The token needs repository access sufficient to create pull requests, read collaborators, create labels, apply labels, and create issue/PR comments.
- `gitea.owner` and `gitea.repo`: Optional if the Git origin URL is parseable, but useful when the local remote is unusual.
- `pr.reviewers`: Use `"all"` by default. Use an explicit list only when the project wants a fixed reviewer set, for example `["alice", "bob"]`.
- `pr.labels`: Leave enabled by default. The review agent creates missing labels before applying them.

Validation guidance:

- Treat `replace-with-gitea-api-token` as incomplete.
- If `pr.reviewers` is `"all"`, live validation should call the Gitea collaborators endpoint after infra is running and confirm at least one reviewer can be resolved.
- If `pr.reviewers` is an array, live validation should confirm each username exists in Gitea when practical.
- If labels are enabled, live validation may list repository labels and report which configured labels are missing; the review workflow can create them later.
- Do not create labels during configuration unless the user explicitly asks for live mutation.

## Plane Docker Env

Target file: `infra/plane/variables.env`

Tracked template: `infra/plane/variables.env.example`

Required local values:

- `DOMAIN_NAME`: Local Plane domain. Default: `agentic.lvh.me`.
- `LISTEN_HTTP_PORT`: Local HTTP port. Default: `8080`.
- `SITE_ADDRESS`: Public site address for Plane. Default: `http://agentic.lvh.me`.
- `WEB_URL`: Plane web URL. Default: `http://agentic.lvh.me:8080`.
- `CORS_ALLOWED_ORIGINS`: Must include `WEB_URL`.
- `MACHINE_SIGNATURE`: Local machine signature. Generate with `[guid]::NewGuid().ToString()` or `openssl rand -hex 16`.
- `POSTGRES_PASSWORD`: Local Postgres password. Replace `plane` or placeholders with a generated local secret.
- `FOLLOWER_POSTGRES_URI`: Must contain the same Postgres password.
- `RABBITMQ_DEFAULT_PASS`: Local RabbitMQ password. Replace `plane` or placeholders with a generated local secret.
- `AMQP_URL`: Must contain the same RabbitMQ password and vhost.
- `SECRET_KEY`: Plane application secret. Generate a 32-byte hex secret.
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`: Local MinIO credentials. Replace `access-key`, `secret-key`, and placeholders.
- `SILO_HMAC_SECRET_KEY`, `AES_SECRET_KEY`, `LIVE_SERVER_SECRET_KEY`, `PI_INTERNAL_SECRET`: Generate local secrets if placeholders or weak defaults are present.

Optional values:

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
- `GITEA_RUNNER_NAME`: Runner name. Default: `agentic-local-runner`.

Validation guidance:

- Treat `replace-with-token-from-gitea` as incomplete.
- Runner token retrieval requires Gitea to be running; remind the user to run `.\infra\up.ps1` or ask whether Codex should run it.

## Nexus

Compose file: `infra/nexus/compose.yml`

Local URL: `http://localhost:8088`

Values usually do not need local config in this repo. If the workflow needs publish credentials, ask the user whether they want to use Nexus's initial admin password, create a service account, or keep artifact publishing disabled for now.

## Monitoring

Files:

- `infra/monitoring/prometheus.yml`
- `infra/monitoring/grafana/provisioning/datasources/prometheus.yml`

Local URLs:

- Dozzle: `http://localhost:8888`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3001`

Known placeholders:

- `replace-dev-app.azurewebsites.net`
- `replace-qa-app.azurewebsites.net`
- `replace-prod-app.azurewebsites.net`

Ask for Azure app hostnames only after Azure apps exist. Until then, report these as expected placeholders, not blocking local infra startup.

## Azure

Files:

- `infra/azure/main.bicep`
- `infra/azure/dev.parameters.json`
- `infra/azure/qa.parameters.json`
- `infra/azure/prod.parameters.json`

Current parameters:

- `environmentName`: fixed per file as `dev`, `qa`, or `prod`.
- `location`: defaults to the resource group location.
- `projectName`: defaults to `agentic-e2e`.

Ask for:

- Azure subscription or tenant context if the user wants deployment commands.
- Resource group names if they differ from `rg-agentic-dev`, `rg-agentic-qa`, and `rg-agentic-prod`.
- Location if the resource group does not already exist.

Useful commands after user approval:

```powershell
az account show
az group show --name rg-agentic-dev
az deployment group what-if --resource-group rg-agentic-dev --template-file .\infra\azure\main.bicep --parameters .\infra\azure\dev.parameters.json
```

Run Azure commands only when the user asks for Azure validation or deployment planning.
