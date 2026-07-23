---
name: configure-dev-environment
description: Configure this repo's local development and delivery environment. The lab stack is fixed: Docker Compose with Gitea, OpenProject, Nexus, and Monitoring.
---

<!-- TIER 3: STAGE-SPECIFIC - Environment setup skill -->

# Configure Dev Environment

## Overview

The lab stack is **always** Docker Compose with Gitea + OpenProject + Nexus + Monitoring. No provider selection, no Rancher Desktop, no Azure.

This skill replaces the old separate skills: `configure-ticket-workflow`, `configure-source-control`, `configure-ci-runner`, `configure-artifact-repository`, `configure-quality-gates`, and `configure-observability`. All domain setup flows are now inline below.

## Prerequisites

Before running quick setup, ensure the following CLI tools are available on the host:

| Tool           | Install Command                                                     | Required For                                                                             |
| -------------- | ------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| Docker Desktop | [docker.com](https://www.docker.com/products/docker-desktop/)       | Compose services, container builds                                                       |
| Node.js (v20+) | [nodejs.org](https://nodejs.org/) or `winget install OpenJS.NodeJS` | OpenSpec CLI, frontend builds                                                            |
| OpenSpec CLI   | `npm install -g @fission-ai/openspec@latest`                        | OpenSpec proposal workflow (`/opsx:propose`, `openspec status`, `openspec instructions`) |
| Lefthook       | `python -m tools.sdd_cli tool-installer install-lefthook`           | Pre-commit hooks (gitleaks scan, commit-msg validation)                                  |

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

This runs 17 steps in order. **All steps are fatal** — if any step fails, the setup stops immediately. Each step is validated before proceeding to the next.

```
 1. InitLocalFiles            (config templates → local files)
 2. InstallLefthook           (lefthook binary + git hooks)
 3. InitProjectProfile        (project schema, profile, adapters)
 4. InitQualityTemplates      (delivery-policy.json)
 5. BuildGiteaActionsImages   (sdd-e2e-ci:local Docker image, checksum-based rebuild)
 6. ValidateAppConfig         (apps.json schema + Dockerfile existence check)
 7. ValidateDockerDesktop     (insecure-registries, socket, Compose, provider detection)
 8. ComposeUp                 (Gitea + Nexus + Seq + Grafana + Dozzle)
 9. ValidateObservability     (Seq + Grafana health endpoints)
10. ValidateGiteaRunner       (Docker, images, tools, socket, docker_push.py, network)
11. ProvisionLabUsers         (Gitea/OpenProject/Nexus users + runner registration token)
12. ProvisionNexusRepositories (EULA acceptance + sdd-artifacts raw hosted repo)
13. ProvisionGiteaSecrets     (NEXUS_USERNAME, KUBECONFIG_B64 credentials via Gitea API)
14. PushToGitea               (create main branch, push dev with v0 code)
15. SetGiteaBranchProtection  (PR approval rules via Gitea API)
16. ScaffoldK8s               (validate Docker Desktop K8s, create manifests)
17. SetSemgrepConfig           (stack-aware SAST rule generation)
```

## Individual Steps

If you need to run steps individually:

| Step                        | Command                                                                           |
| --------------------------- | --------------------------------------------------------------------------------- |
| Start services              | `python -m tools.sdd_cli environment-lab compose-up`                              |
| Stop services               | `python -m tools.sdd_cli environment-lab compose-down`                            |
| Init local files            | `python -m tools.sdd_cli environment-lab init-local-files`                        |
| Init project profile        | `python -m tools.sdd_cli environment-lab init-project-profile`                    |
| Set client tools            | `python -m tools.sdd_cli environment-lab set-client-tools --values-json '{...}'`  |
| Set project stack           | `python -m tools.sdd_cli environment-lab set-project-stack --values-json '{...}'` |
| Build Gitea images (checksum-aware) | `python -m tools.sdd_cli environment-lab build-gitea-images`                      |
| Validate app config                 | `python -m tools.sdd_cli environment-lab validate-app-config`                     |
| Validate Docker Desktop             | `python -m tools.sdd_cli environment-lab validate-docker-desktop`                 |
| Validate observability              | `python -m tools.sdd_cli environment-lab validate-observability`                  |
| Validate Gitea runner               | `python -m tools.sdd_cli environment-lab validate-gitea-runner`                   |
| Provision Gitea secrets             | `python -m tools.sdd_cli environment-lab provision-gitea-secrets`                 |
| Setup MCP server                    | `python tools/bm25s_flashrank/setup_mcp.py`                                       |
| Install lefthook                    | `python -m tools.sdd_cli tool-installer install-lefthook`                         |

## Safety Rules

- Never print, commit, or write real tokens/secrets into tracked files.
- Update only ignored local files for secrets: `.codex/client-tools.local.json`, `.codex/quality.local.json`, `infra/openproject/variables.env`, `infra/monitoring/variables.env`, `infra/gitea/runner.env`.
- Keep tracked files as templates or placeholder-safe documentation.
- Do not start or stop local infra automatically. Ask first before running compose commands.

## Service URLs (default Docker Compose)

| Service     | URL                     |
| ----------- | ----------------------- |
| Gitea       | `http://localhost:3000` |
| OpenProject | `http://localhost:8080` |
| Nexus       | `http://localhost:8081` |
| Seq         | `http://localhost:5341` |
| Grafana     | `http://localhost:3001` |

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
- `provision-nexus-repositories`: configure Nexus: accept EULA, create `sdd-artifacts` raw hosted repository.
- `provision-gitea-secrets`: **auto-fix** — reads Nexus credentials and local kubeconfig, creates/updates `NEXUS_USERNAME`, `NEXUS_PASSWORD`, `NEXUS_URL`, `NEXUS_REPOSITORY`, and `KUBECONFIG_B64` secrets in Gitea Actions. This ensures CI credentials always match the actual Nexus password (prevents `HTTP 401` on artifact uploads).
- `validate-app-config`: validate `infra/deployment/apps.json` against `apps.schema.json` and check every app's Dockerfile exists.
- `validate-docker-desktop`: check Docker Desktop configuration — `insecure-registries` includes `host.docker.internal:5001`, Docker socket present, Docker Compose available.
- `validate-gitea-runner`: check Docker, Gitea runner images, runner tools, Docker socket mount, and `tools/docker_push.py` existence.
- `setup-mcp-server`: run the monorepo-docs-search MCP setup script via `python tools/bm25s_flashrank/setup_mcp.py` (standalone script, not an `environment-lab` subcommand).

## CI Workflow Configuration

After the infrastructure is running and the project stack is set, generate or update the Gitea Actions workflow files to match the project's technology stack and app topology.

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
   - `.gitea/workflows/agent-eval.yml` — Checkout, promptfoo evaluation

### Stack-to-Build Mapping

| Stack                  | Build Command                     | Output Dir             |
| ---------------------- | --------------------------------- | ---------------------- |
| React, Vue, Angular    | `npm ci && npm run build`         | `dist/`                |
| FastAPI, Django, Flask | `pip install -r requirements.txt` | Source tree            |
| .NET / ASP.NET Core    | `dotnet publish -c Release`       | `bin/Release/publish/` |

### When To Run

- After `setup-lab` completes (the `CheckCIWorkflows` step will warn if files are missing)
- After changing the project stack (e.g., adding a backend)
- After adding or removing apps from `infra/deployment/apps.json`

## Troubleshooting: Runner Image Failures

If workflow runs fail with `pull access denied for sdd-e2e-ci`:

1. **Check `force_pull` in runner config** — `setup-lab` step 12 (`ValidateGiteaRunner`) auto-detects and fixes this, along with the validations below:
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

The CI pipeline relies on `host.docker.internal` to reach Gitea and Nexus from within job containers. Without it, checkout steps fail with `Could not resolve host: host.docker.internal` or use fragile hardcoded IPs that break on container restarts.

### What Needs host.docker.internal

| Component              | Where                                                                          | Why                                                                            |
| ---------------------- | ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------ |
| Runner container       | `infra/gitea/compose.yml` → `runner.extra_hosts`                               | Runner itself needs to reach Gitea at `host.docker.internal:3000`              |
| Job containers         | `infra/gitea/config.yml` → `container.options`                                 | Gitea Actions passes `--add-host` to every job container spawned by the runner |
| Workflow checkout URLs | `.gitea/workflows/*.yml` → checkout step `repo_url`                            | Git clone from inside job container needs to reach Gitea                       |
| Nexus upload URL       | `.gitea/workflows/*.yml` → upload step defaults to `host.docker.internal:8088` | Artifact upload from job container needs to reach Nexus                        |

### Validation

`setup-lab` step 12 (`ValidateGiteaRunner`) validates all four:

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

**On Windows/macOS:** `host.docker.internal` is provided automatically by Docker Desktop, but the `extra_hosts` and `--add-host` settings are still needed because Gitea Actions job containers are spawned from the runner container, not directly from the host.

## Troubleshooting: Runner Image (`pull access denied`)

If workflow runs fail with `pull access denied for sdd-e2e-ci`:

1. **Check `force_pull` in runner config** — `setup-lab` step 12 auto-detects and fixes this.

If workflow runs show `HTTP 401` during the Upload to Nexus step:

1. **Check Nexus password** — verify it in client-tools config:

   ```bash
   python -c "import json; c=json.load(open('.codex/client-tools.local.json')); print(c['nexus']['password'])"
   ```

2. **Sync the secret** — `setup-lab` step 9 (`SyncNexusSecrets`) auto-fixes this, or run standalone:

   ```bash
   python -m tools.sdd_cli environment-lab sync-nexus-secrets
   ```

   This pushes the password from `client-tools.local.json` into the `NEXUS_PASSWORD` Gitea Actions secret.

3. **Rerun the workflow** — dispatch a new run on `dev` to pick up the updated secret.

## Domain-Specific Setup

### OpenProject Work Packages

Configure OpenProject API access, workspace/project identifiers, and workflow states.

1. Check `.codex/client-tools.local.json` for `openProject.baseUrl`, `openProject.apiToken`, and `openProject.projectIdentifier`.
2. Check `infra/openproject/variables.env` for OpenProject Docker env values.
3. Run `python -m tools.sdd_cli environment-lab set-client-tools --values-json '{...}'` to set confirmed values.
4. Run `python -m tools.sdd_cli environment-lab set-openproject-env --values-json '{...}'` for env vars.
5. Validate by calling the OpenProject API health endpoint.

**Values needed:** base URL, API token, project identifier, and status names (todo, in-progress, review, QA, done).
**Safety:** Never print the API token. Never read secrets from Docker containers. Do not use OpenProject MCP or direct database access for ticket delivery.

### Gitea PR Automation

Configure repository owner/name, PR reviewers, approval minimums, and review labels.

1. Infer owner/repo from `git remote get-url origin` when possible.
2. Run `python -m tools.sdd_cli environment-lab set-client-tools --values-json '{...}'` with Gitea values.
3. **After provisioning users and pushing code**, `push_to_gitea()` automatically adds provisioned users (FirstUser, SecondUser) as repo collaborators with write permission via the Gitea API (`PUT /api/v1/repos/{owner}/{repo}/collaborators/{username}`).
4. Run `python -m tools.sdd_cli environment-lab set-gitea-branch-protection` to apply approval rules.
5. Validate token, repo, and collaborators only when Gitea is running.

**Values needed:** Gitea base URL, API token, owner, repo, reviewers list, label names. Minimum approvals (`pr.minimumApprovals.dev`, `pr.minimumApprovals.main`) default to 1 each.
**Safety:** Never print the API token. Do not create labels automatically without user approval.

### Gitea Actions Runner

Configure the CI runner for PR validation and deployment jobs.

1. Run `python -m tools.sdd_cli environment-lab init-local-files` to create `infra/gitea/runner.env` if missing.
2. **Generate a runner registration token** from Gitea via API:
   ```bash

   ```

curl -s -X POST --user "${ADMIN_USER:?}:${ADMIN_PASS:?}" \ # gitleaks:allow
http://localhost:3000/api/v1/admin/runners/registration-token \
| python3 -c "import sys,json; print(json.load(sys.stdin)['token'])"

````
3. **Update `infra/gitea/runner.env`** with the correct values. The file is git-ignored:
```bash
python -m tools.sdd_cli environment-lab set-gitea-runner-env --values-json '{
  "GITEA_INSTANCE_URL": "http://gitea:3000",
  "GITEA_RUNNER_REGISTRATION_TOKEN": "TOKEN_FROM_STEP_2",
  "GITEA_RUNNER_LABELS": "ubuntu-latest,docker,windows"
}'
````

- The instance URL **must** be `http://gitea:3000` (internal Docker network), not `localhost`.
- Labels **must** include `ubuntu-latest` — this matches the `runs-on` value used in `.gitea/workflows/*.yml`.

4. **Restart the runner container** to pick up the new config:
   ```bash
   docker restart agentic-gitea-runner
   ```
5. Wait 5 seconds, then **verify the runner is registered and online**:
   ```bash

   ```

curl -s --user "${ADMIN_USER:?}:${ADMIN_PASS:?}" http://localhost:3000/api/v1/admin/runners | python3 -m json.tool # gitleaks:allow

````
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
python -m tools.sdd_cli environment-lab setup-nexus
````

This automates all of the following:

- **Waits for Nexus to be reachable** (retries with backoff, ~30s total)
- **Accepts the Nexus EULA** automatically if not yet accepted (via `POST /service/rest/v1/system/eula`)
- **Creates the `sdd-artifacts` raw hosted repository** via REST API if it doesn't already exist
  - Created with `writePolicy: ALLOW_ONCE` and `strictContentTypeValidation: true`
- **Idempotent**: skips any step already completed

3. **Validate Nexus CI secrets** — check that Gitea Actions secrets for Nexus are correctly configured:

   ```bash
   python -m tools.sdd_cli environment-lab validate-nexus-secrets
   ```

   This checks:
   - `NEXUS_URL` secret does **not** exist (workflow defaults to `host.docker.internal:8088`)
   - `NEXUS_REPOSITORY` secret does **not** exist (workflow defaults to `sdd-artifacts`)
   - `NEXUS_USERNAME` and `NEXUS_PASSWORD` secrets **do** exist

4. **Known issues** (previous manual fixes, now automated):
   - ❌ **EULA not accepted** — previously caused `HTTP 403` on upload. Now auto-accepted in step 2.
   - ❌ **NEXUS_URL secret overriding default** — previously caused `curl exit code 6` (Couldn't resolve host). Now detected in step 3.
   - ❌ **NEXUS_REPOSITORY secret overriding default** — same URL issue. Now detected in step 3.

5. Keep the release model: build once, promote the same artifact through DEV → QA → PROD.

6. Ensure Nexus release manifests at `app/{commitSha}/release.json` carry machine-readable metadata.

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

Trunk is a universal code formatter and linter manager installed locally (not in CI).

1. **Install the launcher:** `npm install -D @trunkio/launcher` (installed as a dev dependency)
2. **Initialize trunk in the repo:** `npx trunk init`
   - This creates `.trunk/trunk.yaml` with default linter/formatter configuration
   - The `.trunk/` directory is gitignored — it contains generated caches and tool downloads
3. **Verify it works:** `npx trunk check --all --ci --no-fix`
4. **Add to pre-commit hook:** Lefthook already includes `npx trunk fmt` in the pre-commit hook to auto-format staged files

Run trunk manually to check formatting: `npx trunk check --all --ci --no-fix`

**Values needed:** Coverage minimum percent, enabled gate IDs.
**Safety:** Keep local hooks lightweight. Do not write scanner secrets into tracked files.

### Observability (Seq & Grafana)

Configure Seq log search and Grafana health dashboards.

1. Run `python -m tools.sdd_cli environment-lab validate-observability` to check Seq and Grafana.
2. Fix any issues before completing setup — observability is required for `config infra`.
3. Required checks: Seq API/health `200`, Grafana health endpoint reachable, Grafana Infinity datasource and health alerts provisioned.

**Values needed:** SEQ_URL (default `http://localhost:5341`), error alert window/threshold.
**Safety:** Keep Seq data in Docker volume; do not export logs to tracked files.

### Documentation Search MCP (monorepo-docs-search)

Configure the `monorepo-docs-search` MCP server for fast BM25 + FlashRank documentation search across Markdown (`.md`, `.mdx`) files. This MCP is used by agents to route documentation lookups per `.codex/mcp-instructions.md`.

1. Run the automated setup script:
   ```bash
   python tools/bm25s_flashrank/setup_mcp.py
   ```
   This script:
   - Checks Python >= 3.10.
   - Creates a shared virtual environment at `%USERPROFILE%\.mcp_shared_venv` (Windows) or `~/.mcp_shared_venv` (macOS/Linux).
   - Installs dependencies: `mcp`, `bm25s`, `flashrank`.
   - Writes the MCP server configuration to `.vscode/mcp.json` and `.cline/mcp_settings.json`.
   - Auto-starts the MCP server and writes a PID file to `.vscode/.mcp_monorepo_docs_search.pid`.
2. Validate the configuration is present in `.vscode/mcp.json` under `servers.monorepo-docs-search`.
3. Validate the server registers correctly by checking agent documentation search routing via `.codex/mcp-instructions.md`.

**Prerequisites:** Python 3.10 or newer, internet access for pip package download.
**Safety:** The setup script only writes to local config files (`.vscode/mcp.json`, `.cline/mcp_settings.json`). It does not send data externally or require API tokens.

## Output

Report: files created/updated, values still missing, observability health, missing tools with install commands, and next steps.

## Failure Rules

- Stop when required user-supplied secrets or tokens are missing; provide source, destination, and setup path.
- Stop before writing secrets to tracked files.
- Stop before reading secrets from Docker containers, volumes, databases, or logs.
- Do not start or stop infra automatically without asking first.
