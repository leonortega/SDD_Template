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
    run_native,
    write_json,
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


# ── Internet skill search ──────────────────────────────────────────────

_MAX_SKILLS_PER_QUERY = 3  # Take top N results from each internet search


def _normalize_stack_value(v: Any) -> str:
    """Extract the 'value' string from a normalized stack domain dict or a raw string."""
    if isinstance(v, dict):
        return str(v.get("value", "")).lower().strip()
    return str(v).lower().strip() if v else ""


def _search_skills_internet(root: Path, query: str, dry_run: bool) -> list[dict[str, Any]]:
    """Search the internet skill registry for skills matching a query.

    Uses ``npx skills find <query>`` to search the public skills.sh registry.
    Results are sorted by install count (most popular first).

    Returns a list of dicts with keys:
        - ``package``: GitHub owner/repo
        - ``skill``: skill name within the package
        - ``installs``: integer install count
        - ``package_skill``: ``owner/repo@skill`` format for ``npx skills add``
    """
    if dry_run:
        return []

    result = run_native(["npx", "skills", "find", query], root, timeout=30)
    if result["returncode"] != 0 or not result["stdout"].strip():
        return []

    skills: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line in result["stdout"].splitlines():
        line = line.strip()
        # Match: owner/repo@skill-name XXX installs
        if "/" not in line or "@" not in line:
            continue
        if "installs" not in line:
            continue

        parts = line.split()
        package_skill = parts[0]  # e.g. "owner/repo@skill-name"
        if package_skill in seen:
            continue
        seen.add(package_skill)

        if "@" not in package_skill:
            continue
        # Split only on the LAST @ to handle repo names with @
        at_idx = package_skill.rindex("@")
        package = package_skill[:at_idx]  # owner/repo
        skill_name = package_skill[at_idx + 1:]  # skill-name

        # Parse install count from parts like "585.8K"
        installs_str = parts[1] if len(parts) > 1 else "0"
        installs = _parse_installs_value(installs_str)

        skills.append({
            "package": package,
            "skill": skill_name,
            "installs": installs,
            "package_skill": package_skill,
        })

    # Sort by popularity descending, take top N
    skills.sort(key=lambda s: s.get("installs", 0), reverse=True)
    return skills[:_MAX_SKILLS_PER_QUERY]


def _skill_exists_locally(root: Path, skill_name: str) -> bool:
    """Check if a skill directory with SKILL.md already exists under .codex/skills/."""
    skill_dir = root / ".codex" / "skills" / skill_name
    return skill_dir.is_dir() and (skill_dir / "SKILL.md").exists()


def _parse_installs_value(raw: str) -> int:
    """Parse install-count strings like '585.8K' or '1.4K' or '50' into integers."""
    raw = raw.replace(",", "").strip()
    if raw.endswith("K"):
        try:
            return int(float(raw[:-1]) * 1000)
        except ValueError:
            return 0
    if raw.endswith("M"):
        try:
            return int(float(raw[:-1]) * 1000000)
        except ValueError:
            return 0
    try:
        return int(raw)
    except ValueError:
        return 0


def _install_skill_via_npx(
    root: Path,
    package: str,
    skill_name: str,
    dry_run: bool,
) -> dict[str, Any]:
    """Install a skill from the internet using npx skills add with --copy.

    Uses ``npx skills add <package> --skill <skill-name> --yes --copy``
    to copy the skill files into the project.
    """
    result = configure_result(
        "InstallInternetSkill", dry_run, write_enabled=not dry_run
    )

    if dry_run:
        result["actions"].append({
            "path": f".codex/skills/{skill_name}",
            "key": "internet.install",
            "severity": "info",
            "message": f"Would install '{skill_name}' from {package} via npx skills add.",
            "phase": "apply",
        })
        result["skillName"] = skill_name
        result["valid"] = True
        return result

    cmd = ["npx", "skills", "add", package, "--skill", skill_name, "--yes", "--copy"]
    try:
        install_result = run_native(cmd, root, timeout=60)
        if install_result["returncode"] == 0:
            result["actions"].append({
                "path": f".codex/skills/{skill_name}",
                "key": "internet.installed",
                "severity": "info",
                "message": f"Skill '{skill_name}' installed from {package} via npx skills add.",
                "phase": "apply",
            })
            result["skillName"] = skill_name
            result["valid"] = True
        else:
            from .tool_installer import install_skill_from_github

            # Fallback: try the GitHub copy approach using the source repo
            # Note: GitHub repos may store skills at different paths; we try
            # 'skills/<skill_name>' as a common convention.
            fallback_res = install_skill_from_github(
                root=root,
                repo=package,
                skill_path=f"skills/{skill_name}",
                skill_name=skill_name,
                dry_run=False,
            )
            fallback_valid = fallback_res.get("valid", False)
            result["actions"].append({
                "path": f".codex/skills/{skill_name}",
                "key": "internet.fallback",
                "severity": "info" if fallback_valid else "warning",
                "message": (
                    f"npx skills add failed. GitHub fallback {'succeeded' if fallback_valid else 'also failed'}."
                ),
                "phase": "apply",
            })
            result["skillName"] = skill_name
            result["valid"] = fallback_valid
            for action in fallback_res.get("actions", []):
                result["actions"].append(action)
            for finding in fallback_res.get("findings", []):
                result["findings"].append(finding)
    except Exception as ex:
        result["actions"].append({
            "path": f"skill/{skill_name}",
            "key": "internet.error",
            "severity": "warning",
            "message": f"Could not install '{skill_name}' from internet: {ex}",
            "phase": "apply",
        })
        result["skillName"] = skill_name
        result["valid"] = False

    return result


