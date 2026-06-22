# Observability Configuration

Owns:

- Seq local log search for DEV, QA, and PROD Azure App Service logs via the required Azure Event Hub collector path.
- Seq local log search for sanitized Rancher Desktop Kubernetes pod logs captured during local-lab deployment.
- Native Seq alerting when any error or fatal log event appears.
- Grafana `/health` alerts for DEV, QA, and PROD web/API probes.
- Required OpenTelemetry Collector Contrib ingestion from Azure Event Hub into Seq.

Use the shared script for the required collector path:

```powershell
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode SetSeqAzureEventHubLogs
```

## Seq

Repo-managed local log search:

- `infra/monitoring/compose.yml` runs `datalust/seq:2025.2.16202` as `agentic-seq`.
- Seq is bound to `http://localhost:5341` and uses explicit local no-auth first-run configuration.
- Seq receives Azure-hosted console logs through the optional OpenTelemetry Collector Contrib Event Hub profile.
- The Rancher Desktop lane posts sanitized pod-log events through Seq's CLEF ingestion endpoint during `infra/rancher/capture-observability.sh`.
- `SetSeqAzureEventHubLogs` creates or updates the native Seq alert `Agentic E2E - Any Seq Error Logs`.
- The error alert uses `SEQ_ERROR_ALERT_WINDOW` and `SEQ_ERROR_ALERT_THRESHOLD` from `infra/monitoring/variables.env`; defaults are `1m` and `0`.

## Grafana Health Alerts

- `infra/monitoring/grafana/provisioning/alerting/health-alerts.yml` provisions a Grafana-managed alert over `probe_success{job="blackbox_http_health"} == 0`.
- `GRAFANA_HEALTH_ALERT_FOR` controls how long a `/health` endpoint must remain down before firing; the default is `10s`, matching Grafana's local scheduler interval.
- The blackbox exporter must listen on `0.0.0.0:9115` so Prometheus can scrape it over the Docker monitoring network.
- `noDataState` and `execErrState` stay `OK` to avoid noisy startup or deploy gaps.

Collector-based ingestion:

- `infra/monitoring/compose.yml` defines the required `agentic-otelcol` service under the `eventhub` profile.
- `infra/monitoring/otelcol/collector.yaml` configures separate DEV, QA, and PROD Azure Event Hub receivers and exports OTLP logs to Seq.
- `infra/monitoring/variables.env` holds the required `OTELCOL_*` connection strings and OTLP endpoint values as ignored local secrets.

Validation (required path):

```powershell
Invoke-RestMethod -Uri 'http://localhost:5341/api'
docker compose --profile eventhub --env-file .\infra\plane\variables.env --env-file .\infra\monitoring\variables.env -f .\infra\compose.yml --project-directory .\infra config --quiet
docker compose --profile eventhub --env-file .\infra\plane\variables.env --env-file .\infra\monitoring\variables.env -f .\infra\compose.yml --project-directory .\infra up -d otelcol
```

After the collector starts, search Seq for `Environment = 'DEV'`, `Environment = 'QA'`, and `Environment = 'PROD'`.

`config infra` is not complete until Seq, the Seq error-log alert, Grafana health alerts, and `agentic-otelcol` are running and healthy, and required OTEL collector connection values are configured in ignored local env.

When the collector profile is enabled, Azure-hosted console logs arrive from Azure Event Hub through the repo-managed collector path.

Direct app page and `/health` HTTP checks remain authoritative deployment gates. Seq log search comes from the collector-based Event Hub path, and Dozzle is the place for local container log inspection.

For the Rancher Desktop local lane, `infra/monitoring/prometheus/targets.local.yml` includes `provider: rancher-desktop` blackbox targets for site/API DEV, QA, and PROD local hosts. Real local values for `SEQ_URL`, `PROMETHEUS_URL`, and `RANCHER_OBSERVABILITY_ENABLED` belong in ignored env files or Gitea Actions secrets.
