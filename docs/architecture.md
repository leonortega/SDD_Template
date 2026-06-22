# Architecture

This repository is a local agentic delivery lab. Its current profile is a .NET Blazor site, ASP.NET Core API, and shared data layer, but the delivery skills are designed to route through `.codex/project-profile.json` and provider adapters instead of hard-coding one stack or toolchain. The repo is designed so Codex-style agents can move a configured ticket from idea to production through explicit planning, implementation, review, artifact promotion, QA, and release checkpoints.

## System Topology

- The frontend application lives under `src/SDDTemplate.Site`.
- The REST API application lives under `src/SDDTemplate.Api`.
- The EF Core entities, DbContext, migrations, and database setup live under `src/SDDTemplate.Data`.
- Application behavior is tested from `tests/SDDTemplate.Site.Tests`.
- Local Docker Compose infrastructure provides Plane, Gitea, the Gitea Actions runner, Nexus, Dozzle, Grafana, and Seq. Rancher Desktop captures sanitized Kubernetes pod logs into Seq during local deployment evidence collection; OpenTelemetry Collector Contrib consumes Azure Event Hub only when the optional Azure lane is selected.
- Rancher Desktop Kubernetes hosts the default DEV, QA, and PROD application runtimes through namespaces `sdd-dev`, `sdd-qa`, and `sdd-prod`.
- Azure can host optional remote DEV, QA, and PROD application runtimes when its adapter is explicitly selected.
- Nexus stores immutable application artifacts, container image metadata, release manifests, and QA evidence.
- Plane records ticket state, generated workflow markers, and human-readable delivery comments.
- OpenSpec records planned behavior before implementation.
- `.codex/skills` encode operator workflows for setup, implementation, review, deployment, QA, rollback, and hotfix.

## Technology Stack And Tool Set

The canonical non-secret stack and tool declaration is `.codex/project-profile.json`. This document explains the current repository profile for humans; agents must read the profile first, then load the selected adapter files under `.codex/providers/`. Configuration audits should verify the profile against current files such as `global.json`, `.csproj` files, `infra/**`, `.gitea/workflows/**`, monitoring provisioning, and OpenSpec context.

- Plane is the ticket system and records generated delivery markers, state transitions, and handoff comments.
- OpenSpec captures planned behavior, requirements, design decisions, and task checklists before implementation and after review feedback.
- Gitea hosts source control and pull requests; Gitea Actions is the authoritative PR validation and deployment workflow runner.
- Nexus stores immutable artifacts, checksums, release manifests, container image digest metadata, and preferred QA evidence bundles.
- Rancher Desktop Kubernetes is the default local-cloud deployment provider.
- Azure App Service remains an optional deployment adapter, not the default provider.
- Azure Monitor and Log Analytics remain Azure-side observability sources when the optional Azure lane is used. Seq provides Rancher Desktop pod-log search through the local capture script. Dozzle provides local container log inspection.
- Repo-local Codex skills under `.codex/skills` are copied from verified repository sources when recommended. `project-guidance-discover` scans the project, checks repo-local workflow sources, searches OpenAI official sources, official tool and technology-owner sources, `skills.sh`/`skills` or marketplace repository leads, and clearly labeled community sources in that order, researches extra useful skills, MCPs, plugins, tools, references, practices, standards, and Codex-applicable IDE helpers, then asks the user only to confirm, dismiss, or name omissions. Confirmation means record accepted ids and run guarded acquisition immediately. `project-guidance-acquire` uses guarded auto acquisition: safe repo-local, non-secret skills may be copied with `sourceKind` attribution, and supported MCP/plugin/tool/IDE configuration runs without a second install prompt for confirmed items. Global, IDE, secret-bearing, privileged, MCP/plugin, or reboot-required installs still require explicit confirmation when they introduce new scope, secrets, or different items. Restart and reboot requirements are aggregated and reported once after all feasible acquisitions finish. `project-guidance-mapper` maps delivery steps to workflow skills, expert skills, MCPs, plugins, tools, references, practices, and standards through ignored `.codex/tool-recommendations.local.json` `usedInSteps`.

## Sources Of Truth

- `.codex/project-profile.json` is authoritative for selected stack, providers, ticket key pattern, branch policy, environments, quality gates, and adapter paths.
- Selected `.codex/providers/*.md` files are authoritative for project-specific provider behavior that generic skills should not hard-code.
- The configured ticket provider is authoritative for ticket state and generated checkpoint comments.
- OpenSpec is authoritative for planned feature behavior while a change is active.
- `.codex/skills/_shared/delivery-contract.md` is authoritative for agent-enforced delivery behavior.
- `docs/` holds durable human-readable project context.
- The configured review provider validation is authoritative for PR quality gates.
- The configured artifact provider `app/{commitSha}/release.json` is authoritative for artifact lineage across environments. For the Rancher Desktop lane, `app/{commitSha}/container-images.json` records the digest-pinned runtime image set promoted through local namespaces.

## Ticket And Worktree Isolation

Normal delivery is locked to one active ticket with ignored `.codex/delivery-context.local.json`. Child skills must verify that resolved ticket, branch, PR, artifact commit, QA evidence, RC tag, and PROD lineage match the locked ticket before mutation. The lock is retained after QA Done so explicit PROD promotion can reuse artifact and RC context; `dev-flow-start-ticket` may replace it lazily only when starting another ticket and the previous locked ticket is verified in the configured Done state.

Parallel delivery uses one Git worktree and one `.codex/delivery-context.local.json` per active ticket. The coordinator records active worktrees and deployment-lane ownership in ignored `.codex/parallel-delivery.local.json`.

## Deployment Lane

Implementation and review can run concurrently across isolated worktrees. DEV, QA, E2E QA, PROD, rollback, and hotfix promotion are serialized because they share runtime environments, Nexus release manifests, RC/final tags, and Plane deployment evidence.
