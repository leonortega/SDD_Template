# Delivery Workflow Contract

Use this reference before running non-config delivery skills. Skill-local instructions may add stricter checks, but must not weaken this contract.

For repeated Plane, Gitea, Nexus, and Git endpoint patterns, read `.codex/skills/_shared/api-helpers.md`.

For common delivery-skill startup, memory read behavior, and memory update classification, read `.codex/skills/_shared/skill-startup.md`.

For durable context policy, read `docs/context-management.md`. The docs are the human-readable context layer; this delivery contract is the agent-enforced operational layer. If the docs and this contract conflict, the delivery contract wins for automation behavior until the docs are corrected.

## Skill Synchronization Rule

When changing any non-OpenSpec delivery skill or any `configure-*` skill, check for policy drift across related skills before finishing.

Source-of-truth order:

1. `_shared/delivery-contract.md`
2. `docs/context-management.md`, `docs/architecture.md`, `docs/development.md`, and `docs/deployment.md` for durable human-readable context
3. Non-OpenSpec delivery-flow skills: `parallel-ticket-coordinator`, `automatic-implement-ticket`, `plane-start-ticket`, `implement-ticket`, `pr-review-feedback-loop`, `gitea-pr-review-agent`, `post-merge-deploy`, `deploy-to-qa`, `test-e2e`, `deploy-to-prod`, `rollback-prod`, `file-qa-bug`, `pipeline-status`, and `hotfix-prod`
4. Configure skills and generated templates: `configure-dev-environment`, `configure-artifact-delivery`, `configure-quality-gates`, and related `configure-*` skills

If configure skills differ from delivery-flow skills, update configure docs, templates, audits, and tests to match the delivery-flow rule. Do not update OpenSpec-specific skills unless the requested change explicitly affects OpenSpec behavior.

Before finishing any change to a non-OpenSpec delivery skill, run this completion gate:

- Identify whether the skill change affects repo setup, generated files, workflow YAML, secrets, ignored local files, Plane/Gitea labels, ticket gates, artifact paths, release manifests, QA/PROD promotion, rollback, or audit/repair behavior.
- If it does, update the matching `configure-*` skill docs, references, templates, scripts, and tests in the same change.
- If it does not, state in the final response that the configure skills were checked and no configure sync was required.
- Add or update regression tests for the sync point when the behavior is enforceable from files.

## Context Findings

Implementation and retrospective work must preserve durable context discovered during delivery. Apply the Context Findings classification from `docs/context-management.md`.

Implementation PR bodies and Plane handoff comments must include `Context findings: added/updated/none`, `Docs updated: <files>` or `Docs: no durable context changes`, `Memory updated: <files>` or `Memory updated: none`, and `Assumptions recorded: <short list or none>`.

## Agent Self-Improvement Gate

Agent self-improvement is a controlled quality lane, not an automatic permission to rewrite workflow behavior.

Use `delivery-retrospective-audit` for prompts such as `Audit recent delivery workflow`, `Audit failed QA/review/CI run`, or `Run agent self-improvement audit`. The audit is read-only by default and must not mutate Plane state, deploy, promote, tag, create scheduled automations, or rewrite active ticket context unless the user explicitly requests that separate action.

Before changing any skill, workflow policy, configure template, or quality gate from retrospective evidence, at least one gate must be met:

- repeated pattern across multiple delivery runs,
- high-severity failure that could recur or affect QA, PROD, artifacts, secrets, or user-visible behavior,
- direct conflict with this delivery contract,
- missing deterministic check for an already-required workflow rule.

When a retrospective changes delivery behavior, update this contract first when the rule is cross-cutting, then synchronize affected delivery skills, configure skills, durable docs, templates, and regression tests under the Skill Synchronization Rule.

## States And Flow

Default Plane states:

- Todo: work is not started.
- In Progress: branch and implementation are active.
- In Review: PR exists and awaits review/merge.
- QA: artifact is deployed to QA and awaits E2E validation.
- Done: E2E QA passed and the artifact is eligible for explicit PROD promotion.

Delivery flow:

```text
Plane Todo -> branch/OpenSpec -> implementation -> PR review -> dev -> DEV/QA -> E2E QA -> main -> PROD -> rollback/hotfix when needed
```

