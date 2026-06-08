---
name: project-guidance-acquire
description: Acquire confirmed project guidance locally. Use after project-guidance-discover has shown suggestions, asked for additional desired skills or guidance, and produced the final confirmed list; manually copy confirmed Codex skills into this repo's .codex/skills directory with no command installers, while non-skill guidance remains catalog metadata.
---

# Project Guidance Acquire

## Overview

Use this skill only with the final confirmed list from `project-guidance-discover`.

This skill handles the repo-local handoff from confirmed skill recommendations to copied `.codex/skills` files. Non-skill guidance such as tools, MCPs, plugins, references, practices, and standards remains metadata in `.codex/tool-recommendations.local.json`.

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

1. Filter the final confirmed list to `type: skill` and `installMethod: manual-copy`.
2. Read the source repository's `SKILL.md`; when a `skills.sh`, `skills`, marketplace, or README command supplied the lead, treat the command as metadata only and use it to locate the repository/ref/path.
3. Create `.codex/skills/{skill-name}/` when it does not exist.
4. Write the copied `SKILL.md` to the target path.
5. Inspect the source and copied `SKILL.md` for required frontmatter, matching name/description intent, and required relative references.
6. Copy only required referenced scripts, templates, assets, or reference files that are needed by that skill.
7. Run the validation command, such as:

```powershell
Test-Path .\.codex\skills\{skill-name}\SKILL.md
```

8. Report copied files, skipped files, validation results, and any source limitations.
9. Refresh `.codex/tool-recommendations.local.json` by rerunning `DiscoverProjectGuidance` with `persistLocal=true` so future `project-guidance-mapper` decisions can see installed skills, source URLs, targets, validation commands, and current `usedInSteps`. Preserve existing accepted/dismissed state and `usedInSteps` unless the user explicitly resets the local catalog.

## Safety Rules

- Do not use command-based skill installers.
- Do not install into `$CODEX_HOME`.
- Do not run plugin installers, MCP installers, package managers, or bootstrap commands to acquire a skill.
- Do not execute installer commands discovered from `skills.sh`, `skills`, marketplace pages, README snippets, or curl examples.
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
