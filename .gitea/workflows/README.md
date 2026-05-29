# Gitea Actions Quality Gates

Gitea PR validation is the source of truth. Local hooks are only convenience checks for staged secrets and commit-message shape.

Coverage threshold defaults to `80%` from `.codex/quality.example.json`. Local development may override it with ignored `.codex/quality.local.json`; CI falls back to the tracked example when no local config is present.

The local runner executes PR validation inside a pinned .NET SDK container. PR validation installs PowerShell in the job container because repository delivery-tool tests execute `.ps1` helpers through `pwsh` on Linux. Keep checkout and security tools shell-based unless the job container explicitly includes `node`; JavaScript `uses:` actions can fail inside plain SDK containers. Validate runner compatibility after workflow changes:

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
- `AZURE_DEV_WEBAPP_NAME`
- `AZURE_DEV_WEBAPP_URL`
- `AZURE_QA_RESOURCE_GROUP`
- `AZURE_QA_WEBAPP_NAME`
- `AZURE_QA_WEBAPP_URL`
- `AZURE_PROD_RESOURCE_GROUP`
- `AZURE_PROD_WEBAPP_NAME`
- `AZURE_PROD_WEBAPP_URL`

Push-triggered deployments are ticket-gated by `.codex/delivery-policy.json`. Only commits or merged PR titles that start with the configured ticket key pattern may deploy. `[SDD]`, OpenSpec, chore, and ops-only maintenance changes do not deploy automatically.

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
feature branch -> dev -> DEV -> QA -> main -> PROD
```

The package workflow builds and publishes from ticket-gated application changes on `dev`, including a baseline `app/{commitSha}/release.json`. DEV and QA must deploy the same Nexus ZIP artifact for the same commit SHA. PROD must deploy the QA-approved Nexus artifact from an exact-commit `main` promotion or explicit dispatch by commit SHA and must pass both the page smoke check and `/health` check.
