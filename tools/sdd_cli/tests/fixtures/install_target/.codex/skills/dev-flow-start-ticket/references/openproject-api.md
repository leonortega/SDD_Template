# OpenProject API Reference for Ticket Start

Use OpenProject API v3 for the chat-driven ticket workflow. Use `Authorization: Bearer <openProject.apiToken>` for every request. Never print the token.

## Config Values

- `baseUrl`: e.g. `http://localhost:8080`
- `projectIdentifier`: e.g. `e2eproject`
- `todoStatus`: e.g. `Todo`
- `inProgressStatus`: e.g. `In Progress`

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

Before mutating, ensure the Git branch exists, the generated description block is valid, and the latest work package `lockVersion` is known.

Update generated ticket description block:

```text
PATCH {baseUrl}/api/v3/work_packages/{workPackageId}
```

Payload:

```json
{
  "lockVersion": 7,
  "description": {
    "raw": "..."
  }
}
```

Add branch comment:

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

Move ticket to In Progress:

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

Resolve the target status by exact configured name before updating. If the work package is already in the target status, skip the update.

## Idempotency

- Before adding a branch comment, read existing activities and skip if the same `IA generated branch: {branchName}` marker already exists.
- Before moving status, compare the current status name/link to the target status.
- Before updating description, replace only the block between `<!-- ia-generated:start -->` and `<!-- ia-generated:end -->`.
