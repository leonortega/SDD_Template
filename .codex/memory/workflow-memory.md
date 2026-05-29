# Workflow Memory

## Default Delivery Flow

- Type: Fact
- Status: Active
- Source: `README.md`, `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-05-29

```text
Plane Todo
  -> branch + OpenSpec proposal
  -> implementation + tests
  -> Gitea PR
  -> PR validation + Codex review agent
  -> merge to dev
  -> Nexus package + Azure DEV + Azure QA
  -> E2E QA evidence
  -> Plane Done
  -> explicit PROD promotion to main/PROD
  -> rollback or hotfix when needed
```

## Default Plane States

- Type: Fact
- Status: Active
- Source: `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-05-29

- `Todo`: work is not started.
- `In Progress`: branch and implementation are active.
- `In Review`: PR exists and awaits review or merge.
- `QA`: artifact is deployed to QA and awaits E2E validation.
- `Done`: E2E QA passed and artifact is eligible for explicit PROD promotion.

## Ticket Key Pattern

- Type: Fact
- Status: Active
- Source: `.codex/delivery-policy.json`
- Last verified: 2026-05-29

Ticket keys must match:

```text
E2EPROJECT-[0-9]+
```

Push-triggered environment deployment is allowed only for ticket-named work. Maintenance, `[SDD]`, and `openspec/...` commits do not deploy environments.

## Stable Markers

- Type: Fact
- Status: Active
- Source: `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-05-29

Use these markers for idempotency:

- `IA generated branch: {branchName}`
- `IA generated QA deployment: {commitSha}`
- `IA generated E2E QA: {ticketKey}`
- `IA generated QA bug: {parentTicketKey}`
- `IA generated PROD deployment: {finalVersion}`
- `IA generated PROD rollback: {rollbackVersionOrCommit}`
- `IA generated PROD rollback incident: {rollbackVersionOrCommit}`
- `IA generated PROD hotfix: {incidentOrTicketKey}`
- `<!-- codex-review-agent:{headSha} -->`
- `<!-- ia-generated:start -->` through `<!-- ia-generated:end -->`

## Ticket Context Lock

- Type: Fact
- Status: Active
- Source: `.codex/skills/_shared/delivery-contract.md`, `docs/architecture.md`
- Last verified: 2026-05-29

Normal automatic delivery stays locked to one Plane ticket through ignored `.codex/delivery-context.local.json`. Parallel delivery uses one worktree and one local ticket lock per active ticket. Child skills must verify ticket, branch, PR, artifact commit, QA evidence, RC tag, and PROD lineage match the lock before mutation.

## Parallel Delivery

- Type: Fact
- Status: Active
- Source: `.codex/skills/_shared/delivery-contract.md`, `docs/architecture.md`
- Last verified: 2026-05-29

Implementation and review can run concurrently across isolated worktrees. DEV, QA, E2E QA, PROD, rollback, and hotfix promotion are serialized because they share Azure environments, Nexus release manifests, RC/final tags, and Plane deployment evidence.

## Context Findings Review

- Type: Fact
- Status: Active
- Source: `docs/context-management.md`, `docs/development.md`, `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-05-29

Every implementation must finish with a Context Findings Review and memory update review. Durable authoritative findings update the matching `docs/` file in the same PR. Reusable non-authoritative findings update `.codex/memory/`. If no durable findings exist, the PR body and Plane handoff comment must state `Docs: no durable context changes` and `Memory updated: none`.

## Delivery Skill Startup

- Type: Fact
- Status: Active
- Source: `.codex/skills/_shared/skill-startup.md`
- Last verified: 2026-05-29

Non-OpenSpec, non-configure delivery skills share a startup sequence through `.codex/skills/_shared/skill-startup.md`. Skills should read memory for recall, then the shared delivery contract and stage-specific docs. Memory updates are allowed only through `.codex/memory/retrieval-policy.md#update-process`.
