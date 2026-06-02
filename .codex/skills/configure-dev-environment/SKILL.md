---
name: configure-dev-environment
description: Router for configuring this repo's local development and delivery environment. Use when Codex needs to set up, audit, repair, or guide configuration for Plane, Gitea PR automation, Gitea Actions runner, code quality gates, Nexus artifacts, Azure DEV/QA/PROD environments, DEV-to-QA deployment promotion, Prometheus/Grafana monitoring, or when the user asks "config infra", "setup environment", or is unsure which setup area they need.
---

# Configure Dev Environment

## Overview

Use this skill as the entrypoint for the repo-local delivery lab. Keep this file lean: run the shared audit, group findings by domain, then route to the focused skill or reference.

## Shared Context

Before changing configure behavior or finishing any non-OpenSpec delivery skill change, read `.codex/skills/_shared/delivery-contract.md` and apply its Skill Synchronization Rule. Keep configure docs, templates, audits, and tests synchronized with the non-OpenSpec delivery-flow skills; when behavior differs, delivery-flow skills are authoritative. If a delivery skill change affects repo setup, generated files, workflow YAML, secrets, ignored local files, labels, ticket gates, artifact paths, release manifests, QA/PROD promotion, rollback, or audit/repair behavior, update the matching configure skill and tests in the same change. If no configure update is needed, say that explicitly in the final response.

Read `docs/context-management.md` before deciding whether setup findings belong in durable docs, skills, tests, memory, a ticket handoff, or local-only config.

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

## Client Tools Local Config Rules

- For `.codex/client-tools.local.json`, complete safe inferred non-secret values during explicit setup/write modes before reporting findings.
- `Audit*` modes are read-only by default. They may report inferred values as actions, but must not write `.codex/client-tools.local.json` unless the operator explicitly passes `-AllowAuditWrites`.
- Inferred values include local service URLs, default workflow state names, Git branch defaults, PR labels, Gitea owner/repo from `origin`, and Nexus local URL/repository name.
- Never infer or fabricate API tokens, passwords, service-account credentials, Plane workspace/project identifiers, or cloud identifiers that are not discoverable from local repo/Azure metadata.
- If a required value is not inferable, report it as a user-supplied value with its source, destination, official setup surface, and validation command.

## Parallel Delivery Rules

- Parallel ticket delivery uses Git worktrees only. The default placeholder-safe config is `parallelDelivery.enabled=false`, `parallelDelivery.maxActiveTickets=2`, `parallelDelivery.worktreeRoot=../ticket-worktrees`, `parallelDelivery.deploymentLanePolicy=serialized`, and `parallelDelivery.agentModelPolicy` with per-role model/reasoning defaults.
- The coordinator runtime index `.codex/parallel-delivery.local.json` and each worktree's `.codex/delivery-context.local.json` must be ignored and never committed.
- Copy ignored local config into ticket worktrees only when a child delivery skill requires it. Report copied filenames, not secret values.
- Use the allowlist from `SyncWorktreeLocalConfig` for default worktree sync: `.codex/client-tools.local.json`, `.codex/quality.local.json`, and `.codex/tool-recommendations.local.json` when present. Do not copy `.codex/parallel-delivery.local.json`, `.codex/delivery-context.local.json`, `.codex/azure-login.local.json`, or app `*.local.json` files by default.
- Deployment promotion remains serialized because DEV, QA, PROD, RC tags, final release tags, and Nexus release manifests are shared surfaces.
- `agentModelPolicy` is a cost-control policy for on-the-fly sub-agents. `model=inherit` means no explicit model override; unavailable model ids should fall back to inherited model behavior and be reported.
- `ValidateParallelDeliveryDryRun` must pass before parallel Git, Plane, or Gitea mutation. Include required ignored local runtime files such as `.codex/client-tools.local.json` and `.codex/quality.local.json` when child skills need them.
- See `docs/parallel-delivery.md` for operator guidance, dry-run checklist, role contracts, and cleanup/recovery steps.

## Shared Script

Use the shared deterministic script:

```powershell
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode Audit
```

The old path under `configure-infra-tools` is a compatibility wrapper. Prefer the new path in all new instructions.

Useful modes:

