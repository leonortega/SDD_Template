## Why

Plane ticket E2EPROJECT-5 asks for Serilog logging across the API and Blazor site, with verbose troubleshooting output in DEV/QA and reduced Warning/Error output in PROD. The change improves operational visibility for deployed Azure environments and gives operators a Grafana view for finding logs by text, date, and category.

## What Changes

- Add environment-specific Serilog configuration for `SDDTemplate.Api` and `SDDTemplate.Site`.
- Route application logs from Azure-hosted runtimes through Grafana Alloy.
- Add one Grafana log board and one log consumer per environment: DEV, QA, and PROD.
- Each environment-specific Grafana board must support filters for text, date/time range, and category/source.
- Add validation for environment-specific logging levels and dashboard/provisioning behavior where practical.
- Avoid committing secrets, local-only Azure hostnames, or credential-bearing observability endpoints.

## Capabilities

### New Capabilities

- `observability-logging`: Application logging configuration, environment-specific log levels, Grafana Alloy log collection, per-environment log consumers, and per-environment Grafana log boards.

### Modified Capabilities

- None.

## Impact

- `src/SDDTemplate.Api` startup, package references, and appsettings.
- `src/SDDTemplate.Site` startup, package references, and appsettings.
- Shared observability or deployment configuration under `infra/monitoring`, `infra/azure`, and tracked placeholders where needed.
- Grafana Alloy configuration for separate DEV, QA, and PROD log consumers.
- Grafana dashboard provisioning files for separate DEV, QA, and PROD log boards.
- Tests or delivery helpers that can verify logging-level configuration and generated dashboard shape.
