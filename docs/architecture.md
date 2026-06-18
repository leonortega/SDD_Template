# Architecture

This repository is a local agentic delivery lab. Its current profile is a .NET Blazor site, ASP.NET Core API, and shared data layer, but the delivery skills are designed to route through `.codex/project-profile.json` and provider adapters instead of hard-coding one stack or toolchain. The repo is designed so Codex-style agents can move a configured ticket from idea to production through explicit planning, implementation, review, artifact promotion, QA, and release checkpoints.

## System Topology

- The frontend application lives under `src/SDDTemplate.Site`.
- The REST API application lives under `src/SDDTemplate.Api`.
- The EF Core entities, DbContext, migrations, and database setup live under `src/SDDTemplate.Data`.
- Application behavior is tested from `tests/SDDTemplate.Site.Tests`.
- Local Docker Compose infrastructure provides Plane, Gitea, the Gitea Actions runner, Nexus, Dozzle, Grafana, and Seq. OpenTelemetry Collector Contrib consumes Azure Event Hub and forwards console logs into Seq.
- Azure hosts only the remote DEV, QA, and PROD application runtimes. The web and API runtimes may be deployed as separate App Service apps per environment.
- Nexus stores immutable application artifacts and release manifests.
- Plane records ticket state, generated workflow markers, and human-readable delivery comments.
- OpenSpec records planned behavior before implementation.
- `.codex/skills` encode operator workflows for setup, implementation, review, deployment, QA, rollback, and hotfix.

## Technology Stack And Tool Set

The canonical non-secret stack and tool declaration is `.codex/project-profile.json`. This document explains the current repository profile for humans; agents must read the profile first, then load the selected adapter files under `.codex/providers/`. Configuration audits should verify the profile against current files such as `global.json`, `.csproj` files, `infra/**`, `.gitea/workflows/**`, monitoring provisioning, and OpenSpec context.

- Plane is the ticket system and records generated delivery markers, state transitions, and handoff comments.
- OpenSpec captures planned behavior, requirements, design decisions, and task checklists before implementation and after review feedback.
- Gitea hosts source control and pull requests; Gitea Actions is the authoritative PR validation and deployment workflow runner.
- Nexus stores immutable artifacts, checksums, release manifests, and preferred QA evidence bundles.
- Azure App Service hosts only the DEV, QA, and PROD application runtimes.
- Azure Monitor and Log Analytics remain Azure-side observability sources. Seq provides local Azure application console log search for DEV, QA, and PROD by consuming Azure Event Hub through an OpenTelemetry Collector Contrib profile. Dozzle provides local container log inspection.
- Repo-local Codex skills under `.codex/skills` are copied from verified repository sources when recommended. `project-guidance-discover` scans the project, checks repo-local workflow sources, searches OpenAI official sources, official tool and technology-owner sources, `skills.sh`/`skills` or marketplace repository leads, and clearly labeled community sources in that order, researches extra useful skills, MCPs, plugins, tools, references, practices, standards, and Codex-applicable IDE helpers, then asks the user only to confirm, dismiss, or name omissions. Confirmation means record accepted ids and run guarded acquisition immediately. `project-guidance-acquire` uses guarded auto acquisition: safe repo-local, non-secret skills may be copied with `sourceKind` attribution, and supported MCP/plugin/tool/IDE configuration runs without a second install prompt for confirmed items. Global, IDE, secret-bearing, privileged, MCP/plugin, or reboot-required installs still require explicit confirmation when they introduce new scope, secrets, or different items. Restart and reboot requirements are aggregated and reported once after all feasible acquisitions finish. `project-guidance-mapper` maps delivery steps to workflow skills, expert skills, MCPs, plugins, tools, references, practices, and standards through ignored `.codex/tool-recommendations.local.json` `usedInSteps`.

## Sources Of Truth

- `.codex/project-profile.json` is authoritative for selected stack, providers, ticket key pattern, branch policy, environments, quality gates, and adapter paths.
- Selected `.codex/providers/*.md` files are authoritative for project-specific provider behavior that generic skills should not hard-code.
- The configured ticket provider is authoritative for ticket state and generated checkpoint comments.
- OpenSpec is authoritative for planned feature behavior while a change is active.
- `.codex/skills/_shared/delivery-contract.md` is authoritative for agent-enforced delivery behavior.
- `docs/` holds durable human-readable project context.
- The configured review provider validation is authoritative for PR quality gates.
- The configured artifact provider `app/{commitSha}/release.json` is authoritative for artifact lineage across environments.

## Ticket And Worktree Isolation

Normal delivery is locked to one active ticket with ignored `.codex/delivery-context.local.json`. Child skills must verify that resolved ticket, branch, PR, artifact commit, QA evidence, RC tag, and PROD lineage match the locked ticket before mutation. The lock is retained after QA Done so explicit PROD promotion can reuse artifact and RC context; `plane-start-ticket` may replace it lazily only when starting another ticket and the previous locked ticket is verified in the configured Done state.

Parallel delivery uses one Git worktree and one `.codex/delivery-context.local.json` per active ticket. The coordinator records active worktrees and deployment-lane ownership in ignored `.codex/parallel-delivery.local.json`.

## Deployment Lane

Implementation and review can run concurrently across isolated worktrees. DEV, QA, E2E QA, PROD, rollback, and hotfix promotion are serialized because they share Azure environments, Nexus release manifests, RC/final tags, and Plane deployment evidence.
