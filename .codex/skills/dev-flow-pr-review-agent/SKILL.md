---
name: dev-flow-pr-review-agent
description: >-
  Review a specific pull request through the selected review adapter and post actionable findings. Use when Codex is
  asked to review a PR, review the PR just created by the implementation workflow, inspect PR diffs, use internet
  research to validate code quality, post review comments, or apply configured review outcome labels.
---

<!-- TIER 3: STAGE-SPECIFIC - PR review workflow skill -->

# repository PR Review Agent

## Overview

Use this skill to review one explicit repository pull request. It is invoked by `dev-flow-implement-ticket` after PR
creation or directly by a user; it is not a recurring polling workflow.

For exact repository/review provider API endpoint guidance, read `the selected repository/review adapter` before making
API calls.

## Shared Context

Before posting review output, follow `.codex/skills/_shared/skill-startup.md`, which reads
`.codex/project-profile.json`, `.codex/skills/_shared/delivery-contract.md`, and
`docs/conventions/context-management.md`, with `docs/conventions/development.md` as the stage-specific doc. Load the
selected review adapter for API endpoints, comment fields, status checks, and
labels.

## Workflow Telemetry

See `.codex/skills/_shared/pipeline-workflow-telemetry.md` for the common workflow telemetry pattern. Use:

- `{workflowStage}` = `dev-flow-pr-review-agent`
- `{agentRole}` = `prReview`

**Unique additions for this skill:**

- **JSONL fallback:** Use `python -m tools.sdd_cli dev-flow append-telemetry -TicketKey {ticketKey}` only as the JSONL
fallback when direct time telemetry is unavailable.
- **Standalone skip:** If the review is explicitly standalone and no ticket key can be safely resolved, report that
workflow telemetry was skipped.

## Configuration

Read `.codex/client-tools.local.json` first. Fall back to `.codex/client-tools.common.json` for defaults only, then
apply environment variable overrides when present.

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

Accept a PR number, PR URL, or the current branch. If the current branch is used, list open PRs for that head branch and
select the matching PR. Review only that PR.

Read `.codex/delivery-context.local.json` when present and verify the PR number, branch, title/body ticket key, and head
SHA when known match the locked `ticketKey`. If the user explicitly requested a
different PR, report the lock mismatch before posting labels or comments.

Fetch:

- PR metadata
- head SHA
- commits
- changed files or diff
- existing PR comments
- existing inline review comments and review-thread replies when the configured repository/review provider version
exposes them
- the latest PR Validation (Gitea Actions) workflow run for the head SHA — run status (success/failure/running/pending)
and per-step results
- relevant local source files for changed code
- changed line count for diff-size classification
- delivery risk and adversarial-review trigger using the shared delivery contract; prefer repo-local helpers when
available

If a comment contains `<!-- codex-review-agent:{headSha} -->`, skip posting another review for the same head SHA unless
the user explicitly asks for a fresh review. The existing review still remains
an implementation feedback source for `dev-flow-implement-ticket`.

Human-authored comments are implementation inputs, not review-agent findings. Preserve them in the review context, avoid
duplicating them as Codex findings unless local analysis independently confirms
the issue, and report actionable human feedback to the caller so `dev-flow-pr-review-feedback-loop` can create OpenSpec
`## PR Review Feedback` tasks, apply fixes, commit, push, rerun AI review, and
record ticket provider feedback batch comments.

### 2. Review The Code

Prioritize findings in this order:

1. Bugs and behavioral regressions.
2. Missing edge-case tests or broken verification.
3. Security, credential, and data-loss risks.
4. API, schema, migration, or compatibility risks.
5. Maintainability suggestions that are clearly worth acting on.

Consult the knowledge base before finalizing findings. Search for known errors, anti-patterns, patterns, and
troubleshooting guides relevant to the changed areas:

```bash
python -m tools.sdd_cli knowledge-search search --query <changed area or symptom terms>
python -m tools.sdd_cli knowledge-search search --list-topics
```

If an existing entry matches a finding or risk, cite it in the review comment instead of duplicating it.

Use internet research when useful. Prefer official docs first; use trusted posts, issue discussions, or release notes
only when official docs are insufficient. Cite sources in the PR comment when
external research materially affects a finding.

