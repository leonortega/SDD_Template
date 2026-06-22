# Failure Pattern Memory

## Seq Alert Updates Need Force For Existing Fields

- Type: Pattern
- Status: Active
- Source: `.codex/skills/configure-dev-environment/scripts/configure_infra_tools.ps1 -Mode SetSeqAzureEventHubLogs`, error `Cannot add a member with the name "Title" because a member with that name already exists`
- Last verified: 2026-06-22

When updating the existing Seq alert `Agentic E2E - Any Seq Error Logs`, PowerShell objects returned by the Seq API may expose fields in a shape where `Add-Member` sees an existing member even if direct property-name checks missed it. Use `Add-Member -Force` in the shared `Set-JsonProperty` helper so repeated `SetSeqAzureEventHubLogs` runs update the alert idempotently instead of failing.

## DeliveryTools Package Workflow Test Has Stale Azure Script Expectation

- Type: Pattern
- Status: Active
- Source: `dotnet test tools/SDDTemplate.DeliveryTools.Tests/SDDTemplate.DeliveryTools.Tests.csproj --no-build`, `tools/SDDTemplate.DeliveryTools.Tests/DeploymentWorkflowTests.cs`
- Last verified: 2026-06-22

`DeploymentWorkflowTests.PackageWorkflowPublishesUploadsAndDeploysPerAppArtifacts` previously failed because it expected the package/deploy workflow text to contain `const apiBaseUrl`, but `.gitea/workflows/package-deploy.yml` now verifies the rendered clients page through `<title>Clients</title>` and `id="client-form"`. Keep the workflow generator, workflow, and tests synchronized when smoke-check criteria change.

## Windows Bash Shim Can Fail Without WSL Bash

- Type: Pattern
- Status: Active
- Source: `bash -n infra/rancher/deploy-local-lab.sh`, `Get-Command bash`, `C:\Program Files\Git\bin\bash.exe -n infra/rancher/capture-observability.sh`
- Last verified: 2026-06-22

On this workstation, `bash` resolves to `C:\WINDOWS\system32\bash.exe` and can fail with `execvpe(/bin/bash) failed: No such file or directory` when WSL has no usable `/bin/bash`. For shell syntax validation, call Git Bash directly at `C:\Program Files\Git\bin\bash.exe` when present.

## Ticket Readiness Helper Lives In DeliveryTools CLI

- Type: Pattern
- Status: Active
- Source: `tools/SDDTemplate.DeliveryTools/Program.cs`, `.codex/skills/_shared/scripts/delivery_tools.ps1 -Mode ClassifyTicketReadiness` failure
- Last verified: 2026-06-19

`ClassifyTicketReadiness` is exposed by the .NET delivery helper CLI, not by `.codex/skills/_shared/scripts/delivery_tools.ps1` on this checkout. If the shared script rejects `-Mode ClassifyTicketReadiness`, run `dotnet run --project tools/SDDTemplate.DeliveryTools -- ClassifyTicketReadiness --title <title> --description <description>` and keep ticket text out of command logs when it contains sensitive details.

## Stop Local Site Server Before Rebuilding

- Type: Pattern
- Status: Active
- Source: `dotnet build .\SDDTemplate.slnx` failure while `dotnet run --project src/SDDTemplate.Site --urls http://127.0.0.1:5098` was active
- Last verified: 2026-06-19

On Windows, a running local `SDDTemplate.Site.exe` from `dotnet run` can lock `src/SDDTemplate.Site/bin/Debug/net10.0/SDDTemplate.Site.exe` and make `dotnet build` fail with `MSB3027` / `MSB3021`. Stop only the local dev-server processes for the test URL, then run `dotnet build-server shutdown` before retrying build or test gates.

## OpenSpec Verification Is Manual In This Checkout

- Type: Pattern
- Status: Active
- Source: `openspec verify feat-e2eproject-8-improve-home-page` returned `unknown command`
- Last verified: 2026-06-19

