## Requirements

### Requirement: Environment-specific Serilog levels

The API and Site SHALL initialize Serilog with environment-specific minimum levels. DEV and QA SHALL allow verbose troubleshooting logs, while PROD SHALL emit only Warning and Error application logs unless a higher-severity override is configured.

#### Scenario: DEV and QA logging is verbose

- **WHEN** the API or Site runs with the DEV or QA environment configuration
- **THEN** Serilog accepts verbose troubleshooting-level application events with timestamp, level, category/source, message, and exception details when present

#### Scenario: PROD logging is restricted

- **WHEN** the API or Site runs with the PROD environment configuration
- **THEN** Serilog emits Warning and Error application events and suppresses lower-severity application events

### Requirement: Safe structured log content

Application logs SHALL include fields needed for operations filtering and SHALL NOT expose configured secrets, tokens, connection strings, or credential-bearing URLs.

#### Scenario: Log fields support filtering

- **WHEN** an application log event is emitted
- **THEN** the event includes timestamp, level, category/source, message, and exception details when present

#### Scenario: Sensitive configuration is not logged

- **WHEN** application startup or request handling writes logs
- **THEN** logged messages do not include configured secrets, tokens, connection strings, or credential-bearing URLs

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

### Requirement: Environment-specific Grafana log boards

Grafana SHALL provide separate Azure Monitor log-focused boards for DEV, QA, and PROD. Each board SHALL let operators filter log records for its environment by text, date/time range, and category/source.

#### Scenario: Operator filters DEV logs

- **WHEN** an operator opens the DEV Grafana log board
- **THEN** the board exposes controls or query variables for text, date/time range, and category/source filtering over DEV logs

#### Scenario: Operator filters QA logs

- **WHEN** an operator opens the QA Grafana log board
- **THEN** the board exposes controls or query variables for text, date/time range, and category/source filtering over QA logs

#### Scenario: Operator filters PROD logs

- **WHEN** an operator opens the PROD Grafana log board
- **THEN** the board exposes controls or query variables for text, date/time range, and category/source filtering over PROD logs
