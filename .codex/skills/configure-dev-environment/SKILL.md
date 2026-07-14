---
name: configure-dev-environment
description: Configure this repo's local development and delivery environment. The lab stack is fixed: Docker Compose with Gitea, OpenProject, Nexus, and Monitoring.
---

# Configure Dev Environment

## Overview

The lab stack is **always** Docker Compose with Gitea + OpenProject + Nexus + Monitoring. No provider selection, no Rancher Desktop, no Azure.

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

## Domain Routing

- OpenProject work packages: use `configure-ticket-workflow`.
- Gitea PR automation: use `configure-source-control`.
- Gitea Actions runner: use `configure-ci-runner`.
- Quality gates and CI: use `configure-quality-gates`.
- Nexus artifacts: use `configure-artifact-repository`.
- Monitoring dashboards: use `configure-observability`.

## Output

Report: files created/updated, values still missing, observability health, missing tools with install commands, and next steps.

## Failure Rules

- Stop when required user-supplied secrets or tokens are missing; provide source, destination, and setup path.
- Stop before writing secrets to tracked files.
- Do not start or stop infra automatically without asking first.
