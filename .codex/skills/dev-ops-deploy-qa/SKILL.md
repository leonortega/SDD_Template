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

Before promotion, follow `.codex/skills/_shared/skill-startup.md`, which reads `.codex/project-profile.json`, `.codex/skills/_shared/provider-adapter-contract.md`, `.codex/skills/_shared/delivery-contract.md`, and `docs/context-management.md`, with `docs/deployment.md` as the stage-specific doc. Load selected artifact, deployment, repository/review, and ticket adapters. Use `python -m tools.sdd_cli delivery` helpers: `ArtifactPaths`, `ValidateTicketLock` for `.codex/delivery-context.local.json`, `ValidateDeploymentLane`, `UpdateReleaseManifest`, `ValidateReleaseManifest`, and `RenderTicketComment -Type QADeployment`.

For push-triggered pre-production deployment, the commit or merged PR title must start with the ticket key format configured in `.codex/project-profile.json` at `workflow.ticketKeyPattern`, and the change must touch configured application or test paths. Non-code changes outside those paths and non-ticket PRs must not deploy.

## Workflow Telemetry

Capture UTC start time after resolving the ticket key and before artifact promotion checks. Prefer OpenProject time-entry telemetry and create or update the `dev-ops-deploy-qa` entry with marker `IA generated workflow telemetry: {ticketKey}:dev-ops-deploy-qa`. Use `python -m tools.sdd_cli delivery -Mode AppendWorkflowTelemetry -TicketKey {ticketKey}` only as the JSONL fallback when direct time telemetry is unavailable. On resume or idempotent reuse, append or update another row for the same stage; workflow timing rendering collapses repeated stage rows into earliest start and latest finish. Include `workflowStage=dev-ops-deploy-qa`, `agentRole=deployment`, `startedUtc`, `finishedUtc`, `retryCount`, and `outcome`.

## Configuration

Read `.codex/client-tools.local.json` first. Fall back to `.codex/client-tools.common.json` for structure only, then apply environment variable overrides when present.

Required or defaulted values:

- `selected ticket adapter runtime values`
- `configured QA state`: target state after QA validation. Default: `QA`.
- `selected repository/review adapter runtime values`
- `nexus.baseUrl`, `nexus.username`, `nexus.password`, `nexus.repository`

Provider-supported environment variables may override local JSON when present. Repository/review overrides include `selected repository/review adapter overrides`.

## Workflow

Run preflight, DEV/QA promotion, ticket provider updates, and handoff reporting in order. Do not move the ticket to QA until deployment validation and release manifest validation pass.

In idempotent verification mode, do not redeploy or duplicate ticket comments. Re-verify the resolved ticket, PR, artifact commit, QA deployment marker, QA state, release manifest, and available DEV/QA validation evidence, then append the `dev-ops-deploy-qa` telemetry row and hand off to E2E QA.

## Preflight

1. Verify the PR is merged and its target branch is `dev`. If the PR merged elsewhere, stop and report the branch mismatch.
2. Resolve the merged commit SHA from repository PR metadata. Use the merge commit SHA as the artifact identity.
3. Verify the PR does not currently carry `pr.labels.needsChanges` or `pr.labels.needsTests`. If either label remains, stop before promotion.
4. Resolve the ticket key from the branch name, PR title, PR body, commit messages, or existing ticket comments.
5. Run `ValidateTicketLock` with the resolved ticket key, PR, branch, and merged/artifact commit. If the result is invalid, stop before reading or promoting artifacts.
6. Verify the selected provider workflow completed for the merged commit. The selected deployment adapter declares the required workflow. If the expected workflow did not run, report that config-infra should repair the selected provider workflow.
7. Build the Nexus artifact paths declared by the selected artifact and deployment adapters.
   - `app/{commitSha}/deployable-apps.json`
   - one `app/{commitSha}/{artifactName}` per topology app
   - one `app/{commitSha}/{artifactName}.sha256` per topology app
   - `app/{commitSha}/commit.sha`
   - `app/{commitSha}/release.json`
   selected deployment provider requires:
   - `app/{commitSha}/container-images.json`
   - `app/{commitSha}/commit.sha`
   - `app/{commitSha}/release.json`
   - `app/{commitSha}/qa-targets.json` after QA deployment
   - `app/{commitSha}/monitoring-summary-dev.json`, `app/{commitSha}/monitoring-summary-qa.json`, and `app/{commitSha}/qa-observability.json` when observability is enabled
