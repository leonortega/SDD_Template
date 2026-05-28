---
name: deploy-to-qa
description: Promote a merged pull request artifact through Nexus, Azure DEV, and Azure QA, then update Plane. Use when Codex needs to verify a merged Gitea PR, locate the linked Plane ticket, confirm the immutable Nexus ZIP artifact and checksum, validate Azure DEV and QA page plus /health checks, comment artifact and deployment links on the ticket, and move the ticket to QA.
---

# Deploy To QA

## Overview

Use this skill after a feature PR has merged to `dev` and the package/deploy workflow has produced a Nexus artifact. For automatic post-merge coordination and artifact waiting, use `post-merge-deploy` first. The release rule is:

```text
feature branch -> dev -> DEV -> QA -> main -> PROD
```

`main` is updated only after QA passes. PROD promotion is separate and must reuse the QA-passed artifact commit.

Before promotion, read `.codex/skills/_shared/delivery-contract.md`. Use `.codex/skills/_shared/scripts/delivery_tools.ps1 -Mode ArtifactPaths` for Nexus paths and validate `release.json` against `.codex/skills/_shared/release.schema.json` after writing it.

## Configuration

Read `.codex/client-tools.local.json` first. Fall back to `.codex/client-tools.example.json` for structure only, then apply environment variable overrides when present.

Required or defaulted values:

- `plane.baseUrl`, `plane.apiToken`, `plane.workspaceSlug`, `plane.projectIdentifier`
- `plane.qaState`: target state after QA validation. Default: `QA`.
- `gitea.baseUrl`, `gitea.apiToken`, `gitea.owner`, `gitea.repo`
- `nexus.baseUrl`, `nexus.username`, `nexus.password`, `nexus.repository`

Optional environment variables override local JSON when present: `PLANE_QA_STATE`, `GITEA_BASE_URL`, `GITEA_API_TOKEN`, `GITEA_OWNER`, `GITEA_REPO`.

Never print, commit, paste into tickets, or write real API tokens, Nexus credentials, Azure credentials, or secret values.

## Preflight

1. Verify the PR is merged and its target branch is `dev`. If the PR merged elsewhere, stop and report the branch mismatch.
2. Resolve the merged commit SHA from Gitea PR metadata. Use the merge commit SHA as the artifact identity.
3. Verify the PR does not currently carry `pr.labels.needsChanges` or `pr.labels.needsTests`. If either label remains, stop before promotion.
4. Resolve the Plane ticket key from the branch name, PR title, PR body, commit messages, or existing Plane comments.
5. Verify the package/deploy workflow completed for the merged commit. If it did not run, report that config-infra should be used to repair `.gitea/workflows/package-deploy.yml`.
6. Build the Nexus artifact paths:
   - `app/{commitSha}/app.zip`
   - `app/{commitSha}/app.zip.sha256`
   - `app/{commitSha}/commit.sha`
   - `app/{commitSha}/release.json`
7. Confirm the artifact, checksum, and commit metadata exist in Nexus using the configured Nexus credentials. Treat missing Nexus local config, Nexus outage, or any missing file as blocking.
8. Compare `commit.sha` with the resolved commit SHA. Treat mismatch as blocking.

## DEV And QA Promotion

1. Confirm DEV deployment succeeded for the same commit. If DEV failed, add a Plane failure comment and stop.
2. Validate the DEV URL using the workflow smoke-check result or a fresh `curl --fail` when the URL is available. For fresh checks, retry with backoff for Azure cold starts: 5 attempts with waits of 5, 10, 20, 30, and 60 seconds.
3. Validate DEV `/health` using workflow output or a fresh request. It must return HTTP 200 and JSON `status=ok`. For fresh checks, use the same retry/backoff policy.
4. Confirm QA deployment downloaded the same Nexus artifact path used by DEV. Do not rebuild.
5. Validate the QA URL using the workflow smoke-check result or a fresh `curl --fail` when the URL is available. For fresh checks, use the same retry/backoff policy.
6. Validate QA `/health` using workflow output or a fresh request. It must return HTTP 200 and JSON `status=ok`. For fresh checks, use the same retry/backoff policy.
7. If DEV or QA page or `/health` validation fails, add a Plane failure comment and do not move the ticket state.
8. Create or update `app/{commitSha}/release.json` with commit SHA, checksum, artifact URL, PR URL, Plane ticket key, DEV/QA URLs, DEV/QA status, health status, workflow run URL, and `versionStatus=unversioned QA candidate` unless an RC tag already exists.
9. Upload `release.json` to Nexus next to the artifact.
10. If QA passes, move the Plane work item to `plane.qaState`, default `QA`.

## Plane Updates

Use Plane API only. Never use Plane MCP, Docker containers, or direct database access for Plane.

Before mutating Plane, resolve the project UUID and target state ID. If the configured QA state does not exist, stop after adding the deployment comment and report the missing state.

Add a comment with this stable marker:

```text
IA generated QA deployment: {commitSha}
```

Skip adding the comment if an existing comment already contains the same marker.

Include:

- PR URL
- commit SHA
- Nexus artifact URL
- checksum
- DEV URL and status
- DEV `/health` status
- QA URL and status
- QA `/health` status
- workflow run URL when available
- Nexus release manifest URL: `app/{commitSha}/release.json`
- version status: `unversioned QA candidate` unless an RC tag already exists for the commit
- source RC version when already known, otherwise state that RC assignment happens during E2E QA before Done

## Failure Rules

- Do not deploy or promote without a checksum.
- Do not rebuild between DEV and QA.
- Do not move the ticket to QA until QA validation passes.
- Stop on DEV failure.
- Stop on QA failure.
- Stop on DEV or QA `/health` failure.
- Stop when merged PR still has `needs-changes` or `needs-tests`.
- Stop when Nexus is unreachable; do not use a degraded artifact source.
- Treat placeholder config as missing.
- Preserve unrelated local working tree changes.
- Route missing infra, secrets, workflow templates, Azure resources, or branch protection setup to `$configure-dev-environment`.
