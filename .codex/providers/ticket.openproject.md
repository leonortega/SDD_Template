# Ticket Adapter: OpenProject

Use this adapter only when `.codex/project-profile.json` selects `providers.ticket.id = "openproject"`.

## Runtime Configuration

- Read non-secret provider identity from `.codex/project-profile.json`.
- Read local endpoint, API token, project identifier, and status names from `.codex/client-tools.local.json` under `openProject`.
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