The installed OpenSpec CLI does not expose an `openspec verify` command. For `dev-flow-verify-change`, use the skill workflow directly: run `openspec status --change <name> --json`, run `openspec instructions apply --change <name> --json`, read the listed artifacts, then manually verify completeness, correctness, and coherence against code/tests.

## OpenSpec CLI Telemetry Can Slow List And Status

- Type: Pattern
- Status: Active
- Source: `openspec list --json`, `openspec status --change feat-e2eproject-6-improve-logging --json`, `OPENSPEC_TELEMETRY=0`
- Last verified: 2026-06-17

The global `@fission-ai/openspec` CLI initializes PostHog telemetry before commands. On this workstation, `openspec list --json` and `openspec status --change ... --json` can take 5-8 seconds or time out under short automation limits when telemetry is enabled. Set user or process environment variable `OPENSPEC_TELEMETRY=0` before running OpenSpec automation; this reduced both commands to roughly 1.3-2.3 seconds in live verification.

## Ambiguous Ticket Or Stale Lock

- Type: Pattern
- Status: Active
- Source: `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-06-09

If a child skill resolves a ticket key that differs from `.codex/delivery-context.local.json`, stop and report the mismatch. Do not deploy, test, move state, tag, or comment the other ticket. `dev-flow-start-ticket` is the only lazy cleanup path: when starting another ticket, it may replace a different existing lock only after the locked Plane ticket is verified in the configured Done state. Active, missing, ambiguous, or unverifiable locks still block.

## Deployment Lane Conflict

- Type: Pattern
- Status: Active
- Source: `.codex/skills/_shared/delivery-contract.md`, `docs/architecture.md`
- Last verified: 2026-05-29

DEV, QA, E2E QA, PROD, rollback, and hotfix stages are serialized. If `.codex/parallel-delivery.local.json` records another deployment-lane owner, report the owner and wait rather than mutating shared deployment state.

## Blocking PR Labels

- Type: Pattern
- Status: Active
- Source: `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-05-29

QA promotion must stop when a merged PR still has `needs-tests` or `needs-changes`.

## Conflicting Release Manifest Or Tags

- Type: Pattern
- Status: Active
- Source: `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-05-29

Stop when release manifest fields conflict with Plane comments or tags. Validate `release.json` against `.codex/skills/_shared/release.schema.json` when reading or writing it.

## Nexus Unavailable

- Type: Pattern
- Status: Active
- Source: `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-05-29

Nexus is mandatory for DEV, QA, PROD, and rollback promotion. If Nexus is unavailable for promotion, stop instead of rebuilding locally or deploying from local files.

## PROD Promotion Must Resolve Artifact SHA From Main Merge Parent

- Type: Pattern
- Status: Active
- Source: current conversation, `.gitea/workflows/package-deploy.yml`
- Last verified: 2026-06-11

For `push` events on `main`, `GITHUB_SHA` is often the merge commit SHA, but Nexus artifacts are stored under the packaged commit SHA from the promoted branch. If PROD download steps use `app/${GITHUB_SHA}/...`, Nexus returns 404 for `deployable-apps.json`. Resolve the promotion artifact SHA from merge parent 2 (`$GITHUB_SHA^2`) when the commit has two parents, and fall back to `GITHUB_SHA` for non-merge pushes.

## Main Divergence

- Type: Pattern
- Status: Active
- Source: `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-05-29

Stop if `main` diverges from the intended QA-approved commit. Rollback does not rewrite `main`; after rollback, require a hotfix PR, revert PR, or explicit temporary divergence note with owner and expected resolution.

## Main Sync Requires PR Approval

- Type: Pattern
- Status: Active
- Source: Gitea PR #51 and `git push origin main` pre-receive rejection
- Last verified: 2026-06-18

Direct pushes to protected `main` are rejected with `Not allowed to push to protected branch main`. For `dev` to `main` syncs, push a `codex/...` branch, open a PR, wait for required status checks, and stop at `Does not have enough approvals` until a configured human approval is present.

## Secret Exposure Risk

- Type: Risk
- Status: Active
- Source: `README.md`, `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-05-29

