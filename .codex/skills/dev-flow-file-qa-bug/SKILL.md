---
name: dev-flow-file-qa-bug
license: MIT
description: >-
  >- Create a linked bug ticket from failed QA evidence, move it through the full bug fix lifecycle (New → Specified →
  In progress), modify the parent ticket's OpenSpec with bug-fix tasks, create a fix/ branch, create PR, deploy to QA
  (after user approval) — the bug flow ends with the QA deployment — close the bug, then return the parent ticket to
  its own QA flow. Use when E2E QA fails with a product defect, a
  committed-test defect, or any QA-identified issue requiring code changes.
---

<!-- TIER 3: STAGE-SPECIFIC - QA bug filing and fix workflow skill -->

# File And Fix QA Bug

## Overview

Use this skill when E2E QA fails against the QA deployment. This skill handles the full bug fix lifecycle:

```text
E2E QA fails → File bug → Move to Specified → Update parent OpenSpec → Commit → Move to In progress → Branch → PR → Merge & deploy to DEV → user approval → deploy to QA → Close bug
```

The **bug flow ends with the QA deployment** (Phase 6). The parent ticket is returned to `In testing` (ID 9) and its
E2E QA re-run continues as the **parent's own flow** (via `dev-ops-deploy-qa` → E2E QA evidence
gate) — it is never part of the bug flow.

**Key differences from feature flow:**

- Bug does NOT create a new OpenSpec change — it modifies the **parent's existing OpenSpec** by appending bug-fix tasks
to its `tasks.md`
- Branch uses `fix/{bugKey}-...` prefix instead of `feat/{prefix}-...`
- PR references both the bug key and the parent ticket key
- Parent ticket stays in its current state (the bug is a child ticket)

## Shared Context

Before filing or linking tickets, follow `.codex/skills/_shared/skill-startup.md`, which reads
`.codex/project-profile.json`, `.codex/skills/_shared/delivery-contract.md`, and
`docs/conventions/context-management.md`, with `docs/conventions/development.md` and `docs/architecture/deployment.md`
as stage-specific docs. Load selected ticket, repository, artifact, deployment,
and E2E adapters as needed.

## Workflow Telemetry

Workflow telemetry is **mandatory** for this stage: before handoff, upsert the stage time entry with the standalone
script (shared pattern `.codex/skills/_shared/pipeline-workflow-telemetry.md`):

```bash
python -m tools.sdd_cli dev-flow telemetry-upsert --ticket-key {ticketKey} \
  --workflow-stage dev-flow-file-qa-bug --agent-role fileQaBug \
  --started-utc {startedUtc} --finished-utc {finishedUtc} --outcome {outcome}
```

The marker `IA generated workflow telemetry: {ticketKey}:dev-flow-file-qa-bug` is written automatically.
If the upsert fails, stop and report before handoff.

## Configuration

Read `.codex/project-profile.json` first. Read `.codex/client-tools.local.json` only for selected adapter runtime values
when a ticket mutation or fix branch is needed.

Bug-specific configuration:

- `fix branch prefix`: default `fix` (configurable via `workflow.bugBranchPrefix` in project-profile)
- `Specified state`: target state after adding acceptance criteria. Default: `Specified`.
  **Fallback:** If the ticket provider rejects `Specified` (unknown state), use `In specification` or `Needs refinement`
  as configured in `project-profile.json → workflow.bugSpecifiedFallback`.
- `In Progress state`: target state after starting work. Default: `In progress` (lowercase p — matches OpenProject
status ID 7).

## Workflow

Run these steps in order. Do not skip any step.

### Phase 1 — File Bug With Evidence

1. Resolve the parent ticket, failed QA run, tested commit, artifact, QA URL, and evidence path or URL from the E2E QA
failure output.
2. Read `.codex/delivery-context.local.json` when present and verify the parent ticket, tested commit, artifact
`release.json.ticketKey`, and evidence path match the locked `ticketKey`. If they do
not, stop before filing a bug against the wrong parent.
3. Confirm the failure is a product defect or committed-test defect, not tooling, missing credentials, missing test
data, unreachable infrastructure, or evidence upload failure.
4. Create or reuse a linked ticket provider bug ticket with:
   - parent ticket key (bug is created as a child of the parent),
   - tested commit and artifact,
   - QA environment and URLs,
   - failed scenario and expected/actual behavior,
   - evidence link or local fallback path,
   - severity and user impact,
   - marker `IA generated QA bug: {parentTicketKey}`.
