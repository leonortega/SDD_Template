---
name: configure-observability
description: Configure Seq log search for this repo through Azure Event Hub to OpenTelemetry Collector Contrib ingestion and local runtime health checks.
---

# Configure Observability

## Overview

Configure Seq and Azure Event Hub to Seq ingestion used for deployment validation and ticket handoff evidence.

Observability is mandatory for `config infra` completion. Do not leave this step as optional.

## Shared Context

Read `.codex/skills/configure-dev-environment/references/observability.md` before asking for values or applying changes.

Use the shared script at `.codex/skills/configure-dev-environment/scripts/configure_infra_tools.ps1`.

Apply `.codex/skills/_shared/delivery-contract.md` and `docs/context-management.md` before changing monitoring validation, dashboard behavior, or handoff evidence.

Safety:

- Keep Seq local data in the Docker `seq-data` volume; do not commit exported logs.

## Workflow

1. Run `Audit`.
2. Use `SetSeqAzureEventHubLogs` to validate and enforce the OpenTelemetry Collector Contrib Azure Event Hub path for Seq.
3. Start or repair local monitoring services when needed so setup ends in a working state.
4. Validate all required checks before completion:
	- Seq API/health endpoint is `200`.
	- Event Hub collector profile is configured and running.
	- Required Event Hub connection strings and OTLP endpoint exist in ignored local env.

## Output

Report Seq API/health status, collector status, missing values, and ticket handoff evidence without exposing secrets.

## Failure Rules

- Stop when required Event Hub/OTLP values are missing.
- Stop when Seq or collector runtime validation fails.
- Stop before writing credentials into tracked files.
