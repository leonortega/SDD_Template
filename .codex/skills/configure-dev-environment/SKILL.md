---
name: configure-dev-environment
description: Router for configuring this repo's local development and delivery environment from `.codex/project-profile.json` plus optional `.codex/project-profile.local.json`. Use when Codex needs to set up, audit, repair, or guide configuration for selected ticket, repository/review, quality, artifact, deployment, observability, stack, and E2E adapters, or when the user asks "config infra", "setup environment", or is unsure which setup area they need.
---

# Configure Dev Environment

## Overview

Use this skill as the entrypoint for the repo-local delivery lab. Keep this file lean: run the shared audit, group findings by domain, then route to the focused skill or reference.

## Shared Context

Before changing configure behavior or finishing any non-OpenSpec delivery skill change, read `.codex/project-profile.json`, optional `.codex/project-profile.local.json`, `.codex/skills/_shared/provider-adapter-contract.md`, and `.codex/skills/_shared/delivery-contract.md`, then apply the Skill Synchronization Rule. Keep configure docs, templates, audits, and tests synchronized with the non-OpenSpec delivery-flow skills; when behavior differs, delivery-flow skills are authoritative. If a delivery skill change affects repo setup, generated files, workflow YAML, secrets, ignored local files, labels, ticket gates, artifact paths, release manifests, QA/PROD promotion, rollback, profile/adapters, or audit/repair behavior, update the matching configure skill and tests in the same change. If no configure update is needed, say that explicitly in the final response.

Read `docs/context-management.md` before deciding whether setup findings belong in durable docs, skills, tests, memory, a ticket handoff, or local-only config.

Act as a step-by-step configurator. When a required executable, SDK, CLI, scanner, local service, library, package, or runtime is missing or incompatible, stop that domain step long enough to tell the user exactly how to install it, link the official source, and list the post-install validation/configuration commands before continuing.

When setup needs values the user must supply manually, do not only ask for the values. Explain where each value comes from, why it is needed, where to configure it, the exact UI or CLI path when possible, official documentation links, and validation commands that prove the value is configured correctly.

## Safety Rules

- Never print, commit, paste into tickets, or write real tokens/secrets into tracked files.
- Update ignored local files only when applying user-confirmed secrets:
  - `.codex/client-tools.local.json`
  - `.codex/quality.local.json`
  - `infra/openproject/variables.env`
  - `infra/monitoring/variables.env`
  - `infra/azure/variables.env`
  - `infra/gitea/runner.env`
- Keep tracked files as templates, workflows, or placeholder-safe documentation.
- Do not read secrets from Docker containers, container shells, mounted volumes, service databases, or logs.
- Do not start or stop local infra automatically. Ask first before running `python -m tools.sdd_cli infra up` or `python -m tools.sdd_cli infra down` unless the user explicitly asks for `config infra` or `setup environment`; those requests are approval to run the minimum infra commands needed to leave configuration working.
- Use Docker only for non-secret operational checks such as service status, mounts, health, and non-sensitive provisioning logs.

## Version And Install Rules

- When a tool, SDK, CLI, runtime, scanner, or required local dependency is missing, read `references/shared-prerequisites.md`, then report: what is missing, why it is required, the install command, the official URL, and the exact command to validate/configure it after install.
- If a required item is not covered in `shared-prerequisites.md`, look up the official install documentation before advising the user. Prefer official vendor docs, release pages, or package-manager pages.
- When a recurring tool can run from an official/vendor or repo-owned pinned Docker image, prefer the Docker path over repeated package-manager installation. Record `installPreference: docker-preferred` plus `dockerAlternative` metadata, validate Docker availability, and keep host install guidance as the explicit fallback only.
- For Docker images and library/package versions, check the current upstream stable version before editing templates or compose files. Use official release notes, official docs, GitHub releases, Docker Hub/registry metadata, or vendor lifecycle pages.
- Do not use `latest`, `main`, `nightly`, release-candidate, preview, or floating major/minor-only tags in Compose files or generated templates unless the user explicitly requests floating tags.
- Pin Docker images to the current stable patch tag when configuring infra, and update the Compose file directly when the existing tag is old or floating.
- Mention any migration notes or breaking changes discovered while checking the current version.

## Manual Value Rules

