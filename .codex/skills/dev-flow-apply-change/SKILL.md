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

2. **Follow the `/opsx:apply` pattern — implement tasks**

   Read `tasks.md` directly from `openspec/changes/<name>/tasks.md` to get the task list with checkboxes.

   Read context files for implementation guidance:
   - `proposal.md` — what & why
   - `specs/*.md` — behavior specs
   - `design.md` — how

   **Handle states:**
   - If `tasks.md` is missing: show message, suggest running the propose flow first
   - If all tasks are marked `[x]`: congratulate, suggest archive
   - Otherwise: proceed to implementation

4. **Show current progress**

   Display:
   - Change name and location
   - Progress: "N/M tasks complete"
   - Remaining tasks list

5. **⚠️ MANDATORY: Write tests based on tasks before product code.** For each pending task:
   - Load the `tdd` skill via `skill('tdd')` (or read `.codex/skills/tdd/SKILL.md`) and apply its test-first cycles throughout.
   - Show which task is being worked on
   - Build or update the acceptance-to-test map for the task before product code changes
   - The test map must cover **three levels** (per component, not per task) as defined in `.codex/skills/_shared/test-requirements.md` — unit tests (per component), integration tests (per endpoint/feature), and architecture tests (project-wide, one file for the entire change)
   - Write the behavior-focused test through a public interface for the next acceptance criterion or task behavior
   - Run the smallest relevant test command and confirm it fails for the expected reason (RED)
   - **❌ HARD RULE**: No product code change is allowed until all three test levels (unit per component, integration per feature, architecture project-wide) are written and confirmed RED for the current task. This is a process violation (authority level 5).
   - Make the smallest product code change required to pass that test
   - Rerun the focused test and confirm it passes (GREEN)
   - Repeat one vertical RED/GREEN cycle at a time until every acceptance criterion has committed automated coverage
   - Refactor only while GREEN, then rerun the relevant tests
   - Keep changes minimal and focused
   - Mark task complete in the tasks file: `- [ ]` → `- [x]`
   - Continue to next task

   **Pause if:**
   - Task is unclear → ask for clarification
   - Implementation reveals a design issue → suggest updating artifacts via `/opsx:update`
   - Error or blocker encountered → report and wait for guidance
   - User interrupts

6. **On completion or pause, show status**

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

**Apply declared skills during TDD cycles**

Skills loaded in the Skill Pre-Analysis above are NOT decorative. In EVERY TDD cycle phase, actively apply them:

- **RED phase**: Apply `tdd` + stack-specific testing patterns + `clean-code` (test structure) + `security-best-practices` (test security boundaries)
- **GREEN phase**: Apply `ponytail full` (minimal code) + stack-specific framework conventions + `clean-code` (naming, functions) + `security-best-practices` (input validation) + `solid` (focused interfaces)
- **REFACTOR phase**: Apply `clean-architecture` (Dependency Rule) + `clean-code` (smell removal) + `solid` (SRP, OCP) + stack-specific architecture patterns

**Check MCP routing for service interactions**

Per `.codex/mcp-instructions.md`, route service interactions through the service MCPs (gitea, openproject, grafana). Repository content search uses built-in file/search tools.

Declare which skills were actively applied at the start of each response body with a `Skills used:` block including per-skill rationale.

**Guardrails**

- Keep going through tasks until done or blocked
- Always read context files before starting from the change directory (proposal.md, specs/*.md, design.md, tasks.md)
- Use `tdd` for ticketed implementation: tests first, public-interface behavior tests, one vertical RED/GREEN cycle at a time
- Do not write all tests first and then all implementation; do not write product code before the acceptance-to-test map and first failing test for the current behavior
- Stop before implementation handoff when any acceptance criterion lacks committed automated coverage
- If task is ambiguous, pause and ask before implementing
- If implementation reveals issues, pause and suggest artifact updates
- Keep code changes minimal and scoped to each task
- Update task checkbox immediately after completing each task
- Pause on errors, blockers, or unclear requirements - don't guess
- Read context files directly from openspec/changes/<name>/ — don't rely on external CLI output

**Fluid Workflow Integration**

This skill supports the "actions on a change" model:

- **Can be invoked anytime**: Before all artifacts are done (if tasks exist), after partial implementation, interleaved with other actions
- **Allows artifact updates**: If implementation reveals design issues, suggest updating artifacts - not phase-locked, work fluidly

## Overview

Use this skill to apply an OpenSpec change inside the repository delivery workflow.

## Shared Context

Before ticketed implementation, read `.codex/skills/_shared/delivery-contract.md` and `docs/conventions/context-management.md`. Keep changes scoped to the active ticket or explicit change, run the needed validation, and preserve handoff details for the caller.

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
