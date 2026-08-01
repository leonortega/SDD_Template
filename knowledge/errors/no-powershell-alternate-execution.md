# User-Requested No-PowerShell Runs Need Alternate Execution

## Summary

When the user says not to use PowerShell, do not call `functions.shell_command` in this Windows workspace because it invokes PowerShell by default.

## Problem

Agent tooling defaulting to PowerShell violates an explicit user instruction and can mutate state through the wrong shell.

## Context

Windows workspace; explicit user request on 2026-06-25 and in subsequent runs. The default shell resolution on this machine points at PowerShell.

## Root Cause

`functions.shell_command` invokes PowerShell by default on Windows rather than a neutral shell.

## Solution

Use `apply_patch` for edits and a non-PowerShell execution path such as Node REPL `child_process.execFile` for validation commands.

## Alternatives

Not recorded.

## Limitations

Manual discipline; there is no enforced guard that blocks the PowerShell default.

## Examples

- Editing: `apply_patch` instead of shell redirection.
- Validation: `child_process.execFile` in a Node REPL instead of `shell_command`.

## Related Documents

- `knowledge/README.md`
- `AGENTS.md`

## Tags

- Type: Pattern
- Status: Active
- Source: conversation request on 2026-06-25 and current Codex run
- Last verified: 2026-06-25
- powershell, execution, windows, tooling