- For required secrets, tokens, passwords, repository names, cloud identifiers, or service-account values, provide a short checklist with: value name, purpose, source, destination, safe example when possible, and validation command.
- Never invent secret values and never read them from containers, mounted volumes, service databases, or logs.
- Prefer manual UI steps for first-time secret entry. Use APIs only after the user provides values explicitly in chat or an approved local secret source.
- Include official documentation links for manual configuration surfaces such as Gitea Actions secrets, Nexus repositories, Azure service principals, and OpenProject/Gitea API tokens.
- If the repo has enough context to infer non-secret values, show the inferred value and ask the user to confirm before writing it.
- At the end of configure-dev-environment, if any required configuration value is still missing, ask for values one at a time. For each value, state the value name, why it is needed, exactly where to obtain it in the owning tool UI or CLI, the destination file/key, and the validation command. Do not batch multiple missing-value questions into one prompt.

## Client Tools Local Config Rules

- For `.codex/client-tools.local.json`, complete safe inferred non-secret values during explicit setup/write modes before reporting findings.
- `Audit*` modes are read-only by default. They may report inferred values as actions, but must not write `.codex/client-tools.local.json` unless the operator explicitly passes `-AllowAuditWrites`.
- Inferred values include local service URLs, default workflow state names, Git branch defaults, PR labels, Gitea owner/repo from `origin`, and Nexus local URL/repository name.
- Never infer or fabricate API tokens, passwords, service-account credentials, OpenProject workspace/project identifiers, or cloud identifiers that are not discoverable from local repo/Azure metadata.
- If a required value is not inferable, report it as a user-supplied value with its source, destination, official setup surface, and validation command.

## Parallel Delivery Rules

- Parallel ticket delivery uses Git worktrees only. The default placeholder-safe config is `parallelDelivery.enabled=false`, `parallelDelivery.maxActiveTickets=2`, `parallelDelivery.worktreeRoot=../ticket-worktrees`, `parallelDelivery.deploymentLanePolicy=serialized`, and `parallelDelivery.agentModelPolicy` with per-role model/reasoning defaults.
- The coordinator runtime index `.codex/parallel-delivery.local.json` and each worktree's `.codex/delivery-context.local.json` must be ignored and never committed.
- Copy ignored local config into ticket worktrees only when a child delivery skill requires it. Report copied filenames, not secret values.
- Use the allowlist from `SyncWorktreeLocalConfig` for default worktree sync: `.codex/client-tools.local.json`, `.codex/project-profile.local.json`, `.codex/quality.local.json`, and `.codex/tool-recommendations.local.json` when present. Do not copy `.codex/parallel-delivery.local.json`, `.codex/delivery-context.local.json`, `.codex/azure-login.local.json`, or app `*.local.json` files by default.
- Deployment promotion remains serialized because DEV, QA, PROD, RC tags, final release tags, and Nexus release manifests are shared surfaces.
- `agentModelPolicy` is a cost-control policy for on-the-fly sub-agents. `model=inherit` means no explicit model override; unavailable model ids should fall back to inherited model behavior and be reported.
- `ValidateParallelDeliveryDryRun` must pass before parallel Git, OpenProject, or Gitea mutation. Include required ignored local runtime files such as `.codex/client-tools.local.json` and `.codex/quality.local.json` when child skills need them.
- The installed-skill runtime index is ignored local state derived from actual `.codex/skills/*/SKILL.md` files. It is not a project guidance catalog and must not duplicate `.codex/tool-recommendations.local.json`.
- See `docs/parallel-delivery.md` for operator guidance, dry-run checklist, role contracts, and cleanup/recovery steps.

## Shared Script

Use the shared deterministic script:

```bash
python -m tools.sdd_cli configure Audit
```

For full setup, follow the repository startup order before any write: `README.md`, `.codex/skills/_shared/skill-startup.md`, memory files, `.codex/delivery-policy.json`, shared contracts, `docs/context-management.md`, then this skill and only the required references.

For modes that accept values, prefer shell-neutral input:

```bash
python -m tools.sdd_cli configure SetClientTools --values-json-file .codex/config-values.local.json
python -m tools.sdd_cli configure SetClientTools --values-json-stdin true
```

Keep value files ignored/local and never commit secret values. `--values-json` remains supported for non-secret compatibility use.

