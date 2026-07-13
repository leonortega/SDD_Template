"""Project guidance: discover, map, acquire recommendations and skills."""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path
from typing import Any

from ._shared import (
    REPO_ROOT,
    SEARCH_PLAN_ID,
    CliError,
    add_bucket_item,
    any_contains,
    build_recommendations,
    build_research_topics,
    build_stack_context_findings,
    configure_result,
    detect_stack_tags,
    load_project_profile,
    load_tool_recommendations_catalog,
    merge_dicts,
    nested,
    read_json,
    run_native,
    write_json,
)


# ── Discover ─────────────────────────────────────────────────────────────

def discover_project_guidance(root: Path, dry_run: bool = False, **values: Any) -> dict[str, Any]:
    """Detect stack, research topics, and build recommendations."""
    result = configure_result("DiscoverProjectGuidance", dry_run, write_enabled=False)
    audit_values = {**values, "skipAutoDiscovery": True}
    audit = _audit_recommended_tools(root, dry_run, **audit_values)
    blockers = [item for item in audit.get("findings", []) if item.get("severity") == "error"]
    if blockers:
        return {
            "mode": "DiscoverProjectGuidance", "valid": False, "writeEnabled": False,
            "detectedTags": audit.get("detectedTags", []),
            "researchTopics": audit.get("researchTopics", []),
            "findings": blockers,
            "errors": [item["message"] for item in blockers],
            "actions": [],
        }
    recommendations = [item for item in audit["recommendations"] if item["id"] != SEARCH_PLAN_ID]
    missing_skills = [item for item in recommendations if item.get("type") == "skill" and item.get("detected", True) and not item.get("targetExists", False)]
    suggested_guidance = [item for item in recommendations if item.get("type") != "skill"]
    user_added = _normalize_added_guidance(values.get("additionalSkills", []))
    final_confirmed = recommendations + user_added if values.get("confirmed") else []
    local_path = root / ".codex" / "tool-recommendations.local.json"
    actions: list[dict[str, str]] = []
    write_enabled = bool(values.get("confirmed") and values.get("persistLocal") and not dry_run)
    if write_enabled:
        existing_catalog = load_tool_recommendations_catalog(root)
        existing_by_id = {item.get("id"): item for item in existing_catalog.get("recommendations", [])}
        persisted_recommendations = []
        for item in recommendations:
            if item.get("type") not in {"skill", "mcp", "plugin", "tool", "practice", "standard", "reference"}:
                continue
            persisted = merge_dicts(existing_by_id.get(item.get("id"), {}), _ensure_used_in_steps(item))
            persisted_recommendations.append(persisted)
        payload = {
            "schemaVersion": 1,
            "mode": "guarded-auto",
            "sourceCatalog": ".codex/tool-recommendations.example.json",
            "detectedTags": audit["detectedTags"],
            "researchTopics": audit["researchTopics"],
            "accepted": existing_catalog.get("accepted", []),
            "dismissed": existing_catalog.get("dismissed", []),
            "recommendations": persisted_recommendations,
            "notRecommended": merge_dicts(
                existing_catalog.get("notRecommended", []),
                [item for item in recommendations if item["id"] == "openproject-mcp-for-ticket-delivery"],
            ),
        }
        write_json(local_path, payload)
        actions.append({"path": ".codex/tool-recommendations.local.json", "key": "persist-local-catalog",
                        "severity": "info", "message": "Persist local project guidance catalog.", "phase": "apply"})
    return {
        "mode": "DiscoverProjectGuidance",
        "valid": True,
        "writeEnabled": write_enabled,
        "detectedTags": audit["detectedTags"],
        "researchTopics": audit["researchTopics"],
        "existingSkills": [],
        "suggestedMissingSkills": missing_skills,
        "suggestedGuidance": suggested_guidance,
        "userAddedRequestedGuidance": user_added,
        "finalConfirmedGuidance": final_confirmed,
        "finalConfirmedSkills": [],
        "discoverySourcePriority": [
            "repo-local", "openai-official", "tool-official", "technology-owner",
            "skills-cli", "marketplace", "community",
        ],
        "localRecommendationsPath": ".codex/tool-recommendations.local.json",
        "nextUserQuestion": "Confirm these suggestions to record and install/configure supported items now.",
        "actions": actions,
    }


