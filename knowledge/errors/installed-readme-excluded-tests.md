# Installed Target README Must Not Point At Excluded Helper Tests

## Summary

The installer excludes `tools/sdd_cli/tests`, so installed consumer repositories cannot run `python -m unittest tools.sdd_cli.tests.test_cli`.

## Problem

README validation commands that reference helper unit tests fail in installed consumer repositories because those tests are intentionally excluded from the installed tool.

## Context

User-reported installed target failure on 2026-06-25; verified against `README.md` and `tools/sdd_cli/cli.py`.

## Root Cause

The installer packages only runtime workflow assets; helper unit tests are lab-repository-only.

## Solution

README validation commands for installed targets must use installed CLI smoke checks such as `python -m tools.sdd_cli environment-lab audit`. Helper unit tests remain lab-repository-only.

## Alternatives

Not recorded.

## Limitations

Installed consumers cannot run the internal unit suite; they rely on CLI-level smoke checks and their own product tests.

## Examples

- Valid installed check: `python -m tools.sdd_cli environment-lab audit`
- Invalid installed check: `python -m unittest tools.sdd_cli.tests.test_cli`

## Related Documents

- `README.md`
- `tools/sdd_cli/cli.py`

## Tags

- Type: Pattern
- Status: Active
- Source: user-reported installed target failure on 2026-06-25
- Last verified: 2026-06-25
- installer, readme, tests, consumer