Do not read secrets from Docker containers, mounted volumes, databases, logs, or committed files. Do not store secrets in memory. Tracked examples must remain placeholder-safe.

## Local Gitleaks No-Git Scans Hit Ignored Secret Files

- Type: Pattern
- Status: Active
- Source: `gitleaks detect --source . --redact --no-git --report-format json --report-path artifacts/gitleaks-report.local.json`
- Last verified: 2026-06-18

On this workstation, the configured local secret scan with `--no-git` scans ignored local files and reports redacted findings in `.codex/client-tools.local.json`, `infra/azure/variables.env`, `infra/gitea/runner.env`, `infra/monitoring/variables.env`, and `infra/plane/variables.env`. Treat this as local secret-bearing runtime state unless the findings reference tracked files. Do not print values. Use redacted metadata only, and keep any local report under ignored `artifacts/`.

## Compose Secret Fallbacks Can Bypass Local Env Values

- Type: Pattern
- Status: Active
- Source: current conversation, `infra/plane/compose.yml`, `infra/plane/variables.env.example`, `docker compose --env-file .\infra\plane\variables.env --env-file .\infra\monitoring\variables.env -f .\infra\compose.yml --project-directory .\infra config --quiet`
- Last verified: 2026-06-12

When hardening local infra Compose files, ensure service env interpolation uses the same variable names as the owning `variables.env.example` file and fail-fast `${VAR:?message}` checks for required secrets. A mismatch such as Compose reading `RABBITMQ_PASSWORD` while the template/local file defines `RABBITMQ_DEFAULT_PASS`, or URL defaults such as `postgresql://plane:plane@...`, can silently bypass generated local secrets. Validate changes with all required tool env files, such as `docker compose --env-file .\infra\plane\variables.env --env-file .\infra\monitoring\variables.env -f .\infra\compose.yml --project-directory .\infra config --quiet`, without printing secret values.

## Docker Compose Dotenv Values Need Escaped Dollar Signs

- Type: Pattern
- Status: Active
- Source: `infra/monitoring/variables.env.example`, `infra/monitoring/variables.env`, `docker compose --env-file .\infra\plane\variables.env --env-file .\infra\monitoring\variables.env -f .\infra\compose.yml --project-directory .\infra config --quiet`
- Last verified: 2026-06-16

Docker Compose interpolates dollar-prefixed dotenv values. Azure Event Hub consumer group values such as `$Default` must be written as `$$Default` in `infra/monitoring/variables.env` and `infra/monitoring/variables.env.example`; otherwise Compose warns that `Default` is unset and passes a blank value to the collector configuration. Validate both local and example env files with `docker compose ... config --quiet`.

## Grafana Health Alerts Need Scheduler-Aligned Blackbox Probes

- Type: Pattern
- Status: Active
- Source: `infra/monitoring/grafana/provisioning/alerting/health-alerts.yml`, `infra/monitoring/compose.yml`, `infra/monitoring/prometheus/prometheus.yml`, `infra/monitoring/prometheus/blackbox.yml`, `configure_infra_tools.ps1 -Mode Audit`
- Last verified: 2026-06-16

Grafana alert rule groups reject intervals below the local scheduler interval; use a 10-second health alert pending duration by default. Prometheus health checks need blackbox exporter to listen on `0.0.0.0:9115`; otherwise Prometheus may time out on `blackbox-exporter:9115` even though the host port responds. Keep blackbox timeout below Prometheus scrape timeout so failed or slow `/health` endpoints still return `probe_success` metrics.

## Full Test Suite Can Fail On Canonical Docs And Event Hub Template Drift

