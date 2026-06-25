# Failure Patterns

Add future entries only when source-backed, current, and not tied to the removed sample product.

### User-Requested No-PowerShell Runs Need Alternate Execution

- Type: Pattern
- Status: Active
- Source: conversation request on 2026-06-25 and current Codex run
- Last verified: 2026-06-25

When the user says not to use PowerShell, do not call `functions.shell_command` in this Windows workspace because it invokes PowerShell by default. Use `apply_patch` for edits and a non-PowerShell execution path such as Node REPL `child_process.execFile` for validation commands.

### Installed Template Config Infra Stops On Missing Native Modes And Memory

- Type: Pattern
- Status: Superseded
- Source: user-reported first template test on 2026-06-25; verified against `tools/sdd_cli/cli.py`, `tools/sdd_cli/tests/test_cli.py`, `.codex/skills/configure-dev-environment/SKILL.md`, and `AGENTS.md`
- Last verified: 2026-06-25

First consumer-repo `config infra` stopped because configure skills required modes such as `EnsureRancherDesktopCluster`, `InitLocalFiles`, `ShowEnvironmentUrls`, and `SetSeqAzureEventHubLogs`, while native `tools.sdd_cli configure` dispatch supported only a smaller set. The installer also excluded `.codex/memory`, even though AGENTS/startup guidance requires `.codex/memory/memory_summary.md`, `.codex/memory/MEMORY.md`, and `.codex/memory/retrieval-policy.md`. This was fixed by porting advertised configure modes into native Python dispatch, seeding required memory files during install/`InitLocalFiles`, and adding tests that fail when advertised configure modes drift from CLI support.

### Installed Target README Must Not Point At Excluded Helper Tests

- Type: Pattern
- Status: Active
- Source: user-reported installed target failure on 2026-06-25; verified against `README.md` and `tools/sdd_cli/cli.py`
- Last verified: 2026-06-25

The installer excludes `tools/sdd_cli/tests`, so installed consumer repositories cannot run `python -m unittest tools.sdd_cli.tests.test_cli`. README validation commands for installed targets must use installed CLI smoke checks such as `python -m tools.sdd_cli configure Audit`; helper unit tests are lab-repository-only.

### Tool Update Must Exclude Runtime Database Directories

- Type: Pattern
- Status: Active
- Source: user-reported update blocker on 2026-06-25; verified against `tools/sdd_cli/cli.py`, `tools/sdd_cli/tests/test_cli.py`, and `python -m tools.sdd_cli tool update --target C:\Endava\EndevLocal\Personal\SDD_test --source C:\Endava\EndevLocal\Personal\SDD_template`
- Last verified: 2026-06-25

The tool updater packages files under include roots unless `is_sdd_tool_excluded` filters them. OpenProject runtime DB paths such as `infra/openproject/openproject/pgdata/**` must be excluded like `data` and `logs`, or updates can stop with unmanaged-collision blockers in consumer repositories.

### OpenProject Compose Needs Container SECRET_KEY_BASE

- Type: Pattern
- Status: Active
- Source: config infra run on 2026-06-25; verified against `infra/openproject/compose.yml`, `.codex/skills/configure-dev-environment/SKILL.md`, OpenProject GHSA-r85r-gjq2-f83r, and OpenProject 17.3.2 release notes
- Last verified: 2026-06-25

OpenProject Docker images require container env `SECRET_KEY_BASE`; mapping only `OPENPROJECT_SECRET_KEY_BASE` leaves the app using or rejecting the default. Keep ignored local env/template key `OPENPROJECT_SECRET_KEY_BASE`, but map it to container key `SECRET_KEY_BASE` in Compose. For current Trivy CLI DB refresh, use `trivy image --download-db-only`, not the old root-level `trivy --download-db-only`.
