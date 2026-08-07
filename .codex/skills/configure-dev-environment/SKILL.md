---
name: configure-dev-environment
license: MIT
description: >-
  Configure this repo's local development and delivery environment. The lab stack is fixed: Docker Compose with Gitea,
  OpenProject, Nexus, and Monitoring.
---

<!-- TIER 3: STAGE-SPECIFIC - Environment setup skill -->

# Configure Dev Environment

## Overview

The lab stack is **always** Docker Compose with Gitea + OpenProject + Nexus + Monitoring. No provider selection, no
Rancher Desktop, no Azure.

This skill replaces the old separate skills: `configure-ticket-workflow`, `configure-source-control`,
`configure-ci-runner`, `configure-artifact-repository`, `configure-quality-gates`, and
`configure-observability`. All domain setup flows are now inline below.

## Shared Context

Read `.codex/skills/_shared/delivery-contract.md` and `docs/conventions/context-management.md` before changing local
configuration. This skill prepares the local delivery environment; the product
stack remains a user decision and setup stays scoped to the active ticket.

## Workflow

Run `setup-lab` (all-in-one) or the individual steps below in order. Each step validates before proceeding; stop on the
first failure and report it. Confirm the stack with the user before any
stack-dependent step, then hand off to the next delivery stage.

## Prerequisites

Before running quick setup, ensure the following CLI tools are available on the host:

