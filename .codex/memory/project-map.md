# Project Map Memory

## Repository Identity

- Type: Fact
- Status: Active
- Source: `README.md`, `docs/architecture.md`
- Last verified: 2026-06-11

This repository is an agentic E2E development lab and SDD/SDLC template. It is designed for Codex-style agents to move a OpenProject work package from idea to production using planning, implementation, review, artifact, QA, deployment, release, rollback, and hotfix checkpoints.

## Main Project Shape

- Type: Fact
- Status: Active
- Source: `README.md`, `docs/development.md`
- Last verified: 2026-05-29

```text
SDDTemplate.slnx
docs/
src/SDDTemplate.Site/
tests/SDDTemplate.Site.Tests/
tools/SDDTemplate.DeliveryTools/
openspec/
infra/
.gitea/
.codex/
artifacts/qa/
```

## Runtime Topology

- Type: Fact
- Status: Active
- Source: `README.md`, `docs/architecture.md`, `docs/deployment.md`
- Last verified: 2026-06-12

- Local Docker Compose provides OpenProject, Gitea, Gitea Actions runner, Nexus, Dozzle, Grafana, and Seq.
- Seq imports DEV, QA, and PROD Azure App Service logs from Log Analytics for local log search.
- Grafana uses Azure Monitor and Log Analytics for health/status dashboards.
- Azure hosts only DEV, QA, and PROD application runtimes.
- Nexus stores immutable application artifacts and release manifests.
- OpenProject records ticket state, generated workflow markers, and human-readable delivery comments.
- OpenSpec records planned behavior before implementation.
- `.codex/skills` encode operator workflows.

## Canonical Context

- Type: Fact
- Status: Active
- Source: `README.md`
- Last verified: 2026-06-11

- `docs/context-management.md`: context authority, freshness, conflict, and handoff rules.
- `docs/architecture.md`: topology, sources of truth, ticket locks, and deployment-lane ownership.
- `docs/development.md`: implementation workflow, local commands, OpenSpec usage, and quality gates.
- `docs/deployment.md`: artifact promotion, QA evidence, versions, PROD, rollback, and hotfix rules.
- `.codex/skills/_shared/delivery-contract.md`: agent-enforced operational policy.

## Local Configuration Files

- Type: Fact
- Status: Active
- Source: `README.md`, repository listing
- Last verified: 2026-05-29

Important local configuration files include:

- `.codex/client-tools.local.json`
- `.codex/quality.local.json`
- `infra/openproject/variables.env`
- `infra/monitoring/variables.env`
- `infra/azure/variables.env`
- `infra/gitea/runner.env`
- `infra/monitoring/grafana/dashboards.local/`

Tracked example files must remain placeholder-safe. Local secrets must stay in ignored local files.
