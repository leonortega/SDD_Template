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