def _update_manifest_with_skills(
    root: Path,
    installed: list[dict[str, Any]],
    dry_run: bool,
) -> dict[str, Any]:
    """Update .codex/skills/manifest.json to include newly installed internet skills.

    Creates or updates a ``"stack"`` category with ``stackTags`` matching the
    installed skill names, so :func:`discover_project_guidance` can find them
    and agents can discover what skills are available for their task.
    """
    result = configure_result(
        "UpdateManifest", dry_run, write_enabled=not dry_run
    )

    manifest_path = root / ".codex" / "skills" / "manifest.json"
    if manifest_path.exists():
        manifest = read_json(manifest_path, optional=False)
    else:
        manifest = {
            "schemaVersion": "1.0",
            "description": "Maps task types to skill paths.",
            "categories": {},
        }

    categories = manifest.get("categories", {})
    if not isinstance(categories, dict):
        categories = {}

    # Collect newly installed skill names
    new_skill_names: set[str] = set()
    for install_result in installed:
        sname = install_result.get("skillName", "")
        if sname and install_result.get("valid", False):
            new_skill_names.add(sname)

    if not new_skill_names:
        result["actions"].append({
            "path": ".codex/skills/manifest.json",
            "key": "manifest.update",
            "severity": "info",
            "message": "No new skills installed; manifest unchanged.",
            "phase": "audit",
        })
        result["valid"] = True
        return result

    # Upsert the "stack" category with stackTags so discover_project_guidance() can find them
    if "stack" not in categories:
        categories["stack"] = {
            "description": "Stack-relevant skills (installed from internet based on project profile)",
            "skills": [],
            "stackTags": [],
        }

    stack_cat = categories["stack"]
    if not isinstance(stack_cat, dict):
        stack_cat = {"description": "", "skills": [], "stackTags": []}
        categories["stack"] = stack_cat

    existing_skills = set(stack_cat.get("skills", []))
    existing_tags = set(stack_cat.get("stackTags", []))

    for sname in sorted(new_skill_names):
        skill_path = f"{sname}/SKILL.md"
        if skill_path not in existing_skills:
            existing_skills.add(skill_path)
            result["actions"].append({
                "path": skill_path,
                "key": "manifest.add-skill",
                "severity": "info",
                "message": f"Added '{skill_path}' to manifest 'stack' category.",
                "phase": "apply",
            })
        if sname not in existing_tags:
            existing_tags.add(sname)

    stack_cat["skills"] = sorted(existing_skills)
    stack_cat["stackTags"] = sorted(existing_tags)
    manifest["categories"] = categories

    if not dry_run:
        write_json(manifest_path, manifest)
        result["actions"].append({
            "path": ".codex/skills/manifest.json",
            "key": "manifest.written",
            "severity": "info",
            "message": f"Updated manifest with {len(new_skill_names)} new skill(s) in 'stack' category.",
            "phase": "apply",
        })

    result["newSkills"] = sorted(new_skill_names)
    result["valid"] = True
    return result


