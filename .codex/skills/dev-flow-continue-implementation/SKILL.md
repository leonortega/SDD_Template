---
name: dev-flow-continue-implementation
description: Orchestrate the full configured ticket delivery lifecycle by inspecting current ticket, repository, review, artifact, OpenSpec, QA, tag, and production state through the selected project-profile adapters, then delegating to the correct focused skill. Use when Codex is asked to automatically continue, resume, implement, deploy, QA, or hand off a ticket without the user knowing the current workflow step.
---

# Automatic Implement Ticket

## Overview

Use this master skill as the default high-level entry point for normal ticket delivery. It does not duplicate child skill workflows. It inspects state, chooses the next valid milestone, invokes the focused child skill, and reports the exact blocker when automation cannot continue.

PROD promotion remains explicit. Do not invoke `dev-ops-deploy-prod` only because QA passed unless the user explicitly asks to promote to PROD.

## Shared Context

Before routing, follow `.codex/skills/_shared/skill-startup.md`, which reads `.codex/project-profile.json`, `.codex/skills/_shared/provider-adapter-contract.md`, `.codex/skills/_shared/delivery-contract.md`, and `docs/context-management.md`, with `docs/architecture.md` as the stage-specific doc. Load only selected adapters needed to inspect the current route.

## Configuration

Read `.codex/client-tools.local.json` first. Fall back to `.codex/client-tools.example.json` only for structure and defaults. Read `.codex/quality.local.json` when coverage context is needed.

Use ignored `.codex/delivery-context.local.json` as the ticket context lock according to the shared contract. If the lock or durable checkpoints conflict with the resolved ticket, stop or invoke `dev-flow-pipeline-status` instead of routing to a child skill.

## Workflow

Run state inspection, routing, rerun handling, and output reporting as one read-first workflow. Use validation evidence from child skills and durable checkpoints before routing to the next handoff stage.

Before delegating child work, apply the shared delivery contract's risk-adaptive depth and installed-skill runtime index rules:

- Resolve delivery risk from ticket, OpenSpec, PR/diff, artifact, and deployment evidence when enough information exists.
- Use compact summaries for low-risk routing, but never skip ticket, branch, PR, validation, QA, artifact, PROD, rollback, or secret-safety gates.
- For high-risk routes, preserve full acceptance/spec context and tell the child skill whether adversarial review, deployment topology checks, or workload forecast resolution is required.
- When a current installed-skill index exists, use it only to pass exact `SKILL.md` paths to child agents. If it is missing or stale, report that it should be regenerated; do not treat it as a replacement for `project-guidance-*`.

Each child delivery skill owns its own workflow telemetry row. Do not append telemetry for a delegated child stage from this router, or the timing comment will double count the stage. This router may append one non-secret `dev-flow-continue-implementation` row with `.codex/skills/_shared/scripts/delivery_tools.ps1 -Mode AppendWorkflowTelemetry -TicketKey {ticketKey}` only when it performs meaningful routing work before or after delegation. Include `workflowStage`, `agentRole`, `startedUtc`, `finishedUtc`, `elapsedMilliseconds`, `retryCount`, and `outcome`; include model, reasoning effort, token counts, cached tokens, tool-call count, and blocker category when the platform exposes them, otherwise leave those optional values null. On resume, create `.codex/agent-telemetry.local.jsonl` if missing, but do not clear existing rows for the same active ticket.

Workflow timing comments use stable marker `IA generated workflow timing: {ticketKey}` and are finalized by `quality-test-e2e` after the E2E QA OpenProject comment is verified. During routing, read existing OpenProject comments when the API allows it and report whether the workflow timing marker is present, missing, or blocked; do not derive timing from OpenProject generated marker timestamps.

Before routing to a later workflow stage, read active ticket telemetry when `.codex/agent-telemetry.local.jsonl` exists and compare it with durable checkpoints. Required predecessor rows are `dev-flow-start-ticket`, `dev-flow-implement-ticket`, `dev-flow-pr-review-agent`, `dev-ops-post-merge-deploy`, `dev-ops-deploy-qa`, and `quality-test-e2e`; `dev-flow-pr-review-feedback-loop` is required only when unresolved PR feedback exists or feedback markers/tasks show it ran. If durable evidence says a predecessor stage completed but its telemetry row is missing, route through that predecessor in idempotent verification mode before advancing. Do not route directly to `quality-test-e2e` for a QA ticket when `dev-ops-post-merge-deploy` or `dev-ops-deploy-qa` telemetry is missing; first route through `dev-ops-post-merge-deploy`, which must invoke `dev-ops-deploy-qa` idempotently. Do not route directly to later PR handoff when an existing current-head review marker lacks `dev-flow-pr-review-agent` telemetry; route through idempotent `dev-flow-pr-review-agent`.

## State Inspection

