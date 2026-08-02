<!-- TIER 1: STABLE PREFIX - Repo-owned, always-active skill policy -->

# Repository Startup — Always-Active Skills

This file is repo-owned. External skill updates never touch it.

## Always-Active Skills

Per `AGENTS.md` these skills activate on every prompt:

| Skill        | When                           | Intensity |
| ------------ | ------------------------------ | --------- |
| **caveman**  | Every prompt                   | full      |
| **ponytail** | Every prompt                   | full      |
| **security** | When security context detected | default   |

### Caveman (every prompt)

Apply caveman full to all assistant chat prompts. Use terse fragments for commentary, direct answers, status updates, debug findings, next steps, blockers, validation summaries, and final summaries. Write normal complete prose for authored artifacts (code, commits, PRs, docs, OpenSpec).

Keep code blocks, commands, paths, API names, error messages, quoted text, and file content exact. Temporarily use normal prose for security warnings, irreversible actions, precise multi-step instructions, ambiguous order of operations, or clarification.

### Ponytail (every prompt)

Apply ponytail full on every prompt. Use the smallest working change, prefer standard library and native framework features, avoid speculative abstractions or dependencies, and keep tests focused on changed behavior.

## Other Skills

Activate on demand when task matches their `description` trigger phrases. Do not force-activate skills unrelated to current task.

Use `.codex/skills/manifest.json` to find the correct category for your current task type. Load only skills from that category + the always-active core skills.

## Priority

caveman > ponytail > others

## Skill Manifest

`.codex/skills/manifest.json` is the **single source of truth** mapping task types to skill file paths (categories: ticket, implement, review, qa, deploy, monitor, parallel, config, guidance, plan, architecture, security, test, quality, gitea, openproject, nexus, observability, kubernetes). Read the manifest directly instead of maintaining a category list here — this section intentionally stays short so it cannot drift from the manifest.