- Type: Pattern
- Status: Active
- Source: `dotnet test .\tools\SDDTemplate.DeliveryTools.Tests`, `tests/SDDTemplate.Site.Tests/ObservabilityLoggingTests.cs`, `tools/SDDTemplate.DeliveryTools.Tests/DeploymentWorkflowTests.cs`, `tools/SDDTemplate.DeliveryTools.Tests/DeliveryToolsTests.cs`
- Last verified: 2026-06-17

When unrelated code changes run the full suite, existing fixture drift can fail tests that assert README/canonical docs text and Event Hub collector template values. Current known failures include missing `OTELCOL_AZURE_EVENT_HUB_DEV_CONNECTION_STRING` in the expected env surface, missing `Azure Monitor` in architecture context, and missing README phrases such as `## Canonical Context` or `Before the first ticket starts`. The old `manual by default` recommendation wording is superseded by guarded-auto acquisition. Treat these as repository guidance/configuration drift, not product-code regressions, unless the current change touched those docs or env templates.

## Clean CI Lacks Ignored Grafana Dashboards Local Files

- Type: Pattern
- Status: Active
- Source: PR #33 Gitea Actions run 194, `tests/SDDTemplate.Site.Tests/ObservabilityLoggingTests.cs`, `.gitignore`
- Last verified: 2026-06-16

`infra/monitoring/grafana/dashboards.local/` is ignored local runtime state. Tests that assert Grafana dashboard provisioning can require the tracked provisioning path, but must not require generated dashboard JSON files to exist in clean Gitea Actions checkouts. If a CI run fails with `DirectoryNotFoundException` for `infra/monitoring/grafana/dashboards.local/dev-health-dashboard.json`, classify it as test/tooling drift and make the test conditional on the local file before treating product code as broken.

## Worktree Local Config Copy Can Leave Placeholders

- Type: Pattern
- Status: Active
- Source: current conversation, `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-06-02

When creating or reusing a ticket worktree, do not assume ignored local config files copied with real values. A copied `.codex/client-tools.local.json` or related local file may still contain placeholders if the copy process used tracked examples, an earlier placeholder source, or skipped sensitive values. Before running Plane, Gitea, Nexus, Azure, or quality-gate automation from a worktree, validate that required local config keys are present without printing secret values. If placeholders are found, repair the worktree local file from the approved original local config source and keep it ignored.

## Gitea Reviewers Must Be Repository Collaborators

- Type: Pattern
- Status: Superseded
- Source: current conversation, Gitea reviewer setup for user `robert`
- Last verified: 2026-06-08

Automatic PR reviewer assignment depends on Gitea users being repository collaborators. If a configured reviewer such as `robert` is not returned by `GET /api/v1/repos/{owner}/{repo}/collaborators`, reviewer assignment may fail or skip even when the username exists. Fix by adding the user as a collaborator in Gitea repository settings, then verify through the same collaborators API used by the source-control skill before retrying PR automation.

Superseded note: E2EPROJECT-4 showed `robert` was returned by the collaborators API, but the resolver treated a single-object response as empty. Use the active entry below.

## Normalize Gitea Collaborator Responses For All Reviewers

- Type: Pattern
- Status: Active
- Source: E2EPROJECT-4 PR #23 reviewer correction, Gitea collaborators API readback, `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-06-08

When `pr.reviewers` is `"all"`, normalize `GET /api/v1/repos/{owner}/{repo}/collaborators` before filtering because Gitea may return a JSON array or a single collaborator object. Resolve each reviewer username from `login` first and `username` second, then exclude the PR author and authenticated automation user. If reviewers are resolved but not shown in the PR response, call `POST /api/v1/repos/{owner}/{repo}/pulls/{prNumber}/requested_reviewers` and re-fetch the PR before moving Plane to review.

## Gitea Actions Runner May Lack Dotnet In Early Utility Jobs

