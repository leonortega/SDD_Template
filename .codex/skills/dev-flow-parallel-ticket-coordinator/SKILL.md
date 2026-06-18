---
name: dev-flow-parallel-ticket-coordinator
description: Coordinate multiple configured tickets through role-specialized delivery agents by assigning one repository worktree and one local ticket lock per active ticket while serializing shared deployment lanes through selected project-profile adapters.
---

# Parallel Ticket Coordinator

## Overview

Use this skill when the user asks to process more than one Plane ticket at the same time, run parallel ticket delivery, create parallel role agents, or coordinate concurrent Plane work.

This skill orchestrates existing role skills. It does not duplicate child workflows and does not implement ticket-specific code itself.

The coordinator owns preflight, routing, runtime-state synthesis, deployment lane ownership, and all cross-ticket decisions. It must synthesize child-agent results before reporting handoff, and it must preserve one Git worktree per active ticket.

## Shared Context

Before routing, follow `.codex/skills/_shared/skill-startup.md`, which reads `.codex/project-profile.json`, `.codex/skills/_shared/provider-adapter-contract.md`, `.codex/skills/_shared/delivery-contract.md`, and `docs/context-management.md`, with `docs/architecture.md` as the stage-specific doc. Load selected ticket, repository, artifact, deployment, and QA adapters for lane decisions.

## Configuration

Read `.codex/client-tools.local.json` first. Fall back to `.codex/client-tools.example.json` only for structure and safe defaults. Required/defaulted values:

- `parallelDelivery.enabled`, default `false`
- `parallelDelivery.maxActiveTickets`, default `2`
- `parallelDelivery.worktreeRoot`, default `../ticket-worktrees`
- `parallelDelivery.deploymentLanePolicy`, default `serialized`
- `parallelDelivery.agentModelPolicy`, default to the placeholder-safe role policy in `.codex/client-tools.example.json`
- `git.baseBranch`, default `dev`
- Plane, Gitea, Nexus, PR label, and quality config used by delegated child skills

When copying ignored local config into a ticket worktree, report only filenames copied, never values. The default allowlist is `.codex/client-tools.local.json`, `.codex/quality.local.json`, and `.codex/tool-recommendations.local.json` when present. Do not copy `.codex/parallel-delivery.local.json`, `.codex/delivery-context.local.json`, `.codex/azure-login.local.json`, or app `*.local.json` files by default.

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

## Role Contracts

- `coordinator`: owns preflight, routing, runtime-state synthesis, lane ownership, and cross-ticket decisions.
- `ticketStarter`: prepares ticket branch, worktree, Plane/OpenSpec setup, and ticket lock only.
- `implementation`: edits and tests one assigned ticket worktree only.
- `prReview`: performs focused review, labels, and comments without taking unrelated implementation work.
- `deployment`: handles post-merge DEV/QA promotion only when the serialized deployment lane is free or owned by the ticket.
- `qa`: validates QA and records evidence only with lane ownership.
- `prodHotfix`: handles PROD, rollback, and hotfix only after explicit user intent and lane validation.

Every child agent must return concise status, files touched, validation run, blockers, and next action.

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
5. Classify each ticket's delivery risk when enough ticket, OpenSpec, PR, or artifact evidence exists. Include the risk level in the planned state and child role prompt.
6. Check installed-skill runtime index status. Use it only to pass exact `SKILL.md` paths to child agents; if missing or stale, report regeneration as setup work instead of rescanning inside every child agent.
7. Before any Git, Plane, or Gitea mutation for new or reused parallel work, run `.codex/skills/_shared/scripts/delivery_tools.ps1 -Mode ValidateParallelDeliveryDryRun` with the planned state. The operator-facing checklist question is: `Can I safely start these 2 tickets in parallel?`

### 2. Select Or Reuse Tickets

1. If the user named tickets, resolve those tickets.
2. If no ticket is specified, list Plane Todo tickets and ask the user to choose before mutating.
3. Enforce `parallelDelivery.maxActiveTickets`. If starting a new ticket would exceed the limit, report active tickets and stop.
4. Reuse existing ticket worktrees when the ticket key, branch, and local lock agree.

### 3. Prepare Worktrees

1. Start from configured `git.baseBranch` in the coordinator checkout and require a clean worktree before creating new worktrees.
2. Create one worktree per ticket under `parallelDelivery.worktreeRoot`.
3. Use the same branch naming rules as `dev-flow-start-ticket`; one active implementation branch belongs to exactly one ticket worktree.
4. Copy required ignored local config files into the ticket worktree:
   - `.codex/client-tools.local.json`
   - `.codex/quality.local.json`
   - `.codex/tool-recommendations.local.json` when present
   - other ignored local delivery config only when a child skill requires it
5. Do not copy `.codex/parallel-delivery.local.json` into ticket worktrees.
6. Do not copy `.codex/delivery-context.local.json`; create or update that worktree's ticket lock only after the ticket, branch, and OpenSpec decision are known.
7. Use `configure-dev-environment` mode `SyncWorktreeLocalConfig` to repair a new or reused ticket worktree before routing child skills when allowlisted local config is missing.
8. Use `configure-dev-environment` mode `EnsureDeliveryContext` to repair a missing ticket lock only after the worktree's ticket key, branch, OpenSpec change, and PR number are known.

