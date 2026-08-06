# OpenProject API Reference for Ticket Start

Use OpenProject API v3 for the chat-driven ticket workflow. Use `Authorization: Bearer <openProject.apiToken>` for every
request. Never print the token.

## Config Values

- `baseUrl`: e.g. `http://localhost:8080`
- `projectIdentifier`: e.g. `e2eproject`
- `featureStatus`: e.g. `Specified` (feature starting point, ID 3)
- `inProgressStatus`: e.g. `In progress` (lowercase p, ID 7)

## Read-Only Checks

Current user:

```text
GET {baseUrl}/api/v3/users/me
```

Resolve the configured project:

```text
GET {baseUrl}/api/v3/projects/{projectIdentifier}
```

List project work packages:

```text
GET {baseUrl}/api/v3/projects/{projectIdentifier}/work_packages
```

Fetch a work package:

```text
GET {baseUrl}/api/v3/work_packages/{workPackageId}
```

Read activities before writing generated markers:

```text
GET {baseUrl}/api/v3/work_packages/{workPackageId}/activities
```

## Mutations

Before mutating, ensure the Git branch exists, the generated description block is valid, and the latest work package
`lockVersion` is known.

### Update Generated Ticket Description Block

### ⚠️ CRITICAL: Preserve Original Human Text

The `description.raw` PATCH payload MUST include the original human-authored text followed by the IA generated block.
Never set `description.raw` to ONLY the generated content.

### First Creation (no markers yet)

Fetch the current description first. Then PATCH with the original text PLUS the new generated block:

```text
PATCH {baseUrl}/api/v3/work_packages/{workPackageId}
```

Payload:

```json
{
  "lockVersion": 7,
  "description": {
    "raw": "This is the original human-authored description.\nIt describes what the ticket should accomplish.\n\n---\n\nIA generated\n\n<!-- ia-generated:start -->\n**AI Analysis:**\n- Acceptance criteria need to cover edge cases\n- Consider error handling\n<!-- ia-generated:end -->"
  }
}
```

### Subsequent Updates (markers exist)

Fetch the current description, keep everything before `<!-- ia-generated:start -->` unchanged, replace only the content
between the markers:

```text
PATCH {baseUrl}/api/v3/work_packages/{workPackageId}
```

Payload:

```json
{
  "lockVersion": 8,
  "description": {
    "raw": "This is the original human-authored description.\nIt describes what the ticket should accomplish.\n\n---\n\nIA generated\n\n<!-- ia-generated:start -->\n**Updated AI Analysis:**\n- Added rate limiting to acceptance criteria\n- Security review completed\n<!-- ia-generated:end -->"
  }
}
```

### Add Branch Comment

```text
POST {baseUrl}/api/v3/work_packages/{workPackageId}/activities
```

Payload:

```json
{
  "comment": {
    "raw": "IA generated branch: {branchName}\n\n**Status:** ..."
  }
}
```

### Move Ticket to In progress

```text
PATCH {baseUrl}/api/v3/work_packages/{workPackageId}
```

Payload:

```json
{
  "lockVersion": 7,
  "_links": {
    "status": {
      "href": "/api/v3/statuses/{statusId}"
    }
  }
}
```

Resolve the target status by exact configured name before updating. If the work package is already in the target status,
skip the update.

## Idempotency

- Before adding a branch comment, read existing activities and skip if the same `IA generated branch: {branchName}`
marker already exists.
- Before moving status, compare the current status name/link to the target status.
- Before updating description, replace only the block between `<!-- ia-generated:start -->` and `<!-- ia-generated:end
-->`. Preserve all human-written text outside the markers.
