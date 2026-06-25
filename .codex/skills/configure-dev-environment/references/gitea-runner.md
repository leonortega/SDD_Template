# Gitea Actions Runner Configuration

Owns:

- `infra/gitea/runner.env`.
- Gitea runner registration.
- Runner image/version warnings.
- Repository Actions enablement checks.

Use the shared script:

```powershell
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode Audit
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode ValidateGiteaActionsRunner
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode SetGiteaRunner -ValuesJson $values
```

## Required Values

- `GITEA_INSTANCE_URL`: URL visible from the runner container. Default `http://gitea:3000`.
- `GITEA_RUNNER_REGISTRATION_TOKEN`: token from Gitea runner settings after Gitea is running.
- `GITEA_RUNNER_NAME`: stable local runner display name.

## Prompting

Ask for the runner token only if missing or placeholder.

How to get it: open Gitea at `http://localhost:3000`, open Site Administration or repository Actions runner settings, create/copy a runner registration token.

Do not retrieve the token from Docker containers, mounted volumes, databases, or logs.

## Audit Findings

When old or floating Gitea/Gitea Runner images are found:

- Old Gitea image pins such as `gitea/gitea:1.21.7`.
- Floating runner image tags such as `gitea/act_runner:latest`.

Check current stable versions from official Gitea release notes, docs, or registry metadata. Pin Compose images to stable patch tags instead of `latest`, and mention migration notes such as the `act_runner` to `gitea/runner` rename when applicable.

## Live Validation

Live validation requires local infra to be running. Ask before running `python -m tools.sdd_cli infra up`.

Validate:

- Gitea Actions are enabled.
- Runner registered and visible in Gitea.
- Runner can start jobs.
- PR validation job image can be pulled by Docker.
- PR validation job image contains required shell tools (`bash`, `git`, `curl`, `tar`, and `dotnet`).
- Containerized checkout can reach the local Gitea repository through `host.docker.internal`.
- Containerized workflows do not rely on JavaScript `uses:` actions unless the job container includes `node`.
