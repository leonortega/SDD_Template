<!-- TIER 3: STAGE-SPECIFIC - Review stage (PR review, feedback loop) -->
# Delivery Contract — Review (PR review, feedback loop)

Stage-specific rules for PR review, adversarial review, review feedback loop, labels, and handoff. Read in addition to `delivery-contract-core.md`.

---

## Ponytail Implementation And Review

When adding or changing project code, implementation agents must apply `ponytail full`: use the smallest working change, prefer standard library and native framework features, avoid speculative abstractions or dependencies, and keep tests focused on changed behavior.

`ponytail-review` runs during PR review as an additive complexity pass. It complements normal correctness, test, security, compatibility, and adversarial review; it does not replace the review-agent pass, configured human reviewers, PR validation, or any label rule.

Actionable `ponytail-review` findings are AI review findings and feed the same `dev-flow-pr-review-feedback-loop` as other current-head AI findings.

## Adversarial Review

`dev-flow-pr-review-agent` must run an adversarial pass when requested explicitly or when risk is `high`, including auth, authorization, persistence, migrations, deployment workflows, secrets, public APIs, `/health`, release manifests, rollback/hotfix, or large diffs. The pass reads OpenProject/OpenSpec acceptance criteria first, then tries to disprove implementation compliance through negative paths, idempotency, security, data-loss, deployment, and missing-test scenarios.

Adversarial review output must include one verdict:
- `PASS`: no blockers or meaningful gaps.
- `PASS WITH GAPS`: no blockers, but warnings or tracked gaps remain.
- `FAIL`: blocker, missing proof for required behavior, or high-risk unresolved issue.

Adversarial findings feed the same `dev-flow-pr-review-feedback-loop` as normal AI review findings.

## PR Reviewer Handoff

Ticket implementation handoff must request the configured human reviewers before moving the OpenProject work package to review. When `pr.reviewers` is `"all"`, resolve reviewers from current Gitea collaborators and exclude the PR author plus the authenticated automation user. Gitea collaborator responses must be normalized before filtering: treat both a JSON array and a single collaborator object as a candidate list, and resolve each username from `login` first, then `username`.

Do not treat the Codex review-agent comment, `codex-reviewed` label, or passing PR validation as a substitute for human reviewer assignment. If no eligible reviewers can be resolved, or Gitea rejects reviewer assignment, keep the PR open but document the reviewer gap in the PR body, OpenProject handoff comment, and final summary.

## PR Labels And Review Severity

Default labels:
- Reviewed: `codex-reviewed`
- Missing tests: `needs-tests`
- Blocking changes: `needs-changes`

Review findings must use:
- `BLOCKER`: must be fixed before handoff/promotion.
- `WARNING`: meaningful non-blocking risk.
- `SUGGESTION`: optional improvement.

Severity describes risk and PR label behavior. In this repository, every AI review finding is still tracked as required PR review feedback before human-review handoff, including `WARNING` and `SUGGESTION`.

## PR Review Feedback

PR review has two reconnectable loops:
1. AI review runs immediately after PR creation. The PR is not ready for human review until the current head has a review-agent comment, AI findings have been converted into OpenSpec feedback tasks, all feedback tasks are complete, relevant validation has passed, and current-head `needs-tests` / `needs-changes` labels are clean.
2. Human review happens later. The automatic workflow reconnects only when the operator manually resumes the ticket.

Feedback batches are identified by source ids, not only by head SHA. Compute `feedbackBatchId` as a deterministic short id from the sorted source ids in the batch.

When actionable AI or human feedback is found:
- Add or update a `## PR Review Feedback` section in the active OpenSpec `tasks.md`.
- Add one task for each feedback item. Each task must record source type, source id or link, head SHA, severity, and the requested change.
- Add a OpenProject work package comment with marker `IA generated PR feedback detected: {headSha}:{feedbackBatchId}` before applying fixes.
- Apply the requested code, test, documentation, or workflow change when it is clear and scoped to the ticket.
- Run the relevant quality checks for the changed files. Commit and push.
- Mark the OpenSpec feedback tasks complete only after the code and validation are complete.
- Add a OpenProject work package comment with marker `IA generated PR feedback fixes: {headSha}:{feedbackBatchId}`.
- Rerun the AI review loop on the new head before returning to human review.

AI review findings must have stable finding ids in the PR review comment. Human-authored Gitea PR feedback includes top-level PR comments and inline code review comments.

Do not treat generated agent comments, duplicate comments already addressed by a newer head SHA or completed feedback batch, resolved/outdated inline comments, or purely informational comments as required code changes.

Before PR handoff, merge, or QA promotion, stop when any current PR feedback batch is unresolved, any OpenSpec `## PR Review Feedback` task is incomplete, or the merged PR still has `needs-tests` or `needs-changes`.