Before starting the first ticket, and before any Todo ticket is moved into implementation when stack context is missing, verify that the project tool set and tech stack are defined in `docs/architecture.md`, `docs/development.md`, `docs/deployment.md`, and `openspec/config.yaml`. The `plane-start-ticket` path must run or inspect `AuditRecommendedTools` and stop before Git, Plane, or OpenSpec mutation when the audit reports `stack-context.*` drift or the stack/tooling files are missing. Route the operator to `configure-dev-environment` to define the stack context and recommendation catalog first. When project guidance coverage is missing, use `project-guidance-discover` to show suggested skills, tools, references, practices, and standards, ask for additional desired guidance, then use `project-guidance-acquire` only after the final skill-copy list is confirmed. Ignored `.codex/tool-recommendations.local.json` may preserve catalog-shaped discovery state and recommendation-level `usedInSteps` for `project-guidance-mapper`, but it must never override the active ticket, this delivery contract, validation gates, or current repo files.

PROD promotion is explicit. Do not promote to PROD only because QA passed unless the user asks for PROD promotion or a non-`[SDD]` merge to `main` triggers the PROD-only workflow.

Push-triggered environment deployment is allowed only for ticket-named work. The ticket key pattern is configured in `.codex/delivery-policy.json`. The commit message must start with the configured ticket key format, such as `E2EPROJECT-123: ...`, or be a Gitea merge commit whose PR title starts with that ticket key format. `[SDD]`, `openspec/...`, and maintenance-only commits do not deploy environments.

## Ticket Context Lock

Normal automatic delivery must stay locked to one Plane ticket. Use ignored `.codex/delivery-context.local.json` as the local ticket context lock. Never commit it.

Parallel delivery keeps the same lock shape, but scopes it to the ticket worktree. Each active ticket worktree must contain its own `.codex/delivery-context.local.json`, and role agents must run only from the worktree assigned to that ticket. Do not share one checkout, one lock file, or one active implementation branch across multiple active tickets.

Baseline shape:

```json
{
  "ticketKey": "E2EPROJECT-123",
  "branch": "feat/e2eproject-123-example",
  "openspecChange": "feat-e2eproject-123-example",
  "prNumber": 12,
  "artifactCommitSha": "abc123",
  "sourceRcVersion": "v1.2.3-rc.1",
  "finalReleaseVersion": "v1.2.3"
}
```

Rules:

- `automatic-implement-ticket` resolves or creates the lock before delegating. If no ticket is selected, it must ask or route to `pipeline-status` instead of guessing.
- `parallel-ticket-coordinator` creates or reuses one Git worktree per active ticket, records that assignment in ignored `.codex/parallel-delivery.local.json`, and delegates child skills only inside the assigned worktree.
- `plane-start-ticket` creates or updates the lock after the selected ticket, branch, and OpenSpec decision are known.
- Child skills must verify their resolved ticket, branch, PR, artifact `release.json.planeTicketKey`, QA evidence path, RC tag, and PROD release lineage match the locked `ticketKey` before mutating or promoting.
- If the lock exists and a child skill resolves a different ticket key, stop and report the mismatch. Do not deploy, test, move state, tag, or comment the other ticket.
- If the lock is stale but all durable checkpoints clearly identify one different ticket, stop and ask the user to clear or replace the lock; do not silently rewrite it.
- `pipeline-status` may read and report the lock plus mismatches. `rollback-prod` may operate by incident/release target, but must report when it differs from the active lock and require explicit user confirmation before mutation.

## Parallel Delivery

Parallel delivery uses role-specialized agents and Git worktrees to let multiple tickets progress through planning, implementation, PR validation, and review at the same time. The default local runtime state file is ignored `.codex/parallel-delivery.local.json`; never commit it or print secret-derived values copied into a worktree.

Baseline shape:

```json
{
  "maxActiveTickets": 2,
  "deploymentLanePolicy": "serialized",
  "agentModelPolicy": {
    "pipelineStatus": {
      "model": "gpt-5.4-mini",
      "reasoningEffort": "low"
    },
    "implementation": {
      "model": "gpt-5.3-codex",
      "reasoningEffort": "medium"
    },
    "deployToProd": {
      "model": "gpt-5.4",
      "reasoningEffort": "high"
    }
  },
  "deploymentLaneOwner": {
    "ticketKey": "E2EPROJECT-123",
    "stage": "deploy-to-qa"
  },
  "tickets": [
    {
      "ticketKey": "E2EPROJECT-123",
      "branch": "feat/e2eproject-123-example",
      "worktreePath": "../ticket-worktrees/e2eproject-123",
      "stage": "implement-ticket",
      "prNumber": 12
    }
  ]
}
```

