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
  -> Nexus artifact set + selected provider DEV + selected provider QA
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
- Source: `.codex/project-profile.json`
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
- Last verified: 2026-06-09

Normal automatic delivery stays locked to one Plane ticket through ignored `.codex/delivery-context.local.json`. Keep the lock after QA Done because explicit PROD promotion may still need artifact and RC context. `dev-flow-start-ticket` may lazily replace the lock when starting another ticket only after the locked ticket is verified in the configured Done state. Parallel delivery uses one worktree and one local ticket lock per active ticket. Child skills must verify ticket, branch, PR, artifact commit, QA evidence, RC tag, and PROD lineage match the lock before mutation.

## Parallel Delivery

- Type: Fact
- Status: Active
- Source: `.codex/skills/_shared/delivery-contract.md`, `docs/architecture.md`
- Last verified: 2026-05-29

Implementation and review can run concurrently across isolated worktrees. DEV, QA, E2E QA, PROD, rollback, and hotfix promotion are serialized because they share selected provider environments, Nexus release manifests, RC/final tags, and Plane deployment evidence.

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

## Durable Learning Capture Gate

- Type: Decision
- Status: Active
- Source: `AGENTS.md`, `.codex/skills/_shared/skill-startup.md`, `.codex/skills/_shared/delivery-contract.md`, current conversation
- Last verified: 2026-06-02

Before final handoff for any non-trivial repository work, agents must classify whether an error, issue, blocker, fix, configuration repair, local tooling correction, or debugging result is reusable. The result must be reported as `Memory updated: <files>` or `Memory updated: none`. Plane comments, PR comments, QA evidence, logs, and chat summaries do not replace durable learning capture.

Agent-caused or tool-discovered failures are memory candidates by default. If a command fails, a hook rejects the agent's action, a required local tool is missing, or the agent repeats a workflow mistake, search memory with the concrete symptom and persist a small update unless the issue is already covered or clearly one-off. Do not use `Memory updated: none` for a newly diagnosed repeatable agent/tooling failure.

## Symptom-Driven Memory Search

- Type: Pattern
- Status: Active
- Source: `.codex/memory/search_memory.ps1`, `.codex/memory/retrieval-policy.md`, current conversation
- Last verified: 2026-06-02

Use `.codex/memory/search_memory.ps1 -Query <symptom>` during debugging and preflight when a task mentions or reveals an error, blocker, failed command, deployment issue, PR feedback, QA failure, configuration mismatch, or local tooling problem. Search concrete terms such as config keys, command names, marker names, workflow stages, and error fragments, then verify the memory lead against current files and live state.

## Plane Generated Comments Require Plane Payload Fields

- Type: Pattern
- Status: Active
- Source: `.codex/skills/_shared/api-helpers.md`, `.codex/skills/_shared/delivery-contract.md`, current conversation
- Last verified: 2026-06-02

Generated Plane comments must send both `comment_html` and `comment_stripped`; Gitea-style fields such as `comment` or `body` can produce blank rendered comments. After posting or patching a generated marker, read the comment back and verify `comment_stripped` starts with the marker before reporting the comment as added.

## Plane Descriptions Strip Raw Html Comments

- Type: Pattern
- Status: Active
- Source: E2EPROJECT-4 ticket start, Plane work-item description PATCH/readback
- Last verified: 2026-06-08

Plane work-item descriptions can strip raw HTML comments such as `<!-- ia-generated:start -->` from `description_html` during sanitization. When writing the managed generated block through Plane API, read the description back and verify marker persistence; escaped marker text such as `&lt;!-- ia-generated:start --&gt;` remains detectable in `description_html` and `description_stripped`.

## Repo-Owned Skills Carry Local Delivery Behavior

- Type: Decision
- Status: Active
- Source: Codex thread `019e83a6-433d-7fa2-8ff0-852d74d2eb21`, `.codex/skills/dev-flow-pr-review-feedback-loop/SKILL.md`
- Last verified: 2026-06-02

Repo-specific delivery behavior should live in repo-owned skills. The reconnectable PR feedback loop for AI findings and late human PR comments belongs in `dev-flow-pr-review-feedback-loop`, with `dev-flow-implement-ticket` and `dev-flow-continue-implementation` delegating to it. OpenSpec-derived dev-flow skills may carry local ticket, validation, and handoff context when they are tracked in this repository.

## PR Feedback Batches Are Reconnectable Work

- Type: Pattern
- Status: Active
- Source: Codex thread `019e83a6-433d-7fa2-8ff0-852d74d2eb21`, `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-06-02

AI review findings and later human PR comments must be converted into OpenSpec `## PR Review Feedback` tasks, Plane detection/fix comments, code/test/doc fixes, validation, commits, pushes, and an AI review rerun before handoff. Feedback batches should use deterministic ids from source comment/review ids so late comments on the same head SHA are not skipped by an earlier batch marker.

## Compatibility Alias Skills Should Stay Thin

- Type: Pattern
- Status: Active
- Source: Codex thread `019e83fb-7f1d-7f42-a1fa-b57bc4541947`, `configure-infra-tools` cleanup
- Last verified: 2026-06-02

Compatibility alias skills should route immediately to the current authoritative skill instead of duplicating setup choices or workflow rules. Duplicated alias content creates policy drift when the active router changes.

## Guidance Catalog Is Local State, Not Stack Source Of Truth

- Type: Pattern
- Status: Active
- Source: Codex thread `019e83fb-7f1d-7f42-a1fa-b57bc4541947`, project-guidance cleanup
- Last verified: 2026-06-02

Tracked tool recommendation examples are templates, not the active project stack source of truth. Durable stack context belongs in docs and OpenSpec config; ignored `.codex/tool-recommendations.local.json` preserves learned guidance/catalog state such as accepted/dismissed guidance and `usedInSteps`. Acquisition refreshes should preserve that local state instead of resetting it.

## Gitea Merge Commit Resolution After API Merge

- Type: Pattern
- Status: Active
- Source: Gitea PR 23 merge response and `origin/dev` fetch during `E2EPROJECT-4` post-merge deployment
- Last verified: 2026-06-08

After a successful Gitea PR merge API call, the PR response may report `merged=true` while `merged_commit_id` and `merged_commit_sha` are still null. For post-merge deployment, verify the target branch and resolve the artifact commit from the updated target ref such as `origin/dev`, then validate the ticket lock and Nexus `commit.sha` against that resolved commit.
