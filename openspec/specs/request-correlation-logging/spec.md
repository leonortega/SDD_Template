# request-correlation-logging Specification

## Purpose
Defines request-scoped correlation ID generation, reuse, propagation, and correlated safe logging behavior across the Site and API.

## Requirements
### Requirement: End-to-end correlation ID propagation
The system SHALL establish one correlation ID per inbound Site request and SHALL propagate that ID to downstream API calls made by the Site.

#### Scenario: Site request without correlation header
- **WHEN** a Site request arrives without a correlation ID header
- **THEN** the Site generates a correlation ID and uses it for request logs and downstream API calls for that request

#### Scenario: Site request with existing correlation header
- **WHEN** a Site request arrives with a valid correlation ID header
- **THEN** the Site reuses that correlation ID for request logs and downstream API calls for that request

### Requirement: API correlation-aware logging
The API SHALL read correlation IDs from incoming requests and include that correlation ID in related request and exception logs for the same request scope.

#### Scenario: API receives propagated correlation header
- **WHEN** the API receives a request with a correlation ID header from the Site
- **THEN** API request and exception logs for that request include the same correlation ID value

### Requirement: Sensitive data exclusion in correlated logs
The Site and API SHALL NOT log sensitive data, including passwords, tokens, authorization headers, and private personal fields, in correlated request or exception log events.

#### Scenario: Exception logging on authenticated request
- **WHEN** an exception occurs during a request that contains authentication/authorization metadata
- **THEN** logged events contain the correlation ID and operational metadata but exclude sensitive values
