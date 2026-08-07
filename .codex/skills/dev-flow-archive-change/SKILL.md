---
name: dev-flow-archive-change
description: >-
  Archive a completed change in the experimental workflow. Use when the user wants to finalize and archive a change
  after implementation is complete.
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.3.1"
---

<!-- TIER 3: STAGE-SPECIFIC - Archive workflow skill -->

Archive a completed change in the experimental workflow.

**Input**: Optionally specify a change name. If omitted, check if it can be inferred from conversation context. If vague
or ambiguous you MUST prompt for available changes.

**Steps**

1. **If no change name provided, prompt for selection**

   List active changes by checking directories in `openspec/changes/` that have a `.openspec.yaml` file. Use the
   **AskUserQuestion tool** to let the user select.

   Show only active changes (not already archived).

   **IMPORTANT**: Do NOT guess or auto-select a change. Always let the user choose.

2. **Follow the `/opsx:archive` pattern — check artifact completion**

   Check that all expected artifact files exist:
   - `openspec/changes/<name>/proposal.md`
   - `openspec/changes/<name>/specs/` (directory with at least one spec)
   - `openspec/changes/<name>/design.md`
   - `openspec/changes/<name>/tasks.md`

   **If any artifacts are missing:**
   - Stop. This is an archive blocker.
   - List missing artifacts.
   - Do not ask for confirmation to continue.
   - Do not move the change directory.

3. **Check task completion status**

   Read the tasks file (typically `tasks.md`) to check for incomplete tasks.

   Count tasks marked with `- [ ]` (incomplete) vs `- [x]` (complete).

   **If incomplete tasks found:**
   - Stop. This is an archive blocker.
   - List or count incomplete tasks.
   - Do not ask for confirmation to continue.
   - Do not move the change directory.

   **If no tasks file exists:** Stop and report `OpenSpec archive blocker: missing tasks.md`.

4. **Assess delta spec sync state**

   Check for delta specs at `openspec/changes/<name>/specs/`. If none exist, proceed without sync prompt.

   **If delta specs exist:**
   - Compare each delta spec with its corresponding main spec at `openspec/specs/<capability>/spec.md`
   - Determine what changes would be applied (adds, modifications, removals, renames)
   - Show a combined summary before prompting

   **Prompt options:**
   - If changes needed: "Sync now"
   - If already synced: "Archive now", "Sync anyway", "Cancel"

   If changes are needed, sync is mandatory before archive. Apply the analyzed delta specs to the main specs at
   `openspec/specs/<capability>/spec.md` (agent-driven sync; see `openspec/config.yaml`
   rules). Proceed to archive only after sync succeeds.

   If sync fails validation, cannot write the main specs, or leaves the delta specs unapplied, stop and report `OpenSpec
   archive blocker: spec sync failed`. Do not move the change directory.

5. **Perform the archive**

   Create the archive directory if it doesn't exist:

   ```bash
   mkdir -p openspec/changes/archive
   ```

   Generate target name using current date: `YYYY-MM-DD-<change-name>`

   **Check if target already exists:**
   - If yes: Fail with error, suggest renaming existing archive or using different date
   - If no: Move the change directory to archive

   ```bash
   mv openspec/changes/<name> openspec/changes/archive/YYYY-MM-DD-<name>
   ```

   After moving, verify the change directory no longer exists at `openspec/changes/<name>/`. If it is still present,
   report `OpenSpec archive blocker: change still active after archive`.

6. **Display summary**

   Show archive completion summary including:
   - Change name
   - Schema that was used
   - Archive location
   - Whether specs were synced (if applicable)
   - Note about any warnings (incomplete artifacts/tasks)

**Output On Success**

```text
## Archive Complete

**Change:** <change-name>
**Schema:** <schema-name>
**Archived to:** openspec/changes/archive/YYYY-MM-DD-<name>/
**Specs:** ✓ Synced to main specs (or "No delta specs" or "Sync skipped")

All artifacts complete. All tasks complete.
```

**Guardrails**

- Always prompt for change selection if not provided
- Check artifact file existence for completion validation (proposal.md, specs/, design.md, tasks.md)
- Incomplete artifacts, incomplete tasks, missing tasks.md, failed spec sync, or failed archive movement are blockers.
Never archive by confirmation when work is incomplete.
- Preserve .openspec.yaml when moving to archive (it moves with the directory)
- Show clear summary of what happened
- If sync is requested, apply the delta specs to the main specs (agent-driven)
- If delta specs exist, always run the sync assessment and show the combined summary before prompting
- Never report archive success unless the change directory has been moved to archive.

## Overview

Use this skill to archive a completed OpenSpec change after implementation and validation are complete.

## Shared Context

Before ticketed archival, read `.codex/skills/_shared/delivery-contract.md` and
`docs/conventions/context-management.md`. Verify the active ticket or explicit change is complete and preserve handoff
context.

## Workflow Telemetry

Workflow telemetry is **mandatory** for this stage: before handoff, upsert the stage time entry with the standalone
script (shared pattern `.codex/skills/_shared/pipeline-workflow-telemetry.md`):

```bash
python -m tools.sdd_cli dev-flow telemetry-upsert --ticket-key {ticketKey} \
  --workflow-stage dev-flow-archive-change --agent-role archive \
  --started-utc {startedUtc} --finished-utc {finishedUtc} --outcome {outcome}
```

The marker `IA generated workflow telemetry: {ticketKey}:dev-flow-archive-change` is written automatically. If the
upsert fails, stop and report before handoff.

## Workflow

Follow the archive checks above and archive only after artifacts, tasks, and any required spec sync are complete.

## Output

Report the archived change, archive path, sync status, validation result, and handoff status.

## Failure Rules

Stop when the change is ambiguous, artifacts or tasks are incomplete, spec sync fails, archive verification fails, or
ticket context conflicts with the requested archival.
