# Artifact Delivery Configuration

Owns:

- Nexus service account and repository guidance.
- `.gitea/workflows/package-deploy.yml`.
- Nexus-related Gitea Actions secrets.
- Build-once, promote-same-artifact release flow.

## Strategy

- Nexus stores build artifacts/packages published by Gitea Actions.
- Azure App Service uses package/ZIP deployment by default.
- Do not configure Azure to pull container images from Nexus unless the user explicitly changes architecture.
- Do not require a Nexus Docker registry for the default flow.

## Required Gitea Actions Secrets

Store these as repository or organization Actions secrets:

- `NEXUS_URL`: Base URL used by the runner to reach Nexus. For this local Docker network, prefer `http://nexus:8081`. For browser/manual checks use `http://localhost:8088`.
- `NEXUS_USERNAME`: Nexus service account username used only by Gitea Actions.
- `NEXUS_PASSWORD`: Nexus service account password or token.
- `NEXUS_REPOSITORY`: Hosted raw repository name, default `raw-hosted`.

Never write Nexus credentials into tracked files.

## Local Nexus Check Configuration

Store the Nexus user used for repository checks in ignored `.codex/client-tools.local.json`, never in tracked files:

- `nexus.baseUrl`: Host URL used by local checks, normally `http://localhost:8088`.
- `nexus.username`: Nexus user that can list repositories and read/write the artifact repository.
- `nexus.password`: Nexus password or token for that user.
- `nexus.repository`: Hosted raw repository name, default `raw-hosted`.

`config infra` infers `nexus.baseUrl` and `nexus.repository`. It must ask the user for `nexus.username` and `nexus.password` because credentials are not inferable and must not be read from containers, mounted volumes, databases, or logs.

Configure it with `SetClientTools` after the user supplies the values:

```powershell
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode SetClientTools -ValuesJson '{
  "nexus": {
    "baseUrl": "http://localhost:8088",
    "username": "gitea-actions",
    "password": "replace-with-user-supplied-password-or-token",
    "repository": "raw-hosted"
  }
}'
```

All Nexus repository checks must use this local configuration. Do not rely on unauthenticated `http://localhost:8088/service/rest/v1/repositories` checks.

Official Gitea Actions secrets documentation: https://docs.gitea.com/usage/actions/secrets

Manual setup in Gitea:

1. Open `http://localhost:3000/leon/SDD_template/settings/actions/secrets`.
2. Add one repository secret for each required value.
3. Use names exactly as listed above. Secret names may contain letters, numbers, and underscores; do not start them with `GITHUB_`, `GITEA_`, or a number.
4. Validate with the Gitea API by listing secret names only:

```powershell
$client = Get-Content .codex/client-tools.local.json -Raw | ConvertFrom-Json
$headers = @{ Authorization = "token $($client.gitea.apiToken)" }
Invoke-RestMethod "$($client.gitea.baseUrl)/api/v1/repos/$($client.gitea.owner)/$($client.gitea.repo)/actions/secrets" -Headers $headers
```

## Prompting

Ask for:

- Nexus service account username.
- Nexus service account password/token.
- Repository name, defaulting to a hosted raw artifact repository such as `raw-hosted`.

How to get it: open Nexus at `http://localhost:8088`, complete first-login/password-reset manually, then create a service account for automation.

Do not read the initial admin password from Docker containers, mounted volumes, databases, or logs.

## Nexus Raw Repository Setup

Use a hosted raw repository for ZIP artifacts and metadata.

Official Sonatype docs:

- Creating repositories: https://help.sonatype.com/en/creating-repositories.html
- Raw repositories: https://help.sonatype.com/en/raw-repositories.html
- Repository REST API overview: https://help.sonatype.com/en/repositories-api.html

Manual setup:

1. Open Nexus at `http://localhost:8088`.
2. Complete the first-login password reset manually if needed.
3. Go to `Administration` -> `Repository` -> `Repositories`.
4. Choose `Create repository`.
5. Select recipe `raw (hosted)`.
6. Set `Name` to `raw-hosted`.
7. Set `Online` enabled.
8. Use blob store `default` unless there is a reason to isolate artifacts.
9. Set deployment/write policy to allow workflow uploads. Prefer `Allow redeploy` for local/dev labs; use a stricter policy later if immutable artifact paths are enforced.
10. Save.

Create a Nexus service account:

1. Go to `Administration` -> `Security` -> `Users`.
2. Create a local user for automation, for example `gitea-actions`.
3. Grant the minimum privileges needed to upload and read from `raw-hosted`.
4. Store the username/password as Gitea Actions secrets, never in tracked files.

Validate from the host without exposing credentials:

```powershell
$client = Get-Content .codex/client-tools.local.json -Raw | ConvertFrom-Json
$pair = "$($client.nexus.username):$($client.nexus.password)"
$encoded = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($pair))
$headers = @{ Authorization = "Basic $encoded" }
Invoke-RestMethod "$($client.nexus.baseUrl)/service/rest/v1/repositories" -Headers $headers |
  Where-Object { $_.name -eq $client.nexus.repository -and $_.format -eq 'raw' -and $_.type -eq 'hosted' }
```

Validate from Gitea Actions later by running the package workflow. The workflow uploads to:

```text
$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/${GITHUB_SHA}/app.zip
```

## Release Flow

- Feature branches open PRs into `dev`.
- Merge to `dev` builds once.
- Publish one deployable ZIP artifact.
- Compute checksum and commit SHA metadata.
- Upload artifact, checksum, and metadata to Nexus.
- Deploy DEV from the Nexus artifact.
- Promote the same artifact to QA after DEV checks pass.
- Move the Plane ticket to QA only after QA checks pass.
- Merge or fast-forward the tested commit to `main` only after QA passes.
- Deploy PROD from the QA-passed artifact commit.
- Do not rebuild between environments.

Default release path:

```text
feature branch -> dev -> DEV -> QA -> main -> PROD
```

If updating `main` creates a new merge commit, record and promote the original QA-passed artifact commit SHA instead of rebuilding a new PROD artifact.
