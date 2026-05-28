---
name: deploy-to-prod
description: Promote a QA-approved release artifact to PROD after Plane E2E QA approval. Use when Codex needs to verify a Plane Done ticket, confirm the QA-approved Nexus artifact and checksum, ensure release/RC tag consistency, update main, trigger PROD deployment, validate PROD page and /health checks, verify Prometheus/Grafana monitoring when available, and comment the PROD result on Plane.
---

# Deploy To PROD

## Overview

Use this skill after `test-e2e` has passed and moved the Plane ticket to `plane.doneState`. The release rule is:

```text
feature branch -> dev -> DEV -> QA -> E2E QA OK -> main -> PROD
```

PROD must reuse the QA-approved Nexus artifact. Never rebuild, republish, or rename the artifact during PROD promotion.

## Configuration

Read `.codex/client-tools.local.json` first. Fall back to `.codex/client-tools.example.json` only for structure, then apply environment overrides when present.

Required values:

- `plane.baseUrl`, `plane.apiToken`, `plane.workspaceSlug`, `plane.projectIdentifier`, `plane.doneState`
- `gitea.baseUrl`, `gitea.apiToken`, `gitea.owner`, `gitea.repo`
- `nexus.baseUrl`, `nexus.username`, `nexus.password`, `nexus.repository`

Optional environment variables override local JSON when present:

- `PLANE_DONE_STATE`
- `GITEA_BASE_URL`
- `GITEA_API_TOKEN`
- `GITEA_OWNER`
- `GITEA_REPO`

Never print, commit, paste into tickets, or write real API tokens, cookies, Nexus credentials, Azure credentials, or other secrets.

## Preflight

1. Resolve the target Plane ticket, PR, QA-approved commit SHA, source RC version, and final release version from user input, Plane comments, Gitea PR metadata, tags, or Nexus artifact paths.
2. Require SemVer tags:
   - source RC: `vMAJOR.MINOR.PATCH-rc.N`
   - final release: `vMAJOR.MINOR.PATCH`
3. Fetch the Plane ticket with expanded state/project data and verify it is in `plane.doneState`.
4. Read Plane comments and find `IA generated E2E QA: {ticketKey}` for the same commit/artifact.
5. Verify the E2E QA comment includes pass result, PR URL, QA URL, Nexus artifact URL, QA evidence URL, and source RC version.
6. Verify Nexus contains:
   - `app/{commitSha}/app.zip`
   - `app/{commitSha}/app.zip.sha256`
   - `app/{commitSha}/commit.sha`
   - `app/{commitSha}/release.json`
7. Download checksum metadata only as needed and verify `commit.sha` exactly matches the QA-approved commit.
8. Read `release.json` and verify it references the same commit SHA, checksum, PR, Plane ticket, QA evidence URL, and source RC version as the Plane E2E QA comment.
9. Verify the source RC tag exists and points to the QA-approved commit.
10. Verify the final release tag does not already exist.

Stop if any QA gate, tag gate, artifact gate, or checksum gate fails.

## Main And Tag Promotion

1. Verify the QA-approved commit exists on `dev`.
2. Verify `main` can fast-forward to the QA-approved commit.
3. If `main` has diverged, stop and report the divergence. Do not create a merge commit unless the user explicitly changes the release policy.
4. Fast-forward `main` to the QA-approved commit.
5. Create an annotated final release tag on the QA-approved commit.
6. Tag message must include ticket key, PR URL, source RC version, final version, QA evidence URL, Nexus artifact URL, checksum, and commit SHA.
7. Push `main` and the release tag only after every preflight check passes.
8. If branch protection blocks the `main` push, open a PR to `main` with the QA-approved commit and final version details, then stop before PROD deployment until that PR is merged. Do not deploy PROD from a commit that is not reachable from `main`.

## PROD Deployment

Trigger the Gitea package/deploy workflow with:

```text
environment=prod
artifact_commit_sha={qaApprovedCommit}
release_version={finalVersion}
source_rc_version={sourceRcVersion}
```

The PROD workflow must download `app/{artifact_commit_sha}/app.zip` from Nexus, verify `app.zip.sha256`, deploy to PROD, then run:

