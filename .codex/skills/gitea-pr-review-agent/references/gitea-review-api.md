# Gitea PR Review API Reference

Use Gitea token auth:

```text
Authorization: token <gitea.apiToken>
```

Never print token values.

## PR Lookup

List open PRs:

```text
GET {gitea.baseUrl}/api/v1/repos/{owner}/{repo}/pulls?state=open
```

Get one PR:

```text
GET {gitea.baseUrl}/api/v1/repos/{owner}/{repo}/pulls/{index}
```

List PR commits:

```text
GET {gitea.baseUrl}/api/v1/repos/{owner}/{repo}/pulls/{index}/commits
```

Fetch PR diff:

```text
GET {gitea.baseUrl}/{owner}/{repo}/pulls/{index}.diff
```

Fetch existing comments through the issue comments endpoint:

```text
GET {gitea.baseUrl}/api/v1/repos/{owner}/{repo}/issues/{index}/comments
```

Fetch pull request reviews and inline review comments when supported by the configured Gitea version:

```text
GET {gitea.baseUrl}/api/v1/repos/{owner}/{repo}/pulls/{index}/reviews
GET {gitea.baseUrl}/api/v1/repos/{owner}/{repo}/pulls/{index}/reviews/{reviewId}/comments
```

Treat human-authored top-level comments, inline code comments, and review-thread replies as implementation feedback. Exclude generated comments such as `<!-- codex-review-agent:{headSha} -->`, `IA generated PR feedback detected: {headSha}:{feedbackBatchId}`, `IA generated PR feedback fixes: {headSha}:{feedbackBatchId}`, and other Plane stable markers from human-feedback fix requirements.

## Review Comment

Post a top-level PR comment:

```text
POST {gitea.baseUrl}/api/v1/repos/{owner}/{repo}/issues/{index}/comments
```

Payload:

```json
{
  "body": "<!-- codex-review-agent:{headSha} -->\nReview findings..."
}
```

Skip posting if an existing comment contains the same marker for the same head SHA.

Every AI finding in the review body must include a stable finding id for the inspected head SHA, such as `AI-001`, so the implementation workflow can compute a deterministic feedback batch id from sorted source ids.

## Labels

List labels:

```text
GET {gitea.baseUrl}/api/v1/repos/{owner}/{repo}/labels
```

Create missing labels:

```text
POST {gitea.baseUrl}/api/v1/repos/{owner}/{repo}/labels
```

Payload:

```json
{
  "name": "needs-changes",
  "color": "#d73a4a"
}
```

Apply labels to the PR:

```text
POST {gitea.baseUrl}/api/v1/repos/{owner}/{repo}/issues/{index}/labels
```

Payload uses label ids:

```json
{
  "labels": [123, 456]
}
```

Default colors:

- `codex-reviewed`: `#5319e7`
- `needs-tests`: `#fbca04`
- `needs-changes`: `#d73a4a`