| Tool           | Install Command                                                     | Required For                                                                             |
| -------------- | ------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| Docker Desktop | [docker.com](https://www.docker.com/products/docker-desktop/)       | Compose services, container builds                                                       |
| Node.js (v20+) | [nodejs.org](https://nodejs.org/) or `winget install OpenJS.NodeJS` | OpenSpec CLI, frontend builds                                                            |
| OpenSpec CLI   | `npm install -g @fission-ai/openspec@latest`                        | OpenSpec opsx chat flow (`$openspec-propose`, `$openspec-apply-change`; CLI: `openspec status`, `openspec instructions`) |
| Lefthook       | `python -m tools.sdd_cli tool-installer install-lefthook`           | Pre-commit hooks (gitleaks scan, commit-msg validation) + pre-push `stack-tests` with coverage gate (`python -m tools.sdd_cli stack-tests` — unit/integration/architecture tests + `coverage.minimumPercent`, default 80) |

Verify tools are installed:

```bash
node --version && npm --version && openspec --version
```

If OpenSpec CLI is missing, install with: `npm install -g @fission-ai/openspec@latest`

Lefthook installs automatically during `setup-lab`. To install separately:

```bash
python -m tools.sdd_cli tool-installer install-lefthook
```

## Quick Setup

Run the idempotent all-in-one command:

```bash
python -m tools.sdd_cli environment-lab setup-lab
```

This runs 19+ steps in order (sub-steps numbered with letters). **All steps are fatal** — if any step fails, the setup
stops immediately. Each step is validated before proceeding to the next.

```text
text
 1. InitLocalFiles            (config templates → local files)
 1b. EnsureOpenProjectEnv     (generate OPENPROJECT_SECRET_KEY_BASE)
 2. InstallLefthook           (lefthook binary + git hooks)
 3. InitProjectProfile        (project schema, profile, adapters)
 4. InitQualityTemplates      (delivery-policy.json)
 5. BuildGiteaActionsImages   (sdd-e2e-ci:local Docker image, checksum-based rebuild)
 6. ValidateAppConfig         (apps.json schema + Dockerfile existence check)
 7. ValidateDockerDesktop     (insecure-registries, socket, Compose, provider detection)
 8. ComposeUp                 (Gitea + Nexus + Seq + Grafana + Dozzle — via root infra/compose.yml)
 8b. WaitForServices          (Gitea/OpenProject/Nexus/Grafana/Seq reachable)
 9. ValidateObservability     (Seq + Grafana health endpoints + dashboard provisioning + Infinity datasource)
 9a. ProvisionGrafanaToken    (create Grafana service account + token via API; write GRAFANA_URL/GRAFANA_SERVICE_ACCOUNT_TOKEN to infra/monitoring/variables.env)
 9b. InstallGrafanaMCP        (Grafana MCP after Grafana is running + token ready)
10. ValidateGiteaRunner       (Docker, images, tools, socket, docker_push.py, network)
11. ProvisionLabUsers         (Gitea/OpenProject/Nexus users + runner registration token)
11b. InstallOpenProjectMCP    (after API key is provisioned)
11c. InstallGiteaMCP          (after API token is provisioned)
12. ProvisionNexusRepositories (EULA + sdd-artifacts raw repo + docker-hosted registry on 5001)
13. ProvisionGiteaSecrets     (NEXUS_USERNAME/PASSWORD, KUBECONFIG — YAML-parse derived, random API port)
14. PushToGitea               (create main branch, push dev with v0 code)
15. SetGiteaBranchProtection  (PR approval rules via Gitea API for dev + main)
16. SetupKindCluster          (kind + extraPortMappings from infra/k8s/kind-config.yaml — FATAL)
17. InstallK8sMCP             (after cluster is up)
17b. EnsureHeadlamp           (K8s web UI, reads ~/.kube/config)
18. ScaffoldK8s               (Kustomize manifests + per-env service patches from ports.json)
19. SetSemgrepConfig           (stack-aware SAST rule generation)
```

## Individual Steps

If you need to run steps individually:

| Step                                | Command                                                                           |
| ----------------------------------- | --------------------------------------------------------------------------------- |
| Start services                      | `python -m tools.sdd_cli environment-lab compose-up`                              |
| Stop services                       | `python -m tools.sdd_cli environment-lab compose-down`                            |
| Init local files                    | `python -m tools.sdd_cli environment-lab init-local-files`                        |
| Init project profile                | `python -m tools.sdd_cli environment-lab init-project-profile`                    |
| Set client tools                    | `python -m tools.sdd_cli environment-lab set-client-tools --values-json '{...}'`  |
| Set project stack                   | `python -m tools.sdd_cli environment-lab set-project-stack --values-json '{...}'` |
| Build Gitea images (checksum-aware) | `python -m tools.sdd_cli environment-lab build-gitea-images`                      |
| Validate app config                 | `python -m tools.sdd_cli environment-lab validate-app-config`                     |
| Validate Docker Desktop             | `python -m tools.sdd_cli environment-lab validate-docker-desktop`                 |
| Validate observability              | `python -m tools.sdd_cli environment-lab validate-observability`                  |
| Provision Grafana token             | `python -m tools.sdd_cli environment-lab provision-grafana-token`                |
| Validate Gitea runner               | `python -m tools.sdd_cli environment-lab validate-gitea-runner`                   |
| Provision Gitea secrets             | `python -m tools.sdd_cli environment-lab provision-gitea-secrets`                 |
| Prune Docker leftovers              | `python -m tools.sdd_cli environment-lab prune-docker-leftovers`                  |
| Install lefthook                    | `python -m tools.sdd_cli tool-installer install-lefthook`                         |

## Safety Rules

- Never print, commit, or write real tokens/secrets into tracked files.
- Update only ignored local files for secrets: `.codex/client-tools.local.json`, `.codex/quality.local.json`,
`infra/openproject/variables.env`, `infra/monitoring/variables.env`,
`infra/gitea/runner.env`.
- Keep tracked files as templates or placeholder-safe documentation.
- Do not start or stop local infra automatically. Ask first before running compose commands.

## Service URLs (default Docker Compose)

| Service     | URL                     |
| ----------- | ----------------------- |
| Gitea       | `http://localhost:3000` |
| OpenProject | `http://localhost:8080` |
| Nexus       | `http://localhost:8088` |
| Seq         | `http://localhost:5341` |
| Grafana     | `http://localhost:3001` |
| Dozzle      | `http://localhost:8888` |

### After Docker Desktop Restart

Docker Desktop containers do not survive a Docker Desktop restart. After restarting Docker Desktop, restart all lab
services with:

```bash
python -m tools.sdd_cli environment-lab compose-up
```

This re-runs `docker compose up -d --remove-orphans` with the correct env files and project directory. All state is
preserved in Docker volumes.

To verify all services are healthy:

```bash
python -m tools.sdd_cli environment-lab health-check
```

## Constraint: Never Assume Tech Stack

The product tech stack (frontend, backend, database) is a **user decision**. Never:

- Auto-detect or infer the stack from source code, file extensions, or package files
- Assume a default stack
- Generate stack-dependent workflows or configuration without explicit user confirmation

Always ask the user what tech stack they want before running `set-project-stack` or any other stack-dependent operation.

## Configure Modes

Useful `environment-lab` modes:

- `compose-up` / `compose-down`: start/stop Docker Compose services.
- `init-local-files`: create ignored local files from tracked templates.
- `init-project-profile`: create project profile, schema, and local overlay.
- `set-client-tools`: update `.codex/client-tools.local.json`.
- `set-project-stack`: update ignored `.codex/project-profile.local.json` with frontend/backend/database choices.
- `set-gitea-branch-protection`: apply PR approval rules via Gitea API.
- `validate-observability`: check Seq + Grafana endpoints and provisioning.
- `validate-gitea-runner`: check Docker, Gitea runner images, and runner tools.
- `build-gitea-images`: build Gitea Actions CI images.
- `provision-nexus-repositories`: configure Nexus: accept EULA, create `sdd-artifacts` raw hosted repository **and** the
`docker-hosted` Docker registry (port `5001`, `forceBasicAuth: true`) —
idempotent GET/PUT reconcile, so an existing repo's connector port + Basic auth are corrected on re-run.
- `provision-gitea-secrets`: **auto-fix** — reads Nexus credentials and the kind cluster kubeconfig (derived via `kind
get kubeconfig` → YAML parse → `host.docker.internal` server, random API port
preserved, `insecure-skip-tls-verify`), creates/updates `NEXUS_USERNAME`, `NEXUS_PASSWORD`, `NEXUS_URL`,
`NEXUS_REPOSITORY`, and `KUBECONFIG` secrets in Gitea Actions. This ensures CI credentials
always match the actual Nexus password (prevents `HTTP 401` on artifact uploads).
- `validate-app-config`: validate `infra/deployment/apps.json` against `apps.schema.json` and check every app's
Dockerfile exists.
- `validate-docker-desktop`: check Docker Desktop configuration — `insecure-registries` includes
`host.docker.internal:5001`, Docker socket present, Docker Compose available.
- `validate-gitea-runner`: check Docker, Gitea runner images, runner tools, Docker socket mount, and
`tools/docker_push.py` existence.

## CI Workflow Configuration

After the infrastructure is running and the project stack is set, generate or update the Gitea Actions workflow files to
match the project's technology stack and app topology.

Use the `configure-ci-workflows` skill:

```bash
# The skill is loaded automatically by the agent when needed
# Ask the agent: "Run configure-ci-workflows"
```

### What It Does

1. Reads the project stack from the project profile (frontend, backend, database technologies).
2. Reads the app topology from `infra/deployment/apps.json`.
3. Reads provider configuration from `client-tools.local.json` (Gitea URL, Nexus config).
4. Generates or updates these workflow files:
   - `.gitea/workflows/package-deploy.yml` — Build, package, upload to Nexus, deploy
   - `.gitea/workflows/pr-validation.yml` — Checkout, JSON validation, secret scan

### Stack-to-Build Mapping

| Stack                  | Build Command                     | Output Dir             |
| ---------------------- | --------------------------------- | ---------------------- |
| React, Vue, Angular    | `npm ci && npm run build`         | `dist/`                |
| FastAPI, Django, Flask | `pip install -r requirements.txt` | Source tree            |
| .NET / ASP.NET Core    | `dotnet publish -c Release`       | `bin/Release/publish/` |

### When To Run

- After `setup-lab` completes (step 19 `SetSemgrepConfig` warns if files are missing)
- After changing the project stack (e.g., adding a backend)
- After adding or removing apps from `infra/deployment/apps.json`

## Troubleshooting: Runner Image Failures

If workflow runs fail with `pull access denied for sdd-e2e-ci`:

1. **Check `force_pull` in runner config** — `setup-lab` step 10 (`ValidateGiteaRunner`) auto-detects and fixes this,
along with the validations below:
   - compose.yml has `extra_hosts: host.docker.internal:host-gateway` for the runner container
   - config.yml has `container.options: '--add-host=host.docker.internal:host-gateway'` for job containers
   - Workflow files use `host.docker.internal` instead of hardcoded IPs like `172.20.0.2`

   ```bash
   python -m tools.sdd_cli environment-lab validate-gitea-runner
   ```

   Fixes are auto-applied: `force_pull: true` → `false`, and hardcoded IPs are flagged as errors.

2. **Restart the runner** after fixing config.yml:

   ```bash
   docker restart agentic-gitea-runner
   ```

3. **Verify the image exists**:

   ```bash
   docker images sdd-e2e-ci:local
   ```

   If missing, rebuild: `python -m tools.sdd_cli environment-lab build-gitea-images`

## host.docker.internal Resolution

The CI pipeline relies on `host.docker.internal` to reach Gitea and Nexus from within job containers. Without it,
checkout steps fail with `Could not resolve host: host.docker.internal` or use fragile
hardcoded IPs that break on container restarts.

### What Needs host.docker.internal

| Component              | Where                                                                          | Why                                                                            |
| ---------------------- | ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------ |
| Runner container       | `infra/gitea/compose.yml` → `runner.extra_hosts`                               | Runner itself needs to reach Gitea at `host.docker.internal:3000`              |
| Job containers         | `infra/gitea/config.yml` → `container.options`                                 | Gitea Actions passes `--add-host` to every job container spawned by the runner |
| Workflow checkout URLs | `.gitea/workflows/*.yml` → checkout step `repo_url`                            | Git clone from inside job container needs to reach Gitea                       |
| Nexus upload URL       | `.gitea/workflows/*.yml` → upload step defaults to `host.docker.internal:8088` | Artifact upload from job container needs to reach Nexus                        |

### Validation

`setup-lab` step 10 (`ValidateGiteaRunner`) validates all four:

1. **compose.yml** — checks `extra_hosts: host.docker.internal:host-gateway` ✅
2. **config.yml** — checks `--add-host=host.docker.internal:host-gateway` in container.options ✅
3. **Workflow files** — checks for hardcoded `172.20.0.x` IPs (error) and absence of `host.docker.internal` (warning) ✅
4. **Nexus URL** — validates NEXUS_URL secret doesn't override the `host.docker.internal:8088` default (step 8) ✅

### Manual Fix

If `host.docker.internal` is not resolving inside job containers:

**On Linux:** Docker Engine does not provide `host.docker.internal` by default. It must be added explicitly:

```yml
# In compose.yml runner service:
extra_hosts:
  - "host.docker.internal:host-gateway"

# In config.yml under container:
container:
  options: "--add-host=host.docker.internal:host-gateway"
```

**On Windows/macOS:** `host.docker.internal` is provided automatically by Docker Desktop, but the `extra_hosts` and
`--add-host` settings are still needed because Gitea Actions job containers are
spawned from the runner container, not directly from the host.

## Troubleshooting: Runner Image (`pull access denied`)

If workflow runs fail with `pull access denied for sdd-e2e-ci`:

1. **Check `force_pull` in runner config** — `setup-lab` step 10 auto-detects and fixes this.

If workflow runs show `HTTP 401` during the Upload to Nexus step:

1. **Check Nexus password** — verify it in client-tools config:

   ```bash
   python -c "import json; c=json.load(open('.codex/client-tools.local.json')); print(c['nexus']['password'])"
   ```

2. **Sync the secret** — `setup-lab` step 13 (`ProvisionGiteaSecrets`) auto-fixes this, or run standalone:

   ```bash
   python -m tools.sdd_cli environment-lab provision-gitea-secrets
   ```

   This pushes the password from `client-tools.local.json` into the `NEXUS_PASSWORD` Gitea Actions secret.

3. **Rerun the workflow** — dispatch a new run on `dev` to pick up the updated secret.

## Domain-Specific Setup

### OpenProject Work Packages

Configure OpenProject API access, workspace/project identifiers, and workflow states.

1. Check `.codex/client-tools.local.json` for `openProject.baseUrl`, `openProject.apiToken`, and
`openProject.projectIdentifier`.
2. Check `infra/openproject/variables.env` for OpenProject Docker env values.
3. Run `python -m tools.sdd_cli environment-lab set-client-tools --values-json '{...}'` to set confirmed values.
4. Run `python -m tools.sdd_cli environment-lab set-openproject-env --values-json '{...}'` for env vars.
5. Validate by calling the OpenProject API health endpoint.

**Values needed:** base URL, API token, project identifier, and status names (todo, in-progress, review, QA, done).
**Safety:** Never print the API token. Never read secrets from Docker containers. Do not use OpenProject MCP or direct
database access for ticket delivery.

### Gitea PR Automation

Configure repository owner/name, PR reviewers, approval minimums, and review labels.

1. Infer owner/repo from `git remote get-url origin` when possible.
2. Run `python -m tools.sdd_cli environment-lab set-client-tools --values-json '{...}'` with Gitea values.
3. **After provisioning users and pushing code**, `push_to_gitea()` automatically adds provisioned users (FirstUser,
SecondUser) as repo collaborators with write permission via the Gitea API (`PUT
/api/v1/repos/{owner}/{repo}/collaborators/{username}`).
4. Run `python -m tools.sdd_cli environment-lab set-gitea-branch-protection` to apply approval rules.
5. Validate token, repo, and collaborators only when Gitea is running.

**Values needed:** Gitea base URL, API token, owner, repo, reviewers list, label names. Minimum approvals
(`pr.minimumApprovals.dev`, `pr.minimumApprovals.main`) default to 1 each.
**Safety:** Never print the API token. Do not create labels automatically without user approval.

### Gitea Actions Runner

Configure the CI runner for PR validation and deployment jobs.

1. Run `python -m tools.sdd_cli environment-lab init-local-files` to create `infra/gitea/runner.env` if missing.
2. **Generate a runner registration token** from Gitea via API:

   ```bash
   curl -s -X POST --user "${ADMIN_USER:?}:${ADMIN_PASS:?}" \ # gitleaks:allow
     http://localhost:3000/api/v1/admin/runners/registration-token \
     | python3 -c "import sys,json; print(json.load[sys.stdin]('token'))"
   ```

3. **Update `infra/gitea/runner.env`** with the correct values. The file is git-ignored:

```bash
python -m tools.sdd_cli environment-lab set-gitea-runner-env --values-json '{
  "GITEA_INSTANCE_URL": "http://gitea:3000",
  "GITEA_RUNNER_REGISTRATION_TOKEN": "TOKEN_FROM_STEP_2",
  "GITEA_RUNNER_LABELS": "ubuntu-latest,docker,windows"
}'
```

- The instance URL **must** be `http://gitea:3000` (internal Docker network), not `localhost`.
- Labels **must** include `ubuntu-latest` — this matches the `runs-on` value used in `.gitea/workflows/*.yml`.

1. **Restart the runner container** to pick up the new config:

   ```bash
   docker restart agentic-gitea-runner

```text

2. Wait 5 seconds, then **verify the runner is registered and online**:

   ```bash

```text

curl -s --user "${ADMIN_USER:?}:${ADMIN_PASS:?}" <http://localhost:3000/api/v1/admin/runners> | python3 -m json.tool #
gitleaks:allow

```text

The response should contain a runner with `"online": true`.
6. Run `python -m tools.sdd_cli environment-lab build-gitea-images` before any CI workflow runs.
7. Run `python -m tools.sdd_cli environment-lab validate-gitea-runner` to check Docker, images, and tools.
8. For old/floating Gitea/Gitea Runner images, check current stable upstream versions and update compose files.

**Values needed:** Admin username/password (to generate token), runner registration token, instance URL.
**Safety:** Never print the registration token. Do not start/stop infra without approval.

### Nexus Artifacts

Configure artifact storage, release manifests, and DEV/QA/PROD promotion.

The `setup-lab` flow handles Nexus setup automatically, but you can also run steps individually.

1. Run `python -m tools.sdd_cli environment-lab set-client-tools --values-json '{...}'` with Nexus credentials.

2. **Full Nexus setup** — run this single command which handles everything below:

```bash
python -m tools.sdd_cli environment-lab provision-nexus-repositories
```text

This automates all of the following:

- **Waits for Nexus to be reachable** (retries with backoff, ~30s total)
- **Accepts the Nexus EULA** automatically if not yet accepted (via `POST /service/rest/v1/system/eula`)
- **Creates the `sdd-artifacts` raw hosted repository** via REST API if it doesn't already exist
  - Created with `writePolicy: ALLOW_ONCE` and `strictContentTypeValidation: true`
- **Creates the `docker-hosted` Docker registry** on port `5001` with `forceBasicAuth: true` (idempotent GET/PUT reconcile — an existing repo's connector port + Basic auth are corrected on re-run)
- **Idempotent**: skips any step already completed

1. **Preview/re-sync Nexus CI secrets** — `provision-gitea-secrets` (step 13) is idempotent: re-running it re-creates/updates the secrets to the workflow-correct values. Use `--dry-run true` to
preview the plan; run without it to re-sync:

   ```bash
   python -m tools.sdd_cli environment-lab provision-gitea-secrets --dry-run true
   python -m tools.sdd_cli environment-lab provision-gitea-secrets   # actual re-sync
```text

   Expected state:
   - `NEXUS_USERNAME`, `NEXUS_PASSWORD`, `NEXUS_URL`, and `NEXUS_REPOSITORY` secrets **exist** and carry the workflow-default values (`http://host.docker.internal:8088` / `sdd-artifacts`)
   - `NEXUS_DOCKER_REGISTRY` is left empty (skipped) so the workflow uses its default (`host.docker.internal:5001`)

2. **Known issues** (previous manual fixes, now automated):
   - ❌ **EULA not accepted** — previously caused `HTTP 403` on upload. Now auto-accepted in step 2.
   - ❌ **Stale `NEXUS_URL`/`NEXUS_REPOSITORY` secret values** (e.g. `localhost:8088` or an old IP) — previously caused `curl exit code 6` (Couldn't resolve host) from inside job containers. Now
   re-synced to the workflow-correct values by step 13 (`provision-gitea-secrets`).

3. Keep the release model: build once, promote the same artifact through DEV → QA → PROD.

4. Ensure Nexus release manifests at `app/{commitSha}/release.json` carry machine-readable metadata.

**Values needed:** Nexus base URL, username, password/token, repository name.
**Safety:** Never print credentials. Never read the initial admin password from Docker containers.

### Quality Gates

Configure code quality thresholds, scanning tools, and local hooks.

1. Run `python -m tools.sdd_cli environment-lab init-quality-templates` if templates are missing.
2. Run `python -m tools.sdd_cli environment-lab set-quality-config --values-json '{...}'` for custom thresholds.
3. Ensure `.codex/quality.local.json` exists (default coverage minimum: 80%).
4. For missing SDKs/tools/scanners, provide install command, official URL, and validation command.
5. Gitea PR validation is the authoritative gate — local hooks are lightweight.
6. Ask whether Semgrep should be enabled only after real app code exists.

### Trunk.io (Local Formatting)

Trunk is a universal code formatter and linter manager installed locally (not in CI). The lefthook hooks `trunk-fmt` and `trunk-check` run `npx --yes trunk fmt` and `npx --yes trunk check` on every commit (`--yes` prevents the npx install prompt from blocking non-TTY hooks), so
trunk must be initialized before the first commit. `ensure-quality-tools` (run by `full-setup`) auto-installs `@trunkio/launcher` into the gitignored `node_modules/` when the probe fails, so hooks resolve trunk without prompting.

1. **Initialize trunk in the repo:** `npx trunk init`
   - `npx` auto-downloads the launcher — no manual install needed
   - Creates `.trunk/trunk.yaml` with default linter/formatter configuration
   - The `.trunk/` directory is gitignored (generated caches and tool downloads)
2. **Verify it works:** `npx trunk check --all --ci --no-fix` — also works as an on-demand formatting check anytime

**Auto-initialization:** During the ticket start workflow (`dev-flow-start-ticket`), trunk is auto-initialized after the tech stack is confirmed if `.trunk/trunk.yaml` doesn't exist yet.

**Values needed:** Coverage minimum percent, enabled gate IDs.
**Safety:** Keep local hooks lightweight. Do not write scanner secrets into tracked files.

### Observability (Seq & Grafana)

Configure Seq log search and Grafana health dashboards.

1. Run `python -m tools.sdd_cli environment-lab validate-observability` to check Seq and Grafana.
2. Fix any issues before completing setup — observability is required for `config infra`.
3. Required checks: Seq API/health `200`, Grafana health endpoint reachable, Grafana Infinity datasource and health alerts provisioned.

**Values needed:** SEQ_URL (default `http://localhost:5341`), error alert window/threshold.
**Safety:** Keep Seq data in Docker volume; do not export logs to tracked files.

### Managing The Monitoring Stack (project `agentic-e2e`)

The monitoring stack (Grafana, health-probe, Seq, Dozzle) is defined in
`infra/monitoring/compose.yml` and included by the root compose file
`infra/compose.yml`, whose project name is **`agentic-e2e`**. **Always manage
the stack through the root file — never run `docker compose up` standalone
from `infra/monitoring/`.** Running standalone creates a second compose
project (`monitoring`) on a separate `monitoring_monitoring` network, so the
health-probe can no longer be resolved as `health-probe:8090` from Grafana
(Service Health panel shows "No data"/400) and can't reach the kind node.

```bash
# ✅ Correct — canonical stack (project agentic-e2e, network agentic-e2e_monitoring)
docker compose --env-file infra/openproject/variables.env \
  --env-file infra/monitoring/variables.env \
  -f infra/compose.yml --project-directory infra up -d health-probe

# ❌ Wrong — spawns a stray `monitoring` project / network
cd infra/monitoring && docker compose up -d health-probe
```text

The `monitoring` network is pinned to `agentic-e2e_monitoring` in
`infra/monitoring/compose.yml`; the `health-probe` service has
`restart: unless-stopped` plus a urllib-based healthcheck (the alpine image
ships no curl). `docker compose ls` should show a single `agentic-e2e`
project — a second `monitoring` project indicates a stray standalone run.

## Output

Report: files created/updated, values still missing, observability health, missing tools with install commands, next steps, and the handoff point to the next delivery stage.

## Failure Rules

- Stop when required user-supplied secrets or tokens are missing; provide source, destination, and setup path.
- Stop before writing secrets to tracked files.
- Stop before reading secrets from Docker containers, volumes, databases, or logs.
- Do not start or stop infra automatically without asking first.