def setup_project_guidance(
    root: Path, values: dict[str, Any], dry_run: bool = False
) -> dict[str, Any]:
    """Search the internet for stack-relevant skills, install them, update manifest.

    Called after the user sets their project stack (frontend, backend, database).
    The flow:

    1. Reads stack values from ``values`` or the project profile
    2. For each stack value, searches the public skills.sh registry via
       ``npx skills find <query>`` and picks the top results by popularity
    3. Installs each skill via ``npx skills add`` (falls back to GitHub copy)
    4. Updates ``.codex/skills/manifest.json`` with the new skills and their
       stack category tags, so :func:`discover_project_guidance` and agents
       can discover what skills are available for each task

    Args:
        root: Repository root.
        values: Stack values (keys: frontend, backend, database).
        dry_run: If True, only report what would be done (no side effects).

    Returns:
        Dict with mode, valid, actions, per-skill internet results, and manifest status.
    """
    result = configure_result(
        "SetupProjectGuidance", dry_run, write_enabled=not dry_run
    )

    # 1. Read stack values — accept raw strings or read from profile
    stack_values: dict[str, str] = {}
    for domain in ("frontend", "backend", "database"):
        if domain in values and values[domain]:
            raw = _normalize_stack_value(values[domain])
            if raw:
                stack_values[domain] = raw

    if not stack_values:
        profile = load_project_profile(root)
        profile_stack = profile.get("stack", {})
        if isinstance(profile_stack, dict):
            for domain in ("frontend", "backend", "database"):
                entry = profile_stack.get(domain, {})
                if isinstance(entry, dict):
                    if entry.get("applies") is True:
                        raw = str(entry.get("value", "")).lower().strip()
                        if raw:
                            stack_values[domain] = raw
                elif isinstance(entry, str):
                    raw = entry.lower().strip()
                    if raw and raw not in ("none", "n/a", "na"):
                        stack_values[domain] = raw

    result["stackInput"] = stack_values

    if not stack_values:
        result["actions"].append({
            "path": "stack",
            "key": "guidance.skip",
            "severity": "info",
            "message": "No stack values provided or configured. Skipping project guidance setup.",
            "phase": "audit",
        })
        result["valid"] = True
        return result

    # 2. Search internet for each stack value
    #    Split compound values like "React + TypeScript" into tokens
    all_internet_skills: list[dict[str, Any]] = []
    seen_package_skill: set[str] = set()

    for domain, raw_value in sorted(stack_values.items()):
        tokens = raw_value.replace("+", " ").replace(",", " ").replace("/", " ").split()
        for token in tokens:
            token_clean = token.strip().lower()
            if not token_clean:
                continue

            result["actions"].append({
                "path": f"internet-search/{domain}",
                "key": "search.query",
                "severity": "info",
                "message": f"Searching internet for skills matching '{token_clean}'.",
                "phase": "audit",
            })

            found = _search_skills_internet(root, token_clean, dry_run)
            for skill in found:
                ps = skill.get("package_skill", "")
                if ps and ps not in seen_package_skill:
                    seen_package_skill.add(ps)
                    all_internet_skills.append(skill)
                    result["actions"].append({
                        "path": f"internet/{skill['package']}/{skill['skill']}",
                        "key": "internet.found",
                        "severity": "info",
                        "message": (
                            f"Found '{skill['skill']}' from {skill['package']} "
                            f"({skill['installs']:,} installs)."
                        ),
                        "phase": "audit",
                    })

    result["foundSkills"] = [s["package_skill"] for s in all_internet_skills]

    if not all_internet_skills:
        result["actions"].append({
            "path": "stack",
            "key": "internet.no-results",
            "severity": "info",
            "message": "No skills found on the internet for the configured stack values.",
            "phase": "audit",
        })
        result["valid"] = True
        return result

    # 3. Check each discovered skill locally — skip if already installed
    install_results: list[dict[str, Any]] = []
    for skill in all_internet_skills:
        package = skill.get("package", "")
        skill_name = skill.get("skill", "")
        if not package or not skill_name:
            continue

        # Idempotency: skip if the skill already exists on disk
        if _skill_exists_locally(root, skill_name):
            result["actions"].append({
                "path": f".codex/skills/{skill_name}",
                "key": "internet.skipped",
                "severity": "info",
                "message": f"Skill '{skill_name}' already exists locally — skipping install.",
                "phase": "audit",
            })
            # Record a valid pseudo-result so manifest update picks it up
            install_results.append({"valid": True, "skillName": skill_name})
            continue

        install_res = _install_skill_via_npx(root, package, skill_name, dry_run)
        install_results.append(install_res)
        for action in install_res.get("actions", []):
            result["actions"].append(action)
        for finding in install_res.get("findings", []):
            result["findings"].append(finding)

    result["installResults"] = install_results

    # 4. Update manifest with newly installed skills
    manifest_result = _update_manifest_with_skills(root, install_results, dry_run)
    for action in manifest_result.get("actions", []):
        result["actions"].append(action)
    for finding in manifest_result.get("findings", []):
        result["findings"].append(finding)

    result["valid"] = not any(
        item.get("severity") == "error" for item in result["findings"]
    )
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
