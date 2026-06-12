# Agentic E2E Development Lab

![Platform](https://img.shields.io/badge/platform-Windows-0078D4)
![Shell](https://img.shields.io/badge/shell-PowerShell-5391FE)
![.NET](https://img.shields.io/badge/.NET-10.0-512BD4)
![App](https://img.shields.io/badge/app-Blazor%20%2B%20ASP.NET%20Core-512BD4)
![Data](https://img.shields.io/badge/data-EF%20Core%20%2B%20SQLite-4479A1)
![Tests](https://img.shields.io/badge/tests-xUnit%20%2B%20Playwright-2EAD33)
![Delivery](https://img.shields.io/badge/delivery-Plane%20%7C%20OpenSpec%20%7C%20Gitea%20%7C%20Nexus-0A66C2)
![Cloud](https://img.shields.io/badge/cloud-Azure%20DEV%20%7C%20QA%20%7C%20PROD-0078D4)
![Release](https://img.shields.io/badge/release-explicit%20PROD%20promotion-6A5ACD)
![Coverage](https://img.shields.io/badge/coverage%20gate-80%25-brightgreen)

An executive-ready software delivery template for teams that want AI agents to move work from idea to production with the same traceability, quality checks, and release discipline expected from a professional engineering organization.

## What This Template Does

This repository packages a complete software delivery lab. It shows how a Codex-style agent can take a product request, plan it, implement it, review it, test it, deploy it, and prepare it for production without losing the human controls that make delivery trustworthy.

It is designed for teams that want to evaluate or sell an agent-assisted SDLC model, not just run a demo. The template combines local delivery tools with remote application environments so the process stays inspectable, repeatable, and close to real-world delivery.

The core idea is simple:

```text
Every change should have a ticket, a plan, a review, a tested artifact, QA evidence, and an explicit production decision.
```

## Why It Matters

- Faster controlled delivery: agents can continue work through known checkpoints instead of restarting from scratch.
- Better leadership visibility: Plane records the ticket state, workflow markers, handoffs, and evidence.
- Stronger quality control: Gitea pull requests, validation gates, Codex review, tests, and QA evidence are part of the normal flow.
- Safer releases: Nexus stores immutable artifacts that are promoted across DEV, QA, PROD, and rollback without rebuilding.
- Clearer accountability: production promotion is explicit, documented, and separated from QA approval.
- Practical observability: Seq, Grafana, Dozzle, Azure diagnostics, and Log Analytics support delivery and runtime inspection.

## Who This Is For

- Engineering leaders evaluating agentic software delivery.
- Product and operations teams that need visible ticket-to-production progress.
- Delivery teams building repeatable SDLC automation.
- Consultants or vendors packaging a professional agent-assisted delivery model.
- Technical operators who need a local lab for Plane, Gitea, Nexus, Azure, QA, release, rollback, and hotfix workflows.

## How The Delivery Flow Works

```text
Idea in Plane
  -> Plan the change with OpenSpec
  -> Implement and test the work
  -> Review through Gitea pull requests
  -> Package an immutable artifact in Nexus
  -> Deploy the same artifact to DEV and QA
  -> Prove acceptance with E2E QA evidence
  -> Mark the ticket Done
  -> Promote explicitly to PROD
  -> Roll back or hotfix when needed
```

In plain language:

- Plane is the work tracker and delivery record.
- OpenSpec captures the planned behavior before implementation.
- Gitea manages source control, pull requests, and validation.
- Nexus stores the exact build artifact used for deployment.
- Azure hosts the DEV, QA, and PROD application runtimes.
- Seq helps operators search DEV/QA/PROD Azure application logs; Grafana and Dozzle help inspect health, delivery signals, and local container logs.
- Codex skills under `.codex/skills/` guide the agent through each delivery stage.

## What Is Included

### Planning And Ticket Control

- Plane-based ticket workflow.
- OpenSpec planning before implementation.
- Checkpoint-based reruns that continue from existing branches, PRs, artifacts, QA evidence, tags, and release manifests.
- Ticket locks and delivery context rules to prevent work from crossing the wrong branch, PR, artifact, or environment.

### Review And Quality Gates

- Gitea pull request flow.
- Gitea Actions validation.
- Codex review-agent workflow.
- Build, test, coverage, formatting, dependency, secret, and container scanning guidance.
- Durable context review so reusable project knowledge is captured in the right docs.

### Artifact Promotion

- Nexus artifact storage by commit SHA.
- DEV, QA, PROD, and rollback promotion from the same immutable artifact.
- Release manifests and checksums for traceability.
- Explicit separation between QA approval and production release.

### QA Evidence

- E2E QA workflow for deployed QA environments.
- Evidence stored under ignored local paths and preferably published to Nexus.
- Acceptance criteria proven through executable assertions, not only screenshots or smoke checks.

### Production, Rollback, And Hotfix

- Explicit PROD promotion from QA-approved artifacts.
- Final release metadata and production evidence.
- Rollback path for known-good artifacts.
- Hotfix workflow for urgent production corrections.

### Local Observability

- Docker Compose platform for local delivery tools.
- Seq log search for Azure App Service logs imported from Log Analytics.
- Grafana health/status dashboards for Azure Monitor and Log Analytics.
- Dozzle for local container logs.
- Azure App Service diagnostics for DEV, QA, and PROD runtimes.

## Quick Start

Configure the local delivery platform through Codex chat:

```text
config infra
```

Continue the current ticket through the next valid workflow stage:

```text
automatically continue this ticket
```

Start the local delivery platform:

```powershell
.\infra\up.ps1
```

Stop it:

```powershell
.\infra\down.ps1
```

Build and test the solution:

```powershell
dotnet build .\SDDTemplate.slnx
dotnet test .\SDDTemplate.slnx
```

Verify formatting:

```powershell
dotnet format --verify-no-changes
```

## Documentation Map

- [Architecture](docs/architecture.md): system topology, sources of truth, ticket locks, and deployment-lane ownership.
- [Development](docs/development.md): implementation workflow, local commands, OpenSpec usage, and quality gates.
- [Deployment](docs/deployment.md): artifact promotion, QA evidence, versions, PROD, rollback, and hotfix rules.
- [Context Management](docs/context-management.md): context authority, freshness, conflict handling, and handoff rules.
- [Parallel Delivery](docs/parallel-delivery.md): optional multi-ticket coordination, worktree isolation, and serialized deployment lanes.
- [Delivery Contract](.codex/skills/_shared/delivery-contract.md): agent-enforced operational policy.

If these documents conflict, the delivery contract wins for automation behavior until the docs are corrected.

## Operator Commands

Common Codex chat requests:

```text
List Plane Todo tickets
Start the next Plane Todo ticket
Start E2EPROJECT-1
Continue E2EPROJECT-1
Where does E2EPROJECT-1 stand?
Run QA for E2EPROJECT-1
Promote E2EPROJECT-1 to PROD
Audit recent delivery workflow
Audit failed QA/review/CI run
Run agent self-improvement audit
Coordinate parallel Plane tickets
```

Direct Docker Compose startup is also supported when the local Plane environment file is configured:

```powershell
docker compose --env-file .\infra\plane\variables.env -f .\infra\compose.yml up -d
```

## Repository Shape

```text
SDDTemplate.slnx
docs/
src/
tests/
openspec/
infra/
.gitea/
.codex/
artifacts/
```

Detailed structure is documented in [Architecture](docs/architecture.md) and [Development](docs/development.md).

## Key Principle

```text
Local tools manage the delivery workflow.
Azure hosts only DEV, QA, and PROD runtime resources.
Nexus stores the exact build artifact promoted between environments.
Plane records ticket state and generated workflow checkpoints.
Production promotion is explicit and artifact-based.
```
