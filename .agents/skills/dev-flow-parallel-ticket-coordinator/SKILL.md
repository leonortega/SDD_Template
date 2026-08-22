---
name: dev-flow-parallel-ticket-coordinator
description: >-
  Coordinate multiple configured tickets through role-specialized delivery agents by assigning one repository worktree
  and one local ticket lock per active ticket while serializing shared deployment lanes through selected project-profile
  adapters.
---

<!-- TIER 3: STAGE-SPECIFIC - Parallel delivery coordination skill -->

# Parallel Ticket Coordinator

## Overview

Use this skill when the AI determines the user asked to implement more than one ticket — for example "implement tickets
TICKET-001 and TICKET-002" or "process these 2 tickets". Ticket count is the decision: one ticket stays on the
linear flow (`dev-flow-start-ticket` → `dev-flow-implement-ticket`), two or more use this coordinator. There is no
`parallelDelivery.enabled` flag gate. Use the coordinator only when the tickets can make progress independently —
tightly coupled tickets stay sequential at the AI's judgment. Also use this skill when the user asks to run parallel
ticket delivery, create parallel role agents, or coordinate concurrent ticket provider work.

This skill orchestrates existing role skills. It does not duplicate child workflows and does not implement
ticket-specific code itself.

**PR flow is owned by the shared lifecycle** (`.agents/skills/_shared/pipeline-pr-lifecycle.md`) — this skill
never redefines reviewer requests, label rules, AI review steps, feedback loops, or merge gates. All PR-related
routing in this skill points to the shared lifecycle or the child skills that implement its steps.

The coordinator owns preflight, routing, runtime-state synthesis, deployment lane ownership, and all cross-ticket
decisions. It must synthesize child-agent results before reporting handoff, and it
must preserve one Git worktree per active ticket.

## Shared Context

Before routing, follow `.agents/skills/_shared/skill-startup.md`, which reads `.template/project-profile.json`,
`.agents/skills/_shared/delivery-contract.md`, and `docs/conventions/context-management.md`,
with `docs/architecture/system.md` as the stage-specific doc. Load selected ticket, repository, artifact, deployment,
and QA adapters for lane decisions.

## Configuration

Read `.template/client-tools.local.json` first. Fall back to
`.template/client-tools.example.json` only for structure and safe defaults.
Required/defaulted values:

- **No `parallelDelivery.enabled` gate** — parallel delivery applies when the AI determines the user asked to implement
  more than one ticket; the keys below configure capacity and isolation only.
- `parallelDelivery.maxActiveTickets`, default `2`
- `parallelDelivery.worktreeRoot`, default `../ticket-worktrees`
- `parallelDelivery.deploymentLanePolicy`, default `serialized`
- `parallelDelivery.agentModelPolicy`, default to the placeholder-safe role policy in `.template/client-tools.example.json`
- `git.baseBranch`, default `dev`
- ticket provider, repository/review provider, Nexus, PR label, and quality config used by delegated child skills

When copying ignored local config into a ticket worktree, report only filenames copied, never values. The default
allowlist is `.template/client-tools.local.json`, `.template/project-profile.local.json`,
`.template/quality.local.json`, and `.template/tool-recommendations.local.json` when present. Do not copy
`.template/parallel-delivery.local.json`, `.template/delivery-context.local.json`,
`.template/deployment-provider-login.local.json`, or app `*.local.json` files by default.

## Agent Model Policy

Use `parallelDelivery.agentModelPolicy` when spawning sub-agents. Each entry maps a delivery role to:

- `model`: a Codex model id, or `inherit` to omit the model override and use the parent run's model.
- `reasoningEffort`: `low`, `medium`, `high`, or `xhigh`, passed as the sub-agent reasoning effort when supported.

Default role mapping:

