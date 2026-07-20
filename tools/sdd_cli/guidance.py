"""Project guidance: discover, map, acquire recommendations and skills."""

from __future__ import annotations

import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from ._shared import (
    REPO_ROOT,
    SEARCH_PLAN_ID,
    CliError,
    add_bucket_item,
    build_recommendations,
    build_research_topics,
    build_stack_context_findings,
    configure_result,
    detect_stack_tags,
    ensure_used_in_steps,
    load_project_profile,
    load_tool_recommendations_catalog,
    merge_dicts,
    nested,
    parse_pairs,
    run_native,
    write_json,
)


# ── Discover ─────────────────────────────────────────────────────────────

def discover_project_guidance(root: Path, dry_run: bool = False, **values: Any) -> dict[str, Any]:
    """Detect stack, research topics, and build recommendations."""
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

    # Search for community skills from detected stack tags and general topics
    detected_tags = audit.get("detectedTags", [])
    skill_search_results = _search_skills_from_tags(root, detected_tags, dry_run or bool(values.get("confirmed")))
    if skill_search_results:
        # Add community-sourced skills to suggestions
        existing_ids = {item["id"] for item in recommendations}
        new_from_search = [s for s in skill_search_results if s["id"] not in existing_ids]
        recommendations.extend(new_from_search)
        missing_skills.extend(
            s for s in new_from_search
            if s.get("type") == "skill" and s.get("detected", True) and not s.get("targetExists", False)
        )
        # Build source summary
        source_counts: dict[str, int] = {}
        for s in new_from_search:
            sk = s.get("sourceKind", "?")
            source_counts[sk] = source_counts.get(sk, 0) + 1
        source_summary = ", ".join(f"{k}: {v}" for k, v in sorted(source_counts.items()))
        actions.append({
            "path": "community-skills", "key": "skill-search", "severity": "info",
            "message": f"Found {len(new_from_search)} community skill(s) from {len(source_counts)} source(s): {source_summary}.",
            "phase": "audit",
        })

    # Detect orphaned accepted items — items in the existing catalog's accepted list
    # that have no matching recommendation with install metadata.
    orphaned_accepted: list[str] = []
    if values.get("confirmed"):
        existing_catalog = load_tool_recommendations_catalog(root)
        existing_accepted = set(existing_catalog.get("accepted", []))
        recommendation_ids = {item["id"] for item in recommendations}
        orphaned_accepted = list(existing_accepted - recommendation_ids)
        if orphaned_accepted:
            actions.append({
                "path": ".codex/tool-recommendations.local.json",
                "key": "orphaned-accepted-items",
                "severity": "warning",
                "message": f"{len(orphaned_accepted)} accepted item(s) have no installable recommendation: {', '.join(orphaned_accepted)}. "
                           f"These items are recorded as accepted but no matching skill or reference exists in the catalog. "
                           f"Consider adding them to .codex/tool-recommendations.common.json or removing from the accepted list.",
                "phase": "audit",
            })
    write_enabled = bool(values.get("confirmed") and values.get("persistLocal") and not dry_run)
    if write_enabled:
        existing_catalog = load_tool_recommendations_catalog(root)
        existing_by_id = {item.get("id"): item for item in existing_catalog.get("recommendations", [])}
        persisted_recommendations = []
        for item in recommendations:
            if item.get("type") not in {"skill", "mcp", "plugin", "tool", "practice", "standard", "reference"}:
                continue
            persisted = merge_dicts(existing_by_id.get(item.get("id"), {}), ensure_used_in_steps(item))
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
            "notRecommended": existing_catalog.get("notRecommended", []) + [
                item for item in recommendations if item["id"] == "openproject-mcp-for-ticket-delivery"
            ],
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
            "recommendations": [ensure_used_in_steps(item) for item in
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
        install_method = item.get("installMethod", "")
        # Handle reference-only items — no binary install needed, just documentation alignment
        if install_method == "manual-reference":
            result["actions"].append({
                "path": name, "key": "manual-reference", "severity": "info",
                "message": f"Reference-only guidance '{name}' — consult source {item.get('source', 'N/A')} and ensure target {item.get('target', 'N/A')} aligns.",
                "phase": "plan",
            })
            continue
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
        # Handle skills-cli-add — install via npx skills add
        if install_method == "skills-cli-add":
            install_cmd = item.get("installCommand", "")
            if install_cmd:
                if dry_run:
                    result["actions"].append({"path": name, "key": "skills-cli-add", "severity": "info",
                                              "message": f"Would run: {install_cmd}", "phase": "plan"})
                else:
                    install_result = run_native(install_cmd.split(), root, timeout=120)
                    if install_result["returncode"] == 0:
                        result["actions"].append({"path": name, "key": "skills-cli-add", "severity": "info",
                                                  "message": f"Installed skill via {install_cmd}", "phase": "apply"})
                        # After installing a skill into .codex/skills, sync to .cline/skills via create_skill_links.py
                        skill_links_script = root / ".cline" / "create_skill_links.py"
                        if skill_links_script.exists():
                            links_result = run_native([sys.executable, str(skill_links_script)], root, timeout=30)
                            if links_result["returncode"] == 0:
                                result["actions"].append({"path": ".cline/skills", "key": "skill-links", "severity": "info",
                                                          "message": f"Ran create_skill_links.py to sync .codex/skills → .cline/skills.", "phase": "apply"})
                            else:
                                add_bucket_item(
                                    result["findings"], ".cline/create_skill_links.py", "link-failed",
                                    f"Could not sync skills to .cline: {links_result['stderr'][:200]}",
                                    "warning", "apply",
                                )
                        else:
                            add_bucket_item(
                                result["findings"], ".cline/create_skill_links.py", "script-missing",
                                "create_skill_links.py not found — .cline/skills will not be synced.",
                                "warning", "post-start",
                            )
                    else:
                        add_bucket_item(
                            result["findings"], name, "install.failed",
                            f"Could not install skill '{name}': {install_result['stderr'][:200]}",
                            "warning", "apply",
                        )
            else:
                add_bucket_item(
                    result["findings"], name, "install.no-command",
                    f"skills-cli-add item '{name}' has no installCommand.",
                    "warning", "pre-start",
                )
            continue
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
                except Exception:
                    pass
            else:
                # Fallback: extract name via regex
                name_m = re.search(r"(?m)^name:\s*(.+)$", fm_match.group(1))
                if name_m:
                    name = name_m.group(1).strip().strip('"')
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

def set_recommended_tools(root: Path, values: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    """Set accepted/dismissed tool recommendations in tool-recommendations.local.json."""
    from ._shared import configure_result, read_json, write_json as _write_json
    result = configure_result("SetRecommendedTools", dry_run, write_enabled=not dry_run)
    path = root / ".codex" / "tool-recommendations.local.json"
    if "accepted" not in values and "dismissed" not in values:
        return {"mode": "SetRecommendedTools", "valid": False,
                "errors": ["values.accepted or values.dismissed is required."]}
    config = read_json(path, optional=True) if path.exists() else {
        "schemaVersion": 1, "mode": "guarded-auto",
        "detectedTags": [], "researchTopics": [],
        "accepted": [], "dismissed": [],
        "recommendations": [], "notRecommended": [],
    }
    for key in ("accepted", "dismissed"):
        existing = list(config.get(key, []))
        for item in values.get(key, []):
            if item not in existing:
                existing.append(item)
        config[key] = existing
        if values.get(key):
            result["actions"].append({"path": ".codex/tool-recommendations.local.json", "key": f"recommendedTools.{key}",
                                      "severity": "info", "message": f"Recorded {key} recommendation ids.", "phase": "apply"})
    result["valid"] = True
    if not dry_run:
        _write_json(path, config)
    return result


def run_guidance(args: list[str]) -> int:
    """CLI entry point for guidance commands."""
    import json as _json
    if not args:
        print("Available: discover, map, acquire, set-recommended-tools, write-skill-index", file=sys.stderr)
        return 1
    subcommand = args[0]
    options = parse_pairs(args[1:])
    root = Path(options.get("root", REPO_ROOT))
    dry_run = options.get("dry-run", "false").lower() == "true"
    handlers: dict[str, Any] = {
        "discover": lambda: _discover_handler(root, dry_run, options),
        "map": lambda: _map_handler(root, dry_run, options),
        "acquire": lambda: _acquire_handler(root, dry_run, options),
        "set-recommended-tools": lambda: set_recommended_tools(root, _parse_set_recommended_values(options), dry_run),
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
    import json as _json
    guidance_json = options.get("finalConfirmedGuidance", "[]")
    try:
        guidance = _json.loads(guidance_json) if guidance_json else []
    except Exception:
        guidance = []
    return acquire_project_guidance(root, dry_run, finalConfirmedGuidance=guidance)


# ── Private helpers ──────────────────────────────────────────────────────

def _parse_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_set_recommended_values(options: dict[str, str]) -> dict[str, Any]:
    """Parse accepted/dismissed JSON arrays from CLI options."""
    import json as _json
    values: dict[str, Any] = {}
    for key in ("accepted", "dismissed"):
        raw = options.get(key, "[]")
        try:
            values[key] = _json.loads(raw) if raw else []
        except _json.JSONDecodeError:
            values[key] = []
    return values


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


# ── Multi-source skill search ──────────────────────────────────────────────
# Source registry: each source is a callable with signature:
#   fn(root, search_queries, detected_tags, found_ids, dry_run)
#   -> list[dict[str, Any]]
# Sources are tried in registry order; results dedup'd by unique_id across all sources.
# To add a new source:
#   1. Define a _source_<name>() function with the above signature
#   2. Add it to _SKILL_SOURCES and _SOURCE_FUNCTIONS below
# The source_kind set via _build_skill_entry() becomes the prefix for skill IDs.


_TAG_QUERIES: dict[str, str] = {
    "react": "react",
    "typescript": "typescript",
    "csharp": "csharp .net",
    "aspnetcore": "aspnetcore",
    "sqlite": "sqlite",
    "entityframework": "entity-framework",
    "python": "python",
    "fastapi": "fastapi",
    "postgresql": "postgresql",
    "javascript": "javascript",
    "node": "nodejs",
}
_DEFAULT_BLOCK_TAGS: set[str] = {"br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section"}


class _HtmlToText(HTMLParser):
    """Extract visible text from HTML, preserving line breaks at block boundaries.

    Strips all HTML tags. Inserts newlines when entering/exiting block-level
    elements so the extracted text preserves the document's line structure.
    """

    def __init__(self, block_tags: set[str] | None = None) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._block_tags = block_tags if block_tags is not None else _DEFAULT_BLOCK_TAGS

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._block_tags:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._block_tags:
            self._parts.append("\n")

    def text(self) -> str:
        return re.sub(r"\n{3,}", "\n\n", "".join(self._parts))


_GENERAL_TOPICS: list[tuple[str, str]] = [
    ("clean-architecture", "clean architecture"),
    ("clean-code", "clean code"),
    ("solid-principles", "SOLID principles"),
    ("best-practices", "software best practices"),
]


def _build_skill_entry(
    unique_id: str,
    display_name: str,
    source_kind: str,
    install_method: str,
    install_command: str,
    source_url: str,
    skill_name: str,
    detected_tags: list[str],
    purpose: str,
) -> dict[str, Any]:
    """Build a standard skill recommendation entry.

    Uses module-level _GENERAL_TOPICS for tag alignment.
    """
    skill_lower = skill_name.lower()
    aligned_tags = [tag for tag in detected_tags if tag in skill_lower]
    if not aligned_tags:
        for topic_id, topic_query in _GENERAL_TOPICS:
            if topic_id in skill_lower or topic_query.split()[0] in skill_lower:
                aligned_tags.append(topic_id.replace("-", ""))
    if not aligned_tags:
        aligned_tags = ["general"]
    return {
        "id": f"{source_kind}:{unique_id}",
        "name": display_name,
        "type": "skill",
        "requires": aligned_tags,
        "purpose": purpose,
        "installMethod": install_method,
        "installCommand": install_command,
        "source": f"{source_kind}:{unique_id}",
        "sourceUrl": source_url,
        "target": f".codex/skills/{skill_name}/SKILL.md",
        "validation": f"Test-Path .\\.codex\\skills\\{skill_name}\\SKILL.md",
        "sourceKind": source_kind,
        "installScope": "repo-local",
        "installerKind": "skills-cli" if install_method == "skills-cli-add" else "web",
        "detected": True,
        "targetExists": False,
        "requiresIdeRestart": False,
        "requiresSystemReboot": False,
        "userActionRequired": False,
        "usedInSteps": [],
    }


def _source_npx_skills(
    root: Path,
    search_queries: list[str],
    detected_tags: list[str],
    found_ids: set[str],
    dry_run: bool,
) -> list[dict[str, Any]]:
    """Source: npx skills find CLI — queries the skills.sh registry (community skills).

    Signature: (root, search_queries, detected_tags, found_ids, dry_run) -> list[dict]
    See _SKILL_SOURCES / _SOURCE_FUNCTIONS for the source registry pattern.
    """
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    skill_line_re = re.compile(r"^(\S+?)/(\S+?)@(\S+?)\s+([\d.]+[KMB]?)\s+installs$")
    url_line_re = re.compile(r"^└\s+(https?://\S+)$")

    results: list[dict[str, Any]] = []

    for query in search_queries:
        if dry_run:
            continue
        output = run_native(["npx", "skills", "find", query], root, timeout=60)
        if output["returncode"] != 0 or not output["stdout"]:
            continue
        clean_stdout = ansi_escape.sub("", output["stdout"])
        lines = clean_stdout.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            skill_match = skill_line_re.match(line)
            if skill_match:
                owner = skill_match.group(1)
                repo = skill_match.group(2)
                skill_name = skill_match.group(3)
                installs_str = skill_match.group(4)
                url = ""
                if i + 1 < len(lines):
                    url_match = url_line_re.match(lines[i + 1].strip())
                    if url_match:
                        url = url_match.group(1)
                unique_id = f"{owner}/{repo}@{skill_name}"
                if unique_id not in found_ids:
                    found_ids.add(unique_id)
                    display_name = f"{skill_name.replace('-', ' ').replace(':', ' ').title()} ({owner}/{repo})"
                    entry = _build_skill_entry(
                        unique_id=unique_id,
                        display_name=display_name,
                        source_kind="skills-sh",
                        install_method="skills-cli-add",
                        install_command=f"npx skills add {owner}/{repo}@{skill_name}",
                        source_url=url,
                        skill_name=skill_name,
                        detected_tags=detected_tags,
                        purpose=f"Community skill from {owner}/{repo} — {installs_str} installs.",
                    )
                    results.append(entry)
                i += 2
            else:
                i += 1
    return results


def _source_officialskills_web(
    root: Path,
    search_queries: list[str],
    detected_tags: list[str],
    found_ids: set[str],
    dry_run: bool,
) -> list[dict[str, Any]]:
    """Source: officialskills.sh — curated official skills from vendor dev teams.

    Uses stdlib HTMLParser to extract skill entries: number → name → vendor → description.
    Signature: (root, search_queries, detected_tags, found_ids, dry_run) -> list[dict]
    """
    import urllib.request

    if dry_run:
        return []

    results: list[dict[str, Any]] = []
    official_url = "https://officialskills.sh/"

    # ── Fetch HTML ──────────────────────────────────────────────────────
    try:
        req = urllib.request.Request(official_url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; SDD-CLI/1.0)",
            "Accept": "text/html",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return []

    # ── Extract visible text preserving line structure ───────────────────
    extractor = _HtmlToText()
    extractor.feed(html)
    text = extractor.text()

    # Find the "Find Skills" section header
    find_idx = text.find("Find Skills")
    if find_idx < 0:
        # Try a broader search — look for "Official Agent Skills" or "Browse Official Skills"
        for marker in ("Browse Official Skills", "Official Agent Skills", "Quick Stats"):
            idx = text.find(marker)
            if idx >= 0:
                find_idx = idx
                break
        if find_idx < 0:
            return []
    text = text[find_idx:]

    # ── Parse skill entries ──────────────────────────────────────────────
    # Format (after HTMLParser extraction) — numbers on their own line:
    #   \n<number>\n\n<skill-name><Vendor>/skills\n\n<description>\n
    # Example:
    #   
    #   1
    #
    #   accessibilityAddy Osmani/skills
    #
    #   Audits and improves web accessibility against WCAG 2.
    #
    #   2
    #
    #   agent-email-inboxResend/skills
    #
    #   Sets up a secure email inbox for AI agents using Resend webhooks.

    lines = text.split("\n")
    num_re = re.compile(r"^(\d+)$")
    # Matches: <skill-name><Vendor>/skills  (skill-name is lowercase-hyphen, vendor starts uppercase)
    entry_re = re.compile(
        r"^([a-z0-9][-a-z0-9]*[a-z0-9]?)"    # skill name (lowercase, hyphenated)
        r"([A-Z][A-Za-z0-9 ./-]*?)"           # vendor name (starts uppercase, non-greedy)
        r"(?:/skills)?"                        # optional /skills suffix
        r"\s*$"
    )

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        num_match = num_re.match(line)
        if not num_match:
            i += 1
            continue
        # Found a number line — look ahead for the name+vendor line
        skill_name = ""
        vendor_raw = ""
        desc = ""
        for j in range(i + 1, min(i + 6, len(lines))):
            stripped = lines[j].strip()
            if not stripped:
                continue
            # Try to parse as skill entry: name+vendor[/skills]
            em = entry_re.match(stripped)
            if em:
                skill_name = em.group(1)
                vendor_raw = em.group(2).replace("/skills", "").strip()
                # Remaining lines (up to 4) are the description
                desc_parts: list[str] = []
                for k in range(j + 1, min(j + 5, len(lines))):
                    next_s = lines[k].strip()
                    if not next_s or num_re.match(next_s):
                        break
                    if next_s == "/skills":
                        continue
                    desc_parts.append(next_s)
                desc = " ".join(desc_parts)
                break
        if not skill_name:
            i += 1
            continue
        # Check relevance: does this skill match any search query or detected tag?
        if not any(
            q.lower() in skill_name.lower() or any(t in skill_name.lower() for t in detected_tags)
            for q in search_queries
        ):
            i += 1
            continue
        unique_id = f"official:{skill_name}"
        if unique_id not in found_ids:
            found_ids.add(unique_id)
            display_name = f"{skill_name.replace('-', ' ').replace(':', ' ').title()} — Official ({vendor_raw})"
            entry = _build_skill_entry(
                unique_id=unique_id,
                display_name=display_name,
                source_kind="official-skills",
                install_method="manual-reference",
                install_command="",
                source_url="https://officialskills.sh/",
                skill_name=skill_name,
                detected_tags=detected_tags,
                purpose=f"Official skill from {vendor_raw}: {desc[:200]}." if desc else f"Official skill from {vendor_raw}.",
            )
            results.append(entry)
        i += 1

    return results


def _source_skills_web(
    root: Path,
    search_queries: list[str],
    detected_tags: list[str],
    found_ids: set[str],
    dry_run: bool,
) -> list[dict[str, Any]]:
    """Source: www.skills.sh — web scrape of the skills.sh leaderboard.

    Used as a fallback when npx CLI is not available. Parses the HTML
    leaderboard to extract: skill name, owner/repo, and install counts.
    Signature: (root, search_queries, detected_tags, found_ids, dry_run) -> list[dict]
    """
    import urllib.request

    if dry_run:
        return []

    results: list[dict[str, Any]] = []
    skills_url = "https://www.skills.sh/"

    # ── Fetch HTML ──────────────────────────────────────────────────────
    try:
        req = urllib.request.Request(skills_url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; SDD-CLI/1.0)",
            "Accept": "text/html",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return []

    # ── Extract visible text preserving line structure ───────────────────
    # skills.sh uses table-based layout — add td/table to block tags
    block_tags = _DEFAULT_BLOCK_TAGS | {"td", "table"}
    extractor = _HtmlToText(block_tags)
    extractor.feed(html)
    text = extractor.text()

    # Find the "Skills Leaderboard" section — entries start after this header
    lb_idx = text.find("Skills Leaderboard")
    if lb_idx < 0:
        return []
    section = text[lb_idx:]

    # ── Parse skill entries ──────────────────────────────────────────────
    # Format (after HTMLParser extraction):
    #   <number>
    #
    #   <skill-name>
    #
    #   <owner/repo>
    #
    #   <installs>
    #
    #   <next-number>
    #
    # Example:
    #   1
    #
    #   find-skills
    #
    #   vercel-labs/skills
    #
    #   2.6M

    lines = section.split("\n")
    num_re = re.compile(r"^\d+$")
    aggregate_re = re.compile(r"^\+\d+\s+more from")

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not num_re.match(line):
            i += 1
            continue

        # Found a ranking number — collect the next 3 non-empty, non-aggregate values
        values: list[str] = []
        for j in range(i + 1, min(i + 12, len(lines))):
            s = lines[j].strip()
            if not s:
                continue
            if aggregate_re.match(s):
                values = []  # aggregate rows have no individual skill data
                break
            if num_re.match(s):
                break  # reached next entry without completing — incomplete data
            values.append(s)
            if len(values) == 3:
                break

        if len(values) == 3:
            skill_name, owner_repo, installs_str = values
            # Validate: owner/repo must contain a slash
            if "/" in owner_repo:
                # Check relevance: does this skill match any search query or detected tag?
                if any(
                    q.lower() in skill_name.lower() or q.lower() in owner_repo.lower()
                    or any(t in skill_name.lower() for t in detected_tags)
                    for q in search_queries
                ):
                    unique_id = f"{owner_repo}@{skill_name}"
                    if unique_id not in found_ids:
                        found_ids.add(unique_id)
                        display_name = f"{skill_name.replace('-', ' ').replace(':', ' ').title()} ({owner_repo})"
                        entry = _build_skill_entry(
                            unique_id=unique_id,
                            display_name=display_name,
                            source_kind="skills-sh-web",
                            install_method="skills-cli-add",
                            install_command=f"npx skills add {owner_repo}@{skill_name}",
                            source_url="https://www.skills.sh/",
                            skill_name=skill_name,
                            detected_tags=detected_tags,
                            purpose=f"Community skill from {owner_repo} — {installs_str} installs.",
                        )
                        results.append(entry)
        i += 1

    return results


# Source registry — order determines priority for dedup (first source wins)
# Each source is keyed by its registry name and mapped to a callable.
# "skills-sh" = skills.sh community registry via npx CLI (https://www.skills.sh/)
# "skills-sh-web" = skills.sh web scrape fallback when npx CLI is not available
# "officialskills-web" = officialskills.sh curated directory (https://officialskills.sh/)
# Add new sources by appending to this list and adding a matching function below.
_SKILL_SOURCES = ["skills-sh", "skills-sh-web", "officialskills-web"]
_SOURCE_FUNCTIONS: dict[str, Any] = {
    "skills-sh": _source_npx_skills,
    "skills-sh-web": _source_skills_web,
    "officialskills-web": _source_officialskills_web,
}


def _search_skills_from_tags(root: Path, detected_tags: list[str], dry_run: bool) -> list[dict[str, Any]]:
    """Search for skills from ALL configured sources.

    Queries each source in registry order, deduplicating by ID.
    Covers: skills.sh (via npx CLI), officialskills.sh (via web fetch),
    and any future sources added to the _SKILL_SOURCES registry.
    """
    search_queries: list[str] = []

    # Build search queries from detected tags
    for tag in detected_tags:
        query = _TAG_QUERIES.get(tag)
        if query and query not in search_queries:
            search_queries.append(query)

    # Always add general topics
    for _, query in _GENERAL_TOPICS:
        if query not in search_queries:
            search_queries.append(query)

    if not search_queries:
        return []

    all_results: list[dict[str, Any]] = []
    found_ids: set[str] = set()
    source_counts: dict[str, int] = {}

    for source_name in _SKILL_SOURCES:
        source_fn = _SOURCE_FUNCTIONS.get(source_name)
        if source_fn is None:
            continue
        try:
            source_results =        source_fn(
                root, search_queries, detected_tags, found_ids, dry_run
            )
            if source_results:
                source_counts[source_name] = len(source_results)
                all_results.extend(source_results)
        except Exception as _exc:
            # Source failed — log to stderr rather than crashing the whole search
            import sys
            import traceback
            traceback.print_exc(file=sys.stderr)
            print(f"[guidance] source '{source_name}' failed — skipping.", file=sys.stderr)

    return all_results


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
