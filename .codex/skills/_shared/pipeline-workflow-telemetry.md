<!-- TIER 3: STAGE-SPECIFIC - Workflow telemetry pattern, shared across all flow skills -->

# Pipeline — Workflow Telemetry

## Usage

Include this section in any delivery skill that needs time tracking. Replace the placeholders:

- `{workflowStage}` — the stage name (e.g. `dev-flow-implement-ticket`, `dev-flow-file-qa-bug`)
- `{agentRole}` — the agent role (e.g. `implementation`, `reviewFeedback`, `prReview`)

## Pattern

Capture UTC start time after resolving the ticket key and before beginning the stage work. Prefer OpenProject time-entry telemetry and create or update the `{workflowStage}` entry via the `time-telemetry-upsert` operation (see `.codex/providers/ticket.openproject.md` → Operations → `time-telemetry-upsert` for the exact API payload with `spentOn`, `hours`, `comment`, and `_links`).

Use marker: `IA generated workflow telemetry: {ticketKey}:{workflowStage}`

Resolve the activity href by running:

```bash
python -m tools.sdd_cli dev-flow resolve-openproject-activity --workflow-stage {workflowStage} --input-json '{"timeTelemetry":{...}}'
```

Then reverse-lookup the activity ID from the resolved name.

On resume or idempotent reuse, create or update another time entry for the same stage; workflow timing rendering collapses repeated stage rows into earliest start and latest finish. Include `workflowStage={workflowStage}`, `agentRole={agentRole}`, `startedUtc`, `finishedUtc`, `retryCount`, and `outcome`.

**Default failure rule:** If `time-telemetry-upsert` fails (returns a 4xx or 5xx error), stop and report the failure. Do not use any fallback mechanism unless the skill explicitly defines an alternative (e.g., JSONL fallback).

For shared API helpers including time-entry POST payload format and activity reverse-lookup, see `.codex/skills/_shared/api-helpers.md` → OpenProject → Workflow time telemetry.
