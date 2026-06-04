---
name: deploy-to-qa
description: Promote merged pull request topology artifacts through Nexus, Azure DEV, and Azure QA, then update Plane. Use when Codex needs to verify a merged Gitea PR, locate the linked Plane ticket, confirm immutable Nexus per-app ZIP artifacts and checksums, validate Azure DEV and QA page plus all app /health checks, comment artifact and deployment links on the ticket, and move the ticket to QA.
---

# Deploy To QA

## Overview

Use this skill after a feature PR has merged to `dev` and the package/deploy workflow has produced a Nexus artifact. For automatic post-merge coordination and artifact waiting, use `post-merge-deploy` first. The release rule is:

```text
feature branch -> dev -> DEV -> QA -> main -> PROD
```

`main` is updated only after QA passes. PROD promotion is separate and must reuse the QA-passed artifact commit.

## Shared Context

Before promotion, follow `.codex/skills/_shared/skill-startup.md`, which reads `.codex/skills/_shared/delivery-contract.md` and `docs/context-management.md`, with `docs/deployment.md` as the stage-specific doc. Use `.codex/skills/_shared/scripts/delivery_tools.ps1` helpers: `ArtifactPaths`, `ValidateTicketLock` for `.codex/delivery-context.local.json`, `ValidateDeploymentLane`, `UpdateReleaseManifest`, `ValidateReleaseManifest`, and `RenderPlaneComment -Type QADeployment`.

For push-triggered DEV/QA deployment, the commit or merged PR title must start with the ticket key format configured in `.codex/delivery-policy.json`, such as `E2EPROJECT-123: ...`. Maintenance commits and non-ticket PRs must not deploy.

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

## Preflight

1. Verify the PR is merged and its target branch is `dev`. If the PR merged elsewhere, stop and report the branch mismatch.
2. Resolve the merged commit SHA from Gitea PR metadata. Use the merge commit SHA as the artifact identity.
3. Verify the PR does not currently carry `pr.labels.needsChanges` or `pr.labels.needsTests`. If either label remains, stop before promotion.
4. Resolve the Plane ticket key from the branch name, PR title, PR body, commit messages, or existing Plane comments.
5. Run `ValidateTicketLock` with the resolved ticket key, PR, branch, and merged/artifact commit. If the result is invalid, stop before reading or promoting artifacts.
6. Verify the package/deploy workflow completed for the merged commit. If it did not run, report that config-infra should be used to repair `.gitea/workflows/package-deploy.yml`.
7. Build the Nexus artifact paths:
   - `app/{commitSha}/deployable-apps.json`
   - one `app/{commitSha}/{artifactName}` per topology app
   - one `app/{commitSha}/{artifactName}.sha256` per topology app
   - `app/{commitSha}/commit.sha`
   - `app/{commitSha}/release.json`
8. Confirm the topology manifest, every app artifact, every checksum, and commit metadata exist in Nexus using the configured Nexus credentials. Treat missing Nexus local config, Nexus outage, or any missing file as blocking.
9. Compare `commit.sha` with the resolved commit SHA. Treat mismatch as blocking.
10. Read `release.json` when present and verify `planeTicketKey` matches the locked/resolved ticket key. Treat another ticket key as blocking cross-ticket promotion.
11. Confirm Nexus contains `app/{commitSha}/deployment-config.json`. Treat a missing deployment configuration artifact as blocking workflow drift and route to `configure-azure-environments`.

## DEV And QA Promotion

1. Confirm DEV deployment succeeded for the same commit. If DEV failed, add a Plane failure comment and stop.
2. Validate the DEV URL using the workflow smoke-check result or a fresh `curl --fail` when the URL is available. For fresh checks, retry with backoff for Azure cold starts: 5 attempts with waits of 5, 10, 20, 30, and 60 seconds.
3. Validate DEV `/health` using workflow output or a fresh request. It must return HTTP 200 and JSON `status=ok`. For fresh checks, use the same retry/backoff policy.
4. Confirm DEV deployment applied and verified `deployment-config.json`; required live App Service settings must exist and non-secret values must match expected resolved values. Missing proof is blocking.
5. Confirm QA deployment downloaded the same Nexus topology, deployment configuration, and app artifact paths used by DEV. Do not rebuild.
6. Validate the QA URL using the workflow smoke-check result or a fresh `curl --fail` when the URL is available. For fresh checks, use the same retry/backoff policy.
7. Validate QA `/health` using workflow output or a fresh request. It must return HTTP 200 and JSON `status=ok`. For fresh checks, use the same retry/backoff policy.
8. Confirm QA deployment applied and verified `deployment-config.json`; required live App Service settings must exist and non-secret values must match expected resolved values. Missing proof is blocking.
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
- Stop when `deployment-config.json` is missing or live DEV/QA App Service setting verification is missing, failed, or mismatched.
- Stop when merged PR still has `needs-changes` or `needs-tests`.
- Stop when the ticket context lock or `release.json.planeTicketKey` points to a different ticket.
- Stop when Nexus is unreachable; do not use a degraded artifact source.
- Treat placeholder config as missing.
- Preserve unrelated local working tree changes.
- Route missing infra, secrets, workflow templates, Azure resources, or branch protection setup to `$configure-dev-environment`.