Do not use per-mode `--help`; configure submodes do not expose dedicated help. Read this skill, the focused reference, or `tools/sdd_cli/cli.py` instead.

Do not bypass the CLI by importing `run_configure_mode` for real setup mutations. Use `python -m tools.sdd_cli configure ...`, then verify writes by reading the affected ignored local file without printing secrets and rerunning `python -m tools.sdd_cli configure Audit`.

When the operator forbids PowerShell, do not use PowerShell wrappers for configure commands or file inspection. Use a non-PowerShell runner while preserving the same CLI arguments.

The old path under `configure-infra-tools` is a compatibility wrapper. Prefer the new path in all new instructions.

Useful modes:

- `Audit`: full file-based audit.
- `AuditRecommendedTools`: read-only stack detection and MCP/plugin/skill/tool/reference/practice recommendation report.
- `DiscoverProjectGuidance`: read-only project-guidance-discover report with detected tags, research topics, existing skills, suggested missing skills, suggested guidance, user-added requested guidance, and final confirmed guidance when supplied.
- `DiscoverProjectGuidance` with `persistLocal=true`: write ignored `.codex/tool-recommendations.local.json` with catalog-shaped project recommendations and recommendation-level `usedInSteps` for later `project-guidance-mapper` use.
- `AcquireProjectGuidance`: auto-copy safe confirmed `manual-copy` `repo:` skill sources into `.codex/skills`; prepare guarded install plans for MCPs, plugins, tools, IDE/global installs, secrets, or restart-required items; aggregate IDE restart/system reboot notices once at the end; require source attribution including `sourceKind`; leave non-skill guidance in the local catalog unless deterministic repo-local config is supported.
- `InitLocalFiles`: create ignored local files from tracked templates.
- `SetClientTools`: update `.codex/client-tools.local.json`.
- `SetProjectStack`: update ignored `.codex/project-profile.local.json` with frontend, backend, and database choices; `none`, `no`, `n/a`, and empty values mean not applicable.
- `SetGiteaBranchProtection`: apply `pr.minimumApprovals.dev/main` to live Gitea branch protection.
- `SetRecommendedTools`: record accepted or dismissed recommendation ids in `.codex/client-tools.local.json`; it must not install skills, plugins, MCPs, or secrets.
- `MapProjectGuidanceStep`: update `.codex/tool-recommendations.local.json` by appending the current workflow step to each used recommendation's `usedInSteps`.
- `WriteInstalledSkillIndex` through `repo-local delivery helper`: generate or reuse ignored `.codex/installed-skill-index.local.json` and `.codex/installed-skill-index.cache.local.json` from installed project skills.
- `SyncWorktreeLocalConfig`: copy the allowlisted ignored local runtime config from the coordinator checkout into selected or discovered ticket worktrees without printing secret values.
- `EnsureDeliveryContext`: create or repair the current worktree's `.codex/delivery-context.local.json` from explicit ticket, branch, OpenSpec, and PR context; never copy this file from another worktree. Use `replaceExisting=true` only after `dev-flow-start-ticket` confirms the existing lock's ticket is in the configured Done state, or after explicit operator confirmation for a known-safe repair. QA Done does not require immediate lock deletion because explicit PROD promotion may still need artifact and RC context.
- `SetOpenProjectEnv`: update `infra/openproject/variables.env`.
- `SetMonitoringEnv`: update `infra/monitoring/variables.env`.
- `SplitInfraEnv`: migrate old mixed `infra/openproject/variables.env` values into tool-owned env files and prune stale keys not present in current templates.
- `SetGiteaRunner`: update `infra/gitea/runner.env`.
- `AuditQualityGates`: inspect quality and CI/CD templates without writing local config by default.
- `BuildGiteaActionsImages`: build and validate pinned local Gitea Actions job images used by PR validation, package/deploy, and QA E2E workflows.
- `ValidateGiteaActionsRunner`: live-check Docker runner prerequisites for PR validation containers, including local image presence, required tools, and local Gitea checkout reachability.
- `InitProjectProfile`: create the canonical project profile, schema, and neutral provider adapter examples. This is a required first-class step for full `config infra`.
- `EnsureRancherDesktopCluster`: when Rancher Desktop is the selected deployment provider, switch to context `rancher-desktop` and wait for a Ready node. `Audit` remains read-only and only reports missing or unhealthy Kubernetes state. Rancher Desktop owns cluster creation and startup through its application settings.
- `EnsureRancherDesktopHeadlamp`: when Rancher Desktop is the selected deployment provider, install or update Headlamp through the official Helm chart, wait for the `headlamp` deployment, and expose it at `http://127.0.0.1:4466`. Tokens must not be printed; copy a fresh login token with `kubectl create token headlamp --namespace headlamp | Set-Clipboard`, then paste it into Headlamp.
- `EnsureRancherDesktopPortForwards`: when Rancher Desktop is the selected deployment provider, start stable `kubectl port-forward --address 127.0.0.1` mappings for deployed local-lab services so Windows browsers can use `127.0.0.1` URLs. It maps DEV site/API to `18081`/`18082`, QA site/API to `18083`/`18084`, and PROD site/API to `18085`/`18086`; services not deployed yet are skipped with warnings.
- `ShowEnvironmentUrls`: show and refresh the ignored local environment URL registry at `.codex/environment-urls.local.json` plus the Grafana Environment URLs dashboard. It lists DEV/QA/PROD Web/API browser URLs, container URLs, ingress URLs, deployment status, and port-forward status without exposing secrets.
- `InitQualityGateTemplates`: create tracked quality-gate templates.
- `SetSeqAzureEventHubLogs`: validate Seq, the native Seq error-log alert, Grafana Infinity health datasource, and Grafana health alerts.
- `SetQualityConfig`: create or update `.codex/quality.local.json`, including `coverage.minimumPercent` (default `80`).

