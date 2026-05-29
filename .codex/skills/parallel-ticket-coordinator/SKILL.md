---
name: parallel-ticket-coordinator
description: Coordinate multiple Plane tickets through role-specialized delivery agents by assigning one Git worktree and one local ticket lock per active ticket while serializing shared deployment lanes.
---

# Parallel Ticket Coordinator

## Overview

Use this skill when the user asks to process more than one Plane ticket at the same time, run parallel ticket delivery, create parallel role agents, or coordinate concurrent Plane work.

This skill orchestrates existing role skills. It does not duplicate child workflows and does not implement ticket-specific code itself.

## Shared Context

Before routing, read `.codex/skills/_shared/delivery-contract.md`, `docs/context-management.md`, and `docs/architecture.md` so one Git worktree per active ticket, ticket context locks, deployment lane ownership, markers, context freshness, and rerun rules match the rest of the delivery workflow.

## Configuration

Read `.codex/client-tools.local.json` first. Fall back to `.codex/client-tools.example.json` only for structure and safe defaults. Required/defaulted values:

- `parallelDelivery.enabled`, default `false`
- `parallelDelivery.maxActiveTickets`, default `2`
- `parallelDelivery.worktreeRoot`, default `../ticket-worktrees`
- `parallelDelivery.deploymentLanePolicy`, default `serialized`
- `parallelDelivery.agentModelPolicy`, default to the placeholder-safe role policy in `.codex/client-tools.example.json`
- `git.baseBranch`, default `dev`
- Plane, Gitea, Nexus, PR label, and quality config used by delegated child skills

Never print, commit, paste into tickets, or write real Plane, Gitea, Nexus, Azure, cookie, or session secrets. When copying ignored local config into a ticket worktree, report only filenames copied, never values.

## Agent Model Policy

Use `parallelDelivery.agentModelPolicy` when spawning sub-agents. Each entry maps a delivery role to:

- `model`: a Codex model id, or `inherit` to omit the model override and use the parent run's model.
- `reasoningEffort`: `low`, `medium`, `high`, or `xhigh`, passed as the sub-agent reasoning effort when supported.

Default role mapping:

- `coordinator`: own this skill and final integration; use `inherit` with `medium` reasoning unless the user requests otherwise.
- `pipelineStatus`: read-only status checks; use a low-cost model with `low` reasoning.
- `ticketStarter`: branch/worktree/ticket start; use a low-cost model with `medium` reasoning.
- `implementation`: code and test changes; use a coding-focused model with `medium` reasoning.
- `prReview`: defect-focused PR review; use a stronger model with `high` reasoning.
- `postMergeDeploy` and `deployToQa`: mechanical promotion checks; use a low-cost model with `medium` reasoning.
- `e2eQa`: QA validation and evidence; use a mid-tier model with `medium` reasoning.
- `deployToProd`, `rollbackProd`, and `hotfixProd`: production-impacting work; use stronger models with `high` reasoning.
- `fileQaBug`: QA defect filing and handoff; use a mid-tier model with `medium` reasoning.

If a role is missing from local config, use the example default for that role and report the fallback. If a configured model is unavailable in the current Codex runtime, omit the model override, keep the configured reasoning effort when possible, and report the fallback without blocking the ticket.

## Runtime State

Use ignored `.codex/parallel-delivery.local.json` in the coordinator checkout as the parallel delivery index. Never commit it.

Track:

- max active tickets and deployment lane policy
- model and reasoning policy used for spawned role agents
- active ticket key, branch, worktree path, current stage, PR number, artifact commit, RC/final versions when known
- deployment lane owner ticket and stage when `deploymentLanePolicy` is `serialized`
- stale or blocked ticket entries that need user or system cleanup

Each ticket worktree must have its own ignored `.codex/delivery-context.local.json`. Child role skills must be invoked from that assigned worktree only.

## Workflow

### 1. Inspect Current State

1. Read `.codex/parallel-delivery.local.json` when present.
2. Run `git worktree list` and compare active worktrees with the runtime state.
3. Inspect Plane/Gitea/Nexus/QA state only as needed to route each ticket.
4. If the runtime state references a missing worktree or a worktree branch no longer matches the ticket, report the stale entry and do not route that ticket until it is repaired.

