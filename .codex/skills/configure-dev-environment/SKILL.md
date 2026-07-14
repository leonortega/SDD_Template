---
name: configure-dev-environment
description: Configure this repo's local development and delivery environment. The lab stack is fixed: Docker Compose with Gitea, OpenProject, Nexus, and Monitoring.
---

# Configure Dev Environment

## Overview

The lab stack is **always** Docker Compose with Gitea + OpenProject + Nexus + Monitoring. No provider selection, no Rancher Desktop, no Azure.

This skill replaces the old separate skills: `configure-ticket-workflow`, `configure-source-control`, `configure-ci-runner`, `configure-artifact-repository`, `configure-quality-gates`, and `configure-observability`. All domain setup flows are now inline below.

## Quick Setup

Run the idempotent all-in-one command:

```bash
python -m tools.sdd_cli environment-lab setup-lab
```

This runs: InitLocalFiles → InitProjectProfile → BuildGiteaImages → compose-up → ValidateObservability → ValidateGiteaRunner.

## Individual Steps

If you need to run steps individually:

| Step | Command |
|---|---|
| Start services | `python -m tools.sdd_cli environment-lab compose-up` |
| Stop services | `python -m tools.sdd_cli environment-lab compose-down` |
| Init local files | `python -m tools.sdd_cli environment-lab init-local-files` |
| Init project profile | `python -m tools.sdd_cli environment-lab init-project-profile` |
| Set client tools | `python -m tools.sdd_cli environment-lab set-client-tools --values-json '{...}'` |
| Set project stack | `python -m tools.sdd_cli environment-lab set-project-stack --values-json '{...}'` |
| Validate observability | `python -m tools.sdd_cli environment-lab validate-observability` |
| Build Gitea images | `python -m tools.sdd_cli environment-lab build-gitea-images` |
| Setup MCP server (`setup-mcp-server`) | `python tools/bm25s_flashrank/setup_mcp.py` |

## Safety Rules

- Never print, commit, or write real tokens/secrets into tracked files.
- Update only ignored local files for secrets: `.codex/client-tools.local.json`, `.codex/quality.local.json`, `infra/openproject/variables.env`, `infra/monitoring/variables.env`, `infra/gitea/runner.env`.
- Keep tracked files as templates or placeholder-safe documentation.
- Do not start or stop local infra automatically. Ask first before running compose commands.

## Service URLs (default Docker Compose)

| Service | URL |
|---|---|
| Gitea | `http://localhost:3000` |
| OpenProject | `http://localhost:8080` |
| Nexus | `http://localhost:8081` |
| Seq | `http://localhost:5341` |
| Grafana | `http://localhost:3001` |

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
- `setup-mcp-server`: run the monorepo-docs-search MCP setup script via `python tools/bm25s_flashrank/setup_mcp.py` (standalone script, not an `environment-lab` subcommand).

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
3. Run `python -m tools.sdd_cli environment-lab set-gitea-branch-protection` to apply approval rules.
4. Validate token, repo, and collaborators only when Gitea is running.

**Values needed:** Gitea base URL, API token, owner, repo, reviewers list, label names. Minimum approvals (`pr.minimumApprovals.dev`, `pr.minimumApprovals.main`) default to 1 each.
**Safety:** Never print the API token. Do not create labels automatically without user approval.

### Gitea Actions Runner

Configure the CI runner for PR validation and deployment jobs.

1. Run `python -m tools.sdd_cli environment-lab init-local-files` to create `infra/gitea/runner.env` if missing.
2. Run `python -m tools.sdd_cli environment-lab set-gitea-runner-env --values-json '{...}'` with runner values.
3. Run `python -m tools.sdd_cli environment-lab build-gitea-images` before any CI workflow runs.
4. Run `python -m tools.sdd_cli environment-lab validate-gitea-runner` to check Docker, images, and tools.
5. For old/floating Gitea/Gitea Runner images, check current stable upstream versions and update compose files.

**Values needed:** Runner registration token, instance URL.
**Safety:** Never print the registration token. Do not start/stop infra without approval.

### Nexus Artifacts

Configure artifact storage, release manifests, and DEV/QA/PROD promotion.

1. Run `python -m tools.sdd_cli environment-lab set-client-tools --values-json '{...}'` with Nexus credentials.
2. Guide the user to store Nexus credentials as Gitea Actions secrets for CI.
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
