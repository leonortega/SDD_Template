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
│  └─ artifact repository / container image registry
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
7. CI publishes artifact/image to Nexus
8. CI deploys to Azure DEV
9. Agent validates DEV
10. Same artifact is promoted to QA
11. Agent validates QA
12. Same artifact is promoted to PROD
13. Agent checks metrics/logs
14. Agent updates Plane ticket
```

## Local Platform

The local platform is managed from a single Docker Compose entrypoint:

```powershell
docker compose --env-file .\infra\plane\variables.env -f .\infra\compose.yml up -d
```

Or use the helper script:

```powershell
.\infra\up.ps1
```

Before first run, create local environment files from the examples:

```powershell
Copy-Item .\infra\plane\variables.env.example .\infra\plane\variables.env
Copy-Item .\infra\gitea\runner.env.example .\infra\gitea\runner.env
```

The real `.env` files are intentionally ignored because they contain local secrets and registration tokens.

## Azure Environments

Azure should contain only the minimum resources needed to host the application environments.

Use one resource group per environment:

```text
rg-agentic-dev
rg-agentic-qa
rg-agentic-prod
```

Each environment contains:

- App runtime
- Environment configuration
- Optional database
- Monitoring integration

## Key Principle

```text
Local tools manage the delivery workflow.
Azure hosts only DEV, QA, and PROD runtime resources.
Nexus stores the exact build artifact promoted between environments.
```