Use these severity labels for every finding:

- `BLOCKER`: likely bug, security/data-loss risk, broken required behavior, missing required test, failing gate, or
release-blocking compatibility issue.
- `WARNING`: meaningful risk or maintainability issue that should be considered. WARNINGs do not gate an individual
finding's severity, but like every finding they keep the `codex-reviewed` clean
marker off until resolved.
- `SUGGESTION`: optional improvement by severity, still tracked as required PR review feedback in this repository before
human-review handoff; like every finding, it keeps `codex-reviewed` off until
resolved.

The implementation loop converts every AI finding into OpenSpec PR review feedback tasks. The `codex-reviewed` label is
the **clean marker**: it is applied only when the current head has ZERO findings
of any severity — no `BLOCKER`, `WARNING`, or `SUGGESTION`, no missing or failing tests, no unresolved adversarial `PASS
WITH GAPS`/`FAIL` verdict, no residual verification gaps, and a green (success)
PR Validation run on the current head. Any finding — of any severity, actionable or not — keeps `codex-reviewed`
removed, so the PR stays red on the CI gate until the feedback loop resolves every
finding. `needs-changes` marks actionable defects (`BLOCKER`/`WARNING`/`SUGGESTION`); missing or failing tests mark
`needs-tests`.

Use deterministic diff scope:

- Under 500 changed lines: review the full diff.
- 500 changed lines or more: perform a structured risk-based review and clearly state any areas not reviewed
line-by-line.
- Always fully inspect changes touching auth, authorization, persistence, migrations, deployment workflows, secrets,
public APIs, tests, and health/deployment contracts.

Run adversarial review mode when requested explicitly or when the shared delivery contract classifies the PR as high
risk. In adversarial mode:

1. Read ticket provider/OpenSpec acceptance criteria before judging the diff.
2. For each requirement, ask how the implementation could fail through negative input, stale state, retries,
idempotency, authorization, data loss, deployment mismatch, or missing test evidence.
3. Treat spec/code mismatches and unproven high-risk behavior as first-class findings.
4. End the review with verdict `PASS`, `PASS WITH GAPS`, or `FAIL`.

Standard mode may use a compact review summary for low-risk PRs, but it must still inspect required tests and configured
quality evidence.

Restrict internet research to official documentation, primary source repositories, release notes, standards, or vendor
docs unless those are insufficient for a concrete finding. Do not browse for
general style opinions. Limit external research to findings where the source materially changes the conclusion.

Do not leave vague style feedback. Every finding must include the affected file or behavior, why it matters, and the
suggested correction.

### 2.05 Frontend / Web Review Checkpoints (web PRs)

When the diff touches a web frontend (React/Vue/Angular/other SPA), check these
proven consumer-project failure patterns in addition to the priorities above:

- **Trust boundary first:** any endpoint that echoes user-supplied identifiers
  back must reject malformed input server-side (e.g. id > 64 chars or non-
  `[A-Za-z0-9-]`) *before* echoing — echoing malformed IDs is a `BLOCKER`.
- **`setSearchParams` with an identical value is a no-op** — re-entering the
  same query (e.g. the same tracking id after an error) triggers no effect.
  The component needs a `retryKey` state bumped on same-id submit. Missing
  retry affordance is a `WARNING`.
- **URL/input query sync:** search inputs must stay synced with the `?q=`
  query param (initial read + back/forward). Drift is a `WARNING`.
- **Modal a11y checklist:** a modal/overlay must have a focus trap, focus
  restore on close, scroll lock while open, and an Escape guard that does NOT
  submit mid-flight. Missing any is a `WARNING` (a11y + behavioral).

These patterns are the durable rules from consumer-project E2EPROJECT-38/39;
cite the affected file/behavior per the finding rules below.

### 2.1 PR Validation Gate Check (mandatory)

Read the latest PR Validation (Gitea Actions) workflow run for the current head SHA before finalizing findings. This is
a hard requirement — never post a review without inspecting it.

- A failing step is a `BLOCKER` finding with a stable finding id. Quote the step name and the exact error so
`dev-flow-pr-review-feedback-loop` can fix it and re-check the next run.
- A run that is red, still running/pending, or whose status cannot be determined (missing run, API error) also keeps
`codex-reviewed` off — the PR stays red on the CI gate until the run completes
green.
- A green run plus zero findings is the only combination that lets `codex-reviewed` be applied.

