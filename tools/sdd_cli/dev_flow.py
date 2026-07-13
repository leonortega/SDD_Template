"""Dev flow: delivery context, ticket lock, telemetry, release manifests, audits."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import shutil

from ._shared import (
    REPO_ROOT,
    STANDARD_STAGES,
    CliError,
    add_bucket_item,
    audit_skill_contracts,
    build_recommendations,
    build_research_topics,
    build_stack_context_findings,
    classify_delivery_risk,
    classify_ticket_readiness,
    configure_result,
    detect_stack_tags,
    fail,
    format_duration,
    http_status,
    load_project_profile,
    merge_dicts,
    nested,
    new_configure_result,
    parse_time,
    profile_audit_findings,
    read_json,
    run_native,
    split_list,
    write_json,
)


# ── Delivery context ─────────────────────────────────────────────────────

def ensure_delivery_context(root: Path, values: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    """Create/update ticket delivery context lock."""
    path = root / ".codex" / "delivery-context.local.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = read_json(path, optional=True) if path.exists() else {}
    ticket_key = values.get("ticketKey")
    replace_existing = bool(values.get("replaceExisting"))
    if existing.get("ticketKey") and ticket_key and existing.get("ticketKey") != ticket_key and not replace_existing:
        raise CliError(f"Existing .codex/delivery-context.local.json points to '{existing.get('ticketKey')}'.")
    data = {
        "ticketKey": ticket_key,
        "branch": values.get("branch"),
        "openspecChange": values.get("openspecChange"),
    }
    if values.get("prNumber") is not None:
        data["prNumber"] = values.get("prNumber")
    if not dry_run:
        write_json(path, {key: value for key, value in data.items() if value is not None})
    return {
        "mode": "EnsureDeliveryContext",
        "valid": True,
        "path": str(path),
        "actions": [{"path": ".codex/delivery-context.local.json", "key": "ensure-delivery-context",
                     "severity": "info", "message": f"Create or update ticket context lock for {ticket_key}.", "phase": "apply"}],
    }


# ── Worktree local config sync ───────────────────────────────────────────

def sync_worktree_local_config(root: Path, values: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    """Copy allowlisted local config files to worktrees."""
    from ._shared import ALLOWLISTED_LOCAL_CONFIG
    result = new_configure_result("SyncWorktreeLocalConfig", dry_run, write_enabled=not dry_run)
    worktrees = [Path(path) for path in values.get("worktreePaths", [])]
    for relative in ALLOWLISTED_LOCAL_CONFIG:
        source = root / relative
        required = relative != ".codex/tool-recommendations.local.json"
        if required and not source.exists():
            add_bucket_item(result["findings"], relative, "missing.required-source",
                            f"Coordinator checkout is missing required local runtime file '{relative}'.", "error")
            continue
        if not source.exists():
            continue
        for worktree in worktrees:
            target = worktree / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            previous = target.read_text(encoding="utf-8") if target.exists() else None
            current = source.read_text(encoding="utf-8")
            if not dry_run:
                shutil.copyfile(source, target)
            message = "Overwrite allowlisted local runtime file." if previous is not None and previous != current else "Copy allowlisted local runtime file."
            result["actions"].append({"path": relative, "key": "sync.local-runtime-config", "severity": "info",
                                      "message": message, "phase": "apply"})
    result["valid"] = True
    return result


# ── Ticket lock ──────────────────────────────────────────────────────────

def validate_ticket_lock(path: Path, options: dict[str, str]) -> dict[str, Any]:
    """Validate ticket lock matches expected values."""
    if not path.exists():
        return {"path": str(path), "exists": False, "valid": True, "errors": []}
    data = read_json(path)
    errors: list[str] = []
    mapping = [
        ("ticket-key", "ticketKey"),
        ("branch", "branch"),
        ("pr-number", "prNumber"),
        ("artifact-commit-sha", "artifactCommitSha"),
        ("source-rc-version", "sourceRcVersion"),
        ("final-release-version", "finalReleaseVersion"),
    ]
    for option, field in mapping:
        expected = options.get(option)
        if expected and str(data.get(field, "")).strip() and str(data.get(field)) != expected:
            errors.append(f"{field} mismatch: lock has '{data.get(field)}', expected '{expected}'.")
    return {"path": str(path), "exists": True, "valid": not errors, "errors": errors, **data}


# ── Deployment lane ──────────────────────────────────────────────────────

def validate_deployment_lane(path: Path, options: dict[str, str]) -> dict[str, Any]:
    """Validate deployment lane ownership."""
    if not path.exists():
        return {"path": str(path), "active": False, "valid": True, "errors": []}
    data = read_json(path)
    policy = data.get("deploymentLanePolicy", "")
    owner_ticket = nested(data, "deploymentLaneOwner", "ticketKey") or ""
    owner_stage = nested(data, "deploymentLaneOwner", "stage") or ""
    ticket = options.get("ticket-key", "")
    errors: list[str] = []
    if policy == "serialized" and owner_ticket and ticket and owner_ticket != ticket:
        errors.append(f"Deployment lane is owned by '{owner_ticket}' at stage '{owner_stage}'.")
    return {"path": str(path), "active": True, "valid": not errors, "errors": errors,
            "deploymentLanePolicy": policy}


# ── Parallel delivery ────────────────────────────────────────────────────

def validate_parallel_delivery_dry_run(root: Path, input_json: str) -> dict[str, Any]:
    """Validate parallel delivery dry-run constraints."""
    data = json.loads(input_json)
    errors: list[str] = []
    tickets = data.get("tickets", [])
    if not data.get("enabled"):
        errors.append("parallelDelivery.enabled must be true.")
    active_count = len(tickets)
    max_active = int(data.get("maxActiveTickets", 0) or 0)
    if max_active and active_count > max_active:
        errors.append(f"Active ticket count '{active_count}' exceeds maxActiveTickets '{max_active}'.")
    policy = data.get("deploymentLanePolicy", "")
    if policy != "serialized":
        errors.append(f"Unsupported deploymentLanePolicy '{policy}'.")
    seen_tickets: set[str] = set()
    seen_branches: set[str] = set()
    seen_worktrees: set[str] = set()
    for ticket in tickets:
        ticket_key = ticket.get("ticketKey", "")
        branch = ticket.get("branch", "")
        worktree = ticket.get("worktreePath", "")
        if ticket_key in seen_tickets:
            errors.append(f"Duplicate ticketKey '{ticket_key}'.")
        seen_tickets.add(ticket_key)
        if branch in seen_branches:
            errors.append(f"Duplicate branch '{branch}'.")
        seen_branches.add(branch)
        if not worktree:
            errors.append(f"Ticket '{ticket_key}' is missing worktreePath.")
        elif worktree in seen_worktrees:
            errors.append(f"Duplicate worktreePath '{worktree}'.")
        seen_worktrees.add(worktree)
    owner = nested(data, "deploymentLaneOwner", "ticketKey")
    if owner and owner not in seen_tickets:
        errors.append(f"Serialized deployment lane owner '{owner}' is not an active ticket.")
    for relative in data.get("requiredLocalConfigFiles", []):
        if not (root / relative).exists():
            errors.append(f"Required local runtime file '{relative}' is missing.")
    return {"valid": not errors, "errors": errors,
            "activeTicketCount": active_count, "deploymentLanePolicy": policy}


# ── Workflow telemetry ───────────────────────────────────────────────────

def _telemetry_path(root: Path) -> Path:
    return root / ".codex" / "agent-telemetry.local.jsonl"


def initialize_workflow_telemetry(root: Path, ticket_key: str) -> dict[str, Any]:
    """Initialize workflow telemetry file."""
    path = _telemetry_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.exists()
    path.write_text("", encoding="utf-8")
    return {"exists": path.exists(), "cleared": existed, "ticketKey": ticket_key, "path": str(path)}


def append_workflow_telemetry(root: Path, ticket_key: str, input_json: str) -> dict[str, Any]:
    """Append a stage to workflow telemetry."""
    path = _telemetry_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = json.loads(input_json)
    started = parse_time(row.get("startedUtc"))
    finished = parse_time(row.get("finishedUtc"))
    if started and finished:
        row["elapsedMilliseconds"] = int((finished - started).total_seconds() * 1000)
    row["ticketKey"] = ticket_key
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, separators=(",", ":")) + "\n")
    return {"appended": True, "path": str(path)}


def read_workflow_telemetry(root: Path, ticket_key: str, input_json: str) -> dict[str, Any]:
    """Read workflow telemetry for a ticket."""
    context = json.loads(input_json)
    rows: list[dict[str, Any]] = []
    path = _telemetry_path(root)
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("ticketKey") == ticket_key:
                rows.append(row)
    stages = _collapse_stages(rows)
    return {
        "ticketKey": ticket_key,
        "status": context.get("status", ""),
        "currentRoute": context.get("currentRoute", ""),
        "totalElapsedMilliseconds": sum(stage.get("elapsedMilliseconds", 0) for stage in stages),
        "stages": stages,
    }


# ── OpenProject time telemetry ───────────────────────────────────────────

def read_openproject_time_telemetry(ticket_key: str, input_json: str) -> dict[str, Any]:
    """Read time telemetry from OpenProject."""
    data = json.loads(input_json)
    rows: list[dict[str, Any]] = []
    for entry in data.get("timeEntries", []):
        raw = nested(entry, "comment", "raw") or ""
        parsed = _parse_time_comment(raw, ticket_key)
        if parsed:
            rows.append(parsed)
    stages = _collapse_stages(rows)
    return {
        "ticketKey": ticket_key,
        "status": data.get("status", ""),
        "currentRoute": data.get("currentRoute", ""),
        "totalElapsedMilliseconds": sum(stage.get("elapsedMilliseconds", 0) for stage in stages),
        "stages": stages,
    }


def resolve_openproject_time_activity(workflow_stage: str, input_json: str) -> dict[str, Any]:
    """Resolve OpenProject activity for a workflow stage."""
    config = json.loads(input_json)
    telemetry = config.get("timeTelemetry", config)
    by_stage = telemetry.get("activityByStage", {})
    stage_config = by_stage.get(workflow_stage, {}) if isinstance(by_stage, dict) else {}
    activity_id = stage_config.get("activityId") or telemetry.get("defaultActivityId") or telemetry.get("activityId")
    activity_name = stage_config.get("activityName") or telemetry.get("defaultActivityName") or telemetry.get("activityName")
    return {
        "workflowStage": workflow_stage,
        "activityId": activity_id or "",
        "activityName": activity_name or "",
        "configuredByStage": bool(stage_config),
        "valid": bool(activity_id or activity_name),
    }


def render_openproject_time_telemetry_comment(ticket_key: str, input_json: str) -> str:
    """Render OpenProject time telemetry as markdown comment."""
    row = json.loads(input_json)
    stage = row.get("workflowStage", "")
    lines = [
        f"IA generated workflow telemetry: {ticket_key}:{stage}",
        f"agentRole: {row.get('agentRole', '')}",
        f"startedUtc: {row.get('startedUtc', '')}",
        f"finishedUtc: {row.get('finishedUtc', '')}",
        f"retryCount: {row.get('retryCount', 0)}",
        f"outcome: {row.get('outcome', '')}",
    ]
    if row.get("blockerCategory"):
        lines.append(f"blockerCategory: {row['blockerCategory']}")
    return "\n".join(lines)


# ── Ticket comment rendering ─────────────────────────────────────────────

def render_ticket_comment(comment_type: str, input_json: str) -> str:
    """Render a ticket markdown comment."""
    data = json.loads(input_json)
    if comment_type == "WorkflowTiming":
        total = int(data.get("totalElapsedMilliseconds", 0) or sum(
            int(item.get("elapsedMilliseconds", 0) or 0) for item in data.get("stages", [])))
        lines = [
            f"IA generated workflow timing: {data.get('ticketKey', '')}",
            "",
            f"**Status:** {data.get('status', '')}",
            f"- Current route: `{data.get('currentRoute', '')}`",
            f"- Total elapsed: {format_duration(total)}",
            "",
            "| Stage | Outcome | Duration | Started UTC | Finished UTC |",
            "| --- | --- | --- | --- | --- |",
        ]
        known = {stage["stage"]: stage for stage in data.get("stages", [])}
        for name in STANDARD_STAGES:
            stage = known.get(name)
            if stage:
                lines.append(
                    f"| `{name}` | {stage.get('outcome', '')} | {format_duration(stage.get('elapsedMilliseconds', 0))} | "
                    f"{stage.get('startedUtc', '-')} | {stage.get('finishedUtc', '-')} |"
                )
            else:
                lines.append(f"| `{name}` | NOT RUN / N/A | no time | - | - |")
        return "\n".join(lines)
    if comment_type == "ProdDeployment":
        tickets = ", ".join(f"`{ticket}`" for ticket in data.get("includedTickets", []))
        commit = str(data.get("commitSha", ""))[:7]
        return "\n".join([
            f"IA generated PROD deployment: {data.get('finalReleaseVersion', 'unknown')}",
            "",
            f"**Status:** {data.get('status', '')}",
            f"- Primary ticket: `{data.get('ticketKey', '')}` ({data.get('ticketState', '')})",
            f"- Included tickets: {tickets}",
            f"- Lineage: `{commit}` -> `{data.get('sourceRcVersion', '')}` -> `{data.get('finalReleaseVersion', '')}`",
            f"**PROD URL:** [open production]({data.get('prodUrl', '')})",
        ])
    marker = {
        "QADeployment": "IA generated QA deployment",
        "E2EQA": "IA generated E2E QA",
    }.get(comment_type, f"IA generated {comment_type}")
    return f"{marker}: {data.get('ticketKey', data.get('finalReleaseVersion', 'unknown'))}\n\n**Status:** {data.get('status', '')}"


# ── Audit ────────────────────────────────────────────────────────────────

def audit_skill_contracts(root: Path, include_configure: bool = False) -> dict[str, Any]:
    """Audit SKILL.md files for required sections and terms."""
    profile_findings = profile_audit_findings(root)
    skill_root = root / ".codex" / "skills"
    results: list[dict[str, Any]] = []
    support_skill_names = {"caveman", "domain-modeling", "grill-me", "grill-with-docs", "grilling",
                           "ponytail", "ponytail-audit", "ponytail-debt", "ponytail-help", "ponytail-review"}
    if not skill_root.exists():
        return {"checked": 0, "passed": 0, "failed": 0, "profilePassed": not profile_findings,
                "profileFindings": profile_findings, "providerSpecificPassed": True,
                "providerSpecificFindings": [], "results": []}
    required_sections = ["Overview", "Shared Context", "Workflow", "Output", "Failure Rules"]
    required_terms = [".codex/skills/_shared/delivery-contract.md", "docs/context-management.md", "ticket", "validation", "handoff"]
    for path in sorted(skill_root.rglob("SKILL.md")):
        skill_name = path.parent.name
        if skill_name in support_skill_names:
            continue
        if not include_configure and skill_name.startswith("configure-"):
            continue
        content = path.read_text(encoding="utf-8")
        missing_sections = [section for section in required_sections
                           if not re.search(rf"(?m)^##\s+{re.escape(section)}\s*$", content)]
        missing_terms = [term for term in required_terms if term not in content]
        results.append({
            "path": path.relative_to(root).as_posix(),
            "passed": not missing_sections and not missing_terms,
            "missingSections": missing_sections,
            "missingTerms": missing_terms,
        })
    return {
        "checked": len(results),
        "passed": sum(1 for item in results if item["passed"]),
        "failed": sum(1 for item in results if not item["passed"]),
        "profilePassed": not profile_findings,
        "profileFindings": profile_findings,
        "providerSpecificPassed": True,
        "providerSpecificFindings": [],
        "results": results,
    }


# ── Release manifests & artifact pointers ────────────────────────────────

def validate_release_manifest(path: Path) -> dict[str, Any]:
    """Validate release manifest JSON."""
    data = read_json(path)
    errors: list[str] = []
    for field in ("schemaVersion", "commitSha", "checksum", "artifactUrl", "ticketKey", "versionStatus"):
        if not data.get(field):
            errors.append(f"Missing required field: {field}")
    if data.get("commitSha") and not re.match(r"^[0-9a-fA-F]{7,40}$", str(data["commitSha"])):
        errors.append("commitSha must be 7 to 40 hex characters.")
    if data.get("sourceRcVersion") and not re.match(r"^v[0-9]+\.[0-9]+\.[0-9]+-rc\.[0-9]+$", str(data["sourceRcVersion"])):
        errors.append("sourceRcVersion must use vMAJOR.MINOR.PATCH-rc.N.")
    if data.get("finalReleaseVersion") and not re.match(r"^v[0-9]+\.[0-9]+\.[0-9]+$", str(data["finalReleaseVersion"])):
        errors.append("finalReleaseVersion must use vMAJOR.MINOR.PATCH.")
    included = data.get("includedTickets")
    if included is not None:
        if not isinstance(included, list):
            errors.append("includedTickets must be an array when present.")
        elif not included:
            errors.append("includedTickets must contain at least one ticket when present.")
        else:
            for index, ticket in enumerate(included):
                if not isinstance(ticket, str) or not ticket.strip():
                    errors.append(f"includedTickets[{index}] must be a non-empty string.")
    images = data.get("containerImages")
    if isinstance(images, list):
        for index, image in enumerate(images):
            reference = image.get("reference", "")
            if "@" not in reference:
                errors.append(f"containerImages[{index}].reference must be pinned by digest.")
    return {"path": str(path), "valid": not errors, "errors": errors}


def create_release_manifest(options: dict[str, str]) -> None:
    """Create a new release manifest."""
    output = Path(require(options, "output"))
    data = {
        "schemaVersion": 1,
        "commitSha": require(options, "commit-sha"),
        "checksum": require(options, "checksum"),
        "artifactUrl": require(options, "artifact-url"),
        "ticketKey": require(options, "ticket-key"),
        "versionStatus": options.get("version-status", "unversioned"),
    }
    write_json(output, data)


def create_artifact_pointer(options: dict[str, str]) -> None:
    """Create an artifact pointer JSON."""
    output = Path(require(options, "output"))
    commit = require(options, "artifact-commit-sha")
    ticket = require(options, "ticket-key")
    tickets = sorted(set(split_list(options.get("included-tickets", "")) or [ticket]))
    created_at = options.get("created-at-utc") or datetime.now(timezone.utc).isoformat()
    data = {
        "schemaVersion": 1,
        "version": require(options, "version"),
        "artifactCommitSha": commit,
        "canonicalPath": f"app/{commit}/",
        "releaseManifestPath": f"app/{commit}/release.json",
        "ticketKey": ticket,
        "includedTickets": tickets,
        "createdAtUtc": created_at,
    }
    write_json(output, data)


def update_release_manifest(path: Path, input_json: str) -> None:
    """Update an existing release manifest."""
    data = read_json(path, optional=True)
    data.update(json.loads(input_json))
    write_json(path, data)


def artifact_paths(commit: str, provider: str | None) -> dict[str, str]:
    """Resolve artifact paths for a commit."""
    selected = provider or selected_deployment_provider(REPO_ROOT)
    data: dict[str, str] = {
        "deploymentProvider": selected,
        "topology": f"app/{commit}/deployable-apps.json",
        "appArtifactPattern": f"app/{commit}/{{artifactName}}",
        "checksumPattern": f"app/{commit}/{{artifactName}}.sha256",
        "commitMetadata": f"app/{commit}/commit.sha",
        "releaseManifestPath": f"app/{commit}/release.json",
        "canonicalPath": f"app/{commit}/",
        "deployableAppsPath": f"app/{commit}/deployable-apps.json",
        "commitShaPath": f"app/{commit}/commit.sha",
    }
    if selected == "rancher-desktop":
        data["containerImages"] = f"app/{commit}/container-images.json"
        data["monitoringSummaryPattern"] = f"app/{commit}/monitoring-summary-{{environment}}.json"
        data["qaObservability"] = f"app/{commit}/qa-observability.json"
    return data


# ── Versioning ───────────────────────────────────────────────────────────

def next_rc_version_output(tags_text: str, target_version: str | None) -> dict[str, str]:
    """Compute next RC version from git tags."""
    finals: list[tuple[int, int, int]] = []
    rcs: list[tuple[int, int, int, int]] = []
    for tag in split_list(tags_text.replace(" ", "\n")):
        match = re.match(r"^v(\d+)\.(\d+)\.(\d+)$", tag)
        if match:
            finals.append((int(match.group(1)), int(match.group(2)), int(match.group(3))))
        elif match := re.match(r"^v(\d+)\.(\d+)\.(\d+)-rc\.(\d+)$", tag):
            rcs.append((int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))))
    if target_version:
        match = re.match(r"^v(\d+)\.(\d+)\.(\d+)$", target_version)
        if not match:
            fail("TargetVersion must use vMAJOR.MINOR.PATCH.")
        major, minor, patch = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    elif finals:
        major, minor, patch = sorted(finals)[-1]
        patch += 1
    else:
        major, minor, patch = (0, 1, 0)
    existing = [row[3] for row in rcs if row[:3] == (major, minor, patch)]
    next_rc = (max(existing) + 1) if existing else 1
    return {"targetVersion": f"v{major}.{minor}.{patch}", "nextRcVersion": f"v{major}.{minor}.{patch}-rc.{next_rc}"}


# ── Coverage / Cobertura ─────────────────────────────────────────────────

def read_coverage_threshold(path: Path, fallback: int = 80) -> str:
    """Read coverage minimum percent from quality JSON."""
    if not path.exists():
        return str(fallback)
    data = read_json(path)
    return str(nested(data, "coverage", "minimumPercent") or fallback)


def read_cobertura_line_rate(path: Path) -> str:
    """Parse line-rate from Cobertura XML."""
    root_el = ET.parse(path).getroot()
    rate = root_el.attrib.get("line-rate")
    if rate is None:
        fail(f"Could not read line-rate from {path}.")
    return f"{round(float(rate) * 100, 2):.2f}"


# ── Ticket readiness / risk ──────────────────────────────────────────────

def ticket_readiness(title: str, description: str) -> dict[str, Any]:
    """Score ticket readiness from title/description."""
    return asdict(classify_ticket_readiness(title, description))


def delivery_risk(paths: list[str], context: str, changed_lines: int) -> dict[str, Any]:
    """Score delivery risk from paths, context, changed lines."""
    return asdict(classify_delivery_risk(paths, context, changed_lines))


# ── Git ──────────────────────────────────────────────────────────────────

def check_git_ignored(root: Path, path: str) -> dict[str, Any]:
    """Check if a path is git-ignored."""
    return {"path": path, "ignored": _check_git_ignored(root, path)}


def _check_git_ignored(root: Path, path: str) -> bool:
    completed = subprocess.run(
        ["git", "check-ignore", path], cwd=root,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    return completed.returncode == 0


# ── Commit message validation ────────────────────────────────────────────

def validate_commit_message(root: Path, message: str) -> dict[str, Any]:
    """Validate commit message against ticket pattern."""
    pattern = _read_ticket_pattern(root)
    allowed = re.compile(
        rf"^(\[SDD\] .+|{pattern}: .+|openspec/[a-z0-9][a-z0-9-]*: .+)",
        re.MULTILINE,
    )
    valid = bool(allowed.search(message))
    return {
        "valid": valid,
        "pattern": pattern,
        "message": message.splitlines()[0] if message else "",
        "error": "" if valid else f"Commit message must start with a ticket matching '{pattern}', OpenSpec id, or [SDD].",
    }


# ── Ticket key extraction ────────────────────────────────────────────────

def extract_ticket_key(message: str, pattern: str, fallback: str = "") -> str:
    """Extract ticket key from a commit message."""
    first = message.replace("\r\n", "\n").split("\n", 1)[0]
    direct = re.match(rf"^({pattern}): ", first)
    if direct:
        return direct.group(1)
    merge = re.match(rf"^Merge pull request '({pattern}):", first)
    return merge.group(1) if merge else fallback


# ── Parse workload forecast ──────────────────────────────────────────────

def parse_workload_forecast(tasks_path: str, openspec_change: str | None = None) -> dict[str, Any]:
    """Parse Review Workload Forecast from OpenSpec tasks.md."""
    path = Path(tasks_path)
    if not path.exists():
        return {"valid": False, "error": f"Tasks file not found: {tasks_path}"}
    content = path.read_text(encoding="utf-8")
    # Find the Review Workload Forecast section
    section_match = re.search(
        r"(?m)^##\s+Review Workload Forecast\s*\n(.*?)(?=\n##\s+|\Z)",
        content, re.DOTALL,
    )
    if not section_match:
        return {"valid": False, "error": "No ## Review Workload Forecast section found.", "path": tasks_path}
    body = section_match.group(1)
    estimated_lines = _extract_forecast_field(body, r"Estimated changed lines:\s*<([^>]+)>|Estimated changed lines:\s*(\S+)")
    budget_risk = _extract_forecast_field(body, r"400-line budget risk:\s*(\S+)")
    chained_prs = _extract_forecast_field(body, r"Chained PRs recommended:\s*(\S+)")
    decision_needed = _extract_forecast_field(body, r"Decision needed before apply:\s*(\S+)")
    delivery_strategy = _extract_forecast_field(body, r"Delivery strategy:\s*(\S+)")
    suggested_units = _extract_forecast_field(body, r"Suggested work units:\s*<([^>]+)>|Suggested work units:\s*(.+)$")
    return {
        "valid": True,
        "path": tasks_path,
        "openspecChange": openspec_change or "",
        "estimatedChangedLines": estimated_lines,
        "fourHundredLineBudgetRisk": budget_risk,
        "chainedPRsRecommended": chained_prs,
        "decisionNeededBeforeApply": decision_needed,
        "deliveryStrategy": delivery_strategy,
        "suggestedWorkUnits": suggested_units,
        "needsDecision": (budget_risk or "").lower() == "high"
                       or (chained_prs or "").lower() == "yes"
                       or (decision_needed or "").lower() == "yes",
    }


def _extract_forecast_field(body: str, pattern: str) -> str:
    match = re.search(pattern, body)
    if match:
        # Return first non-None group
        for g in match.groups():
            if g is not None:
                return g.strip()
    return ""


# ── Detect adversarial review trigger ────────────────────────────────────

def detect_adversarial_trigger(
    changed_paths: str = "",
    risk_level: str = "",
    changed_lines: int = 0,
    request_token: str = "",
) -> dict[str, Any]:
    """Determine whether PR review needs adversarial mode."""
    paths = [p.strip() for p in changed_paths.split(",") if p.strip()] if changed_paths else []
    trigger = False
    reasons: list[str] = []
    # Check explicit request
    if request_token and request_token.lower() in ("true", "yes", "adversarial"):
        trigger = True
        reasons.append("Adversarial review explicitly requested.")
    # Check risk level
    if risk_level and risk_level.lower() == "high":
        trigger = True
        reasons.append(f"Delivery risk is '{risk_level}'.")
    # Check high-risk path patterns
    high_risk_patterns = [
        "auth", "authorization", "persistence", "migration",
        "deploy", "secret", "secrets", "public-api", "health",
        "release", "rollback", "hotfix", "/health", ".gitea/",
        "nexus", "azure", "docker", "k8s", "kubernetes",
    ]
    for p in paths:
        for pattern in high_risk_patterns:
            if pattern in p.lower():
                trigger = True
                reasons.append(f"High-risk path pattern '{pattern}' in: {p}")
                break
    # Check changed lines threshold
    if changed_lines > 500:
        trigger = True
        reasons.append(f"Large diff: {changed_lines} changed lines.")
    return {
        "trigger": trigger,
        "reasons": reasons,
        "riskLevel": risk_level or "",
        "changedPaths": paths,
        "changedLines": changed_lines,
    }


# ── Private helpers ──────────────────────────────────────────────────────

def _collapse_stages(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        stage = row.get("workflowStage", row.get("stage", "unknown"))
        current = grouped.setdefault(stage, {"stage": stage, "retryCount": 0})
        current["outcome"] = row.get("outcome", current.get("outcome", ""))
        current["startedUtc"] = min_text(current.get("startedUtc"), row.get("startedUtc"))
        current["finishedUtc"] = max_text(current.get("finishedUtc"), row.get("finishedUtc"))
        current["retryCount"] += int(row.get("retryCount", 0) or 0)
    for current in grouped.values():
        started = parse_time(current.get("startedUtc"))
        finished = parse_time(current.get("finishedUtc"))
        current["elapsedMilliseconds"] = int((finished - started).total_seconds() * 1000) if started and finished else 0
    return sorted(grouped.values(), key=lambda item: item.get("startedUtc", ""))


def _parse_time_comment(raw: str, ticket_key: str) -> dict[str, Any] | None:
    first = raw.splitlines()[0] if raw else ""
    match = re.match(rf"^IA generated workflow telemetry: {re.escape(ticket_key)}:(.+)$", first)
    if not match:
        return None
    data: dict[str, Any] = {"workflowStage": match.group(1)}
    for line in raw.splitlines()[1:]:
        if ": " not in line:
            continue
        key, value = line.split(": ", 1)
        data[key] = value
    data["retryCount"] = int(data.get("retryCount", 0) or 0)
    started = parse_time(data.get("startedUtc"))
    finished = parse_time(data.get("finishedUtc"))
    if started and finished:
        data["elapsedMilliseconds"] = int((finished - started).total_seconds() * 1000)
    return data


def _read_ticket_pattern(root: Path) -> str:
    profile = load_project_profile(root)
    pattern = nested(profile, "workflow", "ticketKeyPattern")
    if pattern:
        return pattern
    policy = root / ".codex" / "delivery-policy.json"
    data = read_json(policy, optional=True)
    return data.get("ticketKeyPattern", "E2EPROJECT-[0-9]+")


# ── CLI entry point ──────────────────────────────────────────────────────

def run_dev_flow(args: list[str]) -> int:
    """CLI entry point for dev-flow commands."""
    import json as _json
    if not args:
        print("Available: ensure-delivery-context, sync-worktree-config, validate-ticket-lock, "
              "validate-deployment-lane, validate-parallel-dry-run, init-telemetry, append-telemetry, "
              "read-telemetry, read-openproject-telemetry, resolve-openproject-activity, "
              "render-openproject-comment, render-ticket-comment, validate-release-manifest, "
              "create-release-manifest, create-artifact-pointer, update-release-manifest, "
              "artifact-paths, next-rc-version, ticket-readiness, delivery-risk, check-git-ignored, "
              "validate-commit-message, extract-ticket-key, audit-skill-contracts, "
              "parse-workload-forecast, detect-adversarial-trigger", file=sys.stderr)
        return 1
    subcommand = args[0]
    options = _parse_pairs(args[1:])
    root = Path(options.get("root", REPO_ROOT))
    dry_run = options.get("dry-run", "false").lower() == "true"
    handlers: dict[str, Any] = {
        "ensure-delivery-context": lambda: ensure_delivery_context(root, _parse_values(options), dry_run),
        "sync-worktree-config": lambda: sync_worktree_local_config(root, _parse_values(options), dry_run),
        "validate-ticket-lock": lambda: validate_ticket_lock(
            Path(options.get("path", root / ".codex" / "delivery-context.local.json")),
            {k[4:]: v for k, v in options.items() if k.startswith("opt-")},
        ),
        "validate-deployment-lane": lambda: validate_deployment_lane(
            Path(options.get("path", root / ".codex" / "parallel-delivery.local.json")),
            {k[4:]: v for k, v in options.items() if k.startswith("opt-")},
        ),
        "validate-parallel-dry-run": lambda: validate_parallel_delivery_dry_run(root, require(options, "input-json")),
        "init-telemetry": lambda: initialize_workflow_telemetry(root, require(options, "ticket-key")),
        "append-telemetry": lambda: append_workflow_telemetry(root, require(options, "ticket-key"), require(options, "input-json")),
        "read-telemetry": lambda: read_workflow_telemetry(root, require(options, "ticket-key"), options.get("input-json", "{}")),
        "read-openproject-telemetry": lambda: read_openproject_time_telemetry(require(options, "ticket-key"), require(options, "input-json")),
        "resolve-openproject-activity": lambda: resolve_openproject_time_activity(require(options, "workflow-stage"), require(options, "input-json")),
        "render-openproject-comment": lambda: render_openproject_time_telemetry_comment(require(options, "ticket-key"), require(options, "input-json")),
        "render-ticket-comment": lambda: render_ticket_comment(require(options, "type"), require(options, "input-json")),
        "validate-release-manifest": lambda: validate_release_manifest(Path(require(options, "path"))),
        "create-release-manifest": lambda: create_release_manifest(options),
        "create-artifact-pointer": lambda: create_artifact_pointer(options),
        "update-release-manifest": lambda: update_release_manifest(Path(require(options, "path")), require(options, "input-json")),
        "artifact-paths": lambda: artifact_paths(require(options, "commit-sha"), options.get("deployment-provider")),
        "next-rc-version": lambda: next_rc_version_output(options.get("tags", ""), options.get("target-version")),
        "ticket-readiness": lambda: ticket_readiness(options.get("title", ""), options.get("description", "")),
        "delivery-risk": lambda: delivery_risk(
            [p.strip() for p in options.get("paths", "").split(",") if p.strip()],
            options.get("context", ""),
            int(options.get("changed-lines", "0")),
        ),
        "check-git-ignored": lambda: check_git_ignored(root, require(options, "path")),
        "validate-commit-message": lambda: validate_commit_message(root, options.get("message", "")),
        "extract-ticket-key": lambda: extract_ticket_key(require(options, "message"), require(options, "pattern"), options.get("fallback", "")),
        "audit-skill-contracts": lambda: audit_skill_contracts(root, options.get("include-configure", "false").lower() == "true"),
        "parse-workload-forecast": lambda: parse_workload_forecast(
            require(options, "tasks-path"),
            options.get("openspec-change"),
        ),
        "detect-adversarial-trigger": lambda: detect_adversarial_trigger(
            changed_paths=options.get("changed-paths", ""),
            risk_level=options.get("risk-level", ""),
            changed_lines=int(options.get("changed-lines", "0")),
            request_token=options.get("request-token", ""),
        ),
    }
    handler = handlers.get(subcommand)
    if not handler:
        print(f"Unknown dev-flow subcommand: {subcommand}", file=sys.stderr)
        return 1
    result = handler()
    if isinstance(result, str):
        print(result)
        return 0
    print(_json.dumps(result, indent=2))
    return 0 if result.get("valid", True) else 1


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


def _parse_values(options: dict[str, str]) -> dict[str, Any]:
    import json as _json
    raw = options.get("values-json", "{}")
    try:
        return _json.loads(raw) if raw else {}
    except _json.JSONDecodeError:
        return {}


def require(options: dict[str, str], key: str) -> str:
    value = options.get(key)
    if not value:
        raise CliError(f"Missing required option: --{key}")
    return value


