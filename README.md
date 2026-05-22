# Agentic E2E Development Lab

This project defines a local end-to-end software delivery lab for testing AI agents across a realistic development workflow.

The core idea is simple:

- Local Docker Compose runs the software delivery platform.
- Azure runs only the application environments.
- The same build artifact is promoted across DEV, QA, and PROD.

## Architecture

```text
Local machine
├─ Plane
│  └─ ticket management
├─ Gitea
│  └─ source code repository
├─ Gitea Actions runner
│  └─ CI/CD execution
├─ Sonatype Nexus Repository Community Edition
│  └─ artifact and package repository
├─ Dozzle
│  └─ local container logs
├─ Prometheus
│  └─ scrape app metrics
└─ Grafana
   └─ dashboards for local + Azure metrics

Azure
├─ DEV
│  └─ app runtime + config + optional DB
├─ QA
│  └─ app runtime + config + optional DB
└─ PROD
   └─ app runtime + config + optional DB
```

## Repository Layout

```text
infra/
├─ compose.yml
├─ plane/
│  ├─ compose.yml
│  └─ variables.env
├─ gitea/
│  ├─ compose.yml
│  └─ runner.env
├─ nexus/
│  └─ compose.yml
├─ monitoring/
│  ├─ compose.yml
│  ├─ prometheus.yml
│  └─ grafana/
└─ azure/
   ├─ main.bicep
   ├─ dev.parameters.json
   ├─ qa.parameters.json
   └─ prod.parameters.json
```

Use `compose.yml` consistently for Docker Compose files.

## Delivery Flow

```text
1. Create ticket in Plane
2. Agent reads ticket
3. Agent creates branch in Gitea
4. Agent changes code
5. Agent opens PR in Gitea
6. Gitea Actions runs build/tests
7. CI publishes artifact/package to Nexus
8. CI deploys to Azure DEV
9. Agent validates DEV
10. Same artifact is promoted to QA
11. Agent validates QA
12. Same artifact is promoted to PROD
13. Agent checks metrics/logs
14. Agent updates Plane ticket
```

## Client Tool Configuration

Configure this repo through Codex chat, not by manually editing every local file:

```text
config infra
```

That request uses `.codex/skills/configure-infra-tools`. The skill audits local config, initializes missing ignored files from tracked templates, asks for missing values one step at a time, explains how to obtain each value from the relevant UI/API/CLI, and applies only confirmed values.

The skill configures the delivery lab in this order:

```text
Plane -> Gitea -> Gitea Actions runner -> Nexus -> Azure DEV -> Azure QA -> Azure PROD -> Prometheus -> Grafana
```

It handles:

- client tool settings for Plane, Git, Gitea PRs, reviewers, and labels
- Plane Docker environment values and generated local secrets
- Gitea runner registration values
- Nexus artifact/package publishing values
- Azure DEV, QA, and PROD App Service environments
- Prometheus local/Azure scrape targets
- Grafana datasource and dashboard provisioning

The skill separates values into pre-start and post-start phases. If a pre-start value is missing while infra is running, it asks before stopping the stack, applies the value, and then asks before starting the stack again.

Credentials are never read from Docker containers, mounted volumes, databases, or logs. The skill asks for secrets in chat and explains the supported UI/API path to obtain or rotate them.

The main local files managed by the skill are:

```text
.codex/client-tools.local.json
infra/plane/variables.env
infra/gitea/runner.env
infra/monitoring/prometheus.local.yml
```

Tracked templates stay placeholder-safe. Real tokens, local secrets, and Azure hostnames belong only in ignored local files.

After configuration, start the local platform with the helper script:

```powershell
.\infra\up.ps1
```

The same stack can also be started from Docker Compose directly:

```powershell
docker compose --env-file .\infra\plane\variables.env -f .\infra\compose.yml up -d
```

Azure is configured by the same skill after the local delivery tools are ready. It creates one App Service environment per stage:

```text
DEV  -> rg-agentic-dev
QA   -> rg-agentic-qa
PROD -> rg-agentic-prod
```

Each Azure environment contains only the application runtime, environment configuration, SQLite-backed API settings, and monitoring integration. Azure App Service uses runtime/package deployment by default; it does not pull container images from Nexus.

## Chat-Driven Ticket Workflow

Plane ticket work starts from Codex chat, not from a user-run command. The repo-local skill at `.codex/skills/plane-start-ticket` guides Codex to list Todo tickets, create or reuse a Git branch, push that branch to Gitea, generate OpenSpec-style planning notes, update the Plane ticket description, comment with the branch name, move the ticket to `In Progress`, and create an OpenSpec proposal.

Implementation handoff also starts from chat. The repo-local skill at `.codex/skills/openspec-implement-change` runs `/opsx:apply`, implements the OpenSpec tasks, adds edge-case unit tests, verifies the app and tests, commits with a readable change list, pushes after hooks pass, opens a Gitea PR, invokes `.codex/skills/gitea-pr-review-agent`, moves the Plane ticket to the configured review state, and comments on Plane with the PR link.

Example chat requests:

```text
List Plane Todo tickets
Start the next Plane Todo ticket
Start E2EPROJECT-1
```

The workflow uses the Plane API. It must never use Plane MCP, Docker containers, or direct database access for Plane.

After Codex comments on the Plane ticket with the branch, it moves the ticket to the configured `inProgressState`. It then creates an OpenSpec proposal with `/opsx:propose` using a change name derived from the branch; branch slashes are converted to dashes for the OpenSpec change id. Re-runs should not duplicate the generated branch comment or repeat the state move when the ticket is already in progress.

After implementation is complete, Codex opens a Gitea PR and invokes the PR review agent immediately. The review agent reviews only that PR, posts one top-level Gitea comment, adds an idempotency marker for the PR head SHA, ensures configured labels exist, and applies the appropriate review labels. It does not run on a timer.

After the PR review comment is posted, Codex moves the Plane ticket to configured `reviewState` and adds a Plane comment using the stable marker `IA generated PR: {prUrl}`. If the configured review state does not exist, Codex stops after PR creation and review instead of guessing another state.

## Key Principle

```text
Local tools manage the delivery workflow.
Azure hosts only DEV, QA, and PROD runtime resources.
Nexus stores the exact build artifact promoted between environments.
Azure App Service uses runtime/package deployment by default; it does not pull container images from Nexus.
```
