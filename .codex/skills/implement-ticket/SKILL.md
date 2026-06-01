---
name: implement-ticket
description: Implement an already-started Plane ticket through OpenSpec tasks, configured quality and coverage gates, Gitea PR handoff, review-agent fixes, and Plane review-state update. Use when a Plane ticket already has an implementation branch and OpenSpec change, or when Codex is asked to continue, finish, validate, or hand off ticket implementation work.
---

# Implement Ticket

## Overview

Use this skill after `plane-start-ticket` has created or reused the implementation branch, moved the Plane ticket to progress, and created the OpenSpec change. This skill owns implementation through PR handoff. It does not select Todo tickets, create initial branches, or archive OpenSpec changes.

## Shared Context

Before implementation, handoff, or review work, follow `.codex/skills/_shared/skill-startup.md` with `docs/development.md` as the stage-specific doc.

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

## Workflow

### 1. Resolve Context

1. Identify the Plane ticket, current branch, and OpenSpec change from user input, branch name, or existing OpenSpec changes.
2. Read `.codex/delivery-context.local.json` when present and verify the resolved Plane ticket, current branch, OpenSpec change, existing PR, and any artifact commit match the locked `ticketKey`. If they resolve to another ticket, stop and report the mismatch.
3. Stop if the branch or OpenSpec change is missing; tell the user to run the `plane-start-ticket` flow first.
4. Check `git status --porcelain`. If unrelated changes exist, stop before implementation and list the changed files.
5. Detect resume checkpoints before doing new work:
   - completed and pending OpenSpec tasks,
   - existing implementation commits on the branch,
   - upstream branch and push status,
   - existing open PR for the branch,
   - latest review-agent marker and stable AI finding ids for the current head SHA,
   - existing OpenSpec `## PR Review Feedback` tasks,
   - human-authored top-level PR comments and inline code review comments,
   - latest Plane `IA generated PR feedback detected: {headSha}:{feedbackBatchId}` markers,
   - latest Plane `IA generated PR feedback fixes: {headSha}:{feedbackBatchId}` markers,
   - current `needs-tests` and `needs-changes` labels,
   - latest Gitea Actions status.
   Continue from the latest completed checkpoint instead of restarting earlier steps.
6. Confirm the OpenSpec change is active:
   ```powershell
   openspec status --change "<change>" --json
   ```
7. Load apply instructions:
   ```powershell
   openspec instructions apply --change "<change>" --json
   ```
8. Read every context file returned by the apply instructions.

### 2. Discover Quality Gates

Inspect configured quality surfaces. Do not invent validation commands.

- `.codex/quality.local.json`, falling back to coverage threshold `80`
- `.codex/quality.example.json`, for the tracked default
- `.gitea/workflows/pr-validation.yml`
- `.gitea/workflows/README.md`
- `lefthook.yml`

Treat Gitea Actions PR validation as the authoritative quality gate. Treat local hooks as automatic protections that run through normal Git operations.

For coverage, discover a local fallback command before relying on CI-only feedback:

1. Prefer the command used by `.gitea/workflows/pr-validation.yml`.
2. Then prefer commands documented in `.gitea/workflows/README.md`, `lefthook.yml`, project README files, or package/build manifests.
3. If exactly one stack-native coverage command is obvious, use it as a local fallback. For .NET, this may be `dotnet test --collect:"XPlat Code Coverage"` only when the repo is clearly a .NET test solution and no repo-specific command overrides it.
4. If no unambiguous local coverage command exists, report that CI remains the only coverage source.

The local fallback is advisory for faster iteration. Gitea Actions remains authoritative before PR handoff.

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
2. Treat app, code, spec, formatting, build, test, coverage, staged-secret, or PR review feedback against changed behavior as implementation failures. Fix them in the current ticket, add or update OpenSpec tasks before or alongside the fix, update specs/design when behavior changes, and add or update tests for regressions, edge cases, and coverage gaps.
3. Treat runner, workflow-container, Docker image pull, missing `node`, local Gitea hostname, scanner installation, missing shell tool, or stale tool-install URL failures as infra/tooling failures. Route through `configure-dev-environment`, `configure-gitea-actions-runner`, or `configure-quality-gates`; run `AuditQualityGates` and `ValidateGiteaActionsRunner` when applicable.
4. If an infra/tooling failure blocks the authoritative PR gate, fix repo-owned workflow/config issues in the branch or route external setup issues to the infra skill, then keep the ticket open until Gitea PR validation passes. Record the fix separately from feature implementation work.
5. Full local `gitleaks detect --source . --redact --no-git` findings in ignored local secret files are local setup notes, not implementation defects. Staged `gitleaks protect --staged --redact` and CI secret scans remain authoritative for tracked changes.
6. Treat flaky or intermittent failures separately when the same command or CI job passes and fails without code changes. Rerun once. If the rerun passes, record a flaky-test note and continue only when the authoritative gate is passing. If it fails again, classify as implementation or infra based on the failure evidence.
7. Maintain a running list grouped as feature fixes, quality/test fixes, flaky/intermittent notes, infra validation fixes, and remaining non-blocking infra notes.

