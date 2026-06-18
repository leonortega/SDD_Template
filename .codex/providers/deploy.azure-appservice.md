# Deployment Adapter: Azure App Service

Use this adapter only when `.codex/project-profile.json` selects `providers.deployment.id = "azure-appservice"`.

## Runtime Configuration

- Read environment names and release policy from `.codex/project-profile.json`.
- Read local cloud configuration and secret locations from `.codex/client-tools.local.json` or CI secrets.
- Keep executable deployment behavior in `.gitea/workflows/*.yml` and `infra/azure/`.
- Keep exact image/tool versions in workflow and infrastructure files.

## Operations

- `deploy-artifact`: deploy the selected artifact from the artifact adapter without rebuilding.
- `apply-config`: apply generated deployment settings for each app/environment.
- `verify-config`: verify non-secret values and secret presence without printing secrets.
- `health`: run configured page and health checks.
- `record`: update release metadata and ticket comments through the selected adapters.

## Failure Rules

- Stop when deployment configuration is unmapped, manual, missing, or mismatched.
- Stop when smoke checks hit the wrong environment, a platform error page, or stale endpoints.
- Production promotion requires an existing QA-approved artifact and explicit release intent.
