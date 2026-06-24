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
