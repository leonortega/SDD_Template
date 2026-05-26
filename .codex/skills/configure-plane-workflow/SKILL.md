---
name: configure-plane-workflow
description: Configure Plane ticket workflow for this repo, including Plane API access, workspace/project/state values, Plane Docker local environment values, generated local secrets, and Plane live validation. Use when Codex needs to set up or repair Plane ticket management, Plane API config, or infra/plane/variables.env.
---

# Configure Plane Workflow

Read `.codex/skills/configure-dev-environment/references/plane.md` before asking for values or applying changes.

Use the shared script at `.codex/skills/configure-dev-environment/scripts/configure_infra_tools.ps1`.

Safety:

- Do not print Plane API tokens or generated secrets.
- Do not read secrets from Docker containers, mounted volumes, databases, or logs.
- Do not start or stop local infra without explicit user approval.
- Use Plane API for live validation; do not use Plane MCP or direct database queries.

Workflow:

1. Run `Audit`.
2. Initialize local files with `InitLocalFiles` only if needed.
3. Ask only for missing or placeholder Plane values.
4. Apply confirmed `.codex/client-tools.local.json` values with `SetClientTools`.
5. Apply confirmed `infra/plane/variables.env` values with `SetPlaneEnv`.
6. Perform live Plane API validation only when infra is running or the user approves starting it.
