## Why

Plane ticket E2EPROJECT-6 requires consistent, structured logging across the Blazor site and API with end-to-end correlation IDs. Current behavior does not guarantee correlation propagation, safe redaction, or consistent request/exception logging conventions.

## What Changes

- Configure and standardize structured logging in both `SDDTemplate.Site` and `SDDTemplate.Api`.
- Implement correlation ID generation/reuse and propagation from site requests into downstream API calls.
- Ensure request and exception logging include operational metadata while redacting sensitive values.
- Add focused automated tests for correlation propagation and safe logging behavior.
- Update developer guidance for logging conventions and safe logging boundaries.

## Capabilities

### New Capabilities
- `request-correlation-logging`: End-to-end correlation ID behavior and structured request/exception logging between Site and API.

### Modified Capabilities
- `observability-logging`: Extend existing logging capability to include strict correlation propagation and sensitive-data redaction requirements for application logs.

## Impact

- `src/SDDTemplate.Site` startup/middleware, API client calls, and logging configuration.
- `src/SDDTemplate.Api` startup/middleware and logging configuration.
- Logging-related tests under `tests/SDDTemplate.Site.Tests`.
- Potentially shared logging helper/middleware code where cross-app behavior is centralized.
- `docs/development.md` if durable logging conventions are clarified.
