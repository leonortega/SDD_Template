# PR Lifecycle (Shared 7-Step Pattern)

Every pull request in this template — feature ticket, bug fix, hotfix, or release
— runs the **same 7-step PR lifecycle**. The sequence never changes; only the PR
body and the handoff context differ per flow. This document is the readable map
of that pattern; the authoritative mechanics live in
`.agents/skills/_shared/pipeline-pr-lifecycle.md` (referenced by the flow skills
`dev-flow-implement-ticket` §10–11.5, `dev-flow-file-qa-bug`, `dev-ops-hotfix-prod`,
and `dev-ops-deploy-prod`).

## The 7 Steps

```text
1. Create / reuse the PR (PR body + ticket comment + state move)
2. Request human reviewers (immediately at creation — HARD GATE)
3. Run the AI review (findings + labels, agent-reviewed clean marker)
4. PR review feedback loop (OpenSpec tasks, fixes, re-review)
5. CI validation check and fix (pr-validation.yml green on the current head)
6. Re-verify human reviewers after the AI review (idempotent — HARD GATE)
7. Merge (human) + post-merge handoff (approval is the automated agent-reviewed gate; merges are human-only — HARD GATE)
```

| # | Step | Owner / tool | Key contract |
|---|------|--------------|--------------|
| 1 | Create / reuse PR | Caller flow (e.g. `dev-flow-implement-ticket` §10) | PR body (ticket id, OpenSpec change, acceptance-to-test map, TDD RED/GREEN evidence, coverage result, quality gates, risk, reviewers requested); ticket comment `IA generated PR: {prUrl}`; move ticket to `Developed` (ID 8) |
| 2 | Request reviewers | `python -m tools.sdd_cli gitea request-reviewers --pr {n}` | Immediately after creation, never deferred; unprovisioned lab config = BLOCKER; resolve order `gitea.reviewers` → `pr.reviewers` (`"all"` → collaborators) → `gitea.provisioning.users`; excludes PR author |
| 3 | AI review | `dev-flow-pr-review-agent` | Findings `BLOCKER`/`WARNING`/`SUGGESTION` with stable ids (`AI-001`…); marker `<!-- agent-review:{headSha} -->`; labels `agent-reviewed` (only zero findings + green CI), `needs-tests`, `needs-changes`; adversarial mode on high risk; ponytail complexity pass; mandatory PR Validation gate check |
| 4 | Feedback loop | `dev-flow-pr-review-feedback-loop` | Classify feedback (actionable/stale/ambiguous); one OpenSpec `## PR Review Feedback` task per item; markers `IA generated PR feedback detected/fixes: {headSha}:{batchId}`; remove `agent-reviewed` while feedback open; fix → validate → commit → push → re-review |
| 5 | CI validation | `.gitea/workflows/pr-validation.yml` | Continuous gate (checked in Steps 3–5); gitleaks, semgrep, trivy, checkov, JSON, kustomize overlays, `agent-reviewed` label gate; every failing step is a `BLOCKER` finding until fixed |
| 6 | Re-verify reviewers | `python -m tools.sdd_cli gitea request-reviewers --pr {n}` | Idempotent re-run after AI review; reviewers verified, missing ones re-requested |
| 7 | Merge (human) + handoff | Human (agent never merges; approval is the automated `agent-reviewed` gate) | Merge requires `agent-reviewed` present (automated approval: zero findings + green CI), `needs-tests`/`needs-changes` absent, ticket in `Developed`, handoff comment `IA generated handoff: {ticketKey}`; post-merge continues via `dev-ops-post-merge-deploy` |

## HARD GATEs (authority level 5)

- **Reviewers requested at PR creation** — never deferred until after the AI review;
  human review runs in parallel.
- **Unprovisioned lab config is a BLOCKER** — placeholder `apiToken`/`owner`/`repo`
  in `client-tools.local.json` stops the flow until `setup-lab` runs.
- **Reviewers re-verified after the AI review** — idempotent `request-reviewers`
  re-run so the merge gate never silently misses a reviewer.
- **Never use human users to approve a PR** — the automated approval is
  `agent-reviewed` + green PR Validation; the agent never submits an approval
  review and never requests/waits for a human approval. Merges are human-only:
  the agent never merges (provisioned lab accounts included).

## Flow Coverage

The same lifecycle is consumed by every flow that opens a PR:

| Flow | Where it consumes the lifecycle |
|------|---------------------------------|
| Feature ticket | `dev-flow-implement-ticket` §10–11.5 (full 7 steps) |
| QA bug fix | `dev-flow-file-qa-bug` (PR phase: full shared lifecycle; steps 2/3/6 called out explicitly) |
| PROD hotfix | `dev-ops-hotfix-prod` (delegates to implement-ticket) |
| PROD release | `dev-ops-deploy-prod` — **Step 1 only** (see below) |

## PROD Release-PR Variant (Step 1 only)

A release-blocking PR (`release/vX.Y.Z → main`) promotes an already QA-approved,
code-reviewed artifact, so the full review/feedback loop does not apply:

1. Open the PR `release/vX.Y.Z → main` with the release body.
2. Apply the `agent-reviewed` label directly (the artifact is already clean — the
   caller's responsibility, not the review agent's). If the repository requires
   reviewers and they are configured, run the Step 2 command.
3. The `agent-reviewed` label is the approval — no human approval step
   (branch-protection approval requirements, if configured, are enforced by
   Gitea, never requested or orchestrated by the agent). The human merges.

No AI review, feedback loop, or CI fix loop runs for this PR.

## Related Files

- `.agents/skills/_shared/pipeline-pr-lifecycle.md` — authoritative lifecycle
  (Steps 1–7 + PROD variant)
- `.agents/skills/_shared/pipeline-review-handoff.md` — detailed reviewer request
  pattern (Steps 2/6 mechanics)
- `.agents/skills/dev-flow-pr-review-agent/SKILL.md` — the AI review (Step 3)
- `.agents/skills/dev-flow-pr-review-feedback-loop/SKILL.md` — the feedback loop
  (Step 4)
- `.gitea/workflows/pr-validation.yml` — the CI gate (Step 5)
- `implementation-deploy-flows.md` — the linear ticket → PROD flow (Stage 5 = PR
  Review Agent, Stage 6 = PR Review Feedback Loop)