Rules:

- `parallelDelivery.maxActiveTickets` limits active ticket worktrees. If the limit is reached, report the active tickets and do not start another one.
- `parallelDelivery.worktreeRoot` is the only supported isolation model for parallel implementation. Fresh clones and shared-checkout parallelism are unsupported.
- `parallelDelivery.agentModelPolicy` maps each delivery role to a model and reasoning effort. `model: inherit` means omit the model override and use the parent Codex run's model.
- Each active ticket owns exactly one worktree and one implementation branch. Reuse matching worktrees; stop if a ticket, branch, or worktree mapping conflicts with durable Plane/Gitea/Git checkpoints.
- Copy ignored local config needed by child skills into each worktree without printing tokens, passwords, cookies, or credential-bearing URLs. The default allowlist is `.codex/client-tools.local.json`, `.codex/quality.local.json`, and `.codex/tool-recommendations.local.json` when present; do not copy `.codex/parallel-delivery.local.json`, `.codex/delivery-context.local.json`, `.codex/azure-login.local.json`, or app `*.local.json` files by default. Keep tracked templates placeholder-safe.
- Before Git, Plane, or Gitea mutation for new or reused parallel work, run `ValidateParallelDeliveryDryRun` with planned tickets, lane state, enabled state, and required local runtime files. The operator-facing question is: `Can I safely start these 2 tickets in parallel?`
- Implementation and review stages may run concurrently across tickets.
- DEV, QA, E2E QA, PROD, rollback, and hotfix promotion share deployment lanes and release tags. With `deploymentLanePolicy` set to `serialized`, only the recorded lane owner may run `post-merge-deploy`, `deploy-to-qa`, `test-e2e`, or `deploy-to-prod`; other agents must wait or report the owner.
- PROD promotion remains explicit. Parallel delivery must not promote to PROD only because QA passed.

Role contracts:

- `coordinator`: owns preflight, routing, runtime-state synthesis, lane ownership, and all cross-ticket decisions.
- `ticketStarter`: prepares ticket branch, worktree, Plane/OpenSpec setup, and ticket lock only.
- `implementation`: edits and tests one assigned ticket worktree only.
- `prReview`: performs focused review, labels, and comments without taking unrelated implementation work.
- `deployment`: handles post-merge DEV/QA promotion only when the serialized deployment lane is free or owned by the ticket.
- `qa`: validates QA and records evidence only with lane ownership.
- `prodHotfix`: handles PROD, rollback, and hotfix only after explicit user intent and lane validation.

Every child agent must return concise status, files touched, validation run, blockers, and next action. Never let two agents mutate the same Plane ticket. Never parallelize DEV, QA, E2E QA, PROD, rollback, or hotfix promotion.

## Stable Markers

Use these exact markers for idempotency:

- Branch start: `IA generated branch: {branchName}`
- QA deployment: `IA generated QA deployment: {commitSha}`
- E2E QA: `IA generated E2E QA: {ticketKey}`
- QA bug: `IA generated QA bug: {parentTicketKey}`
- PROD deployment: `IA generated PROD deployment: {finalVersion}`
- PROD rollback: `IA generated PROD rollback: {rollbackVersionOrCommit}`
- PROD rollback incident: `IA generated PROD rollback incident: {rollbackVersionOrCommit}`
- PROD hotfix: `IA generated PROD hotfix: {incidentOrTicketKey}`
- PR review agent: `<!-- codex-review-agent:{headSha} -->`
- PR review feedback detected: `IA generated PR feedback detected: {headSha}:{feedbackBatchId}`
- PR review feedback fixes: `IA generated PR feedback fixes: {headSha}:{feedbackBatchId}`
- Plane generated description block: `<!-- ia-generated:start -->` through `<!-- ia-generated:end -->`

Before adding generated comments or moving states, read existing comments when the API allows it and treat matching markers as already completed.

## Plane Comment Format