# ── Map ──────────────────────────────────────────────────────────────────

def map_project_guidance_step(root: Path, workflow_step: str, recommendation_ids: list[str], dry_run: bool = False) -> dict[str, Any]:
    """Map recommendations to a workflow step."""
    if not workflow_step:
        return {"mode": "MapProjectGuidanceStep", "valid": False,
                "errors": ["values.workflowStep is required."]}
    path = root / ".codex" / "tool-recommendations.local.json"
    current = load_tool_recommendations_catalog(root)
    if not current:
        current = {
            "schemaVersion": 1,
            "mode": "guarded-auto",
            "sourceCatalog": ".codex/tool-recommendations.example.json",
            "detectedTags": [],
            "researchTopics": [],
            "recommendations": [_ensure_used_in_steps(item) for item in
                                build_recommendations(root, detect_stack_tags(root),
                                                      build_research_topics(detect_stack_tags(root)))
                                if item["id"] != SEARCH_PLAN_ID],
            "notRecommended": [],
        }
    ids = set(recommendation_ids)
    for item in current.get("recommendations", []):
        if item.get("id") not in ids:
            continue
        used = item.setdefault("usedInSteps", [])
        if workflow_step not in used:
            used.append(workflow_step)
    if not dry_run:
        write_json(path, current)
    return {"mode": "MapProjectGuidanceStep", "valid": True, "writeEnabled": not dry_run,
            "changed": True, "path": str(path), "dryRun": dry_run}


# ── Acquire ──────────────────────────────────────────────────────────────

def acquire_project_guidance(root: Path, dry_run: bool = False, **values: Any) -> dict[str, Any]:
    """Plan/record final confirmed guidance actions."""
    result = configure_result("AcquireProjectGuidance", dry_run, write_enabled=not dry_run)
    final_guidance = values.get("finalConfirmedGuidance", [])
    restart_items: list[str] = []
    for item in final_guidance:
        if "installCommand" in item:
            raise CliError(f"{item.get('name', item.get('id', 'guidance'))} rejects installCommand.")
        name = item.get("name", item.get("id", "guidance"))
        if item.get("installPreference") == "docker-preferred":
            docker = item.get("dockerAlternative")
            if docker and docker.get("image"):
                result["actions"].append({"path": name, "key": "docker-preferred", "severity": "info",
                                          "message": f"Use Docker-preferred runtime {docker['image']}.", "phase": "plan"})
            else:
                result["warnings"].append({"path": name, "key": "docker-preferred.blocked", "severity": "warning",
                                           "message": "Docker-preferred metadata is incomplete.", "phase": "plan"})
        if item.get("userActionRequired"):
            result["warnings"].append({"path": name, "key": "guarded-install-plan", "severity": "warning",
                                       "message": "User action is required for this guarded install.", "phase": "plan"})
        if item.get("installMethod") == "manual-copy" and item.get("sourceKind") is None:
            result["warnings"].append({"path": name, "key": "validation", "severity": "warning",
                                       "message": "manual-copy guidance should include sourceKind.", "phase": "plan"})
        if item.get("requiresIdeRestart"):
            restart_items.append(f"{name} [ide-restart]")
        if item.get("requiresSystemReboot"):
            restart_items.append(f"{name} [system-reboot]")
    if restart_items:
        result["findings"].append({"path": ".", "key": "important.restart-summary", "severity": "info",
                                   "message": f"Complete all feasible installs first, then restart/reboot for: {', '.join(restart_items)}.", "phase": "handoff"})
    result["valid"] = True
    return result


# ── Audit recommended tools ──────────────────────────────────────────────

