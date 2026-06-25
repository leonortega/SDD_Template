# Configuration Values

This compatibility reference has moved to the split setup skills.

Use `$configure-dev-environment` as the router and load domain references from:

- `.codex/skills/configure-dev-environment/references/shared-prerequisites.md`
- `.codex/skills/configure-dev-environment/references/openproject.md`
- `.codex/skills/configure-dev-environment/references/gitea-pr.md`
- `.codex/skills/configure-dev-environment/references/gitea-runner.md`
- `.codex/skills/configure-dev-environment/references/quality-gates.md`
- `.codex/skills/configure-dev-environment/references/nexus.md`
- `.codex/skills/configure-dev-environment/references/azure.md`
- `.codex/skills/configure-dev-environment/references/observability.md`

Prefer the new shared script path:

```bash
python -m tools.sdd_cli configure Audit
```
