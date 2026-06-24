---
name: dev-flow-implement-change
description: Implement an OpenSpec change through the complete local delivery workflow. Use when Codex is asked to run /opsx:apply, implement a OpenProject work package or OpenSpec change, add edge-case tests, verify the app, commit, push, open a Gitea pull request, invoke a PR review agent, move the OpenProject work package to review, or complete implementation handoff.
---

# OpenSpec Implement Change

## Overview

Use this skill to take an active OpenSpec change from implementation through Gitea PR handoff. Compose the existing `dev-flow-apply-change` workflow with local verification, Git, Gitea, the `dev-flow-pr-review-agent` skill, and OpenProject API updates.

For exact Gitea and OpenProject endpoint guidance, read `references/gitea-ticket-handoff.md` before making API calls. Read `docs/context-management.md` before implementation handoff so context findings, freshness, and handoff summaries match the repo policy.

## Shared Context

Before ticketed implementation, read `.codex/skills/_shared/delivery-contract.md` and `docs/context-management.md`. Keep the active ticket, OpenSpec change, validation gates, review handoff, and deployment context aligned.

## Configuration

Read `.codex/client-tools.local.json` first. Fall back to `.codex/client-tools.example.json` for defaults only, then apply environment variable overrides when present.

Required or defaulted values:

- `openProject.baseUrl`, `openProject.apiToken`, `openProject.projectIdentifier`, `openProject.projectIdentifier`
- `openProject.reviewStatus`: target state after PR creation and review. Default: `In Review`.
- `git.baseBranch`, `git.branchPattern`, `git.maxBranchLength`
- `gitea.baseUrl`: default `http://localhost:3000`
- `gitea.apiToken`: required for Gitea API mutations.
- `gitea.owner` and `gitea.repo`: infer from `git remote get-url origin` when omitted.
- `pr.reviewers`: either `"all"` or an array of Gitea usernames.
- `pr.labels`: optional label config. Defaults to `codex-reviewed`, `needs-tests`, and `needs-changes`.

Optional environment variables override local JSON when present: `OPENPROJECT_REVIEW_STATUS`, `GITEA_BASE_URL`, `GITEA_API_TOKEN`, `GITEA_OWNER`, `GITEA_REPO`, `PR_REVIEWERS`, `PR_LABEL_REVIEWED`, `PR_LABEL_NEEDS_TESTS`, `PR_LABEL_NEEDS_CHANGES`.

Never print, commit, paste into tickets, or write real API tokens into tracked files.

## Workflow

### 1. Select And Apply The Change

1. Select the OpenSpec change using the existing `dev-flow-apply-change` rules. If ambiguous, list active changes and ask the user to choose.
2. Announce the selected change and how to override it.
3. Run the equivalent of `/opsx:apply <change>` by following `.codex/skills/dev-flow-apply-change/SKILL.md`.
4. Read every context file returned by `openspec instructions apply --change "<name>" --json`.
5. Implement every pending task unless blocked by unclear requirements or a design conflict.
6. Mark each task complete only after its code and validation are complete.

### 2. Add Edge-Case Tests

Add or update focused unit tests for the meaningful edge cases introduced by the implementation. Prefer existing test frameworks and patterns. Cover boundaries, invalid inputs, missing config, fallback paths, and failure modes when they are relevant to the change.

If the repository has no test project or framework, report that clearly and add the smallest appropriate test structure only when it fits the project conventions.

### 3. Verify Locally

Discover validation commands from manifests, README files, project files, and existing scripts. Run:

- the most specific test command for changed code
- any available build/check command
- the app locally when the repo has a runnable app and the command is discoverable

Fix every failure before continuing. If no runnable app exists, record that as a verification gap instead of inventing a command.

For web/API application work, preserve the deployment health contract: `/health` must return HTTP 200 with JSON `status=ok` and must not expose secrets or host internals. Add or preserve tests for this endpoint when app startup, routing, middleware, hosting, or deployment-facing behavior changes. Treat health endpoint removal or breakage as a release-blocking implementation failure.

### 4. Commit And Push

