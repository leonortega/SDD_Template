---
name: dev-flow-pr-review-agent
description: Review a specific pull request through the selected review adapter and post actionable findings. Use when Codex is asked to review a PR, review the PR just created by the implementation workflow, inspect PR diffs, use internet research to validate code quality, post review comments, or apply configured review outcome labels.
---

# repository PR Review Agent

## Overview

Use this skill to review one explicit repository pull request. It is invoked by `dev-flow-implement-change` after PR creation or directly by a user; it is not a recurring polling workflow.

For exact repository/review provider API endpoint guidance, read `the selected repository/review adapter` before making API calls.

## Shared Context

Before posting review output, follow `.codex/skills/_shared/skill-startup.md`, which reads `.codex/project-profile.json`, `.codex/skills/_shared/provider-adapter-contract.md`, `.codex/skills/_shared/delivery-contract.md`, and `docs/context-management.md`, with `docs/development.md` as the stage-specific doc. Load the selected review adapter for API endpoints, comment fields, status checks, and labels.

## Workflow Telemetry

When this skill runs as part of a ticket workflow and a ticket key is resolved, capture UTC start time before PR review reads. Prefer OpenProject time-entry telemetry and create or update the `dev-flow-pr-review-agent` entry with marker `IA generated workflow telemetry: {ticketKey}:dev-flow-pr-review-agent`. Use `python -m tools.sdd_cli delivery -Mode AppendWorkflowTelemetry -TicketKey {ticketKey}` only as the JSONL fallback when direct time telemetry is unavailable. On resume or idempotent reuse, append or update another row for the same stage; workflow timing rendering collapses repeated stage rows into earliest start and latest finish. Include `workflowStage=dev-flow-pr-review-agent`, `agentRole=prReview`, `startedUtc`, `finishedUtc`, `retryCount`, and `outcome`. If the review is explicitly standalone and no ticket key can be safely resolved, report that workflow telemetry was skipped.

## Configuration

Read `.codex/client-tools.local.json` first. Fall back to `.codex/client-tools.common.json` for defaults only, then apply environment variable overrides when present.

Required or defaulted values:

- `selected repository/review adapter runtime values`
- `selected repository/review adapter token`: required for PR reads and comments when the repository is private.
- `selected repository owner` and `selected repository name`: infer from `git remote get-url origin` when omitted.
- `pr.labels.enabled`: default `true`.
- `pr.labels.reviewed`: default `codex-reviewed`.
- `pr.labels.needsTests`: default `needs-tests`.
- `pr.labels.needsChanges`: default `needs-changes`.

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
- existing inline review comments and review-thread replies when the configured repository/review provider version exposes them
- relevant local source files for changed code
- changed line count for diff-size classification
- delivery risk and adversarial-review trigger using the shared delivery contract; prefer repo-local helpers when available

If a comment contains `<!-- codex-review-agent:{headSha} -->`, skip posting another review for the same head SHA unless the user explicitly asks for a fresh review. The existing review still remains an implementation feedback source for `dev-flow-implement-ticket`.

Human-authored comments are implementation inputs, not review-agent findings. Preserve them in the review context, avoid duplicating them as Codex findings unless local analysis independently confirms the issue, and report actionable human feedback to the caller so `dev-flow-pr-review-feedback-loop` can create OpenSpec `## PR Review Feedback` tasks, apply fixes, commit, push, rerun AI review, and record ticket provider feedback batch comments.

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
- `SUGGESTION`: optional improvement by severity, still tracked as required PR review feedback in this repository before human-review handoff.

The implementation loop converts every AI finding into OpenSpec PR review feedback tasks. Only `BLOCKER` findings control release-blocking review severity and `needs-changes`; missing or failing tests control `needs-tests`.

Use deterministic diff scope:

- Under 500 changed lines: review the full diff.
- 500 changed lines or more: perform a structured risk-based review and clearly state any areas not reviewed line-by-line.
- Always fully inspect changes touching auth, authorization, persistence, migrations, deployment workflows, secrets, public APIs, tests, and health/deployment contracts.

Run adversarial review mode when requested explicitly or when the shared delivery contract classifies the PR as high risk. In adversarial mode:

