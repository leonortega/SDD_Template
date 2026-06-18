# Provider Adapter Contract

Generic delivery skills must read `.codex/project-profile.json` before provider-specific instructions.

## Profile First

Use the project profile for:

- stack and test framework identity,
- selected ticket, repository, review, artifact, deployment, and observability providers,
- ticket key pattern, branch policy, environment names, and release policy,
- quality gate names and workflow job mapping,
- adapter reference paths.

Use `.codex/client-tools.local.json` only for local endpoint values, credentials, usernames, workspace ids, project ids, reviewer names, labels, and other runtime values. Do not print secret-bearing values.

## Adapter Loading

Load only adapters selected by `.codex/project-profile.json` and needed for the current stage:

- ticket adapter for ticket reads, comments, state changes, and generated markers,
- repository/review adapter for branches, pushes, pull requests, checks, labels, comments, and reviewers,
- artifact adapter for immutable artifacts, checksums, manifests, promotions, and QA evidence,
- deployment adapter for environment deploys, configuration verification, health checks, and rollback,
- stack adapter for framework-specific build/test behavior,
- E2E adapter for browser or API acceptance evidence.

If an adapter path is missing or points outside the repository, stop before mutation.

## Generic Operation Names

Skills should describe workflow intent with these provider-neutral operation names:

- Ticket: `list`, `read`, `enrich`, `move-state`, `comment`, `verify-marker`.
- Repo/review: `branch`, `push`, `pull-request`, `status`, `label`, `comment`, `request-reviewers`.
- Artifact: `publish`, `retrieve`, `verify`, `promote-alias`, `publish-evidence`.
- Deploy: `deploy-artifact`, `apply-config`, `verify-config`, `health`, `record`.
- QA: `discover-targets`, `run`, `diagnose`, `publish-evidence`.

Provider adapters translate these operations to concrete API calls, CLI commands, workflow jobs, and field names.

## Specificity Boundary

Generic skills may mention concrete provider or framework names only when:

- naming the selected adapter path,
- describing where to load provider-specific details,
- preserving a stable marker or existing compatibility command,
- documenting an example explicitly marked as provider-specific.

Exact versions, Docker images, SDK versions, package versions, cloud resource names, and local URLs belong in executable config, provider adapters, or local ignored files, not generic skills.
