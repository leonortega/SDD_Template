---
name: configure-observability
description: Configure Grafana Azure Monitor observability for this repo, including Log Analytics workspace validation, Azure Monitor datasource provisioning, Azure Monitor dashboards, and local Grafana health checks.
---

# Configure Observability

## Overview

Configure Grafana, Azure Monitor, and Log Analytics observability used for deployment validation and ticket handoff evidence.

## Shared Context

Read `.codex/skills/configure-dev-environment/references/observability.md` before asking for values or applying changes.

Use the shared script at `.codex/skills/configure-dev-environment/scripts/configure_infra_tools.ps1`.

Apply `.codex/skills/_shared/delivery-contract.md` and `docs/context-management.md` before changing monitoring validation, dashboard behavior, or handoff evidence.

Safety:

- Keep Grafana Azure service-principal secrets in ignored `infra/plane/variables.env`.
- Keep generated environment dashboard JSON in ignored `infra/monitoring/grafana/dashboards.local/`.
- Do not rotate or expose Grafana credentials without explicit user direction.

## Workflow

1. Run `Audit`.
2. Configure Azure Monitor only after Bicep creates Log Analytics workspaces and App Service diagnostic settings.
3. Use `SetGrafanaAzureMonitor` to infer workspace IDs, create or reuse the Grafana service principal, assign `Reader` and `Log Analytics Reader`, and write ignored local env values.
4. Ask before recreating Grafana unless the user has explicitly requested full implementation.
5. Validate Grafana health and Azure Monitor log visibility only when infra is running and Azure credentials are configured.

## Output

Report Grafana health, Azure Monitor datasource provisioning status, Log Analytics validation commands, missing values, and ticket handoff evidence without exposing secrets.

## Failure Rules

- Stop when Azure workspace values are missing or not confirmed.
- Stop when infra is unavailable and the user has not approved live validation.
- Stop before writing credentials into tracked files.
