# Gitea Actions Quality Gates

Gitea PR validation is the source of truth. Local hooks are only convenience checks for staged secrets and commit-message shape. Developers and agents should run targeted local checks for touched behavior, but they are not required to duplicate the full CI suite before opening or updating a PR.

Workflow jobs use repo-owned pinned images built by `config infra`:

- `agentic/dotnet-ci:10.0.300-tools-1` for PR validation, package, DEV/QA/PROD deployment, scanners, and Azure CLI work.
- `agentic/e2e-ci:playwright-1.57.0-1` for deployed-QA Playwright evidence runs.

Use the same E2E image for local QA diagnosis from `tests/SDDTemplate.E2ETests`:

```powershell
npm run test:docker
npm run test:docker:list
```

The Docker runner reads `E2E_SITE_URL`/`E2E_API_URL` or the ignored `.codex/client-tools.local.json` QA URL values and avoids host-level browser installs.

Run this after changing image Dockerfiles, image tags, or a runner machine:

```powershell
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode BuildGiteaActionsImages
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode ValidateGiteaActionsRunner
```

Coverage threshold defaults to `80%` from `.codex/quality.example.json`. Local development may override it with ignored `.codex/quality.local.json`; CI falls back to the tracked example when no local config is present.

The local runner executes PR validation inside a pinned .NET SDK container. PR validation triggers only for application code, tests, and root app build inputs such as `.editorconfig`, `Directory.Build.props`, `Directory.Build.targets`, `Directory.Packages.props`, `global.json`, `NuGet.config`, `SDDTemplate.slnx`, and `dotnet-tools.json`. It must target product/application projects specifically for restore, format, build, tests, coverage, and dependency audit. For this template, CI uses explicit `src/SDDTemplate.Site`, `src/SDDTemplate.Api`, and `tests/SDDTemplate.Site.Tests` project paths; SDD delivery-tool, workflow, agent, OpenSpec, infrastructure, workflow files, docs, and meta-tests remain local/template-maintenance checks and are not part of normal PR CI. Keep checkout and security tools shell-based unless the job container explicitly includes `node`; JavaScript `uses:` actions can fail inside plain SDK containers. Validate runner compatibility after workflow changes:

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

Push-triggered deployments are ticket-gated by `.codex/project-profile.json` `workflow.ticketKeyPattern`. Only commits or merged PR titles that start with the configured ticket key pattern may deploy, and automatic CI/deployment work is skipped when the change does not touch `src/**` or `tests/**`.

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

The package workflow reads `infra/deployment/apps.json`, rejects deployable project paths outside `src/`, builds one ZIP per deployable app, builds `deployment-config.json` from `infra/deployment/configuration.json` plus each app's `appsettings*.json`, and publishes the topology, deployment configuration, and app artifacts under `app/{commitSha}/` with a baseline `release.json`. Merge and deployment jobs focus on immutable artifact packaging, deployment configuration verification, checksum validation, and environment smoke checks; they do not rerun the same unit test suite already covered by PR validation unless package inputs changed outside that path. DEV, QA, and PROD apply and verify `deployment-config.json` before deployment success is claimed; missing or mismatched required settings fail closed. Smoke checks also verify that the clients page renders the expected API base URL and that API CORS preflight allows the matching web origin. DEV and QA must deploy the same Nexus artifacts for the same commit SHA. After QA deploy and smoke checks, the workflow publishes `app/{commitSha}/qa-targets.json` with the QA Site/API URLs so local Playwright diagnosis can discover the deployed target. Then push a `qa/{ticketKey}` branch from current `dev` to run the committed Playwright suite against the deployed QA Site/API URLs. Reusable Playwright tests should normally be added during implementation; the QA branch is primarily a remote evidence trigger. The `e2e-qa` job runs remotely without redeploying, resolves the artifact commit from the branch point with `dev`, and uploads `app/{commitSha}/qa-e2e-evidence.zip` plus a ticket/run evidence copy under `qa/{ticketKey}/{runId}/qa-e2e-evidence.zip`. This Gitea job is evidence-only; the `test-e2e` skill remains responsible for acceptance-to-assertion QA proof, Plane Done state, RC tagging, release manifest QA lineage, and deleting the remote `qa/{ticketKey}` branch after durable Nexus/Plane/release/tag evidence exists. Only full `PASS` can move Plane to Done; `PASS WITH GAPS` or `FAIL` remain in QA. PROD is an explicit release event that may include one or more Done tickets through `release.json.includedTickets`; it must deploy the QA-approved Nexus artifacts from an exact-commit `main` promotion or explicit dispatch by commit SHA, pass deployment configuration verification, rendered API base URL validation, CORS preflight validation, the web page smoke check, and every app `/health` check, then record the PROD result on every included ticket.

When adding a new appsetting, add a mapping to `infra/deployment/configuration.json`. Use topology references for values derived from another deployed app, literals for placeholder-safe values, `environmentSecret` for secret-backed values stored as Gitea Actions secrets, and `manualRequired` only as a temporary blocker while gathering the value.
