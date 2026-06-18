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
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode InitProjectProfile
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode InitQualityGateTemplates
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode SetQualityConfig -ValuesJson '{"coverage":{"minimumPercent":80}}'
```

If local Trivy scans report a stale vulnerability database, refresh it before scanning:

```powershell
trivy --download-db-only
```

## Strategy

- Gitea PR validation is the source of truth for formatting, build, tests, coverage, dependency audit, full secret scanning, and filesystem security scanning.
- Local validation is for fast feedback and test authoring: run targeted builds/tests for touched behavior and cheap checks such as staged secret scanning, then let PR validation run the full required gate in the pinned runner.
- Repo-owned Gitea Actions images are the source of reusable CI tooling. Use `BuildGiteaActionsImages` during `config infra` to build `agentic/dotnet-ci:10.0.300-tools-1` and `agentic/e2e-ci:playwright-1.57.0-1` into the Docker daemon used by the runner.
- `.codex/project-profile.json` and selected provider adapter files are initialized by `InitProjectProfile`, which must run before full `config infra` quality/provider setup.
- `.codex/project-profile.json` must include `workflow.ticketKeyPattern` for deployment gating.
- `.codex/delivery-policy.json` must include `agentOptimization` defaults for retry limits, prompt-cache ordering, telemetry output, and workflow eval paths.
- Coverage threshold is configurable through `.codex/quality.local.json`; default to `coverage.minimumPercent = 80`.
- Gitea Actions should fall back to `.codex/quality.example.json` when local config is absent.
- `.gitattributes` must force text files to LF with `* text=auto eol=lf` so Windows `core.autocrlf=true` checkouts do not break `.editorconfig` `end_of_line = lf` or `dotnet format --verify-no-changes`.
- Local Git hooks are convenience checks only.
- Do not configure default pre-push restore/build/test/security scans.
- Do not require agents to duplicate the full PR validation suite locally before opening or updating a PR unless the ticket or risk explicitly asks for it.
- Do not write scanner, Gitea, Nexus, or Azure secrets into tracked files.

## Local Hooks

Use Lefthook by default:

- `pre-commit`: `gitleaks protect --staged --redact`.
- `commit-msg`: require a ticket or OpenSpec id such as `E2EPROJECT-1: scaffold blank Blazor site`.
- Optional staged formatting checks are acceptable only when fast and scoped.

## PR Validation

Use the pinned repo-owned .NET 10 runner image that has been validated on the local runner: `agentic/dotnet-ci:10.0.300-tools-1`.

PR validation runs only for pull request changes under `src/**`, `tests/**`, or root app build inputs: `.editorconfig`, `Directory.Build.props`, `Directory.Build.targets`, `Directory.Packages.props`, `global.json`, `NuGet.config`, `SDDTemplate.slnx`, and `dotnet-tools.json`. Agent skills, workflow files, OpenSpec, infrastructure, docs, delivery tools, and other meta/template-maintenance changes skip normal app PR CI.

CI restore, format, build, test, coverage, dependency-audit, and publish commands must target product/application projects specifically. Do not include SDD template, delivery-tool, workflow, agent, OpenSpec, infrastructure, or meta-test projects in normal PR CI for downstream applications. Keep those tests as local/template-maintenance checks unless a repository explicitly owns them as application behavior.

Downstream projects must define explicit application project, application test project, and deployable application publish sets instead of using full-template solution commands. Small SDD helper tools may run only when needed for workflow metadata; they must not be treated as application compile, test, coverage, dependency-audit, or publish targets.

When a workflow uses a job `container:`, keep the image pinned and locally buildable. Prefer the repo-owned images under `infra/gitea/actions-images/` so workflows do not reinstall common tools every run:

- `agentic/dotnet-ci:10.0.300-tools-1`: .NET SDK 10, git, curl, tar, jq, zip, Gitleaks, Trivy, Azure CLI, Node/npm for JavaScript `uses:` actions.
- `agentic/e2e-ci:playwright-1.57.0-1`: Node/Playwright runtime, browser dependencies, git, curl, and zip.
- Shell checkout still rewrites local Gitea hostnames (`localhost` and `gitea`) to `host.docker.internal`.

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

Merge and deployment jobs should not rerun the same unit test suite that PR validation already ran for the reviewed commit. They should focus on immutable artifact packaging, deployment configuration verification, checksum validation, and environment smoke checks unless package or artifact inputs changed outside the PR validation path.

Run `BuildGiteaActionsImages` after changing image Dockerfiles, tool versions, or workflow image tags. Then run `ValidateGiteaActionsRunner`; it validates Docker availability, local image presence, required tools inside each image, and that the PR validation job image can reach the repository origin through `host.docker.internal`.

Semgrep is optional. Default to skipping it until the first real application code exists.

## Branch Protection

Ask the user to configure Gitea branch protection:

- Block direct pushes to `dev` and `main`.
- Require pull requests into `dev`.
- Update `main` only after QA passes, preferably by fast-forwarding the tested commit.
- Require the PR validation workflow to pass.
- Require coverage to meet the configured threshold.
- Require the exact emitted PR validation status context: `PR validation / validate (pull_request)`.
- Require `pr.minimumApprovals.dev/main` review approval(s), default `1` per branch, or the configured review label.
- Block merge while `needs-changes` is present.

## Deployment Gating

Push-triggered deployments are gated by `.codex/project-profile.json` `workflow.ticketKeyPattern` and changed paths. The workflow deploys only when the commit message or merged PR title starts with that ticket key and the change touches `src/**` or `tests/**`. `.codex/delivery-policy.json` carries `agentOptimization` defaults used by delivery agents when the platform exposes retry, prompt-cache, telemetry, or eval data. Non-code changes outside `src/**` and `tests/**` skip automatic CI/deployment work.

DEV and QA deploy only from `dev` when application/test/package source changed. PROD deploys only from `main` when `main` points to the exact QA-approved packaged commit for the same ticket-gated application change and `app/qa-approved/latest.json` points to that same commit. Manual workflow dispatch remains available for explicit promotion with `artifact_commit_sha`.

E2E QA is an acceptance-evidence gate. Implementation records browser E2E expectations and lower-level regression coverage, but Playwright E2E creation, repair, execution, evidence, and QA pass/fail classification are owned by `quality-test-e2e` unless the user, Plane ticket, or OpenSpec artifacts explicitly make implementation-owned E2E part of the PR scope. After QA deployment, `quality-test-e2e` uses the temporary `qa/{ticketKey}` branch to run existing committed tests and create or repair reusable E2E tests when current coverage cannot prove acceptance. During QA, one-off exploratory scripts and generated probes stay under ignored `artifacts/qa/**` and are evidence, not committed regression coverage. For deployed browser E2E failures, Playwright MCP or the configured Browser/Playwright tool is the first diagnostic source before source-code changes; classify the failure as product defect, E2E harness issue, deployment/environment issue, or workflow gate gap. Local diagnostics should use `npm run test:docker` in `tests/SDDTemplate.E2ETests` and the pinned `agentic/e2e-ci:playwright-1.57.0-1` image rather than host browser installs. App code must remain product-only and must not receive E2E-only JavaScript helpers, hidden hooks, test ids, bypasses, timing shims, or Playwright-specific behavior. `quality-test-e2e` may move a Plane ticket to Done only when the deployed QA artifact receives a full `PASS`: ticket acceptance criteria are mapped to executable assertions, relevant user workflow/API/backend/state/validation/error/environment/evidence-integrity scenarios are covered, and screenshots or smoke checks support rather than replace assertions. `PASS WITH GAPS` and `FAIL` must remain in QA.

## Release Branching

Use this release path:

```text
feature branch -> dev -> DEV -> QA -> main -> PROD
```

The package/deploy workflow should build and publish from ticket-gated application changes on `dev`, including one ZIP per app in `infra/deployment/apps.json`, `deployable-apps.json`, and a baseline `app/{commitSha}/release.json`. DEV and QA deployments must download the same Nexus topology artifacts for the same commit SHA and pass page plus all app `/health` checks. PROD must reuse the QA-passed artifact commit after `main` is fast-forwarded to that exact commit or explicit dispatch is requested; main-push PROD resolves through `app/qa-approved/latest.json`, while dispatch promotions use `artifact_commit_sha`, `release_version`, and `source_rc_version`. PROD must not rebuild and must pass page plus all app `/health` checks before success is recorded. E2E QA `PASS` closes tickets as Done, while PROD is an explicit release event that may include one or more Done tickets through `release.json.includedTickets`. Release automation should update `app/{commitSha}/release.json` instead of renaming ZIP artifacts, publish human-readable pointer aliases under `app/rc/{sourceRcVersion}/` and `app/releases/{finalReleaseVersion}/`, and comment the PROD result on every included ticket. After PROD success, `dev-ops-deploy-prod` should run a read-only post-PROD retrospective and store sanitized learning evidence in ignored `.codex/agent-evals/results.local.json`; this audit evidence must not change deployment outcome or mutate delivery state.
