## Review Workload Forecast

Estimated changed lines: 220-420
400-line budget risk: Medium
Chained PRs recommended: No
Decision needed before apply: No
Delivery strategy: single-pr
Suggested work units: single PR covering Site/API logging changes, tests, and docs/context review.

## 1. Correlation and Logging Implementation

- [x] 1.1 Add or standardize correlation ID middleware for Site request handling.
- [x] 1.2 Propagate correlation IDs from Site API calls to API request headers.
- [x] 1.3 Add or standardize API correlation ID middleware and ensure request/exception logs include the propagated ID.
- [x] 1.4 Verify structured message-template usage in touched logging paths.

## 2. Safe Logging Guardrails

- [x] 2.1 Add or update logging filters/redaction for sensitive headers and payload fields.
- [x] 2.2 Ensure exception logging preserves operational metadata while excluding sensitive values.
- [x] 2.3 Review touched paths for unsafe interpolation/payload logging patterns and replace as needed.

## 3. Tests and Validation

- [x] 3.1 Add tests for correlation ID generation/reuse and Site-to-API propagation.
- [x] 3.2 Add tests for API correlation-aware request/exception log behavior.
- [x] 3.3 Add tests or deterministic checks that sensitive values are excluded from logs.
- [x] 3.4 Run targeted validation (`dotnet build .\SDDTemplate.slnx`, `dotnet test .\SDDTemplate.slnx`).

## 4. Quality Gates and Handoff

- [x] 4.1 Confirm PR validation remains authoritative for full quality/security gates.
- [x] 4.2 Run Context Findings Review and update docs if durable logging conventions changed.
- [x] 4.3 Update implementation handoff with validation evidence, assumptions, docs status, and memory status.

## PR Review Feedback

- [x] PRF-1 (source: gitea review 23, severity: actionable): Extract duplicated correlation middleware into a shared common project consumed by both Site and API.
- [x] PRF-2 (source: gitea review 23, severity: actionable): Add Info/Debug logs in relevant API and Site startup/process/validation paths.
