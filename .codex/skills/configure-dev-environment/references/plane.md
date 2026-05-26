# Plane Workflow Configuration

Owns:

- `.codex/client-tools.local.json` Plane section.
- `infra/plane/variables.env`.
- Plane API validation and ticket state names.

Use the shared script:

```powershell
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode Audit
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode InitLocalFiles
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode SetClientTools -ValuesJson $values
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode SetPlaneEnv -ValuesJson $values
```

## Client Tool Values

Ask only when missing or placeholder:

- `plane.baseUrl`: Plane web/API base URL. Default local value is usually `http://agentic.lvh.me:8080`.
- `plane.apiToken`: Personal access token from Plane Profile Settings. Never print it.
- `plane.workspaceSlug`: Lowercase workspace slug from the Plane URL.
- `plane.projectIdentifier`: Ticket prefix, for example `E2EPROJECT`.
- `plane.todoState`: default ready state, usually `Todo`.
- `plane.inProgressState`: default `In Progress`.
- `plane.reviewState`: default `In Review`.

## Docker Env Values

Pre-start values belong in `infra/plane/variables.env`.

Replace unsafe local defaults when found:

- `POSTGRES_PASSWORD=plane`
- RabbitMQ password `plane`
- MinIO `access-key` / `secret-key`
- placeholder generated secrets such as `SECRET_KEY`, `AES_SECRET_KEY`, and `PI_INTERNAL_SECRET`

Generate local-only secrets with:

```powershell
[guid]::NewGuid().ToString()
[Convert]::ToHexString([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32)).ToLower()
```

Update dependent URI values when passwords change.

## Live Validation

Live validation requires local infra to be running. Ask before running `.\infra\up.ps1`.

Validate with the Plane API:

- `GET {baseUrl}/api/v1/users/me/` with `X-API-Key`.
- List projects/states to confirm `workspaceSlug`, `projectIdentifier`, and state names.

Do not use Plane MCP, Docker database access, or direct database queries for Plane client workflow validation.