### 2. Select Or Reuse Tickets

1. If the user named tickets, resolve those tickets.
2. If no ticket is specified, list Plane Todo tickets and ask the user to choose before mutating.
3. Enforce `parallelDelivery.maxActiveTickets`. If starting a new ticket would exceed the limit, report active tickets and stop.
4. Reuse existing ticket worktrees when the ticket key, branch, and local lock agree.

### 3. Prepare Worktrees

1. Start from configured `git.baseBranch` in the coordinator checkout and require a clean worktree before creating new worktrees.
2. Create one worktree per ticket under `parallelDelivery.worktreeRoot`.
3. Use the same branch naming rules as `plane-start-ticket`; one active implementation branch belongs to exactly one ticket worktree.
4. Copy required ignored local config files into the ticket worktree:
   - `.codex/client-tools.local.json`
   - `.codex/quality.local.json`
   - other ignored local delivery config only when a child skill requires it
5. Do not copy `.codex/parallel-delivery.local.json` into ticket worktrees.
6. Create or update that worktree's `.codex/delivery-context.local.json` only after the ticket, branch, and OpenSpec decision are known.

### 4. Route Role Agents

Route each ticket by current durable checkpoint:

- Todo with no branch: use `plane-start-ticket` in that ticket worktree.
- In Progress with branch/OpenSpec and no PR: use `implement-ticket` in that ticket worktree.
- Open PR: use `implement-ticket` for the review/fix loop or `gitea-pr-review-agent` for a focused review.
- Merged PR awaiting artifact/QA: use `post-merge-deploy` only when the serialized deployment lane is free or already owned by that ticket.
- Ticket in QA: use `test-e2e` only when the serialized deployment lane is free or already owned by that ticket.
- Ticket Done and user explicitly requested PROD: use `deploy-to-prod` only when the serialized deployment lane is free or already owned by that ticket.
- Ambiguous state: use `pipeline-status`.

When spawning a role agent, select the matching `agentModelPolicy` entry:

- `pipeline-status` -> `pipelineStatus`
- `plane-start-ticket` -> `ticketStarter`
- `implement-ticket` -> `implementation`
- `gitea-pr-review-agent` -> `prReview`
- `post-merge-deploy` -> `postMergeDeploy`
- `deploy-to-qa` -> `deployToQa`
- `test-e2e` -> `e2eQa`
- `deploy-to-prod` -> `deployToProd`
- `file-qa-bug` -> `fileQaBug`
- `rollback-prod` -> `rollbackProd`
- `hotfix-prod` -> `hotfixProd`

### 5. Deployment Lane

With `deploymentLanePolicy` set to `serialized`, only one ticket may own the shared DEV/QA/PROD lane at a time.

- Acquire the lane before invoking `post-merge-deploy`, `deploy-to-qa`, `test-e2e`, or `deploy-to-prod`.
- Preserve the lane owner while the ticket is in deployment, QA, or explicit PROD promotion.
- Release the lane after the stage reaches a stable checkpoint: QA evidence recorded, PROD deployment recorded, rollback/hotfix handoff recorded, or a blocker is reported.
- If another ticket owns the lane, continue implementation/review work for other tickets when possible and report the lane owner for blocked promotion work.

## Failure Rules

- Missing or disabled `parallelDelivery.enabled`: report that parallel delivery is not enabled and show the placeholder-safe config keys to set.
- Missing `worktreeRoot`: use `../ticket-worktrees` and report the default.
- Dirty coordinator checkout before creating a new worktree: stop before Git or Plane mutation.
- Existing worktree mapped to a different ticket or branch: stop and report the conflict.
- Existing `.codex/delivery-context.local.json` in a ticket worktree points to another ticket: stop before routing.
- Serialized deployment lane owned by another ticket: do not promote, deploy, tag, move QA/Done state, or write release evidence for the blocked ticket.
- Missing child-skill config: preserve the child skill blocker and do not route around it.

## Output

Summarize:

- active ticket count and configured maximum
- ticket-to-worktree mapping
- role skill routed for each ticket or blocker found
- deployment lane owner when present
- next action for blocked tickets