- Type: Pattern
- Status: Active
- Source: current conversation, Gitea Actions classify-changes failure in run before PR 12
- Last verified: 2026-06-02

Early utility jobs such as changed-file classification should not assume `dotnet` exists on the runner unless the workflow step installs the SDK first. A classify script failed with `dotnet: command not found`; the durable fix was to avoid using `dotnet` for lightweight classification and keep the step runnable in the base Actions environment. Future workflow utility steps should use shell/JQ/simple scripts or install prerequisites explicitly.

## Pipefail Requires Bash In Gitea Actions Steps

- Type: Pattern
- Status: Active
- Source: current conversation, package/deploy shell execution failure fixed by PR 13
- Last verified: 2026-06-02

Gitea Actions steps that use Bash-only features such as `set -euo pipefail`, Bash arrays, or `BASH_REMATCH` must declare `shell: bash`. A package/deploy run failed when a script with `pipefail` ran under `sh`. When adding workflow scripts, align the shell declaration with the script syntax and add regression checks for critical topology/deploy steps.

## PowerShell Install Feed Must Match Container OS

- Type: Pattern
- Status: Active
- Source: Codex thread `019e858b-9e2b-7873-97e5-72693998f2d0`, PR validation workflow fix for E2EPROJECT-2
- Last verified: 2026-06-02

When installing PowerShell in Gitea Actions containers, derive the Microsoft package feed from `/etc/os-release` instead of assuming Debian. The .NET SDK container used by PR validation can be Ubuntu 24.04, and a hardcoded `packages.microsoft.com/config/debian/24.04/...` URL fails with 404. Keep the live workflow, configure template, workflow README, and regression tests synchronized when fixing this.

## Cross-Platform Test Harnesses Must Select Pwsh Or Powershell

- Type: Pattern
- Status: Active
- Source: Codex thread `019e858b-9e2b-7873-97e5-72693998f2d0`, delivery-tool test harness fix
- Last verified: 2026-06-02

Delivery-tool tests that invoke PowerShell must select `pwsh` on non-Windows and `powershell` on Windows, or otherwise detect the executable before running subprocess tests. A Linux Gitea runner failed because one helper path still hardcoded `powershell`. Apply the same executable-selection helper to success and expected-failure subprocess paths.

## Coverage Gates Should Exclude Generated And Adapter Boundaries

- Type: Pattern
- Status: Active
- Source: Codex thread `019e858b-9e2b-7873-97e5-72693998f2d0`, E2EPROJECT-2 coverage repair
- Last verified: 2026-06-02

When coverage fails because generated EF migration files or CLI adapter entrypoints are counted at 0%, prefer targeted `ExcludeFromCodeCoverage` on generated/adapter boundaries rather than adding shallow tests. Confirm the underlying behavior is covered through meaningful tests, then rerun coverage threshold checks from fresh Cobertura reports.

## Stale TestResults Can Spoof Coverage Failures

- Type: Pattern
- Status: Active
- Source: E2EPROJECT-3 implementation, `dotnet test -c Release --no-build --logger trx --collect:"XPlat Code Coverage"` and coverage threshold check
- Last verified: 2026-06-05

Ignored `TestResults/` directories can retain older `coverage.cobertura.xml` files. A local threshold script that scans all Cobertura files may fail because stale reports are below the current threshold even when the latest run passes. Before enforcing local coverage from file discovery, remove ignored `tests/**/TestResults` and `tools/**/TestResults` directories or filter to the current run's report paths, then rerun tests with coverage and threshold parsing.

## Windows Line Endings Can Create Noisy Status Without Meaningful Diff

- Type: Pattern
- Status: Active
- Source: Codex thread `019e858b-9e2b-7873-97e5-72693998f2d0`, line-ending cleanup during E2EPROJECT-2 validation
- Last verified: 2026-06-02