def _audit_recommended_tools(root: Path, dry_run: bool = False, **values: Any) -> dict[str, Any]:
    """Detect stack and build recommendations (internal helper)."""
    detected = detect_stack_tags(root)
    topics = build_research_topics(detected, root)
    recommendations = build_recommendations(root, detected, topics)
    decisions = nested(load_tool_recommendations_catalog(root), "recommendedTools") or {}
    accepted = set(decisions.get("accepted", []))
    dismissed = set(decisions.get("dismissed", []))
    filtered = []
    for item in recommendations:
        if item.get("id") in dismissed:
            continue
        if item.get("id") in accepted:
            item["accepted"] = True
        filtered.append(item)
    findings = build_stack_context_findings(root, detected)
    metadata_finding = _stack_metadata_validation_finding(root)
    if metadata_finding:
        findings.append(metadata_finding)
    skill_gaps = [item for item in filtered if item.get("type") == "skill" and item.get("detected") and not item.get("targetExists")]
    if skill_gaps and not dry_run and not metadata_finding and not values.get("skipAutoDiscovery"):
        gap_ids = [item["id"] for item in skill_gaps]
        discovery_values = {"confirmed": gap_ids, "persistLocal": True, "additionalSkills": []}
        discovery_result = discover_project_guidance(root, dry_run=False, **discovery_values)
        findings.extend([finding for finding in discovery_result.get("findings", []) if finding.get("severity") == "error"])
        for action in discovery_result.get("actions", []):
            if action.get("key") == "persist-local-catalog":
                findings.append({"path": action["path"], "key": "project-guidance.auto-discovered", "severity": "info",
                                  "message": f"Auto-discovered and persisted {len(gap_ids)} missing skill(s): {', '.join(gap_ids)}.", "phase": "audit"})
    return {
        "mode": "AuditRecommendedTools",
        "valid": True,
        "writeEnabled": False,
        "detectedTags": detected,
        "researchTopics": topics,
        "actions": [{"path": ".", "key": "detectedStack", "severity": "info",
                     "message": f"Detected stack: {', '.join(detected)}", "phase": "audit"}],
        "findings": findings,
        "recommendations": filtered,
    }


# ── Write installed skill index ──────────────────────────────────────────

