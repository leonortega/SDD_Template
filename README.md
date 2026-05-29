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

## Ticket Lifecycle

Plane states used by the delivery workflow:

- `Todo`: work is not started.
- `In Progress`: branch and implementation are active.
- `In Review`: PR exists and awaits review or merge.
- `QA`: the artifact is deployed to QA and awaits E2E validation.
- `Done`: E2E QA passed and the artifact is eligible for explicit PROD promotion.

Useful chat requests:

```text
List Plane Todo tickets
Start the next Plane Todo ticket
Start E2EPROJECT-1
Continue E2EPROJECT-1
Where does E2EPROJECT-1 stand?
Run QA for E2EPROJECT-1
Promote E2EPROJECT-1 to PROD
```

The ticket key pattern is configured in `.codex/delivery-policy.json` and currently matches:

```text
E2EPROJECT-[0-9]+
```

Ticket delivery is locked to one active ticket with ignored `.codex/delivery-context.local.json`. Child skills verify that Plane comments, branch, PR, artifact commit, QA evidence, RC tag, and PROD release lineage match the locked ticket before mutating or promoting anything.

## Parallel Ticket Delivery

Use the parallel coordinator when more than one ticket should be active at the same time:

```text
Coordinate parallel Plane tickets
```

That routes through `.codex/skills/parallel-ticket-coordinator`. The coordinator assigns one Git worktree and one local ticket lock to each active ticket, then invokes the existing role skills from inside the assigned worktree.

Default placeholder-safe config lives in `.codex/client-tools.example.json`:

```json
"parallelDelivery": {
  "enabled": false,
  "maxActiveTickets": 2,
  "worktreeRoot": "../ticket-worktrees",
  "deploymentLanePolicy": "serialized",
  "agentModelPolicy": {
    "pipelineStatus": {
      "model": "gpt-5.4-mini",
      "reasoningEffort": "low"
    },
    "implementation": {
      "model": "gpt-5.3-codex",
      "reasoningEffort": "medium"
    },
    "deployToProd": {
      "model": "gpt-5.4",
      "reasoningEffort": "high"
    }
  }
}
```

Parallel implementation uses this shape:

```text
SDD_template/                  coordinator checkout
../ticket-worktrees/
  e2eproject-123/              ticket worktree with its own .codex/delivery-context.local.json
  e2eproject-124/              ticket worktree with its own .codex/delivery-context.local.json
```

Planning, implementation, PR validation, and review can run concurrently across ticket worktrees. DEV, QA, E2E QA, PROD, rollback, and hotfix promotion stay serialized because they share Azure environments, Nexus release manifests, RC/final tags, and Plane deployment evidence. The coordinator records active ticket mappings and deployment-lane ownership in ignored `.codex/parallel-delivery.local.json`.

`agentModelPolicy` controls cost per on-the-fly sub-agent. Read-only status and mechanical promotion checks can use smaller models and lower reasoning; implementation, review, PROD, rollback, and hotfix work use stronger models or higher reasoning. `model: "inherit"` means the coordinator should not override the parent run's model.

## Quality Gates

Gitea PR validation is the source of truth. Local hooks are convenience checks only.

PR validation runs:

- `dotnet restore`
- `dotnet format --verify-no-changes --no-restore`
- `dotnet build -c Release --no-restore`
- `dotnet test -c Release --no-build --collect:"XPlat Code Coverage"`
- coverage enforcement, defaulting to `80%`
- `dotnet list package --vulnerable --include-transitive`
- Gitleaks secret scan
- Trivy filesystem scan for high and critical findings

The workflow file is `.gitea/workflows/pr-validation.yml`. See `.gitea/workflows/README.md` for required repository secrets and branch protection guidance.

Recommended branch rules:

- Block direct pushes to `dev` and `main`.
- Require pull requests into `dev`.
- Require the PR validation workflow to pass.
- Require review approval or the configured review label.
- Block merge while `needs-tests` or `needs-changes` is present.
- Update `main` only after QA passes for the exact artifact commit.

## Artifact And Release Rules

Nexus is mandatory for DEV, QA, PROD, and rollback promotion. The workflow does not rebuild between environments and does not deploy from local files.

Artifact identity is the commit SHA:

```text
app/{commitSha}/app.zip
app/{commitSha}/app.zip.sha256
app/{commitSha}/commit.sha
app/{commitSha}/release.json
```

`commit.sha` must match the artifact commit. `app.zip.sha256` must verify before deployment.

`release.json` is validated against `.codex/skills/_shared/release.schema.json`. It records the artifact checksum, Plane ticket key, DEV/QA/PROD deployment metadata, QA evidence, RC version, final release version, and rollback lineage as the artifact moves through the pipeline.

Version rules:

- Source RC format: `vMAJOR.MINOR.PATCH-rc.N`
- Final release format: `vMAJOR.MINOR.PATCH`
- RC tags point to the QA-tested artifact commit.
- Final tags point to the QA-approved artifact commit.

## Deployment Rules

Push-triggered deployment is ticket-gated. Only application or test changes with a commit message or merged PR title that starts with the configured ticket key can deploy automatically.

Flow:

```text
feature branch -> dev -> DEV -> QA -> main -> PROD
```

DEV and QA deploy from `dev` using the same Nexus ZIP artifact for the same commit SHA. PROD deploys only from `main` when `main` points to the QA-approved packaged commit, or through an explicit manual dispatch that supplies an existing `artifact_commit_sha`, `release_version`, and `source_rc_version`.

PROD promotion is explicit. QA passing makes a ticket eligible for PROD; it does not automatically promote the artifact unless the user asks for PROD promotion or a ticket-gated merge to `main` triggers the PROD-only workflow.

Rollback deploys a previously verified Nexus artifact and does not rewrite `main`. After rollback, the expected follow-up is a hotfix PR, revert PR, or an explicit temporary divergence note with an owner and resolution plan.

## Operator Skills

The repo-local workflow is encoded as Codex skills under `.codex/skills/`.

Common entry points:

- `configure-dev-environment`: configure Plane, Gitea, runner, quality gates, Nexus, Azure, and observability.
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

## Key Principle

```text
Local tools manage the delivery workflow.
Azure hosts only DEV, QA, and PROD runtime resources.
Nexus stores the exact build artifact promoted between environments.
Plane records ticket state and generated workflow checkpoints.
Production promotion is explicit and artifact-based.
```
