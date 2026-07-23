---
name: dev-flow-apply-change
description: Implement tasks from an OpenSpec change. Use when the user wants to start implementing, continue implementation, or work through tasks.
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.3.1"
---

<!-- TIER 3: STAGE-SPECIFIC - Implementation workflow skill -->

Implement tasks from an OpenSpec change.

**Input**: Optionally specify a change name. If omitted, check if it can be inferred from conversation context. If vague or ambiguous you MUST prompt for available changes.

**Steps**

1. **Select the change**

   If a name is provided, use it. Otherwise:
   - Infer from conversation context if the user mentioned a change
   - Auto-select if only one active change exists
   - If ambiguous, run `openspec list --json` to get available changes and use the **AskUserQuestion tool** to let the user select

   Always announce: "Using change: <name>" and how to override (e.g., `/opsx:apply <other>`).

2. **Check status to understand the schema**

   ```bash
   openspec status --change "<name>" --json
   ```

   Parse the JSON to understand:
   - `schemaName`: The workflow being used (e.g., "spec-driven")
   - Which artifact contains the tasks (typically "tasks" for spec-driven, check status for others)

3. **Get apply instructions**

   ```bash
   openspec instructions apply --change "<name>" --json
   ```

   This returns:
   - `contextFiles`: artifact ID -> array of concrete file paths (varies by schema - could be proposal/specs/design/tasks or spec/tests/implementation/docs)
   - Progress (total, complete, remaining)
   - Task list with status
   - Dynamic instruction based on current state

   **Handle states:**
   - If `state: "blocked"` (missing artifacts): show message, suggest using openspec-continue-change
   - If `state: "all_done"`: congratulate, suggest archive
   - Otherwise: proceed to implementation

4. **Read context files**

   Read every file path listed under `contextFiles` from the apply instructions output.
   The files depend on the schema being used:
   - **spec-driven**: proposal, specs, design, tasks
   - Other schemas: follow the contextFiles from CLI output

5. **Show current progress**

   Display:
   - Schema being used
   - Progress: "N/M tasks complete"
   - Remaining tasks overview
   - Dynamic instruction from CLI

6. **Implement tasks (loop until done or blocked)**

   For each pending task:
   - Show which task is being worked on
   - Build or update the acceptance-to-test map for the task before product code changes
   - Write one behavior-focused test through a public interface for the next acceptance criterion or task behavior
   - Run the smallest relevant test command and confirm it fails for the expected reason (RED)
   - Make the smallest product code change required to pass that test
   - Rerun the focused test and confirm it passes (GREEN)
   - Repeat one vertical RED/GREEN cycle at a time until every acceptance criterion has committed automated coverage
   - Refactor only while GREEN, then rerun the relevant tests
   - Keep changes minimal and focused
   - Mark task complete in the tasks file: `- [ ]` → `- [x]`
   - Continue to next task

   **Pause if:**
   - Task is unclear → ask for clarification
   - Implementation reveals a design issue → suggest updating artifacts
   - Error or blocker encountered → report and wait for guidance
   - User interrupts

7. **On completion or pause, show status**

   Display:
   - Tasks completed this session
   - Overall progress: "N/M tasks complete"
   - If all done: suggest archive
   - If paused: explain why and wait for guidance

**Output During Implementation**

```
## Implementing: <change-name> (schema: <schema-name>)

Working on task 3/7: <task description>
[...implementation happening...]
✓ Task complete

Working on task 4/7: <task description>
[...implementation happening...]
✓ Task complete
```

**Output On Completion**

```
## Implementation Complete

**Change:** <change-name>
**Schema:** <schema-name>
**Progress:** 7/7 tasks complete ✓

### Completed This Session
- [x] Task 1
- [x] Task 2
...

All tasks complete! Ready to archive this change.
```

**Output On Pause (Issue Encountered)**

```
## Implementation Paused

**Change:** <change-name>
**Schema:** <schema-name>
**Progress:** 4/7 tasks complete

### Issue Encountered
<description of the issue>

**Options:**
1. <option 1>
2. <option 2>
3. Other approach

What would you like to do?
```

**Guardrails**

- Keep going through tasks until done or blocked
- Always read context files before starting (from the apply instructions output)
- Use `tdd` for ticketed implementation: tests first, public-interface behavior tests, one vertical RED/GREEN cycle at a time
- Do not write all tests first and then all implementation; do not write product code before the acceptance-to-test map and first failing test for the current behavior
- Stop before implementation handoff when any acceptance criterion lacks committed automated coverage
- If task is ambiguous, pause and ask before implementing
- If implementation reveals issues, pause and suggest artifact updates
- Keep code changes minimal and scoped to each task
- Update task checkbox immediately after completing each task
- Pause on errors, blockers, or unclear requirements - don't guess
- Use contextFiles from CLI output, don't assume specific file names

**Fluid Workflow Integration**

This skill supports the "actions on a change" model:

- **Can be invoked anytime**: Before all artifacts are done (if tasks exist), after partial implementation, interleaved with other actions
- **Allows artifact updates**: If implementation reveals design issues, suggest updating artifacts - not phase-locked, work fluidly

## Overview

Use this skill to apply an OpenSpec change inside the repository delivery workflow.

## Shared Context

Before ticketed implementation, read `.codex/skills/_shared/delivery-contract.md` and `docs/context-management.md`. Keep changes scoped to the active ticket or explicit change, run the needed validation, and preserve handoff details for the caller.

## Skill Pre-Analysis

Before any code changes, the caller (`dev-flow-implement-ticket`) runs the **Skill Pre-Analysis** step to determine which skills are applicable based on the project stack and tool recommendations. See `dev-flow-implement-ticket/SKILL.md` §1 step 5 for the full analysis procedure.

When called directly without the parent pre-analysis, perform a lightweight pre-analysis:

1. Read `.codex/project-profile.local.json` → `stack` section for frontend/backend/database values (stack lives **only** in the ignored local overlay). If it does not exist, stack is empty. Read `.codex/project-profile.json` for non-stack config (providers, workflow, gates).
2. Read `.codex/tool-recommendations.local.json` → `accepted` list to find which skills are enabled.
3. Map the stack to skills per the table in `dev-flow-implement-ticket/SKILL.md` §1 step 5b.
4. Load and declare every applicable skill before starting TDD cycles:
   - Try the `skill` tool first. If it reports "no skills available", read the SKILL.md directly from `.codex/skills/<name>/SKILL.md` and apply its rules manually.
5. If the stack is empty but the ticket implies a product, suggest running `python -m tools.sdd_cli guidance discover` or configuring via `set-project-stack`.

## Workflow

Follow the OpenSpec apply steps above, then return control to the owning dev-flow skill for review, QA, deployment, or handoff.

## Output

Report the selected change, completed tasks, remaining blockers, validation performed, and handoff status.

## Failure Rules

Stop when the active change is ambiguous, required artifacts are missing, a task conflicts with the ticket scope, validation cannot run, or implementation would require guessing.
