# Delivery Workflow Contract

Use this reference before running non-config delivery skills. Skill-local instructions may add stricter checks, but must not weaken this contract.

For repeated Plane, Gitea, Nexus, and Git endpoint patterns, read `.codex/skills/_shared/api-helpers.md`.

## Skill Synchronization Rule

When changing any non-OpenSpec delivery skill or any `configure-*` skill, check for policy drift across related skills before finishing.

Source-of-truth order:

1. `_shared/delivery-contract.md`
2. Non-OpenSpec delivery-flow skills: `parallel-ticket-coordinator`, `automatic-implement-ticket`, `plane-start-ticket`, `implement-ticket`, `gitea-pr-review-agent`, `post-merge-deploy`, `deploy-to-qa`, `test-e2e`, `deploy-to-prod`, `rollback-prod`, `file-qa-bug`, `pipeline-status`, and `hotfix-prod`
3. Configure skills and generated templates: `configure-dev-environment`, `configure-artifact-delivery`, `configure-quality-gates`, and related `configure-*` skills

If configure skills differ from delivery-flow skills, update configure docs, templates, audits, and tests to match the delivery-flow rule. Do not update OpenSpec-specific skills unless the requested change explicitly affects OpenSpec behavior.

Before finishing any change to a non-OpenSpec delivery skill, run this completion gate:

- Identify whether the skill change affects repo setup, generated files, workflow YAML, secrets, ignored local files, Plane/Gitea labels, ticket gates, artifact paths, release manifests, QA/PROD promotion, rollback, or audit/repair behavior.
- If it does, update the matching `configure-*` skill docs, references, templates, scripts, and tests in the same change.
- If it does not, state in the final response that the configure skills were checked and no configure sync was required.
- Add or update regression tests for the sync point when the behavior is enforceable from files.

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
- Copy ignored local config needed by child skills into each worktree without printing tokens, passwords, cookies, or credential-bearing URLs. Keep tracked templates placeholder-safe.
- Implementation and review stages may run concurrently across tickets.
- DEV, QA, E2E QA, PROD, rollback, and hotfix promotion share deployment lanes and release tags. With `deploymentLanePolicy` set to `serialized`, only the recorded lane owner may run `post-merge-deploy`, `deploy-to-qa`, `test-e2e`, or `deploy-to-prod`; other agents must wait or report the owner.
- PROD promotion remains explicit. Parallel delivery must not promote to PROD only because QA passed.

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

## PR Labels And Review Severity

Default labels:

- Reviewed: `codex-reviewed`
- Missing tests: `needs-tests`
- Blocking changes: `needs-changes`

Review findings must use:

- `BLOCKER`: must be fixed before handoff/promotion.
- `WARNING`: meaningful non-blocking risk.
- `SUGGESTION`: optional improvement.

QA promotion must stop when a merged PR still has `needs-tests` or `needs-changes`.

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
