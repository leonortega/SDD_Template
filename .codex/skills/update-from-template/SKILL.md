---
name: update-from-template
description: Update this consumer repository from the canonical SDD_Template source. Use when the user asks to update to the latest template version or to a specific tagged release.
---

<!-- TIER 3: STAGE-SPECIFIC - Template update skill -->

# Update From Template

## Overview

This repository is a **consumer** of the **SDD_Template** (`C:\LeonRepository\SDD_Template`). Template updates copy managed files (skills, providers, docs, infra, tools, config) from the source into this repo while preserving local-only files (project-profile, secrets, memory, product source).

Updates are done via the `template-installer` CLI tool built into `tools/sdd_cli/`.

## Agent Routing

Trigger this skill when the user says:
- "Update from template"
- "Update to latest version / last version"
- "Update SDD template to vX.Y.Z"
- "Sync with SDD_Template"
- "Apply new template version"

## Quick Update Command

Path note: This repo lives at `C:\LeonRepository\SDD_Test` (Windows) which is `/c/LeonRepository/SDD_Test` in Git Bash / WSL. The SDD_Template source is at `C:\LeonRepository\SDD_Template` (`/c/LeonRepository/SDD_Template` in bash). Use the format matching your shell.

```bash
cd /c/LeonRepository/SDD_Test
python -m tools.sdd_cli template-installer update \
  --source /c/LeonRepository/SDD_Template \
  --version v1.0.25 \
  --target /c/LeonRepository/SDD_Test
```

- Omit `--version` to auto-resolve the latest final Git tag (ignores `-rc.x` tags).
- Use `--dry-run true` to preview changes without applying them.

## Prerequisites

1. **SDD_Template exists** at `C:\LeonRepository\SDD_Template` with a valid Git tag.
2. **This repo has a manifest** at `.codex/sdd-tool-version.json` (created by a prior `install` or `update`).
3. **No unmanaged file collisions** — run `--dry-run true` first to check.

## Available Versions

Check the source repo for available tags:

```bash
cd /c/LeonRepository/SDD_Template && git tag --list 'v*'
```

Final releases look like `v1.0.25`. Pre-release tags look like `v0.1.7-rc.2`.

## What Gets Updated

**Managed files** (from `sdd-tool-data.json` → `SDD_TOOL_INCLUDE_DIRS`):
- `.agents/`, `.cline/`, `.codex/providers/`, `.codex/skills/`
- `.gitea/workflows/`, `docs/`, `infra/`, `tools/`, `.vscode/`

**Preserved files** (not overwritten):
- `.codex/project-profile.local.json`
- `.codex/memory/MEMORY.md`, `memory_summary.md`, `retrieval-policy.md`
- `.codex/client-tools.local.json`, `.codex/quality.local.json`
- `.codex/environment-urls.local.json`, `.codex/tool-recommendations.local.json`

## What Happens During Update

1. Reads the old manifest (`sdd-tool-version.json`) to know which files were previously managed.
2. Scans the SDD_Template source for all managed files (skipping `.git`, `__pycache__`, tests, evals, etc.).
3. Checks for **unmanaged collisions** — existing files in this repo that are NOT in the managed file list but differ from the source. If found, the update **refuses to proceed**.
4. Copies every managed file from source to target, overwriting previous versions.
5. Removes files that were managed in the old version but no longer exist in the new version.
6. Writes the updated manifest with new version, checksum, and file list.

## After Update

1. **Review changed files** via `git diff --stat` (look for ~30-100 changed files).
2. **Verify the manifest** at `.codex/sdd-tool-version.json` shows the correct version tag.
3. **Re-apply any local-only tweaks** to managed files that were overwritten.
4. **Commit the update** on the current working branch.

## Output

Report: source version, target version, number of files managed, number of files changed, number of files removed, and any collisions that blocked the update.
