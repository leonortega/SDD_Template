# observability-logging Specification

## Purpose
Defines application logging behavior, safe structured log content, deployed log routing, and local Seq search expectations for Azure-hosted Site and API environments.

## Requirements
### Requirement: Environment-specific Serilog levels

The API and Site SHALL initialize Serilog with environment-specific minimum levels. DEV and QA SHALL allow Debug-or-higher troubleshooting logs, while PROD SHALL emit only Warning and Error application logs unless a higher-severity override is configured.

#### Scenario: DEV and QA logging is debug

- **WHEN** the API or Site runs with the DEV or QA environment configuration
- **THEN** Serilog accepts Debug-or-higher troubleshooting-level application events with timestamp, level, category/source, message, and exception details when present

#### Scenario: PROD logging is restricted

- **WHEN** the API or Site runs with the PROD environment configuration
- **THEN** Serilog emits Warning and Error application events and suppresses lower-severity application events

### Requirement: Safe structured log content
Application logs SHALL include fields needed for operations filtering and SHALL NOT expose configured secrets, tokens, connection strings, or credential-bearing URLs.

#### Scenario: Log fields support filtering
- **WHEN** an application log event is emitted by the Site or API
- **THEN** the event includes timestamp, level, category/source, message, exception details when present, and correlation ID when the event is request-scoped

#### Scenario: Sensitive configuration is not logged
- **WHEN** application startup, request handling, or exception handling writes logs
- **THEN** logged messages do not include configured secrets, tokens, connection strings, authorization headers, or credential-bearing URLs

### Requirement: Deployed log routing

Azure-hosted API and Site logs SHALL be routed through App Service diagnostic settings to the matching Log Analytics workspace for DEV, QA, and PROD.

#### Scenario: DEV logs use DEV workspace

- **WHEN** the API or Site emits logs in the Azure-hosted DEV environment
- **THEN** App Service diagnostics write those logs to the DEV Log Analytics workspace

#### Scenario: QA logs use QA workspace

- **WHEN** the API or Site emits logs in the Azure-hosted QA environment
- **THEN** App Service diagnostics write those logs to the QA Log Analytics workspace

#### Scenario: PROD logs use PROD workspace

- **WHEN** the API or Site emits logs in the Azure-hosted PROD environment
- **THEN** App Service diagnostics write those logs to the PROD Log Analytics workspace

### Requirement: Environment-specific Seq console log search

Seq SHALL provide searchable Azure-hosted application console logs for DEV, QA, and PROD through the optional Azure Event Hub collector path. Imported log events SHALL include environment, timestamp, category/source, resource, and message fields so operators can search each environment by text, date/time range, and category/source.

#### Scenario: Operator searches imported environment logs

- **WHEN** an operator searches Seq for imported Azure-hosted application logs by environment, text, date/time range, or category/source
- **THEN** matching log events include environment, timestamp, category/source, resource, and message fields.

### Requirement: Optional Event Hub collector ingestion

When Azure Event Hub ingestion is configured, Seq SHALL support Azure-hosted application console logs through an OpenTelemetry Collector Contrib pipeline that consumes the DEV, QA, and PROD Event Hub inputs and exports logs into Seq.

#### Scenario: Operator filters DEV logs

- **WHEN** an operator searches Seq for DEV logs
- **THEN** Seq contains DEV console events imported from the DEV Log Analytics workspace with environment, text, date/time, and category/source fields

#### Scenario: Operator filters QA logs

- **WHEN** an operator searches Seq for QA logs
- **THEN** Seq contains QA console events imported from the QA Log Analytics workspace with environment, text, date/time, and category/source fields

#### Scenario: Collector ingests DEV Event Hub logs

- **WHEN** the optional Event Hub collector profile is enabled for DEV
- **THEN** the collector consumes DEV console log events from Azure Event Hub and exports them to Seq with environment labeling

#### Scenario: Collector ingests QA Event Hub logs

- **WHEN** the optional Event Hub collector profile is enabled for QA
- **THEN** the collector consumes QA console log events from Azure Event Hub and exports them to Seq with environment labeling

#### Scenario: Collector ingests PROD Event Hub logs

- **WHEN** the optional Event Hub collector profile is enabled for PROD
- **THEN** the collector consumes PROD console log events from Azure Event Hub and exports them to Seq with environment labeling