On Windows checkouts with `core.autocrlf`, patching can create mixed LF/CRLF files or status noise with little or no content diff. Normalize only touched files, inspect staged diffs before committing, avoid sweeping unrelated repo-wide line endings, and report residual formatter failures when they are pre-existing checkout-wide newline issues.

## Git May Be Installed But Missing From Codex Shell Path

- Type: Pattern
- Status: Active
- Source: Codex thread `019e83a6-433d-7fa2-8ff0-852d74d2eb21`, local Git PATH repair
- Last verified: 2026-06-02

If `git` is unavailable in a Codex PowerShell session, first check whether Git is installed under `C:\Program Files\Git\cmd\git.exe`. Adding that directory to the user PATH helps future terminals but not necessarily the current Codex shell. For immediate use, prefer an approved executable directory already on the session PATH; avoid leaving broken script or batch shims that shadow real Git when the host blocks execution.

## Ticket Branch Merge Messages Must Satisfy Hooks

- Type: Pattern
- Status: Active
- Source: Codex thread `019e83a6-433d-7fa2-8ff0-852d74d2eb21`, merge of `dev` into E2EPROJECT-2 branch
- Last verified: 2026-06-02

When merging `dev` into a ticket feature branch, Git's generated merge message can fail the commit-message hook. Complete the merge with a ticket-prefixed message such as `E2EPROJECT-2: merge dev updates into feature` so hooks and deployment gating recognize the commit correctly.

## Direct SDD Maintenance Commits Need `[SDD]` Prefix

- Type: Pattern
- Status: Active
- Source: repeated local commit hook failures, latest during project guidance acquisition flow commit
- Last verified: 2026-06-17

When committing direct repository maintenance that is not tied to a Plane ticket or OpenSpec change, start the commit message with `[SDD]`, for example `[SDD] Improve project guidance acquisition flow`. The `.githooks/require-ticket.ps1` commit-msg hook rejects ordinary messages that do not start with a configured ticket key, an OpenSpec id, or `[SDD]`. Before running `git commit` in this repository, classify the work as ticketed, OpenSpec, or direct SDD maintenance and choose the prefix first.

## Timed-Out Playwright Installs Can Leave A Cache Lock

- Type: Pattern
- Status: Active
- Source: current conversation, local validation while adding Gitea-run QA E2E automation
- Last verified: 2026-06-03

If `npx playwright install` or `npm run install:browsers` times out locally, later Playwright commands may fail with an active lockfile at `%LOCALAPPDATA%\ms-playwright\__dirlock`. Before removing the lock, check for live `node.exe` processes whose command line still references Playwright install or download. Stop only those stale installer processes, then remove the lock. In this repository, official QA E2E should run remotely through Gitea against deployed QA apps; local Playwright execution is only for authoring diagnostics.

## Docker Backend Timeout Blocks Gitea Actions Image Validation

- Type: Pattern
- Status: Active
- Source: current conversation, `BuildGiteaActionsImages` while adding repo-owned Gitea Actions images
- Last verified: 2026-06-09

When Docker Desktop is installed but its backend is unhealthy, `docker version`, `docker image inspect`, or `docker build` can fail with `failed to connect to the backend: timed out dialing Hyper-V socket`. Treat this as a live Docker blocker, not a workflow or Dockerfile failure. `configure_infra_tools.ps1` must check `$LASTEXITCODE` after native `docker` commands because PowerShell may otherwise continue and report false success. After Docker Desktop is restarted or repaired, rerun `BuildGiteaActionsImages` and then `ValidateGiteaActionsRunner`.

## PowerShell Json Timestamps Need Explicit Formatting

- Type: Pattern
- Status: Active
- Source: PR 16 CI failure in `RenderPlaneCommentRendersWorkflowTimingTable`, `.codex/skills/_shared/scripts/delivery_tools.ps1`
- Last verified: 2026-06-03

