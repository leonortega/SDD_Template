<!-- TIER 3: STAGE-SPECIFIC - Workflow telemetry pattern, shared across all flow skills -->

# Pipeline — Workflow Telemetry

## Usage

Workflow telemetry is a **mandatory step at the end of every delivery stage**: each stage upserts its OpenProject
time-entry row before handoff. Include this section in any delivery skill that needs time tracking. Replace the
placeholders:

- `{workflowStage}` — the stage name (e.g. `dev-flow-implement-ticket`, `dev-flow-file-qa-bug`, `qa-gate`)
- `{agentRole}` — the agent role (e.g. `implementation`, `reviewFeedback`, `prReview`, `e2eQa`, `deployToProd`)

## Pattern

Capture UTC start time after resolving the ticket key and before beginning the stage work (`startedUtc`). At the
**end** of the stage (before handoff), upsert the stage time entry with the standalone script — one command per stage:

```bash
python -m tools.sdd_cli dev-flow telemetry-upsert \
  --ticket-key {ticketKey} --workflow-stage {workflowStage} --agent-role {agentRole} \
  --started-utc {startedUtc} --finished-utc {finishedUtc} --outcome {outcome} \
  [--retry-count N] [--work-package-id {workPackageId}] [--activity-id {activityId}] \
  [--jsonl-fallback true]
```

The script (repo `tools/sdd_cli/workflow_telemetry.py`, exposed as the `dev-flow telemetry-upsert` subcommand)
encapsulates the whole pattern:

- resolves the activity ID — explicit `--activity-id`, or client-tools `timeTelemetry` config, or the default per-stage
  mapping (e.g. Development for implementation/deploy, Testing for verify/QA, Support for rollback/hotfix)
- resolves the work package and user hrefs via the OpenProject API when not passed explicitly
- builds the time-entry payload (`POST /api/v3/time_entries`, Bearer auth from `client-tools.local.json`, `spentOn` +
  `hours` derived from `startedUtc`/`finishedUtc`, canonical comment marker below)
- fails loud on API errors by default; only a skill that explicitly defines the JSONL alternative passes
  `--jsonl-fallback true` to record to the ignored `.codex/agent-telemetry.local.jsonl` instead

Use marker (written automatically as the first comment line):

`IA generated workflow telemetry: {ticketKey}:{workflowStage}`

On resume or idempotent reuse, run the upsert again with a new `startedUtc`/`finishedUtc`; workflow timing rendering
collapses repeated stage rows into earliest start and latest finish. Include `retryCount` and `outcome`.

**Default failure rule:** the script stops and reports (exit 1) when required arguments are missing, when timestamps
are not ISO-8601, when the API is unreachable, or when it cannot resolve the activity. JSONL fallback is **opt-in**
(`--jsonl-fallback true`) and only skills that explicitly define the JSONL alternative may use it. Do not invent other
fallbacks.

For the raw API contract (payload fields, activity IDs, reverse-lookup), see
`.codex/skills/openproject-sprint-backlog/references/openproject-api.md` → Operations → `time-telemetry-upsert`, and
`.codex/skills/_shared/api-helpers.md` → OpenProject → Workflow time telemetry.
