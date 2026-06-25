# Failure Patterns

Add future entries only when source-backed, current, and not tied to the removed sample product.

### Installed Template Config Infra Stops On Missing Native Modes And Memory

- Type: Pattern
- Status: Superseded
- Source: user-reported first template test on 2026-06-25; verified against `tools/sdd_cli/cli.py`, `tools/sdd_cli/tests/test_cli.py`, `.codex/skills/configure-dev-environment/SKILL.md`, and `AGENTS.md`
- Last verified: 2026-06-25

First consumer-repo `config infra` stopped because configure skills required modes such as `EnsureRancherDesktopCluster`, `InitLocalFiles`, `ShowEnvironmentUrls`, and `SetSeqAzureEventHubLogs`, while native `tools.sdd_cli configure` dispatch supported only a smaller set. The installer also excluded `.codex/memory`, even though AGENTS/startup guidance requires `.codex/memory/memory_summary.md`, `.codex/memory/MEMORY.md`, and `.codex/memory/retrieval-policy.md`. This was fixed by porting advertised configure modes into native Python dispatch, seeding required memory files during install/`InitLocalFiles`, and adding tests that fail when advertised configure modes drift from CLI support.
