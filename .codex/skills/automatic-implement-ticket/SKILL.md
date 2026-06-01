---
name: automatic-implement-ticket
description: Orchestrate the full Plane ticket delivery lifecycle by inspecting current Plane, Git, Gitea, Nexus, OpenSpec, QA, tag, and PROD state, then delegating to the correct focused skill. Use when Codex is asked to automatically continue, resume, implement, deploy, QA, or hand off a ticket without the user knowing the current workflow step.
---

# Automatic Implement Ticket

## Overview

Use this master skill as the default high-level entry point for normal ticket delivery. It does not duplicate child skill workflows. It inspects state, chooses the next valid milestone, invokes the focused child skill, and reports the exact blocker when automation cannot continue.

PROD promotion remains explicit. Do not invoke `deploy-to-prod` only because QA passed unless the user explicitly asks to promote to PROD.

## Shared Context

Before routing, follow `.codex/skills/_shared/skill-startup.md`, which reads `.codex/skills/_shared/delivery-contract.md` and `docs/context-management.md`, with `docs/architecture.md` as the stage-specific doc.

## Configuration

Read `.codex/client-tools.local.json` first. Fall back to `.codex/client-tools.example.json` only for structure and defaults. Read `.codex/quality.local.json` when coverage context is needed.

Use ignored `.codex/delivery-context.local.json` as the ticket context lock according to the shared contract. If the lock or durable checkpoints conflict with the resolved ticket, stop or invoke `pipeline-status` instead of routing to a child skill.

## Workflow

Run state inspection, routing, rerun handling, and output reporting as one read-first workflow. Use validation evidence from child skills and durable checkpoints before routing to the next handoff stage.

## State Inspection

Before delegating, inspect as much context as is safely available:

- Plane ticket key, state, generated markers, linked parent/bug tickets, and deployment/QA/PROD comments.
- Current Git branch, branch naming, local dirty state, remote branch, active OpenSpec change, and relevant tags.
- Gitea PR status, target branch, merge status, head/merge commit, AI review markers, stable AI finding ids, human-authored top-level and inline review comments, OpenSpec `## PR Review Feedback` tasks, Plane PR feedback detection/fix batch markers, and `needs-tests` / `needs-changes` labels.
- Nexus artifact files under `app/{commitSha}/`: `app.zip`, `app.zip.sha256`, `commit.sha`, and `release.json`.
- QA evidence marker `IA generated E2E QA: {ticketKey}` and source RC tag.
- PROD marker `IA generated PROD deployment: {finalVersion}` and latest release manifest.
- Active `.codex/delivery-context.local.json` lock and whether branch, PR, artifact, QA, RC, and PROD evidence match its ticket.

If the state is ambiguous, invoke `pipeline-status` or produce a read-only status summary instead of guessing.

## Routing

- Ticket in Todo with no branch: invoke `plane-start-ticket`.

  Before routing, preserve the `plane-start-ticket` Stack Context Preflight:
  - The first ticket must not create a branch, Plane generated block, ticket lock, or OpenSpec proposal until `docs/architecture.md`, `docs/development.md`, `docs/deployment.md`, and `openspec/config.yaml` define the current tool set and tech stack without `stack-context.*` drift from `AuditRecommendedTools`.
  - Treat `.codex/tool-recommendations.example.json` as the tracked shape/template only.
  - When project guidance coverage has not been reviewed, route to `project-guidance-discover` so suggested skills and guidance are shown, additional desired items are requested, and only confirmed skill items are passed to `project-guidance-acquire`.
- Ticket in In Progress with active branch/OpenSpec but no PR: invoke `implement-ticket`.
- Open PR exists: route to `implement-ticket`; it delegates immediate AI review feedback fixes and late human PR feedback fixes to the repo-owned `pr-review-feedback-loop` skill.
- PR merged to `dev` and artifact is not yet promoted to QA: invoke `post-merge-deploy`.
- Ticket in QA: invoke `test-e2e`.
- QA failed with product defect: invoke `file-qa-bug`.
- Ticket in Done with QA-approved RC but no PROD release: stop unless the user explicitly requested PROD; if requested, invoke `deploy-to-prod`.
- PROD incident or regression: invoke `rollback-prod` when restore is needed, or `hotfix-prod` when a targeted code fix is needed.
- User asks where the work stands, or routing has multiple plausible targets: invoke `pipeline-status`.

## Rerun Policy

Treat existing generated comments, branches, PRs, artifacts, QA evidence, and tags as checkpoints. Continue from the latest completed checkpoint instead of restarting earlier steps.

When a child skill stops on a blocker, preserve its blocker classification and do not route around it. Examples:

- Missing Nexus artifact blocks deployment promotion.
- Stale `needs-changes` or `needs-tests` labels block QA promotion.
- Unresolved PR review feedback batches, incomplete OpenSpec `## PR Review Feedback` tasks, or late actionable human PR comments block implementation handoff and QA promotion until fixes are committed, pushed, rerun through AI review, and recorded in Plane.
- A later human comment on the same PR head SHA is not covered by an earlier feedback-fix marker unless its source id is included in that marker's `feedbackBatchId`.
- Missing RC tag blocks PROD promotion.
- QA product defect routes to `file-qa-bug`, not direct code edits inside QA.

## Failure Rules

If routing evidence is ambiguous, validation is missing for the next mutating stage, or the ticket context lock conflicts with durable checkpoints, stop or route to `pipeline-status` instead of guessing.

## Output

Summarize:

- ticket and current state,
- resolved route,
- child skill invoked or blocker found,
- checkpoint evidence used,
- memory updates made or skipped,
- next required user or system action when blocked.
