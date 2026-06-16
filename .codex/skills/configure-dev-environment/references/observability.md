# Observability Configuration

Owns:

- Seq local log search for DEV, QA, and PROD Azure App Service logs via the required Azure Event Hub collector path.
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

`config infra` is not complete until Seq and `agentic-otelcol` are running and healthy, and required OTEL collector connection values are configured in ignored local env.

When the collector profile is enabled, Azure-hosted console logs arrive from Azure Event Hub through the repo-managed collector path.

Direct app page and `/health` HTTP checks remain authoritative deployment gates. Seq log search comes from the collector-based Event Hub path, and Dozzle is the place for local container log inspection.
