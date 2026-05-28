---
name: post-merge-deploy
description: Coordinate the post-merge transition from a Gitea PR merged to dev into QA deployment by validating PR labels, resolving the merge commit, waiting for Nexus artifact metadata, and delegating promotion to deploy-to-qa. Use after a PR merges or when Codex is asked to trigger or continue QA deployment for merged work.
---

# Post Merge Deploy

## Overview

Use this skill after a PR has merged to `dev` but before QA promotion. It is an orchestration bridge: validate the merged PR is eligible, wait for the immutable artifact, then invoke `deploy-to-qa`.

Do not perform DEV/QA validation inside this skill. `deploy-to-qa` owns artifact promotion and environment checks.

Before running, read `.codex/skills/_shared/delivery-contract.md`. Use `.codex/skills/_shared/scripts/delivery_tools.ps1 -Mode ArtifactPaths` when building Nexus artifact paths.

## Configuration

Read `.codex/client-tools.local.json` first. Required values are Plane, Gitea, and Nexus settings used by `deploy-to-qa`.

Never print or write real tokens, passwords, cookies, Azure credentials, or Nexus credentials.

## Workflow

1. Resolve the PR from user input, current branch, Plane comments, commit messages, or ticket key.
2. Verify the PR is merged and its target branch is `dev`.
3. Verify the PR does not currently have configured `pr.labels.needsChanges` or `pr.labels.needsTests`.
4. Resolve the merge commit SHA from Gitea metadata.
5. Resolve the Plane ticket key from the PR title/body, branch name, commit messages, or Plane comments.
6. Poll for the Nexus artifact files for the merge commit:
   - `app/{commitSha}/app.zip`
   - `app/{commitSha}/app.zip.sha256`
   - `app/{commitSha}/commit.sha`
   - `app/{commitSha}/release.json` when present
7. Use bounded waiting: check immediately, then retry with backoff for up to 10 minutes unless the user asked for a shorter wait.
8. Verify `commit.sha` matches the merge commit before delegating.
9. Invoke `deploy-to-qa` with the resolved PR, ticket key, and merge commit.

## Idempotency

- If the QA deployment marker `IA generated QA deployment: {commitSha}` already exists and the ticket is in QA, report that QA promotion is already complete.
- If the artifact exists, skip waiting and delegate immediately.
- If labels were stale but have since been removed, continue.

## Failure Rules

- Unmerged PR: stop and report the PR state.
- PR target is not `dev`: stop and report the mismatch.
- Stale `needs-changes` or `needs-tests` labels: stop before artifact promotion.
- Nexus artifact missing after the wait window: stop and report artifact paths checked.
- Nexus unavailable: stop; do not use a degraded artifact source.
- Commit metadata mismatch: stop and report the expected and actual commit SHA.
