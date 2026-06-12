---
name: pr-review-feedback-loop
description: Process AI review findings and later human PR comments for an active ticket PR by creating OpenSpec feedback tasks, recording Plane feedback batches, applying fixes, validating, pushing, and rerunning AI review before handoff.
---

# PR Review Feedback Loop

## Overview

Use this repo-owned delivery skill after a Gitea PR exists for an active Plane ticket. It owns the reconnectable PR feedback loop that must not live in external `openspec-*` skills.

The loop has two timed phases:

1. AI review runs immediately after PR creation and after every pushed feedback fix.
2. Human review feedback is processed only on a later manual resume, such as `automatically continue this ticket` or `continue E2EPROJECT-123`.

## Shared Context

Before reading or mutating review feedback, follow `.codex/skills/_shared/skill-startup.md`, which reads `.codex/skills/_shared/delivery-contract.md` and `docs/context-management.md`, with `docs/development.md` as the stage-specific doc.

Read `.codex/delivery-context.local.json` when present and verify the resolved ticket, branch, PR, and current head SHA match the locked ticket context before mutation.

## Workflow Telemetry

Capture UTC start time after resolving the active ticket and PR. Append one `pr-review-feedback-loop` row with `.codex/skills/_shared/scripts/delivery_tools.ps1 -Mode AppendWorkflowTelemetry -TicketKey {ticketKey}` when feedback handling succeeds, blocks, fails, or is skipped idempotently. Include `workflowStage=pr-review-feedback-loop`, `agentRole=reviewFeedback`, `startedUtc`, `finishedUtc`, `retryCount`, and `outcome`. If no active feedback exists and the loop reuses an existing current-head review, record `outcome=SKIP`.

## Configuration

Read `.codex/client-tools.local.json` first. Fall back to `.codex/client-tools.example.json` only for defaults and setup guidance.

Required/defaulted values:

- `plane.baseUrl`, `plane.apiToken`, `plane.workspaceSlug`, `plane.projectIdentifier`
- `gitea.baseUrl`, `gitea.apiToken`, `gitea.owner`, `gitea.repo`
- `pr.labels.reviewed`, `pr.labels.needsTests`, `pr.labels.needsChanges`
- local quality settings used by `implement-ticket`

## Workflow

1. Resolve the Plane ticket, active branch, OpenSpec change, PR number, current head SHA, latest Gitea Actions status, and current PR labels.
2. Invoke or reuse `gitea-pr-review-agent` for the current head SHA. The AI review comment must use `<!-- codex-review-agent:{headSha} -->` and stable finding ids for every finding.
3. Read current PR feedback sources:
   - AI review findings from the latest current-head review-agent comment, including adversarial review findings and verdict when present,
   - human top-level PR comments from the issue comments endpoint,
   - human inline code review comments and review-thread replies from Gitea pull review/comment endpoints,
   - existing OpenSpec `## PR Review Feedback` tasks,
   - Plane `IA generated PR feedback detected: {headSha}:{feedbackBatchId}` and `IA generated PR feedback fixes: {headSha}:{feedbackBatchId}` markers.
4. Classify each feedback item:
   - `actionable`: clear AI finding or human-requested code, test, documentation, or workflow change scoped to the ticket.
   - `non-actionable`: praise, FYI, already-answered questions, generated output, or source ids already covered by a completed feedback batch.
   - `stale`: outdated diff-line feedback or older-head feedback already satisfied by current code.
   - `ambiguous/conflicting`: unclear request, ticket/OpenSpec/security conflict, or conflict with another human comment.
5. For every actionable AI finding and actionable human comment, including AI `BLOCKER`, `WARNING`, and `SUGGESTION` severities, compute `feedbackBatchId` as a deterministic short id from sorted source ids such as AI finding ids, Gitea top-level comment ids, and inline review comment ids.
6. Add or update a `## PR Review Feedback` section in the active OpenSpec `tasks.md`. Add one task per feedback item, recording source type, source id or link, head SHA, severity, review mode, adversarial verdict when present, and requested change.
7. Before applying fixes, add a Plane comment with marker:

   ```text
   IA generated PR feedback detected: {headSha}:{feedbackBatchId}
   ```

   Include PR link, source ids or links, classifications, and OpenSpec feedback task ids.
   Use the Plane work-item comments API payload fields `comment_html` and `comment_stripped`; do not use Gitea-style `comment` or `body` fields. Read the comment back and verify `comment_stripped` starts with the marker so the workflow cannot silently create a blank Plane comment.
8. Apply the requested code, test, documentation, or workflow change in the existing PR branch. Update OpenSpec specs or design artifacts when behavior changes.
9. Run the relevant validation checks for changed files. Use the same quality-gate discovery and failure classification as `implement-ticket`. If feedback fixes touch `src/**.csproj`, `src/**/Program.cs`, `src/**/appsettings*.json`, `infra/deployment/**`, `infra/azure/**`, or `.gitea/workflows/package-deploy.yml`, run Deployment Topology Review through `configure-azure-environments` and report `Deployment topology: updated`, `Deployment topology: verified`, or `Deployment topology: no deployable app changes` in the Plane fix comment.
10. Mark OpenSpec feedback tasks complete only after code and validation are complete.
11. Commit the feedback batch as its own ticket-prefixed commit when tracked changes exist. Skip empty commits. Do not automatically stash normal ticket progress; use stash only for unrelated local or user changes that block the fix. Push the fix commit, then add a Plane comment with marker:

   ```text
   IA generated PR feedback fixes: {headSha}:{feedbackBatchId}
   ```

   Include source ids or links addressed, OpenSpec tasks completed, commit SHA pushed, validation run, skipped comments, stash notes when relevant, and remaining blockers.
   Use the Plane work-item comments API payload fields `comment_html` and `comment_stripped`; do not use Gitea-style `comment` or `body` fields. If a generated comment is accidentally blank, patch that comment id with the same payload shape and then read it back before handoff.
12. Rerun the AI review loop on the new head before returning to human review or implementation handoff.

Keep Plane in `In Review` while late human feedback fixes are applied. Do not move the ticket backward unless another workflow rule explicitly requires it.

## Output

Report the ticket, branch, PR URL, original and new head SHA, feedback batch id, OpenSpec feedback tasks created or completed, commits pushed, validation run, PR labels, Plane comments added, and handoff status.

## Failure Rules

- Missing branch, PR, Plane ticket, or OpenSpec change: stop and route back to `implement-ticket`.
- Ticket context lock mismatch: stop before Git, Plane, Gitea, or OpenSpec mutation.
- Missing or placeholder API token: stop before Plane or Gitea mutation.
- Ambiguous or conflicting human feedback: stop before changing code, request clarification in the PR when possible, record the blocker in Plane, and leave Plane in its current state.
- Feedback source ids already covered by a completed feedback batch: do not duplicate tasks or Plane comments.
- Adversarial verdict `FAIL`: keep feedback tasks open until fixes and validation are complete and a new current-head review no longer fails.
- OpenSpec `## PR Review Feedback` tasks remain incomplete: do not hand off for merge or QA promotion.
- `needs-tests` or `needs-changes` remains valid after fixes: do not remove the label or hand off.
- Validation failure after applying feedback: keep the task open, classify the failure, and report the blocker.
