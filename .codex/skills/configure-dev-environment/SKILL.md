---
name: configure-dev-environment
description: Router for configuring this repo's local development and delivery environment. Use when Codex needs to set up, audit, repair, or guide configuration for Plane, Gitea PR automation, Gitea Actions runner, code quality gates, Nexus artifacts, Azure DEV/QA/PROD environments, DEV-to-QA deployment promotion, Prometheus/Grafana monitoring, or when the user asks "config infra", "setup environment", or is unsure which setup area they need.
---

# Configure Dev Environment

Use this skill as the entrypoint for the repo-local delivery lab. Keep this file lean: run the shared audit, group findings by domain, then route to the focused skill or reference.

Act as a step-by-step configurator. When a required executable, SDK, CLI, scanner, local service, library, package, or runtime is missing or incompatible, stop that domain step long enough to tell the user exactly how to install it, link the official source, and list the post-install validation/configuration commands before continuing.

When setup needs values the user must supply manually, do not only ask for the values. Explain where each value comes from, why it is needed, where to configure it, the exact UI or CLI path when possible, official documentation links, and validation commands that prove the value is configured correctly.

## Safety Rules

- Never print, commit, paste into tickets, or write real tokens/secrets into tracked files.
- Update ignored local files only when applying user-confirmed secrets:
  - `.codex/client-tools.local.json`
  - `.codex/quality.local.json`
  - `infra/plane/variables.env`
  - `infra/gitea/runner.env`
  - `infra/monitoring/prometheus.local.yml`
- Keep tracked files as templates, workflows, or placeholder-safe documentation.
- Do not read secrets from Docker containers, container shells, mounted volumes, service databases, or logs.
- Do not start or stop local infra automatically. Ask first before running `.\infra\up.ps1` or `.\infra\down.ps1`.
- Use Docker only for non-secret operational checks such as service status, mounts, health, and non-sensitive provisioning logs.

## Version And Install Rules

- When a tool, SDK, CLI, runtime, scanner, or required local dependency is missing, read `references/shared-prerequisites.md`, then report: what is missing, why it is required, the install command, the official URL, and the exact command to validate/configure it after install.
- If a required item is not covered in `shared-prerequisites.md`, look up the official install documentation before advising the user. Prefer official vendor docs, release pages, or package-manager pages.
- For Docker images and library/package versions, check the current upstream stable version before editing templates or compose files. Use official release notes, official docs, GitHub releases, Docker Hub/registry metadata, or vendor lifecycle pages.
- Do not use `latest`, `main`, `nightly`, release-candidate, preview, or floating major/minor-only tags in Compose files or generated templates unless the user explicitly requests floating tags.
- Pin Docker images to the current stable patch tag when configuring infra, and update the Compose file directly when the existing tag is old or floating.
- Mention any migration notes or breaking changes discovered while checking the current version.

## Manual Value Rules

- For required secrets, tokens, passwords, repository names, cloud identifiers, or service-account values, provide a short checklist with: value name, purpose, source, destination, safe example when possible, and validation command.
- Never invent secret values and never read them from containers, mounted volumes, service databases, or logs.
- Prefer manual UI steps for first-time secret entry. Use APIs only after the user provides values explicitly in chat or an approved local secret source.
- Include official documentation links for manual configuration surfaces such as Gitea Actions secrets, Nexus repositories, Azure service principals, and Plane/Gitea API tokens.
- If the repo has enough context to infer non-secret values, show the inferred value and ask the user to confirm before writing it.

## Shared Script

Use the shared deterministic script:

```powershell
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode Audit
```

The old path under `configure-infra-tools` is a compatibility wrapper. Prefer the new path in all new instructions.

Useful modes:

- `Audit`: full file-based audit.
- `InitLocalFiles`: create ignored local files from tracked templates.
- `SetClientTools`: update `.codex/client-tools.local.json`.
- `SetPlaneEnv`: update `infra/plane/variables.env`.
- `SetGiteaRunner`: update `infra/gitea/runner.env`.
- `AuditQualityGates`: inspect quality and CI/CD templates.
- `ValidateGiteaActionsRunner`: live-check Docker runner prerequisites for PR validation containers, including image pull, required tools, and local Gitea checkout reachability.
- `InitQualityGateTemplates`: create tracked quality-gate templates.
- `SetPrometheusAzureTargets`: update ignored Prometheus Azure targets.
- `SetQualityConfig`: create or update `.codex/quality.local.json`, including `coverage.minimumPercent` (default `80`).

## Routing Flow

1. Run `Audit` first unless the user asked for a very specific area and a narrower audit is enough.
2. Summarize findings by domain without exposing secret values.
3. For every missing prerequisite found during audit or validation, provide install, official link, and post-install validation/configuration commands.
4. For every missing user-supplied value, provide source, destination, manual setup steps, official link, and validation command.
5. Ask: `Which setup area do you want to work on now?`
6. Offer these choices:
   - Full guided setup
   - Plane tickets
   - Gitea PR automation
   - Gitea Actions runner
   - Quality gates and CI
   - Nexus artifacts and DEV-to-QA promotion
   - Azure environments
   - Monitoring dashboards
7. If the user is vague, default to full guided setup in this order:
   Plane -> Gitea PR automation -> Gitea Actions runner -> Quality gates and CI -> Nexus artifacts and DEV-to-QA promotion -> Azure environments -> Monitoring dashboards.

## Domain Routing

- Plane tickets: use `$configure-plane-workflow`; read `references/plane.md`.
- Gitea PR automation: use `$configure-gitea-source-control`; read `references/gitea-pr.md`.
- Gitea Actions runner: use `$configure-gitea-actions-runner`; read `references/gitea-runner.md`.
- Quality gates and CI: use `$configure-quality-gates`; read `references/quality-gates.md`.
- Nexus artifacts and deployment promotion: use `$configure-artifact-delivery`; read `references/nexus.md`.
- Azure environments: use `$configure-azure-environments`; read `references/azure.md`.
- Monitoring dashboards: use `$configure-observability`; read `references/observability.md`.

For prerequisite installation guidance, read `references/shared-prerequisites.md` whenever a required executable is missing, incompatible, or a domain skill asks for it.

## Completion Summary

End setup work with:

- Files created or updated, without secret values.
- Values still missing or intentionally skipped.
- Missing tools with install command, official URL, and validation/configuration command.
- Missing user-supplied values with source, destination, manual setup steps, official URL, and validation command.
- Docker images or libraries pinned/updated, including the source used to confirm the current stable version.
- Whether validation was file-only or included live checks.
- Reminder to run `.\infra\up.ps1` if live services were not started.