## Workflow

1. For full `config infra` or full guided setup, run `InitProjectProfile` first, then `InitLocalFiles` so ignored local env/config files and required memory seed files exist before audit or provider checks need them. If the profile, schema, local files, memory files, or selected adapters already exist, treat the mode as idempotent and continue from its `Template already exists` or preserved-file findings.
2. When Rancher Desktop is the selected deployment provider and the user explicitly asked for `config infra`, full setup, or Rancher Desktop local lab setup, run `EnsureRancherDesktopCluster` before `EnsureRancherDesktopHeadlamp`, `EnsureRancherDesktopPortForwards`, `ShowEnvironmentUrls`, and `Audit`. `EnsureRancherDesktopHeadlamp` installs the Kubernetes management UI and starts its localhost mapping. `EnsureRancherDesktopPortForwards` starts localhost browser mappings for services that are already deployed. This is the only configure path that may switch Rancher Desktop Kubernetes context, install Headlamp, or start Rancher Desktop local-lab port-forward processes; plain `Audit` remains read-only.
3. Run `Audit` after `InitProjectProfile` and any selected-provider prerequisite repair unless the user asked for a very specific area and a narrower audit is enough.
   `Audit` must report missing current template keys and stale non-template keys in ignored env files.
4. For core compose status checks, always include the OpenProject env file so variable resolution matches runtime expectations:

```bash
docker compose --env-file .\infra\openproject\variables.env --env-file .\infra\monitoring\variables.env -f .\infra\compose.yml ps
```

5. Summarize findings by domain without exposing secret values.
6. Observability is mandatory for `config infra`: run `SetSeqAzureEventHubLogs`, then ensure Seq, the native Seq error-log alert, Grafana Infinity health datasource, and Grafana health alerts are running and healthy.
7. Azure Event Hub collector ingestion is not part of the current Rancher Desktop environment.
8. Do not finish `config infra` successfully while observability findings remain unresolved.
9. For every missing prerequisite found during audit or validation, provide install, official link, and post-install validation/configuration commands.
10. For every missing user-supplied value, provide source, destination, manual setup steps, official link, and validation command.
11. If local Trivy checks report a stale vulnerability database, refresh it before local scans:

```bash
trivy image --download-db-only
```

