# Observability Configuration

Owns:

- Seq local log search for live Rancher Desktop Kubernetes app logs emitted through Serilog.
- Native Seq alerting when any error or fatal log event appears.
- Grafana Infinity `/health` dashboards and alerts for DEV, QA, and PROD web/API probes.
- Optional future Azure Event Hub ingestion into Seq when Azure App Service is selected.

Use the shared script for the required collector path:

```bash
python -m tools.sdd_cli configure SetSeqAzureEventHubLogs
```

## Seq

Repo-managed local log search:

- `infra/monitoring/compose.yml` runs `datalust/seq:2025.2.16202` as `agentic-seq`.
- Seq is bound to `http://localhost:5341` and uses explicit local no-auth first-run configuration.
- Rancher Desktop site/API pods send live Serilog events directly to Seq through `RANCHER_APP_SEQ_URL`, default `http://host.docker.internal:5341`.
- `SetSeqAzureEventHubLogs` creates or updates the native Seq alert `Agentic E2E - Any Seq Error Logs`.
- The error alert uses `SEQ_ERROR_ALERT_WINDOW` and `SEQ_ERROR_ALERT_THRESHOLD` from `infra/monitoring/variables.env`; defaults are `1m` and `0`.

## Grafana Health Alerts

- `infra/monitoring/grafana/provisioning/datasources/infinity-health.yml` provisions the Grafana Infinity datasource for Rancher Desktop health URLs.
- `infra/monitoring/grafana/provisioning/alerting/health-alerts.yml` provisions Grafana-managed alerts that query `/health` JSON through Infinity and fire when the derived `up` value is below `1`.
- `GRAFANA_HEALTH_ALERT_FOR` controls how long a `/health` endpoint must remain down before firing; the default is `2m`.
- `noDataState` and `execErrState` stay `OK` to avoid noisy startup or deploy gaps.

Azure Event Hub ingestion is not part of the current local environment. Add a collector path only when Azure App Service is selected again.

Validation (required path):

```bash
python -m tools.sdd_cli configure SetSeqAzureEventHubLogs
```

`config infra` is not complete until Seq, the Seq error-log alert, Grafana Infinity health datasource, Grafana health alerts, and local Rancher Desktop health dashboards are running and healthy.

Direct app page and `/health` checks remain authoritative deployment gates. Seq log search comes from direct Serilog Seq sinks for Rancher Desktop. Grafana health dashboards are operator visibility over the same direct `/health` endpoints.

For the Rancher Desktop local lane, Grafana Infinity queries the site/API DEV, QA, and PROD localhost port-forward ports through `host.docker.internal`, because Grafana runs inside Docker. Real local values for `SEQ_URL` and `RANCHER_APP_SEQ_URL` belong in ignored env files or Gitea Actions secrets.
