---
name: dev-flow-propose-change
description: Propose a new change with all artifacts generated in one step. Use when the user wants to quickly describe what they want to build and get a complete proposal with design, specs, and tasks ready for implementation.
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.3.1"
---

<!-- TIER 3: STAGE-SPECIFIC - Proposal workflow skill -->

Propose a new change — create the change and generate all planning artifacts in one step following the `/opsx:propose` pattern.

I'll create a change with all planning artifacts:

- proposal.md (what & why)
- specs/**/*.md (behavior specs)
- design.md (how)
- tasks.md (implementation steps with Review Workload Forecast)

When ready to implement, run /opsx:apply.

---

**Input**: The user's request should include a change name (kebab-case) OR a description of what they want to build.

**Steps**

1. **If no clear input provided, ask what they want to build**

   Use the **AskUserQuestion tool** (open-ended, no preset options) to ask:

   > "What change do you want to work on? Describe what you want to build or fix."

   From their description, derive a kebab-case name (e.g., "add user authentication" → `add-user-auth`).

   **IMPORTANT**: Do NOT proceed without understanding what the user wants to build.

2. **Create the change directory**

   ```bash
   openspec new change "<name>"
   ```

   This creates a scaffolded change at `openspec/changes/<name>/` with `.openspec.yaml`.

3. **Propose — generate all planning artifacts in one flow**

   Follow the `/opsx:propose` pattern. Read the project context from `openspec/config.yaml` (context + rules) and the schema definition. Generate ALL artifacts in a single coherent pass, in dependency order:

   1. **Read context**: Load `openspec/config.yaml` for `context:`, `rules:`, and schema information. Read any existing specs in `openspec/specs/` for existing behavior standards.

   2. **Create `proposal.md`** — Problem / opportunity, user story, scope, acceptance criteria, out of scope, risks. Use the ticket description and refined planning as input.

   3. **Create `specs/`** — Behavior specs as `specs/*.md` in the change folder. Each spec covers one capability with concrete scenarios.

   4. **Create `design.md`** — Architecture decisions, technology choices, component structure, data flow, alternatives considered.

   5. **Create `tasks.md`** — Implementation tasks with checkboxes, grouped by concern, including a Review Workload Forecast with estimated changed lines, budget risk, and delivery strategy.

   **Apply these guidelines:**
   - Use `openspec/config.yaml` context and rules as constraints for what you write — do NOT copy them into the artifacts.
   - Read completed dependency artifacts before creating the next one (e.g., read `proposal.md` before writing `design.md`).
   - Capture resolved grill-style decisions: planned behavior in specs, design choices in design, implementation steps in tasks.
   - Each artifact file must be written to the correct path inside `openspec/changes/<name>/`.

4. **Verify all artifacts**

   ```bash
   openspec status --change "<name>"
   ```

   Confirm all required artifacts show `[x]` (complete). If any are missing, create the file and re-verify.

**Output**

After completing all artifacts, summarize:

- Change name and location
- List of artifacts created with brief descriptions
- What's ready: "All artifacts created! Ready for implementation."
- Prompt: "Run `/opsx:apply` or ask me to implement to start working on the tasks."

**Artifact Creation Guidelines**

- Use `openspec/config.yaml` context and rules as constraints for what you write — do NOT copy them into artifacts.
- The schema (`spec-driven`) defines what each artifact should contain. Follow the expected structure for each type.
- Read dependency artifacts before creating the next one (e.g., read `proposal.md` before writing `design.md`).
- Capture resolved grill-style decisions in the normal OpenSpec artifacts: planned behavior in specs, design choices and rationale in design, and implementation steps in tasks.
- Write each artifact to its correct path inside `openspec/changes/<name>/`:
  - `proposal.md`
  - `specs/<area>.md` (one or more spec files by capability area)
  - `design.md`
  - `tasks.md`
- **IMPORTANT**: `context` and `rules` from config.yaml guide what you write but must NEVER appear in the artifact files.

**Guardrails**

- Create ALL artifacts needed for implementation (schema's `apply.requires`: at minimum `tasks`)
- Always read dependency artifacts before creating a new one
- If context is critically unclear, ask the user - but prefer making reasonable decisions to keep momentum
- If a change with that name already exists, ask if user wants to continue it or create a new one
- Verify all artifacts exist with `openspec status` before declaring the propose flow complete

## Overview

Use this skill to create an OpenSpec change proposal and the artifacts needed before implementation.

## Shared Context

For ticketed changes, read `.codex/skills/_shared/delivery-contract.md` and `docs/context-management.md` before creating artifacts. Keep proposal scope aligned with the active ticket or explicit user request, and preserve validation and handoff expectations for implementation.

## Workflow

Follow the proposal artifact creation steps above, capture resolved `grill-with-docs` planning knowledge in OpenSpec instead of a separate context file, then route implementation through the appropriate dev-flow skill.

## Output

Report the change name, artifacts created, validation performed, ready-to-implement status, and handoff notes.

## Failure Rules

Stop when the requested change is ambiguous, conflicts with the active ticket, cannot create required artifacts, or requires implementation decisions that should be resolved before proposal handoff.
