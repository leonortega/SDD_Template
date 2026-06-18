# Module Map Memory

## Application And Tests

- Type: Fact
- Status: Active
- Source: `docs/development.md`, repository listing
- Last verified: 2026-05-29

- App project: `src/SDDTemplate.Site`.
- Test project: `tests/SDDTemplate.Site.Tests`.
- Solution: `SDDTemplate.slnx`.
- Delivery helper project: `tools/SDDTemplate.DeliveryTools`.

## Documentation Modules

- Type: Fact
- Status: Active
- Source: `README.md`, `docs/context-management.md`
- Last verified: 2026-05-29

- Architecture/topology/source-of-truth finding -> `docs/architecture.md`.
- Local setup, commands, repo conventions, testing, or quality gates -> `docs/development.md`.
- Artifact, deployment, QA, release, rollback, or monitoring finding -> `docs/deployment.md`.
- Agent context loading, freshness, authority, handoff, or conflict rule -> `docs/context-management.md`.
- Enforceable automation behavior -> `.codex/skills/_shared/delivery-contract.md` plus affected skills and tests.

## Skill Modules

- Type: Fact
- Status: Active
- Source: `README.md`, `.codex/skills/`
- Last verified: 2026-05-29

Common workflow entry points:

- `configure-dev-environment`
- `dev-flow-pipeline-status`
- `dev-flow-parallel-ticket-coordinator`
- `dev-flow-continue-implementation`
- `dev-flow-start-ticket`
- `dev-flow-implement-ticket`
- `dev-flow-pr-review-agent`
- `dev-ops-post-merge-deploy`
- `dev-ops-deploy-qa`
- `quality-test-e2e`
- `dev-ops-deploy-prod`
- `dev-ops-rollback-prod`
- `dev-ops-hotfix-prod`

## Shared Delivery Helpers

- Type: Fact
- Status: Active
- Source: `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-05-29

Use `.codex/skills/_shared/scripts/delivery_tools.ps1` for deterministic delivery mechanics such as artifact paths, ignore checks, RC versioning, delivery policy reading, ticket key extraction, coverage threshold reading, Cobertura parsing, release manifest validation, ticket lock validation, deployment lane validation, Plane comment rendering, and release manifest updates.

