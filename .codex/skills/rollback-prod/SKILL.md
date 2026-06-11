---
name: rollback-prod
description: Roll back PROD to previously verified Nexus topology artifacts. Use when Codex needs to choose a known-good release from release.json metadata, redeploy app/{commitSha}/deployable-apps.json and per-app ZIPs to PROD without rebuilding, verify PROD page and all app /health checks, check Grafana Azure Monitor when available, and comment rollback evidence on Plane.
---

# Rollback PROD

## Overview

Use this skill when PROD must be restored to a previous known-good artifact. Rollback is a deployment operation, not a rebuild. It must redeploy an existing Nexus artifact and preserve release traceability.

## Shared Context

Before rollback, follow `.codex/skills/_shared/skill-startup.md`, which reads `.codex/skills/_shared/delivery-contract.md` and `docs/context-management.md`, with `docs/deployment.md` as the stage-specific doc. Use `.codex/skills/_shared/scripts/delivery_tools.ps1` helpers: `ArtifactPaths`, `ValidateReleaseManifest`, `ValidateTicketLock`, and `UpdateReleaseManifest`. Rollback may target an incident/release rather than the active ticket lock, but a mismatch must be explicit.

## Configuration

Read `.codex/client-tools.local.json` first. Required values:

- `plane.baseUrl`, `plane.apiToken`, `plane.workspaceSlug`, `plane.projectIdentifier`
- `gitea.baseUrl`, `gitea.apiToken`, `gitea.owner`, `gitea.repo`
- `nexus.baseUrl`, `nexus.username`, `nexus.password`, `nexus.repository`

## Workflow

Run preflight, rollback deployment, verification, Plane result, and follow-up handoff steps in order. Do not mutate PROD until artifact and release-manifest validation pass.

## Preflight

1. Resolve the current PROD release from the latest Plane PROD deployment comment or release manifest.
2. Run `ValidateTicketLock` when `.codex/delivery-context.local.json` is present and report the active ticket lock. If the rollback target differs from the lock, require explicit user confirmation before mutation.
3. If the user did not supply a rollback target, list known-good candidates from Plane PROD comments, Git tags, and Nexus `release.json` metadata. Order newest-first, mark the current PROD release, and ask the user to choose a target before mutating anything.
4. Resolve the rollback target from user input, Plane PROD comments, Git tags, or Nexus `release.json` metadata.
5. Verify the target artifact exists:
   - `app/{commitSha}/deployable-apps.json`
   - one `app/{commitSha}/{artifactName}` per topology app
   - one `app/{commitSha}/{artifactName}.sha256` per topology app
   - `app/{commitSha}/commit.sha`
   - `app/{commitSha}/release.json`
6. Verify checksum and `commit.sha`.
7. Verify `release.json` marks the target as previously QA-approved and either previously PROD-deployed or explicitly user-approved as the rollback target.
8. Stop if the target commit equals the current PROD commit unless the user explicitly asks to redeploy the same artifact.

## Rollback Deployment

Trigger the package/deploy workflow with:

```text
environment=prod
artifact_commit_sha={rollbackCommit}
release_version={rollbackVersionOrTag}
source_rc_version={sourceRcVersion}
```

The workflow must download `app/{artifact_commit_sha}/deployable-apps.json`, download every listed app ZIP, verify every checksum, deploy the ZIPs, and run page plus all app `/health` checks. Do not rebuild.

## Verification

1. Verify PROD page returns HTTP 200 and expected title/content.
2. Verify `{prodWebUrl}/health` returns HTTP 200 and JSON `status=ok`.
3. Query Grafana health when local Grafana is reachable.
4. Run `infra/monitoring/validate-azure-monitor-logs.ps1` when Grafana Azure Monitor credentials and Log Analytics workspace IDs are configured.
5. If page or `/health` fails, comment rollback failure and stop.
6. If only monitoring is unavailable, rollback may still pass but the Plane comment must record monitoring unavailable.

## Plane Result

Add a Plane comment with marker:

```text
IA generated PROD rollback: {rollbackVersionOrCommit}
```

Include current PROD version/commit, rollback target version/commit, Nexus artifact URL, checksum, release manifest URL, workflow run URL, PROD URL, page status, `/health` status, Grafana Azure Monitor status, and failure or success result.

Use `UpdateReleaseManifest` to update `app/{commitSha}/release.json` with rollback deployment timestamp, workflow run URL, PROD URL, and rollback source/current version relationship when rollback passes.

Create or update a Plane incident ticket with marker:

```text
IA generated PROD rollback incident: {rollbackVersionOrCommit}
```

Record who or what requested the rollback when known, why it was needed, current PROD before rollback, rollback target, timeline, verification evidence, and follow-up decision.

After rollback, explicitly document Git state. `main` is not automatically reverted. Require one follow-up: open a hotfix PR, open a revert PR, or record an accepted temporary divergence note with owner and expected resolution.

## Output

Report the rollback target, current and restored PROD versions, artifact commit, validation results, Plane rollback comment, incident/follow-up handoff, and any remaining Git-line divergence.

## Failure Rules

- Missing artifact/checksum/commit metadata: stop.
- Missing or inconsistent `release.json`: stop unless the user explicitly approves the artifact as rollback target.
- Checksum mismatch: stop.
- No rollback target supplied: list known-good candidates and stop before mutation.
- Workflow rebuilds or skips `/health`: stop.
- PROD page or `/health` failure: comment failure and stop.
- Monitoring unavailable: record as unavailable, not product failure, when direct app checks pass.