12. Run `AuditRecommendedTools` when the user is doing full setup or base-code creation, then summarize relevant MCPs, plugins, tools, references, practices, detected stack tags, stack-context drift, and scan-derived guidance findings for tools, frameworks, code standards, web UI, REST/API design, security, and QA. If no product source exists and `.codex/project-profile.local.json` has no frontend/backend/database selection, ask three separate questions for frontend, backend, and database before project guidance discovery; accept `none`, `no`, `n/a`, or an empty answer as not applicable, then record the answers with `SetProjectStack`. Use `.codex/tool-recommendations.common.json` as common recommendation catalog metadata, not as runtime project state or a substitute for scanning the repository.
13. Treat `docs/` as the durable stack/tooling source of truth and `openspec/config.yaml` as the compact AI-facing summary. The recommendation audit verifies those against current repo files; when they differ, report the drift before recommending new tooling.
14. Use `project-guidance-discover` for project guidance findings. Treat `project-guidance-search-plan` as the first step: build topics from scanned technologies, tools, environments, test frameworks, QA workflows, security gates, code standards, and other detected project signals; do not rely on a fixed catalog alone.
15. `project-guidance-discover` must research extra useful skills, MCPs, plugins, tools, references, practices, standards, and Codex-applicable IDE helpers before it shows suggested missing guidance to the user. Ask only for confirmation, dismissals, or omissions before anything is copied. Make confirmation mean "record and install/configure supported items now"; do not ask a second install question. If the user names omissions, add them to the list, research and verify each source with the same multi-source, official-first policy, then confirm the full list. Valid source families include repo-local workflow sources, OpenAI official catalogs/docs, official tool repositories/docs, technology-owner repositories/docs, `skills.sh` or `skills` command examples, marketplace pages, and clearly labeled community repositories.
16. After confirmation, persist the catalog-shaped local discovery state to ignored `.codex/tool-recommendations.local.json` with `DiscoverProjectGuidance` and `persistLocal=true`, record accepted ids with `SetRecommendedTools`, then run `project-guidance-acquire` and any supported guarded installer/configuration path for the same confirmed items. This file should keep sources, targets, validation commands, accepted/dismissed ids, and recommendation-level `usedInSteps`; it is a local reference for `project-guidance-mapper`, not a tracked source of truth.
17. Use `project-guidance-acquire` only after the final confirmed list exists. It auto-copies safe repo-local confirmed skill `SKILL.md` files and required referenced resources into `.codex/skills`, and installs/configures confirmed non-skill items when a platform-supported path exists; it must not run arbitrary command installers. Refresh `.codex/tool-recommendations.local.json` after acquisition so installed/present state is current.
18. If `dev-flow-start-ticket` or `dev-flow-continue-implementation` blocks the first ticket because stack context is missing, configure `docs/architecture.md`, `docs/development.md`, and `docs/deployment.md`, complete `openspec/config.yaml`, verify the tracked example catalog still describes the allowed shape, and write or refresh ignored `.codex/tool-recommendations.local.json` only after project guidance discovery is confirmed.
19. For skills, use guarded repo-based acquisition: identify the source repo/path/ref, classify `sourceKind`, read the source `SKILL.md`, verify frontmatter matches the intended use, create `.codex/skills/{skill-name}/`, write `.codex/skills/{skill-name}/SKILL.md`, and copy only required referenced scripts/templates. Treat `skills.sh`, `skills`, marketplace, README, curl, or install commands as metadata for repository/path discovery only. Do not copy secrets, local state, caches, generated artifacts, or unrelated files. When adding an external skill, keep its upstream name unless the user explicitly approves a rename, mark it as `External` in `.codex/skills/README.md`, and cite the source repository in the root `README.md`.
20. For plugins, MCPs, tools, and IDE extensions, prefer platform-supported install/configuration surfaces and exact install plans over arbitrary commands. For repeated tools, first check accepted `dockerAlternative` metadata and use the pinned repo/official Docker image when available; keep host installs for MCPs, IDE plugins, Docker itself, interactive auth, secret-bearing tools, and tools without a verified image. Ask before global, IDE, privileged, secret-bearing, MCP/plugin, or reboot-required installs. Continue independent acquisitions after one item needs restart, then report one Important restart/reboot message with affected tools and validation commands.
21. Use `project-guidance-mapper` when the operator asks which skills or guidance apply to the current delivery step or when a workflow needs to combine repo-local workflow skills with installed expert skills, tools, references, practices, and standards. Let `project-guidance-mapper` read and update `.codex/tool-recommendations.local.json` through `MapProjectGuidanceStep` after a step mapping is chosen, used, or inferred.
22. Record accepted or dismissed recommendation ids with `SetRecommendedTools` only after user confirmation.
23. Ask: `Which setup area do you want to work on now?`
24. Offer these choices:
   - Full guided setup
   - OpenProject work packages
   - Gitea PR automation
   - Gitea Actions runner
   - Quality gates and CI
   - Nexus artifacts and deployment promotion
   - Rancher Desktop local lab
   - Azure environments
   - Monitoring dashboards
   - Azure Event Hub to Seq ingestion
