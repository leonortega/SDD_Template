# Plane API Reference for Ticket Start

Use these endpoint patterns for the chat-driven ticket workflow. Use `X-API-Key: <plane.apiToken>` for every request. Never print the token.

## Config Values

- `baseUrl`: e.g. `http://agentic.lvh.me:8080`
- `workspaceSlug`: lowercase slug from the Plane URL, e.g. `e2etest`
- `projectIdentifier`: e.g. `E2EPROJECT`
- `todoState`: e.g. `Todo`
- `inProgressState`: e.g. `In Progress`

## Read-Only Checks

Current user:

```text
GET {baseUrl}/api/v1/users/me/
```

List projects and resolve `projectIdentifier` to UUID:

```text
GET {baseUrl}/api/v1/workspaces/{workspaceSlug}/projects/
```

Ticket lookup by key:

```text
GET {baseUrl}/api/v1/workspaces/{workspaceSlug}/work-items/{ticketKey}/?expand=state,project
```

Search work items:

```text
GET {baseUrl}/api/v1/workspaces/{workspaceSlug}/work-items/search/?search={query}
```

Project-scoped work item list:

```text
GET {baseUrl}/api/v1/workspaces/{workspaceSlug}/projects/{projectUuid}/work-items/?expand=state,project
```

## Mutations

Before mutating, ensure the Git branch exists and the generated description block is valid.

Update generated ticket description block:

```text
PATCH {baseUrl}/api/v1/workspaces/{workspaceSlug}/projects/{projectUuid}/work-items/{workItemUuid}/
```

Set generated estimate when missing:

```text
PATCH {baseUrl}/api/v1/workspaces/{workspaceSlug}/projects/{projectUuid}/work-items/{workItemUuid}/
```

Payload:

```json
{
  "point": 3
}
```

Only send this patch when the fetched work item has null or empty `point` and `estimate_point`. Preserve any non-empty `point` or `estimate_point` value.

Add branch comment:

```text
POST {baseUrl}/api/v1/workspaces/{workspaceSlug}/projects/{projectUuid}/work-items/{workItemUuid}/comments/
```

Payload:

```json
{
  "comment_html": "<p>IA generated branch: {branchName}</p><p>**Status:** ...</p>",
  "comment_stripped": "IA generated branch: {branchName}\n\n**Status:** ..."
}
```

Do not send a `comment` or `body` field. Plane work-item comments render from `comment_html`; the stable marker must also be present at the start of `comment_stripped` so later workflow runs can detect it. Read the comment back after posting and verify `comment_stripped` starts with the marker.

Use a stable generated marker in the comment body:

```text
IA generated branch: {branchName}
```

Move ticket to In Progress:

```text
PATCH {baseUrl}/api/v1/workspaces/{workspaceSlug}/projects/{projectUuid}/work-items/{workItemUuid}/
```

Payload must set the state to the resolved state id. Resolve states by project before updating. If the ticket is already in the target state, skip the update.

## Idempotency

- Before adding a branch comment, read existing comments if the API allows it and skip if the same `IA generated branch: {branchName}` marker already exists.
- Before moving state, compare the current state name/id to the target state.
- Before updating description, replace only the block between `<!-- ia-generated:start -->` and `<!-- ia-generated:end -->`.
- Before setting `point`, compare the current `point` and `estimate_point` values and skip the patch when either is already non-empty.