PowerShell `ConvertFrom-Json` can coerce ISO timestamp strings into `DateTime` values, and later string interpolation renders them with the host culture instead of the original `yyyy-MM-ddTHH:mm:ssZ` form. For Plane comments, workflow timing tables, or tests that assert exact UTC text, format timestamp values explicitly with invariant UTC formatting before interpolation. Reproduce failures with the CI-shaped command `dotnet test .\SDDTemplate.slnx -c Release --no-build --logger trx --collect:"XPlat Code Coverage"`.

## Missing Workflow Timing Comments Need Ticket Telemetry Initialization

- Type: Pattern
- Status: Active
- Source: E2EPROJECT-3 and E2EPROJECT-4 Done tickets missing `IA generated workflow timing` comments while other generated Plane markers existed
- Last verified: 2026-06-09

When `.codex/agent-telemetry.local.jsonl` is absent or a delivery run missed telemetry writes, treat that as a workflow instrumentation failure. Initialize or clear telemetry at selected ticket start with `InitializeWorkflowTelemetry`, append stage rows with `AppendWorkflowTelemetry`, read active ticket rows with `ReadWorkflowTelemetry`, then render `IA generated workflow timing: {ticketKey}` with `RenderPlaneComment -Type WorkflowTiming`. Do not derive workflow timing from generated Plane marker timestamps. Verify the posted comment by reading Plane comments back and matching the timing marker.

## Noncanonical QA Evidence Marker Bypasses Timing Finalization

- Type: Pattern
- Status: Active
- Source: E2EPROJECT-6 Plane comments and `.codex/agent-telemetry.local.jsonl`
- Last verified: 2026-06-12

If a ticket is moved to Done after a Gitea QA evidence run using a noncanonical marker such as `IA generated QA evidence: {ticketKey}` instead of the `quality-test-e2e` marker `IA generated E2E QA: {ticketKey}`, the `quality-test-e2e` finalization path may never append a `quality-test-e2e` telemetry row or post `IA generated workflow timing: {ticketKey}`. Treat Done state plus QA evidence marker as insufficient; rerun or repair through `quality-test-e2e` so the canonical E2E QA marker, workflow timing comment, and telemetry row are verified.

## Azure Event Hubs Kafka 9093 EOF Can Be Network-Side

- Type: Pattern
- Status: Active
- Source: current conversation, Grafana Alloy Azure Event Hubs log ingestion setup
- Last verified: 2026-06-10

When Alloy `loki.source.azure_event_hubs` reports `kafka: client has run out of available brokers to talk to: EOF`, first verify the Event Hubs namespace is Standard or higher, Kafka is enabled, the listen rule is scoped correctly, and local env values are present without printing secrets. If those checks pass but `SslStream` or `kcat` to `<namespace>.servicebus.windows.net:9093` fails with connection reset or TLS handshake failure, treat it as a Kafka/TLS 9093 network or service endpoint blocker before changing repository configuration. Retry from a stable network or validate firewall/proxy rules for Event Hubs Kafka port 9093.

## Azure App Service Smoke Can Beat Warm-Up

- Type: Pattern
- Status: Active
- Source: E2EPROJECT-7 package/deploy run 204, DEV deploy succeeded but immediate smoke failed; fresh DEV `/health` checks passed shortly after.
- Last verified: 2026-06-16

When `az webapp deploy` reports `RuntimeSuccessful` but the immediate page, CORS, or `/health` smoke check fails, re-check live DEV/QA targets after a short delay before changing app code. If live checks pass, treat it as Azure App Service warm-up tolerance and add bounded retry/backoff to the workflow smoke checks. Keep `.gitea/workflows/package-deploy.yml` and the `configure_infra_tools.ps1` workflow generator synchronized.

## Docker MCP Toolkit Requires Docker MCP CLI Support

- Type: Pattern
- Status: Active
- Source: project guidance MCP install pass
- Last verified: 2026-06-17

