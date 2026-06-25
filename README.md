# Agentic E2E Development Lab

![Platform](https://img.shields.io/badge/platform-Windows-0078D4)
![Shell](https://img.shields.io/badge/shell-PowerShell-5391FE)
![.NET](https://img.shields.io/badge/.NET-10.0-512BD4)
![App](https://img.shields.io/badge/app-Blazor%20%2B%20ASP.NET%20Core-512BD4)
![Data](https://img.shields.io/badge/data-EF%20Core%20%2B%20SQLite-4479A1)
![Tests](https://img.shields.io/badge/tests-xUnit%20%2B%20Playwright-2EAD33)
![Delivery](https://img.shields.io/badge/delivery-OpenProject%20%7C%20OpenSpec%20%7C%20Gitea%20%7C%20Nexus-0A66C2)
![Local Cloud](https://img.shields.io/badge/local%20cloud-Rancher Desktop%20Desktop%20DEV%20%7C%20QA%20%7C%20PROD-326CE5)
![Optional Cloud](https://img.shields.io/badge/optional%20cloud-Azure%20App%20Service-0078D4)
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
- Better leadership visibility: OpenProject records the ticket state, workflow markers, handoffs, and evidence.
- Stronger quality control: Gitea pull requests, validation gates, Codex review, tests, and QA evidence are part of the normal flow.
- Safer releases: Nexus stores immutable artifacts that are promoted across DEV, QA, PROD, and rollback without rebuilding.
- Clearer accountability: production promotion is explicit, documented, and separated from QA approval.
- Practical observability: Seq, Grafana, Dozzle, Rancher Desktop Kubernetes log capture, and optional Azure diagnostics support delivery and runtime inspection.

## Who This Is For

- Engineering leaders evaluating agentic software delivery.
- Product and operations teams that need visible ticket-to-production progress.
- Delivery teams building repeatable SDLC automation.
- Consultants or vendors packaging a professional agent-assisted delivery model.
- Technical operators who need a local lab for OpenProject, Gitea, Nexus, Rancher Desktop Kubernetes, QA, release, rollback, and hotfix workflows.

## How The Delivery Flow Works

```text
Idea in OpenProject
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

- OpenProject is the work tracker and delivery record.
- OpenSpec captures the planned behavior before implementation.
- Gitea manages source control, pull requests, and validation.
- Nexus stores the exact build artifact used for deployment.
- Rancher Desktop hosts the DEV, QA, and PROD application runtimes by default.
- Azure App Service remains an optional remote DEV, QA, and PROD lane.
- Seq helps operators search sanitized Rancher Desktop pod logs and optional Azure application logs; Grafana and Dozzle help inspect health, delivery signals, and local container logs.
- Codex skills under `.codex/skills/` guide the agent through each delivery stage.

## What Is Included

### Planning And Ticket Control

- OpenProject-based ticket workflow.
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
- Rancher Desktop local lane using Nexus Docker image digests for runtime artifacts and Nexus raw paths for manifests, pointers, and QA evidence.

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
- Seq log search for app-emitted Rancher Desktop Serilog events.
- Grafana Infinity health/status dashboards for Rancher Desktop local health targets.
- Direct `/health` deployment evidence for the local lab lane.
- Dozzle for local container logs.
- Optional Azure App Service diagnostics for remote DEV, QA, and PROD runtimes.

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

## Canonical Context

`.codex/project-profile.json` is the canonical non-secret declaration for the current stack, providers, ticket key pattern, branch policy, environments, quality gates, and adapter paths. Generic delivery skills read that profile first and then load the selected `.codex/providers/*.md` adapter files for project-specific behavior. Exact versions, images, executable commands, endpoints, and secrets stay in project files, workflow files, infrastructure files, or ignored local config.

Before the first ticket starts, the workflow validates stack context and routes to `configure-dev-environment` when required docs, OpenSpec context, or recommendation catalogs are missing or drifted. Full `config infra` runs `InitProjectProfile` first to create the canonical project profile, schema, and neutral provider adapter examples before provider-specific setup, quality gates, CI, deployment, or ticket work. `configure-dev-environment` then scans stack, tooling, environments, test frameworks, and workflow files, researches extra useful skills, MCPs, plugins, tools, references, practices, standards, and Codex-applicable IDE helpers, reports suggested missing guidance, and asks the operator only to confirm, dismiss, or name omissions. Confirmation means record and install/configure supported items immediately; there is no second install prompt.

Project guidance uses guarded auto acquisition. Confirmed repo-local, non-secret skills may be copied into `.codex/skills` from verified `SKILL.md` sources; confirmed MCPs, plugins, tools, and IDE extensions are installed or configured when a platform-supported guarded path exists. Global installs, secrets, reboot-required items, or new scope still require explicit confirmation. Restart requirements are collected and reported once after all feasible acquisitions finish. `.codex/tool-recommendations.example.json` documents the tracked catalog shape, `.codex/skills/README.md` is the tracked skill ownership and naming catalog, while ignored `.codex/tool-recommendations.local.json` stores local discovery state and `project-guidance-mapper` reads that local file for step mapping.

## External Skills

External skills keep their upstream names and must be marked as external in `.codex/skills/README.md`. Whenever a new external skill is added, cite its source repository in this section and in the skill catalog before handoff.

Current external skill sources:

- `aspnet-core`: ASP.NET Core guidance from https://github.com/openai/skills/tree/main/skills/.curated/aspnet-core.
- `assertion-quality`: test assertion analysis guidance from https://github.com/dotnet/skills/tree/main/plugins/dotnet-test/skills/assertion-quality.
- `caveman`: output compression guidance from https://github.com/JuliusBrussee/caveman.
- `domain-modeling`: domain glossary and decision guidance from https://github.com/mattpocock/skills/tree/main/skills/engineering/domain-modeling.
- `dotnet-webapi`: ASP.NET Core Web API endpoint guidance from https://github.com/dotnet/skills/tree/main/plugins/dotnet-aspnet/skills/dotnet-webapi.
- `grill-me`: planning interview guidance from https://github.com/mattpocock/skills/tree/main/skills/productivity/grill-me.
- `grill-with-docs`: planning interview plus documentation guidance from https://github.com/mattpocock/skills/tree/main/skills/engineering/grill-with-docs.
- `grilling`: support skill for grill-style planning interviews from https://github.com/mattpocock/skills/tree/main/skills/productivity/grilling.
- `plan-ui-change`: Blazor UI planning guidance from https://github.com/dotnet/skills/tree/main/plugins/dotnet-blazor/skills/plan-ui-change.
- `playwright`: browser automation guidance from https://github.com/openai/skills/tree/main/skills/.curated/playwright.
- `security-best-practices`: secure coding guidance from https://github.com/openai/skills/tree/main/skills/.curated/security-best-practices.
- `tdd`: test-driven development guidance from https://github.com/mattpocock/skills/tree/main/skills/engineering/tdd.
- `test-analysis-extensions`: language-specific test analysis extensions from https://github.com/dotnet/skills/tree/main/plugins/dotnet-test/skills/test-analysis-extensions.

Agent utility skills are treated as external for naming purposes and are listed in `.codex/skills/README.md`; they are not renamed by delivery category.

Implementation handoffs must report context findings and either list updated docs or state `Docs: no durable context changes`.

## Operator Commands

Common Codex chat requests:

```text
List OpenProject Todo tickets
Start the next OpenProject Todo ticket
Start E2EPROJECT-1
Continue E2EPROJECT-1
Where does E2EPROJECT-1 stand?
Run QA for E2EPROJECT-1
Promote E2EPROJECT-1 to PROD
Audit recent delivery workflow
Audit failed QA/review/CI run
Run agent self-improvement audit
Coordinate parallel OpenProject work packages
```

Direct Docker Compose startup is also supported when the local OpenProject and monitoring environment files are configured:

```powershell
docker compose --env-file .\infra\openproject\variables.env --env-file .\infra\monitoring\variables.env -f .\infra\compose.yml up -d
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
Rancher Desktop hosts DEV, QA, and PROD runtime resources by default.
Azure App Service may host an optional remote DEV, QA, and PROD lane.
Nexus stores the exact build artifact or image metadata promoted between environments.
OpenProject records ticket state and generated workflow checkpoints.
Production promotion is explicit and artifact-based.
```

