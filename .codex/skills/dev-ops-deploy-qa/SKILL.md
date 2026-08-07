---
name: dev-ops-deploy-qa
description: >-
  Promote merged pull request artifacts through the selected artifact and deployment adapters into configured
  pre-production environments, then update the ticket adapter. Use when Codex needs to verify a merged PR, locate the
  linked ticket, confirm immutable artifacts and checksums, validate configured environment health checks, comment
  artifact and deployment links, and move the ticket to QA.
---

<!-- TIER 3: STAGE-SPECIFIC - QA deployment skill -->

# Deploy To QA

## Overview

Use this skill after a feature PR has merged to `dev` and the CI pipeline has deployed DEV. The pipeline deploys
**DEV only**; QA is not auto-promoted. This skill verifies the DEV deployment, asks the user for approval to deploy
to QA, dispatches the QA deployment, then validates QA and updates the ticket.

For automatic post-merge coordination and artifact waiting, use `dev-ops-post-merge-deploy` first. The release rule is:

```text
feature branch -> dev -> DEV (CI) -> verify DEV -> user approval -> QA (CI dispatch) -> E2E QA OK -> main -> PROD
```

`main` is updated only after QA passes. PROD promotion is separate and must reuse the QA-passed artifact commit.

## Shared Context

Before promotion, follow `.codex/skills/_shared/skill-startup.md`, which reads `.codex/project-profile.json`,
`.codex/skills/_shared/delivery-contract.md`, and
`docs/conventions/context-management.md`, with `docs/architecture/deployment.md` as the stage-specific doc. Load
selected artifact, deployment, repository/review, and ticket adapters. Use `python -m
tools.sdd_cli dev-flow` helpers: `ArtifactPaths`, `ValidateTicketLock` for `.codex/delivery-context.local.json`,
`ValidateDeploymentLane`, `UpdateReleaseManifest`, `ValidateReleaseManifest`, and
`RenderTicketComment -Type QADeployment`.

For push-triggered pre-production deployment, the commit or merged PR title must start with the ticket key format
configured in `.codex/project-profile.json` at `workflow.ticketKeyPattern`, and the
change must touch configured application or test paths. Non-code changes outside those paths and non-ticket PRs must not
deploy.

## Workflow Telemetry

Apply the shared workflow telemetry pattern (`.codex/skills/_shared/pipeline-workflow-telemetry.md`) with:

- `{workflowStage}` = `dev-ops-deploy-qa`
- `{agentRole}` = `deployment`

Capture UTC start time after resolving the ticket key and before artifact promotion checks. Create or update the
`dev-ops-deploy-qa` entry via `time-telemetry-upsert` (payload in
`.codex/skills/openproject-sprint-backlog/references/openproject-api.md` → Operations → `time-telemetry-upsert`; shared
helpers in `.codex/skills/_shared/api-helpers.md` → OpenProject → Workflow time
telemetry). Use marker `IA generated workflow telemetry: {ticketKey}:dev-ops-deploy-qa`. Resolve the activity via
`python -m tools.sdd_cli dev-flow resolve-openproject-activity --workflow-stage
dev-ops-deploy-qa --input-json '{"timeTelemetry":{...}}'` and reverse-lookup the activity ID. Use `python -m
tools.sdd_cli dev-flow append-telemetry -TicketKey {ticketKey}` only as the JSONL fallback
when direct time telemetry is unavailable. On resume, append or update another row for the same stage; timing rendering
collapses repeated stage rows into earliest start and latest finish. Include
`workflowStage`, `agentRole`, `startedUtc`, `finishedUtc`, `retryCount`, and `outcome`.

## Configuration

Read `.codex/client-tools.local.json` first. Fall back to `.codex/client-tools.common.json` for structure only, then
apply environment variable overrides when present.

Required or defaulted values:

- `selected ticket adapter runtime values`
- `configured QA state`: target state after QA validation. Default: `In testing` (matches OpenProject status ID 9).
- `selected repository/review adapter runtime values`
- `nexus.baseUrl`, `nexus.username`, `nexus.password`, `nexus.repository`

Provider-supported environment variables may override local JSON when present. Repository/review overrides include
`selected repository/review adapter overrides`.

## Workflow

Run preflight, wait for CI pipeline (DEV only), verify DEV, request user approval, dispatch QA, validate QA, ticket
provider updates, and handoff reporting in order. Do not move the ticket to QA until DEV is verified, the user
approves, and QA deployment validation passes.

