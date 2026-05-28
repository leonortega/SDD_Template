# Observability Configuration

Owns:

- `infra/monitoring/prometheus.yml`.
- `infra/monitoring/prometheus.local.yml`.
- Grafana datasource and dashboard provisioning.
- Azure scrape targets after Azure outputs exist.

Use the shared script:

```powershell
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode SetPrometheusAzureTargets -ValuesJson $values
```

## Prometheus

Tracked template:

- `infra/monitoring/prometheus.yml`

Ignored runtime config:

- `infra/monitoring/prometheus.local.yml`

Use `infra/monitoring/prometheus.local.yml` for real Azure hostnames. Keep tracked `prometheus.yml` placeholder-safe.

Ask for Azure app hostnames only after Azure apps exist. Strip `https://` before writing Prometheus targets.

If `PROMETHEUS_CONFIG_FILE=./prometheus.local.yml` is needed, update ignored `infra/plane/variables.env` and recreate Prometheus after user approval.

Validation:

```powershell
docker inspect agentic-prometheus --format '{{range .Mounts}}{{println .Source "=>" .Destination}}{{end}}'
Invoke-RestMethod -Uri 'http://localhost:9090/api/v1/targets'
```

For PROD promotion checks, verify the PROD web target is present and `health=up` when Prometheus is running. If the PROD API target is configured but no API is deployed for the current app, record it as an observability configuration note rather than an application failure. Direct PROD page and `/health` checks remain the authoritative app-working gate.

## Grafana

Repo-managed provisioning:

- `infra/monitoring/grafana/provisioning/datasources/prometheus.yml`
- `infra/monitoring/grafana/provisioning/dashboards/dashboards.yml`
- `infra/monitoring/grafana/dashboards/local-infra-health.json`
- `infra/monitoring/grafana/dashboards/azure-app-health.json`

Default datasource points to `http://prometheus:9090` inside Docker.

Ask whether to rotate default Grafana credentials if dashboards will be shared or exposed beyond localhost.

Validation:

```powershell
Invoke-RestMethod -Uri 'http://localhost:3001/api/health'
docker logs --since 2m agentic-grafana 2>&1 | Select-String -Pattern 'provisioning.dashboard|finished to provision dashboards|level=error'
```
