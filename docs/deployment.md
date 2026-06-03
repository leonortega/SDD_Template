# Deployment

Deployment is ticket-gated and artifact-based. The workflow promotes one immutable Nexus artifact through DEV, QA, PROD, and rollback paths without rebuilding between environments.

## Flow

```text
feature branch -> dev -> DEV -> QA -> main -> PROD
```

Push-triggered deployment is allowed only for ticket-named application changes. The ticket key pattern is configured in `.codex/delivery-policy.json`. `[SDD]`, OpenSpec-only, chore, and ops-only maintenance commits do not deploy environments automatically.

## Technology Stack And Tool Set

Deployment tooling is intentionally local-first except for the application runtimes. Gitea Actions packages and deploys ticket-gated application changes, Nexus stores the exact artifact and `release.json`, Azure App Service hosts DEV/QA/PROD web and API runtimes, and Prometheus/Grafana verify configured health visibility.

- Nexus paths under `app/{commitSha}/` are the durable artifact identity; environments must promote that same ZIP and checksum instead of rebuilding.
- Azure deployment uses App Service ZIP deployment from the existing Nexus artifact.
- The Blazor site project (`src/SDDTemplate.Site`) and REST API project (`src/SDDTemplate.Api`) are separated so Azure environments can host web and API App Service apps independently. The API references `src/SDDTemplate.Data` for EF Core entities, DbContext, migrations, and database setup.
- Prometheus scrapes local infrastructure and configured Azure app `/health` targets.
- Grafana dashboards are provisioned from tracked files and should visualize Prometheus data without embedding secrets.
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

`commit.sha` must match the artifact commit. Every `{artifactName}.sha256` from `deployable-apps.json` must verify before deployment. `release.json` records ticket, representative artifact metadata, environment, QA, version, PROD, and rollback lineage.

## Environments

DEV and QA deploy from `dev` and must use the same Nexus artifacts for the same commit SHA. The deploy workflow reads `infra/deployment/apps.json`, publishes one ZIP per deployable app, deploys each ZIP to its matching Azure App Service app, and requires web page checks plus every app `/health` smoke check. After QA smoke checks pass, Gitea Actions runs the committed Playwright QA E2E suite against `AZURE_QA_SITE_APP_URL` and `AZURE_QA_API_APP_URL`; this job produces evidence only and does not move Plane state, create RC tags, or update release lineage. When QA-specific tests need to be created after the ticket is already in QA, push them to a `qa/{ticketKey}` branch; that branch runs the same remote E2E job without redeploying and stores evidence against the branch point artifact commit from `dev`.

PROD deploys only a QA-approved existing Nexus artifact. PROD does not rebuild. Promotion requires a final version, source RC version, verified artifact commit, and successful PROD web page plus web/API `/health` checks.

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
