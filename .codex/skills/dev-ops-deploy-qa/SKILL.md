---
name: dev-ops-deploy-qa
description: Promote merged pull request artifacts through the selected artifact and deployment adapters into configured pre-production environments, then update the ticket adapter. Use when Codex needs to verify a merged PR, locate the linked ticket, confirm immutable artifacts and checksums, validate configured environment health checks, comment artifact and deployment links, and move the ticket to QA.
---

# Deploy To QA

## Overview

Use this skill after a feature PR has merged to `dev` and the package/deploy workflow has produced a Nexus artifact. For automatic post-merge coordination and artifact waiting, use `dev-ops-post-merge-deploy` first. The release rule is:

```text
feature branch -> dev -> DEV -> QA -> main -> PROD
```

`main` is updated only after QA passes. PROD promotion is separate and must reuse the QA-passed artifact commit.

## Shared Context

Before promotion, follow `.codex/skills/_shared/skill-startup.md`, which reads `.codex/project-profile.json`, `.codex/skills/_shared/provider-adapter-contract.md`, `.codex/skills/_shared/delivery-contract.md`, and `docs/context-management.md`, with `docs/deployment.md` as the stage-specific doc. Load selected artifact, deployment, repository/review, and ticket adapters. Use `.codex/skills/_shared/scripts/delivery_tools.ps1` helpers: `ArtifactPaths`, `ValidateTicketLock` for `.codex/delivery-context.local.json`, `ValidateDeploymentLane`, `UpdateReleaseManifest`, `ValidateReleaseManifest`, and `RenderPlaneComment -Type QADeployment`.

For push-triggered pre-production deployment, the commit or merged PR title must start with the ticket key format configured in `.codex/project-profile.json` at `workflow.ticketKeyPattern`, and the change must touch configured application or test paths. Non-code changes outside those paths and non-ticket PRs must not deploy.

## Workflow Telemetry

Capture UTC start time after resolving the ticket key and before artifact promotion checks. Append a `dev-ops-deploy-qa` row with `.codex/skills/_shared/scripts/delivery_tools.ps1 -Mode AppendWorkflowTelemetry -TicketKey {ticketKey}` when QA promotion succeeds, blocks, fails, or is skipped idempotently because the QA deployment marker already exists. On resume or idempotent reuse, append another row for the same stage; workflow timing rendering collapses repeated stage rows into earliest start and latest finish. Include `workflowStage=dev-ops-deploy-qa`, `agentRole=deployment`, `startedUtc`, `finishedUtc`, `retryCount`, and `outcome`.

## Configuration

Read `.codex/client-tools.local.json` first. Fall back to `.codex/client-tools.example.json` for structure only, then apply environment variable overrides when present.

Required or defaulted values:

- `plane.baseUrl`, `plane.apiToken`, `plane.workspaceSlug`, `plane.projectIdentifier`
- `plane.qaState`: target state after QA validation. Default: `QA`.
- `gitea.baseUrl`, `gitea.apiToken`, `gitea.owner`, `gitea.repo`
- `nexus.baseUrl`, `nexus.username`, `nexus.password`, `nexus.repository`

Optional environment variables override local JSON when present: `PLANE_QA_STATE`, `GITEA_BASE_URL`, `GITEA_API_TOKEN`, `GITEA_OWNER`, `GITEA_REPO`.

## Workflow

Run preflight, DEV/QA promotion, Plane updates, and handoff reporting in order. Do not move the ticket to QA until deployment validation and release manifest validation pass.

In idempotent verification mode, do not redeploy or duplicate Plane comments. Re-verify the resolved ticket, PR, artifact commit, QA deployment marker, QA state, release manifest, and available DEV/QA validation evidence, then append the `dev-ops-deploy-qa` telemetry row and hand off to E2E QA.

## Preflight

1. Verify the PR is merged and its target branch is `dev`. If the PR merged elsewhere, stop and report the branch mismatch.
2. Resolve the merged commit SHA from Gitea PR metadata. Use the merge commit SHA as the artifact identity.
3. Verify the PR does not currently carry `pr.labels.needsChanges` or `pr.labels.needsTests`. If either label remains, stop before promotion.
4. Resolve the Plane ticket key from the branch name, PR title, PR body, commit messages, or existing Plane comments.
5. Run `ValidateTicketLock` with the resolved ticket key, PR, branch, and merged/artifact commit. If the result is invalid, stop before reading or promoting artifacts.
6. Verify the selected provider workflow completed for the merged commit. Azure uses `.gitea/workflows/package-deploy.yml`; k3d uses `.gitea/workflows/k3d-local-deploy.yml`. If the expected workflow did not run, report that config-infra should repair the selected provider workflow.
7. Build the Nexus artifact paths for the selected provider. Azure requires:
   - `app/{commitSha}/deployable-apps.json`
   - one `app/{commitSha}/{artifactName}` per topology app
   - one `app/{commitSha}/{artifactName}.sha256` per topology app
   - `app/{commitSha}/commit.sha`
   - `app/{commitSha}/release.json`
   k3d requires:
   - `app/{commitSha}/container-images.json`
   - `app/{commitSha}/commit.sha`
   - `app/{commitSha}/release.json`
   - `app/{commitSha}/qa-targets.json` after QA deployment
   - `app/{commitSha}/monitoring-summary-dev.json`, `app/{commitSha}/monitoring-summary-qa.json`, and `app/{commitSha}/qa-observability.json` when observability is enabled