### 4. Route Role Agents

Route each ticket by current durable checkpoint:

- Todo with no branch: use `dev-flow-start-ticket` in that ticket worktree.
- In Progress with branch/OpenSpec and no PR: use `dev-flow-implement-ticket` in that ticket worktree.
- Open PR: use `dev-flow-implement-ticket` for the review/fix loop or `dev-flow-pr-review-agent` for a focused review.
- Merged PR awaiting artifact/QA: use `dev-ops-post-merge-deploy` only when the serialized deployment lane is free or already owned by that ticket.
- Ticket in QA: use `quality-test-e2e` only when the serialized deployment lane is free or already owned by that ticket.
- Ticket Done and user explicitly requested PROD: use `dev-ops-deploy-prod` only when the serialized deployment lane is free or already owned by that ticket.
- Ambiguous state: use `dev-flow-pipeline-status`.

When spawning a role agent, select the matching `agentModelPolicy` entry:

- `dev-flow-pipeline-status` -> `pipelineStatus`
- `dev-flow-start-ticket` -> `ticketStarter`
- `dev-flow-implement-ticket` -> `implementation`
- `dev-flow-pr-review-agent` -> `prReview`
- `dev-ops-post-merge-deploy` -> `postMergeDeploy`
- `dev-ops-deploy-qa` -> `deployToQa`
- `quality-test-e2e` -> `e2eQa`
- `dev-ops-deploy-prod` -> `deployToProd`
- `dev-flow-file-qa-bug` -> `fileQaBug`
- `dev-ops-rollback-prod` -> `rollbackProd`
- `dev-ops-hotfix-prod` -> `hotfixProd`

### 5. Deployment Lane

With `deploymentLanePolicy` set to `serialized`, only one ticket may own the shared DEV/QA/PROD lane at a time.

- Acquire the lane before invoking `dev-ops-post-merge-deploy`, `dev-ops-deploy-qa`, `quality-test-e2e`, or `dev-ops-deploy-prod`.
- Preserve the lane owner while the ticket is in deployment, QA, or explicit PROD promotion.
- Release the lane after the stage reaches a stable checkpoint: QA evidence recorded, PROD deployment recorded, rollback/hotfix handoff recorded, or a blocker is reported.
- If another ticket owns the lane, continue implementation/review work for other tickets when possible and report the lane owner for blocked promotion work.

## Failure Rules

- Missing or disabled `parallelDelivery.enabled`: report that parallel delivery is not enabled and show the placeholder-safe config keys to set.
- Missing `worktreeRoot`: use `../ticket-worktrees` and report the default.
- Failed `ValidateParallelDeliveryDryRun`: stop before Git, Plane, or Gitea mutation and report duplicate tickets, duplicate branches, duplicate worktrees, missing worktree paths, deployment lane conflicts, unsupported lane policy, disabled parallel delivery, or missing required ignored local runtime files.
- Dirty coordinator checkout before creating a new worktree: stop before Git or Plane mutation.
- Existing worktree mapped to a different ticket or branch: stop and report the conflict.
- Existing `.codex/delivery-context.local.json` in a ticket worktree points to another ticket: stop before routing.
- Serialized deployment lane owned by another ticket: do not promote, deploy, tag, move QA/Done state, or write release evidence for the blocked ticket.
- Missing child-skill config: preserve the child skill blocker and do not route around it.

## Cleanup And Recovery

- Stale runtime state: compare `.codex/parallel-delivery.local.json` with `git worktree list`, Plane, Gitea, and branch state; do not route stale entries until repaired.
- Missing worktree: report the ticket and branch, then recreate only after durable checkpoints confirm the same ticket/branch mapping.
- Blocked ticket: keep the ticket entry, record the blocker, and route other independent tickets if max active tickets and lane ownership allow it.
- Lane-owner conflict: preserve the owner until QA evidence, PROD evidence, rollback/hotfix handoff, or a clear blocker releases the lane.
- Completed ticket: after QA evidence is recorded and the Plane ticket is moved to Done, run teardown from the coordinator checkout only:
  1. Verify `git -C <worktreePath> status --porcelain` is empty.
  2. Verify the worktree branch is merged into configured `git.baseBranch`, for example `git merge-base --is-ancestor <branch> <baseBranch>`.
  3. Verify no deployment lane owner still references the ticket.
  4. Run `git worktree remove <worktreePath>` and `git worktree prune`.
  5. Remove the ticket from `.codex/parallel-delivery.local.json`.
- Child role agents must not delete their own assigned worktree.

## Output

Summarize:

- active ticket count and configured maximum
- ticket-to-worktree mapping
- role skill routed for each ticket or blocker found
- delivery risk and installed-skill index status for each routed ticket
- deployment lane owner when present
- next action for blocked tickets
