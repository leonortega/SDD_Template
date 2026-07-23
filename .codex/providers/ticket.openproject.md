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
- `enrich`: update only the managed generated block between `<!-- ia-generated:start -->` and `<!-- ia-generated:end -->` in the work package description. The original user-authored description MUST be preserved. See [Enrich pattern](#enrich-pattern) below for the exact format and PATCH payload.
- `move-state`: update `_links.status` to the configured target status and include the current `lockVersion`.
- `comment`: add generated comments as work package activities with the stable marker as the first line.
- `verify-marker`: re-read activities and verify the marker appears in activity comment text before reporting success.
- `time-telemetry-detect`: verify `/api/v3/time_entries` accepts work-package time-entry reads/writes for the authenticated user and that `openProject.timeTelemetry.enabled` is true with `activityFlow` mapping every OpenProject activity name to flow steps and each flow step resolving through `activityByStage.{workflowStage}.activityId` or resolvable `activityName`, falling back to `defaultActivityId` or `defaultActivityName`.
- `time-telemetry-list`: query `/api/v3/time_entries` filtered by `entity_type=WorkPackage` and `entity_id={workPackageId}`.
- `time-telemetry-upsert`: create or update generated time entries for workflow stage timing. Use marker `IA generated workflow telemetry: {ticketKey}:{workflowStage}` as the first line of the time-entry comment, link `_links.entity.href` to `/api/v3/work_packages/{workPackageId}`, set `_links.activity.href` from the resolved per-stage activity, set `spentOn` from `finishedUtc`, and set `hours` as an ISO-8601 duration from elapsed time.

## Enrich Pattern

The `enrich` operation uses a managed block delimited by HTML comments. The original description text is NEVER removed.

### Marker Format

The description is split into two zones:

```
text
[User-authored original description — preserved exactly as-is]

<!-- ia-generated:start -->
[AI-generated content — improved description, analysis, notes]
<!-- ia-generated:end -->
```

### Before Enrich (first time)

Original description from the user/author:

```
This ticket adds login with Google OAuth.
Users should be able to sign in with their Google account.
```

### After Enrich (first PATCH — markers are created)

The PATCH payload writes the FULL description including both zones:

```json
{
  "lockVersion": 1,
  "description": {
    "raw": "This ticket adds login with Google OAuth.\nUsers should be able to sign in with their Google account.\n\n<!-- ia-generated:start -->\n**AI Analysis & Improvements:**\n- Acceptance criteria should include: redirect handling, error states, token refresh\n- Consider adding rate limiting for the OAuth endpoint\n\n**Refined description:**\nImplement Google OAuth login flow. Users sign in via Google, the system handles token exchange, session creation, error states, and rate limiting.\n<!-- ia-generated:end -->"
  }
}
```

### After Enrich (subsequent updates)

Only the content between `<!-- ia-generated:start -->` and `<!-- ia-generated:end -->` changes. The user-authored portion stays intact:

```json
{
  "lockVersion": 2,
  "description": {
    "raw": "This ticket adds login with Google OAuth.\nUsers should be able to sign in with their Google account.\n\n<!-- ia-generated:start -->\n**AI Analysis & Improvements:**\n- Acceptance criteria should include: redirect handling, error states, token refresh\n- Consider adding rate limiting for the OAuth endpoint\n- Added: session timeout configuration per security review\n\n**Refined description:**\nImplement Google OAuth login flow. Users sign in via Google, the system handles token exchange, session creation, error states, rate limiting, and configurable session timeouts.\n<!-- ia-generated:end -->"
  }
}
```

### Implementation Steps for Agents

1. **Read** the work package description using `GET /api/v3/work_packages/{id}`. Extract the `lockVersion` and `description.raw`.
2. **Check** if `<!-- ia-generated:start -->` exists in the description:
   - **No markers**: Prepend the user-authored portion as-is, then append the markers with generated content.
   - **Has markers**: Keep everything before `<!-- ia-generated:start -->` unchanged. Replace only the content between `start` and `end`.
3. **Run `grill-with-docs` to sharpen understanding before writing.** Invoke the `grill-with-docs` skill to:
   - Interview the user on unclear aspects of the ticket (acceptance criteria, edge cases, dependencies).
   - Capture domain knowledge surfaced during the interview.
   - Write durable context to `docs/` or `.codex/memory/` as appropriate.
   - Use the clarified requirements to produce a richer, more accurate improved description.

   This step is especially important when the ticket has gaps, ambiguous language, or missing acceptance criteria. Skip the interactive grill step only when the description is already complete and unambiguous.

4. **Compose the improved content** using the knowledge gathered from `grill-with-docs` and any other relevant context (codebase exploration, existing docs, memory). Include:
   - Key clarifications or decisions made during the grill session.
   - Refined acceptance criteria.
   - A sharpened description that reflects the shared understanding.
5. **PATCH** the work package with the full reconstructed description and current `lockVersion`.

### CRITICAL — Common Mistakes to Avoid

- ❌ **Do NOT** replace the entire description — always preserve user-authored text before `<!-- ia-generated:start -->`.
- ❌ **Do NOT** omit the markers — without them, the next enrich cannot distinguish user text from generated text.
- ❌ **Do NOT** skip `lockVersion` — OpenProject rejects updates without the correct version.
- ❌ **Do NOT** write raw prompts, token counts, or tool output into the marker block. Keep it human-readable.

## Status Mapping

- New: `openProject.newStatus` (default: `New`)
- To Do: `openProject.todoStatus` (default: `To Do`)
- In Progress: `openProject.inProgressStatus` (default: `In Process`)
- In Review: `openProject.reviewStatus` (default: `In Process`)
- QA: `openProject.qaStatus` (default: `QA`)
- Done: `openProject.doneStatus` (default: `Done`)

## Failure Rules

- Stop before mutation when OpenProject config is missing, the work package is ambiguous, or the current status conflicts with the active delivery lock.
- OpenProject work package updates must include the current `lockVersion`.
- Do not read OpenProject data from containers, databases, or mounted volumes.
- OpenProject time entries are the primary workflow telemetry store when the API and resolved per-stage activity allow writes. If time-entry support, config, permissions, or schema validation fails, fall back to ignored `.codex/agent-telemetry.local.jsonl` and report the fallback reason.
- Raw prompts, token counts, credential-bearing URLs, secrets, and noisy tool output must not be stored in OpenProject time entries.
