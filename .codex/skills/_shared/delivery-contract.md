# Delivery Workflow Contract

Use this reference before running non-config delivery skills. Skill-local instructions may add stricter checks, but must not weaken this contract.

For repeated Plane, Gitea, Nexus, and Git endpoint patterns, read `.codex/skills/_shared/api-helpers.md`.

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
