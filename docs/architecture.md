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
