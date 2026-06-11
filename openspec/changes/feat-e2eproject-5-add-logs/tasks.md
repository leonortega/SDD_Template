## Review Workload Forecast

Estimated changed lines: 350-650
400-line budget risk: Medium
Chained PRs recommended: No
Decision needed before apply: No. Decision recorded: use Grafana Alloy to collect Azure Event Hubs logs and write to local Loki for Grafana log boards.
Delivery strategy: single-pr
Suggested work units: single PR covering Serilog configuration, Alloy/Loki/Grafana provisioning, tests, and docs/context review.

## 1. Observability Decision

- [x] 1.1 Inspect existing monitoring, Azure, Grafana, and Grafana Alloy configuration to identify the supported downstream log store/datasource path.
- [x] 1.2 Record the datasource decision or implementation gap in design/tasks before changing application code.
- [x] 1.3 Verify no secret-bearing Azure, Grafana, or datasource values need to be committed.

## 2. Serilog Configuration

- [x] 2.1 Add required Serilog package references to API and Site projects.
- [x] 2.2 Configure API startup to use Serilog with structured fields and safe filtering.
- [x] 2.3 Configure Site startup to use Serilog with structured fields and safe filtering.
- [x] 2.4 Add placeholder-safe appsettings or environment variable configuration for DEV, QA, and PROD minimum levels.

## 3. Log Routing And Grafana

- [x] 3.1 Add or update Grafana Alloy configuration with separate DEV, QA, and PROD Azure log consumers.
- [x] 3.2 Add or update deployment/observability configuration for Azure-hosted log routing through the matching environment consumer.
- [x] 3.3 Add separate DEV, QA, and PROD Grafana boards with text, date/time range, and category/source filtering.
- [x] 3.4 Keep tracked monitoring files placeholder-safe and document local-only values where required.

## 4. Tests And Validation

- [x] 4.1 Add tests or deterministic checks for environment-specific logging levels.
- [x] 4.2 Add tests or deterministic checks for Grafana Alloy per-environment consumers.
- [x] 4.3 Add tests or deterministic checks for DEV, QA, and PROD Grafana board filter variables.
- [x] 4.4 Run targeted build/tests for touched projects.
- [x] 4.5 Confirm full PR validation remains responsible for format, coverage, dependency audit, secret scan, and Trivy gates.

## 5. Context And Handoff

- [x] 5.1 Run Context Findings Review and update docs if durable observability guidance changes.
- [x] 5.2 Update Plane/Gitea handoff with validation, assumptions, docs status, and memory status.

## PR Review Feedback

- [x] PRF-1 Source: Gitea review 21, head b28a1e6e0e420635a877e20c2f507bfc5c0a7a4c, severity BLOCKER, review mode human, requested change: add an executable validation path for Azure Event Hubs -> Grafana Alloy -> Loki ingestion instead of leaving live ingestion as an unaddressed QA gap.
- [x] PRF-2 Source: Gitea review 21, head b28a1e6e0e420635a877e20c2f507bfc5c0a7a4c, severity BLOCKER, review mode human, requested change: fix full-solution dotnet format JSON002 in tools/SDDTemplate.DeliveryTools.Tests/DeliveryToolsTests.cs:1146.