### 2.5 Ponytail Complexity Pass

After the normal review findings are identified, run `ponytail-review` on the PR diff as a separate complexity-only
pass. This pass hunts unnecessary code, hand-rolled standard-library behavior,
unneeded dependencies, speculative abstractions, dead flexibility, and same-behavior-smaller rewrites.

Keep `ponytail-review` findings grouped separately as simplification findings. Do not use this pass to replace
correctness, test, security, compatibility, adversarial, PR validation, or human-review
requirements.

When a `ponytail-review` finding is actionable and scoped to the PR, include it in the PR comment with a stable finding
id so `dev-flow-pr-review-feedback-loop` can convert it into OpenSpec PR review
feedback. Use the normal review severity labels based on delivery risk: usually `SUGGESTION`, or `WARNING` when the
complexity creates meaningful maintainability or validation risk.

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

Stable finding ids must be deterministic for the same head SHA and finding target. Use compact ids such as `AI-001`,
`AI-002`, or `AI-{shortHash}` and include them in the visible finding heading so
`dev-flow-implement-ticket` can compute feedback batch ids and create OpenSpec feedback tasks.

If no issues are found, say so clearly. Residual or unverifiable areas count as gaps — record them as findings so the
clean marker is not applied prematurely.

### 4. Apply Labels

When `pr.labels.enabled` is true:

1. Ensure configured labels exist in repository/review provider. Create missing labels before applying them. Use
deterministic colors:
   - `codex-reviewed`: `#5319e7`
   - `needs-tests`: `#fbca04`
   - `needs-changes`: `#d73a4a`
2. Apply the `codex-reviewed` label ONLY when the current-head review has ZERO findings of any severity (no `BLOCKER`,
`WARNING`, or `SUGGESTION`, no missing/failing tests, no unresolved adversarial
verdict — `PASS WITH GAPS` or `FAIL` keep it off, as do residual verification gaps) AND the current-head PR Validation
run is green (success). A red, pending, or unreadable run keeps it off. It is the
clean/mergeable marker: exactly one `codex-reviewed` label live means the PR has been looped reviewed and fixed until
nothing remains.
3. If ANY finding exists — of any severity, actionable or not — REMOVE the `codex-reviewed` label (or do not apply it).
The PR stays red on the CI `codex-reviewed` gate until the feedback loop
resolves every finding and a re-review confirms a clean head.
4. Apply the needs-tests label if the review identifies missing or failing tests.
5. Apply the needs-changes label if the review identifies actionable defects (`BLOCKER`, `WARNING`, or `SUGGESTION`).
6. Remove the needs-tests label when the current head no longer has missing or failing test findings.
7. Remove the needs-changes label when the current head no longer has actionable findings of any severity.
8. If label creation, assignment, or removal fails due to permissions or disabled labels, continue the review and
mention the label failure in the PR comment or completion summary.

## Output

Return the reviewed PR number, head SHA, labels applied or removed (including whether `codex-reviewed` is present — i.e.
the head is clean), validation context inspected, findings summary, and any
handoff notes for `dev-flow-implement-ticket`.

## Output Style

Use a code-review stance. Lead with findings and severity. Keep summaries brief. Avoid repeating the full diff. If there
are no findings, state that directly.

## Failure Rules

- Missing or placeholder `selected repository/review adapter token`: stop before posting comments or labels.
- PR not found: stop and report the lookup attempted.
- Duplicate review marker for the same head SHA: skip mutation unless explicitly asked to refresh.
- Internet unavailable: continue with local review and note that external validation was skipped.
- Large diffs: follow the threshold rules above and clearly state what was not reviewed line-by-line.
- Required adversarial review without acceptance/spec context: stop or report `FAIL` when required behavior cannot be
proven.
- Findings present on the current head: never apply `codex-reviewed`; report the head as not clean so
`dev-flow-pr-review-feedback-loop` keeps iterating.
- PR Validation run red, pending, or unreadable on the current head: never apply `codex-reviewed`; report each failing
step as a `BLOCKER` finding and the head as not clean.
