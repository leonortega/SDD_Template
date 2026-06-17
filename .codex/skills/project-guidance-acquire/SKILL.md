---
name: project-guidance-acquire
description: Acquire confirmed project guidance locally. Use after project-guidance-discover has researched extra useful skills, MCPs, plugins, tools, references, practices, standards, and Codex-applicable IDE helpers, shown suggestions, received confirmation/dismissals/omissions, and produced the final confirmed list; auto-copy safe repo-local Codex skills into this repo's .codex/skills directory; prepare guarded install plans for MCPs, plugins, tools, IDE/global installs, secrets, or restart-required items; aggregate IDE restart/system reboot notices once at the end.
---

# Project Guidance Acquire

## Overview

Use this skill only with the final confirmed list from `project-guidance-discover`. A confirmed list means the user has already authorized recording and supported guarded installation/configuration for those items; do not ask a second install confirmation.

This skill handles guarded acquisition from confirmed recommendations. Safe repo-local, non-secret skill recommendations may be copied into `.codex/skills`. Non-skill guidance such as tools, MCPs, plugins, IDE extensions, references, practices, and standards remains metadata in `.codex/tool-recommendations.local.json` unless a deterministic repo-local config path or platform-supported installer is explicitly supported.

## Shared Context

Read `.codex/skills/_shared/delivery-contract.md` and `docs/context-management.md` before copying skills that affect ticket delivery, QA, deployment, security, or handoff behavior. The source `SKILL.md`, repository docs, and validation commands are the authority for what to copy.

## Input Contract

Each confirmed skill must include:

- `name`
- `type: skill`
- `installMethod: manual-copy`
- `source`
- `target`, normally `.codex/skills/{skill-name}/SKILL.md`
- `validation`, normally `Test-Path .codex/skills/{skill-name}/SKILL.md`
- `sourceKind`, such as `repo-local`, `openai-official`, `tool-official`, `technology-owner`, `skills-cli`, `marketplace`, or `community`

If a source is missing or ambiguous, return to `project-guidance-discover` for research before copying.

## Workflow

1. Filter the final confirmed list by type and install metadata.
2. Read the source repository's `SKILL.md`; when a `skills.sh`, `skills`, marketplace, or README command supplied the lead, treat the command as metadata only and use it to locate the repository/ref/path.
3. Create `.codex/skills/{skill-name}/` when it does not exist.
4. Write the copied `SKILL.md` to the target path.
5. Inspect the source and copied `SKILL.md` for required frontmatter, matching name/description intent, and required relative references.
6. Copy only required referenced scripts, templates, assets, or reference files that are needed by that skill.
7. Run the validation command, such as:

```powershell
Test-Path .\.codex\skills\{skill-name}\SKILL.md
```

8. Install or configure confirmed non-skill items when a platform-supported installer/configuration tool is available, such as `codex mcp add` for Codex MCP servers. Do not run arbitrary installer snippets.
9. Report copied files, skipped files, installed/configured items, guarded install plans that could not be executed automatically, validation results, and any source limitations.
10. Refresh `.codex/tool-recommendations.local.json` by rerunning `DiscoverProjectGuidance` with `persistLocal=true` so future `project-guidance-mapper` decisions can see installed skills, source URLs, targets, validation commands, and current `usedInSteps`. Preserve existing accepted/dismissed state and `usedInSteps` unless the user explicitly resets the local catalog.
11. Aggregate all `requiresIdeRestart` and `requiresSystemReboot` items. Finish all independent acquisition work first, then show one Important message listing affected items, restart/reboot type, reason, and post-restart validation commands.

## Safety Rules

- Do not run arbitrary command installers, curl scripts, bootstrap snippets, or package-manager commands discovered from external sources.
- Do not install into `$CODEX_HOME`.
- Require explicit confirmation before global, IDE, privileged, MCP/plugin, secret-bearing, or reboot-required installs. The final confirmed list from `project-guidance-discover` is that confirmation for listed non-secret items; ask again only when a concrete installer would introduce new scope, privilege, secrets, destructive behavior, or different items.
- Do not reboot automatically. Report one aggregate IDE restart/system reboot notice after all feasible work finishes.
- Use platform-supported plugin/connector install tools only when available and only for the exact requested or confirmed item.
- Use `codex mcp add` for confirmed Codex MCP entries when source and command/URL are known from official/vendor metadata.
- Do not copy secrets, tokens, `.local` files, caches, generated artifacts, build outputs, logs, local state, `.git`, or unrelated files.
- Do not overwrite an existing repo-local skill unless the user explicitly confirms replacement.
- Keep source attribution in the handoff so later agents know where the skill came from.
- Label community-maintained sources as `sourceKind: community`; prefer repo-local, official, tool-owner, or technology-owner sources when available.
- Do not copy OpenSpec or configure skills as recommended/acquired expert skills.

## Output

Return a concise result:

- skills copied
- skills already present
- skills skipped with reason
- non-skill guidance left in the local catalog
- validation commands and pass/fail result
- files copied under each skill folder
- whether `.codex/tool-recommendations.local.json` was refreshed

If any skill cannot be copied safely, stop before partial unrelated copying and report the blocker.

## Failure Rules

- Stop if the input is not the final confirmed list from `project-guidance-discover`.
- Stop if a source is missing, ambiguous, unverifiable, or asks for command-based installation.
- Stop if copying would overwrite an existing skill without explicit user confirmation.
- Stop if referenced files include secrets, local state, caches, generated artifacts, or unrelated files.
