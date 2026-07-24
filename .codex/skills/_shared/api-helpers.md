<!-- TIER 3: STAGE-SPECIFIC - API helper patterns, loaded when stage needs API calls -->

# Shared Delivery API Helpers

Use these patterns for repeated OpenProject, Gitea, Nexus, and Git operations. Load credentials from `.codex/client-tools.local.json` or approved environment overrides. Never print tokens or credential-bearing URLs.

## OpenProject

Headers:

```text
Authorization: Bearer {openProject.apiToken}
Accept: application/hal+json
Content-Type: application/json
```

Resolve the configured project:

```text
GET {openProject.baseUrl}/api/v3/projects/{projectIdentifier}
```

List candidate work packages:

```text
GET {openProject.baseUrl}/api/v3/projects/{projectIdentifier}/work_packages
```

Fetch one work package:

```text
GET {openProject.baseUrl}/api/v3/work_packages/{workPackageId}
```

Read activities before writing generated markers:

```text
GET {openProject.baseUrl}/api/v3/work_packages/{workPackageId}/activities
```

Patch description or status:

```text
PATCH {openProject.baseUrl}/api/v3/work_packages/{workPackageId}
```

Status payload:

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

Description payload:

```json
{
  "lockVersion": 7,
  "description": {
    "raw": "..."
  }
}
```

Create generated comments:

```text
POST {openProject.baseUrl}/api/v3/work_packages/{workPackageId}/activities
```

Payload:

```json
{
  "comment": {
    "raw": "IA generated marker...\n\nStatus: ..."
  }
}
```

After posting a generated marker, read activities back and verify the comment text starts with the marker before reporting success.

Workflow time telemetry uses OpenProject time entries first when the selected ticket adapter supports them and `openProject.timeTelemetry.enabled` is true:

```text
GET {openProject.baseUrl}/api/v3/time_entries
POST {openProject.baseUrl}/api/v3/time_entries
PATCH {openProject.baseUrl}/api/v3/time_entries/{timeEntryId}
GET {openProject.baseUrl}/api/v3/time_entries/activities/{activityId}     # note: plural "activities"
```

For the full API contract including required fields, activity ID mappings, and reverse-lookup from name to ID, see the `time-telemetry-upsert` operation in `.codex/providers/ticket.openproject.md`.

List existing generated telemetry with filters for `entity_type=WorkPackage` and `entity_id={workPackageId}`. Create a time entry via `POST /api/v3/time_entries` with payload:

```json
{
  "spentOn": "YYYY-MM-DD",
  "hours": "PTnHnM",
  "comment": {"raw": "IA generated workflow telemetry: {ticketKey}:{workflowStage}"},
  "_links": {
    "user": {"href": "/api/v3/users/{userId}"},
    "entity": {"href": "/api/v3/work_packages/{workPackageId}"},
    "project": {"href": "/api/v3/projects/{projectIdentifier}"},
    "activity": {"href": "/api/v3/time_entries/activities/{activityId}"}
  }
}
```

Resolve the activity href via:
1. Run `python -m tools.sdd_cli dev-flow resolve-openproject-activity --workflow-stage {stage} --input-json '{...}'` to get the `activityName` from `client-tools.local.json` config.
2. Look up the numeric activity ID from the name using the mapping in `ticket.openproject.md` (e.g. "Specification" → 2, "Development" → 3).
3. Construct the href as `/api/v3/time_entries/activities/{id}`.

If the time-entry API, permissions, or resolved per-stage activity cannot be used, record the fallback reason and use ignored `.codex/agent-telemetry.local.jsonl`.

## Gitea

Headers:

```text
Authorization: token {gitea.apiToken}
```

Find PRs by head branch:

```text
GET {gitea.baseUrl}/api/v1/repos/{owner}/{repo}/pulls?state=open
GET {gitea.baseUrl}/api/v1/repos/{owner}/{repo}/pulls?state=closed
```

Fetch one PR and commits:

```text
GET {gitea.baseUrl}/api/v1/repos/{owner}/{repo}/pulls/{index}
GET {gitea.baseUrl}/api/v1/repos/{owner}/{repo}/pulls/{index}/commits
```

Fetch issue comments and labels:

```text
GET {gitea.baseUrl}/api/v1/repos/{owner}/{repo}/issues/{index}/comments
GET {gitea.baseUrl}/api/v1/repos/{owner}/{repo}/issues/{index}/labels
```

Request reviewers for a PR (always verify after PR create — Gitea may ignore the `reviewers` property in the create payload):

```text
POST {gitea.baseUrl}/api/v1/repos/{owner}/{repo}/pulls/{index}/requested_reviewers
```

Payload:

```json
{
  "reviewers": ["username1", "username2"]
}
```

List repository collaborators (when `pr.reviewers` is `"all"`):

```text
GET {gitea.baseUrl}/api/v1/repos/{owner}/{repo}/collaborators
```

Normalize the response before filtering: Gitea may return either a JSON array or a single collaborator object. Use each collaborator's `login` value first, then `username`. Exclude the PR author, the authenticated automation user, and empty/disabled/duplicate usernames.

Apply labels by id:

```text
POST {gitea.baseUrl}/api/v1/repos/{owner}/{repo}/issues/{index}/labels
```

## Nexus

Artifact paths are defined in `delivery-contract.md`. Use the configured base URL and repository:

```text
{nexus.baseUrl}/repository/{nexus.repository}/app/{commitSha}/deployable-apps.json
{nexus.baseUrl}/repository/{nexus.repository}/app/{commitSha}/{artifactName}
{nexus.baseUrl}/repository/{nexus.repository}/app/{commitSha}/{artifactName}.sha256
{nexus.baseUrl}/repository/{nexus.repository}/app/{commitSha}/commit.sha
{nexus.baseUrl}/repository/{nexus.repository}/app/{commitSha}/release.json
```

Use HTTP basic auth with `nexus.username` and `nexus.password`. Treat 401, 403, 404, checksum mismatch, or `commit.sha` mismatch as blocking for promotion.

## Git

Branch conflict pre-scan:

```powershell
git show-ref --verify refs/heads/{branchName}
git ls-remote --heads origin {branchName}
```

Check whether evidence is ignored:

```powershell
git check-ignore -q -- artifacts/qa/{ticketKey}/{runId}/qa-summary.md
```

Tag inspection for RC/final versions:

```powershell
git tag --list "v*"
git rev-parse {tag}^{commit}
git for-each-ref refs/tags/{tag} --format="%(objecttype)"
```
