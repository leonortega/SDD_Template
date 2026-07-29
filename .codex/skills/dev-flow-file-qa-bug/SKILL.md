---
name: dev-flow-file-qa-bug
description: Create a linked bug ticket from failed QA evidence, move it through the bug fix lifecycle (New → Specified → In progress), modify the parent ticket's OpenSpec with bug-fix tasks, create a fix/ branch, and hand off to implementation. Use when E2E QA fails with a product defect, a committed-test defect, or any QA-identified issue requiring code changes.
---

<!-- TIER 3: STAGE-SPECIFIC - QA bug filing and fix workflow skill -->

# File And Fix QA Bug

## Overview

Use this skill when E2E QA fails against the QA deployment. This skill handles the full bug fix lifecycle:

```text
E2E QA fails → File bug → Move to Specified → Update parent OpenSpec → Commit → Move to In progress → Branch → PR → Hand off to implementation
```

**Key differences from feature flow:**
- Bug does NOT create a new OpenSpec change — it modifies the **parent's existing OpenSpec** by appending bug-fix tasks to its `tasks.md`
- Branch uses `fix/{bugKey}-...` prefix instead of `feat/{prefix}-...`
- PR references both the bug key and the parent ticket key
- Parent ticket stays in its current state (the bug is a child ticket)

## Shared Context

Before filing or linking tickets, follow `.codex/skills/_shared/skill-startup.md`, which reads `.codex/project-profile.json`, `.codex/skills/_shared/provider-adapter-contract.md`, `.codex/skills/_shared/delivery-contract.md`, and `docs/context-management.md`, with `docs/development.md` and `docs/deployment.md` as stage-specific docs. Load selected ticket, repository, artifact, deployment, and E2E adapters as needed.

## Configuration

Read `.codex/project-profile.json` first. Read `.codex/client-tools.local.json` only for selected adapter runtime values when a ticket mutation or fix branch is needed.

Bug-specific configuration:
- `fix branch prefix`: default `fix` (configurable via `workflow.bugBranchPrefix` in project-profile)
- `Specified state`: target state after adding acceptance criteria. Default: `Specified`.
  **Fallback:** If the ticket provider rejects `Specified` (unknown state), use `In specification` or `Needs refinement` as configured in `project-profile.json → workflow.bugSpecifiedFallback`.
- `In Progress state`: target state after starting work. Default: `In progress` (lowercase p — matches OpenProject status ID 7).

## Workflow

Run these steps in order. Do not skip any step.

### Phase 1 — File Bug With Evidence

1. Resolve the parent ticket, failed QA run, tested commit, artifact, QA URL, and evidence path or URL from the E2E QA failure output.
2. Read `.codex/delivery-context.local.json` when present and verify the parent ticket, tested commit, artifact `release.json.ticketKey`, and evidence path match the locked `ticketKey`. If they do not, stop before filing a bug against the wrong parent.
3. Confirm the failure is a product defect or committed-test defect, not tooling, missing credentials, missing test data, unreachable infrastructure, or evidence upload failure.
4. Create or reuse a linked ticket provider bug ticket with:
   - parent ticket key (bug is created as a child of the parent),
   - tested commit and artifact,
   - QA environment and URLs,
   - failed scenario and expected/actual behavior,
   - evidence link or local fallback path,
   - severity and user impact,
   - marker `IA generated QA bug: {parentTicketKey}`.
5. Comment on the parent ticket with the bug link. Leave the parent in its current state (e.g., `Tested` or `QA`). The parent does NOT move until the bug is fixed and E2E QA re-runs successfully.

### Phase 2 — Move Bug To Specified

6. Fetch the bug ticket (just created in step 4) and expand its description.
7. Add a detailed fix plan to the bug description using the IA generated block format:
   - **Root cause** of the failure (from E2E QA evidence)
   - **Fix approach** (what needs to change and where)
   - **Acceptance criteria** for the fix (specific, testable assertions)
   - **Affected files** (list of files that need changes)
   - **Validation** (how to verify the fix — re-run affected tests)
   - **Estimated effort** (hours forecast)
8. Move the bug ticket to the target specification state. Attempt the transition via the ticket provider API. If the API returns an error indicating the state is unknown or not allowed, retry with the fallback state from `project-profile.json → workflow.bugSpecifiedFallback`, or use `In specification` as a final fallback.

   Use marker: `IA generated bug specification: {bugKey}`

### Phase 3 — Update Parent OpenSpec With Bug Tasks

9. Identify the parent ticket's active OpenSpec change. Run:
   ```bash
   openspec list --json
   ```
   Find the change by matching the parent ticket key against each change's **`description` or `metadata.ticketKey`** field — not the directory name, which may use a different convention (e.g., `refactor-`, `chore-`).

   **Fallback:** If `openspec list --json` doesn't expose ticketKey in metadata, search the `openspec/changes/` directory listing and match by directory name convention (e.g., `{prefix}-{parentKey}-*`).

10. Read the parent's `tasks.md`:
    ```bash
    cat openspec/changes/{parentChangeName}/tasks.md
    ```