Generated Plane comments must keep the stable marker as the first line by itself, followed by a blank line and a human-readable Markdown summary.

Use this structure unless a workflow-specific skill requires more detail:

1. `**Status:** PASS|FAIL|BLOCKED - one-sentence outcome`
2. `**Context:**` compact bullets for ticket, state, version, commit, PR, artifact, and workflow run.
3. `**Validation:**` grouped bullets or a small Markdown table for environment checks, test totals, and monitoring checks.
4. `**Evidence:**` durable links to Nexus manifests, evidence ZIPs, screenshots, logs, or local fallback paths.
5. `**Notes:**` only when defects, blockers, assumptions, or tooling issues matter.

Prefer Markdown links for long URLs, short commit display text such as ``8acc4d4`` with the full SHA recorded in a field when needed, and grouped sections over long flat `Label: value` lists. Keep automation-critical values present and searchable; do not hide the stable marker, commit SHA, ticket key, release version, artifact URL, or evidence URL inside prose only.

## Reusable Delivery Tools

Use `.codex/skills/_shared/scripts/delivery_tools.ps1` for deterministic delivery mechanics instead of duplicating script logic in skills:

- `ArtifactPaths`: derive Nexus artifact paths for `app/{commitSha}`.
- `CheckGitIgnored`: verify evidence or local runtime paths are ignored before writing generated files.
- `NextRcVersion`: derive the next RC version from existing Git tags.
- `ReadDeliveryPolicy`: read `.codex/delivery-policy.json` and return the configured ticket key pattern.
- `ExtractTicketKey`: extract ticket keys from ticket-prefixed commits or Gitea merge commit titles.
- `ReadCoverageThreshold`: read the configured coverage minimum with the repo default fallback.
- `ReadCoberturaLineRate`: read Cobertura coverage percent from XML without shell text parsing.
- `ValidateReleaseManifest`: validate required `release.json` fields and version formats.
- `ValidateTicketLock`: compare resolved ticket, branch, PR, artifact commit, RC, or final version against `.codex/delivery-context.local.json`.
- `ValidateDeploymentLane`: enforce serialized deployment ownership from `.codex/parallel-delivery.local.json`.
- `ValidateParallelDeliveryDryRun`: validate enabled state, planned ticket/worktree/branch uniqueness, serialized lane ownership, supported lane policy, and required ignored local runtime files without mutating Git, Plane, Gitea, Nexus, or Azure.
- `RenderPlaneComment`: render standard Markdown Plane comments for QA deployment, E2E QA, and PROD deployment.
- `UpdateReleaseManifest`: merge stage-specific fields into `release.json` while preserving existing metadata, then validate the result.

Skills remain responsible for API calls, user-facing decisions, blocker classification, and whether a mutation is allowed. The script is the reusable preflight/render/update helper.

## PR Labels And Review Severity

Default labels:

- Reviewed: `codex-reviewed`
- Missing tests: `needs-tests`
- Blocking changes: `needs-changes`

Review findings must use:

- `BLOCKER`: must be fixed before handoff/promotion.
- `WARNING`: meaningful non-blocking risk.
- `SUGGESTION`: optional improvement.

Severity describes risk and PR label behavior. In this repository, every AI review finding is still tracked as required PR review feedback before human-review handoff, including `WARNING` and `SUGGESTION`.

## PR Review Feedback

PR review has two reconnectable loops:

1. AI review runs immediately after PR creation. The PR is not ready for human review until the current head has a review-agent comment, AI findings have been converted into OpenSpec feedback tasks, all feedback tasks are complete, relevant validation has passed, and current-head `needs-tests` / `needs-changes` labels are clean.
2. Human review happens later. The automatic workflow reconnects only when the operator manually resumes the ticket, such as `automatically continue this ticket` or `continue E2EPROJECT-123`. Plane remains `In Review` while human feedback fixes are applied unless the workflow stops on an ambiguous or conflicting blocker.

Feedback batches are identified by source ids, not only by head SHA. Compute `feedbackBatchId` as a deterministic short id from the sorted source ids in the batch, such as AI finding ids, Gitea top-level comment ids, and inline review comment ids. This allows late human comments on the same `headSha` to create a new batch instead of being skipped by an earlier fix marker.

`pr-review-feedback-loop` is the repo-owned skill that applies this rule. External `openspec-*` skills must not be edited to carry this local delivery behavior.