1. Read ticket provider/OpenSpec acceptance criteria before judging the diff.
2. For each requirement, ask how the implementation could fail through negative input, stale state, retries, idempotency, authorization, data loss, deployment mismatch, or missing test evidence.
3. Treat spec/code mismatches and unproven high-risk behavior as first-class findings.
4. End the review with verdict `PASS`, `PASS WITH GAPS`, or `FAIL`.

Standard mode may use a compact review summary for low-risk PRs, but it must still inspect required tests and configured quality evidence.

Restrict internet research to official documentation, primary source repositories, release notes, standards, or vendor docs unless those are insufficient for a concrete finding. Do not browse for general style opinions. Limit external research to findings where the source materially changes the conclusion.

Do not leave vague style feedback. Every finding must include the affected file or behavior, why it matters, and the suggested correction.

### 2.5 Ponytail Complexity Pass

After the normal review findings are identified, run `ponytail-review` on the PR diff as a separate complexity-only pass. This pass hunts unnecessary code, hand-rolled standard-library behavior, unneeded dependencies, speculative abstractions, dead flexibility, and same-behavior-smaller rewrites.

Keep `ponytail-review` findings grouped separately as simplification findings. Do not use this pass to replace correctness, test, security, compatibility, adversarial, PR validation, or human-review requirements.

When a `ponytail-review` finding is actionable and scoped to the PR, include it in the PR comment with a stable finding id so `dev-flow-pr-review-feedback-loop` can convert it into OpenSpec PR review feedback. Use the normal review severity labels based on delivery risk: usually `SUGGESTION`, or `WARNING` when the complexity creates meaningful maintainability or validation risk.

### 3. Post The Review

Post one top-level repository PR comment. Include:

- marker `<!-- codex-review-agent:{headSha} -->`
- short review summary
- findings ordered by severity, each with a stable finding id
- separate `ponytail-review` simplification findings, each actionable item with a stable finding id
- test gaps
- diff scope reviewed and any large-diff sampling limits
- review mode `standard` or `adversarial`
- adversarial verdict `PASS`, `PASS WITH GAPS`, or `FAIL` when adversarial mode runs
- sources consulted when applicable

Stable finding ids must be deterministic for the same head SHA and finding target. Use compact ids such as `AI-001`, `AI-002`, or `AI-{shortHash}` and include them in the visible finding heading so `dev-flow-implement-ticket` can compute feedback batch ids and create OpenSpec feedback tasks.

If no issues are found, say so clearly and mention any residual verification gaps.

### 4. Apply Labels

When `pr.labels.enabled` is true:

1. Ensure configured labels exist in repository/review provider. Create missing labels before applying them. Use deterministic colors:
   - `codex-reviewed`: `#5319e7`
   - `needs-tests`: `#fbca04`
   - `needs-changes`: `#d73a4a`
2. Apply the reviewed label after posting a review comment.
3. Apply the needs-tests label if the review identifies missing or failing tests.
4. Apply the needs-changes label if the review identifies actionable defects or blocking issues.
5. Remove the needs-tests label when the current head no longer has missing or failing test findings.
6. Remove the needs-changes label when the current head no longer has actionable defects or blocking issues.
7. If label creation, assignment, or removal fails due to permissions or disabled labels, continue the review and mention the label failure in the PR comment or completion summary.

## Output

Return the reviewed PR number, head SHA, labels applied or removed, validation context inspected, findings summary, and any handoff notes for `dev-flow-implement-ticket`.

## Output Style

Use a code-review stance. Lead with findings and severity. Keep summaries brief. Avoid repeating the full diff. If there are no findings, state that directly.

## Failure Rules

- Missing or placeholder `selected repository/review adapter token`: stop before posting comments or labels.
- PR not found: stop and report the lookup attempted.
- Duplicate review marker for the same head SHA: skip mutation unless explicitly asked to refresh.
- Internet unavailable: continue with local review and note that external validation was skipped.
- Large diffs: follow the threshold rules above and clearly state what was not reviewed line-by-line.
- Required adversarial review without acceptance/spec context: stop or report `FAIL` when required behavior cannot be proven.
