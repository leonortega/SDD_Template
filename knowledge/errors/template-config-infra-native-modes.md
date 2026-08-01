# Installed Template Config Infra Stops On Missing Native Modes And Knowledge

## Summary

First consumer-repo `config infra` stopped because configure skills advertised modes the native CLI dispatch did not implement, and the installer did not seed the knowledge base files startup guidance requires.

## Problem

Configure skills required modes such as `EnsureRancherDesktopCluster`, `InitLocalFiles`, `ShowEnvironmentUrls`, and `ValidateObservability`, while native `tools.sdd_cli configure` dispatch supported only a smaller set.

## Context

User-reported first template test on 2026-06-25; verified against `tools/sdd_cli/cli.py`, `tools/sdd_cli/tests/test_cli.py`, `.codex/skills/configure-dev-environment/SKILL.md`, and `AGENTS.md`.

## Root Cause

Advertised configure modes drifted from the CLI implementation, and AGENTS/startup guidance required `knowledge/README.md` (previously `knowledge/README.md`, `knowledge/README.md`, `knowledge/README.md`) which the installer did not seed.

## Solution

Port advertised configure modes into native Python dispatch, seed the required knowledge files during install/`InitLocalFiles`, and add tests that fail when advertised configure modes drift from CLI support.

## Alternatives

Keeping a PowerShell/legacy fallback dispatcher was rejected because it hid drift instead of failing loudly.

## Limitations

The test gate only covers configure modes; other advertised surfaces must be covered by their own drift tests.

## Examples

- `python -m tools.sdd_cli configure InitLocalFiles` works natively after the fix.

## Related Documents

- `tools/sdd_cli/cli.py`
- `.codex/skills/configure-dev-environment/SKILL.md`
- `knowledge/README.md`

## Tags

- Type: Pattern
- Status: Superseded
- Source: user-reported first template test on 2026-06-25
- Last verified: 2026-06-25
- configure, installer, native-dispatch, seeding
