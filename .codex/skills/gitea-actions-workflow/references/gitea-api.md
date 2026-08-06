# Repository And Review Adapter: Gitea

Use this adapter only when `.codex/project-profile.json` selects `providers.repository.id` or `providers.review.id =
"gitea"`.

## Runtime Configuration

- Read non-secret branch and workflow policy from `.codex/project-profile.json`.
- Read local endpoint, token, owner, repository, reviewers, and labels from `.codex/client-tools.local.json`.
- Keep workflow job images and exact versions in `.gitea/workflows/*.yml`.
- Never print tokens or credential-bearing remote URLs.

## API Token

The Gitea API token (`gitea.apiToken`) must have the following scopes for the agent to perform all operations:

| Scope | Required For |
|---|---|
| `write:repository` | Pushing code, creating branches |
| `write:issue` | Adding labels (PRs are issues in Gitea) |
| `write:pull_request` | Creating PRs, requesting reviewers |

### Auto-generation

During `setup-lab` → `provision-lab-users`, the token is automatically generated via `POST /api/v1/users/admin/tokens`
using the built-in admin credentials (`admin`/`admin123`). The token is written to `.codex/client-tools.local.json`
under `gitea.apiToken`.

### Manual generation

If the token needs to be regenerated, run:

```bash
python -m tools.sdd_cli environment-lab generate-gitea-token
```

### Token verification & renewal

Verify the current token is still valid:

```bash
python -m tools.sdd_cli environment-lab verify-gitea-token
```

Renovate (verify + generate new if invalid) in one command:

```bash
python -m tools.sdd_cli environment-lab renovate-gitea-token
```

## Operations

- `branch`: create or reuse the ticket branch from the configured base branch.
- `push`: push only scoped changes from the active worktree.
- `pull-request`: create or read the PR linked to the active ticket/branch.
- `status`: read PR checks, labels, reviews, and head SHA.
- `label`: apply configured review labels without inventing new labels.
- `comment`: post generated review/handoff comments.
- `request-reviewers`: request configured human reviewers and verify the PR reflects them.

### `request-reviewers` Operation Details

PR create payload may include a `reviewers` property:

```text
POST {gitea.baseUrl}/api/v1/repos/{owner}/{repo}/pulls
```

```json
{
  "base": "dev",
  "head": "feat/example",
  "title": "Example title",
  "body": "Description",
  "reviewers": ["developer1", "developer2"]
}
```

**Important:** Gitea may ignore the `reviewers` property in the create payload. Always verify after creation and call
the dedicated endpoint if reviewers are missing.

After creating or reusing the PR, inspect the PR response for `requested_reviewers`. If eligible reviewers were resolved
but are missing, request them explicitly:

```text
POST {gitea.baseUrl}/api/v1/repos/{owner}/{repo}/pulls/{prNumber}/requested_reviewers
```

Payload:

```json
{
  "reviewers": ["developer1", "developer2"]
}
```

Then re-fetch the PR and verify the requested reviewers appear in `requested_reviewers`. If Gitea rejects the request
(e.g. 404, 422), document the reviewer gap in the PR body, ticket handoff comment, and final summary.

When `pr.reviewers` is `"all"`, list repository collaborators:

```text
GET {gitea.baseUrl}/api/v1/repos/{owner}/{repo}/collaborators
```

Normalize the response before filtering because Gitea may return either a JSON array or a single collaborator object.
Use each collaborator's `login` value first, then `username`, as the developer list. Exclude:

- PR author
- authenticated automation user
- empty, disabled, or duplicate usernames

When `pr.reviewers` is an array, use that array exactly after trimming empty values.

## Failure Rules

- Stop when the branch, PR, head SHA, labels, or requested reviewers do not match the delivery lock.
- Do not treat an agent review comment as a human reviewer request.
- Do not force-push, rewrite history, or alter unrelated branches unless explicitly requested.
