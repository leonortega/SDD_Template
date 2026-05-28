---
name: implement-ticket
description: Implement an already-started Plane ticket through OpenSpec tasks, configured quality and coverage gates, Gitea PR handoff, review-agent fixes, and Plane review-state update. Use when a Plane ticket already has an implementation branch and OpenSpec change, or when Codex is asked to continue, finish, validate, or hand off ticket implementation work.
---

# Implement Ticket

## Overview

Use this skill after `plane-start-ticket` has created or reused the implementation branch, moved the Plane ticket to progress, and created the OpenSpec change. This skill owns implementation through PR handoff. It does not select Todo tickets, create initial branches, or archive OpenSpec changes.

## Configuration

Read `.codex/client-tools.local.json` first. Fall back to `.codex/client-tools.example.json` only for defaults and setup guidance.

Read coverage config from `.codex/quality.local.json` when present. If it is missing, invalid, or missing `coverage.minimumPercent`, use `80` and report the configuration gap. The safe tracked template is `.codex/quality.example.json`.

Required/defaulted values:

- `plane.baseUrl`, `plane.apiToken`, `plane.workspaceSlug`, `plane.projectIdentifier`
- `plane.reviewState`, default `In Review`
- `git.baseBranch`
- `gitea.baseUrl`, `gitea.apiToken`, `gitea.owner`, `gitea.repo`
- `pr.reviewers`
- `pr.labels.reviewed`, `pr.labels.needsTests`, `pr.labels.needsChanges`
- `coverage.minimumPercent`, default `80`

Never print, commit, paste into tickets, or write real tokens into tracked files.

## Workflow

### 1. Resolve Context

1. Identify the Plane ticket, current branch, and OpenSpec change from user input, branch name, or existing OpenSpec changes.
2. Stop if the branch or OpenSpec change is missing; tell the user to run the `plane-start-ticket` flow first.
3. Check `git status --porcelain`. If unrelated changes exist, stop before implementation and list the changed files.
4. Confirm the OpenSpec change is active:
   ```powershell
   openspec status --change "<change>" --json
   ```
5. Load apply instructions:
   ```powershell
   openspec instructions apply --change "<change>" --json
   ```
6. Read every context file returned by the apply instructions.

### 2. Discover Quality Gates

Inspect configured quality surfaces. Do not invent validation commands.

- `.codex/quality.local.json`, falling back to coverage threshold `80`
- `.codex/quality.example.json`, for the tracked default
- `.gitea/workflows/pr-validation.yml`
- `.gitea/workflows/README.md`
- `lefthook.yml`

Treat Gitea Actions PR validation as the authoritative quality gate. Treat local hooks as automatic protections that run through normal Git operations.

When Gitea Actions runner, workflow container, or security tool compatibility is part of the configured gate, use the existing infra validation path instead of inventing ad hoc checks:

```powershell
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode AuditQualityGates
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode ValidateGiteaActionsRunner
```

Use `ValidateGiteaActionsRunner` whenever Gitea Actions fails before repository validation commands run, or logs show image pull failures, missing `node`, checkout networking failures, missing scanners, missing shell tools, or job-container tool incompatibility.

### 3. Implement Tasks

Follow `openspec-apply-change`:

1. Implement pending OpenSpec tasks one at a time.
2. Add or update tests for changed behavior.
3. Mark a task complete only after its code and related tests are updated.
4. If implementation reveals extra required work, add a new OpenSpec task before doing that work.
5. Keep OpenSpec specs, design notes, and tasks aligned with the latest implementation.

### 4. Quality And Coverage Completion

Implementation is not complete until:

- all OpenSpec tasks are complete,
- OpenSpec verification has no critical issues,
- configured local hooks or quality tools pass when they run,
- Gitea PR validation passes,
- coverage meets `coverage.minimumPercent`.

For web/API application work, preserve the delivery health contract required by deployment promotion:

- The app must expose `/health` with HTTP 200 and JSON `status=ok`.
- The endpoint must not expose secrets, connection strings, tokens, host internals, or detailed exception data.
- Add or preserve focused tests for `/health` when application startup, routing, middleware, hosting, or deployment-facing behavior changes.
- Treat removal or breakage of `/health` as an implementation failure because DEV, QA, and PROD promotion gates depend on it.

If coverage is below the configured threshold, add or update OpenSpec tasks for missing test coverage, then add tests until the threshold is met. Never lower the threshold just to pass a ticket.

### 5. Validation Failure Classification

When local hooks, configured quality tools, OpenSpec verification, PR review, or Gitea Actions fail:

