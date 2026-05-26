---
name: configure-observability
description: Configure Prometheus, Grafana, logs, and Azure scrape targets for this repo, including prometheus.local.yml, Prometheus mount validation, Grafana datasource/dashboard provisioning, Azure app health dashboards, and local service health checks.
---

# Configure Observability

Read `.codex/skills/configure-dev-environment/references/observability.md` before asking for values or applying changes.

Use the shared script at `.codex/skills/configure-dev-environment/scripts/configure_infra_tools.ps1`.

Safety:

- Keep real Azure hostnames in ignored `infra/monitoring/prometheus.local.yml`.
- Keep tracked `infra/monitoring/prometheus.yml` placeholder-safe.
- Do not rotate or expose Grafana credentials without explicit user direction.

Workflow:

1. Run `Audit`.
2. Configure Prometheus Azure targets only after Azure output URLs exist.
3. Use `SetPrometheusAzureTargets` for ignored local target updates.
4. Ask before recreating Prometheus or Grafana containers.
5. Validate Prometheus targets and Grafana health only when infra is running.
