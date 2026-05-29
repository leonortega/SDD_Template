# Agentic E2E Development Lab

This repository is a template for a local, agent-driven software delivery lab. Its goal is to let Codex-style agents take a Plane ticket from idea to production using the same checks, handoffs, artifacts, and promotion rules a real engineering team would use.

The lab keeps delivery tooling local and deployment targets remote:

- Local Docker Compose runs Plane, Gitea, the Gitea Actions runner, Nexus, Dozzle, Prometheus, and Grafana.
- Azure hosts only the DEV, QA, and PROD application runtimes.
- Nexus stores the immutable build artifact promoted across DEV, QA, PROD, and rollback.
- Plane is the source of ticket state, generated workflow markers, and delivery comments.
- OpenSpec records the planned behavior before implementation.

## Current Workflow

The current delivery flow is:

```text
Plane Todo
  -> branch + OpenSpec proposal
  -> implementation + tests
  -> Gitea PR
  -> PR validation + Codex review agent
  -> merge to dev
  -> Nexus package + Azure DEV + Azure QA
  -> E2E QA evidence
  -> Plane Done
  -> explicit PROD promotion to main/PROD
  -> rollback or hotfix when needed
```

Normal ticket work is driven from Codex chat. The high-level entry point is:

```text
automatically continue this ticket
```

or any equivalent request to continue, resume, implement, deploy, QA, or hand off a ticket. That routes through `.codex/skills/automatic-implement-ticket`, which inspects Plane, Git, Gitea, Nexus, OpenSpec, QA evidence, tags, and PROD state, then delegates to the next focused workflow skill.

The workflow is intentionally checkpoint-based. Reruns continue from existing Plane comments, branch names, PRs, Nexus artifacts, QA evidence, tags, and release manifests instead of restarting from the beginning.

## Repository Layout

```text
SDDTemplate.slnx
docs/
|-- architecture.md
|-- context-management.md
|-- deployment.md
`-- development.md
src/
`-- SDDTemplate.Site/
tests/
`-- SDDTemplate.Site.Tests/
openspec/
`-- changes/
infra/
|-- compose.yml
|-- up.ps1
|-- down.ps1
|-- plane/
|-- gitea/
|-- nexus/
|-- monitoring/
`-- azure/
.gitea/
`-- workflows/
.codex/
|-- skills/
|-- client-tools.example.json
|-- quality.example.json
`-- delivery-policy.json
artifacts/
`-- qa/
```

Use `compose.yml` consistently for Docker Compose files.

## Canonical Context

Durable project context lives in `docs/`:

- `docs/context-management.md`: context authority, freshness, conflict, and handoff rules.
- `docs/architecture.md`: system topology, sources of truth, ticket locks, and deployment-lane ownership.
- `docs/development.md`: implementation workflow, local commands, OpenSpec usage, and quality gates.
- `docs/deployment.md`: artifact promotion, QA evidence, versions, PROD, rollback, and hotfix rules.

The shared delivery contract remains `.codex/skills/_shared/delivery-contract.md`. It is the agent-enforced operational policy. If docs and the delivery contract conflict, the delivery contract wins for automation behavior until the docs are corrected.

Every implementation must run a Context Findings Review. Durable findings update the matching `docs/` file in the same PR. If no durable context changed, the PR body and Plane handoff comment must state `Docs: no durable context changes`.

## Local Development

Build the solution from the repository root:

```powershell
dotnet build .\SDDTemplate.slnx
```

Run tests:

```powershell
dotnet test .\SDDTemplate.slnx
```

Run formatting verification:

```powershell
dotnet format --verify-no-changes
```

Start the local delivery platform:

```powershell
.\infra\up.ps1
```

Stop it:

```powershell
.\infra\down.ps1
```

The same stack can be started directly with Docker Compose:

```powershell
docker compose --env-file .\infra\plane\variables.env -f .\infra\compose.yml up -d
```

## Configuration Workflow

Configure the lab through Codex chat:

```text
config infra
```

That routes through `.codex/skills/configure-dev-environment`, which delegates to the specific setup skills for Plane, Gitea, the Gitea Actions runner, Nexus, Azure, quality gates, and observability.

Configuration order:

```text
Plane -> Gitea -> Gitea Actions runner -> quality gates -> Nexus -> Azure DEV -> Azure QA -> Azure PROD -> Prometheus -> Grafana
```

During full setup or base-code creation, the configurator can also run a recommended tooling audit:

```powershell
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode AuditRecommendedTools
```

The audit suggests stack-relevant MCPs, plugins, and Codex skills from `.codex/tool-recommendations.example.json`. Skill acquisition is manual by default: read the source repository's `SKILL.md`, create `.codex/skills/{skill-name}/`, write the new `SKILL.md`, and copy only required referenced scripts or templates. Plugin and MCP setup should prefer manual configuration instructions over installer commands, and secrets must never be configured automatically.

The main local files are:

```text
.codex/client-tools.local.json
.codex/quality.local.json
infra/plane/variables.env
infra/gitea/runner.env
infra/monitoring/prometheus.local.yml
```

Tracked example files remain placeholder-safe. Real tokens, local secrets, generated Plane secrets, local Azure hostnames, and delivery locks belong only in ignored local files.

Credentials must be supplied through supported UI/API/CLI paths. The workflow must not read secrets from Docker containers, mounted volumes, databases, logs, or committed files.

## Workflow References

Useful chat requests:

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
```

Use `Coordinate parallel Plane tickets` when more than one ticket should be active at the same time. Read `docs/parallel-delivery.md` first for the dry-run checklist, worktree layout, role contracts, serialized deployment lane rules, and cleanup/recovery steps.

Detailed workflow references:

- `docs/context-management.md`: ticket states, locks, context authority, freshness, conflict handling, and handoff rules.
- `docs/architecture.md`: parallel worktree isolation, deployment-lane ownership, and source-of-truth topology.
- `docs/development.md`: implementation flow, OpenSpec usage, quality gates, and local validation commands.
- `docs/deployment.md`: artifact identity, release manifests, versioning, QA evidence, deployment, PROD, rollback, and hotfix rules.
- `docs/parallel-delivery.md`: optional multi-ticket coordination, dry-run preflight, subagent role contracts, and cleanup/recovery.
- `.codex/skills/_shared/delivery-contract.md`: agent-enforced operational rules.

## Operator Skills

The repo-local workflow is encoded as Codex skills under `.codex/skills/`.

Common entry points:

- `configure-dev-environment`: configure Plane, Gitea, runner, quality gates, Nexus, Azure, and observability.
- `delivery-retrospective-audit`: inspect recent delivery evidence and propose evidence-gated workflow or agent self-improvements.
- `pipeline-status`: read-only dashboard for tickets, PRs, artifacts, QA evidence, tags, and deployments.
- `parallel-ticket-coordinator`: coordinate multiple active tickets across isolated Git worktrees while serializing deployment promotion.
- `automatic-implement-ticket`: inspect state and route to the next valid delivery step.
- `plane-start-ticket`: select a Plane ticket, create branch context, and create the OpenSpec proposal.
- `implement-ticket`: implement an active ticket and hand off a PR.
- `gitea-pr-review-agent`: review a specific Gitea PR and apply review labels.
- `post-merge-deploy`: continue after a PR merges to `dev`.
- `deploy-to-qa`: verify the merged PR artifact and promote through DEV/QA.
- `test-e2e`: run QA checks, store evidence, and move passing tickets to `Done`.
- `deploy-to-prod`: promote a QA-approved artifact to PROD.
- `rollback-prod`: restore PROD to a previously verified artifact.
- `hotfix-prod`: run an expedited, gated production hotfix.

The shared delivery contract is `.codex/skills/_shared/delivery-contract.md`. When delivery behavior changes, update the related skills, configuration docs, workflow files, and regression tests together.

## Quality: Audit Agents & Self-Improvement

The delivery lab includes a manual quality lane for improving agent behavior from evidence. Use `delivery-retrospective-audit` after QA bugs, meaningful review misses, CI/tooling blockers, deployment blockers, delivery/configure skill drift, or as a periodic manual review after several completed tickets.

The audit is read-only by default. It can recommend skill, contract, docs, template, quality-gate, memory, or follow-up ticket changes, but durable workflow changes require repeated evidence, a high-severity gap, direct delivery-contract drift, or a missing deterministic check for an already-required rule. Recurring scheduled audits should be introduced through a separate follow-up ticket that defines cadence, ownership, output location, and allowed mutations.

## Key Principle

```text
Local tools manage the delivery workflow.
Azure hosts only DEV, QA, and PROD runtime resources.
Nexus stores the exact build artifact promoted between environments.
Plane records ticket state and generated workflow checkpoints.
Production promotion is explicit and artifact-based.
```
