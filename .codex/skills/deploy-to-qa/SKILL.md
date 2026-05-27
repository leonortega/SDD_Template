---
name: deploy-to-qa
description: Promote a merged pull request artifact through Nexus, Azure DEV, and Azure QA, then update Plane. Use when Codex needs to verify a merged Gitea PR, locate the linked Plane ticket, confirm the immutable Nexus ZIP artifact and checksum, validate Azure DEV, promote the same artifact to Azure QA, validate QA, comment artifact and deployment links on the ticket, and move the ticket to QA.
---

# Deploy To QA

## Overview

Use this skill after a feature PR has merged to `dev` and the package/deploy workflow has produced a Nexus artifact. The release rule is:

```text
feature branch -> dev -> DEV -> QA -> main -> PROD
```

`main` is updated only after QA passes. PROD promotion is separate and must reuse the QA-passed artifact commit.

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
3. Resolve the Plane ticket key from the branch name, PR title, PR body, commit messages, or existing Plane comments.
4. Verify the package/deploy workflow completed for the merged commit. If it did not run, report that config-infra should be used to repair `.gitea/workflows/package-deploy.yml`.
5. Build the Nexus artifact paths:
   - `app/{commitSha}/app.zip`
   - `app/{commitSha}/app.zip.sha256`
   - `app/{commitSha}/commit.sha`
6. Confirm the artifact, checksum, and commit metadata exist in Nexus using the configured Nexus credentials. Treat missing Nexus local config or any missing file as blocking.
7. Compare `commit.sha` with the resolved commit SHA. Treat mismatch as blocking.

## DEV And QA Promotion

1. Confirm DEV deployment succeeded for the same commit. If DEV failed, add a Plane failure comment and stop.
2. Validate the DEV URL using the workflow smoke-check result or a fresh `curl --fail` when the URL is available.
3. Confirm QA deployment downloaded the same Nexus artifact path used by DEV. Do not rebuild.
4. Validate the QA URL using the workflow smoke-check result or a fresh `curl --fail` when the URL is available.
5. If QA fails, add a Plane failure comment and do not move the ticket state.
6. If QA passes, move the Plane work item to `plane.qaState`, default `QA`.

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
- QA URL and status
- workflow run URL when available

## Failure Rules

- Do not deploy or promote without a checksum.
- Do not rebuild between DEV and QA.
- Do not move the ticket to QA until QA validation passes.
- Stop on DEV failure.
- Stop on QA failure.
- Treat placeholder config as missing.
- Preserve unrelated local working tree changes.
- Route missing infra, secrets, workflow templates, Azure resources, or branch protection setup to `$configure-dev-environment`.
