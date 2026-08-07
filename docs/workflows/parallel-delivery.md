# Parallel Delivery

Parallel delivery coordinates more than one OpenProject work package at the same time. The AI applies it automatically
when the user asks to implement more than one ticket — there is no `parallelDelivery.enabled` flag gate; single-ticket
requests keep the linear flow. Prefer parallel delivery only when the tickets can make progress independently and the
operator can supervise the coordinator's synthesis.

## When To Use Parallel Agents

Use parallel agents when work can be split without shared mutable state:

- independent OpenProject work packages with separate branches and separate Git worktrees
- research-heavy investigations where each agent returns a compact summary
- repeated pattern updates across unrelated files or modules
- fresh PR review, QA evidence review, or security/performance review from an isolated context
- verbose checks where only the failures and summary should return to the coordinator

Do not use parallel agents for quick targeted edits, tightly coupled implementation, tasks that need frequent
back-and-forth, or work where multiple phases must share one evolving context.

## Required Isolation

Parallel delivery uses only Git worktrees. Each active ticket has exactly one worktree under
`parallelDelivery.worktreeRoot`, one implementation branch, and one ignored `.codex/delivery-context.local.json` inside
that worktree.

The coordinator checkout owns ignored `.codex/parallel-delivery.local.json`. Do not copy that file into ticket
worktrees. Copy ignored local config such as `.codex/client-tools.local.json`, `.codex/project-profile.local.json`, and
`.codex/quality.local.json` only when a child skill requires it, and report only filenames.

The default worktree-local config allowlist is `.codex/client-tools.local.json`, `.codex/project-profile.local.json`,
and `.codex/quality.local.json` when present. Do not copy `.codex/delivery-context.local.json`,
`.codex/parallel-delivery.local.json`, or app `*.local.json` files by default. Use `configure-dev-environment` mode
`SyncWorktreeLocalConfig` to repair new or reused ticket worktrees before routing child skills. Use
`EnsureDeliveryContext` to repair a missing ticket lock only after the worktree's ticket key, branch, OpenSpec change,
and PR number are known.

Default configuration:

- No `parallelDelivery.enabled` gate — the AI decides by ticket count (1 ticket → linear flow; >1 → parallel).
- `parallelDelivery.maxActiveTickets=2`
- `parallelDelivery.worktreeRoot=../ticket-worktrees`
- `parallelDelivery.deploymentLanePolicy=serialized`

## Multi-Ticket Refinement

Each Todo ticket started in parallel runs its own refinement inside its worktree through
`dev-flow-start-ticket`, and every ticket follows the same always-ask gate as the linear
flow: at least 1 `grill-with-docs` cycle (at most 4), and the user is **always asked for
extra info for that ticket** — even when the ticket seems complete — before that ticket's
curated IA block is written. The coordinator must not let any ticketStarter agent write an
IA block without the user having been asked for that ticket, and must not batch-answer or
silently self-answer across tickets.

## Dry-Run Checklist

Before Git, OpenProject, or Gitea mutation, answer: `Can I safely start these 2 tickets in parallel?`

Run `ValidateParallelDeliveryDryRun` with the planned ticket/worktree state. The input should include `enabled`,
`maxActiveTickets`, `deploymentLanePolicy`, `requiredLocalConfigFiles`, and planned `tickets`.

The dry run must pass before routing child agents. It must report:

- too many active tickets
- duplicate ticket keys
- duplicate branches
- duplicate worktree paths
- missing worktree paths
- unsupported deployment lane policy
- deployment lane owner that is not an active ticket
- missing or non-ignored local runtime files required by child worktrees

`configure-dev-environment -Mode Audit` also reports recorded ticket worktrees that are missing required local runtime
config so operators can run `SyncWorktreeLocalConfig` before child agents lose OpenProject, Gitea, Nexus, PR reviewer,
or quality settings.

## Role Contracts

- `coordinator`: owns preflight, routing, runtime-state synthesis, lane ownership, and cross-ticket decisions.
- `ticketStarter`: prepares ticket branch, worktree, OpenProject/OpenSpec setup, and ticket lock only.
- `implementation`: edits and tests one assigned ticket worktree only.
- `prReview`: performs focused review, labels, and comments without taking unrelated implementation work.
- `deployment`: runs post-merge DEV/QA promotion only when the serialized deployment lane is free or owned by the
ticket.
- `qa`: validates QA and records evidence only with lane ownership.
- `prodHotfix`: handles PROD, rollback, and hotfix only after explicit user intent and lane validation.

Every child agent must return concise status, files touched, validation run, blockers, and next action. A
`ticketStarter` starting a Todo ticket via `dev-flow-start-ticket` must also report whether refinement asked the
user (`refinementUserAsked: yes/no`), so the coordinator can verify the always-ask gate before routing the ticket
forward.

## Deployment Lane Serialization

Implementation and review may run concurrently across isolated worktrees. DEV, QA, E2E QA, PROD, rollback, and hotfix
promotion are serialized because they share the selected deployment provider environments, Nexus release manifests,
release tags, and OpenProject deployment evidence.

If another ticket owns the deployment lane, continue implementation or review work for other tickets when safe. Do not
deploy, test, tag, move QA/Done state, or write deployment evidence for a ticket that does not own the lane.

## Cleanup And Recovery

Use cleanup and recovery when runtime state and durable state disagree:

- stale runtime state: compare `.codex/parallel-delivery.local.json` with `git worktree list`, OpenProject, Gitea, and
branch state; do not route stale entries until repaired
- missing worktree: report the ticket and branch, then recreate only after durable checkpoints confirm the same
ticket/branch mapping
- blocked ticket: keep the ticket entry, record the blocker, and route other independent tickets if max active tickets
and lane ownership allow it
- lane-owner conflict: preserve the current owner until QA evidence, PROD evidence, rollback/hotfix handoff, or a clear
blocker releases the lane
- completed ticket: after QA evidence is recorded and the OpenProject work package is moved to Done, the coordinator
checkout should verify the ticket worktree is clean, verify its branch is merged into the configured base branch, run
`git worktree remove <worktreePath>` followed by `git worktree prune`, and then remove the ticket from the local runtime
index

Never clear a ticket lock, lane owner, or worktree mapping silently. If durable checkpoints conflict, stop and ask for
explicit operator confirmation.
