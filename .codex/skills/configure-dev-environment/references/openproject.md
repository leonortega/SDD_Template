# OpenProject Workflow Configuration

Owns:

- `.codex/client-tools.local.json` `openProject` section.
- `infra/openproject/variables.env`.
- OpenProject API validation and ticket status names.

Use the shared script:

```bash
python -m tools.sdd_cli configure Audit
python -m tools.sdd_cli configure InitLocalFiles
python -m tools.sdd_cli configure SetClientTools --values-json $values
python -m tools.sdd_cli configure SetOpenProjectEnv --values-json $values
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
- `openProject.timeTelemetry.activityId`: time-entry activity id used for generated workflow telemetry.
- `openProject.timeTelemetry.activityName`: optional activity name to resolve when `activityId` is not set.

## Docker Env Values

Pre-start values belong in `infra/openproject/variables.env`.

Generate local-only secrets with:

```bash
[Convert]::ToHexString([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(64)).ToLower()
```

Required generated value:

- `OPENPROJECT_SECRET_KEY_BASE`

## Live Validation

Live validation requires local infra to be running. Ask before running `python -m tools.sdd_cli infra up`.

Validate with OpenProject API v3:

- `GET {baseUrl}/api/v3/users/me` with `Authorization: Bearer {apiToken}`.
- `GET {baseUrl}/api/v3/projects/{projectIdentifier}`.
- Resolve configured status names through the work package schema or statuses API before state mutations.
- When time telemetry is enabled, validate the configured time-entry activity with `GET {baseUrl}/api/v3/time_entries/activity/{activityId}` or resolve the configured `activityName`, then verify the current user can list/create time entries for a test work package before relying on direct telemetry.

Do not use OpenProject MCP, Docker database access, or direct database queries for ticket workflow validation.
