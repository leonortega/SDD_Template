# OpenProject Workflow Configuration

Owns:

- `.codex/client-tools.local.json` `openProject` section.
- `infra/openproject/variables.env`.
- OpenProject API validation and ticket status names.

Use the shared script:

```powershell
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode Audit
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode InitLocalFiles
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode SetClientTools -ValuesJson $values
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode SetOpenProjectEnv -ValuesJson $values
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

## Docker Env Values

Pre-start values belong in `infra/openproject/variables.env`.

Generate local-only secrets with:

```powershell
[Convert]::ToHexString([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(64)).ToLower()
```

Required generated value:

- `OPENPROJECT_SECRET_KEY_BASE`

## Live Validation

Live validation requires local infra to be running. Ask before running `.\infra\up.ps1`.

Validate with OpenProject API v3:

- `GET {baseUrl}/api/v3/users/me` with `Authorization: Bearer {apiToken}`.
- `GET {baseUrl}/api/v3/projects/{projectIdentifier}`.
- Resolve configured status names through the work package schema or statuses API before state mutations.

Do not use OpenProject MCP, Docker database access, or direct database queries for ticket workflow validation.
