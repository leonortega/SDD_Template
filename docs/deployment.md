# Deployment

Deployment is ticket-gated and artifact-based. The workflow promotes one immutable Nexus artifact through DEV, QA, PROD, and rollback paths without rebuilding between environments.

## Flow

```text
feature branch -> dev -> DEV -> QA -> main -> PROD
```

Push-triggered deployment is allowed only for ticket-named application changes under `src/**` or `tests/**`. The ticket key pattern is configured in `.codex/delivery-policy.json`; non-code changes outside those folders do not run automatic CI/deployment work.

## Technology Stack And Tool Set

Deployment tooling is intentionally local-first except for the application runtimes. Gitea Actions packages and deploys ticket-gated application changes, Nexus stores the exact artifact and `release.json`, Azure App Service hosts DEV/QA/PROD web and API runtimes, and local Grafana uses Azure Monitor plus Log Analytics for configured log and health visibility.

- Nexus paths under `app/{commitSha}/` are the durable artifact identity; environments must promote that same ZIP and checksum instead of rebuilding.
- Azure deployment uses App Service ZIP deployment from the existing Nexus artifact.
- The Blazor site project (`src/SDDTemplate.Site`) and REST API project (`src/SDDTemplate.Api`) are separated so Azure environments can host web and API App Service apps independently. The API references `src/SDDTemplate.Data` for EF Core entities, DbContext, migrations, and database setup.
- App Service diagnostic settings send logs to the matching DEV, QA, or PROD Log Analytics workspace using dedicated resource tables.
- Grafana dashboards are provisioned from tracked files and generated local-only dashboard files, and should query Azure Monitor without embedding secrets.
- Azure Monitor log validation is executable through `infra/monitoring/validate-azure-monitor-logs.ps1` after Grafana Azure service-principal values and environment workspace IDs are configured in ignored local env files. The script fails closed when required variables are absent or recent logs for any environment are not observed in Log Analytics.
- QA evidence is retained locally under ignored paths and preferably published to Nexus under `qa/{ticketKey}/{runId}/qa-evidence.zip`.
- Deployment guidance is mapped through `project-guidance-mapper`; missing deployment, observability, QA, security, release, or rollback skills and references are discovered by `project-guidance-discover`, copied only through `project-guidance-acquire` when they are confirmed skill items, and otherwise kept as local catalog guidance.

## Artifacts

Nexus stores artifacts by commit SHA:

```text
app/{commitSha}/deployable-apps.json
app/{commitSha}/{artifactName}
app/{commitSha}/{artifactName}.sha256
app/{commitSha}/commit.sha
app/{commitSha}/release.json
```

`commit.sha` must match the artifact commit. Every `{artifactName}.sha256` from `deployable-apps.json` must verify before deployment. `release.json` records ticket, representative artifact metadata, environment, QA, version, PROD, and rollback lineage. `planeTicketKey` remains the primary ticket for compatibility; optional `includedTickets` records all Done tickets included in a PROD release.

## Environments

DEV and QA deploy from `dev` and must use the same Nexus artifacts for the same commit SHA. The deploy workflow reads `infra/deployment/apps.json`, publishes one ZIP per deployable app, generates `deployment-config.json` from `infra/deployment/configuration.json` plus each app's `appsettings*.json`, deploys each ZIP to its matching Azure App Service app, and requires deployment configuration verification, rendered web API-base-url verification, API CORS preflight verification, web page checks, plus every app `/health` smoke check. After QA smoke checks pass, push a `qa/{ticketKey}` branch from current `dev`; Gitea Actions runs the committed Playwright QA E2E suite against `AZURE_QA_SITE_APP_URL` and `AZURE_QA_API_APP_URL` without redeploying, and stores evidence against the branch point artifact commit from `dev`. This job produces evidence only and does not move Plane state, create RC tags, or update release lineage. The `test-e2e` skill may move Plane to Done only when the QA result is `PASS`: every ticket acceptance criterion is mapped to executable assertions against the deployed QA artifact, relevant user workflow, API/backend effect, independent state, validation/boundary, error-handling, environment-correctness, and evidence-integrity checks are covered, and screenshots/logs/traces support rather than replace assertions. `PASS WITH GAPS` and `FAIL` leave the ticket in QA. After the E2E QA Plane comment is verified, E2E QA posts or patches the workflow timing comment from `.codex/agent-telemetry.local.jsonl`; PROD timing and PROD deployment comments remain part of the separate explicit PROD promotion step. After Nexus evidence exists, the E2E QA Plane comment is verified, the workflow timing comment is handled, the RC tag is created or verified, release metadata is updated, and Plane is Done, delete the remote `qa/{ticketKey}` branch from Gitea because the durable evidence is in Nexus, Plane, the release manifest, and tags.

Deployment configuration is fail-closed. New `appsettings*.json` keys must be mapped in `infra/deployment/configuration.json` before CI can deploy. Interactive configure runs should infer safe values or ask the developer for the mapping and exact secret/setup steps; CI must not guess missing required values. Initial Azure provisioning applies the same non-secret topology settings through explicit App Service appsettings resources, and package deployment reapplies and verifies them from `deployment-config.json`. Removed keys are drift findings and are not automatically deleted from live App Service settings without an explicit operator request.

PROD deploys only a QA-approved existing Nexus artifact. PROD does not rebuild. Promotion requires a final version, source RC version, verified artifact commit, included Done ticket list, and successful PROD web page plus web/API `/health` checks. E2E QA `PASS` closes each ticket as Done; PROD is a later explicit release event that may include one or more Done tickets. After successful PROD evidence is recorded, the workflow updates `release.json`, comments the PROD result on every included ticket, and runs a read-only post-PROD retrospective for the just-promoted release with per-ticket findings when useful. Sanitized learning evidence is stored in ignored `.codex/agent-evals/results.local.json` plus compact Plane markers. This retrospective is learning evidence for later workflow improvements, not a release gate.

## QA Evidence And Versions

E2E QA evidence is stored under ignored local paths:

```text
artifacts/qa/{ticketKey}/{runId}/
```

The preferred durable publication target is Nexus at:

```text
qa/{ticketKey}/{runId}/qa-evidence.zip
```

The Gitea-run QA E2E job also uploads its evidence bundle to the artifact commit path:

```text
app/{commitSha}/qa-e2e-evidence.zip
```

RC tags identify QA-approved artifacts. Final tags identify production releases. Release lineage should remain traceable as:

```text
artifact commit -> source RC version -> final release version
```

## Rollback And Hotfix

Rollback deploys a previously verified Nexus artifact and does not rewrite `main`. After rollback, the expected follow-up is a hotfix PR, revert PR, or explicit temporary divergence note with owner and resolution plan.