def write_skill_index(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Write or refresh the ignored installed-skill runtime index from SKILL.md files."""
    result = configure_result("WriteInstalledSkillIndex", dry_run, write_enabled=not dry_run)
    skill_root = root / ".codex" / "skills"
    if not skill_root.exists():
        return {"mode": "WriteInstalledSkillIndex", "valid": False,
                "errors": ["Skills directory not found: .codex/skills"]}
    entries: list[dict[str, Any]] = []
    cache: dict[str, dict[str, Any]] = {}
    for path in sorted(skill_root.rglob("SKILL.md")):
        skill_name = path.parent.name
        stat = path.stat()
        # Compute cache fingerprint: mtime + size
        fingerprint = f"{stat.st_mtime_ns}:{stat.st_size}"
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        # Parse frontmatter
        name = skill_name
        description = ""
        fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if fm_match:
            try:
                import yaml  # type: ignore[import]
            except ImportError:
                yaml = None
            if yaml:
                try:
                    parsed = yaml.safe_load(fm_match.group(1))
                    if isinstance(parsed, dict):
                        name = str(parsed.get("name", skill_name))
                        description = str(parsed.get("description", ""))
                except Exception:
                    pass
            else:
                # Fallback: extract name/description via regex
                name_m = re.search(r"(?m)^name:\s*(.+)$", fm_match.group(1))
                desc_m = re.search(r"(?m)^description:\s*(.+)$", fm_match.group(1))
                if name_m:
                    name = name_m.group(1).strip().strip('"')
                if desc_m:
                    description = desc_m.group(1).strip().strip('"')
        entries.append({
            "name": name,
            "path": path.relative_to(root).as_posix(),
            "relativePath": path.relative_to(skill_root.parent).as_posix(),
            "mtimeNs": stat.st_mtime_ns,
            "sizeBytes": stat.st_size,
        })
        cache[skill_name] = {"fingerprint": fingerprint}
    payload = {
        "schemaVersion": 1,
        "generatedAtUtc": int(time.time()),
        "skillCount": len(entries),
        "skills": entries,
        "cache": cache,
    }
    output_path = root / ".codex" / "installed-skill-index.local.json"
    if not dry_run:
        write_json(output_path, payload)
    result["actions"].append({"path": ".codex/installed-skill-index.local.json", "key": "write-skill-index",
                              "severity": "info", "message": f"Wrote skill index with {len(entries)} skills.", "phase": "apply"})
    result["skillCount"] = len(entries)
    result["outputPath"] = str(output_path)
    result["valid"] = True
    return result


# ── CLI entry point ──────────────────────────────────────────────────────

def run_guidance(args: list[str]) -> int:
    """CLI entry point for guidance commands."""
    import json as _json
    if not args:
        print("Available: discover, map, acquire, write-skill-index", file=sys.stderr)
        return 1
    subcommand = args[0]
    options = _parse_pairs(args[1:])
    root = Path(options.get("root", REPO_ROOT))
    dry_run = options.get("dry-run", "false").lower() == "true"
    handlers: dict[str, Any] = {
        "discover": lambda: _discover_handler(root, dry_run, options),
        "map": lambda: _map_handler(root, dry_run, options),
        "acquire": lambda: _acquire_handler(root, dry_run, options),
        "write-skill-index": lambda: write_skill_index(root, dry_run),
    }
    handler = handlers.get(subcommand)
    if not handler:
        print(f"Unknown guidance subcommand: {subcommand}", file=sys.stderr)
        return 1
    result = handler()
    print(_json.dumps(result, indent=2))
    return 0 if result.get("valid", True) else 1


def _discover_handler(root: Path, dry_run: bool, options: dict[str, str]) -> dict[str, Any]:
    confirmed = _parse_list(options.get("confirmed", ""))
    additional = _parse_json_list(options.get("additionalSkills", "[]"))
    return discover_project_guidance(
        root, dry_run,
        confirmed=confirmed,
        persistLocal=options.get("persistLocal", "false").lower() == "true",
        additionalSkills=additional,
    )


def _map_handler(root: Path, dry_run: bool, options: dict[str, str]) -> dict[str, Any]:
    step = options.get("workflowStep", "")
    ids = _parse_list(options.get("recommendationIds", ""))
    return map_project_guidance_step(root, step, ids, dry_run)


def _acquire_handler(root: Path, dry_run: bool, options: dict[str, str]) -> dict[str, Any]:
    guidance_json = options.get("finalConfirmedGuidance", "[]")
    try:
        guidance = _json.loads(guidance_json) if guidance_json else []
    except Exception:
        guidance = []
    return acquire_project_guidance(root, dry_run, finalConfirmedGuidance=guidance)


# ── Private helpers ──────────────────────────────────────────────────────

def _parse_pairs(items: list[str]) -> dict[str, str]:
    from ._shared import trim_remainder
    args = trim_remainder(items)
    pairs: dict[str, str] = {}
    index = 0
    while index < len(args):
        key = args[index]
        if not key.startswith("--"):
            raise CliError(f"Expected --option, got: {key}")
        if index + 1 >= len(args):
            raise CliError(f"Missing value for option {key}")
        pairs[key[2:]] = args[index + 1]
        index += 2
    return pairs


def _parse_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_json_list(value: str) -> list[Any]:
    import json as _json
    try:
        parsed = _json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _normalize_added_guidance(items: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, str):
            normalized.append({"name": item})
        elif isinstance(item, dict):
            normalized.append(item)
    return normalized


def _ensure_used_in_steps(item: dict[str, Any]) -> dict[str, Any]:
    clone = __import__("json").loads(__import__("json").dumps(item))
    clone.setdefault("usedInSteps", [])
    return clone


def _stack_metadata_validation_finding(root: Path) -> dict[str, str] | None:
    profile = load_project_profile(root).get("stack")
    if not isinstance(profile, dict):
        return None
    selection_recorded = profile.get("selectionRecorded") is True
    any_applies = any(
        isinstance(profile.get(domain), dict) and profile.get(domain, {}).get("applies") and str(profile.get(domain, {}).get("value", "")).strip()
        for domain in ("frontend", "backend", "database")
    )
    if not selection_recorded and not any_applies:
        return None
    if profile.get("metadataValidationStatus") == "validated":
        return None
    return {
        "key": "stack.metadata.validation",
        "severity": "error",
        "phase": "pre-discovery",
        "message": "Validate stack metadata before project guidance discovery.",
        "path": ".codex/project-profile.local.json",
    }