In idempotent verification mode, do not redeploy or duplicate ticket comments. Re-verify the resolved ticket
(Pre-Deploy Ticket Status Gate applied — ticket in `Developed` before deploy), PR,
artifact commit, QA deployment marker, QA state, release manifest, and available
DEV/QA validation evidence, then append the `dev-ops-deploy-qa` telemetry row and hand off to E2E QA.

### Pre-Deploy Ticket Status Gate (HARD GATE)

**❌ HARD GATE (authority level 5):** Before any QA deployment activity — preflight checks, artifact promotion, or
ticket mutation — the ticket MUST be in the `Developed` state (OpenProject ID 8).

1. Resolve the current ticket state through the selected ticket adapter.
2. If the state is already `Developed` (ID 8), keep it and proceed.
3. If the state is earlier (e.g., `In progress` ID 7 or `Specified` ID 3), transition the ticket to `Developed` (ID 8)
   before running preflight or any deployment mutation.
4. If the state cannot be resolved or the transition fails, stop and report before promoting. Do not deploy to QA
   while the ticket is not in `Developed`.

The ticket moves to the configured QA state (`In testing`, ID 9) only after deployment validation passes (Dispatch QA
step 10).

## Preflight

**Status gate first:** run the Pre-Deploy Ticket Status Gate above before any preflight knowledge consult or
promotion check.

**Knowledge consult before promoting.** Before any QA promotion mutation, consult the knowledge base for deployment,
artifact, and rollback lessons relevant to the release:

```bash
python -m tools.sdd_cli knowledge-search search --query <release or deployment terms>
python -m tools.sdd_cli knowledge-search search --list-topics
```

If an existing `knowledge/lessons-learned/` or `knowledge/troubleshooting/` entry matches the deployment shape, apply it
and cite it in the QA handoff. Record `Knowledge consulted: <files>` or
`Knowledge consulted: none`.

1. Verify the PR is merged and its target branch is `dev`. If the PR merged elsewhere, stop and report the branch
mismatch.

2. Resolve the merged commit SHA from repository PR metadata. Use the merge commit SHA as the artifact identity.
3. Verify the PR does not currently carry `pr.labels.needsChanges` or `pr.labels.needsTests`. If either label remains,
stop before promotion.
4. Resolve the ticket key from the branch name, PR title, PR body, commit messages, or existing ticket comments.
5. Run `ValidateTicketLock` with the resolved ticket key, PR, branch, and merged/artifact commit. If the result is
invalid, stop before reading or promoting artifacts.
6. Verify the selected provider workflow completed for the merged commit. The selected deployment adapter declares the
required workflow. If the expected workflow did not run, report that config-infra
should repair the selected provider workflow.
7. Build the **DEV** Nexus artifact paths declared by the selected artifact and deployment adapters.
   - `app/{commitSha}/deployable-apps.json`
   - one `app/{commitSha}/{artifactName}` per topology app
   - one `app/{commitSha}/{artifactName}.sha256` per topology app
   - `app/{commitSha}/commit.sha`
   - `app/{commitSha}/release-dev.json` (DEV)
   QA artifacts (`release-qa.json`, `qa-targets.json`, `env-urls-qa.json`) do not exist yet — they are produced and
   verified in Dispatch QA after the user-approved deployment.
     selected deployment provider requires:
   - `app/{commitSha}/container-images.json`
   - `app/{commitSha}/monitoring-summary-dev.json` when observability is enabled
8. Confirm the selected provider artifact metadata, runtime artifacts, and commit metadata exist in Nexus using the
configured Nexus credentials. Treat missing Nexus local config, Nexus outage, or any
missing required DEV file as blocking.
9. Compare `commit.sha` with the resolved commit SHA. Treat mismatch as blocking.
10. Read `release-dev.json` when present and verify `ticketKey` matches the locked/resolved ticket
key. Treat another ticket key as blocking cross-ticket promotion.
11. Confirm Nexus contains all DEV deployment metadata required by the selected deployment adapter. Missing deployment
configuration or immutable artifact metadata is blocking workflow drift and routes to
the selected deployment configure path.

## Wait For CI Pipeline (DEV Only)

The CI pipeline deploys **DEV only** on PR merge into `dev`; QA is not auto-promoted. This skill verifies DEV, asks
the user for approval, and dispatches the QA deployment as a separate pipeline run.

