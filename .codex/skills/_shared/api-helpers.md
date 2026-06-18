# Shared Delivery API Helpers

Use these patterns for repeated Plane, Gitea, Nexus, and Git operations. Load credentials from `.codex/client-tools.local.json` or approved environment overrides. Never print tokens or credential-bearing URLs.

## Plane

Headers:

```text
X-API-Key: {plane.apiToken}
```

Resolve project UUID from configured identifier:

```text
GET {plane.baseUrl}/api/v1/workspaces/{workspaceSlug}/projects/
```

Fetch ticket with expanded state/project:

```text
GET {plane.baseUrl}/api/v1/workspaces/{workspaceSlug}/work-items/{ticketKey}/?expand=state,project
```

Read comments before writing generated markers:

```text
GET {plane.baseUrl}/api/v1/workspaces/{workspaceSlug}/projects/{projectUuid}/work-items/{workItemUuid}/comments/
```

Patch description or state:

```text
PATCH {plane.baseUrl}/api/v1/workspaces/{workspaceSlug}/projects/{projectUuid}/work-items/{workItemUuid}/
```

State payload:

```json
{
  "state": "{stateUuid}"
}
```

Use the resolved state UUID in the `state` field. Do not use `state_id`; Plane accepts the request but does not move the work item state.

Create generated comments:

```text
POST {plane.baseUrl}/api/v1/workspaces/{workspaceSlug}/projects/{projectUuid}/work-items/{workItemUuid}/comments/
```

Payload:

```json
{
  "comment_html": "<p>IA generated marker...</p>",
  "comment_stripped": "IA generated marker...\n\nStatus: ..."
}
```

Plane work-item comments render from `comment_html` and expose searchable text through `comment_stripped`. Do not send a Gitea-style `comment` or `body` field; it can create a blank `<p></p>` Plane comment. After posting or patching a generated marker, read the comment back and verify `comment_stripped` starts with the stable marker before reporting success.

Repair an accidentally blank generated comment:

```text
PATCH {plane.baseUrl}/api/v1/workspaces/{workspaceSlug}/projects/{projectUuid}/work-items/{workItemUuid}/comments/{commentUuid}/
```

Use the same `comment_html` and `comment_stripped` payload shape.

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