Before delegating, inspect as much context as is safely available:

- OpenProject work package key, state, generated markers, linked parent/bug tickets, workflow timing marker, and deployment/QA/PROD comments.
- Current Git branch, branch naming, local dirty state, remote branch, active OpenSpec change, and relevant tags.
- Gitea PR status, target branch, merge status, head/merge commit, AI review markers, stable AI finding ids, human-authored top-level and inline review comments, OpenSpec `## PR Review Feedback` tasks, OpenProject PR feedback detection/fix batch markers, and `needs-tests` / `needs-changes` labels.
- Nexus artifact files under `app/{commitSha}/` for the selected provider: Azure uses `deployable-apps.json`, each manifest app ZIP/checksum pair, `commit.sha`, and `release.json`; k3d uses `container-images.json`, `commit.sha`, `release.json`, and monitoring summaries.
- QA evidence marker `IA generated E2E QA: {ticketKey}` and source RC tag.
- PROD marker `IA generated PROD deployment: {finalVersion}` and latest release manifest.
- Active `.codex/delivery-context.local.json` lock and whether branch, PR, artifact, QA, RC, and PROD evidence match its ticket.

If the state is ambiguous, invoke `dev-flow-pipeline-status` or produce a read-only status summary instead of guessing.

## Routing

- Ticket in Todo with no branch: invoke `dev-flow-start-ticket`.

  Before routing, preserve the `dev-flow-start-ticket` Stack Context Preflight:
  - The first ticket must not create a branch, OpenProject generated block, ticket lock, or OpenSpec proposal until `docs/architecture.md`, `docs/development.md`, `docs/deployment.md`, and `openspec/config.yaml` define the current tool set and tech stack without `stack-context.*` drift from `AuditRecommendedTools`.
  - Treat `.codex/tool-recommendations.example.json` as the tracked shape/template only.
  - When project guidance coverage has not been reviewed, route to `project-guidance-discover` so extra useful skills, MCPs, plugins, tools, references, practices, standards, and Codex-applicable IDE helpers are researched before suggestions are shown, and only confirmed items are passed to `project-guidance-acquire`.
- Ticket in In Progress with active branch/OpenSpec but no PR: invoke `dev-flow-implement-ticket`.
- Open PR exists: route to `dev-flow-implement-ticket`; it delegates immediate AI review feedback fixes and late human PR feedback fixes to the repo-owned `dev-flow-pr-review-feedback-loop` skill.
- PR merged to `dev` and artifact is not yet promoted to QA: invoke `dev-ops-post-merge-deploy`.
- PR merged to `dev`, QA deployment evidence already exists, but `dev-ops-post-merge-deploy` or `dev-ops-deploy-qa` telemetry is missing: invoke `dev-ops-post-merge-deploy` in idempotent verification mode before `quality-test-e2e`.
- Ticket in QA: invoke `quality-test-e2e` only after required predecessor telemetry exists.
- QA failed with product defect: invoke `dev-flow-file-qa-bug`.
- Ticket in Done with QA-approved RC but no PROD release: stop unless the user explicitly requested PROD; if requested, invoke `dev-ops-deploy-prod`.
- PROD incident or regression: invoke `dev-ops-rollback-prod` when restore is needed, or `dev-ops-hotfix-prod` when a targeted code fix is needed.
- User asks where the work stands, or routing has multiple plausible targets: invoke `dev-flow-pipeline-status`.

## Rerun Policy

Treat existing generated comments, branches, PRs, artifacts, QA evidence, and tags as checkpoints. Continue from the latest completed checkpoint instead of restarting earlier steps.

When a child skill stops on a blocker, preserve its blocker classification and do not route around it. Examples:

- Missing Nexus artifact blocks deployment promotion.
- Stale `needs-changes` or `needs-tests` labels block QA promotion.
- Unresolved PR review feedback batches, incomplete OpenSpec `## PR Review Feedback` tasks, or late actionable human PR comments block implementation handoff and QA promotion until fixes are committed, pushed, rerun through AI review, and recorded in OpenProject.
- A later human comment on the same PR head SHA is not covered by an earlier feedback-fix marker unless its source id is included in that marker's `feedbackBatchId`.
- Missing RC tag blocks PROD promotion.
- QA product defect routes to `dev-flow-file-qa-bug`, not direct code edits inside QA.

## Failure Rules

If routing evidence is ambiguous, validation is missing for the next mutating stage, or the ticket context lock conflicts with durable checkpoints, stop or route to `dev-flow-pipeline-status` instead of guessing.

## Output

Summarize:

- ticket and current state,
- resolved route,
- delivery risk and whether compact or full depth was used,
- child skill invoked or blocker found,
- checkpoint evidence used,
- workflow timing comment added, updated, reused, or skipped with reason,
- memory updates made or skipped,
- next required user or system action when blocked.
