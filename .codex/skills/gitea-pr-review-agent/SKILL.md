---
name: gitea-pr-review-agent
description: Review a specific Gitea pull request and post actionable findings. Use when Codex is asked to review a Gitea PR, review the PR just created by the implementation workflow, inspect PR diffs, use internet research to validate code quality, post review comments, or apply review outcome labels such as codex-reviewed, needs-tests, or needs-changes.
---

# Gitea PR Review Agent

## Overview

Use this skill to review one explicit Gitea pull request. It is invoked by `openspec-implement-change` after PR creation or directly by a user; it is not a recurring polling workflow.

For exact Gitea API endpoint guidance, read `references/gitea-review-api.md` before making API calls.

Read `.codex/skills/_shared/delivery-contract.md` before posting review output so severity labels, ticket context lock, and PR label semantics remain consistent with implementation and deployment gates.

## Configuration

Read `.codex/client-tools.local.json` first. Fall back to `.codex/client-tools.example.json` for defaults only, then apply environment variable overrides when present.

Required or defaulted values:

- `gitea.baseUrl`: default `http://localhost:3000`
- `gitea.apiToken`: required for PR reads and comments when the repository is private.
- `gitea.owner` and `gitea.repo`: infer from `git remote get-url origin` when omitted.
- `pr.labels.enabled`: default `true`.
- `pr.labels.reviewed`: default `codex-reviewed`.
- `pr.labels.needsTests`: default `needs-tests`.
- `pr.labels.needsChanges`: default `needs-changes`.

Never print Gitea tokens.

## Workflow

### 1. Resolve The PR

Accept a PR number, PR URL, or the current branch. If the current branch is used, list open PRs for that head branch and select the matching PR. Review only that PR.

Read `.codex/delivery-context.local.json` when present and verify the PR number, branch, title/body ticket key, and head SHA when known match the locked `ticketKey`. If the user explicitly requested a different PR, report the lock mismatch before posting labels or comments.

Fetch:

- PR metadata
- head SHA
- commits
- changed files or diff
- existing PR comments
- relevant local source files for changed code
- changed line count for diff-size classification

If a comment contains `<!-- codex-review-agent:{headSha} -->`, skip posting another review for the same head SHA unless the user explicitly asks for a fresh review.

### 2. Review The Code

Prioritize findings in this order:

1. Bugs and behavioral regressions.
2. Missing edge-case tests or broken verification.
3. Security, credential, and data-loss risks.
4. API, schema, migration, or compatibility risks.
5. Maintainability suggestions that are clearly worth acting on.

Use internet research when useful. Prefer official docs first; use trusted posts, issue discussions, or release notes only when official docs are insufficient. Cite sources in the PR comment when external research materially affects a finding.

Use these severity labels for every finding:

- `BLOCKER`: likely bug, security/data-loss risk, broken required behavior, missing required test, failing gate, or release-blocking compatibility issue.
- `WARNING`: meaningful risk or maintainability issue that should be considered but does not block the current PR.
- `SUGGESTION`: optional improvement that should not block implementation handoff.

The implementation loop treats only `BLOCKER` findings as blocking.

Use deterministic diff scope:

- Under 500 changed lines: review the full diff.
- 500 changed lines or more: perform a structured risk-based review and clearly state any areas not reviewed line-by-line.
- Always fully inspect changes touching auth, authorization, persistence, migrations, deployment workflows, secrets, public APIs, tests, and health/deployment contracts.

Restrict internet research to official documentation, primary source repositories, release notes, standards, or vendor docs unless those are insufficient for a concrete finding. Do not browse for general style opinions. Limit external research to findings where the source materially changes the conclusion.

Do not leave vague style feedback. Every finding must include the affected file or behavior, why it matters, and the suggested correction.

### 3. Post The Review

Post one top-level Gitea PR comment. Include:

- marker `<!-- codex-review-agent:{headSha} -->`
- short review summary
- findings ordered by severity
- test gaps
- diff scope reviewed and any large-diff sampling limits
- sources consulted when applicable

If no issues are found, say so clearly and mention any residual verification gaps.

### 4. Apply Labels

When `pr.labels.enabled` is true:

1. Ensure configured labels exist in Gitea. Create missing labels before applying them. Use deterministic colors:
   - `codex-reviewed`: `#5319e7`
   - `needs-tests`: `#fbca04`
   - `needs-changes`: `#d73a4a`
2. Apply the reviewed label after posting a review comment.
3. Apply the needs-tests label if the review identifies missing or failing tests.
4. Apply the needs-changes label if the review identifies actionable defects or blocking issues.
5. Remove the needs-tests label when the current head no longer has missing or failing test findings.
6. Remove the needs-changes label when the current head no longer has actionable defects or blocking issues.
7. If label creation, assignment, or removal fails due to permissions or disabled labels, continue the review and mention the label failure in the PR comment or completion summary.

## Output Style

Use a code-review stance. Lead with findings and severity. Keep summaries brief. Avoid repeating the full diff. If there are no findings, state that directly.

## Failure Rules

- Missing or placeholder `gitea.apiToken`: stop before posting comments or labels.
- PR not found: stop and report the lookup attempted.
- Duplicate review marker for the same head SHA: skip mutation unless explicitly asked to refresh.
- Internet unavailable: continue with local review and note that external validation was skipped.
- Large diffs: follow the threshold rules above and clearly state what was not reviewed line-by-line.
