---
name: dev-flow-archive-change
description: Archive a completed change in the experimental workflow. Use when the user wants to finalize and archive a change after implementation is complete.
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.3.1"
---

<!-- TIER 3: STAGE-SPECIFIC - Archive workflow skill -->

Archive a completed change in the experimental workflow.

**Input**: Optionally specify a change name. If omitted, check if it can be inferred from conversation context. If vague or ambiguous you MUST prompt for available changes.

**Steps**

1. **If no change name provided, prompt for selection**

   Run `openspec list --json` to get available changes. Use the **AskUserQuestion tool** to let the user select.

   Show only active changes (not already archived).
   Include the schema used for each change if available.

   **IMPORTANT**: Do NOT guess or auto-select a change. Always let the user choose.

2. **Check artifact completion status**

   Run `openspec status --change "<name>" --json` with process environment `OPENSPEC_TELEMETRY=0` to check artifact completion.

   Parse the JSON to understand:
   - `schemaName`: The workflow being used
   - `artifacts`: List of artifacts with their status (`done` or other)

   **If any artifacts are not `done`:**
   - Stop. This is an archive blocker.
   - List incomplete artifacts.
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

   If changes are needed, sync is mandatory before archive. Use Task tool (subagent_type: "general-purpose", prompt: "Use Skill tool to invoke openspec-sync-specs for change '<name>'. Delta spec analysis: <include the analyzed delta spec summary>"). Proceed to archive only after sync succeeds.

   If sync fails validation, cannot write the main specs, or leaves the delta specs unapplied, stop and report `OpenSpec archive blocker: spec sync failed`. Do not move the change directory.

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

   After moving, run `openspec list --json` with `OPENSPEC_TELEMETRY=0` and verify `<change-name>` is absent from active changes. If it is still active, report `OpenSpec archive blocker: change still active after archive`.

6. **Display summary**

   Show archive completion summary including:
   - Change name
   - Schema that was used
   - Archive location
   - Whether specs were synced (if applicable)
   - Note about any warnings (incomplete artifacts/tasks)

**Output On Success**

```
## Archive Complete

**Change:** <change-name>
**Schema:** <schema-name>
**Archived to:** openspec/changes/archive/YYYY-MM-DD-<name>/
**Specs:** ✓ Synced to main specs (or "No delta specs" or "Sync skipped")

All artifacts complete. All tasks complete.
```

**Guardrails**

- Always prompt for change selection if not provided
- Use artifact graph (openspec status --json) for completion checking
- Incomplete artifacts, incomplete tasks, missing tasks.md, failed spec sync, or failed archive movement are blockers. Never archive by confirmation when work is incomplete.
- Preserve .openspec.yaml when moving to archive (it moves with the directory)
- Show clear summary of what happened
- If sync is requested, use openspec-sync-specs approach (agent-driven)
- If delta specs exist, always run the sync assessment and show the combined summary before prompting
- Never report archive success unless the active change is gone from `openspec list --json`.

## Overview

Use this skill to archive a completed OpenSpec change after implementation and validation are complete.

## Shared Context

Before ticketed archival, read `.codex/skills/_shared/delivery-contract.md` and `docs/context-management.md`. Verify the active ticket or explicit change is complete and preserve handoff context.

## Workflow

Follow the archive checks above and archive only after artifacts, tasks, and any required spec sync are complete.

## Output

Report the archived change, archive path, sync status, validation result, and handoff status.

## Failure Rules

Stop when the change is ambiguous, artifacts or tasks are incomplete, spec sync fails, archive verification fails, or ticket context conflicts with the requested archival.