8. Confirm the selected provider artifact metadata, runtime artifacts, and commit metadata exist in Nexus using the configured Nexus credentials. Treat missing Nexus local config, Nexus outage, or any missing required file as blocking.
9. Compare `commit.sha` with the resolved commit SHA. Treat mismatch as blocking.
10. Read `release.json` when present and verify `planeTicketKey` matches the locked/resolved ticket key. Treat another ticket key as blocking cross-ticket promotion.
11. For Azure, confirm Nexus contains `app/{commitSha}/deployment-config.json`; a missing deployment configuration artifact is blocking workflow drift and routes to `configure-cloud-environments`. For k3d, confirm `container-images.json` contains site and API references pinned with `@sha256:` and route drift to the k3d local-lab config path.

## DEV And QA Promotion

1. Confirm DEV deployment succeeded for the same commit. If DEV failed, add a Plane failure comment and stop.
2. Validate the DEV URL using the workflow smoke-check result or a fresh `curl --fail` when the URL is available. For Azure fresh checks, retry with backoff for cold starts: 5 attempts with waits of 5, 10, 20, 30, and 60 seconds. For k3d, verify the `sdd-dev` namespace health and ingress URL.
3. Validate DEV `/health` using workflow output or a fresh request. It must return HTTP 200 and JSON `status=ok`. For fresh checks, use the same retry/backoff policy.
4. For Azure, confirm DEV applied and verified `deployment-config.json`; required live App Service settings must exist and non-secret values must match expected resolved values. For k3d, confirm DEV deployed the digest references from `container-images.json` and published `monitoring-summary-dev.json`. Missing proof is blocking.
5. Confirm QA deployed the same Azure ZIP/checksum set or k3d digest set used by DEV. Do not rebuild.
6. Validate the QA URL using the workflow smoke-check result or a fresh `curl --fail` when the URL is available. For fresh checks, use the same retry/backoff policy.
7. Validate QA `/health` using workflow output or a fresh request. It must return HTTP 200 and JSON `status=ok`. For fresh checks, use the same retry/backoff policy.
8. For Azure, confirm QA applied and verified `deployment-config.json`; required live App Service settings must exist and non-secret values must match expected resolved values. For k3d, confirm QA deployed the same image digests to `sdd-qa`, published `qa-targets.json`, and captured observability evidence. Missing proof is blocking.
9. If DEV or QA page, `/health`, or deployment configuration validation fails, add a Plane failure comment and do not move the ticket state.
10. Use `UpdateReleaseManifest` to create or update `app/{commitSha}/release.json` with commit SHA, representative checksum/artifact URL, PR URL, Plane ticket key, DEV/QA URLs, DEV/QA status, per-app health status, deployment configuration status, workflow run URL, and `versionStatus=unversioned QA candidate` unless an RC tag already exists.
11. Validate and upload `release.json` to Nexus next to the artifact.
12. If QA passes, move the Plane work item to `plane.qaState`, default `QA`.

## Plane Updates

Use Plane API only. Never use Plane MCP, Docker containers, or direct database access for Plane.

Before mutating Plane, resolve the project UUID and target state ID. If the configured QA state does not exist, stop after adding the deployment comment and report the missing state.

Add a comment with this stable marker:

```text
IA generated QA deployment: {commitSha}
```

Skip adding the comment if an existing comment already contains the same marker.

Keep the marker as the first line by itself. Use `RenderPlaneComment -Type QADeployment` with the resolved deployment data to format the readable Markdown body.

The comment must include:

- PR URL
- commit SHA
- Nexus topology/artifact URLs
- checksum
- DEV URL and status
- DEV per-app `/health` status
- QA URL and status
- QA per-app `/health` status
- workflow run URL when available
- Nexus release manifest URL: `app/{commitSha}/release.json`
- version status: `unversioned QA candidate` unless an RC tag already exists for the commit
- source RC version when already known, otherwise state that RC assignment happens during E2E QA before Done

## Output

Report the ticket, merged PR, artifact commit, DEV/QA URLs, health validation, Nexus release manifest, Plane QA-state update, and next handoff to E2E QA.

## Failure Rules

- Do not deploy or promote without a checksum.
- Do not rebuild between DEV and QA.
- Do not move the ticket to QA until QA validation passes.
- Stop on DEV failure.
- Stop on QA failure.
- Stop on DEV or QA `/health` failure.
- For Azure, stop when `deployment-config.json` is missing or live DEV/QA App Service setting verification is missing, failed, or mismatched.
- For k3d, stop when `container-images.json` is missing, mutable, not digest-pinned, or DEV/QA namespace health and observability evidence are missing when enabled.
- Stop when merged PR still has `needs-changes` or `needs-tests`.
- Stop when the ticket context lock or `release.json.planeTicketKey` points to a different ticket.
- Stop when Nexus is unreachable; do not use a degraded artifact source.
- Treat placeholder config as missing.
- Preserve unrelated local working tree changes.
- Route missing infra, secrets, workflow templates, Azure resources, or branch protection setup to `$configure-dev-environment`.