- `coordinator`: own this skill and final integration; use `inherit` with `medium` reasoning unless the user requests
otherwise.
- `pipelineStatus`: read-only status checks; use a low-cost model with `low` reasoning.
- `ticketStarter`: branch/worktree/ticket start; use a low-cost model with `medium` reasoning.
- `implementation`: code and test changes; use a coding-focused model with `medium` reasoning.
- `prReview`: defect-focused PR review; use a stronger model with `high` reasoning.
- `postMergeDeploy` and `deployToQa`: mechanical promotion checks; use a low-cost model with `medium` reasoning.
- `e2eQa`: QA validation and evidence; use a mid-tier model with `medium` reasoning.
- `deployToProd`, `rollbackProd`, and `hotfixProd`: production-impacting work; use stronger models with `high`
reasoning.
- `fileQaBug`: QA defect filing and handoff; use a mid-tier model with `medium` reasoning.

If a role is missing from local config, use the example default for that role and report the fallback. If a configured
model is unavailable in the current Codex runtime, omit the model override, keep
the configured reasoning effort when possible, and report the fallback without blocking the ticket.

## Role Contracts

- `coordinator`: owns preflight, routing, runtime-state synthesis, lane ownership, and cross-ticket decisions.
- `ticketStarter`: prepares ticket branch, worktree, ticket provider/OpenSpec setup, and ticket lock only.
- `implementation`: edits and tests one assigned ticket worktree only.
- `prReview`: performs focused review, labels, and comments without taking unrelated implementation work.
- `deployment`: handles post-merge DEV/QA promotion only when the serialized deployment lane is free or owned by the
ticket.
- `qa`: validates QA and records evidence only with lane ownership.
- `prodHotfix`: handles PROD, rollback, and hotfix only after explicit user intent and lane validation.

Every child agent must return concise status, files touched, validation run, blockers, and next action. A
`ticketStarter` starting a Todo ticket via `dev-flow-start-ticket` must also report whether refinement asked the user
(`refinementUserAsked: yes/no`), so the coordinator can verify the always-ask gate before routing the ticket forward.

## Runtime State

Use ignored `.template/parallel-delivery.local.json` in the coordinator checkout as the parallel delivery index. Never
commit it.

Track:

- max active tickets and deployment lane policy
- model and reasoning policy used for spawned role agents
- active ticket key, branch, worktree path, current stage, PR number, artifact commit, RC/final versions when known
- deployment lane owner ticket and stage when `deploymentLanePolicy` is `serialized`
- `pruneOwner` per scaffold kind (`service`/`job`/`db-bootstrap`) so the prune runs once, not per ticket
- stale or blocked ticket entries that need user or system cleanup

Each ticket worktree must have its own ignored `.template/delivery-context.local.json`. Child role skills must be invoked
from that assigned worktree only.

## Workflow

### 1. Inspect Current State

1. Read `.template/parallel-delivery.local.json` when present.
2. Run `git worktree list` and compare active worktrees with the runtime state.
3. Inspect ticket provider/repository/review provider/Nexus/QA state only as needed to route each ticket.
4. If the runtime state references a missing worktree or a worktree branch no longer matches the ticket, report the
stale entry and do not route that ticket until it is repaired.
5. Classify each ticket's delivery risk when enough ticket, OpenSpec, PR, or artifact evidence exists. Include the risk
level in the planned state and child role prompt.
6. Check installed-skill runtime index status. Use it only to pass exact `SKILL.md` paths to child agents; if missing or
stale, report regeneration as setup work instead of rescanning inside every
child agent.
7. Before any Git, OpenProject, or Gitea mutation for new or reused parallel work, run `python -m tools.sdd_cli dev-flow
validate-parallel-dry-run` with the planned state. The operator-facing
checklist question is: `Can I safely start these 2 tickets in parallel?`

### 2. Select Or Reuse Tickets

