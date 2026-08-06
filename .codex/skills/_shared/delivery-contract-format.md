<!-- TIER 2: SEMI-STABLE - Stable markers and OpenProject comment format reference -->

# Delivery Contract — Format Reference

Extracted from `delivery-contract-core.md` to keep core rules focused on logic. Load this file when the task involves
generating or checking markers, comments, or format strings.

## Stable Markers

Use these exact markers for idempotency. Markers are grouped by workflow stage.

### General Flow

- Branch start: `IA generated branch: {branchName}`
- Ticket PR comment: `IA generated PR: {prUrl}`
- Ticket handoff: `IA generated handoff: {ticketKey}`
- Workflow timing: `IA generated workflow timing: {ticketKey}`
- OpenProject generated description block: `<!-- ia-generated:start -->` through `<!-- ia-generated:end -->`

### Bug Flow (QA-Discovered Defects)

- QA bug (parent notification): `IA generated QA bug: {parentTicketKey}`
- Bug specification: `IA generated bug specification: {bugKey}`
- Bug branch: `IA generated bug branch: fix/{bugKeySlug}-{short-description}`
- Bug PR: `IA generated bug PR: {prUrl}`
- Bug closed: `IA generated bug closed: {bugKey}`

### Review Flow (AI & Human PR Review)

- PR review agent: `<!-- codex-review-agent:{headSha} -->`
- PR review feedback detected: `IA generated PR feedback detected: {headSha}:{feedbackBatchId}`
- PR review feedback fixes: `IA generated PR feedback fixes: {headSha}:{feedbackBatchId}`

### QA & E2E Flow

- QA deployment: `IA generated QA deployment: {commitSha}`
- E2E QA: `IA generated E2E QA: {ticketKey}`

### Production Flow (Deploy, Rollback, Hotfix)

- PROD deployment: `IA generated PROD deployment: {finalVersion}`
- Post-PROD retrospective: `IA generated post-PROD retrospective: {finalVersion}`
- PROD rollback: `IA generated PROD rollback: {rollbackVersionOrCommit}`
- PROD rollback incident: `IA generated PROD rollback incident: {rollbackVersionOrCommit}`
- PROD hotfix: `IA generated PROD hotfix: {incidentOrTicketKey}`

Before adding generated comments or moving states, read existing comments when the API allows it and treat matching
markers as already completed.

## OpenProject Comment Format

Generated OpenProject comments must keep the stable marker as the first line by itself, followed by a blank line and a
human-readable Markdown summary. Use this structure:

1. `**Status:** PASS|FAIL|BLOCKED - one-sentence outcome`
2. `**Context:**` compact bullets for ticket, state, version, commit, PR, artifact, and workflow run.
3. `**Validation:**` grouped bullets or a small Markdown table for environment checks, test totals, and monitoring
checks.
4. `**Evidence:**` durable links to Nexus manifests, evidence ZIPs, screenshots, logs, or local fallback paths.
5. `**Notes:**` only when defects, blockers, assumptions, or tooling issues matter.

Prefer Markdown links for long URLs, short commit display text such as `8acc4d4` with the full SHA recorded in a field
when needed, and grouped sections over long flat lists. Keep automation-critical
values present and searchable; do not hide the stable marker, commit SHA, ticket key, release version, artifact URL, or
evidence URL inside prose only.
