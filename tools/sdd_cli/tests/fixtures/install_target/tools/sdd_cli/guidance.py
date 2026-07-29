"""Project guidance: list relevant skills from manifest based on project stack."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from ._shared import (
    REPO_ROOT,
    configure_result,
    load_project_profile,
    parse_pairs,
    read_json,
)


def _read_stack_tags(profile: dict[str, Any]) -> list[str]:
    """Extract simple stack tags from the project profile.

    Returns lowercase tags for the three stack domains (frontend, backend, database)
    when they have ``applies: true`` and a non-empty value.
    """
    tags: list[str] = []
    stack = profile.get("stack", {})
    if not isinstance(stack, dict):
        return tags
    for domain in ("frontend", "backend", "database"):
        domain_info = stack.get(domain, {})
        if isinstance(domain_info, dict):
            if domain_info.get("applies") is True:
                raw = str(domain_info.get("value", "")).lower().strip()
                if raw:
                    tags.append(raw)
        elif isinstance(domain_info, str):
            raw = domain_info.lower().strip()
            if raw and raw not in ("none", "n/a", "na"):
                tags.append(raw)
    return tags


def discover_project_guidance(
    root: Path, dry_run: bool = False, **values: Any
) -> dict[str, Any]:
    """List relevant skills from .codex/skills/manifest.json for the project stack.

    Reads the project stack from profile, finds matching skills from the manifest
    categories, and returns them. Categories with ``stackTags`` are only included
    when the stack value overlaps with that field. Categories without ``stackTags``
    are always included (stack-agnostic methodology/process skills).
    """
    result = configure_result(
        "DiscoverProjectGuidance", dry_run, write_enabled=not dry_run
    )
    manifest_path = root / ".codex" / "skills" / "manifest.json"
    if not manifest_path.exists():
        return {
            "mode": "DiscoverProjectGuidance",
            "valid": False,
            "errors": ["Manifest not found at .codex/skills/manifest.json"],
        }

    manifest = read_json(manifest_path, optional=True)
    if not manifest:
        return {
            "mode": "DiscoverProjectGuidance",
            "valid": False,
            "errors": ["Could not parse .codex/skills/manifest.json"],
        }

    categories = manifest.get("categories", {})
    profile = load_project_profile(root)
    stack_tags = _read_stack_tags(profile)
    stack_tags_lower = [t.lower() for t in stack_tags]

    # Collect skills from non-core categories, filtering by stackTags when present
    relevant_skills: list[dict[str, Any]] = []
    filtered_categories: list[dict[str, Any]] = []
    for cat_name, cat_data in categories.items():
        if not isinstance(cat_data, dict):
            continue
        if cat_data.get("alwaysActive"):
            continue

        # Check stackTag filter if present
        cat_stack_tags = cat_data.get("stackTags")
        if isinstance(cat_stack_tags, list) and cat_stack_tags:
            if stack_tags and not any(
                _tag_matches_stack(tag, stack_tags_lower) for tag in cat_stack_tags
            ):
                # Stack set but no match — skip
                filtered_categories.append({
                    "category": cat_name,
                    "reason": f"No stack tag matches {cat_stack_tags}",
                })
                continue

        cat_skills = cat_data.get("skills", [])
        if not isinstance(cat_skills, list):
            continue
        for skill_path in cat_skills:
            skill_dir = root / ".codex" / "skills" / skill_path
            exists = skill_dir.exists()
            relevant_skills.append({
                "category": cat_name,
                "path": skill_path,
                "exists": exists,
            })

    if stack_tags:
        result["actions"].append({
            "path": "stack",
            "key": "detected",
            "severity": "info",
            "message": f"Stack values from profile: {', '.join(stack_tags)}",
            "phase": "audit",
        })

    result["stackTags"] = stack_tags
    result["relevantSkills"] = relevant_skills
    result["skillCount"] = len(relevant_skills)
    result["filteredCategories"] = filtered_categories
    result["valid"] = True
    return result


def _tag_matches_stack(tag: str, stack_lower: list[str]) -> bool:
    """Check if a manifest tag matches any of the stack values.

    Uses substring matching (e.g. 'react' matches 'react + typescript').
    """
    tag_lower = tag.lower()
    return any(tag_lower in s for s in stack_lower)


def run_guidance(args: list[str]) -> int:
    """CLI entry point for guidance commands."""
    if not args:
        print("Available: discover", file=sys.stderr)
        return 1
    subcommand = args[0]
    options = parse_pairs(args[1:])
    root = Path(options.get("root", REPO_ROOT))
    dry_run = options.get("dry-run", "false").lower() == "true"

    if subcommand == "discover":
        result = discover_project_guidance(root, dry_run)
        print(json.dumps(result, indent=2))
        return 0 if result.get("valid", True) else 1

    print(f"Unknown guidance subcommand: {subcommand}", file=sys.stderr)
    return 1
