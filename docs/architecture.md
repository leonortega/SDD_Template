# Architecture

This repository is a local agentic delivery lab for a .NET Blazor site. The repo is designed so Codex-style agents can move a Plane ticket from idea to production through explicit planning, implementation, review, artifact promotion, QA, and release checkpoints.

## System Topology

- The application lives under `src/SDDTemplate.Site` and is tested from `tests/SDDTemplate.Site.Tests`.
- Local Docker Compose infrastructure provides Plane, Gitea, the Gitea Actions runner, Nexus, Dozzle, Prometheus, and Grafana.
- Azure hosts only the remote DEV, QA, and PROD application runtimes.
- Nexus stores immutable application artifacts and release manifests.
- Plane records ticket state, generated workflow markers, and human-readable delivery comments.
- OpenSpec records planned behavior before implementation.
- `.codex/skills` encode operator workflows for setup, implementation, review, deployment, QA, rollback, and hotfix.

## Technology Stack And Tool Set

The intended delivery tool set is tracked here so agents can distinguish project intent from accidental local drift. Configuration audits should verify this intent against current files such as `global.json`, `.csproj` files, `infra/**`, `.gitea/workflows/**`, monitoring provisioning, and OpenSpec context.

- Plane is the ticket system and records generated delivery markers, state transitions, and handoff comments.
- OpenSpec captures planned behavior, requirements, design decisions, and task checklists before implementation and after review feedback.
- Gitea hosts source control and pull requests; Gitea Actions is the authoritative PR validation and deployment workflow runner.
- Nexus stores immutable artifacts, checksums, release manifests, and preferred QA evidence bundles.
- Azure App Service hosts only the DEV, QA, and PROD application runtimes.
- Prometheus and Grafana provide local infrastructure and Azure application health visibility; Dozzle provides local container log inspection.
- Repo-local Codex skills under `.codex/skills` are copied from repository sources when recommended. `project-guidance-discover` scans the project and asks the user for additional desired skills or guidance, `project-guidance-acquire` manually copies confirmed skill items, and `project-guidance-mapper` maps delivery steps to workflow skills, expert skills, tools, references, practices, and standards through ignored `.codex/tool-recommendations.local.json` `usedInSteps`. Skills are not installed by command, and MCP/plugin setup is manual configuration unless a later explicit task authorizes otherwise.

## Sources Of Truth

- Plane is authoritative for ticket state and generated checkpoint comments.
- OpenSpec is authoritative for planned feature behavior while a change is active.
- `.codex/skills/_shared/delivery-contract.md` is authoritative for agent-enforced delivery behavior.
- `docs/` holds durable human-readable project context.
- Gitea PR validation is authoritative for PR quality gates.
- Nexus `app/{commitSha}/release.json` is authoritative for artifact lineage across environments.

## Ticket And Worktree Isolation

Normal delivery is locked to one active ticket with ignored `.codex/delivery-context.local.json`. Child skills must verify that resolved ticket, branch, PR, artifact commit, QA evidence, RC tag, and PROD lineage match the locked ticket before mutation.

Parallel delivery uses one Git worktree and one `.codex/delivery-context.local.json` per active ticket. The coordinator records active worktrees and deployment-lane ownership in ignored `.codex/parallel-delivery.local.json`.

## Deployment Lane

Implementation and review can run concurrently across isolated worktrees. DEV, QA, E2E QA, PROD, rollback, and hotfix promotion are serialized because they share Azure environments, Nexus release manifests, RC/final tags, and Plane deployment evidence.
