# Deployment

Deployment is ticket-gated and artifact-based. The selected providers and environments are declared in `.codex/project-profile.json`; this repository's adapters promote one immutable artifact set through DEV, QA, PROD, and rollback paths without rebuilding between environments.

## Flow

```text
feature branch -> dev -> DEV -> QA -> main -> PROD
```

Push-triggered deployment is allowed only for ticket-named application changes under configured application or test paths. The ticket key pattern is configured in `.codex/project-profile.json` at `workflow.ticketKeyPattern`; non-code changes outside those folders do not run automatic CI/deployment work.

## Technology Stack And Tool Set

Deployment tooling is intentionally local-first except for the application runtimes. Generic skills load the selected artifact, deployment, review, ticket, and observability adapters from `.codex/project-profile.json`; provider-specific names, endpoints, and commands belong in `.codex/providers/`, `.codex/client-tools.local.json`, workflow files, and infrastructure files.

The current profile uses Rancher Desktop Kubernetes for default deployed runtimes and local Grafana/Seq views for operator checks. Azure App Service, Azure Monitor, and Log Analytics remain optional cloud-side adapters when that lane is explicitly selected.

- Nexus paths under `app/{commitSha}/` are the durable artifact identity; environments must promote that same artifact set and checksum/digest metadata instead of rebuilding.
- Rancher Desktop deployment uses Nexus Docker image digests recorded in `app/{commitSha}/container-images.json`; local DEV, QA, PROD, and rollback must promote those same digest references instead of rebuilding.
- Optional Azure deployment uses App Service ZIP deployment from the existing Nexus artifact.
- The Blazor site project (`src/SDDTemplate.Site`) and REST API project (`src/SDDTemplate.Api`) are separated so Azure environments can host web and API App Service apps independently. The API references `src/SDDTemplate.Data` for EF Core entities, DbContext, migrations, and database setup.
- Seq runs locally at `http://localhost:5341` and receives app-emitted Serilog events from the Rancher Desktop site/API pods through `RANCHER_APP_SEQ_URL`, default `http://host.docker.internal:5341`.
- The Rancher Desktop lane uses direct site/API `/health` checks for deployment evidence. Deployment jobs call the deployed endpoints after namespace deployment and write `monitoring-summary.json` for Nexus evidence.
- Grafana dashboards and health alert rules are provisioned from tracked files and generated local-only dashboard files. Health alerts query `/health` JSON through the Infinity datasource and fire only when the derived `up` value stays below `1` for the configured pending duration, default `2m`, to avoid short deployment blips.
- Seq uses a native alert named `Agentic E2E - Any Seq Error Logs` to flag any error or fatal log event in the configured window.
- Seq search validation covers app-emitted Serilog events only. Direct health validation covers Rancher Desktop `/health` targets; Grafana Infinity provides operator dashboards and alerts over the same targets.
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

The Rancher Desktop lane additionally stores:

```text
app/{commitSha}/container-images.json
```

`commit.sha` must match the artifact commit. Every `{artifactName}.sha256` from `deployable-apps.json` must verify before ZIP deployment. Every container image reference in `container-images.json` must be pinned by `@sha256:` digest before Rancher Desktop deployment. `release.json` records ticket, representative artifact metadata, container image metadata when present, environment, QA, version, PROD, and rollback lineage. `ticketKey` remains the primary ticket for compatibility; optional `includedTickets` records all Done tickets included in a PROD release.

Human-readable Nexus version folders are metadata aliases, not artifact identity. The canonical ZIPs remain under `app/{commitSha}/`. QA approval publishes `app/qa-approved/latest.json` plus `app/rc/{sourceRcVersion}/artifact-pointer.json` and `app/rc/{sourceRcVersion}/release.json`. PROD success publishes `app/releases/{finalReleaseVersion}/artifact-pointer.json` and `app/releases/{finalReleaseVersion}/release.json`. Each pointer records the version, artifact commit SHA, canonical path, release manifest path, primary OpenProject work package, included tickets, and creation timestamp.

## Environments

