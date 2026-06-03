# Parallel Delivery

Parallel delivery is an optional mode for coordinating more than one Plane ticket at the same time. Single-ticket delivery remains the default. Enable parallel delivery only when the tickets can make progress independently and the operator can supervise the coordinator's synthesis.

## When To Use Parallel Agents

Use parallel agents when work can be split without shared mutable state:

- independent Plane tickets with separate branches and separate Git worktrees
- research-heavy investigations where each agent returns a compact summary
- repeated pattern updates across unrelated files or modules
- fresh PR review, QA evidence review, or security/performance review from an isolated context
- verbose checks where only the failures and summary should return to the coordinator

Do not use parallel agents for quick targeted edits, tightly coupled implementation, tasks that need frequent back-and-forth, or work where multiple phases must share one evolving context.

## Required Isolation

Parallel delivery uses only Git worktrees. Each active ticket has exactly one worktree under `parallelDelivery.worktreeRoot`, one implementation branch, and one ignored `.codex/delivery-context.local.json` inside that worktree.

The coordinator checkout owns ignored `.codex/parallel-delivery.local.json`. Do not copy that file into ticket worktrees. Copy ignored local config such as `.codex/client-tools.local.json` and `.codex/quality.local.json` only when a child skill requires it, and report only filenames.

The default worktree-local config allowlist is `.codex/client-tools.local.json`, `.codex/quality.local.json`, and `.codex/tool-recommendations.local.json` when present. Do not copy `.codex/delivery-context.local.json`, `.codex/parallel-delivery.local.json`, `.codex/azure-login.local.json`, or app `*.local.json` files by default. Use `configure-dev-environment` mode `SyncWorktreeLocalConfig` to repair new or reused ticket worktrees before routing child skills. Use `EnsureDeliveryContext` to repair a missing ticket lock only after the worktree's ticket key, branch, OpenSpec change, and PR number are known.

Default configuration:

- `parallelDelivery.enabled=false`
- `parallelDelivery.maxActiveTickets=2`
- `parallelDelivery.worktreeRoot=../ticket-worktrees`
- `parallelDelivery.deploymentLanePolicy=serialized`

## Dry-Run Checklist

Before Git, Plane, or Gitea mutation, answer: `Can I safely start these 2 tickets in parallel?`

Run `ValidateParallelDeliveryDryRun` with the planned ticket/worktree state. The input should include `enabled`, `maxActiveTickets`, `deploymentLanePolicy`, `requiredLocalConfigFiles`, and planned `tickets`.

The dry run must pass before routing child agents. It must report:

- disabled `parallelDelivery.enabled`
- too many active tickets
- duplicate ticket keys
- duplicate branches
- duplicate worktree paths
- missing worktree paths
- unsupported deployment lane policy
- deployment lane owner that is not an active ticket
- missing or non-ignored local runtime files required by child worktrees

`configure-dev-environment -Mode Audit` also reports recorded ticket worktrees that are missing required local runtime config so operators can run `SyncWorktreeLocalConfig` before child agents lose Plane, Gitea, Nexus, PR reviewer, or quality settings.

## Role Contracts

- `coordinator`: owns preflight, routing, runtime-state synthesis, lane ownership, and cross-ticket decisions.
- `ticketStarter`: prepares ticket branch, worktree, Plane/OpenSpec setup, and ticket lock only.
- `implementation`: edits and tests one assigned ticket worktree only.
- `prReview`: performs focused review, labels, and comments without taking unrelated implementation work.
- `deployment`: runs post-merge DEV/QA promotion only when the serialized deployment lane is free or owned by the ticket.
- `qa`: validates QA and records evidence only with lane ownership.
- `prodHotfix`: handles PROD, rollback, and hotfix only after explicit user intent and lane validation.

Every child agent must return concise status, files touched, validation run, blockers, and next action.

## Deployment Lane Serialization

Implementation and review may run concurrently across isolated worktrees. DEV, QA, E2E QA, PROD, rollback, and hotfix promotion are serialized because they share Azure environments, Nexus release manifests, release tags, and Plane deployment evidence.

If another ticket owns the deployment lane, continue implementation or review work for other tickets when safe. Do not deploy, test, tag, move QA/Done state, or write deployment evidence for a ticket that does not own the lane.

## Cleanup And Recovery

Use cleanup and recovery when runtime state and durable state disagree:

- stale runtime state: compare `.codex/parallel-delivery.local.json` with `git worktree list`, Plane, Gitea, and branch state; do not route stale entries until repaired
- missing worktree: report the ticket and branch, then recreate only after durable checkpoints confirm the same ticket/branch mapping
- blocked ticket: keep the ticket entry, record the blocker, and route other independent tickets if max active tickets and lane ownership allow it
- lane-owner conflict: preserve the current owner until QA evidence, PROD evidence, rollback/hotfix handoff, or a clear blocker releases the lane
- completed ticket: after QA evidence is recorded and the Plane ticket is moved to Done, the coordinator checkout should verify the ticket worktree is clean, verify its branch is merged into the configured base branch, run `git worktree remove <worktreePath>` followed by `git worktree prune`, and then remove the ticket from the local runtime index

Never clear a ticket lock, lane owner, or worktree mapping silently. If durable checkpoints conflict, stop and ask for explicit operator confirmation.