- `Audit`: full file-based audit.
- `AuditRecommendedTools`: read-only stack detection and MCP/plugin/skill/tool/reference/practice recommendation report.
- `DiscoverProjectGuidance`: read-only project-guidance-discover report with detected tags, research topics, existing skills, suggested missing skills, suggested guidance, user-added requested guidance, and final confirmed guidance when supplied.
- `DiscoverProjectGuidance` with `persistLocal=true`: write ignored `.codex/tool-recommendations.local.json` with catalog-shaped project recommendations and recommendation-level `usedInSteps` for later `project-guidance-mapper` use.
- `AcquireProjectGuidance`: copy confirmed `manual-copy` `repo:` skill sources into `.codex/skills` without command installers; leave non-skill guidance in the local catalog.
- `InitLocalFiles`: create ignored local files from tracked templates.
- `SetClientTools`: update `.codex/client-tools.local.json`.
- `SetRecommendedTools`: record accepted or dismissed recommendation ids in `.codex/client-tools.local.json`; it must not install skills, plugins, MCPs, or secrets.
- `MapProjectGuidanceStep`: update `.codex/tool-recommendations.local.json` by appending the current workflow step to each used recommendation's `usedInSteps`.
- `SyncWorktreeLocalConfig`: copy the allowlisted ignored local runtime config from the coordinator checkout into selected or discovered ticket worktrees without printing secret values.
- `EnsureDeliveryContext`: create or repair the current worktree's `.codex/delivery-context.local.json` from explicit ticket, branch, OpenSpec, and PR context; never copy this file from another worktree.
- `SetPlaneEnv`: update `infra/plane/variables.env`.
- `SetGiteaRunner`: update `infra/gitea/runner.env`.
- `AuditQualityGates`: inspect quality and CI/CD templates without writing local config by default.
- `ValidateGiteaActionsRunner`: live-check Docker runner prerequisites for PR validation containers, including image pull, required tools, and local Gitea checkout reachability.
- `InitQualityGateTemplates`: create tracked quality-gate templates.
- `SetPrometheusAzureTargets`: update ignored Prometheus Azure targets.
- `SetQualityConfig`: create or update `.codex/quality.local.json`, including `coverage.minimumPercent` (default `80`).

## Workflow

1. Run `Audit` first unless the user asked for a very specific area and a narrower audit is enough.
2. Summarize findings by domain without exposing secret values.
3. For every missing prerequisite found during audit or validation, provide install, official link, and post-install validation/configuration commands.
4. For every missing user-supplied value, provide source, destination, manual setup steps, official link, and validation command.
5. Run `AuditRecommendedTools` when the user is doing full setup or base-code creation, then summarize relevant MCPs, plugins, tools, references, practices, detected stack tags, stack-context drift, and scan-derived guidance findings for tools, frameworks, code standards, web UI, REST/API design, security, and QA. Use `.codex/tool-recommendations.example.json` as example recommendation metadata, not as runtime project state or a substitute for scanning the repository.
6. Treat `docs/` as the durable stack/tooling source of truth and `openspec/config.yaml` as the compact AI-facing summary. The recommendation audit verifies those against current repo files; when they differ, report the drift before recommending new tooling.
7. Use `project-guidance-discover` for project guidance findings. Treat `project-guidance-search-plan` as the first step: build topics from scanned technologies, tools, environments, test frameworks, QA workflows, security gates, code standards, and other detected project signals; do not rely on a fixed catalog alone.
8. `project-guidance-discover` must show suggested missing skills and guidance to the user and ask for additional desired skills or guidance before anything is copied. If the user says no, confirm the suggested list. If the user names more items, add them to the list, research and verify each source with the same official-first policy, then confirm the full list.
9. After confirmation, persist the catalog-shaped local discovery state to ignored `.codex/tool-recommendations.local.json` with `DiscoverProjectGuidance` and `persistLocal=true`. This file should keep sources, targets, validation commands, accepted/dismissed ids, and recommendation-level `usedInSteps`; it is a local reference for `project-guidance-mapper`, not a tracked source of truth.
10. Use `project-guidance-acquire` only after the final confirmed list exists. It manually copies confirmed skill `SKILL.md` files and required referenced resources into `.codex/skills`; it must not use command installers or global skill installation. Refresh `.codex/tool-recommendations.local.json` after copying so installed/present state is current.
11. If `plane-start-ticket` or `automatic-implement-ticket` blocks the first ticket because stack context is missing, configure `docs/architecture.md`, `docs/development.md`, and `docs/deployment.md`, complete `openspec/config.yaml`, verify the tracked example catalog still describes the allowed shape, and write or refresh ignored `.codex/tool-recommendations.local.json` only after project guidance discovery is confirmed.
12. For skills, use manual repo-based acquisition only: identify the source repo/path, read the source `SKILL.md`, create `.codex/skills/{skill-name}/`, write `.codex/skills/{skill-name}/SKILL.md`, and copy only required referenced scripts/templates. Do not install skills by command. Do not copy secrets, local state, caches, generated artifacts, or unrelated files.
13. For plugins and MCPs, prefer manual configuration instructions over installer commands. Show the exact files or UI fields to create or edit when known, ask before adding config, and never configure secrets automatically. Command installers are fallback-only after explicit approval.
14. Use `project-guidance-mapper` when the operator asks which skills or guidance apply to the current delivery step or when a workflow needs to combine repo-local workflow skills with installed expert skills, tools, references, practices, and standards. Let `project-guidance-mapper` read and update `.codex/tool-recommendations.local.json` through `MapProjectGuidanceStep` after a step mapping is chosen, used, or inferred.
15. Record accepted or dismissed recommendation ids with `SetRecommendedTools` only after user confirmation.
16. Ask: `Which setup area do you want to work on now?`
17. Offer these choices:
   - Full guided setup
   - Plane tickets
   - Gitea PR automation
   - Gitea Actions runner
   - Quality gates and CI
   - Nexus artifacts and deployment promotion
   - Azure environments
   - Monitoring dashboards
