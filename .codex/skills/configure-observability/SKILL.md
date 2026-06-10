---
name: configure-observability
description: Configure Prometheus, Grafana, logs, and Azure scrape targets for this repo, including prometheus.local.yml, Prometheus mount validation, Grafana datasource/dashboard provisioning, Azure app health dashboards, and local service health checks.
---

# Configure Observability

## Overview

Configure Prometheus, Grafana, Loki, Grafana Alloy, Azure Event Hubs log ingestion, and Azure scrape targets used for deployment validation and ticket handoff evidence.

## Shared Context

Read `.codex/skills/configure-dev-environment/references/observability.md` before asking for values or applying changes.

Use the shared script at `.codex/skills/configure-dev-environment/scripts/configure_infra_tools.ps1`.

Apply `.codex/skills/_shared/delivery-contract.md` and `docs/context-management.md` before changing monitoring validation, dashboard behavior, or handoff evidence.

Safety:

- Keep real Azure hostnames in ignored `infra/monitoring/prometheus.local.yml`.
- Keep tracked `infra/monitoring/prometheus.yml` placeholder-safe.
- Keep Azure Event Hubs, Alloy service-principal values, and listen-only Event Hubs connection strings in ignored `infra/plane/variables.env`.
- Do not rotate or expose Grafana credentials without explicit user direction.

## Workflow

1. Run `Audit`.
2. Configure Prometheus Azure targets only after Azure output URLs exist.
3. Use `SetPrometheusAzureTargets` for ignored local target updates.
4. Configure Azure log ingestion only after Bicep creates Event Hubs and App Service diagnostic settings.
5. Use `SetAzureLogIngestion` to infer Event Hubs values, create or reuse the Alloy service principal, assign Event Hubs Data Receiver, and write ignored local env values, including listen-only Event Hubs connection strings for Alloy.
6. Ask before recreating Prometheus, Loki, Alloy, or Grafana containers unless the user has explicitly requested full implementation.
7. Validate Prometheus targets, Loki readiness, Alloy readiness, Grafana health, and log ingestion only when infra is running.

## Output

Report Prometheus target status, Loki readiness, Alloy readiness, Grafana provisioning status, validation commands, missing values, and ticket handoff evidence without exposing secrets.

## Failure Rules

- Stop when Azure target values are missing or not confirmed.
- Stop when infra is unavailable and the user has not approved live validation.
- Stop before writing real hostnames or credentials into tracked files.
