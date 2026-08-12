<!-- TIER 3: STAGE-SPECIFIC - Ticket stage (start, implement, propose, explore) -->

# Delivery Contract — Ticket (start, implement, propose, explore)

Stage-specific rules for ticket creation, implementation planning, and commit workflow. Read in addition to
`delivery-contract-core.md`.

---

## Status Mapping

The delivery workflow uses **OpenProject status names directly** — no external labels
or aliases. Only the statuses in the mapping table below are part of the flow chain; tickets never move to any other
OpenProject status:

| OpenProject Status | ID | Description |
|---|---|---|
| New | 1 | Bug starting point — filed from E2E QA failure |
| Specified | 3 | Feature starting point — acceptance criteria defined |
| In progress | 7 | Implementation active on the branch |
| Developed | 8 | Code complete, PR exists for review |
| In testing | 9 | Artifact deployed to QA, awaiting E2E validation |
| Closed | 12 | All tests passed — ticket is done |

## States And Flow

Real OpenProject statuses from the provisioned instance (verified via `GET /api/v3/statuses`). Only the statuses
in the Status Mapping table are flow states; the rest exist in OpenProject but the delivery flow never moves tickets
into them (e.g., `In specification` ID 2 is used only as the `bugSpecifiedFallback` API fallback):

- **New** (ID 1, default): bug starting point — filed from E2E QA failure. Not used for feature tickets.
- **In specification** (ID 2): ticket is being refined with acceptance criteria.
- **Specified** (ID 3): feature starting point — acceptance criteria, fix plan, and effort forecast are defined.
  **Fallback:** If the provider API rejects `Specified` as unknown, use `In specification` or `Needs refinement` as
  configured in `project-profile.json → workflow.bugSpecifiedFallback`.
- **Confirmed** (ID 4): bug is reproduced and confirmed as valid.
- **To be scheduled** (ID 5): ticket is queued for a future sprint.
- **Scheduled** (ID 6): ticket is assigned to a sprint.
- **In progress** (ID 7): implementation is active on the branch.
- **Developed** (ID 8): code is complete and PR exists for review.
- **In testing** (ID 9): artifact is deployed to QA and awaits E2E validation. The ticket stays here while E2E QA
  runs; a QA failure does **not** change its state — it files a child bug (see `dev-flow-file-qa-bug`) and, once the
  fix is deployed, E2E re-runs with the ticket still in `In testing`.
- **Closed** (ID 12, isClosed): ticket is done — all tests passed. Not eligible for further work.
- **On hold** (ID 13): work is paused temporarily.
- **Rejected** (ID 14, isClosed): ticket is declined.

**Standard flow:** `Specified → In progress → Developed → In testing → Closed`

**Feature flow:** `Specified → In progress → Developed → In testing → Closed`

**Bug fix flow:** `New → Specified → In progress → Developed → In testing → Closed`

**Bug revert flow:** `In testing → (E2E FAIL → file child bug) → … → Closed` — the
child bug runs the bug fix flow; the parent stays in `In testing` throughout; only
the child bug moves through the chain.

Delivery flow:

```text
OpenProject → branch/OpenSpec → implementation → PR → merge to dev → DEV deploy → QA deploy → E2E QA → PROD → rollback/hotfix when needed
```

Before starting the first ticket, and before any ticket is moved into implementation when stack context is missing,
verify that the project tool set and tech stack are defined in the merged project
profile, that every selected adapter path exists, and that docs/OpenSpec context points to the profile instead of
duplicating canonical provider facts. The ticket-start path must run or inspect the
configured guidance audit and stop before repository, ticket, or OpenSpec mutation when the audit reports
`stack-context.*` drift or missing profile/adapter files. Route the operator to
`configure-dev-environment` to define the project profile and recommendation catalog first.

Push-triggered environment deployment is allowed only for ticket-named work that changes configured application or test
paths. The commit message must start with the configured ticket key format, or
be a repository-adapter merge commit whose PR title starts with that ticket key format. Non-code changes outside
configured deploy-trigger paths do not run automatic CI/deployment work.

Before committing, classify the change as ticketed work, an OpenSpec maintenance change, or direct SDD repository
maintenance. Ticketed work uses the configured ticket prefix such as `E2EPROJECT-123:
...`; OpenSpec maintenance uses the OpenSpec id prefix; direct SDD maintenance must use `[SDD]`, for example `[SDD]
Improve project guidance acquisition flow`. Do this before invoking `git commit` so
the `require-ticket` hook does not fail on a preventable prefix issue.

