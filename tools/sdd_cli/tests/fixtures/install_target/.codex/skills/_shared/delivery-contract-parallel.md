<!-- TIER 3: STAGE-SPECIFIC - Parallel delivery (multi-ticket coordination) -->

# Delivery Contract — Parallel (multi-ticket coordination)

Stage-specific rules for parallel delivery, worktree management, and serialized deployment lanes. Read in addition to `delivery-contract-core.md` and `delivery-contract-ticket.md`.

---

## Parallel Delivery

Parallel delivery uses role-specialized agents and Git worktrees to let multiple tickets progress through planning, implementation, PR validation, and review at the same time. The default local runtime state file is ignored `.codex/parallel-delivery.local.json`; never commit it or print secret-derived values copied into a worktree.

Baseline shape:

```json
{
  "maxActiveTickets": 2,
  "deploymentLanePolicy": "serialized",
  "agentModelPolicy": { ... },
  "deploymentLaneOwner": { "ticketKey": "...", "stage": "..." },
  "tickets": [
    { "ticketKey": "...", "branch": "...", "worktreePath": "...", "stage": "...", "prNumber": 0 }
  ]
}
```

Rules:

- `parallelDelivery.maxActiveTickets` limits active ticket worktrees. If the limit is reached, report the active tickets and do not start another one.
- `parallelDelivery.worktreeRoot` is the only supported isolation model. Fresh clones and shared-checkout parallelism are unsupported.
- `parallelDelivery.agentModelPolicy` maps each delivery role to a model and reasoning effort. `model: inherit` means omit the model override.
- For non-parallel workflows, use `.codex/client-tools.local.json.openRouter.defaultChatModel` with optional per-skill model mapping overrides.
- Each active ticket owns exactly one worktree and one implementation branch.
- Copy ignored local config needed by child skills into each worktree without printing tokens, passwords, cookies, or credential-bearing URLs. The default allowlist is `.codex/client-tools.local.json`, `.codex/project-profile.local.json`, `.codex/quality.local.json`, and `.codex/tool-recommendations.local.json` when present.
- Before Git, OpenProject, or Gitea mutation for new or reused parallel work, run `python -m tools.sdd_cli dev-flow validate-parallel-dry-run` with planned tickets, lane state, enabled state, and required local runtime files.
- With `deploymentLanePolicy` set to `serialized`, only the recorded lane owner may run post-merge deploy, QA deploy, QA gate, or PROD deploy; other agents must wait or report the owner.
- PROD promotion remains explicit. Parallel delivery must not promote to PROD only because QA passed.
- After QA evidence is recorded and OpenProject is moved to Done, the coordinator checkout owns ticket worktree teardown.

Role contracts:

- `coordinator`: owns preflight, routing, runtime-state synthesis, lane ownership, and all cross-ticket decisions.
- `ticketStarter`: prepares ticket branch, worktree, OpenProject/OpenSpec setup, and ticket lock only.
- `implementation`: edits and tests one assigned ticket worktree only.
- `prReview`: performs focused review, labels, and comments without taking unrelated implementation work.
- `deployment`: handles post-merge DEV/QA promotion only when the serialized deployment lane is free or owned by the ticket.
- `qa`: validates QA and records evidence only with lane ownership.
- `prodHotfix`: handles PROD, rollback, and hotfix only after explicit user intent and lane validation.

Every child agent must return concise status, files touched, validation run, blockers, and next action. Never let two agents mutate the same OpenProject work package. Never parallelize DEV, QA, E2E QA, PROD, rollback, or hotfix promotion.
