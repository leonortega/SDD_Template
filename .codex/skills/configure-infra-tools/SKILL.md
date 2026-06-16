---
name: configure-infra-tools
description: Compatibility alias for configuring this repo's local development and delivery environment. Use when older prompts mention "config infra", "configure infra tools", or the previous configure-infra-tools skill name; route immediately to configure-dev-environment and the specialized setup skills for Plane, Gitea, Gitea Actions, quality gates, Nexus, Azure, and observability.
---

# Configure Infra Tools

## Overview

This skill is a compatibility router for older prompts. The active entrypoint is `$configure-dev-environment`; keep the operational setup flow there so this alias does not drift.

## Shared Context

Before changing configure behavior, read `.codex/skills/_shared/delivery-contract.md` and apply its Skill Synchronization Rule.

Also apply `docs/context-management.md` for durable configuration findings, ticket context, validation notes, and handoff reporting.

## Workflow

When this skill triggers:

1. Read `.codex/skills/configure-dev-environment/SKILL.md`.
2. Route immediately to `$configure-dev-environment` and follow its audit, safety, domain routing, and output rules.
3. During infra status checks for the core stack, use the compose env file explicitly:

```powershell
docker compose --env-file .\infra\plane\variables.env --env-file .\infra\monitoring\variables.env -f .\infra\compose.yml ps
```

4. When local Trivy scans report a stale DB, refresh before scanning:

```powershell
trivy --download-db-only
```

5. If the caller explicitly asked for the legacy script path, use the active shared script path instead:

```powershell
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode Audit
```

Keep using the same safety rules as `$configure-dev-environment`: no secrets in tracked files, no Docker secret extraction, and no automatic infra startup or shutdown.

## Output

Report that routing moved to `$configure-dev-environment`, the audit result, selected setup area, validation status, and handoff blockers.

## Failure Rules

- Stop when the active configure entrypoint cannot be read.
- Stop when validation finds missing local config or secrets that require manual user action.
- Stop before mutating ticket, Git, Plane, Gitea, Nexus, Azure, or monitoring state from this compatibility alias.
