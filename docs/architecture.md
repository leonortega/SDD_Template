# Architecture

This repository is a product-free SDLC shell. The previous sample application has been removed so a new product can start from zero while reusing the delivery workflow.

## System Topology

- `.codex/skills` contains repo-local workflow skills for configuration, ticket start, planning, implementation orchestration, review, deployment, QA coordination, rollback, and retrospective work.
- `.codex/project-profile.json` is the tracked non-secret declaration for common providers, workflow, and quality defaults.
- `.codex/project-profile.local.json` is the ignored local overlay for stack choices and project-specific adapter experiments.
- `.codex/providers` contains provider adapters for the delivery platform.
- `openspec/config.yaml` keeps the OpenSpec process available for future product specs.
- `infra/` contains local platform infrastructure for ticketing, repository, artifact storage, deployment support, and observability.
- `.gitea/workflows/` contains placeholder workflows until a new product stack is added.
- `tools/` contains delivery helper tooling.

The `src/` and `tests/` product trees are intentionally absent.

## Sources Of Truth

- Current user request and active ticket context define the work.
- `.codex/project-profile.json` defines common selected providers and workflow defaults; `.codex/project-profile.local.json` may add local stack choices before a product stack is committed.
- Selected `.codex/providers/*.md` files define provider behavior.
- OpenSpec artifacts define planned behavior for active product changes.
- `.codex/skills/_shared/delivery-contract.md` defines agent-enforced delivery behavior.
- `docs/` holds durable human-readable project context.

## Product Stack

No product stack is selected. Future work can draft stack choices in `.codex/project-profile.local.json`. When the new product becomes real, update the tracked profile, docs, workflow jobs, deployment targets, quality gates, and OpenSpec specs together.

Generic TDD and Playwright skills remain available for future implementation and browser-facing validation, but they are not tied to any current product app.

## Versioned Consumer Installation

This repository is the canonical SDLC tool source. Product repositories consume pinned releases through `python -m tools.sdd_cli tool install --version vMAJOR.MINOR.PATCH --target <repo>` and later `tool update` with a newer version. When `--version` is omitted, install resolves the latest final Git tag matching `vMAJOR.MINOR.PATCH` and ignores release-candidate tags.

Installed repos get only runtime workflow assets: Codex skills, provider adapters/templates, docs, OpenSpec config, infrastructure templates, workflow templates, common non-secret config, and `tools/sdd_cli`. Tool-source-only files such as CLI tests, repo memory, OpenSpec changes, eval output, telemetry, and local config are not installed.

The consumer manifest `.codex/sdd-tool-version.json` records the installed version, source repo, source commit, checksum, managed file list, and preserved local file list. Updates replace only managed files and leave consumer project code, secrets, local overlays, and product OpenSpec changes untouched.

## Deployment Lane

Deployment providers remain configured as shell capabilities. No app target is currently deployable. `infra/deployment/apps.json` is empty until a new product adds concrete artifacts, health checks, and environment configuration.
