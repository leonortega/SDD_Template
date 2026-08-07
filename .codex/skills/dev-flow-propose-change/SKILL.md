---
name: dev-flow-propose-change
description: >-
  >- Propose a new change with all artifacts generated in one step. Use when the user wants to quickly describe what
  they want to build and get a complete proposal with design, specs, and tasks ready for implementation.
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.3.1"
---

<!-- TIER 3: STAGE-SPECIFIC - Proposal workflow skill -->

Propose a new change — create the change and generate all planning artifacts in one step using the **opsx propose
flow** (`openspec-propose` skill → `openspec` CLI).

I'll create a change with all planning artifacts:

- proposal.md (what & why)
- specs/**/*.md (behavior specs)
- design.md (how)
- tasks.md (implementation steps with Review Workload Forecast)

When ready to implement, run `$openspec-apply-change` (Codex).

---

**Input**: The user's request should include a change name (kebab-case) OR a description of what they want to build.

**Steps**

1. **If no clear input provided, ask what they want to build**

   Use the **AskUserQuestion tool** (open-ended, no preset options) to ask:

   > "What change do you want to work on? Describe what you want to build or fix."

   From their description, derive a kebab-case name (e.g., "add user authentication" → `add-user-auth`).

   **IMPORTANT**: Do NOT proceed without understanding what the user wants to build.

2. **Run the opsx propose flow — delegate to `openspec-propose`.**

   Load the `openspec-propose` skill (`.agents/skills/openspec-propose/SKILL.md`, registered in the manifest `openspec`
   category) and follow its Workflow exactly. It drives the `openspec` CLI (`openspec new change`, `openspec status
   --json`, `openspec instructions <artifact> --change <name> --json`) to scaffold the change and create every planning
   artifact in dependency order, honoring `openspec/config.yaml` context and rules.

   **Do NOT hand-write the artifacts from the schema** — the opsx flow generates each artifact from the CLI's
   authoritative `instructions` output (structure, context, and rules), which is what prevents drift and skipped
   artifacts. If the `openspec-propose` skill cannot be loaded, read its SKILL.md directly and follow it, still calling
   the `openspec` CLI for scaffolding, status, and per-artifact instructions.

3. **Verify all artifacts**

   ```bash
   openspec status --change "<name>"
   ```

   Confirm all required artifacts show `[x]` (complete). If any are missing, continue the opsx flow to create them
   (per-artifact `openspec instructions`), then re-verify.

**Output**

After completing all artifacts, summarize:

- Change name and location
- List of artifacts created with brief descriptions
- What's ready: "All artifacts created! Ready for implementation."
- Prompt: "Run `$openspec-apply-change` or ask me to implement to start working on the tasks."

**Artifact Creation Guidelines**

- Always follow the `instruction` field from `openspec instructions <artifact> --change <name> --json` — it is the
  authoritative guidance, even for familiar artifact names.
- The schema (`spec-driven`) defines what each artifact should contain; the opsx flow enforces it via the CLI.
- Read dependency artifacts before creating the next one (e.g., read `proposal.md` before writing `design.md`).
- Capture resolved grill-style decisions in the normal OpenSpec artifacts: planned behavior in specs, design choices and
rationale in design, and implementation steps in tasks.
- Write each artifact to the `resolvedOutputPath` returned by the CLI instructions, inside
  `openspec/changes/<name>/`.
- **IMPORTANT**: `context` and `rules` from config.yaml guide what you write but must NEVER appear in the artifact
files.

**Guardrails**

- Create ALL artifacts the apply phase transitively depends on (follow the `requires` edges from `openspec status
  --json`), not just the ids in `apply.requires`
- Always read dependency artifacts before creating a new one — re-read from disk, not from conversation memory
- If context is critically unclear, ask the user - but prefer making reasonable decisions to keep momentum
- If a change with that name already exists, ask if user wants to continue it or create a new one
- Verify all artifacts exist with `openspec status` before declaring the propose flow complete

## Overview

Use this skill to create an OpenSpec change proposal and the artifacts needed before implementation.

## Shared Context

For ticketed changes, read `.codex/skills/_shared/delivery-contract.md` and `docs/conventions/context-management.md`
before creating artifacts. Keep proposal scope aligned with the active ticket or
explicit user request, and preserve validation and handoff expectations for implementation.

## Workflow Telemetry

Workflow telemetry is **mandatory** for this stage: before handoff, upsert the stage time entry with the standalone
script (shared pattern `.codex/skills/_shared/pipeline-workflow-telemetry.md`):

```bash
python -m tools.sdd_cli dev-flow telemetry-upsert --ticket-key {ticketKey} \
  --workflow-stage dev-flow-propose-change --agent-role proposeChange \
  --started-utc {startedUtc} --finished-utc {finishedUtc} --outcome {outcome}
```

The marker `IA generated workflow telemetry: {ticketKey}:dev-flow-propose-change` is written automatically. If the
upsert fails, stop and report before handoff.

## Workflow

### Knowledge Consult

Before creating proposal artifacts, consult the knowledge base for known errors, patterns, and lessons relevant to the
change's area:

```bash
python -m tools.sdd_cli knowledge-search search --query <change or feature area terms>
python -m tools.sdd_cli knowledge-search search --list-topics
```

Fold relevant entries into the proposal context, design notes, and risk analysis. Record `Knowledge consulted: <files>`
or `Knowledge consulted: none` in the proposal handoff.

Follow the proposal artifact creation steps above, capture resolved `grill-with-docs` planning knowledge in OpenSpec
instead of a separate context file, then route implementation through the
appropriate dev-flow skill.

## Output

Report the change name, artifacts created, validation performed, ready-to-implement status, and handoff notes.

## Failure Rules

Stop when the requested change is ambiguous, conflicts with the active ticket, cannot create required artifacts, or
requires implementation decisions that should be resolved before proposal handoff.
