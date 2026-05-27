# Quality Gates Configuration

Owns:

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
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode InitQualityGateTemplates
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode SetQualityConfig -ValuesJson '{"coverage":{"minimumPercent":80}}'
```

## Strategy

- Gitea PR validation is the source of truth for formatting, build, tests, coverage, dependency audit, full secret scanning, and filesystem security scanning.
- Coverage threshold is configurable through `.codex/quality.local.json`; default to `coverage.minimumPercent = 80`.
- Gitea Actions should fall back to `.codex/quality.example.json` when local config is absent.
- Local Git hooks are convenience checks only.
- Do not configure default pre-push restore/build/test/security scans.
- Do not write scanner, Gitea, Nexus, or Azure secrets into tracked files.

## Local Hooks

Use Lefthook by default:

- `pre-commit`: `gitleaks protect --staged --redact`.
- `commit-msg`: require a ticket or OpenSpec id such as `E2EPROJECT-1: scaffold blank Blazor site`.
- Optional staged formatting checks are acceptable only when fast and scoped.

## PR Validation

Use a .NET 10 SDK runner image, for example `mcr.microsoft.com/dotnet/sdk:10.0`.

Required checks:

- `dotnet restore`
- `dotnet format --verify-no-changes --no-restore`
- `dotnet build -c Release --no-restore`
- `dotnet test -c Release --no-build`
- coverage collection/reporting
- coverage threshold enforcement using configured `coverage.minimumPercent`
- `dotnet list package --vulnerable --include-transitive`
- full Gitleaks scan
- Trivy filesystem scan

Semgrep is optional. Default to skipping it until the first real application code exists.

## Branch Protection

Ask the user to configure Gitea branch protection:

- Block direct pushes to `dev` and `main`.
- Require pull requests into `dev`.
- Update `main` only after QA passes, preferably by fast-forwarding the tested commit.
- Require the PR validation workflow to pass.
- Require coverage to meet the configured threshold.
- Require review approval or the configured review label.
- Block merge while `needs-changes` is present.

## Release Branching

Use this release path:

```text
feature branch -> dev -> DEV -> QA -> main -> PROD
```

The package/deploy workflow should build and publish from `dev`. DEV and QA deployments must download the same Nexus ZIP for the same commit SHA. PROD must reuse the QA-passed artifact commit after `main` is updated.