18. If the user is vague, default to full guided setup in this order:
   Plane -> Gitea PR automation -> Gitea Actions runner -> Quality gates and CI -> Nexus artifacts and deployment promotion -> Azure environments -> Monitoring dashboards.

## Domain Routing

- Plane tickets: use `$configure-plane-workflow`; read `references/plane.md`.
- Gitea PR automation: use `$configure-gitea-source-control`; read `references/gitea-pr.md`.
- Gitea Actions runner: use `$configure-gitea-actions-runner`; read `references/gitea-runner.md`.
- Quality gates and CI: use `$configure-quality-gates`; read `references/quality-gates.md`.
- Nexus artifacts and deployment promotion: use `$configure-artifact-delivery`; read `references/nexus.md`.
- Azure environments: use `$configure-azure-environments`; read `references/azure.md`.
- Monitoring dashboards: use `$configure-observability`; read `references/observability.md`.

For prerequisite installation guidance, read `references/shared-prerequisites.md` whenever a required executable is missing, incompatible, or a domain skill asks for it.

## Output

End setup work with:

- Files created or updated, without secret values.
- Values still missing or intentionally skipped.
- Missing tools with install command, official URL, and validation/configuration command.
- Missing user-supplied values with source, destination, manual setup steps, official URL, and validation command.
- Docker images or libraries pinned/updated, including the source used to confirm the current stable version.
- Recommended MCPs, plugins, and skills shown, accepted, dismissed, or skipped. For accepted skills, state that manual copy from source `SKILL.md` is the default acquisition path.
- Whether `.codex/tool-recommendations.local.json` was written or updated for local discovery/mapping state.
- Whether validation was file-only or included live checks.
- Reminder to run `.\infra\up.ps1` if live services were not started.

## Failure Rules

- Stop when required user-supplied secrets, tokens, workspace IDs, project IDs, cloud IDs, or service account values are missing; provide source, destination, official setup path, validation command, and handoff impact.
- Stop before writing secrets to tracked files or reading secrets from containers, volumes, databases, or logs.
- Stop before branch, Plane, ticket-lock, or OpenSpec mutation when first-ticket stack context, guidance discovery review, or recommendation audit context is missing or drifted.
- Stop before using command installers for skills; route confirmed skill copying to `project-guidance-acquire`.
