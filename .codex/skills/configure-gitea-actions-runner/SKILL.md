---
name: configure-gitea-actions-runner
description: Configure the Gitea Actions runner for this repo, including infra/gitea/runner.env, runner registration token guidance, runner name, Gitea Actions enablement, and runner image/version audit findings. Use when Codex needs to set up or repair CI runner registration or Gitea Actions execution.
---

# Configure Gitea Actions Runner

## Overview

Configure the Gitea Actions runner used for ticket PR validation and deployment jobs.

## Shared Context

Read `.codex/skills/configure-dev-environment/references/gitea-runner.md` before asking for values or applying changes.

Use the shared script at `.codex/skills/configure-dev-environment/scripts/configure_infra_tools.ps1`.

Apply `.codex/skills/_shared/delivery-contract.md` and `docs/context-management.md` before changing CI validation or handoff behavior.

Safety:

- Do not print runner registration tokens.
- Do not read runner tokens from Docker containers, mounted volumes, databases, or logs.
- Do not start or restart infra without explicit user approval.

## Workflow

1. Run `Audit`.
2. Initialize `infra/gitea/runner.env` with `InitLocalFiles` only if missing.
3. Ask for runner token/name only when missing or placeholder.
4. Apply confirmed values with `SetGiteaRunner`.
5. For old or floating Gitea/Gitea Runner images, check the current stable upstream versions, update Compose to stable patch tags, and report official sources plus migration notes.
6. Validate runner registration only when Gitea is running.

## Output

Report runner config status, missing tokens, image/version findings, validation commands, and any ticket handoff impact without printing tokens.

## Failure Rules

- Stop when runner token, runner name, Docker access, or Gitea availability blocks validation.
- Stop before reading secrets from containers, volumes, databases, or logs.
- Stop before changing CI runner behavior without matching configure and delivery documentation.