- PROD page smoke check: HTTP 200, expected title/content, no Azure placeholder page.
- PROD health check: `GET {prodWebUrl}/health` returns HTTP 200 and JSON `status=ok`.

After dispatch, inspect the workflow run jobs. A successful run is valid only when a `deploy-prod` job exists, completes successfully, and the package/DEV/QA jobs are skipped for `environment=prod`. If the run succeeds without `deploy-prod`, treat it as blocking workflow drift rather than a deployment success.

If the workflow rebuilds, republishes, downloads from `GITHUB_SHA` instead of `artifact_commit_sha`, lacks the `deploy-prod` job, or skips `/health`, treat it as blocking workflow drift.

## PROD Verification

After the workflow succeeds, run direct verification before commenting success:

1. Request the PROD web URL and assert HTTP 200 plus expected page title/content.
2. Request `{prodWebUrl}/health` and assert HTTP 200 plus `status=ok`.
3. Query Prometheus targets at `http://localhost:9090/api/v1/targets` when local Prometheus is reachable.
4. Verify the PROD web target is present and `health=up`.
5. If a PROD API target is configured but this repo does not deploy an API, record it as an observability configuration note instead of a product failure.
6. Query Grafana health at `http://localhost:3001/api/health` when local Grafana is reachable.
7. If Prometheus or Grafana is unreachable, classify monitoring as unavailable. Direct HTTP and `/health` checks remain authoritative for app success.
8. If direct page or `/health` checks fail, classify PROD verification as failed and do not claim success.
9. When PROD verification passes, update `app/{commitSha}/release.json` with final release version, final tag, PROD URL, PROD page status, PROD `/health` status, workflow run URL, monitoring status, and PROD deployment timestamp. Upload the updated manifest to Nexus.

PROD success must never be based on screenshots alone.

## Plane Result

Before commenting, read existing comments when the API allows it. Use this stable marker:

```text
IA generated PROD deployment: {finalVersion}
```

Do not duplicate a PROD result comment with the same marker, commit, artifact, and PROD URL unless the user explicitly asks for a fresh run.

The comment must include:

- ticket key and current state
- final release version and source RC version
- release lineage: `artifact commit -> source RC version -> final release version`
- final release tag URL or tag name and verified tag target commit
- PR URL
- commit SHA
- Nexus artifact URL and checksum
- Nexus release manifest URL
- QA evidence URL
- main ref update result
- workflow run URL
- PROD URL, page smoke status, and `/health` status
- Prometheus status and Grafana status, or monitoring unavailable/configuration notes
- pass/fail result

Only write a success result after the workflow passed and direct PROD page plus `/health` verification passed. If app checks fail, write a failure comment and stop. If only local monitoring is unavailable, deployment may still pass, but the comment must state monitoring verification was unavailable.

## Failure Rules

- Missing Plane API config: stop before Plane reads or mutations.
- Ticket not in `plane.doneState`: stop.
- Missing or stale E2E QA marker: stop.
- Missing source RC tag or wrong tag target: stop.
- Existing final release tag: stop.
- Missing Nexus artifact/checksum/commit metadata: stop.
- Checksum or commit metadata mismatch: stop.
- Diverged `main`: stop.
- Missing PROD workflow job or skipped `deploy-prod`: route to `$configure-artifact-delivery` or `$configure-dev-environment`, fix the workflow through PR, then rerun PROD dispatch only after the fix reaches `main`.
- Missing `AZURE_PROD_RESOURCE_GROUP`, `AZURE_PROD_WEBAPP_NAME`, or `AZURE_PROD_WEBAPP_URL` Gitea Actions secrets: route to `$configure-azure-environments` or `$configure-dev-environment`, configure the secrets from Azure deployment outputs without exposing secret values, then rerun PROD dispatch.
- PROD workflow failure: comment failure and stop.
- PROD page or `/health` failure: comment failure and stop.
- Prometheus/Grafana unavailable: record as monitoring unavailable; do not fail the deployment when direct app checks pass.
- Secrets in logs or comments: redact or discard before reporting.
