---
name: project-guidance-discover
description: Detect the project tech stack and list relevant skills from .codex/skills/manifest.json. Use when setting up a new project, onboarding to a codebase, or before implementation work to know which skills apply.
---

# Project Guidance Discover

## Overview

Detect the project's technology stack and return the list of relevant skills from the local manifest. No external searches, no website scraping, no complex catalogs — just the skills already installed in this repository.

## Workflow

1. Run `python -m tools.sdd_cli guidance discover` to detect stack tags and list relevant skills.
2. Read the output `detectedTags` and `relevantSkills` to see which skills apply.
3. Cross-reference the relevant skills against the user's current task using the Mandatory Skill Catalog Review process in AGENTS.md.

## Output

- `detectedTags`: technology stack tags detected (e.g. react, python, typescript)
- `relevantSkills`: list of skills from manifest.json with their category and path
- `skillCount`: total count of non-core skills in the manifest
