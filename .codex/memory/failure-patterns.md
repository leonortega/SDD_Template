# Failure Pattern Memory

## Ambiguous Ticket Or Stale Lock

- Type: Pattern
- Status: Active
- Source: `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-06-09

If a child skill resolves a ticket key that differs from `.codex/delivery-context.local.json`, stop and report the mismatch. Do not deploy, test, move state, tag, or comment the other ticket. `plane-start-ticket` is the only lazy cleanup path: when starting another ticket, it may replace a different existing lock only after the locked Plane ticket is verified in the configured Done state. Active, missing, ambiguous, or unverifiable locks still block.

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

## Main Divergence

- Type: Pattern
- Status: Active
- Source: `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-05-29

Stop if `main` diverges from the intended QA-approved commit. Rollback does not rewrite `main`; after rollback, require a hotfix PR, revert PR, or explicit temporary divergence note with owner and expected resolution.

## Secret Exposure Risk

- Type: Risk
- Status: Active
- Source: `README.md`, `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-05-29

Do not read secrets from Docker containers, mounted volumes, databases, logs, or committed files. Do not store secrets in memory. Tracked examples must remain placeholder-safe.

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

## Timed-Out Playwright Installs Can Leave A Cache Lock

- Type: Pattern
- Status: Active
- Source: current conversation, local validation while adding Gitea-run QA E2E automation
- Last verified: 2026-06-03

If `npx playwright install` or `npm run install:browsers` times out locally, later Playwright commands may fail with an active lockfile at `%LOCALAPPDATA%\ms-playwright\__dirlock`. Before removing the lock, check for live `node.exe` processes whose command line still references Playwright install or download. Stop only those stale installer processes, then remove the lock. In this repository, official QA E2E should run remotely through Gitea against deployed QA apps; local Playwright execution is only for authoring diagnostics.

## PowerShell Json Timestamps Need Explicit Formatting

- Type: Pattern
- Status: Active
- Source: PR 16 CI failure in `RenderPlaneCommentRendersWorkflowTimingTable`, `.codex/skills/_shared/scripts/delivery_tools.ps1`
- Last verified: 2026-06-03

PowerShell `ConvertFrom-Json` can coerce ISO timestamp strings into `DateTime` values, and later string interpolation renders them with the host culture instead of the original `yyyy-MM-ddTHH:mm:ssZ` form. For Plane comments, workflow timing tables, or tests that assert exact UTC text, format timestamp values explicitly with invariant UTC formatting before interpolation. Reproduce failures with the CI-shaped command `dotnet test .\SDDTemplate.slnx -c Release --no-build --logger trx --collect:"XPlat Code Coverage"`.
