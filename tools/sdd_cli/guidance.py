"""Project guidance: detect tech stack and return relevant skills from manifest."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from ._shared import (
    REPO_ROOT,
    configure_result,
    detect_stack_tags,
    parse_pairs,
    read_json,
)


def discover_project_guidance(
    root: Path, dry_run: bool = False, **values: Any
) -> dict[str, Any]:
    """Detect tech stack and return relevant skills from .codex/skills/manifest.json.

    Reads the project stack tags, looks up matching skills from the manifest
    categories, and returns them as recommendations.

    Categories with a ``stackTags`` field are only included when the detected
    stack tags overlap with that field. Categories without ``stackTags`` are
    always included (they are stack-agnostic methodology/process skills).
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
    detected = detect_stack_tags(root)
    detected_lower = [t.lower() for t in detected]

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
            if detected and any(
                tag.lower() in detected_lower for tag in cat_stack_tags
            ):
                # Stack matches this category's tags
                pass
            elif not detected:
                # No stack detected yet — include anyway (conservative)
                pass
            else:
                # Stack detected but no match — skip this category
                filtered_categories.append({
                    "category": cat_name,
                    "reason": f"No detected stack tag matches {cat_stack_tags}",
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

    if detected:
        result["actions"].append({
            "path": "stack",
            "key": "detected",
            "severity": "info",
            "message": f"Detected stack tags: {', '.join(detected)}",
            "phase": "audit",
        })

    result["detectedTags"] = detected
    result["relevantSkills"] = relevant_skills
    result["skillCount"] = len(relevant_skills)
    result["filteredCategories"] = filtered_categories
    result["valid"] = True
    return result


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
