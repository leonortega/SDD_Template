<!-- TIER 3: STAGE-SPECIFIC - OpenProject ticket comment pattern, shared across all flow skills -->

# Pipeline — Ticket Comment (OpenProject)

## Usage

Use this pattern whenever a flow skill needs to add a comment to an OpenProject work package and verify it was created.
Replace the placeholders:

- `{workPackageId}` — the work package ID (numeric)
- `{marker}` — the stable marker (e.g. `IA generated PR: {prUrl}`)
- `{commentRaw}` — the full comment body (marker on first line, then blank line, then Markdown body)
- `{severity}` — `blocking` (stop flow on failure) or `advisory` (log and continue)

## Pattern

### Create a comment

```text
POST {openProject.baseUrl}/api/v3/work_packages/{workPackageId}/activities
```

Payload:

```json
{
  "comment": {
    "raw": "{marker}\n\n{commentRaw}"
  }
}
```

### Verify the comment was created

```text
GET {openProject.baseUrl}/api/v3/work_packages/{workPackageId}/activities
```

Check if any activity comment starts with the marker text. If the marker is found, the comment was created successfully.

### Retry logic

1. POST the comment.
2. GET activities and check for marker.
3. If marker NOT found:
   - If this is the **first attempt**: retry the POST once, then GET activities again and re-check.
   - If retry also fails:
     - **Blocking severity**: stop the flow. Report the failure. Do not proceed to the next stage.
     - **Advisory severity**: log the error, document the gap in the final summary, and continue.

### Headers for all requests

```text
Authorization: Bearer {openProject.apiToken}
Accept: application/hal+json
Content-Type: application/json
```

### Reading existing comments before writing

Before creating a new comment with a known marker, read existing activities. If any activity already starts with the
same marker, skip the POST — the comment was already created in a previous run.