8. Confirm the selected provider artifact metadata, runtime artifacts, and commit metadata exist in Nexus using the configured Nexus credentials. Treat missing Nexus local config, Nexus outage, or any missing required file as blocking.
9. Compare `commit.sha` with the resolved commit SHA. Treat mismatch as blocking.
10. Read `release.json` when present and verify `ticketKey` matches the locked/resolved ticket key. Treat another ticket key as blocking cross-ticket promotion.
11. Confirm Nexus contains all deployment metadata required by the selected deployment adapter. Missing deployment configuration or immutable artifact metadata is blocking workflow drift and routes to the selected deployment configure path.

## DEV And QA Promotion

1. Confirm DEV deployment succeeded for the same commit. If DEV failed, add a ticket provider failure comment and stop.
2. Validate the DEV URL using the workflow smoke-check result or a fresh `curl --fail` when the URL is available. Apply any retry or environment-health behavior required by the selected deployment adapter.
3. Validate DEV `/health` using workflow output or a fresh request. It must return HTTP 200 and JSON `status=ok`. For fresh checks, use the same retry/backoff policy.
4. Confirm DEV applied and verified all configuration and artifact metadata required by the selected deployment adapter. Missing proof is blocking.
5. Confirm QA deployed the same selected artifact set used by DEV. Do not rebuild.
6. Validate the QA URL using the workflow smoke-check result or a fresh `curl --fail` when the URL is available. For fresh checks, use the same retry/backoff policy.
7. Validate QA `/health` using workflow output or a fresh request. It must return HTTP 200 and JSON `status=ok`. For fresh checks, use the same retry/backoff policy.
8. Confirm QA applied and verified all configuration, artifact metadata, target URL, and observability evidence required by the selected deployment adapter. Missing proof is blocking.
9. If DEV or QA page, `/health`, or deployment configuration validation fails, add a ticket provider failure comment and do not move the ticket state.
10. Use `UpdateReleaseManifest` to create or update `app/{commitSha}/release.json` with commit SHA, representative checksum/artifact URL, PR URL, ticket key, DEV/QA URLs, DEV/QA status, per-app health status, deployment configuration status, workflow run URL, and `versionStatus=unversioned QA candidate` unless an RC tag already exists.
11. Validate and upload `release.json` to Nexus next to the artifact.
12. If QA passes, move the ticket to `configured QA state`, default `QA`.

## Ticket Provider Updates

Use the selected ticket adapter only. Never use MCPs, Docker containers, or direct database access for ticket delivery unless the selected adapter explicitly requires it.

Before mutating ticket state, resolve the target state through the selected ticket adapter. If the configured QA state does not exist, stop after adding the deployment comment and report the missing state.

Add a comment with this stable marker:

```text
IA generated QA deployment: {commitSha}
```

Skip adding the comment if an existing comment already contains the same marker.

Keep the marker as the first line by itself. Use `RenderTicketComment -Type QADeployment` with the resolved deployment data to format the readable Markdown body.

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

Report the ticket, merged PR, artifact commit, DEV/QA URLs, health validation, Nexus release manifest, ticket provider QA-state update, and next handoff to E2E QA.

## Failure Rules

- Do not deploy or promote without a checksum.
- Do not rebuild between DEV and QA.
- Do not move the ticket to QA until QA validation passes.
- Stop on DEV failure.
- Stop on QA failure.
- Stop on DEV or QA `/health` failure.
- Stop when selected deployment-adapter configuration verification is missing, failed, or mismatched.
- Stop when selected deployment-adapter immutable artifact metadata, environment health, or observability evidence is missing when required.
- Stop when merged PR still has `needs-changes` or `needs-tests`.
- Stop when the ticket context lock or `release.json.ticketKey` points to a different ticket.
- Stop when Nexus is unreachable; do not use a degraded artifact source.
- Treat placeholder config as missing.
- Preserve unrelated local working tree changes.
- Route missing infra, secrets, workflow templates, selected deployment provider resources, or branch protection setup to `$configure-dev-environment`.