When actionable AI or human feedback is found:

- Add or update a `## PR Review Feedback` section in the active OpenSpec `tasks.md`.
- Add one task for each feedback item. Each task must record source type, source id or link, head SHA, severity, and the requested code, test, documentation, or workflow change.
- Add a Plane ticket comment with marker `IA generated PR feedback detected: {headSha}:{feedbackBatchId}` before applying fixes. The comment must list source ids or links, classifications, and OpenSpec feedback task ids.
- Apply the requested code, test, documentation, or workflow change when it is clear and scoped to the ticket.
- Update OpenSpec specs or design artifacts when the feedback changes required behavior.
- Run the relevant quality checks for the changed files.
- Commit and push the fix to the existing PR branch.
- Mark the OpenSpec feedback tasks complete only after the code and validation are complete.
- Add a Plane ticket comment with marker `IA generated PR feedback fixes: {headSha}:{feedbackBatchId}` that lists the source ids or links addressed, the OpenSpec tasks completed, the commit pushed, validation run, and any comments skipped as non-actionable, stale, ambiguous, duplicate, generated, or conflicting.
- Rerun the AI review loop on the new head before returning to human review.

AI review findings must have stable finding ids in the PR review comment so `pr-review-feedback-loop` can convert them into deterministic feedback tasks and batch ids. Human-authored Gitea PR feedback includes top-level PR comments and inline code review comments, plus review-thread replies supported by the configured Gitea version.

Do not treat generated agent comments, duplicate comments already addressed by a newer head SHA or completed feedback batch, resolved/outdated inline comments, or purely informational comments as required code changes. Record skipped human comments in the Plane detection or fix comment. If human feedback is ambiguous or conflicts with the ticket, OpenSpec, security policy, or another human comment, stop before guessing and report the blocker in the PR and Plane ticket.

Before PR handoff, merge, or QA promotion, stop when any current PR feedback batch is unresolved, any OpenSpec `## PR Review Feedback` task is incomplete, or the merged PR still has `needs-tests` or `needs-changes`.

## Nexus Artifacts

Nexus is mandatory for DEV, QA, PROD, and rollback promotion. Do not rebuild between environments and do not deploy from local files.

Artifact identity is the commit SHA:

```text
app/{commitSha}/app.zip
app/{commitSha}/app.zip.sha256
app/{commitSha}/commit.sha
app/{commitSha}/release.json
```

`commit.sha` must exactly match the artifact commit. `app.zip.sha256` must verify the ZIP before deployment.

## Release Manifest

Validate `release.json` against `.codex/skills/_shared/release.schema.json` when reading or writing it. Preserve existing fields when adding stage-specific data.

Required baseline fields:

- `schemaVersion`
- `commitSha`
- `checksum`
- `artifactUrl`
- `planeTicketKey`
- `versionStatus`

Stage-specific fields are added by the responsible skill:

- DEV/QA deployment: DEV/QA URLs, statuses, health checks, PR URL, workflow URL.
- E2E QA: source RC version, QA evidence URL, QA result, tested URLs, QA timestamp.
- PROD: final release version, final tag, PROD URL, PROD statuses, monitoring status, PROD timestamp.
- Rollback: rollback timestamp, rollback workflow URL, rollback source/current version relationship.

## Version Rules

- Source RC format: `vMAJOR.MINOR.PATCH-rc.N`
- Final release format: `vMAJOR.MINOR.PATCH`
- RC tags must be annotated and point to the tested artifact commit.
- Final tags must be annotated and point to the QA-approved artifact commit.
- If no RC is supplied, derive the next RC from existing tags only when unambiguous.

## Rerun And Failure Policy

Reruns must continue from the latest completed marker, branch, PR, artifact, tag, or manifest checkpoint.

Stop instead of guessing when:

- the ticket, PR, commit, artifact, or target state is ambiguous,
- Nexus is unavailable for promotion,
- PR labels still indicate blocking review/test work,
- QA evidence cannot be safely stored or published,
- release manifest fields conflict with Plane comments or tags,
- `main` diverges from the intended QA-approved commit.

Rollback does not rewrite `main`. After rollback, require a hotfix PR, revert PR, or explicit temporary divergence note with owner and expected resolution.
