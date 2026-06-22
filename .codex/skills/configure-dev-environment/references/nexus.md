# Artifact Delivery Configuration

Owns:

- Nexus service account and repository guidance.
- `.gitea/workflows/package-deploy.yml`.
- Nexus-related Gitea Actions secrets.
- Build-once, promote-same-artifact release flow.

## Strategy

- Nexus stores build artifacts/packages published by Gitea Actions.
- Rancher Desktop uses digest-pinned container image metadata from Nexus Docker plus raw Nexus release metadata by default.
- Azure App Service uses package/ZIP deployment when the optional Azure lane is selected.
- Do not configure Azure to pull container images from Nexus unless the user explicitly changes architecture.
- The default Rancher Desktop flow requires a Nexus Docker registry.

## Required Gitea Actions Secrets

Store these as repository or organization Actions secrets:

- `NEXUS_URL`: Base URL used by the runner job containers to reach Nexus. For this local Docker Desktop setup, prefer `http://host.docker.internal:8088` because Gitea Actions creates per-job networks that cannot resolve the Nexus Compose service alias. For browser/manual checks use `http://localhost:8088`.
- `NEXUS_USERNAME`: Nexus service account username used only by Gitea Actions.
- `NEXUS_PASSWORD`: Nexus service account password or token.
- `NEXUS_REPOSITORY`: Hosted raw repository name, default `raw-hosted`.

For the Rancher Desktop local Kubernetes lane, also store:

- `NEXUS_DOCKER_REGISTRY`: Docker registry endpoint reachable by both the Gitea runner and Rancher Desktop Kubernetes, for example `host.docker.internal:5001` when that name is valid in the local runtime.
- `NEXUS_DOCKER_USERNAME`: Nexus Docker service account username.
- `NEXUS_DOCKER_PASSWORD`: Nexus Docker service account password or token.
- `RANCHER_KUBECONFIG_B64`: Base64-encoded kubeconfig for the `rancher-desktop` context.

Do not store kubeconfig contents or registry credentials in tracked files.

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
$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/${GITHUB_SHA}/deployable-apps.json
$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/${GITHUB_SHA}/{artifactName}
$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/${GITHUB_SHA}/{artifactName}.sha256
```

For PROD promotion, the workflow must download from the QA-approved artifact commit. A ticket-gated push to `main` resolves this from `app/qa-approved/latest.json`, requires the pointer commit to equal `GITHUB_SHA`, and validates `commit.sha`, `release.json`, and the source RC tag before downloading ZIPs; explicit workflow dispatch uses the supplied `artifact_commit_sha`:

```text
$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/${artifact_commit_sha}/deployable-apps.json
$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/${artifact_commit_sha}/{artifactName}
```

Each artifact commit must also have a machine-readable release manifest:

```text
$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/${commitSha}/release.json
```

Use `release.json` for automation and idempotency. It should carry commit SHA, checksum, artifact path, PR URL, Plane ticket key, DEV/QA/PROD URLs and status, QA evidence URL, source RC tag, final release tag, workflow run URLs, monitoring status, and timestamps. Plane comments remain the human-readable summary.

## Nexus Docker Repository Setup

Use a hosted Docker repository for the Rancher Desktop local lane. Keep raw Nexus as the release metadata and QA evidence store.

Manual setup:

1. Open Nexus at `http://localhost:8088`.
2. Create a hosted Docker repository, for example `docker-hosted`.
3. Configure an HTTP connector port that matches `infra/nexus/compose.yml`, default `5001`.
4. Create or reuse the automation service account with Docker repository read/write privileges.
5. Configure Rancher Desktop/containerd to trust or allow the local registry endpoint. Prefer trusted local TLS; use an insecure local registry only for the lab.
6. Store `NEXUS_DOCKER_REGISTRY`, `NEXUS_DOCKER_USERNAME`, and `NEXUS_DOCKER_PASSWORD` as Gitea Actions secrets.

The Rancher workflow uploads image metadata to raw Nexus:

```text
$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/${commitSha}/container-images.json
$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/${commitSha}/monitoring-summary.json
$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/${commitSha}/qa-observability.json
```

The container metadata file, not the mutable image tag, is the promotion source of truth. Monitoring files are evidence only and must contain sanitized logs or summary fields, never kubeconfig, registry credentials, connection strings, tokens, or unsanitized pod logs.

Human-readable Nexus version folders are metadata aliases. They must point back to `app/{commitSha}/` and must not duplicate ZIPs by default:

```text
$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/qa-approved/latest.json
$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/rc/${sourceRcVersion}/artifact-pointer.json
$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/rc/${sourceRcVersion}/release.json
$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/releases/${finalReleaseVersion}/artifact-pointer.json
$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/releases/${finalReleaseVersion}/release.json
```

## Release Flow

- Feature branches open PRs into `dev`.
- Merge to `dev` builds once.
- For Azure, publish one deployable ZIP artifact per app in `infra/deployment/apps.json`, compute per-app checksums, upload topology/artifacts/checksums/metadata to Nexus, deploy DEV from the Nexus topology artifacts, and promote the same topology artifacts to QA after DEV page and all app `/health` checks pass.
- For Rancher Desktop, build `sddtemplate/site` and `sddtemplate/api` images once, push to Nexus Docker, upload `app/{commitSha}/container-images.json`, deploy the digest-pinned references to `sdd-dev`, and promote the same digest set to `sdd-qa` after DEV health and observability checks pass.
- Move the Plane ticket to QA only after QA checks pass.
- Create or verify an annotated RC tag such as `v1.2.0-rc.1` on the QA-approved artifact commit after E2E QA passes, then publish `app/qa-approved/latest.json` and the matching `app/rc/{sourceRcVersion}/` alias metadata.
- Fast-forward the tested commit to `main` only after QA passes. Push-triggered PROD deployment is allowed only when `main` points to the exact QA-approved packaged commit, the commit or merged PR title starts with the configured ticket key pattern in `.codex/project-profile.json`, and application/test/package source changed.
- Create the final annotated release tag such as `v1.2.0` on the same commit.
- Deploy PROD from the QA-passed artifact commit by Azure ticket-gated `main` push through `app/qa-approved/latest.json` or explicit provider workflow dispatch inputs `artifact_commit_sha`, `release_version`, and `source_rc_version`.
- After PROD passes, publish the final `app/releases/{finalReleaseVersion}/` alias metadata.
- Validate PROD page and all app `/health` checks; use Seq log search as observability verification when available.
- Record version lineage in Plane comments at each phase: QA deployment as unversioned candidate or known RC, E2E QA as `artifact commit -> source RC`, and PROD as `artifact commit -> source RC -> final release`.
- For rollback, redeploy the previous known-good provider artifact set: Azure `app/{commitSha}/deployable-apps.json` ZIP topology with checksums, or Rancher `app/{commitSha}/container-images.json` digest set. Verify `/health`, update `release.json`, and comment Plane with rollback lineage.
- Do not rebuild between environments.

Default release path:

```text
feature branch -> dev -> DEV -> QA -> main -> PROD
```

If updating `main` creates a new merge commit, ensure that exact merge commit already has the QA-approved Nexus artifact before allowing push-triggered PROD deployment. Otherwise, use explicit dispatch with the original QA-passed artifact commit SHA. Non-code changes outside `src/**` and `tests/**` must not deploy automatically.
