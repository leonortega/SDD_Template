---
name: dev-flow-pr-review-feedback-loop
description: Process AI review findings and later human PR comments for an active ticket pull request through selected ticket and review adapters by creating OpenSpec feedback tasks, recording feedback batches, applying fixes, validating, pushing, and rerunning AI review before handoff.
---

# PR Review Feedback Loop

## Overview

Use this repo-owned delivery skill after a pull request exists for an active ticket. It owns the reconnectable PR feedback loop for local delivery.

The loop has two timed phases:

1. AI review runs immediately after PR creation and after every pushed feedback fix.
2. Human review feedback is processed only on a later manual resume, such as `automatically continue this ticket` or `continue E2EPROJECT-123`.

## Shared Context

Before reading or mutating review feedback, follow `.codex/skills/_shared/skill-startup.md`, which reads `.codex/project-profile.json`, `.codex/skills/_shared/provider-adapter-contract.md`, `.codex/skills/_shared/delivery-contract.md`, and `docs/context-management.md`, with `docs/development.md` as the stage-specific doc. Load selected ticket, repository, and review adapters.

Read `.codex/delivery-context.local.json` when present and verify the resolved ticket, branch, PR, and current head SHA match the locked ticket context before mutation.

## Workflow Telemetry

Capture UTC start time after resolving the active ticket and PR. Prefer OpenProject time-entry telemetry and create or update the `dev-flow-pr-review-feedback-loop` entry with marker `IA generated workflow telemetry: {ticketKey}:dev-flow-pr-review-feedback-loop`. Use `python -m tools.sdd_cli delivery -Mode AppendWorkflowTelemetry -TicketKey {ticketKey}` only as the JSONL fallback when direct time telemetry is unavailable. On resume or idempotent reuse, append or update another row for the same stage; workflow timing rendering collapses repeated stage rows into earliest start and latest finish. Include `workflowStage=dev-flow-pr-review-feedback-loop`, `agentRole=reviewFeedback`, `startedUtc`, `finishedUtc`, `retryCount`, and `outcome`. If no active feedback exists and the loop reuses an existing current-head review, record `outcome=SKIP`.

## Configuration

Read `.codex/client-tools.local.json` first. Fall back to `.codex/client-tools.example.json` only for defaults and setup guidance.

Required/defaulted values:

- `selected ticket adapter runtime values`
- `selected repository/review adapter runtime values`
- `pr.labels.reviewed`, `pr.labels.needsTests`, `pr.labels.needsChanges`
- local quality settings used by `dev-flow-implement-ticket`

## Workflow

1. Resolve the ticket, active branch, OpenSpec change, PR number, current head SHA, latest repository workflow status, and current PR labels.
2. Invoke or reuse `dev-flow-pr-review-agent` for the current head SHA. The AI review comment must use `<!-- codex-review-agent:{headSha} -->` and stable finding ids for every finding.
3. Read current PR feedback sources:
   - AI review findings from the latest current-head review-agent comment, including adversarial review findings, `ponytail-review` simplification findings, and verdict when present,
   - human top-level PR comments from the issue comments endpoint,
   - human inline code review comments and review-thread replies from repository/review provider pull review/comment endpoints,
   - existing OpenSpec `## PR Review Feedback` tasks,
   - ticket provider `IA generated PR feedback detected: {headSha}:{feedbackBatchId}` and `IA generated PR feedback fixes: {headSha}:{feedbackBatchId}` markers.
4. Classify each feedback item:
   - `actionable`: clear AI finding or human-requested code, test, documentation, or workflow change scoped to the ticket.
   - `non-actionable`: praise, FYI, already-answered questions, generated output, or source ids already covered by a completed feedback batch.
   - `stale`: outdated diff-line feedback or older-head feedback already satisfied by current code.
   - `ambiguous/conflicting`: unclear request, ticket/OpenSpec/security conflict, or conflict with another human comment.
