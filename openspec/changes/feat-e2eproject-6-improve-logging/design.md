## Context

This change targets two running apps (`SDDTemplate.Site` and `SDDTemplate.Api`) and requires consistent logging semantics across the HTTP boundary. The repository already has observability/logging behavior from E2EPROJECT-5; this ticket tightens app-level behavior for correlation IDs, request/exception coverage, and safe logging.

## Goals / Non-Goals

**Goals:**
- Establish one correlation ID lifecycle per incoming site request.
- Propagate correlation ID to API requests and ensure both sides log the same ID.
- Standardize structured request and exception logging fields.
- Prevent sensitive data from being logged in routine or error paths.
- Add deterministic tests for cross-app correlation behavior.

**Non-Goals:**
- Building new dashboards/alerts.
- Replacing the existing environment-level observability pipeline.
- Refactoring unrelated feature code.

## Decisions

1. Correlation ID middleware in both apps
- Decision: Introduce or standardize middleware that reads incoming correlation header, validates it, and generates one when absent.
- Rationale: Middleware ensures consistent behavior early in the pipeline and avoids scattered per-endpoint handling.
- Alternative considered: Generate IDs only in controllers/components. Rejected due to incomplete coverage and inconsistent request logging.

2. Header-based propagation from Site to API
- Decision: The Site forwards correlation IDs via HTTP headers on API calls.
- Rationale: Header propagation is explicit, transport-safe, and testable in integration tests.
- Alternative considered: Ambient/static context only. Rejected because it is fragile across async boundaries and external calls.

3. Structured templates plus safe redaction guardrails
- Decision: Keep structured templates and enforce sensitive-field exclusion in logging paths (especially exceptions/request details).
- Rationale: Supports queryability while preventing secret leakage.
- Alternative considered: Full payload logging for diagnostics. Rejected due to security/privacy risk.

4. Add behavior tests, not just configuration checks
- Decision: Add tests that verify correlation continuity and absence of sensitive values in representative log paths.
- Rationale: Config-only checks can pass while runtime behavior is wrong.
- Alternative considered: Manual-only verification. Rejected due to regression risk.

## Risks / Trade-offs

- [Risk] Middleware ordering mistakes can break correlation propagation.
  - Mitigation: Place correlation middleware before request logging and validate order in tests.
- [Risk] Over-redaction can reduce diagnostics value.
  - Mitigation: Redact only known sensitive keys/headers and keep operational metadata fields intact.
- [Risk] Increased log volume in DEV/QA.
  - Mitigation: Keep existing environment-level level controls and avoid verbose payload dumps.

## Migration Plan

1. Implement correlation middleware and propagation hooks.
2. Update logging setup in Site and API startup/configuration.
3. Add/adjust tests for correlation and sensitive-data exclusion.
4. Run targeted build/tests locally.
5. Rely on PR validation for full quality gates and security scans.

Rollback strategy:
- Revert the logging middleware/propagation changes while preserving existing baseline logging configuration.

## Open Questions

- Should correlation IDs use an existing external trace header format exclusively, or support both internal and external names during transition?
- Do we need additional test coverage for background/async flows that are not request-scoped?
