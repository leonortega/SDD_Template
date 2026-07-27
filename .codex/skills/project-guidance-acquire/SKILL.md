---
name: project-guidance-acquire
description: This skill is deprecated — skill discovery and activation is now handled by the Mandatory Skill Catalog Review process in AGENTS.md. Use project-guidance-discover to list relevant skills from manifest.json.
---

# Project Guidance Acquire

**Deprecated.** Skills are no longer acquired through this flow.

To use skills from manifest.json:
1. Run `python -m tools.sdd_cli guidance discover` to see relevant skills.
2. Follow the Mandatory Skill Catalog Review process in AGENTS.md to select and load skills for the current task.
3. To install new skills, use `npx skills add <owner/repo>@<skill-name>` or move them manually into `.codex/skills/`.
