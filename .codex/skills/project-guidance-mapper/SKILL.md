---
name: project-guidance-mapper
license: MIT
description: This skill is deprecated — skill selection is handled by the Mandatory Skill Catalog Review process in AGENTS.md and the Workflow Stage Routing table. Use project-guidance-discover to list relevant skills from manifest.json.
---

# Project Guidance Mapper

**Deprecated.** Skill-to-workflow mapping is now handled by:
- The **Mandatory Skill Catalog Review** process in AGENTS.md — determines which skills apply to the current task.
- The **Workflow Stage Routing** table in AGENTS.md — maps workflow stages to specific skill paths.

To discover skills relevant to your tech stack:
```bash
python -m tools.sdd_cli guidance discover
```
