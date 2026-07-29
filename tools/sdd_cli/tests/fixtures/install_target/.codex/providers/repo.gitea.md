# Repository And Review Adapter: Gitea

Use this adapter only when `.codex/project-profile.json` selects `providers.repository.id` or `providers.review.id = "gitea"`.

## Runtime Configuration

- Read non-secret branch and workflow policy from `.codex/project-profile.json`.
- Read local endpoint, token, owner, repository, reviewers, and labels from `.codex/client-tools.local.json`.
- Keep workflow job images and exact versions in `.gitea/workflows/*.yml`.
- Never print tokens or credential-bearing remote URLs.

## Operations

- `branch`: create or reuse the ticket branch from the configured base branch.
- `push`: push only scoped changes from the active worktree.
- `pull-request`: create or read the PR linked to the active ticket/branch.
- `status`: read PR checks, labels, reviews, and head SHA.
- `label`: apply configured review labels without inventing new labels.
- `comment`: post generated review/handoff comments.
- `request-reviewers`: request configured human reviewers and verify the PR reflects them.

## Failure Rules

- Stop when the branch, PR, head SHA, labels, or requested reviewers do not match the delivery lock.
- Do not treat an agent review comment as a human reviewer request.
- Do not force-push, rewrite history, or alter unrelated branches unless explicitly requested.