Docker MCP Toolkit cannot be enabled through plain Docker CLI when `docker mcp` is unavailable. On this workstation, `docker --version` reports Rancher Desktop `29.1.4-rd`, and `docker mcp` falls back to generic Docker help with no MCP subcommand. Treat Docker MCP Toolkit as blocked until Docker Desktop or another Docker distribution exposes the official Docker MCP catalog/toolkit commands. Do not add a broken Codex MCP entry that calls `docker mcp ...`; keep the recommendation status as blocked and report one Codex restart only for MCPs that were actually configured.

## Parallel Dotnet Gates Can Lock Build Outputs

- Type: Pattern
- Status: Active
- Source: current project-profile generalization validation, parallel `dotnet build`, `dotnet test`, and `dotnet format` run
- Last verified: 2026-06-18

Do not run repo-wide `dotnet build`, `dotnet test`, and `dotnet format` concurrently in this repository on Windows. Parallel execution can leave MSBuild/VSTest processes holding `obj/**` or `bin/**` assemblies, causing `CS2012` file-lock failures such as `Cannot open ... for writing` and sometimes implicating Microsoft Defender. Run .NET quality gates sequentially. If a run is interrupted or times out, inspect live `dotnet.exe` command lines, stop only stale `vstest.console.dll` test runners, then run `dotnet build-server shutdown` before retrying.

## Package Updates Need Release Deps Refresh Before Trivy

- Type: Pattern
- Status: Active
- Source: package update validation, `dotnet list .\SDDTemplate.slnx package --vulnerable --include-transitive`, `trivy fs --scanners vuln,secret --exit-code 1 --severity HIGH,CRITICAL .`, `dotnet build .\SDDTemplate.slnx -c Release --no-restore`
- Last verified: 2026-06-18

After NuGet package updates, `dotnet list package --vulnerable --include-transitive` can be clean while Trivy still reports vulnerabilities from stale generated `bin/Release/**/*.deps.json` files. Rebuild Release with `dotnet build .\SDDTemplate.slnx -c Release --no-restore` before rerunning Trivy, or clean ignored build outputs if a full rebuild is not needed. Do not treat stale Release deps findings as unresolved package graph drift until the generated deps files are refreshed.

## Root Page Title Is A Deployment Smoke Contract

- Type: Pattern
- Status: Active
- Source: E2EPROJECT-8 Gitea Actions run 268, DEV smoke check after PR 53 merge
- Last verified: 2026-06-19

The package/deploy workflow checks the deployed web root for `<title>SDD Template</title>`. A visible homepage rebrand can keep the app healthy while still failing DEV smoke if `Home.razor` changes the root `PageTitle`. Preserve that title or update `.gitea/workflows/package-deploy.yml` and its generator/tests together before merging homepage changes.

## QA Branch E2E Image Needs Jq Before Artifact Resolution

- Type: Pattern
- Status: Active
- Source: E2EPROJECT-8 Gitea Actions run 272, `e2e-qa` job
- Last verified: 2026-06-19

The QA branch `e2e-qa` job resolves the ticket key with `jq -r '.workflow.ticketKeyPattern // empty' .codex/project-profile.json` before running `npm ci`. If `agentic/e2e-ci:playwright-1.57.0-1` lacks `jq`, the job fails with `line 8: jq: command not found` before any browser tests execute. Classify this as workflow image/tooling failure, not product QA failure. Use local `npm run test:docker` or repair the image/workflow before treating QA branch evidence as authoritative.

## Landing CTAs Can Collide With Broad E2E Link Locators

- Type: Pattern
- Status: Active
- Source: E2EPROJECT-8 local Docker E2E run after landing page deployment
- Last verified: 2026-06-19

When a landing page adds CTA links like `View products`, Playwright locators such as `getByRole("link", { name: "Products" })` can match both the navigation link and CTA because accessible-name matching is substring-based by default. Use `exact: true` for navigation links whose text also appears inside longer CTA labels.
