---
name: rollback-prod
description: Roll back PROD to a previously verified Nexus artifact. Use when Codex needs to choose a known-good release from release.json metadata, redeploy app/{commitSha}/app.zip to PROD without rebuilding, verify PROD page and /health, check Prometheus/Grafana when available, and comment rollback evidence on Plane.
---

# Rollback PROD

## Overview

Use this skill when PROD must be restored to a previous known-good artifact. Rollback is a deployment operation, not a rebuild. It must redeploy an existing Nexus artifact and preserve release traceability.

## Configuration

Read `.codex/client-tools.local.json` first. Required values:

- `plane.baseUrl`, `plane.apiToken`, `plane.workspaceSlug`, `plane.projectIdentifier`
- `gitea.baseUrl`, `gitea.apiToken`, `gitea.owner`, `gitea.repo`
- `nexus.baseUrl`, `nexus.username`, `nexus.password`, `nexus.repository`

Never print, commit, paste into tickets, or write real tokens, Nexus credentials, Azure credentials, or secrets.

## Preflight

1. Resolve the rollback target from user input, Plane PROD comments, Git tags, or Nexus `release.json` metadata.
2. Verify the target artifact exists:
   - `app/{commitSha}/app.zip`
   - `app/{commitSha}/app.zip.sha256`
   - `app/{commitSha}/commit.sha`
   - `app/{commitSha}/release.json`
3. Verify checksum and `commit.sha`.
4. Verify `release.json` marks the target as previously QA-approved and either previously PROD-deployed or explicitly user-approved as the rollback target.
5. Resolve the current PROD release from the latest Plane PROD deployment comment or release manifest.
6. Stop if the target commit equals the current PROD commit unless the user explicitly asks to redeploy the same artifact.

## Rollback Deployment

Trigger the package/deploy workflow with:

```text
environment=prod
artifact_commit_sha={rollbackCommit}
release_version={rollbackVersionOrTag}
source_rc_version={sourceRcVersion}
```

The workflow must download `app/{artifact_commit_sha}/app.zip`, verify checksum, deploy the ZIP, and run page plus `/health` checks. Do not rebuild.

## Verification

1. Verify PROD page returns HTTP 200 and expected title/content.
2. Verify `{prodWebUrl}/health` returns HTTP 200 and JSON `status=ok`.
3. Query Prometheus targets when local Prometheus is reachable and record PROD web target status.
4. Query Grafana health when local Grafana is reachable.
5. If page or `/health` fails, comment rollback failure and stop.
6. If only monitoring is unavailable, rollback may still pass but the Plane comment must record monitoring unavailable.

## Plane Result

Add a Plane comment with marker:

```text
IA generated PROD rollback: {rollbackVersionOrCommit}
```

Include current PROD version/commit, rollback target version/commit, Nexus artifact URL, checksum, release manifest URL, workflow run URL, PROD URL, page status, `/health` status, Prometheus/Grafana status, and failure or success result.

Update `app/{commitSha}/release.json` with rollback deployment timestamp, workflow run URL, PROD URL, and rollback source/current version relationship when rollback passes.

## Failure Rules

- Missing artifact/checksum/commit metadata: stop.
- Missing or inconsistent `release.json`: stop unless the user explicitly approves the artifact as rollback target.
- Checksum mismatch: stop.
- Workflow rebuilds or skips `/health`: stop.
- PROD page or `/health` failure: comment failure and stop.
- Monitoring unavailable: record as unavailable, not product failure, when direct app checks pass.
