## MODIFIED Requirements

### Requirement: Safe structured log content
Application logs SHALL include fields needed for operations filtering and SHALL NOT expose configured secrets, tokens, connection strings, or credential-bearing URLs.

#### Scenario: Log fields support filtering
- **WHEN** an application log event is emitted by the Site or API
- **THEN** the event includes timestamp, level, category/source, message, exception details when present, and correlation ID when the event is request-scoped

#### Scenario: Sensitive configuration is not logged
- **WHEN** application startup, request handling, or exception handling writes logs
- **THEN** logged messages do not include configured secrets, tokens, connection strings, authorization headers, or credential-bearing URLs
