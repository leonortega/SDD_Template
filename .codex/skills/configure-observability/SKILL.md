---
name: configure-observability
description: Configure Seq app log search, Grafana Infinity health checks, Grafana health alerts, and optional future Azure Event Hub ingestion guidance.
---

# Configure Observability

## Overview

Configure Seq, Grafana Infinity health alerts, and direct Rancher Desktop `/health` deployment checks used for ticket handoff evidence.

Observability is mandatory for `config infra` completion. Do not leave this step as optional.

## Shared Context

Read `.codex/skills/configure-dev-environment/references/observability.md` before asking for values or applying changes.

Use the shared command `python -m tools.sdd_cli configure`.

Apply `.codex/skills/_shared/delivery-contract.md` and `docs/context-management.md` before changing monitoring validation, dashboard behavior, or handoff evidence.

Safety:

- Keep Seq local data in the Docker `seq-data` volume; do not commit exported logs.

## Workflow

1. Run `Audit`.
2. Use `ValidateObservability` to validate Seq, Grafana Infinity health alerts, and direct Rancher Desktop health-check readiness.
3. Start or repair local monitoring services when needed so setup ends in a working state.
4. Validate all required checks before completion:
	- Seq API/health endpoint is `200`.
	- Seq native error-log alert exists.
	- Grafana `/health` alert rule exists and uses the configured pending duration.
	- Grafana Infinity health datasource and DEV, QA, and PROD health dashboards are configured.
	- Azure Event Hub collector configuration is not required for the current Rancher Desktop environment.

## Output

Report Seq API/health status, Seq alert status, Grafana Infinity datasource status, Grafana health alert status, missing values, and ticket handoff evidence without exposing secrets.

## Failure Rules

- Stop when required selected-lane values are missing.
- Stop when Seq or Grafana health validation fails.
- Stop before writing credentials into tracked files.
