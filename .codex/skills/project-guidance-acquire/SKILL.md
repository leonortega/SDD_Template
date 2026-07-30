---
name: project-guidance-acquire
license: MIT
description: Install skills from configured GitHub sources using the SDD CLI tool installer. Uses GitHub raw content API (no cloning required).
---

# Project Guidance Acquire

Installs skills using a hybrid approach:
1. **Primary**: tries `npx skills add` (skills.sh registry)
2. **Fallback**: fetches raw content from GitHub repos via the GitHub API

## Prerequisites

- Node.js / npx available on PATH (for primary method)
- `.codex/skill-sources.json` or `.codex/skill-sources.example.json` with configured GitHub source repos (for fallback)
- Optional: GitHub token for higher API rate limits (`--token`)

## Usage

### List available skills from configured GitHub sources

```bash
python -m tools.sdd_cli tool-installer list-skills
```

This reads `.codex/skill-sources.json` (falling back to `.codex/skill-sources.example.json`, then hardcoded defaults), fetches the GitHub Contents API for each source, and returns all discoverable skill directories.

### Install a skill by source name

```bash
python -m tools.sdd_cli tool-installer install-skill \
  --source awesome-copilot \
  --skill-name my-skill
```

The source name is looked up in the config to resolve the repo and path. Default sources:

| Name | Repo | Description |
|------|------|-------------|
| `awesome-copilot` | `github/awesome-copilot` (skills/) | GitHub's awesome-copilot skills collection |
| `anthropics` | `anthropics/skills` (skills/) | Anthropic's skills collection |

### Install a skill directly (without source config)

```bash
python -m tools.sdd_cli tool-installer install-skill \
  --repo owner/repo \
  --skill-path path/to/skill-dir \
  --skill-name my-skill \
  --branch main
```

### Preview without downloading

Add `--dry-run true` to any of the above commands to see what would be installed without making API calls.

### Configure custom skill sources

Create `.codex/skill-sources.json` with your own repos:

```json
{
  "sources": [
    {
      "name": "my-skills",
      "repo": "my-org/my-repo",
      "path": "skills",
      "branch": "main",
      "description": "My custom skills"
    }
  ]
}
```

## What gets installed

- **npx method**: skill is installed to `.codex/skills/<skill-name>/` via the skills.sh registry
- **GitHub fallback**: the entire skill directory is copied to `.codex/skills/<skill-name>/`
- If a `SKILL.md` exists in the installed files, the skill is auto-registered in `manifest.json` under the `community` category
- Existing files are skipped (no overwrites)

## See also

- `python -m tools.sdd_cli guidance discover` — list relevant skills from manifest.json by tech stack
- `python -m tools.sdd_cli tool-installer validate-manifest` — verify all manifest skills exist on disk
- `docs/context-management.md` — Mandatory Skill Catalog Review process