5. Comment on the parent ticket with the bug link. See `.codex/skills/_shared/pipeline-ticket-comment.md` for the common
comment pattern. Use:
   - Marker: `IA generated QA bug: {parentTicketKey}`
   - Comment body: `**Bug ticket:** {bugUrl}\n**Evidence:** {evidencePath}`
   - Severity: `advisory` (log and continue on failure)

    Leave the parent in its current state (e.g., `Test failed` ID 11 or `In testing` ID 9). The parent does NOT move
    until the bug is fixed and
    E2E QA re-runs successfully.

### Phase 2 — Move Bug To Specified

1. Fetch the bug ticket (just created in step 4) and expand its description.
2. Add a detailed fix plan to the bug description using the IA generated block format:
   - **Root cause** of the failure (from E2E QA evidence)
   - **Fix approach** (what needs to change and where)
   - **Acceptance criteria** for the fix (specific, testable assertions)
   - **Affected files** (list of files that need changes)
   - **Validation** (how to verify the fix — re-run affected tests)
   - **Estimated effort** (hours forecast)
3. Move the bug ticket to the target specification state. Attempt the transition via the ticket provider API. If the API
returns an error indicating the state is unknown or not allowed, retry with the
fallback state from `project-profile.json → workflow.bugSpecifiedFallback`, or use `In specification` as a final
fallback.

   Use marker: `IA generated bug specification: {bugKey}`

### Phase 3 — Update Parent OpenSpec With Bug Tasks

1. Identify the parent ticket's active OpenSpec change. Run:

   ```bash
   openspec list --json
   ```

   Find the change by matching the parent ticket key against each change's **`description` or `metadata.ticketKey`**
   field — not the directory name, which may use a different convention (e.g.,
   `refactor-`, `chore-`).

   **Fallback:** If `openspec list --json` doesn't expose ticketKey in metadata, search the `openspec/changes/`
   directory listing and match by directory name convention (e.g.,
   `{prefix}-{parentKey}-*`).

2. Read the parent's `tasks.md`:

    ```bash
    cat openspec/changes/{parentChangeName}/tasks.md
    ```

3. **Append** bug-fix tasks to the parent's `tasks.md`. Do NOT replace or remove existing tasks. Append a new numbered
section with the bug title and tasks:

    ```markdown
    ## Bug Fix: {bugKey} — {short description}
    
    - [ ] {bugKey}-1: Implement the fix (describe what)
    - [ ] {bugKey}-2: Update existing tests if needed
    - [ ] {bugKey}-3: Verify fix passes E2E QA against QA deployment
    ```

4. Verify the updated `tasks.md` is well-formed (no broken markdown).