1. Verify the CI pipeline (`package-deploy`) was already triggered by the PR merge into `dev` (the workflow runs on a
   `pull_request` closed+merged event, not on push — direct pushes to `dev` never deploy).
2. Poll for the CI pipeline run completion (DEV deployment target only).
3. Wait for the DEV Nexus artifact files:
   - `app/{commitSha}/release-dev.json`
   - `app/{commitSha}/env-urls-dev.json`
   QA artifacts (`release-qa.json`, `env-urls-qa.json`) do not exist yet — they are produced by the user-approved QA
   dispatch in Dispatch QA below.
4. Use bounded waiting: check immediately, then retry with backoff for up to 10 minutes.
5. If the CI pipeline did not run or the DEV artifacts are missing, stop and report. Do not deploy QA separately.

   **DEV health gate in CI:** the pipeline verifies every app's `/health` on the external DEV host URLs immediately
after the DEV rollout and exits when DEV is unhealthy. The DEV Nexus artifacts therefore only exist when the CI DEV
gate passed — evidence DEV was confirmed deployed and healthy.

## DEV Validation

The CI pipeline deployed DEV only (see Wait For CI Pipeline). Verify DEV is fully healthy before asking the user for
approval — never request approval on an unverified DEV.

1. Confirm DEV deployment succeeded by checking `app/{commitSha}/release-dev.json` exists in Nexus. If DEV failed or
artifacts are missing, add a ticket provider failure comment and stop.
2. Validate the DEV URL from `app/latest/env-urls-dev.json` using `curl --fail`. Apply any retry or environment-health
behavior required by the selected deployment adapter.
3. Validate DEV `/health` using the URL from step 2. It must return HTTP 200 and JSON `status=ok`. For fresh checks, use
the same retry/backoff policy.
4. Confirm DEV applied and verified all configuration and artifact metadata required by the selected deployment adapter.
Missing proof is blocking.
5. If any DEV check fails, stop and report — do not ask the user to deploy QA.

## User Approval Gate (HARD GATE)

**❌ HARD GATE (authority level 5):** QA must not be deployed without explicit user approval.

1. After DEV validation passes, present the DEV verification summary to the user and ask for approval to deploy to QA.
2. Wait for an explicit user response. Never auto-approve and never assume consent from silence or a timeout.
3. If the user declines or requests changes, stop. Fix the issues, re-run the DEV pipeline, and re-verify before
asking again.
4. On approval, continue to Dispatch QA below.

## Dispatch QA (After User Approval)

1. Dispatch the QA deployment: `package-deploy` `workflow_dispatch` with `environment=qa` and
   `artifact_commit_sha=<the verified DEV commit SHA>` — reuse the exact artifact commit verified in DEV,
   never rebuild. Include `release_version` / `source_rc_version` when applicable so `release-qa.json` records real
   version data.
2. Wait for the QA pipeline run and the QA Nexus artifacts (`app/{commitSha}/release-qa.json`,
   `app/{commitSha}/env-urls-qa.json`). Use bounded waiting with backoff for up to 10 minutes.
3. Confirm QA deployed the same selected artifact set used by DEV (same commit SHA). Do not rebuild.
4. Validate the QA URL from `app/latest/env-urls-qa.json` using `curl --fail`. For fresh checks, use the same
retry/backoff policy.
5. Validate QA `/health` using the URL from step 4. It must return HTTP 200 and JSON `status=ok`. For fresh checks, use
the same retry/backoff policy.
6. Confirm QA applied and verified all configuration, artifact metadata, target URL, and observability evidence required
by the selected deployment adapter. Missing proof is blocking.
7. If the QA page, `/health`, or deployment configuration validation fails, add a ticket provider failure comment and
do not move the ticket state.
8. Use `UpdateReleaseManifest` to create or update `app/{commitSha}/release-qa.json` with commit SHA, representative
checksum/artifact URL, PR URL, ticket key, DEV/QA URLs, DEV/QA status, per-app
health status, deployment configuration status, workflow run URL, and `versionStatus=unversioned QA candidate` unless an
RC tag already exists.
9. Validate and upload `release-qa.json` to Nexus next to the artifact.
10. If QA passes, move the ticket to `configured QA state`, default `In testing` (OpenProject ID 9).

## Ticket Provider Updates