1. If the user named tickets, resolve those tickets.
2. If no ticket is specified, list ticket provider Todo tickets and ask the user to choose before mutating.
3. Enforce `parallelDelivery.maxActiveTickets`. If starting a new ticket would exceed the limit, report active tickets
and stop.
4. Reuse existing ticket worktrees when the ticket key, branch, and local lock agree.
5. **Per-ticket refinement always asks the user.** Each Todo ticket's refinement runs in its own worktree via
`dev-flow-start-ticket` and MUST follow the same always-ask gate as the linear flow: 1 to 4 `grill-with-docs`
cycles with no fixed default (~2 typical; never cut the process short — keep grilling while questions remain), and
the user is
ALWAYS asked for extra info for that ticket — even
when the ticket seems complete — before that ticket's curated IA block is written. The coordinator must not let any
ticketStarter agent write an IA block without the user having been asked for that ticket (no batching, no silent
self-answering across tickets).

### 3. Prepare Worktrees

1. Start from configured `git.baseBranch` in the coordinator checkout and require a clean worktree before creating new
worktrees.
2. Create one worktree per ticket under `parallelDelivery.worktreeRoot`.
3. Use the same branch naming rules as `dev-flow-start-ticket`; one active implementation branch belongs to exactly one
ticket worktree.
4. Copy required ignored local config files into the ticket worktree:
   - `.template/client-tools.local.json`
   - `.template/quality.local.json`
   - `.template/project-profile.local.json` when present
   - `.template/tool-recommendations.local.json` when present
   - other ignored local delivery config only when a child skill requires it
5. Do not copy `.template/parallel-delivery.local.json` into ticket worktrees.
6. Do not copy `.template/delivery-context.local.json`; create or update that worktree's ticket lock only after the ticket,
branch, and OpenSpec decision are known.
7. Use `configure-dev-environment` mode `SyncWorktreeLocalConfig` to repair a new or reused ticket worktree before
routing child skills when allowlisted local config is missing.
8. Use `configure-dev-environment` mode `EnsureDeliveryContext` to repair a missing ticket lock only after the
worktree's ticket key, branch, OpenSpec change, and PR number are known.

### 4. Route Role Agents

Route each ticket by current durable checkpoint:

- Todo with no branch: use `dev-flow-start-ticket` in that ticket worktree. The child agent MUST run the
  refinement always-ask gate (Section 2 step 5) before writing that ticket's curated IA block.
- In Progress with branch/OpenSpec and no PR: use `dev-flow-implement-ticket` in that ticket worktree.
- Open PR (chained or not): **⚠️ HARD GATE (authority level 5): Load and follow the PR lifecycle skill.** Load `.agents/skills/_shared/pipeline-pr-lifecycle.md` and follow every step it defines, in order. Do NOT skip, reorder, or substitute any step. Chained/sibling PRs get the same gate as the first PR.

  **Verification:** After the PR lifecycle completes, verify every step defined in `pipeline-pr-lifecycle.md` was executed. If any step was skipped, STOP and complete it before proceeding.
- Merged PR awaiting artifact/QA: use `dev-ops-post-merge-deploy` only when the serialized deployment lane is free or
already owned by that ticket.
- Ticket in QA: use `configured QA gate` only when the serialized deployment lane is free or already owned by that
ticket.
- Ticket Done and user explicitly requested PROD: use `dev-ops-deploy-prod` only when the serialized deployment lane is
free or already owned by that ticket.
- Ambiguous state: use `dev-flow-pipeline-status`.

When spawning a role agent, select the matching `agentModelPolicy` entry:

- `dev-flow-pipeline-status` -> `pipelineStatus`
- `dev-flow-start-ticket` -> `ticketStarter`
- `dev-flow-implement-ticket` -> `implementation`
- `dev-flow-pr-review-agent` -> `prReview`
- `dev-ops-post-merge-deploy` -> `postMergeDeploy`
- `dev-ops-deploy-qa` -> `deployToQa`
- `configured QA gate` -> `e2eQa`
- `dev-ops-deploy-prod` -> `deployToProd`
- `dev-flow-file-qa-bug` -> `fileQaBug`
- `dev-ops-rollback-prod` -> `rollbackProd`
- `dev-ops-hotfix-prod` -> `hotfixProd`