5. For every actionable AI finding and actionable human comment, including AI `BLOCKER`, `WARNING`, and `SUGGESTION` severities and `ponytail-review` simplification findings, compute `feedbackBatchId` as a deterministic short id from sorted source ids such as AI finding ids, repository/review provider top-level comment ids, and inline review comment ids.
6. Add or update a `## PR Review Feedback` section in the active OpenSpec `tasks.md`. Add one task per feedback item, recording source type, source id or link, head SHA, severity, review mode, `ponytail-review` source when applicable, adversarial verdict when present, and requested change.
7. Before applying fixes, add a ticket comment with marker:

   ```text
   IA generated PR feedback detected: {headSha}:{feedbackBatchId}
   ```

   Include PR link, source ids or links, classifications, and OpenSpec feedback task ids.
   Use the ticket activities API with a `comment.raw` payload. Read activities back and verify the activity comment starts with the marker.
8. Apply the requested code, test, documentation, or workflow change in the existing PR branch. Update OpenSpec specs or design artifacts when behavior changes.
9. Run the relevant validation checks for changed files. Use the same quality-gate discovery and failure classification as `dev-flow-implement-ticket`. If feedback fixes touch deployable project files, deployment manifests, provider-specific deployment infrastructure, or configured package/deploy workflows, run Deployment Topology Review through the selected deployment configure skill and report `Deployment topology: updated`, `Deployment topology: verified`, or `Deployment topology: no deployable app changes` in the ticket provider fix comment.
10. Mark OpenSpec feedback tasks complete only after code and validation are complete.
11. Commit with the ticket key: commit the feedback batch as its own ticket-prefixed commit when tracked changes exist. Skip empty commits. Do not automatically stash normal ticket progress; use stash only for unrelated local or user changes that block the fix. Push the fix commit, then add a ticket comment with marker:

   ```text
   IA generated PR feedback fixes: {headSha}:{feedbackBatchId}
   ```

   Keep the marker as the first line by itself, followed by a blank line and a reviewer-facing Markdown summary. The body must be human-readable, not only automation evidence, and must include:

   - `**Status:** READY FOR REVIEW | BLOCKED | PARTIAL - short outcome`
   - `**Reviewer feedback addressed:**` source ids or links plus a short human summary of each comment
   - `**How IA resolved it:**` concrete changes in reviewer language, not only file names or task ids
   - `**Changed:**` commit SHA pushed, PR link, and completed OpenSpec feedback tasks
   - `**Validation:**` checks run and results
   - `**Reviewer readiness:**` what the reviewer should re-check, plus remaining blockers or `None`
   - `**Skipped comments:**` only when non-actionable, stale, duplicate, generated, ambiguous, or conflicting comments were skipped

   Include stash notes when relevant without exposing secrets or noisy tool output.
   Use the ticket activities API with a `comment.raw` payload. If a generated activity is missing or wrong, add a corrected marker activity and then read activities back before handoff.
12. Rerun the AI review loop on the new head before returning to human review or implementation handoff.

Keep ticket provider in `In Review` while late human feedback fixes are applied. Do not move the ticket backward unless another workflow rule explicitly requires it.

## Output

Report the ticket, branch, PR URL, original and new head SHA, feedback batch id, OpenSpec feedback tasks created or completed, commits pushed, validation run, PR labels, ticket comments added, and handoff status.

## Failure Rules

- Missing branch, PR, ticket, or OpenSpec change: stop and route back to `dev-flow-implement-ticket`.
- Ticket context lock mismatch: stop before Git, ticket provider, repository/review provider, or OpenSpec mutation.
- Missing or placeholder API token: stop before ticket provider or repository/review provider mutation.
- Ambiguous or conflicting human feedback: stop before changing code, request clarification in the PR when possible, record the blocker in ticket provider, and leave ticket provider in its current state.
- Feedback source ids already covered by a completed feedback batch: do not duplicate tasks or ticket comments.
- Adversarial verdict `FAIL`: keep feedback tasks open until fixes and validation are complete and a new current-head review no longer fails.
- OpenSpec `## PR Review Feedback` tasks remain incomplete: do not hand off for merge or QA promotion.
- `needs-tests` or `needs-changes` remains valid after fixes: do not remove the label or hand off.
- Validation failure after applying feedback: keep the task open, classify the failure, and report the blocker.