1. Classify the failure before editing files.
2. Treat app, code, spec, formatting, build, test, coverage, staged-secret, or review findings against changed behavior as implementation failures. Fix them in the current ticket, add or update OpenSpec tasks before or alongside the fix, update specs/design when behavior changes, and add or update tests for regressions, edge cases, and coverage gaps.
3. Treat runner, workflow-container, Docker image pull, missing `node`, local Gitea hostname, scanner installation, missing shell tool, or stale tool-install URL failures as infra/tooling failures. Route through `configure-dev-environment`, `configure-gitea-actions-runner`, or `configure-quality-gates`; run `AuditQualityGates` and `ValidateGiteaActionsRunner` when applicable.
4. If an infra/tooling failure blocks the authoritative PR gate, fix repo-owned workflow/config issues in the branch or route external setup issues to the infra skill, then keep the ticket open until Gitea PR validation passes. Record the fix separately from feature implementation work.
5. Full local `gitleaks detect --source . --redact --no-git` findings in ignored local secret files are local setup notes, not implementation defects. Staged `gitleaks protect --staged --redact` and CI secret scans remain authoritative for tracked changes.
6. Maintain a running list grouped as feature fixes, quality/test fixes, infra validation fixes, and remaining non-blocking infra notes.

### 6. Verify OpenSpec

Run `openspec-verify-change` before PR handoff. Fix critical issues. Convert required follow-up into OpenSpec tasks and keep artifacts current with the final code state.

### 7. Commit And Push

1. Stage only intentional files.
2. Commit with a message that satisfies the configured commit hook and includes the Plane ticket or OpenSpec id.
3. Let hooks run naturally. Do not bypass hooks unless the user explicitly requests that in the current chat.
4. Push the branch.

### 8. Create Or Reuse The Gitea PR

Reuse an existing open PR for the branch when present. Otherwise create a PR targeting the configured base branch.

The PR body must include:

- Plane ticket id
- OpenSpec change id
- implementation summary
- tests added or updated
- coverage threshold used
- configured quality gates expected to run
- feature fixes applied
- quality/test fixes applied
- infra validation fixes applied
- remaining non-blocking infra notes
- known non-blocking product risks or gaps

### 9. Review And Fix Loop

Invoke `gitea-pr-review-agent`. Fix actionable findings, update OpenSpec tasks/artifacts for each review-driven fix, push updates, and repeat until there are no blocking review findings or quality failures. Apply configured PR labels based on the final review outcome.

The review agent uses `<!-- codex-review-agent:{headSha} -->` markers. After every pushed head SHA, ensure the review-agent outcome applies to the current head. Do not duplicate review comments for the same head SHA unless the user explicitly asks for a fresh review.

When the current head has passing tests/CI and the latest review-agent outcome no longer identifies missing tests or blocking changes, remove stale `pr.labels.needsTests` and `pr.labels.needsChanges` labels from the PR. Keep `pr.labels.reviewed` when the current head has been reviewed.

### 10. Plane Handoff

Move the Plane ticket to `plane.reviewState`, default `In Review`, only after PR creation, review-agent posting, and blocking fix loops are complete.

Add a Plane comment with:

- PR link
- coverage threshold used
- quality gate result
- feature fixes applied
- quality/test fixes applied
- infra validation fixes applied
- improvements applied
- tests added or updated
- remaining non-blocking infra notes
- remaining non-blocking risks or gaps

Do not move the ticket to Done.

## Archive And QA Policy

- Do not archive OpenSpec changes in this skill.
- Archive only after PR merge in a separate post-merge flow.
- QA findings after merge must create a new related Plane bug ticket linked to the parent ticket.
- The bug ticket gets its own branch, OpenSpec change if needed, implementation, PR, and review flow.

## Failure Rules

- Missing branch or OpenSpec change: stop and route to `plane-start-ticket`.
- Dirty worktree with unrelated changes: stop before implementation.
- Missing or placeholder API token: stop before Plane or Gitea mutations.
- Invalid coverage config: use `80`, report the issue, and do not lower the gate.
- Failing coverage: add/update OpenSpec task and tests before completion.
- Gitea Actions infra/tooling failure: route through `configure-dev-environment`, `configure-gitea-actions-runner`, or `configure-quality-gates`; run `ValidateGiteaActionsRunner` when runner/container compatibility is implicated; do not classify it as a product implementation defect.
- Ignored local secret findings from full local scans: report as local setup notes unless the same secret is staged, tracked, or reported by CI.
- Existing PR: reuse it instead of creating a duplicate.
- Existing review-agent comment for same head SHA: reuse it instead of posting a duplicate; post a new review marker only after the head SHA changes.
- Stale PR labels: remove `needs-tests` after required tests are added and passing; remove `needs-changes` after requested fixes are in place and the current-head review has no blocking findings.
- Missing Plane review state: stop after PR/review work and report the missing state.