Use the selected ticket adapter only. Never use MCPs, Docker containers, or direct database access for ticket delivery
unless the selected adapter explicitly requires it.

The Pre-Deploy Ticket Status Gate already moved the ticket to `Developed` (ID 8); this section handles the
post-validation move to the configured QA state. Before mutating ticket state, resolve the target state through the
selected ticket adapter. If the configured QA state does not exist, stop after adding the deployment comment and report
the missing state.

Add a comment with this stable marker:

```text
IA generated QA deployment: {commitSha}
```

Skip adding the comment if an existing comment already contains the same marker.

Keep the marker as the first line by itself. Use `RenderTicketComment -Type QADeployment` with the resolved deployment
data to format the readable Markdown body.

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
- Nexus release manifest URL: `app/{commitSha}/release-qa.json`
- version status: `unversioned QA candidate` unless an RC tag already exists for the commit
- source RC version when already known, otherwise state that RC assignment happens during E2E QA before Done

## Grafana Dashboard Update

After the QA deployment is confirmed successful and the ticket comments are posted, **automatically run the
`grafana-board-update` skill** to update the Grafana SDD Service Status dashboard with the
latest DEV and QA URLs.

1. Fetch `app/latest/env-urls-dev.json` and `app/latest/env-urls-qa.json` from Nexus
2. Follow the workflow in `.codex/skills/grafana-board-update/SKILL.md` to intelligently merge changes into
`infra/monitoring/grafana/dashboards/health-board.json`
3. Commit and push the updated dashboard JSON
4. Optionally push to Grafana API at `http://localhost:3001` for immediate effect

   **⚠️ Note:** If the dashboard is **provisioned from disk** (via
   `infra/monitoring/grafana/provisioning/dashboards/dashboards.yml`), Grafana rejects API writes with `"Cannot save
   provisioned
   dashboard"`. The file-based change is sufficient — provisioning picks it up on next restart (version bump ensures it
   overwrites the DB entry).

## E2E QA Evidence Gate

The E2E suite runs **only after** the QA deployment is confirmed OK (Dispatch QA validation passed) and the ticket is
in `In testing` (OpenProject ID 9) — it runs **against the QA URLs only, never DEV**.

After the QA deployment is confirmed successful, the ticket is in `In testing`, all ticket comments are posted, and
the Grafana dashboard is updated,
**apply the E2E QA evidence contract** in
`.codex/skills/_shared/delivery-contract-qa.md` to validate the deployment against the ticket's acceptance criteria
(which targets the deployed QA URLs).

**This is a required gate.** Do not skip the E2E QA evidence step — the release pipeline must not proceed to PROD
without:

- PASS result and `IA generated E2E QA: {ticketKey}` marker in the ticket comment
- Nexus release manifest updated with `e2eQaStatus: "passed"`
- OpenSpec change archived (per delivery-contract-qa.md → OpenSpec Completion Archive Gate)
- QA trigger branch cleaned up (per delivery-contract-qa.md → QA Evidence Trigger Branch Cleanup)

## Output

Report the ticket, merged PR, artifact commit, DEV/QA URLs, health validation, Nexus release manifest, ticket provider
QA-state update, Grafana dashboard update status, E2E QA evidence gate status,
and next handoff to PROD promotion.

## Failure Rules

- Do not deploy or promote without a checksum.
- Do not rebuild between DEV and QA.
- Do not deploy QA without explicit user approval (User Approval Gate); stop if the user declines or requests changes.
- Do not move the ticket to QA until QA validation passes.
- Stop on DEV failure.
- Stop on QA failure.
- Stop on DEV or QA `/health` failure.
- Stop when selected deployment-adapter configuration verification is missing, failed, or mismatched.
- Stop when selected deployment-adapter immutable artifact metadata, environment health, or observability evidence is
missing when required.
- Stop when merged PR still has `needs-changes` or `needs-tests`.
- Stop when the ticket context lock or `release-qa.json.ticketKey` (or `release-dev.json`) points to a different ticket.
- Stop when the ticket is not in `Developed` (ID 8) before deployment, or the Pre-Deploy Ticket Status Gate
transition fails.
- Stop when Nexus is unreachable; do not use a degraded artifact source.
- Treat placeholder config as missing.
- Preserve unrelated local working tree changes.
- Route missing infra, secrets, workflow templates, selected deployment provider resources, or branch protection setup
to `$configure-dev-environment`.
