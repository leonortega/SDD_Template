---
name: project-guidance-discover
license: MIT
description: Detect the project tech stack and list relevant skills from .codex/skills/manifest.json. Use when setting up a new project, onboarding to a codebase, or before implementation work to know which skills apply.
---

# Project Guidance Discover

## Overview

Ask the user for their project's technology stack and return the list of relevant skills from the local manifest. No automated detection, no file inspection — the stack must come from the user. No external searches, no website scraping, no complex catalogs — just the skills already installed in this repository.

## Workflow

1. **Ask the user** what tech stack they are using (frontend, backend, database, languages).
2. Once confirmed, run `python -m tools.sdd_cli guidance discover` to list relevant skills.
3. Read the output `relevantSkills` to see which skills apply.
4. Cross-reference the relevant skills against the user's current task using the Mandatory Skill Catalog Review process in AGENTS.md.

## Output

- `relevantSkills`: list of skills from manifest.json with their category and path
- `skillCount`: total count of non-core skills in the manifest

## Constraints

- **Never auto-detect or infer** the tech stack from source code, file extensions, or configuration files.
- **Always ask the user first.** Stack detection without user confirmation is a violation of the SDLC process (authority level 5).
