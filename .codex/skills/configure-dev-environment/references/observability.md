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

## Loki And Grafana Alloy

Azure App Service logs flow through Azure diagnostic settings to Event Hubs, then Grafana Alloy reads those hubs and writes to Loki. The tracked Azure Bicep provisions one Event Hubs namespace per environment, an `appservice-logs` hub, a `grafana-alloy-{env}` consumer group, a send-only diagnostic authorization rule, a listen-only Alloy authorization rule, and App Service diagnostic settings. The namespace must be Standard or higher with Kafka enabled; Alloy uses the Event Hubs Kafka endpoint.

Use the shared script after Bicep deployment has created Event Hubs:

```powershell
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode SetAzureLogIngestion
```

The mode infers the current Azure subscription, tenant, default resource groups, Event Hubs namespaces, and App Service diagnostic settings. It creates or reuses `sp-agentic-e2e-alloy-logs`, assigns `Azure Event Hubs Data Receiver`, and writes only ignored local values to `infra/plane/variables.env`. Alloy reads from listen-only Event Hubs connection strings so local ingestion remains independent of Azure CLI login state:

- `AZURE_DEV_EVENTHUB_NAMESPACE`
- `AZURE_DEV_EVENTHUB_NAME`
- `AZURE_DEV_EVENTHUB_CONNECTION_STRING`
- `AZURE_QA_EVENTHUB_NAMESPACE`
- `AZURE_QA_EVENTHUB_NAME`
- `AZURE_QA_EVENTHUB_CONNECTION_STRING`
- `AZURE_PROD_EVENTHUB_NAMESPACE`
- `AZURE_PROD_EVENTHUB_NAME`
- `AZURE_PROD_EVENTHUB_CONNECTION_STRING`
- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_CLIENT_SECRET`

Validation:

```powershell
docker compose --env-file .\infra\plane\variables.env -f .\infra\compose.yml up -d loki alloy
Invoke-RestMethod -Uri 'http://localhost:3100/ready'
Invoke-RestMethod -Uri 'http://localhost:12345/-/ready'
.\infra\monitoring\validate-azure-log-ingestion.ps1
```

Do not print service principal secrets or Event Hubs connection strings. If Alloy logs show `kafka: client has run out of available brokers to talk to: EOF`, verify the namespace has `kafkaEnabled: true`, the namespace is Standard or higher, the container can reach `*.servicebus.windows.net:9093`, and `AZURE_{ENV}_EVENTHUB_CONNECTION_STRING` was loaded when Alloy was recreated.