25. If the user is vague, default to full guided setup in this order:
   InitProjectProfile -> EnsureRancherDesktopCluster when Rancher Desktop is selected -> EnsureRancherDesktopHeadlamp when Rancher Desktop is selected -> EnsureRancherDesktopPortForwards when Rancher Desktop is selected -> ShowEnvironmentUrls when Rancher Desktop is selected -> Audit -> OpenProject -> Gitea PR automation -> Gitea Actions runner -> Quality gates and CI -> Nexus artifacts and Rancher Desktop deployment promotion -> Monitoring dashboards -> final Audit.

## Domain Routing

- OpenProject work packages: use `$configure-ticket-workflow`; read `references/openproject.md`.
- Gitea PR automation: use `$configure-source-control`; read `references/gitea-pr.md`.
- Gitea Actions runner: use `$configure-ci-runner`; read `references/gitea-runner.md`.
- Quality gates and CI: use `$configure-quality-gates`; read `references/quality-gates.md`.
- Nexus artifacts and deployment promotion: use `$configure-artifact-repository`; read `references/nexus.md`.
- Rancher Desktop local lab: read `references/nexus.md`, `references/observability.md`, and `.codex/providers/deploy.rancher-desktop.md`.
- Azure environments: use `$configure-cloud-environments`; read `references/azure.md`.
- Monitoring dashboards: use `$configure-observability`; read `references/observability.md`.
- Azure Event Hub to Seq ingestion: use `$configure-observability`; read `references/observability.md`.

For prerequisite installation guidance, read `references/shared-prerequisites.md` whenever a required executable is missing, incompatible, or a domain skill asks for it.

## Output

End setup work with:

- Files created or updated, without secret values.
- Values still missing or intentionally skipped.
- Observability findings and status from the current run, including at minimum: Seq runtime health, Seq error-log alert status, Grafana Infinity health datasource status, and Grafana `/health` alert status.
- Missing tools with install command, official URL, and validation/configuration command.
- Missing user-supplied values with source, destination, manual setup steps, official URL, and validation command.
- If required values are still missing, the next user prompt must request only the first missing value and include how to obtain it in the owning tool.
- Docker images or libraries pinned/updated, including the source used to confirm the current stable version.
- Recommended MCPs, plugins, and skills shown, accepted, dismissed, or skipped. For accepted skills, state that manual copy from source `SKILL.md` is the default acquisition path.
- Whether `.codex/tool-recommendations.local.json` was written or updated for local discovery/mapping state.
- Whether validation was file-only or included live checks.
- If setup was requested as `config infra` or full setup, report the live `docker compose ... ps` state instead of deferring with a reminder.

## Failure Rules

- Stop when required user-supplied secrets, tokens, workspace IDs, project IDs, cloud IDs, or service account values are missing; provide source, destination, official setup path, validation command, and handoff impact.
- Stop before provider-specific mutation when `.codex/project-profile.json`, `.codex/project-profile.schema.json`, or any selected adapter path in the merged profile is missing; run `InitProjectProfile` or the focused provider configure skill first.
- Stop successful completion of `config infra` when selected observability is not working: Seq unhealthy, Grafana Infinity health datasource missing, or Grafana health alert missing.
- Stop before writing secrets to tracked files or reading secrets from containers, volumes, databases, or logs.
- Stop before branch, OpenProject, ticket-lock, or OpenSpec mutation when first-ticket stack context, guidance discovery review, or recommendation audit context is missing or drifted.
- Stop before using arbitrary command installers; route confirmed acquisition and guarded install planning to `project-guidance-acquire`.
- If a required repo skill, command, memory rule, definition, or configured tool/install path cannot be applied, do not silently switch to an ad hoc setup path. Report the failed required item, why it is required, the current-flow fix, the viable alternative, and the alternative's risk or impact, then ask the user whether to fix the current flow or continue with the alternative.