### 6. Verify OpenSpec

Run `openspec-verify-change` before PR handoff. Fix critical issues. Convert required follow-up into OpenSpec tasks and keep artifacts current with the final code state.

### 7. Commit And Push

1. Run Context Findings Review before staging.
2. Stage only intentional files.
3. Commit with a message that satisfies the configured commit hook and includes the Plane ticket or OpenSpec id.
4. Let hooks run naturally. Do not bypass hooks unless the user explicitly requests that in the current chat.
5. Push the branch.

### Context Findings Review

Before committing, apply the Context Findings classification from `docs/context-management.md` and the memory update process from `.codex/memory/retrieval-policy.md`. If the finding changes enforceable automation behavior, update `.codex/skills/_shared/delivery-contract.md` plus related skills and tests.

If implementation discovers durable authoritative knowledge, update the matching doc in the same PR. If it discovers reusable non-authoritative knowledge, update `.codex/memory/`. If no durable knowledge was discovered, record `Docs: no durable context changes` in the PR body and Plane handoff comment.

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
- Context findings: added/updated/none
- Docs updated: <files> or Docs: no durable context changes
- `Memory updated: <files>` or `Memory updated: none`
- Assumptions recorded: <short list or none>
- remaining non-blocking infra notes
- known non-blocking product risks or gaps

### 9. Review And Fix Loop

Invoke the repo-owned `pr-review-feedback-loop` skill after PR creation and on every open-PR resume. That skill owns AI review findings, late human PR comments, feedback batch ids, Plane detection/fix comments, and OpenSpec `## PR Review Feedback` tasks. Do not put this local delivery behavior in external `openspec-*` skills.

After `pr-review-feedback-loop` returns, continue only when:

- current-head AI review has been run or reused,
- all OpenSpec `## PR Review Feedback` tasks are complete,
- all current feedback batches have `IA generated PR feedback fixes: {headSha}:{feedbackBatchId}` markers,
- validation for feedback fixes has passed,
- `pr.labels.needsTests` and `pr.labels.needsChanges` are no longer valid for the current head.

Keep Plane in `In Review` while late human feedback fixes are applied. If `pr-review-feedback-loop` reports ambiguous or conflicting human feedback, stop and preserve its blocker classification.

### 10. Plane Handoff

Move the Plane ticket to `plane.reviewState`, default `In Review`, only after PR creation, AI review-agent posting, all current OpenSpec PR review feedback tasks are complete, all current feedback batches have fix markers, and blocking fix loops are complete. If the ticket is already `In Review` during a late human-feedback resume, leave it there and add the detection/fix comments instead of moving state.

Add a Plane comment with:

- PR link
- coverage threshold used
- quality gate result
- feature fixes applied
- quality/test fixes applied
- infra validation fixes applied
- improvements applied
- tests added or updated
- Context findings: added/updated/none
- Docs updated: <files> or Docs: no durable context changes
- `Memory updated: <files>` or `Memory updated: none`
- Assumptions recorded: <short list or none>
- remaining non-blocking infra notes
- remaining non-blocking risks or gaps

Do not move the ticket to Done.

## Output

Report the ticket, branch, OpenSpec change, PR URL, commits pushed, validation and coverage results, PR review feedback batches handled, Context Findings Review result, Plane handoff state, and any remaining blockers or risks.

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
- Missing local coverage command: report the gap; do not invent a command when CI is the only configured coverage source.
- Flaky test or CI failure: rerun once before classifying; do not edit product code solely for an unconfirmed intermittent failure.
- Gitea Actions infra/tooling failure: route through `configure-dev-environment`, `configure-gitea-actions-runner`, or `configure-quality-gates`; run `ValidateGiteaActionsRunner` when runner/container compatibility is implicated; do not classify it as a product implementation defect.
- Ignored local secret findings from full local scans: report as local setup notes unless the same secret is staged, tracked, or reported by CI.
- Existing PR: reuse it instead of creating a duplicate.
- Existing review-agent comment for same head SHA: reuse it instead of posting a duplicate; post a new review marker only after the head SHA changes.
- Actionable AI or human PR feedback: invoke `pr-review-feedback-loop` to create OpenSpec `## PR Review Feedback` tasks, post Plane feedback batch comments, apply fixes, validate, commit, push, and rerun AI review before handoff.
- Ambiguous or conflicting human PR feedback: stop before changing code, request clarification in the PR when possible, and record the blocker in Plane.
- Late human PR feedback after `In Review`: process it on manual resume and keep Plane in `In Review` while fixes are applied.
- Stale PR labels: remove `needs-tests` after required tests are added and passing; remove `needs-changes` after requested fixes are in place, OpenSpec PR review feedback tasks are complete, and the current-head review has no blocking findings.
- Review loop exceeds 3 cycles with remaining blockers: stop and escalate with a concise conflict/stale-feedback summary.
- Missing Plane review state: stop after PR/review work and report the missing state.