PROD promotion is explicit and release-centric. Do not promote to PROD only because QA passed unless the user asks for
PROD promotion or a ticket-named `src/**` or `test/**` merge to `main` triggers
the PROD-only workflow.

## Ticket Refinement Gate

Before `dev-flow-start-ticket` mutates Git, OpenProject status, the delivery lock, or OpenSpec, classify the ticket as:

- `ready`: includes a user-visible goal, concrete acceptance criteria, and validation expectations.
- `refinable`: intent is clear enough to proceed after adding Scrum-ready planning details to the managed OpenProject
block.
- `blocked`: product or technical intent is too vague to safely generate acceptance criteria.

For `refinable`, update only the generated OpenProject block and continue. For `blocked`, stop before branch,
OpenProject status, delivery lock, or OpenSpec mutation and report the missing intent.

## Review Workload Forecast

OpenSpec `tasks.md` for ticketed implementation must include a compact `Review Workload Forecast` near the top:

```text
Estimated changed lines: <rough range or number>
Estimated total hours: <hours as number>
400-line budget risk: Low|Medium|High
Chained PRs recommended: Yes|No
Decision needed before apply: Yes|No
Delivery strategy: ask-on-risk|auto-chain|single-pr|exception-ok
Suggested work units: <single PR or PR 1 -> PR 2 -> PR 3>
```

If the forecast says `400-line budget risk: High`, `Chained PRs recommended: Yes`, or `Decision needed before apply:
Yes`, implementation must not start until the prompt, OpenProject/OpenSpec
artifacts, or user decision records one of: split/chained work-unit plan, `size:exception`, or `exception-ok`.

## Ticket Commit Strategy

Default ticket implementation uses one PR with multiple ticket-prefixed commits. Chained PRs remain reserved for
oversized or high-risk work. Commit after each completed workflow step when the step
produced tracked changes, then start the next step from a clean working tree.

Stable commit checkpoints include: OpenSpec task, spec, or design refinement; implementation changes; tests or reusable
QA regression coverage; documentation, context, memory, or workflow policy
updates; PR review feedback fixes; tooling or configuration fixes scoped to the active ticket.

For each commit checkpoint: finish changes, review `git status` and diff, run the smallest relevant validation, stage
only related files, commit with a message that starts with the OpenProject work
package key or OpenSpec id, continue only after the working tree is clean.

## Installed Skill Runtime Index

Project guidance remains the broad catalog for skills, tools, references, practices, standards, MCPs, and plugins. The
installed-skill runtime index is only a derived cache of actual
`.agents/skills/*/SKILL.md` files and exact paths for delegation.

Rules:

- The index must be ignored local state and secret-free.
- Cache by schema version plus skill path, mtime, and size so unchanged skills are cheap to reuse.
- `SKILL.md` remains the source of truth; the index does not summarize, rewrite, acquire, accept, dismiss, or replace
project guidance.
- Coordinator skills may use the index to pass exact skill paths to child agents, while `project-guidance-*` continues
to own broad guidance discovery, acquisition, and mapping.

## Ticket Context Lock

Normal automatic delivery must stay locked to one OpenProject work package. Use ignored
`.template/delivery-context.local.json` as the local active delivery context lock. Never commit it. Do not delete
the lock merely because E2E QA moved a ticket to `Done`; the lock can still carry QA-approved artifact, RC, and release
context needed for explicit PROD promotion.

Baseline shape:

```json
{
  "ticketKey": "E2EPROJECT-123",
  "branch": "feat/e2eproject-123-example",
  "openspecChange": "feat-e2eproject-123-example",
  "prNumber": 12,
  "artifactCommitSha": "abc123",
  "sourceRcVersion": "v1.2.3-rc.1",
  "finalReleaseVersion": "v1.2.3"
}
```

Rules:

- `dev-flow-continue-implementation` resolves or creates the lock before delegating.
- `dev-flow-start-ticket` creates or updates the lock after the selected ticket, branch, and OpenSpec decision are
known. If an existing lock names a different ticket that is `Closed`, replace the
lock. If the locked ticket is active, missing, ambiguous, or cannot be verified, stop and report the lock blocker.
- Child skills must verify their resolved ticket, branch, PR, artifact `release.json.ticketKey`, QA evidence path, RC
tag, and PROD release lineage match the locked `ticketKey` before mutating or
promoting.
- If the lock exists and a child skill resolves a different ticket key, stop and report the mismatch.
- `dev-flow-pipeline-status` may read and report the lock plus mismatches. `dev-ops-rollback-prod` may operate by
incident/release target, but must report when it differs from the active lock.
