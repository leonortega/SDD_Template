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

1. **If no change name provided, prompt for selection (opsx flow)**

   Run `openspec list --json` to list active changes (not already archived) and use the **AskUserQuestion tool** to let
   the user select.

   **IMPORTANT**: Do NOT guess or auto-select a change. Always let the user choose.

2. **Run the opsx archive flow — delegate to `openspec-archive-change`.**

   Load the `openspec-archive-change` skill (`.agents/skills/openspec-archive-change/SKILL.md`, manifest `openspec`
   category) and follow its Workflow exactly. It drives the `openspec` CLI to:
   - check artifact completion (`openspec status --change "<name>" --json`),
   - check task completion from the task list,
   - assess and apply delta-spec sync (`openspec` archive/sync semantics), and
   - perform the archive move (`openspec archive <name>`).

   The CLI is authoritative for artifact status, sync state, and the archive operation. Do NOT hand-implement the sync
   diff or the archive move with raw file commands.

   **Archive blockers (stop and report, never archive by confirmation):**
   - `openspec status` reports missing planning artifacts or the change is incomplete,
   - incomplete tasks remain (`- [ ]`),
   - no tasks file exists (`OpenSpec archive blocker: missing tasks.md`),
   - spec sync fails validation or cannot be applied (`OpenSpec archive blocker: spec sync failed`),
   - the change directory is still present after the archive operation (`OpenSpec archive blocker: change still active
   after archive`).

3. **Display summary**

   Show archive completion summary including:
   - Change name
   - Schema that was used
   - Archive location
   - Whether specs were synced (if applicable)
   - Note about any warnings (incomplete artifacts/tasks)

4. **Capture durable learning (mandatory after archive)**

   After the archive succeeds, run the Durable Learning Capture Gate
   (`.codex/skills/_shared/delivery-contract-core.md` → Durable Learning Capture Gate) using the
   deterministic classifier:

   ```bash
   python -m tools.sdd_cli knowledge-search classify --task "<change name + ticket summary>" --changed-files "<comma-separated changed paths>" --test-results "<E2E QA outcome, e.g. PASS>"
   ```

   Build the changed-file list from the change's commits (e.g. `git diff --name-only` over the change branch vs its base)
or the ticket's changed-file list; when unavailable, fall back to the change's own paths under `openspec/changes/<name>/`.

   Then:
   - If the classifier returns `UPDATE` candidates, load `.codex/skills/docs-knowledge-maintenance/SKILL.md`
     and update **only** those candidate files (standard template, source-backed, never secrets).
   - If it returns `NO_CHANGES`, record `Docs: no durable context changes` / `Knowledge updated: none` — do not
     invent files to update.
   - Commit and push the updated `docs/` or `knowledge/` files with a ticket-key-prefixed message (e.g.
     `{ticketKey}: archive {change} - update docs/knowledge`).

   The archived spec files under `openspec/specs/` are the durable behavior record — do not duplicate their
   content into `docs/` or `knowledge/`.

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
- Use the opsx archive flow (`openspec-archive-change` skill → `openspec` CLI) for artifact/task checks, sync
assessment, and the archive move — do not hand-implement with raw file commands
- Incomplete artifacts, incomplete tasks, missing tasks.md, failed spec sync, or failed archive movement are blockers.
Never archive by confirmation when work is incomplete.
- Preserve .openspec.yaml when moving to archive (the CLI archive keeps it with the directory)
- Show clear summary of what happened
- If sync is requested, let the CLI apply the delta specs to the main specs
- If delta specs exist, always run the sync assessment and show the combined summary before prompting
- Never report archive success unless the change directory has been moved to archive.
- Never skip the durable-learning capture step; `NO_CHANGES` is a valid classifier outcome, not an error.

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

Report the archived change, archive path, sync status, validation result, docs/knowledge capture outcome
(`Docs updated: <files>` / `Docs: no durable context changes`, `Knowledge updated: <files>` /
`Knowledge updated: none`), and handoff status.

## Failure Rules

Stop when the change is ambiguous, artifacts or tasks are incomplete, spec sync fails, archive verification fails, or
ticket context conflicts with the requested archival. If the classifier or `docs-knowledge-maintenance` update fails,
stop the update step and report the blocker in the handoff — the archive itself remains valid, but the workflow is
not complete without the capture outcome.
