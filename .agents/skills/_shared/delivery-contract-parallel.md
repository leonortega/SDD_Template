<!-- TIER 3: STAGE-SPECIFIC - Parallel delivery (multi-ticket coordination) -->

# Delivery Contract — Parallel (multi-ticket coordination)

Stage-specific rules for parallel delivery, worktree management, and serialized deployment lanes. Read in addition to
`delivery-contract-core.md` and `delivery-contract-ticket.md`.

---

## Parallel Delivery

Parallel delivery uses role-specialized agents and Git worktrees to let multiple tickets progress through planning,
implementation, PR validation, and review at the same time. The default local
runtime state file is ignored `.template/parallel-delivery.local.json`; never commit it or print secret-derived values
copied into a worktree.

**Trigger.** The AI applies parallel delivery when the user asks to implement more than one ticket. There is no
`parallelDelivery.enabled` flag gate — ticket count is the decision; single-ticket requests stay on the linear flow.

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

- `parallelDelivery.maxActiveTickets` limits active ticket worktrees. If the limit is reached, report the active tickets
and do not start another one.
- `parallelDelivery.worktreeRoot` is the only supported isolation model. Fresh clones and shared-checkout parallelism
are unsupported.
- `parallelDelivery.agentModelPolicy` maps each delivery role to a model and reasoning effort. `model: inherit` means
omit the model override.
- For non-parallel workflows, use `.template/client-tools.local.json.openRouter.defaultChatModel` with optional per-skill
model mapping overrides.
- Each active ticket owns exactly one worktree and one implementation branch.
- Copy ignored local config needed by child skills into each worktree without printing tokens, passwords, cookies, or
credential-bearing URLs. The default allowlist is
`.template/client-tools.local.json`, `.template/project-profile.local.json`, `.template/quality.local.json`, and
`.template/tool-recommendations.local.json` when present.
- Before Git, OpenProject, or Gitea mutation for new or reused parallel work, run `python -m tools.sdd_cli dev-flow
validate-parallel-dry-run` with planned tickets, lane state, enabled state, and
required local runtime files.
- With `deploymentLanePolicy` set to `serialized`, only the recorded lane owner may run post-merge deploy, QA deploy, QA
gate, or PROD deploy; other agents must wait or report the owner.
- PROD promotion remains explicit. Parallel delivery must not promote to PROD only because QA passed.
- Each ticket started in parallel runs its own refinement via `dev-flow-start-ticket` and follows the same always-ask
gate as the linear flow: 1 to 4 `grill-with-docs` cycles with no fixed default (~2 typical;
never cut the process short — keep grilling while questions remain),
always asking the user for extra info for
that ticket — even when the ticket seems complete — before writing its curated IA block, with no batching or silent
self-answering across tickets. The coordinator never lets a ticketStarter write an IA block without the user having
been asked for that ticket.
- After QA evidence is recorded and OpenProject is moved to Done, the coordinator checkout owns ticket worktree
teardown — and teardown runs the **MUST post-close cleanup** (authority level 5): `environment-lab
  prune-docker-leftovers` + `prune-kind-images` from the coordinator checkout. Image/volume/container/kind pruning was
  removed from CI, so every closed ticket (chained/sibling included) cleans up here; the prunes are idempotent and
  non-fatal but mandatory — never hand off a closed ticket without them.
- **Every open PR — chained/sibling included — runs the full PR review skill.** For each open PR in its ticket
  worktree, run `dev-flow-pr-review-agent` (mandatory, never optional): check the PR Validation (Gitea Actions) CI
  run for the head SHA, post AI findings, and apply the `agent-reviewed` label only on green + zero findings
  (§2.1). All label changes go through the deterministic idempotent `gitea labels` CLI (`python -m tools.sdd_cli
  gitea labels --pr <number> --add agent-reviewed --remove needs-tests,needs-changes`) — never hand-rolled REST —
  so repeated review loops on chained PRs can never duplicate a label (one canonical id per name, diffed against
  the PR's current labels). Resolve findings via `dev-flow-pr-review-feedback-loop` (fix → push → rerun AI review →
  re-check CI; label changes do NOT trigger a fresh CI run, so rerun PR Validation on the new head). After
  sibling-conflict resolution, re-run the gate on the new head before merge. Never skip the review skill for any
  open PR.

Role contracts:

- `coordinator`: owns preflight, routing, runtime-state synthesis, lane ownership, and all cross-ticket decisions.
- `ticketStarter`: prepares ticket branch, worktree, OpenProject/OpenSpec setup, and ticket lock only.
- `implementation`: edits and tests one assigned ticket worktree only.
- `prReview`: performs focused review, labels, and comments without taking unrelated implementation work.
- `deployment`: handles post-merge DEV/QA promotion only when the serialized deployment lane is free or owned by the
ticket.
- `qa`: validates QA and records evidence only with lane ownership.
- `prodHotfix`: handles PROD, rollback, and hotfix only after explicit user intent and lane validation.

Every child agent must return concise status, files touched, validation run, blockers, and next action. A
`ticketStarter` starting a Todo ticket via `dev-flow-start-ticket` must also report whether refinement asked the user
(`refinementUserAsked: yes/no`) so the coordinator can verify the always-ask gate. Never let two
agents mutate the same OpenProject work package. Never parallelize DEV, QA, E2E
QA, PROD, rollback, or hotfix promotion.
