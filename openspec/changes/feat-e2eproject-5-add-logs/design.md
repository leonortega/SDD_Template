## Context

The repository currently has separate ASP.NET Core API and Blazor Site deployables, Azure DEV/QA/PROD runtimes, and local Prometheus/Grafana monitoring. E2EPROJECT-5 adds cross-cutting logging behavior, so both application startup paths and observability provisioning need aligned behavior without leaking local secrets or environment-specific private values into tracked files.

## Goals / Non-Goals

**Goals:**

- Configure Serilog consistently for the API and Site.
- Use environment-specific minimum levels: verbose enough for DEV/QA troubleshooting and Warning/Error only for PROD.
- Preserve useful fields for filtering: timestamp, level, category/source, message, and exception details when present.
- Provide separate Grafana log boards for DEV, QA, and PROD with text, date/time range, and category/source filtering.
- Configure separate Grafana Alloy log consumers for DEV, QA, and PROD Azure logs.
- Keep deployable configuration compatible with Azure App Service and the repo's existing delivery flow.

**Non-Goals:**

- Replace the repository's existing deployment topology.
- Commit Azure credentials, private hostnames, tokens, or local-only datasource endpoints.
- Build one shared log consumer for all environments.
- Build a separate production log storage product unless Grafana Alloy requires a compatible downstream log store already supported by the repo's observability stack.
- Change user-facing application behavior beyond observability.

## Decisions

- Use Serilog in both deployables through shared conventions rather than independent ad hoc setup. This keeps environment level behavior consistent across API and Site while still allowing each appsettings file to hold project-specific overrides. Alternative considered: configure only Microsoft.Extensions.Logging providers; this would not satisfy the explicit Serilog requirement.
- Keep environment-specific levels in configuration, not hard-coded branches. DEV and QA can use verbose/debug settings, while PROD can restrict to Warning/Error through production appsettings or deployment environment variables. Alternative considered: compile-time constants; this would make deployment promotion less flexible.
- Use Grafana Alloy as the Azure log collection component. Alloy configuration should define separate DEV, QA, and PROD consumers so environment routing, filtering, and credentials remain isolated. Alternative considered: one shared consumer for all Azure logs; this was rejected because the updated ticket scope requires one consumer per environment.
- Use local Loki as the downstream log store for Alloy and Grafana. The current repo has Prometheus for metrics only, and Loki matches Grafana log boards while keeping the monitoring stack local and placeholder-safe. Alternative considered: query logs from Prometheus; this was rejected because Prometheus is metric-oriented and the requested board is log-focused.
- Provision separate Grafana boards for DEV, QA, and PROD as tracked dashboard/configuration shapes with placeholder-safe datasource references. Real datasource URLs and credentials remain local or environment-managed. Alternative considered: one shared dashboard with an environment variable; this was rejected because the updated ticket scope asks for one board per environment.

## Risks / Trade-offs

- Grafana Alloy needs a compatible downstream log path for querying -> use the repo-supported Grafana datasource path and keep per-environment routing explicit.
- Verbose DEV/QA logs can expose sensitive values -> configure filtering/enrichment carefully and avoid logging secrets, connection strings, tokens, or raw request bodies.
- Azure App Service logging differs by runtime and environment -> prefer environment variables and deployment-safe placeholders over hard-coded host-specific values.
- Grafana dashboard JSON can drift from available datasources -> keep datasource names configurable and validate all three board shapes in tests or scripted checks.

## Migration Plan

- Add Serilog package references and startup configuration to API and Site.
- Add placeholder-safe logging configuration for each environment.
- Add or update Grafana Alloy consumers for DEV, QA, and PROD.
- Add or update Grafana boards for DEV, QA, and PROD.
- Validate locally with build/tests and rely on PR validation for the full gate.
- Roll back by reverting the application logging package/configuration and Grafana provisioning changes before deployment promotion.

## Open Questions

- None.

## QA Evidence Note

QA should verify tracked provisioning and application logging configuration. Live Azure Event Hubs to Alloy to Loki ingestion evidence should be collected when the environment-specific Event Hubs settings and Azure identity are configured; otherwise the PR and Plane handoff must record the environment setup gap.
