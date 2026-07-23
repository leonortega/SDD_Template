# Gitea And OpenProject Handoff Reference

Use bearer-style token auth for Gitea:

```text
Authorization: token <gitea.apiToken>
```

Use OpenProject API v3 bearer token auth:

```text
Authorization: Bearer <openProject.apiToken>
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

After creating or reusing the PR, verify the requested reviewers on the PR response. If eligible reviewers were resolved but are missing from the response, request them explicitly:

```text
POST {gitea.baseUrl}/api/v1/repos/{owner}/{repo}/pulls/{prNumber}/requested_reviewers
```

Payload:

```json
{
  "reviewers": ["developer1", "developer2"]
}
```

Then re-fetch the PR and verify the requested reviewers are present before moving the OpenProject work package to review. If Gitea rejects the request, document the reviewer gap in the PR body, OpenProject handoff comment, and final summary.

## Reviewers

When `pr.reviewers` is `"all"`, list repository collaborators:

```text
GET {gitea.baseUrl}/api/v1/repos/{owner}/{repo}/collaborators
```

Normalize the response before filtering because Gitea may return either a JSON array or a single collaborator object. Use each collaborator's `login` value first, then `username`, as the developer list. Exclude:

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

## OpenProject Review State

Resolve the configured project:

```text
GET {openProject.baseUrl}/api/v3/projects/{projectIdentifier}
```

Fetch the work package and current `lockVersion`:

```text
GET {openProject.baseUrl}/api/v3/work_packages/{workPackageId}
```

Resolve the status whose name equals `openProject.reviewStatus`, default `In Review`, then move the work package:

```text
PATCH {openProject.baseUrl}/api/v3/work_packages/{workPackageId}
```

Payload must set `_links.status` to the resolved status link and include the current `lockVersion`. If the target status does not exist, stop and report the missing configuration.

Add the PR link comment:

```text
POST {openProject.baseUrl}/api/v3/work_packages/{workPackageId}/activities
```

Payload:

```json
{
  "comment": {
    "raw": "IA generated PR: {prUrl}\n\n**Status:** ..."
  }
}
```

After posting, read activities back and verify the activity comment starts with the stable marker.

Use a stable marker:

```text
IA generated PR: {prUrl}
```

Before adding the comment, read existing activities when the API allows it and skip if the same marker already exists.