### 5. Deployment Lane

With `deploymentLanePolicy` set to `serialized`, only one ticket may own the shared DEV/QA/PROD lane at a time.

- Acquire the lane before invoking `dev-ops-post-merge-deploy`, `dev-ops-deploy-qa`, `configured QA gate`, or
`dev-ops-deploy-prod`.
- Preserve the lane owner while the ticket is in deployment, QA, or explicit PROD promotion.
- Release the lane after the stage reaches a stable checkpoint: QA evidence recorded, PROD deployment recorded,
rollback/hotfix handoff recorded, or a blocker is reported.
- If another ticket owns the lane, continue implementation/review work for other tickets when possible and report the
lane owner for blocked promotion work.

### 6. Scaffold Shape Prune Ownership

`dev-flow-implement-ticket` step 9.5 prunes `.template/scaffold/` shapes once an app of that kind is registered
(`environment-lab prune-scaffold`). In parallel delivery every ticket runs implementation in its own worktree — if two
tickets implement the same kind (e.g. two service-kind apps), both would delete the same shape: duplicate deletions and
PR merge conflicts. **The coordinator owns the prune, once per kind.**

1. **Assign prune ownership per kind.** Before routing implementation tickets that register apps, determine which
   ticket is the prune owner for each kind (`service`, `job`, and `db-bootstrap`): prefer the lowest `deployOrder`
   among the apps the ticket registers, then the lowest ticket key. Record `pruneOwner` per kind in
   `.template/parallel-delivery.local.json`.
2. **Owner ticket runs step 9.5 normally** — the destructive `prune-scaffold` runs in that worktree and its PR carries
   the deletion.
3. **Non-owner tickets dry-run only.** For tickets that register an app of an already-owned kind, instruct the
   `implementation` role agent to run `prune-scaffold --dry-run true` (confirm the plan, do NOT delete) and report the
   outcome — their PRs must not touch the shape files. **This coordinator instruction overrides step 9.5 for
   non-owner tickets**: the child must not run the destructive prune even though the implement-ticket skill describes it
   as the default.
4. **Coordinator safety net.** After the owner ticket's PR merges, run `prune-scaffold` from the coordinator checkout
   once as an idempotent verification: a leftover shape (e.g. a second kind registered by a later ticket) is removed;
   an already-pruned shape reports `prune.missing` and is left alone. Never run the destructive prune from more than
   one worktree.

### 7. Sibling PR Merge Conflicts

Parallel tickets branched from the same base frequently touch the same files (e.g. `app.ts` router wiring,
`index.css`, shared page components). When one PR merges first, the later PR goes red with conflicts. Resolve them in
the later ticket's worktree — never on `dev` — and verify before pushing:

1. **Merge the base into the ticket branch** (`git merge gitea/dev` or the configured base). Resolve each conflict by
   keeping BOTH sides' contributions (e.g. both routers, both CSS blocks) unless the change is genuinely superseded.
