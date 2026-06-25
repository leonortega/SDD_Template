# Gitea PR Automation Configuration

Owns:

- `.codex/client-tools.local.json` Gitea and PR sections.
- Gitea API token guidance.
- Repository owner/name, reviewers, and review labels.

Use the shared script:

```bash
python -m tools.sdd_cli configure Audit
python -m tools.sdd_cli configure SetClientTools --values-json $values
```

## Required Values

Ask only when missing, placeholder, or not inferable:

- `gitea.baseUrl`: usually `http://localhost:3000`.
- `gitea.apiToken`: personal access token with repository, issue/PR, user, and organization read access. Never print it.
- `gitea.owner`: repository owner, inferred from `git remote get-url origin` when possible.
- `gitea.repo`: repository name, inferred from the remote when possible.
- `pr.reviewers`: default `"all"` unless the user wants fixed reviewers.
- `pr.minimumApprovals.dev`: default `1`; use this value for the `dev` branch protection Required approvals.
- `pr.minimumApprovals.main`: default `1`; use this value for the `main` branch protection Required approvals.
- `pr.labels.enabled`: default `true`.
- `pr.labels.reviewed`: default `codex-reviewed`.
- `pr.labels.needsTests`: default `needs-tests`.
- `pr.labels.needsChanges`: default `needs-changes`.

## Prompting

Ask for `gitea.apiToken` only if missing or placeholder.

How to get it: open Gitea at `http://localhost:3000`, log in, open user Settings, choose Applications, generate a token with repository and PR/comment/label access, then copy it once.

Do not retrieve or generate this token from Docker containers, databases, mounted volumes, or logs.

## Live Validation

Live validation requires local infra to be running. Ask before running `python -m tools.sdd_cli infra up`.

Validate:

- Token can access the current user endpoint.
- Owner/repo exists.
- If `pr.reviewers = "all"`, collaborators can be listed and at least one reviewer is resolvable after normalizing either an array response or a single collaborator object, using `login` first and `username` second.
- Branch protection for `dev` and `main` matches `pr.minimumApprovals.dev/main` when branch protection can be read.
- If labels are enabled, labels can be listed. Missing labels may be created later by the review workflow; do not create labels during configuration unless explicitly requested.

Configuration validation proves that reviewers can be resolved. Ticket handoff remains responsible for proving reviewers were actually requested on each PR, including using the Gitea requested-reviewers endpoint when the PR create response omits resolved reviewers.
