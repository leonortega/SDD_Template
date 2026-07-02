# Ticket Adapter: OpenProject

Use this adapter only when `.codex/project-profile.json` selects `providers.ticket.id = "openproject"`.

## Runtime Configuration

- Read non-secret provider identity from `.codex/project-profile.json`.
- Read local endpoint, API token, project identifier, status names, and optional `openProject.timeTelemetry` per-stage activity config from `.codex/client-tools.local.json`.
- Use `.codex/client-tools.example.json` only for placeholder shape.
- Never print tokens, cookies, session values, or secret-bearing URLs.

## Authentication

Use OpenProject API v3 bearer token authentication:

```http
Authorization: Bearer {openProject.apiToken}
Accept: application/hal+json
Content-Type: application/json
```

## Operations

- `list`: query `/api/v3/projects/{projectIdentifier}/work_packages` with filters for the configured status.
- `read`: fetch the work package subject, description, status, activities, and `lockVersion`.
- `enrich`: update only the managed generated block between `<!-- ia-generated:start -->` and `<!-- ia-generated:end -->` in the work package description.
- `move-state`: update `_links.status` to the configured target status and include the current `lockVersion`.
- `comment`: add generated comments as work package activities with the stable marker as the first line.
- `verify-marker`: re-read activities and verify the marker appears in activity comment text before reporting success.
- `time-telemetry-detect`: verify `/api/v3/time_entries` accepts work-package time-entry reads/writes for the authenticated user and that `openProject.timeTelemetry.enabled` is true with `activityFlow` mapping every OpenProject activity name to flow steps and each flow step resolving through `activityByStage.{workflowStage}.activityId` or resolvable `activityName`, falling back to `defaultActivityId` or `defaultActivityName`.
- `time-telemetry-list`: query `/api/v3/time_entries` filtered by `entity_type=WorkPackage` and `entity_id={workPackageId}`.
- `time-telemetry-upsert`: create or update generated time entries for workflow stage timing. Use marker `IA generated workflow telemetry: {ticketKey}:{workflowStage}` as the first line of the time-entry comment, link `_links.entity.href` to `/api/v3/work_packages/{workPackageId}`, set `_links.activity.href` from the resolved per-stage activity, set `spentOn` from `finishedUtc`, and set `hours` as an ISO-8601 duration from elapsed time.

## Status Mapping

- Todo: `openProject.todoStatus`
- In Progress: `openProject.inProgressStatus`
- In Review: `openProject.reviewStatus`
- QA: `openProject.qaStatus`
- Done: `openProject.doneStatus`

## Failure Rules

- Stop before mutation when OpenProject config is missing, the work package is ambiguous, or the current status conflicts with the active delivery lock.
- OpenProject work package updates must include the current `lockVersion`.
- Do not read OpenProject data from containers, databases, or mounted volumes.
- OpenProject time entries are the primary workflow telemetry store when the API and resolved per-stage activity allow writes. If time-entry support, config, permissions, or schema validation fails, fall back to ignored `.codex/agent-telemetry.local.jsonl` and report the fallback reason.
- Raw prompts, token counts, credential-bearing URLs, secrets, and noisy tool output must not be stored in OpenProject time entries.
