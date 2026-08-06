---
name: project-guidance-discover
license: MIT
description: >-
  >- Search the internet (public skills.sh registry via npx skills) for skills relevant to the project tech stack. Never
  consults local skills to answer guidance. Use when setting up a new project, onboarding to a codebase, or before
  implementation work to know which skills apply.
---

# Project Guidance Discover

## Overview

Ask the user for their project's technology stack, then search the **public skills.sh registry on the internet** (`npx
skills find <query>`) for skills relevant to that stack. The answer to what
skills apply ALWAYS comes from the internet — local skills and `.codex/skills/manifest.json` are NEVER consulted to
answer guidance. The user decides which discovered skills to install (see
`project-guidance-acquire` / `setup_project_guidance`).

## Shared Context

Read `.codex/skills/_shared/delivery-contract.md` and
`docs/conventions/context-management.md` before discovering. Discovery supports
the active ticket's skill catalog review — the stack must come from the user,
never auto-detected.

## Workflow

1. **Ask the user** what tech stack they are using (frontend, backend, database, languages).
2. Once confirmed, run `python -m tools.sdd_cli guidance discover` to search the internet for stack-relevant skills.
3. Read the output `foundSkills` (internet results) and `stackTags` to see which skills apply.
4. Present the internet results to the user and ask which to install before installing anything (interactive gate,
authority level 5).
5. After the user selects, install the chosen skills via `npx skills add` (falls back to GitHub copy). Installing
updates `manifest.json` — bookkeeping only, never the source of guidance.

## Output

- `stackTags`: normalized stack values from the user/profile (frontend, backend, database)
- `foundSkills`: skills found on the internet for those stack values (`owner/repo@skill` format)
- `skillCount`: total internet skills found for the stack
- Present results for user validation; record the chosen skills for handoff

## Constraints

- **Never auto-detect or infer** the tech stack from source code, file extensions, or configuration files.
- **Always ask the user first.** Stack detection without user confirmation is a violation of the SDLC process (authority
level 5).
- **Never answer guidance from local skills.** `.codex/skills/manifest.json` and installed skills exist only for
idempotency (skip reinstall) and catalog review — never as the basis for recommending
skills.
- **Always ask before installing.** Internet-discovered skills are candidates; the user chooses which to install.

## Failure Rules

- Stop if the user has not confirmed the tech stack — never auto-detect.
- Stop if the user has not approved the discovered skills — never install unvetted skills.
- Stop if `npx skills` is unavailable; report the blocker instead of consulting local skills.
- Do not answer guidance from local skills or `manifest.json` at any point.