DEV and QA deploy from `dev` and must use the same Nexus artifact set for the same commit SHA. The Rancher Desktop deploy workflow builds site/API container images, pushes them to Nexus Docker, records digest-pinned image metadata in `app/{commitSha}/container-images.json`, deploys those digests to `sdd-dev`, then promotes the exact same digest set to `sdd-qa` after DEV succeeds. Deployment requires configuration verification, rendered web API-base-url verification, API CORS preflight verification, web page checks, plus every app `/health` smoke check. After QA smoke checks pass, the workflow publishes `app/{commitSha}/qa-targets.json` with the deployed QA Site/API URLs; then push a `qa-local/{ticketKey}` branch from current `dev`. Gitea Actions runs the committed Playwright QA E2E suite against `RANCHER_QA_SITE_URL` and `RANCHER_QA_API_URL` without redeploying, and stores evidence against the branch point artifact commit from `dev`. This job produces evidence only and does not move OpenProject status, create RC tags, or update release lineage. Implementation PRs must include committed automated coverage for every acceptance criterion, including Playwright E2E tests when browser-level proof is required; the QA branch and `quality-test-e2e` only rerun existing committed tests and evaluate evidence. Local E2E QA is forbidden unless a deployment-related blocker prevents the normal Gitea `e2e-qa` path from running or completing and 2 deploy-fix attempts have failed. Product E2E test failures remain QA failures and are not a local-fallback trigger. Any local fallback must use `npm run test:docker` against the deployed QA `E2E_SITE_URL` and `E2E_API_URL`, never localhost, and the QA evidence must record the blocker, both failed fix attempts, local command, tested URLs, and evidence. The `quality-test-e2e` skill may move OpenProject to Done only when the QA result is `PASS`: every ticket acceptance criterion is mapped to executable assertions from existing committed tests against the deployed QA artifact, relevant user workflow, API/backend effect, independent state, validation/boundary, error-handling, environment-correctness, and evidence-integrity checks are covered, and screenshots/logs/traces support rather than replace assertions. Missing committed coverage is a `FAIL` or blocked QA result and leaves the ticket in QA. `PASS WITH GAPS` and `FAIL` leave the ticket in QA. After the E2E QA OpenProject comment is verified, E2E QA posts or patches the workflow timing comment from OpenProject time entries, falling back to `.codex/agent-telemetry.local.jsonl` only when direct time telemetry is unavailable; PROD timing and PROD deployment comments remain part of the separate explicit PROD promotion step. After Nexus evidence exists, the E2E QA OpenProject comment is verified, the workflow timing comment is handled, the RC tag is created or verified, release metadata is updated, and OpenProject is Done, delete the remote `qa-local/{ticketKey}` branch from Gitea because the durable evidence is in Nexus, OpenProject, the release manifest, and tags.

The Rancher Desktop lane uses `.gitea/workflows/rancher-local-deploy.yml`. It builds `sddtemplate/site` and `sddtemplate/api` images, pushes them to a Nexus Docker hosted repository, writes `container-images.json`, deploys the digest-pinned images to `sdd-dev`, then promotes the exact same digest set to `sdd-qa` after DEV succeeds. Local PROD promotion is explicit and deploys an existing QA-approved commit's digest set to `sdd-prod`. The QA evidence path remains `qa/{ticketKey}/{runId}/qa-evidence.zip`; QA branches use `qa-local/{ticketKey}` with `RANCHER_QA_SITE_URL` and `RANCHER_QA_API_URL`.

When Windows cannot resolve the Rancher Desktop ingress hosts such as `site.dev.sdd.localhost`, `config infra` runs `EnsureRancherDesktopPortForwards` after Kubernetes setup. It starts stable `kubectl port-forward --address 127.0.0.1` browser mappings for deployed services: DEV site/API on `http://127.0.0.1:18081` and `http://127.0.0.1:18082`, QA site/API on `http://127.0.0.1:18083` and `http://127.0.0.1:18084`, and PROD site/API on `http://127.0.0.1:18085` and `http://127.0.0.1:18086`. Docker-hosted monitoring and Gitea Action jobs reach those same forwards through `host.docker.internal` because `localhost` inside a job or monitoring container is the container itself. Missing services are reported as warnings because a fresh lab may not have every namespace deployed yet.

`config infra` also refreshes `.codex/environment-urls.local.json` and the Grafana `Environment URLs` dashboard. They list DEV, QA, and PROD Web/API browser URLs, Docker/Gitea Action container URLs, Rancher Desktop ingress host URLs, deployment status, and port-forward status. Use `ShowEnvironmentUrls` for a quick command-line view without opening Grafana.

Rancher Desktop observability evidence is attached to the artifact commit. DEV and QA app pods stream live Serilog events to Seq when the image includes `Serilog.Sinks.Seq` and the deployment sets `Serilog__WriteTo__1__Args__serverUrl`. Deployment jobs verify site/API `/health` with direct HTTP checks and upload `monitoring-summary*.json` to Nexus raw under `app/{commitSha}/`. QA additionally publishes `app/{commitSha}/qa-observability.json`, and the local E2E evidence bundle includes that file when available. Grafana Infinity dashboards and alerts provide operator visibility but are not the deployment evidence source.

Deployment configuration is fail-closed. New `appsettings*.json` keys must be mapped in `infra/deployment/configuration.json` before CI can deploy. Interactive configure runs should infer safe values or ask the developer for the mapping and exact secret/setup steps; CI must not guess missing required values. Initial Azure provisioning applies the same non-secret topology settings through explicit App Service appsettings resources, and package deployment reapplies and verifies them from `deployment-config.json`. Serilog and default application log levels are applied as Debug for DEV/QA and Warning for PROD. Removed keys are drift findings and are not automatically deleted from live App Service settings without an explicit operator request.

PROD deploys only a QA-approved existing Nexus artifact. PROD does not rebuild. Promotion requires a final version, source RC version, verified artifact commit, included Done ticket list, and successful PROD web page plus web/API `/health` checks. For push-triggered PROD, the workflow resolves the artifact through `app/qa-approved/latest.json` and then validates that pointer against `commit.sha`, `release.json`, and the source RC tag before downloading ZIPs. Manual workflow dispatch may still pass `artifact_commit_sha` explicitly. E2E QA `PASS` closes each ticket as Done; PROD is a later explicit release event that may include one or more Done tickets. After successful PROD evidence is recorded, the workflow updates `release.json`, publishes the final release alias, comments the PROD result on every included ticket, and runs a read-only post-PROD retrospective for the just-promoted release with per-ticket findings when useful. Sanitized learning evidence is stored in ignored `.codex/agent-evals/results.local.json` plus compact OpenProject markers. This retrospective is learning evidence for later workflow improvements, not a release gate.

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


