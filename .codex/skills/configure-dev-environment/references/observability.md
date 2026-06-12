# Observability Configuration

Owns:

- Grafana datasource and dashboard provisioning.
- Azure Monitor and Log Analytics local configuration after Azure outputs exist.
- `infra/monitoring/validate-azure-monitor-logs.ps1`.

Use the shared script after Azure Bicep deployment has created Log Analytics workspaces and App Service diagnostic settings:

```powershell
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode SetGrafanaAzureMonitor
```

## Azure Monitor

Azure App Service diagnostics flow directly to Log Analytics workspaces. Grafana queries those workspaces through the built-in Azure Monitor datasource. This repo does not use a local scrape store, log store, log collector, or streaming hub for observability.

The Bicep template creates one Log Analytics workspace per environment and configures App Service diagnostics with:

- `workspaceId`
- `logAnalyticsDestinationType: Dedicated`

The configure script infers the deployed workspaces and writes local-only values to ignored `infra/plane/variables.env`:

- `GRAFANA_AZURE_TENANT_ID`
- `GRAFANA_AZURE_CLIENT_ID`
- `GRAFANA_AZURE_CLIENT_SECRET`
- `GRAFANA_AZURE_SUBSCRIPTION_ID`
- `GRAFANA_AZURE_DEV_LOG_ANALYTICS_WORKSPACE_ID`
- `GRAFANA_AZURE_QA_LOG_ANALYTICS_WORKSPACE_ID`
- `GRAFANA_AZURE_PROD_LOG_ANALYTICS_WORKSPACE_ID`
- `GRAFANA_AZURE_DEV_LOG_ANALYTICS_WORKSPACE_RESOURCE_ID`
- `GRAFANA_AZURE_QA_LOG_ANALYTICS_WORKSPACE_RESOURCE_ID`
- `GRAFANA_AZURE_PROD_LOG_ANALYTICS_WORKSPACE_RESOURCE_ID`

Do not print service-principal secrets or write them to tracked files.

## Grafana

Repo-managed provisioning:

- `infra/monitoring/grafana/provisioning/datasources/azure-monitor.yml`
- `infra/monitoring/grafana/provisioning/dashboards/dashboards.yml`

Local generated dashboard files belong in ignored `infra/monitoring/grafana/dashboards.local/`.
`SetGrafanaAzureMonitor` generates one Azure Monitor dashboard per environment with:

- Azure log activity.
- App Service `/health` check activity and failures.
- Recent `/health` check rows.
- Recent Azure App Service logs.

It also generates one explicit health dashboard per environment named `DEV Health Dashboard`, `QA Health Dashboard`, and `PROD Health Dashboard`. Each health dashboard uses red/green stat blocks for the web and API App Service `/health` state. A block is green only when the latest `/health` row for that app returned HTTP 2xx within the last 24 hours; missing, stale, or non-2xx rows are red. The dashboard keeps a 7-day lookback so older health evidence still explains why a block is stale instead of showing an empty panel.

`Audit` reports stale generated dashboards when the local dashboard JSON does not include the `/health` panels or explicit health dashboards.

Default datasource:

- `uid: azure-monitor`
- `type: grafana-azure-monitor-datasource`
- App Registration client-secret auth from ignored environment variables.

Validation:

```powershell
Invoke-RestMethod -Uri 'http://localhost:3001/api/health'
docker logs --since 2m agentic-grafana 2>&1 | Select-String -Pattern 'provisioning.dashboard|finished to provision dashboards|level=error|Azure Monitor'
.\infra\monitoring\validate-azure-monitor-logs.ps1
```

Direct app page and `/health` HTTP checks remain authoritative deployment gates. Grafana Azure Monitor is deployment evidence when configured and reachable.
