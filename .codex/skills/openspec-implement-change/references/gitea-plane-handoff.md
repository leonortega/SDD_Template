# Gitea And Plane Handoff Reference

Use bearer-style token auth for Gitea:

```text
Authorization: token <gitea.apiToken>
```

Use Plane API key auth:

```text
X-API-Key: <plane.apiToken>
```

Never print token values.

## Gitea Repository

Resolve `owner` and `repo` from config first. If either is missing, parse `git remote get-url origin`.

Supported origin examples:

```text
http://localhost:3000/leon/SDD_template.git
git@localhost:leon/SDD_template.git
ssh://git@localhost:2222/leon/SDD_template.git
```

Normalize the repository name by removing a trailing `.git`.

## Pull Requests

List open PRs:

```text
GET {gitea.baseUrl}/api/v1/repos/{owner}/{repo}/pulls?state=open
```

Create a PR:

```text
POST {gitea.baseUrl}/api/v1/repos/{owner}/{repo}/pulls
```

Payload:

```json
{
  "base": "dev",
  "head": "feat/example",
  "title": "Example title",
  "body": "Commit change list and validation summary.",
  "reviewers": ["developer1", "developer2"]
}
```

If reviewers cannot be resolved, omit the `reviewers` property and document that in the body.

## Reviewers

When `pr.reviewers` is `"all"`, list repository collaborators:

```text
GET {gitea.baseUrl}/api/v1/repos/{owner}/{repo}/collaborators
```

Use the returned usernames as the developer list. Exclude:

- PR author
- authenticated automation user
- empty, disabled, or duplicate usernames

When `pr.reviewers` is an array, use that array exactly after trimming empty values.

## Labels

Configured labels are optional but enabled by default. Ensure each configured label exists before applying it.

List labels:

```text
GET {gitea.baseUrl}/api/v1/repos/{owner}/{repo}/labels
```

Create a missing label:

```text
POST {gitea.baseUrl}/api/v1/repos/{owner}/{repo}/labels
```

Payload:

```json
{
  "name": "codex-reviewed",
  "color": "#5319e7"
}
```

Apply labels to the PR by using the issue labels endpoint because Gitea PRs are issues:

```text
POST {gitea.baseUrl}/api/v1/repos/{owner}/{repo}/issues/{prNumber}/labels
```

Payload:

```json
{
  "labels": [123]
}
```

Default label meanings:

- `codex-reviewed`: review agent posted a review for the PR head SHA.
- `needs-tests`: review found missing or failing tests.
- `needs-changes`: review found actionable defects or blocking concerns.

## Plane Review State

Resolve `projectIdentifier` to a project UUID:

```text
GET {plane.baseUrl}/api/v1/workspaces/{workspaceSlug}/projects/
```

Resolve project states and find `plane.reviewState` by exact name, default `In Review`:

```text
GET {plane.baseUrl}/api/v1/workspaces/{workspaceSlug}/projects/{projectUuid}/states/
```

Move the work item:

```text
PATCH {plane.baseUrl}/api/v1/workspaces/{workspaceSlug}/projects/{projectUuid}/work-items/{workItemUuid}/
```

Payload must set the state to the resolved state id. If the target state does not exist, stop and report the missing configuration.

Add the PR link comment:

```text
POST {plane.baseUrl}/api/v1/workspaces/{workspaceSlug}/projects/{projectUuid}/work-items/{workItemUuid}/comments/
```

Use a stable marker:

```text
IA generated PR: {prUrl}
```

Before adding the comment, read existing comments when the API allows it and skip if the same marker already exists.