1. Run Context Findings Review before staging.
2. Inspect `git status --porcelain` and stage only intentional files.
3. Create a commit with a human-readable subject derived from the branch or change name.
4. Include a commit body with:
   - implemented changes
   - tests added or changed
   - verification commands run
5. Push the branch.
6. If Husky or another Git hook fails during commit or push, fix the issue, rerun relevant verification, update the commit as needed, and retry. Do not bypass hooks unless the user explicitly instructs that in the current chat.

### Context Findings Review

Before committing, classify durable implementation findings using `docs/context-management.md` and `.codex/skills/_shared/delivery-contract.md`:

- architecture/topology/source-of-truth finding -> `docs/architecture.md`
- local setup, commands, repo conventions, testing, or quality gates -> `docs/development.md`
- artifact, deployment, QA, release, rollback, or monitoring finding -> `docs/deployment.md`
- agent context loading, freshness, authority, handoff, or conflict rule -> `docs/context-management.md`
- enforceable automation behavior -> `.codex/skills/_shared/delivery-contract.md` plus related skills and tests

If implementation discovers durable knowledge, update the matching doc in the same PR. If no durable knowledge was discovered, record `Docs: no durable context changes` in the PR body and OpenProject handoff comment.

### 5. Open The Gitea PR

1. Resolve `owner` and `repo` from config or the `origin` remote.
2. Resolve reviewers:
   - If `pr.reviewers` equals `"all"`, list repository collaborators/developers from Gitea, normalize the response to a candidate list even when Gitea returns a single object, resolve each reviewer from `login` first and `username` second, then exclude the PR author plus the automation user.
   - If `pr.reviewers` is an array, use that username list exactly.
   - If no reviewers can be resolved, create the PR without reviewers and document the gap in the PR body.
3. Create configured PR labels if they do not exist and labels are enabled.
4. Create the PR with title from the branch in human-readable text and a body containing all commit message change lists, `Context findings: added/updated/none`, `Docs updated: <files>` or `Docs: no durable context changes`, and `Assumptions recorded: <short list or none>`.
5. Verify human reviewers before review handoff:
   - If reviewers were resolved but the PR create response does not show them as requested, call `POST /api/v1/repos/{owner}/{repo}/pulls/{prNumber}/requested_reviewers` with the resolved reviewer usernames.
   - Re-fetch the PR and confirm the requested reviewers are present.
   - If Gitea rejects reviewer assignment or the verification still shows no requested reviewers, document the gap in the PR body, OpenProject handoff comment, and final summary before moving on.
6. Apply the configured reviewed label after the review agent completes. Apply `needs-tests` or `needs-changes` when the review agent reports those outcomes.

### 6. Review And Update OpenProject

1. Invoke the `dev-flow-pr-review-agent` skill against the newly created PR.
2. Move the linked OpenProject work package to `openProject.reviewStatus`, default `In Review`, only after PR creation, human reviewer request verification or documented reviewer gap, and review-agent posting complete.
3. Add a OpenProject comment containing the PR link, `Context findings: added/updated/none`, `Docs updated: <files>` or `Docs: no durable context changes`, and `Assumptions recorded: <short list or none>`.
4. If the configured OpenProject status is missing, stop after PR creation and review, report the missing state, and do not guess another state.

## Idempotency And Failure Rules

- Do not duplicate PRs for the same source branch; reuse an existing open PR when found.
- Do not duplicate OpenProject PR-link comments when the same PR URL is already present.
- Use stable generated markers for PR review comments as defined by `dev-flow-pr-review-agent`.
- Preserve unrelated user changes in the working tree. If unrelated changes block staging or verification, stop and explain the conflict.
- Treat placeholder tokens as missing config.
- Keep mutation order: implement and verify, commit, push, PR, review agent, OpenProject status/comment.

## Completion Summary

End with the selected change, commit SHA, PR URL, reviewers requested, labels applied, OpenProject status update result, verification commands, context findings, docs updated or `Docs: no durable context changes`, assumptions recorded, and any gaps.

## Output

Report implementation scope, files changed, tests and validation run, PR/review state, ticket handoff, and any blockers.

## Failure Rules

Stop when the change or ticket context is ambiguous, required local config is missing, validation fails, unrelated user changes block safe staging, or review/ticket handoff cannot be verified.