### Phase 4 — Start Fix Branch

 1. Move the bug ticket to `In progress` state.
 2. Commit the OpenSpec changes made in Phase 3:

    ```bash
    git add openspec/changes/{parentChangeName}/tasks.md
    git commit -m "{bugKey}: add bug-fix tasks to {parentTicketKey} OpenSpec"
    ```

    This commits the bug tasks to `dev` **before** branching, so the OpenSpec edit is not lost.

 3. Verify the working tree is clean: `git status --porcelain` must show no output.
 4. Run `git pull --ff-only` (already on `dev` from Step 14's commit).
 5. Create a fix branch:

    ```bash
    git checkout -b fix/{bugKeySlug}-{short-description}
    ```

    Example: `fix/e2eproject-38-no-validate-forgot-password`
 6. Push the branch to the remote with upstream tracking:

    ```bash
    git push -u {remoteName} fix/{bugKeySlug}-{short-description}
    ```

 7. Add a comment on the bug ticket with the branch name, base branch, and remote. See
 `.codex/skills/_shared/pipeline-ticket-comment.md` for the common comment pattern. Use:

- Marker: `IA generated bug branch: fix/{bugKeySlug}-{short-description}`
- Comment body: `**Base branch:** dev\n**Remote:** {remoteName}`
- Severity: `advisory` (log and continue on failure)

### Phase 4.5 — ⚠️ MANDATORY: Implement Fix With Tests

**Knowledge consult before fixing.** Before writing the fix, consult the knowledge base for known errors and fixes
relevant to the bug symptom:

```bash
python -m tools.sdd_cli knowledge-search search --query <bug symptom terms>
python -m tools.sdd_cli knowledge-search search --list-topics
```

If an existing `knowledge/errors/<error>.md` or `knowledge/fixes/<fix>.md` entry matches the symptom, apply it and cite
it in the bug comment and PR. If the bug fix is a validated reusable fix, record
it via `knowledge/README.md` and the `docs-knowledge-maintenance` skill at handoff. Record `Knowledge consulted:
<files>` or `Knowledge consulted: none` in the bug comment and PR handoff.

See `.codex/skills/_shared/pipeline-tdd-cycle.md` for the common TDD test-first pattern. Bug-flow-specific details:

- **AC source:** the bug ticket description (the IA generated block set in Phase 2 step 7). These are the contract for
the fix.
- **Task source:** the parent's `tasks.md` for any additional bug-fix tasks (appended in Phase 3).
- **Test levels:** unit tests (per component), integration tests (per endpoint/feature), architecture tests (update
existing project-wide file if structure changes).
- **Quality gates:** the same hard gates as the feature flow apply to the bug fix:
  - **Lefthook pre-push stack tests + coverage (`python -m tools.sdd_cli stack-tests`)** must pass before pushing. The
  hook runs unit, integration, and architecture tests per
  `.codex/skills/_shared/test-requirements.md`, driven by `stack.testFrameworks` from
  `.codex/project-profile.local.json`, then the **coverage gate** with the configurable threshold
  `coverage.minimumPercent` (default `80`) — stack-configured: install + test + coverage each mapped framework; no
  stack: clean skip. Do not bypass the hook with `--no-verify` unless the user
  explicitly requests it.
  - **Coverage gate:** coverage must meet `coverage.minimumPercent` (default `80`) from `.codex/quality.local.json`
  before PR creation. Below threshold: HARD STOP (authority level 5) — add/update
  tests and re-run until met.
  - **Full local CI loop:** run the checks in `.gitea/workflows/pr-validation.yml` (via `sdd-e2e-ci:local` when Docker
  is available) and fix all errors before creating the PR.

Commit on the fix branch:

```bash
git add -A
git commit -m "{bugKey}: implement fix with tests"
git push
```

### Phase 5 — Create Pull Request

 1. Create a pull request from the fix branch to `dev` with:
    - Title: `{bugKey}: {short description} (parent: {parentTicketKey})`
    - Description including:
      - The bug ticket link
      - The parent ticket link
      - A summary of the fix
      - Acceptance-to-test map (ACs → unit/integration/architecture tests)
      - TDD RED/GREEN evidence
      - Link to E2E QA evidence
      - Any affected files
    - Labels: `bug`, `qa-verified` if applicable

 2. **Add a comment on the bug ticket with the PR link — verify and retry if missing.** See
 `.codex/skills/_shared/pipeline-ticket-comment.md` for the common comment pattern. Use:

- Marker: `IA generated bug PR: {prUrl}`
- Comment body: `**Branch:** fix/{bugKeySlug}-{short-description}\n**Parent ticket:** {parentTicketKey}`
- Severity: `blocking` (stop if comment cannot be created — the PR link is required for traceability)

 1. **Run AI review on the PR.** Load and follow the `dev-flow-pr-review-agent` skill to review the PR diffs, post
 findings, and apply labels (e.g., `codex-reviewed`, `needs-changes`, `needs-tests`).

    This step runs immediately after PR creation so the developer has AI review feedback before merging. If the AI
    review finds blocking issues (`BLOCKER` severity), the implementation phase should
    address them before merging.

 2. **Add reviewers to the PR** after the AI review completes. See `.codex/skills/_shared/pipeline-review-handoff.md`
 for the common reviewer request pattern.

### Phase 6 — Merge & Deploy To QA (User-Approved)

After the implementer completes the fix on the branch and merges the PR to `dev`, the AI automatically handles
deployment, bug closure, and return to the parent ticket's QA flow.

 1. Confirm the PR has been merged to `dev`. Check:
    - Gitea API: `GET /api/v1/repos/{owner}/{repo}/pulls/{prNumber}` — `merged_at` must not be null
    - If the PR is still open, report the PR URL and stop — wait for the implementer to merge

 2. Move the bug ticket to `Developed` (ID 8) — code is merged:

    ```bash
    PATCH /api/v3/work_packages/{bugId}
    {"lockVersion": {n}, "_links": {"status": {"href": "/api/v3/statuses/8"}}}
    ```

 3. Update `.codex/delivery-context.local.json` to switch context to the bug ticket for deployment tracking:

    ```json
    {
      "ticketKey": "{bugKey}",
      "parentTicketKey": "{parentTicketKey}",
      "branch": "dev",
      "openspecChange": "{parentChangeName}",
      "prNumber": {prNumber},
      "artifactCommitSha": "{mergeCommitSha}"
    }
    ```

 4. Invoke `dev-ops-post-merge-deploy` with the resolved PR number and bug ticket key. This skill:
    - Validates the merged PR is clean (no `needs-changes` or `needs-tests` labels)
    - Dispatches the CI pipeline on `dev` (deploys DEV only)
    - Waits for Nexus artifacts to appear for the merge commit
    - Delegates to `dev-ops-deploy-qa`, which verifies DEV, asks the user for approval, then dispatches the QA
      deployment (no auto-promote — QA deploys only after user approval)

 5. Verify the QA deployment succeeded. **This is the end of the bug flow's deploy phase** — the bug does not run E2E
    or promote to PROD itself:
    - Check for `IA generated QA deployment: {mergeCommitSha}` marker in the bug ticket comments
    - Confirm QA frontend URL returns HTTP 200
    - Confirm QA backend `/health` returns `{"status":"ok"}`
    - If QA deployment fails, follow the failure rules and stop — do not close the bug

### Phase 7 — Close Bug & Return To Parent QA

 1. Mark all bug-fix tasks as completed in the parent's OpenSpec `tasks.md`. Change every unchecked `- [ ]` to `- [x]`
 for the bug's section:

    ```bash
    sed -i "/^## Bug Fix: {bugKey}/,/^## /{s/- \[ \]/- [x]/}" openspec/changes/{parentChangeName}/tasks.md
    ```

    This marks the bug-fix tasks as done. Other sections of `tasks.md` are not affected.

 2. Commit and push the `tasks.md` update:

    ```bash
    git add openspec/changes/{parentChangeName}/tasks.md
    git commit -m "{bugKey}: mark bug-fix tasks as completed"
    git push
    ```

 3. Delete the fix branch (local and remote) — it is no longer needed. This is best-effort cleanup since
 `dev-ops-post-merge-deploy` (Phase 6 step 27) may have already deleted it:

    ```bash
    BRANCH="fix/{bugKeySlug}-{short-description}"
    # Delete remote first (safer — local can be cleaned up later)
    git push "{remoteName}" --delete "$BRANCH" 2>/dev/null || \
      echo "Remote branch '$BRANCH' already deleted or not found"
    # Delete local branch if it exists
    git branch -d "$BRANCH" 2>/dev/null || \
      echo "Local branch '$BRANCH' not found or not fully merged"
    echo "Branch '$BRANCH' cleanup complete"
    ```

 4. Add a comment on the bug ticket documenting the closure, then move it to `Closed` (ID 12). See
 `.codex/skills/_shared/pipeline-ticket-comment.md` for the common comment pattern. Use:

- Marker: `IA generated bug closed: {bugKey}`
- Comment body: `**Parent ticket:** {parentTicketKey}\n**Fix commit:** {mergeCommitSha}\n**QA deployed:**
{qaUrl}\n\nBug-fix tasks marked completed, fix branch deleted, deployment verified.`
- Severity: `advisory` (retry once, then continue)

  - **Move status:**

      ```bash
      PATCH /api/v3/work_packages/{bugId}
      {"lockVersion": {n}, "_links": {"status": {"href": "/api/v3/statuses/12"}}}
      ```

 1. Update `.codex/delivery-context.local.json` to point back to the **parent ticket**:

    ```json
    {
      "ticketKey": "{parentTicketKey}",
      "branch": "dev",
      "openspecChange": "{parentChangeName}",
      "artifactCommitSha": "{mergeCommitSha}",
      "evidencePath": "QA URL: {qaUrl}"
    }
    ```

 1. Move the parent ticket `{parentTicketKey}` from `Test failed` (ID 11) back to `In testing` (ID 9) — the bug is
 fixed, deployed, and the parent can be re-tested:

    ```bash
    PATCH /api/v3/work_packages/{parentId}
    {"lockVersion": {n}, "_links": {"status": {"href": "/api/v3/statuses/9"}}}
    ```

 1. Hand the parent back to its own QA flow. The **bug flow ends with the QA deployment** — the bug does not run E2E
    or PROD itself:
    - The parent is already back in `In testing` (ID 9) above
    - The parent's E2E QA evidence gate runs as part of the parent's own flow (`dev-ops-deploy-qa` →
      `delivery-contract-qa.md`), with the ticket in `In testing`, over QA only
    - If that E2E QA passes, the parent proceeds to PROD promotion per `dev-ops-deploy-prod`
    - The bug is already closed — it does not block the parent

### Non-Code Defects

If the defect is only data, environment, or unclear requirements (not a code change):

1. Do NOT modify OpenSpec.
2. Do NOT create a branch.
3. Comment on the bug ticket explaining why no code change is needed.
4. Report the non-code owner (e.g., operations, product owner).
5. Do not move the bug to `In Progress`.

## OpenSpec Policy

Bugs **modify the parent's existing OpenSpec** — they do NOT create a new OpenSpec change. The bug-fix tasks are
appended to the parent's `tasks.md` as a new section. This keeps all work for a feature
(including bug fixes found during E2E QA) in one place.

The parent's OpenSpec is archived only when the parent ticket itself moves to Done. Bug tasks remain in the parent's
tasks.md as historical record even after the bug is fixed.

Skip OpenSpec modification only when:

- the bug is explicitly marked `no-openspec` or `ops-only`,
- the user explicitly requests no OpenSpec modification,
- the parent ticket has no active OpenSpec change (unusual for QA-discovered bugs).

## Output

Report the parent ticket, bug ticket (with link), E2E QA evidence path, bug specification state (with fallback if used),
parent OpenSpec change updated with bug tasks, fix branch name and remote with
initial commit, PR URL, AI review result (passed / blocking findings with ids), merge commit SHA, deployment status (DEV
✓ / QA ✓), bug-closure status (tasks marked done, branch deleted, ticket moved
to Closed), parent ticket returned to In testing, and handoff to E2E QA for the parent.

For non-code defects, report the parent ticket, evidence path, and required non-code owner and stop (no branch, no
deploy, no close).

## Failure Rules

- Missing parent ticket or QA evidence: stop and ask for the missing identifier.
- Ticket context lock mismatch: stop before filing or linking a bug.
- Unsafe evidence contains secrets: redact or discard unsafe evidence before commenting.
- Existing linked bug with the same marker and tested commit: reuse it instead of creating a duplicate.
- ticket-provider mutation fails: do not create branches or OpenSpec changes until the bug relationship is recorded.
- Dirty working tree: stop before branch creation.
- Parent ticket has no active OpenSpec change: report this as an anomaly but continue (create branch without OpenSpec
update).
- openspec CLI unavailable: report the blocker but continue with branch creation (skip OpenSpec update).
- AI review fails to run (network error, missing token, skill unavailable): report the blocker but continue — AI review
is advisory for the implementer, not a hard gate. If it ran and found `BLOCKER`
findings, document them in the handoff output.
- Lefthook pre-push stack tests fail or an unmapped framework is configured: stop before pushing — fix the tests or
framework mapping and re-run `python -m tools.sdd_cli stack-tests` until it passes.
Do not bypass the hook with `--no-verify` unless the user explicitly requests it. When no stack is configured the hook
skips cleanly (expected template state).
- Coverage below `coverage.minimumPercent` (default `80`): HARD STOP (authority level 5) before PR creation — add or
update tests and re-run coverage until the threshold is met.
- PR not merged before Phase 6: stop and report the PR URL — do not deploy unmerged changes.
- QA deployment fails (Phase 6 step 5): stop and report deployment failure — do not close the bug or return the parent
to QA.
- Parent ticket is not in `Test failed` when moving back to `In testing`: report the current state but continue — the
parent may already be in a valid retest state.
