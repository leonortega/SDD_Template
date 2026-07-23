# Cline Skills Mapping

This directory contains a mapping/wrapper structure that points to the actual skills in `.codex/skills/`.

## Structure

- `.cline/skills/` contains directory junctions (Windows equivalent of symbolic links) that point to the corresponding skill directories in `.codex/skills/`
- Each skill directory in `.cline/skills/` is a junction that transparently redirects to the actual skill location
- This allows Cline or other tools to access skills through the `.cline/skills/` path while maintaining the actual skill definitions in `.codex/skills/`

## How It Works

The mapping was created using Windows directory junctions via the `mklink /J` command. This creates a seamless wrapper where:

- `.cline\skills\<skill-name>\` → `.codex\skills\<skill-name>\`
- All files and subdirectories are accessible through either path
- Changes made through either path affect the same underlying files

## Why Directory Junctions?

This implementation uses individual directory junctions because they provide several key advantages:

- **No Special Permissions Required**: Works without Developer Mode or admin rights
- **Broader Compatibility**: Compatible across different Windows configurations
- **Explicit Mapping**: Each skill has its own dedicated junction for better management
- **Easy Maintenance**: Simple to update individual mappings when new skills are added
- **Reliable**: Junctions are a stable, well-supported Windows feature

## Available Skills

All skills from `.codex/skills/` (except the `_shared` directory) are mapped to `.cline/skills/`. This includes:

- Core workflow skills (dev-flow-_, configure-_)
- Utility skills (caveman, ponytail, grill-*, etc.)
- Technical skills (playwright, tdd, security-best-practices, etc.)
- Project management skills (project-guidance-*, domain-modeling)

## Maintenance

To update the mappings if new skills are added:

1. Run the Python script: `python .cline\create_skill_links.py`
2. This will create junctions for any new skills that don't already have mappings

## Python Script Features

The Python script provides several advantages:

- **Cross-platform compatible** (though junctions are Windows-specific)
- **Better error handling** and progress reporting
- **Automatic directory creation** if needed
- **Detailed logging** of which junctions were created vs. skipped
- **Windows platform check** to prevent errors on other operating systems

## Benefits

1. **Compatibility**: Provides a Cline-compatible skills directory structure
2. **No Duplication**: Skills are not copied, just linked - saving disk space
3. **Single Source of Truth**: All skill definitions remain in `.codex/skills/`
4. **Transparent**: Applications can access skills through either path seamlessly
