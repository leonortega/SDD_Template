# Quality Gates Configuration

Owns:

- `.codex/delivery-policy.json`
- `global.json`
- `.editorconfig`
- `Directory.Build.props`
- `.codex/quality.example.json`
- `.codex/quality.local.json`
- `lefthook.yml`
- `.gitea/workflows/pr-validation.yml`
- `.gitea/workflows/README.md`

Use the shared script:

```powershell
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode AuditQualityGates
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode ValidateGiteaActionsRunner
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode InitQualityGateTemplates
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode SetQualityConfig -ValuesJson '{"coverage":{"minimumPercent":80}}'
```

## Strategy

- Gitea PR validation is the source of truth for formatting, build, tests, coverage, dependency audit, full secret scanning, and filesystem security scanning.
- `.codex/delivery-policy.json` must include both `ticketKeyPattern` for deployment gating and `agentOptimization` defaults for retry limits, prompt-cache ordering, telemetry output, and workflow eval paths.
- Coverage threshold is configurable through `.codex/quality.local.json`; default to `coverage.minimumPercent = 80`.
- Gitea Actions should fall back to `.codex/quality.example.json` when local config is absent.
- `.gitattributes` must force text files to LF with `* text=auto eol=lf` so Windows `core.autocrlf=true` checkouts do not break `.editorconfig` `end_of_line = lf` or `dotnet format --verify-no-changes`.
- Local Git hooks are convenience checks only.
- Do not configure default pre-push restore/build/test/security scans.
- Do not write scanner, Gitea, Nexus, or Azure secrets into tracked files.

## Local Hooks

Use Lefthook by default:

- `pre-commit`: `gitleaks protect --staged --redact`.
- `commit-msg`: require a ticket or OpenSpec id such as `E2EPROJECT-1: scaffold blank Blazor site`.
- Optional staged formatting checks are acceptable only when fast and scoped.

## PR Validation

Use a pinned .NET 10 SDK runner image that has been validated on the local runner, for example `mcr.microsoft.com/dotnet/sdk:10.0.300`.

PR validation runs only for pull request changes under `src/**` or `tests/**`. Non-code PRs outside those folders skip automatic CI.

CI restore, format, build, test, coverage, dependency-audit, and publish commands must target product/application projects specifically. Do not include SDD template, delivery-tool, workflow, agent, OpenSpec, infrastructure, or meta-test projects in normal PR CI for downstream applications. Keep those tests as local/template-maintenance checks unless a repository explicitly owns them as application behavior.

Downstream projects must define explicit application project, application test project, and deployable application publish sets instead of using full-template solution commands. Small SDD helper tools may run only when needed for workflow metadata; they must not be treated as application compile, test, coverage, dependency-audit, or publish targets.

When a workflow uses a job `container:` based on the .NET SDK image, avoid JavaScript-based `uses:` actions inside that job unless the container also includes `node`. Prefer shell steps for checkout and scanner execution:

- Shell checkout that rewrites local Gitea hostnames (`localhost` and `gitea`) to `host.docker.internal`.
- Pinned Gitleaks release archive installation.
- Shell Trivy installation and `trivy fs` execution.

Required checks:

- application project restore, for this template: `dotnet restore "$project"` over `src/SDDTemplate.Site`, `src/SDDTemplate.Api`, and `tests/SDDTemplate.Site.Tests`
- application project formatting, for this template: `dotnet format "$project" --verify-no-changes --no-restore` over the same explicit project set
- application project build, for this template: `dotnet build "$project" -c Release --no-restore` over the same explicit project set
- application test command, for this template: `dotnet test tests/SDDTemplate.Site.Tests/SDDTemplate.Site.Tests.csproj -c Release --no-build`
- coverage collection/reporting
- coverage threshold enforcement using configured `coverage.minimumPercent`
- application dependency audit, for this template: `dotnet list "$project" package --vulnerable --include-transitive` over the same explicit project set
- full Gitleaks scan
- Trivy filesystem scan

Run `ValidateGiteaActionsRunner` after changing workflow container images or checkout/scanner setup. It validates Docker availability, pulls the configured PR validation image, checks required tools inside the image, and verifies the job container can reach the repository origin through `host.docker.internal`.

Semgrep is optional. Default to skipping it until the first real application code exists.

## Branch Protection

Ask the user to configure Gitea branch protection:

- Block direct pushes to `dev` and `main`.
- Require pull requests into `dev`.
- Update `main` only after QA passes, preferably by fast-forwarding the tested commit.
- Require the PR validation workflow to pass.
- Require coverage to meet the configured threshold.
- Require the exact emitted PR validation status context: `PR validation / validate (pull_request)`.
- Require review approval or the configured review label.
- Block merge while `needs-changes` is present.

## Deployment Gating

Push-triggered deployments are gated by `.codex/delivery-policy.json` and changed paths. The workflow reads `ticketKeyPattern` and deploys only when the commit message or merged PR title starts with that ticket key and the change touches `src/**` or `tests/**`. The same policy file carries `agentOptimization` defaults used by delivery agents when the platform exposes retry, prompt-cache, telemetry, or eval data. Non-code changes outside `src/**` and `tests/**` skip automatic CI/deployment work.

DEV and QA deploy only from `dev` when application/test/package source changed. PROD deploys only from `main` when `main` points to the exact QA-approved packaged commit for the same ticket-gated application change. Manual workflow dispatch remains available for explicit promotion with `artifact_commit_sha`.

E2E QA is an acceptance-evidence gate. `test-e2e` may move a Plane ticket to Done only when the deployed QA artifact receives a full `PASS`: ticket acceptance criteria are mapped to executable assertions, relevant user workflow/API/backend/state/validation/error/environment/evidence-integrity scenarios are covered, and screenshots or smoke checks support rather than replace assertions. `PASS WITH GAPS` and `FAIL` must remain in QA.

## Release Branching

Use this release path:

```text
feature branch -> dev -> DEV -> QA -> main -> PROD
```

The package/deploy workflow should build and publish from ticket-gated application changes on `dev`, including one ZIP per app in `infra/deployment/apps.json`, `deployable-apps.json`, and a baseline `app/{commitSha}/release.json`. DEV and QA deployments must download the same Nexus topology artifacts for the same commit SHA and pass page plus all app `/health` checks. PROD must reuse the QA-passed artifact commit after `main` is fast-forwarded to that exact commit or explicit dispatch is requested, using `artifact_commit_sha`, `release_version`, and `source_rc_version` for dispatch promotions; PROD must not rebuild and must pass page plus all app `/health` checks before success is recorded. Release automation should update `app/{commitSha}/release.json` instead of renaming ZIP artifacts. After PROD success, `deploy-to-prod` should run a read-only post-PROD retrospective and store sanitized learning evidence in ignored `.codex/agent-evals/results.local.json`; this audit evidence must not change deployment outcome or mutate delivery state.
