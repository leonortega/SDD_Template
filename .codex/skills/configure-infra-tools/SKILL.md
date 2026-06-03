---
name: configure-infra-tools
description: Compatibility alias for configuring this repo's local development and delivery environment. Use when older prompts mention "config infra", "configure infra tools", or the previous configure-infra-tools skill name; route immediately to configure-dev-environment and the specialized setup skills for Plane, Gitea, Gitea Actions, quality gates, Nexus, Azure, and observability.
---

# Configure Infra Tools

This skill is a compatibility router. The active entrypoint is `$configure-dev-environment`.

Before changing configure behavior, read `.codex/skills/_shared/delivery-contract.md` and apply its Skill Synchronization Rule.

When this skill triggers:

1. Read `.codex/skills/configure-dev-environment/SKILL.md`.
2. Run the shared audit through the new script path:

```powershell
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode Audit
```

3. Ask which setup area the user wants to work on:
   - Full guided setup
   - Plane tickets
   - Gitea PR automation
   - Gitea Actions runner
   - Quality gates and CI
   - Nexus artifacts
   - Azure environments
   - Monitoring dashboards
4. Route to the matching specialized skill.

Keep using the same safety rules as `$configure-dev-environment`: no secrets in tracked files, no Docker secret extraction, and no automatic infra startup or shutdown.
