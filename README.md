# Product-Free SDLC Shell

This repository is an agentic SDLC shell. It keeps the delivery workflow, local platform, provider adapters, OpenSpec process, and Codex skills needed to start a new product from zero.

There is no current application implementation in this repo. Add a new product stack in a future change, then wire its build, test, package, deployment, and QA gates into the existing delivery workflow.

## What Remains

- OpenProject-ticketed delivery workflow.
- OpenSpec planning structure.
- Gitea repository and review workflow guidance.
- Nexus artifact and release-lineage guidance.
- Rancher Desktop local deployment platform guidance.
- Observability platform guidance for Seq, Grafana, and Dozzle.
- Generic Playwright and TDD skills for future product work.
- Repo-local Codex workflow skills under `.codex/skills/`.
- Delivery helper tooling under `tools/`.

## Current Shape

```text
docs/
openspec/
infra/
.gitea/
.codex/
tools/
artifacts/        # ignored runtime/evidence output
```

The product application folders are intentionally absent:

```text
src/
tests/
```

Create them only when the new product stack is chosen.

## Start A New Product

1. Define the new product stack and delivery expectations.
2. Put local stack choices in ignored `.codex/project-profile.local.json`; keep `.codex/project-profile.json` for common provider, workflow, and quality defaults.
3. Add product source and tests under the paths chosen for the new stack.
4. Add OpenSpec specs for the new product behavior.
5. Add app targets to `infra/deployment/apps.json` only when there is something deployable.
6. Replace placeholder Gitea workflows with stack-specific build, test, package, deployment, and QA jobs.

## Common Platform Commands

Start local delivery infrastructure:

```bash
python -m tools.sdd_cli infra up
```

Stop it:

```bash
python -m tools.sdd_cli infra down
```

Run delivery helper tests when their dependencies are available:

```bash
python -m pytest tools/sdd_cli/tests
```

## Documentation Map

- [Architecture](docs/architecture.md): product-free shell topology and sources of truth.
- [Development](docs/development.md): how to add the next product stack.
- [Deployment](docs/deployment.md): deployment shell and app-target wiring.
- [Context Management](docs/context-management.md): context authority, freshness, conflict handling, and handoff rules.
- [Parallel Delivery](docs/parallel-delivery.md): optional multi-ticket coordination.
- [Delivery Contract](.codex/skills/_shared/delivery-contract.md): agent-enforced operational policy.

## Current Boundary

This repo is not a runnable product app today. It is the delivery shell for the next product.

Keep workflow and provider changes small until the new product stack is selected. Do not add stack-specific tools, MCPs, skills, or CI jobs before they are needed.
