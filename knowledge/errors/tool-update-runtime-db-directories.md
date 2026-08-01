# Tool Update Must Exclude Runtime Database Directories

## Summary

The tool updater packages files under include roots unless exclusion filters them; OpenProject runtime DB paths must be excluded like `data` and `logs`.

## Problem

Updates can stop with unmanaged-collision blockers in consumer repositories when runtime database directories are treated as managed tool files.

## Context

User-reported update blocker on 2026-06-25; verified against `tools/sdd_cli/cli.py`, `tools/sdd_cli/tests/test_cli.py`, and a real `template-installer update` run from the template source into a consumer target.

## Root Cause

OpenProject runtime DB paths such as `infra/openproject/openproject/pgdata/**` were walked as managed files instead of excluded.

## Solution

Exclude `pgdata` (and `data`, `logs`) from managed tool files so updates never treat runtime databases as tool-owned.

## Alternatives

Not recorded.

## Limitations

Exclusion lists must be kept in sync as new runtime paths appear.

## Examples

- Excluded segments: `data`, `logs`, `pgdata`.

## Related Documents

- `tools/sdd_cli/tools/sdd-tool-data.json` (exclusion config)
- `tools/sdd_cli/_shared.py` (`walk_sdd_source_files`)

## Tags

- Type: Pattern
- Status: Active
- Source: user-reported update blocker on 2026-06-25
- Last verified: 2026-06-25
- installer, update, exclusion, pgdata