11. **Append** bug-fix tasks to the parent's `tasks.md`. Do NOT replace or remove existing tasks. Append a new numbered section with the bug title and tasks:
    ```markdown
    ## Bug Fix: {bugKey} — {short description}
    
    - [ ] {bugKey}-1: Implement the fix (describe what)
    - [ ] {bugKey}-2: Update existing tests if needed
    - [ ] {bugKey}-3: Verify fix passes E2E QA against QA deployment
    ```

12. Verify the updated `tasks.md` is well-formed (no broken markdown).

### Phase 4 — Start Fix Branch

13. Move the bug ticket to `In progress` state.
14. Commit the OpenSpec changes made in Phase 3:
    ```bash
    git add openspec/changes/{parentChangeName}/tasks.md
    git commit -m "{bugKey}: add bug-fix tasks to {parentTicketKey} OpenSpec"
    ```
    This commits the bug tasks to `dev` **before** branching, so the OpenSpec edit is not lost.

15. Verify the working tree is clean: `git status --porcelain` must show no output.
16. Run `git pull --ff-only` (already on `dev` from Step 14's commit).
17. Create a fix branch:
    ```bash
    git checkout -b fix/{bugKeySlug}-{short-description}
    ```
    Example: `fix/e2eproject-38-no-validate-forgot-password`
18. Push the branch to the remote with upstream tracking:
    ```bash
    git push -u {remoteName} fix/{bugKeySlug}-{short-description}
    ```
19. Add a comment on the bug ticket with the branch name, base branch, and remote:
    ```text
    IA generated bug branch: fix/{bugKeySlug}-{short-description}
    ```

### Phase 5 — Create Pull Request

20. Create a pull request from the fix branch to `dev` with:
    - Title: `{bugKey}: {short description} (parent: {parentTicketKey})`
    - Description including:
      - The bug ticket link
      - The parent ticket link
      - A summary of the fix
      - Link to E2E QA evidence
      - Any affected files
    - Labels: `bug`, `qa-verified` if applicable

21. Add a comment on the bug ticket with the PR link:
    ```text
    IA generated bug PR: {prUrl}
    ```

### Phase 6 — Hand Off To Implementation

22. Update `.codex/delivery-context.local.json` with:
    - `ticketKey`: bug ticket key
    - `parentTicketKey`: parent ticket key (advisory for cross-referencing)
    - `branch`: fix branch name (✅ `dev-flow-continue-implementation` auto-checkouts this branch via its Pre-Flight step)
    - `openspecChange`: parent's OpenSpec change name (bug tasks live there)
    - `evidencePath`: E2E QA evidence path or URL

23. Hand off to `dev-flow-continue-implementation` or the user to implement the fix on the fix branch.

    **Note:** The orchestrator's Pre-Flight step will auto-checkout the fix branch from the `branch` field set above. No manual checkout needed.

    **Important:** After implementation is complete, the implementer must:
    - Run E2E QA against the fix before merging
    - If QA re-runs pass, merge the PR back to `dev`
    - Move the bug ticket to `Done`
    - The parent ticket `{parentTicketKey}` remains in its current state (e.g., `Tested` or `QA`) — it does NOT move when the bug is closed

### Non-Code Defects

If the defect is only data, environment, or unclear requirements (not a code change):

1. Do NOT modify OpenSpec.
2. Do NOT create a branch.
3. Comment on the bug ticket explaining why no code change is needed.
4. Report the non-code owner (e.g., operations, product owner).
5. Do not move the bug to `In Progress`.

## OpenSpec Policy

Bugs **modify the parent's existing OpenSpec** — they do NOT create a new OpenSpec change. The bug-fix tasks are appended to the parent's `tasks.md` as a new section. This keeps all work for a feature (including bug fixes found during E2E QA) in one place.

The parent's OpenSpec is archived only when the parent ticket itself moves to Done. Bug tasks remain in the parent's tasks.md as historical record even after the bug is fixed.

Skip OpenSpec modification only when:
- the bug is explicitly marked `no-openspec` or `ops-only`,
- the user explicitly requests no OpenSpec modification,
- the parent ticket has no active OpenSpec change (unusual for QA-discovered bugs).

## Output

Report the parent ticket, bug ticket (with link), E2E QA evidence path, bug specification state (with fallback if used), parent OpenSpec change updated with bug tasks, fix branch name and remote with initial commit, PR URL, bug ticket In progress state, handoff to implementation, and post-implementation summary (E2E QA re-run result, merge status, bug closed, parent remains in current state).

For non-code defects, report the parent ticket, evidence path, and required non-code owner.

## Failure Rules

- Missing parent ticket or QA evidence: stop and ask for the missing identifier.
- Ticket context lock mismatch: stop before filing or linking a bug.
- Unsafe evidence contains secrets: redact or discard unsafe evidence before commenting.
- Existing linked bug with the same marker and tested commit: reuse it instead of creating a duplicate.
- ticket-provider mutation fails: do not create branches or OpenSpec changes until the bug relationship is recorded.
- Dirty working tree: stop before branch creation.
- Parent ticket has no active OpenSpec change: report this as an anomaly but continue (create branch without OpenSpec update).
- openspec CLI unavailable: report the blocker but continue with branch creation (skip OpenSpec update).
