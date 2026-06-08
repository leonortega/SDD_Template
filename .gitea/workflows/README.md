# Gitea Actions Quality Gates

Gitea PR validation is the source of truth. Local hooks are only convenience checks for staged secrets and commit-message shape.

Coverage threshold defaults to `80%` from `.codex/quality.example.json`. Local development may override it with ignored `.codex/quality.local.json`; CI falls back to the tracked example when no local config is present.

The local runner executes PR validation inside a pinned .NET SDK container. PR validation installs PowerShell in the job container because repository delivery-tool tests execute `.ps1` helpers through `pwsh` on Linux. The install step derives the Microsoft package feed from `/etc/os-release` because pinned .NET SDK containers may be Ubuntu even though they are Debian-like. Keep checkout and security tools shell-based unless the job container explicitly includes `node`; JavaScript `uses:` actions can fail inside plain SDK containers. Validate runner compatibility after workflow changes:

```powershell
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode ValidateGiteaActionsRunner
```

That check pulls the configured job image, verifies required tools inside it, and confirms the container can reach local Gitea through `host.docker.internal`.

Required repository secrets:

- `NEXUS_URL` - use `http://host.docker.internal:8088` for local Docker Desktop runner jobs.
- `NEXUS_USERNAME`
- `NEXUS_PASSWORD`
- `NEXUS_REPOSITORY`
- `AZURE_CREDENTIALS`
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

Push-triggered deployments are ticket-gated by `.codex/delivery-policy.json`. Only commits or merged PR titles that start with the configured ticket key pattern may deploy, and automatic CI/deployment work is skipped when the change does not touch `src/**` or `tests/**`.

DEV and QA deploy only from `dev` when application/test/package source changed. PROD deploys only from `main` when `main` points to the exact QA-approved packaged commit for the same ticket-gated application change. Manual workflow dispatch remains available for explicit DEV/QA/PROD promotion; PROD dispatch must pass an existing `artifact_commit_sha`, `release_version`, and `source_rc_version`. The PROD job downloads the existing Nexus artifact and does not rebuild.

Recommended branch protection:

- Block direct pushes to `dev` and `main`.
- Require pull requests into `dev`.
- Update `main` only after QA passes, preferably by fast-forwarding the tested commit.
- Require the PR validation workflow to pass.
- Require the exact emitted status check context: `PR validation / validate (pull_request)`.
- Require coverage to meet the configured threshold.
- Require review approval or the configured review label.
- Block merge while `needs-changes` is present.

Release flow:

```text
feature branch -> dev -> DEV -> QA -> Gitea E2E evidence -> Plane E2E QA -> main -> PROD
```

The package workflow reads `infra/deployment/apps.json`, builds one ZIP per deployable app, builds `deployment-config.json` from `infra/deployment/configuration.json` plus each app's `appsettings*.json`, and publishes the topology, deployment configuration, and app artifacts under `app/{commitSha}/` with a baseline `release.json`. DEV, QA, and PROD apply and verify `deployment-config.json` before deployment success is claimed; missing or mismatched required settings fail closed. Smoke checks also verify that the clients page renders the expected API base URL and that API CORS preflight allows the matching web origin. DEV and QA must deploy the same Nexus artifacts for the same commit SHA. After QA deploy and smoke checks, push a `qa/{ticketKey}` branch from current `dev` to run the committed Playwright suite against the deployed QA Site/API URLs. The `e2e-qa-branch` job runs remotely without redeploying, resolves the artifact commit from the branch point with `dev`, and uploads `app/{commitSha}/qa-e2e-evidence.zip` plus a ticket/run evidence copy under `qa/{ticketKey}/{runId}/qa-e2e-evidence.zip`. This Gitea job is evidence-only; the `test-e2e` skill remains responsible for acceptance-to-assertion QA proof, Plane Done state, RC tagging, release manifest QA lineage, and deleting the remote `qa/{ticketKey}` branch after durable Nexus/Plane/release/tag evidence exists. Only full `PASS` can move Plane to Done; `PASS WITH GAPS` or `FAIL` remain in QA. PROD must deploy the QA-approved Nexus artifacts from an exact-commit `main` promotion or explicit dispatch by commit SHA and must pass deployment configuration verification, rendered API base URL validation, CORS preflight validation, the web page smoke check, and every app `/health` check.

When adding a new appsetting, add a mapping to `infra/deployment/configuration.json`. Use topology references for values derived from another deployed app, literals for placeholder-safe values, `environmentSecret` for secret-backed values stored as Gitea Actions secrets, and `manualRequired` only as a temporary blocker while gathering the value.