2. **Manual resolution is error-prone — verify with hooks and full suites on the merged tree.** A string/regex
   conflict resolution silently dropped a closing brace (unclosed `.quote-confirmation-note {`) that swallowed
   unrelated CSS and broke the web build; prettier/trunk caught it only because the hooks ran. After resolving:
   - run the repo's formatter/lint (`trunk check`/prettier) on the merged files,
   - run typecheck + the full test suites for every touched app (both tickets' tests now live in this tree),
   - confirm `git status` shows no conflict markers (`<<<<<<<`/`=======`/`>>>>>>>`) before staging.
3. Stage, commit with the ticket prefix, validate OpenSpec, and push. **Re-run the shared PR lifecycle
   (`.agents/skills/_shared/pipeline-pr-lifecycle.md`) steps 2–6 on the new head — mandatory, not optional.**
   This includes reviewer requests (Steps 2 + 6), AI review (Step 3), feedback loop (Step 4), and CI
   validation (Step 5). Do NOT redefine the PR flow here — the shared lifecycle is the single source of
   truth. `agent-reviewed` stays off until the new head is green with zero findings AND reviewers are verified.

## Failure Rules

- Single-ticket request routed here: when the AI determines only one ticket is to be implemented, do not start parallel
work — route the ticket through the linear flow (`dev-flow-start-ticket` → `dev-flow-implement-ticket`).
- Child ticketStarter wrote a curated IA block without asking the user for extra info for that ticket: stop, have the
child re-run the refinement always-ask gate (Section 2 step 5), and do not route the ticket forward until the user
has been asked.
- Missing `worktreeRoot`: use `../ticket-worktrees` and report the default.
- Failed `ValidateParallelDeliveryDryRun`: stop before Git, ticket provider, or repository/review provider mutation and
report duplicate tickets, duplicate branches, duplicate worktrees, missing
worktree paths, deployment lane conflicts, unsupported lane policy, disabled parallel delivery, or missing required
ignored local runtime files.
- Dirty coordinator checkout before creating a new worktree: stop before Git or ticket-provider mutation.
- Existing worktree mapped to a different ticket or branch: stop and report the conflict.
- Existing `.template/delivery-context.local.json` in a ticket worktree points to another ticket: stop before routing.
- Serialized deployment lane owned by another ticket: do not promote, deploy, tag, move QA/Done state, or write release
evidence for the blocked ticket.
- Missing child-skill config: preserve the child skill blocker and do not route around it.
- Two tickets registering the same scaffold kind with no `pruneOwner` assigned, or a non-owner ticket executing the
destructive `prune-scaffold`: stop, reconcile the owner in `.template/parallel-delivery.local.json`, and re-instruct the
child implementation agents before any merge.

## Cleanup And Recovery

- Stale runtime state: compare `.template/parallel-delivery.local.json` with `git worktree list`, ticket provider,
repository/review provider, and branch state; do not route stale entries until repaired.
- Missing worktree: report the ticket and branch, then recreate only after durable checkpoints confirm the same
ticket/branch mapping.
- Blocked ticket: keep the ticket entry, record the blocker, and route other independent tickets if max active tickets
and lane ownership allow it.
- Lane-owner conflict: preserve the owner until QA evidence, PROD evidence, rollback/hotfix handoff, or a clear blocker
releases the lane.
- Completed ticket: after QA evidence is recorded and the ticket is moved to Done, run teardown from the coordinator
checkout only:
  1. Verify `git -C <worktreePath> status --porcelain` is empty.
  2. Verify the worktree branch is merged into configured `git.baseBranch`, for example `git merge-base --is-ancestor
  <branch> <baseBranch>`.
  3. Verify no deployment lane owner still references the ticket.
  4. **Run the MUST post-close cleanup (authority level 5, never skipped)** — image/volume/container/kind pruning was
     removed from CI, so every closed ticket (chained/sibling included) cleans up here, once, from the coordinator
     checkout:

     ```bash
     python -m tools.sdd_cli environment-lab prune-docker-leftovers
     python -m tools.sdd_cli environment-lab prune-kind-images
     ```

     Both commands are idempotent and non-fatal (a failed prune is a warning), but running them is mandatory — a
     ticket is not fully closed without this step. If the prunes cannot be executed, report a blocker instead of
     silently handing off.
  5. Run `git worktree remove <worktreePath>` and `git worktree prune`.
  6. Remove the ticket from `.template/parallel-delivery.local.json`.
- Child role agents must not delete their own assigned worktree.

## Output

Summarize:

- active ticket count and configured maximum
- ticket-to-worktree mapping
- role skill routed for each ticket or blocker found
- delivery risk and installed-skill index status for each routed ticket
- deployment lane owner when present
- next action for blocked tickets
