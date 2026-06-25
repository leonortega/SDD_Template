# Failure Patterns

Add future entries only when source-backed, current, and not tied to the removed sample product.

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
