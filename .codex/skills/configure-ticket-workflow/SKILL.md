---
name: configure-ticket-workflow
description: Configure OpenProject work package workflow for this repo, including OpenProject API access, workspace/project/state values, OpenProject Docker local environment values, generated local secrets, and OpenProject live validation. Use when Codex needs to set up or repair OpenProject work package management, OpenProject API config, or infra/openproject/variables.env.
---

# Configure OpenProject Workflow

## Overview

Configure OpenProject work package workflow values used for local ticket state, validation, and delivery handoff.

## Shared Context

Read `.codex/skills/configure-dev-environment/references/openproject.md` before asking for values or applying changes.

Use the shared script at `.codex/skills/configure-dev-environment/scripts/configure_infra_tools.ps1`.

Apply `.codex/skills/_shared/delivery-contract.md` and `docs/context-management.md` before changing ticket workflow behavior or handoff rules.

Safety:

- Do not print OpenProject API tokens or generated secrets.
- Do not read secrets from Docker containers, mounted volumes, databases, or logs.
- Do not start or stop local infra without explicit user approval.
- Use OpenProject API for live validation; do not use OpenProject MCP or direct database queries.

## Workflow

1. Run `Audit`.
2. Initialize local files with `InitLocalFiles` only if needed.
3. Ask only for missing or placeholder OpenProject values.
4. Apply confirmed `.codex/client-tools.local.json` values with `SetClientTools`.
5. Apply confirmed `infra/openproject/variables.env` values with `SetOpenProjectEnv`.
6. Perform live OpenProject API validation only when infra is running or the user approves starting it.

## Output

Report configured OpenProject fields, missing values, validation status, and ticket handoff blockers without exposing tokens or generated secrets.

## Failure Rules

- Stop when OpenProject API values, workspace/project identifiers, or state names are missing.
- Stop before reading secrets from containers, mounted volumes, databases, or logs.
- Stop before using OpenProject MCP or direct database access for ticket delivery.
