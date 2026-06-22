---
name: dev-ops-post-merge-deploy
description: Coordinate the post-merge transition from a merged pull request into QA deployment by validating review labels, resolving the merge commit, waiting for artifact metadata, and delegating promotion to dev-ops-deploy-qa through selected project-profile adapters. Use after a PR merges or when Codex is asked to trigger or continue QA deployment for merged work.
---

# Post Merge Deploy

## Overview

Use this skill after a PR has merged to `dev` but before QA promotion. It is an orchestration bridge: validate the merged PR is eligible, wait for the immutable artifact, then invoke `dev-ops-deploy-qa`.

Do not perform DEV/QA validation inside this skill. `dev-ops-deploy-qa` owns artifact promotion and environment checks.

## Shared Context

Before running, follow `.codex/skills/_shared/skill-startup.md`, which reads `.codex/project-profile.json`, `.codex/skills/_shared/provider-adapter-contract.md`, `.codex/skills/_shared/delivery-contract.md`, and `docs/context-management.md`, with `docs/deployment.md` as the stage-specific doc. Load selected repository/review, artifact, deployment, and ticket adapters. Use `.codex/skills/_shared/scripts/delivery_tools.ps1` helpers: `ValidateTicketLock` for `.codex/delivery-context.local.json`, `ValidateDeploymentLane`, and `ArtifactPaths`.

## Workflow Telemetry

Capture UTC start time after resolving the ticket key and before post-merge validation or artifact waiting. Append a `dev-ops-post-merge-deploy` row with `.codex/skills/_shared/scripts/delivery_tools.ps1 -Mode AppendWorkflowTelemetry -TicketKey {ticketKey}` when the bridge succeeds, blocks, fails, or is skipped idempotently because QA deployment is already complete. On resume or idempotent reuse, append another row for the same stage; workflow timing rendering collapses repeated stage rows into earliest start and latest finish. Include `workflowStage=dev-ops-post-merge-deploy`, `agentRole=deployment`, `startedUtc`, `finishedUtc`, `retryCount`, and `outcome`. Do not duplicate the `dev-ops-deploy-qa` row; `dev-ops-deploy-qa` records its own stage when invoked.

## Configuration

Read `.codex/client-tools.local.json` first. Required values are Plane, Gitea, and Nexus settings used by `dev-ops-deploy-qa`.

## Workflow

1. Resolve the PR from user input, current branch, Plane comments, commit messages, or ticket key.
2. Verify the PR is merged and its target branch is `dev`.
3. Verify the PR does not currently have configured `pr.labels.needsChanges` or `pr.labels.needsTests`.
4. Resolve the merge commit SHA from Gitea metadata.
5. Resolve the Plane ticket key from the PR title/body, branch name, commit messages, or Plane comments.
6. Run `ValidateTicketLock` with the resolved ticket key, PR number, branch, and merge/artifact commit when known. If the result is invalid, stop before waiting for artifacts.
7. Poll for the Nexus artifact files for the merge commit according to the selected deployment provider. For Azure App Service, require:
   - `app/{commitSha}/deployable-apps.json`
   - one `app/{commitSha}/{artifactName}` per topology app
   - one `app/{commitSha}/{artifactName}.sha256` per topology app
   - `app/{commitSha}/commit.sha`
   - `app/{commitSha}/release.json` when present
   For Rancher Desktop, require:
   - `app/{commitSha}/container-images.json`
   - `app/{commitSha}/commit.sha`
   - `app/{commitSha}/release.json`
   - `app/{commitSha}/monitoring-summary-dev.json` and `app/{commitSha}/monitoring-summary-qa.json` when DEV/QA deployment already completed
8. Use bounded waiting: check immediately, then retry with backoff for up to 10 minutes unless the user asked for a shorter wait.
9. Verify `commit.sha` matches the merge commit before delegating.
10. If `release.json` exists, verify `planeTicketKey` matches the locked/resolved ticket key.
11. Invoke `dev-ops-deploy-qa` with the resolved PR, ticket key, and merge commit. If QA deployment is already complete, invoke `dev-ops-deploy-qa` in idempotent verification mode so that stage records its own telemetry row without duplicating Plane comments or state changes.

## Idempotency

- If the QA deployment marker `IA generated QA deployment: {commitSha}` already exists and the ticket is in QA, append `dev-ops-post-merge-deploy` telemetry, invoke `dev-ops-deploy-qa` idempotently, and report that QA promotion is already complete.
- If the artifact exists, skip waiting and delegate immediately.
- If labels were stale but have since been removed, continue.

## Output

Report the PR, merge commit, artifact availability, validation status, deployment-lane result, invoked child skill, and handoff to QA or the blocker found.

## Failure Rules

- Unmerged PR: stop and report the PR state.
- PR target is not `dev`: stop and report the mismatch.
- Stale `needs-changes` or `needs-tests` labels: stop before artifact promotion.
- Nexus artifact missing after the wait window: stop and report provider-specific artifact paths checked.
- Nexus unavailable: stop; do not use a degraded artifact source.
- Commit metadata mismatch: stop and report the expected and actual commit SHA.
