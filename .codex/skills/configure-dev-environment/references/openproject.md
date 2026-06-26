# OpenProject Workflow Configuration

Owns:

- `.codex/client-tools.local.json` `openProject` section.
- `infra/openproject/variables.env`.
- OpenProject API validation and ticket status names.

Use the shared script:

```bash
python -m tools.sdd_cli configure Audit
python -m tools.sdd_cli configure InitLocalFiles
python -m tools.sdd_cli configure SetClientTools --values-json-file .codex/config-values.local.json
python -m tools.sdd_cli configure SetOpenProjectEnv --values-json-file .codex/config-values.local.json
```

## Client Tool Values

Ask only when missing or placeholder:

- `openProject.baseUrl`: OpenProject web/API base URL. Default local value is usually `http://localhost:8080`.
- `openProject.apiToken`: API token from the OpenProject user account. Never print it.
- `openProject.projectIdentifier`: OpenProject project identifier containing delivery work packages.
- `openProject.todoStatus`: default ready status, usually `Todo`.
- `openProject.inProgressStatus`: default `In Progress`.
- `openProject.reviewStatus`: default `In Review`.
- `openProject.qaStatus`: default `QA`.
- `openProject.doneStatus`: default `Done`.
- `openProject.timeTelemetry.enabled`: default `true`; when supported, workflow duration telemetry is written as OpenProject time entries before falling back to local JSONL.
- `openProject.timeTelemetry.defaultActivityName`: fallback time-entry activity name, usually `Other`.
- `openProject.timeTelemetry.activityFlow`: activity-name-first map for the OpenProject activity list. Use `Management` for `dev-ops-post-merge-deploy` and `dev-ops-deploy-prod`; `Specification` for `dev-flow-propose-change`, `dev-flow-start-ticket`, `dev-flow-verify-change`, and `dev-flow-archive-change`; `Development` for `dev-flow-implement-ticket`, `dev-flow-pr-review-agent`, and `dev-flow-pr-review-feedback-loop`; `Testing` for `dev-ops-deploy-qa` and `configured-qa-gate`; `Support` for `dev-flow-file-qa-bug`, `dev-ops-rollback-prod`, and `dev-ops-hotfix-prod`; `Other` for `dev-flow-pipeline-status` and `dev-flow-retrospective-audit`.
- `openProject.timeTelemetry.activityByStage`: per-workflow-stage activity map used by automation. Each stage entry may use `activityName` or exact `activityId`; keep it consistent with `activityFlow`.

## Docker Env Values

Pre-start values belong in `infra/openproject/variables.env`.

Generate local-only secrets with:

```bash
python -c "import secrets; print(secrets.token_hex(64))"
```

Required generated value:

- `OPENPROJECT_SECRET_KEY_BASE`

## Live Validation

Live validation requires local infra to be running. Ask before running `python -m tools.sdd_cli infra up`.

Validate with OpenProject API v3:

- `GET {baseUrl}/api/v3/users/me` with `Authorization: Bearer {apiToken}`.
- `GET {baseUrl}/api/v3/projects/{projectIdentifier}`.
- Resolve configured status names through the work package schema or statuses API before state mutations.
- When time telemetry is enabled, validate every configured per-stage time-entry activity with `GET {baseUrl}/api/v3/time_entries/activity/{activityId}` or resolve each configured `activityName`, then verify the current user can list/create time entries for a test work package before relying on direct telemetry.

Do not use OpenProject MCP, Docker database access, or direct database queries for ticket workflow validation.
