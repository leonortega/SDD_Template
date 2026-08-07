"""Standalone workflow telemetry script.

One command writes the OpenProject time-entry row for any delivery stage:

    python -m tools.sdd_cli dev-flow telemetry-upsert \
      --ticket-key E2EPROJECT-11 --workflow-stage dev-flow-verify-change \
      --agent-role verify --started-utc 2026-08-07T10:00:00Z \
      --finished-utc 2026-08-07T11:30:00Z --outcome PASS

The script encapsulates the whole shared pattern (see
``.codex/skills/_shared/pipeline-workflow-telemetry.md``): resolve the activity
ID (client-tools ``timeTelemetry`` override or the default per-stage mapping),
build the time-entry payload with the canonical marker comment, POST
``/api/v3/time_entries`` with Bearer auth from ``.codex/client-tools.local.json``,
and fail loud on API errors unless ``--jsonl-fallback true`` records to the
ignored JSONL file instead.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ._shared import http_json, read_json

# Default OpenProject time-entry activity IDs (from POST /api/v3/time_entries/form).
_ACTIVITY_BY_NAME: dict[str, int] = {
    "Management": 1,
    "Specification": 2,
    "Development": 3,
    "Testing": 4,
    "Support": 5,
    "Other": 6,
}

# Default per-stage activity name (overridable via client-tools timeTelemetry).
_STAGE_ACTIVITY: dict[str, str] = {
    "dev-flow-start-ticket": "Specification",
    "dev-flow-propose-change": "Specification",
    "dev-flow-implement-ticket": "Development",
    "dev-flow-verify-change": "Testing",
    "dev-flow-pr-review-agent": "Development",
    "dev-flow-pr-review-feedback-loop": "Development",
    "dev-ops-post-merge-deploy": "Development",
    "dev-ops-deploy-qa": "Development",
    "qa-gate": "Testing",
    "dev-flow-archive-change": "Management",
    "dev-flow-file-qa-bug": "Testing",
    "dev-ops-deploy-prod": "Development",
    "dev-ops-rollback-prod": "Support",
    "dev-ops-hotfix-prod": "Support",
    "dev-flow-continue-implementation": "Development",
}

_TELEMETRY_JSONL = ".codex/agent-telemetry.local.jsonl"


def render_telemetry_comment(ticket_key: str, row: dict[str, Any]) -> str:
    """Render the canonical telemetry marker comment (mirrors dev_flow rendering)."""
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


def _default_activity_name(stage: str) -> str:
    """Map a workflow stage to its default OpenProject activity name."""
    return _STAGE_ACTIVITY.get(stage, "Development")


def _resolve_activity_id(
    stage: str,
    config: dict[str, Any],
    explicit: str = "",
) -> int | None:
    """Resolve the numeric activity id for a stage.

    Priority: ``--activity-id`` > client-tools ``timeTelemetry.activityByStage``
    > client-tools ``timeTelemetry`` defaults > the default per-stage mapping.
    A configured activity name is reverse-looked-up against the known set; an
    unknown name returns ``None`` (caller falls back).
    """
    if explicit:
        return int(explicit) if explicit.isdigit() else None
    telemetry = config.get("timeTelemetry", {})
    if not isinstance(telemetry, dict):
        telemetry = {}
    by_stage = telemetry.get("activityByStage", {})
    stage_config = (
        by_stage.get(stage, {}) if isinstance(by_stage, dict) else {}
    )
    activity_id = (
        stage_config.get("activityId")
        or telemetry.get("defaultActivityId")
        or telemetry.get("activityId")
    )
    if activity_id:
        return int(activity_id) if str(activity_id).isdigit() else None
    activity_name = (
        stage_config.get("activityName")
        or telemetry.get("defaultActivityName")
        or telemetry.get("activityName")
        or _default_activity_name(stage)
    )
    return _ACTIVITY_BY_NAME.get(activity_name)


def _iso8601_duration(seconds: int) -> str:
    """Format seconds as an ISO-8601 duration (PTnHnMnS)."""
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    parts = []
    if hours:
        parts.append(f"{hours}H")
    if minutes:
        parts.append(f"{minutes}M")
    if secs or not parts:
        parts.append(f"{secs}S")
    return f"PT{''.join(parts)}"


def _elapsed_seconds(started_utc: str, finished_utc: str) -> int:
    """Elapsed seconds between two ISO-8601 UTC timestamps (0 on parse failure)."""
    try:
        start = datetime.fromisoformat(started_utc.replace("Z", "+00:00"))
        finish = datetime.fromisoformat(finished_utc.replace("Z", "+00:00"))
    except ValueError:
        return 0
    return max(0, int((finish - start).total_seconds()))


def _openproject_config(root: Path) -> dict[str, Any]:
    """Read the openProject section of client-tools.local.json (empty on error)."""
    path = root / ".codex" / "client-tools.local.json"
    if not path.exists():
        return {}
    try:
        data = read_json(path, optional=True)
    except Exception:
        return {}
    openproject = data.get("openProject", {}) if isinstance(data, dict) else {}
    return openproject if isinstance(openproject, dict) else {}


def _resolve_work_package_id(
    base_url: str,
    token: str,
    project_identifier: str,
    ticket_key: str,
) -> int | None:
    """Find the work package id whose subject contains the ticket key."""
    import urllib.parse

    filters = json.dumps(
        [{"subject": {"operator": "~", "values": [ticket_key]}}]
    )
    url = (
        f"{base_url}/api/v3/projects/{urllib.parse.quote(project_identifier)}"
        f"/work_packages?filters={urllib.parse.quote(filters)}&pageSize=1"
    )
    status, body = http_json("GET", url, bearer=token, timeout=10)
    if status != 200:
        return None
    try:
        data = json.loads(body)
        elements = (data.get("_embedded") or {}).get("elements") or []
        if elements and elements[0].get("id"):
            return int(elements[0]["id"])
    except (ValueError, TypeError):
        return None
    return None


def _resolve_user_id(base_url: str, token: str) -> int | None:
    """Resolve the authenticated user id (GET /api/v3/users/me)."""
    status, body = http_json("GET", f"{base_url}/api/v3/users/me", bearer=token, timeout=10)
    if status != 200:
        return None
    try:
        data = json.loads(body)
        if isinstance(data, dict) and data.get("id"):
            return int(data["id"])
    except (ValueError, TypeError):
        return None
    return None


def _append_jsonl(root: Path, row: dict[str, Any]) -> Path:
    """Append a telemetry row to the ignored JSONL file."""
    path = root / _TELEMETRY_JSONL
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def telemetry_upsert_cli(
    root: Path, options: dict[str, str], dry_run: bool = False
) -> dict[str, Any]:
    """Upsert the workflow telemetry row for one stage (CLI entry point).

    Reads kebab-case options from the dev-flow subcommand. Writes the OpenProject
    time entry via Bearer auth, falling back to the ignored JSONL file when the
    API is unavailable unless ``--no-jsonl-fallback true`` is set.
    """
    ticket_key = (options.get("ticket-key") or "").strip()
    workflow_stage = (options.get("workflow-stage") or "").strip()
    agent_role = (options.get("agent-role") or "").strip()
    started_utc = (options.get("started-utc") or "").strip()
    finished_utc = (options.get("finished-utc") or "").strip()
    outcome = (options.get("outcome") or "").strip()
    retry_count = int(options.get("retry-count", "0") or 0)
    jsonl_fallback = (options.get("jsonl-fallback") or "false").lower() == "true"

    missing = [
        name
        for name, value in (
            ("ticket-key", ticket_key),
            ("workflow-stage", workflow_stage),
            ("agent-role", agent_role),
            ("started-utc", started_utc),
            ("finished-utc", finished_utc),
            ("outcome", outcome),
        )
        if not value
    ]
    if missing:
        return {
            "mode": "TelemetryUpsert",
            "valid": False,
            "errors": [f"Missing required option: {name}" for name in missing],
        }

    try:
        datetime.fromisoformat(started_utc.replace("Z", "+00:00"))
        datetime.fromisoformat(finished_utc.replace("Z", "+00:00"))
    except ValueError:
        return {
            "mode": "TelemetryUpsert",
            "valid": False,
            "errors": [
                "started-utc and finished-utc must be ISO-8601 UTC timestamps"
            ],
        }

    config = _openproject_config(root)
    base_url = str(config.get("baseUrl", "") or "").rstrip("/")
    token = str(config.get("apiToken", "") or "")
    project_identifier = str(config.get("projectIdentifier", "") or "").strip()
    token_ok = bool(token) and not token.startswith("replace-with")

    marker = (
        f"IA generated workflow telemetry: {ticket_key}:{workflow_stage}"
    )
    comment = render_telemetry_comment(
        ticket_key,
        {
            "workflowStage": workflow_stage,
            "agentRole": agent_role,
            "startedUtc": started_utc,
            "finishedUtc": finished_utc,
            "retryCount": retry_count,
            "outcome": outcome,
        },
    )
    payload: dict[str, Any] = {
        "spentOn": (finished_utc or started_utc)[:10],
        "hours": _iso8601_duration(
            _elapsed_seconds(started_utc, finished_utc)
        ),
        "comment": {"raw": comment},
        "_links": {
            "user": {"href": f"/api/v3/users/{options.get('user-id') or '{userId}'}"},
            "entity": {"href": f"/api/v3/work_packages/{options.get('work-package-id') or '{workPackageId}'}"},
            "project": {"href": f"/api/v3/projects/{project_identifier or '{projectIdentifier}'}"},
            "activity": {"href": "/api/v3/time_entries/activities/{activityId}"},
        },
    }

    def _fallback(reason: str) -> dict[str, Any]:
        if not jsonl_fallback:
            return {
                "mode": "TelemetryUpsert",
                "valid": False,
                "errors": [f"Workflow telemetry upsert failed: {reason}"],
                "marker": marker,
            }
        row = {
            "ticketKey": ticket_key,
            "workflowStage": workflow_stage,
            "agentRole": agent_role,
            "startedUtc": started_utc,
            "finishedUtc": finished_utc,
            "retryCount": retry_count,
            "outcome": outcome,
            "marker": marker,
            "fallbackReason": reason,
            "createdAtUtc": datetime.now(timezone.utc).isoformat(),
        }
        jsonl_path = _append_jsonl(root, row)
        return {
            "mode": "TelemetryUpsert",
            "valid": True,
            "action": "jsonl-fallback",
            "marker": marker,
            "jsonlPath": str(jsonl_path),
            "fallbackReason": reason,
        }

    if dry_run:
        activity_id = _resolve_activity_id(workflow_stage, config, options.get("activity-id", ""))
        if activity_id:
            payload["_links"]["activity"]["href"] = (
                f"/api/v3/time_entries/activities/{activity_id}"
            )
        return {
            "mode": "TelemetryUpsert",
            "valid": True,
            "dryRun": True,
            "action": "dry-run",
            "marker": marker,
            "payload": payload,
        }

    if not token_ok:
        return _fallback("openProject.apiToken is missing or placeholder")

    activity_id = _resolve_activity_id(workflow_stage, config, options.get("activity-id", ""))
    if activity_id is None:
        return _fallback(f"could not resolve activity for stage '{workflow_stage}'")
    payload["_links"]["activity"]["href"] = (
        f"/api/v3/time_entries/activities/{activity_id}"
    )

    work_package_id = options.get("work-package-id", "")
    if work_package_id and work_package_id.isdigit():
        payload["_links"]["entity"]["href"] = (
            f"/api/v3/work_packages/{work_package_id}"
        )
    elif project_identifier:
        resolved = _resolve_work_package_id(
            base_url, token, project_identifier, ticket_key
        )
        if resolved is None:
            return _fallback(f"could not resolve work package for '{ticket_key}'")
        payload["_links"]["entity"]["href"] = f"/api/v3/work_packages/{resolved}"
    else:
        return _fallback("openProject.projectIdentifier is missing")

    user_id = options.get("user-id", "")
    if user_id and user_id.isdigit():
        payload["_links"]["user"]["href"] = f"/api/v3/users/{user_id}"
    else:
        resolved_user = _resolve_user_id(base_url, token)
        if resolved_user is None:
            return _fallback("could not resolve OpenProject user")
        payload["_links"]["user"]["href"] = f"/api/v3/users/{resolved_user}"

    status, body = http_json(
        "POST", f"{base_url}/api/v3/time_entries", body=payload, bearer=token, timeout=15
    )
    if status not in (200, 201):
        return _fallback(f"POST /api/v3/time_entries returned {status}")
    time_entry_id: int | None = None
    try:
        data = json.loads(body)
        if isinstance(data, dict) and data.get("id"):
            time_entry_id = int(data["id"])
    except (ValueError, TypeError):
        pass
    return {
        "mode": "TelemetryUpsert",
        "valid": True,
        "action": "upserted",
        "marker": marker,
        "timeEntryId": time_entry_id,
        "payload": payload,
    }


def append_telemetry_cli(root: Path, options: dict[str, str]) -> dict[str, Any]:
    """Append a JSONL telemetry row (explicit fallback command)."""
    ticket_key = (options.get("ticket-key") or "").strip()
    if not ticket_key:
        return {
            "mode": "AppendTelemetry",
            "valid": False,
            "errors": ["Missing required option: ticket-key"],
        }
    row = {
        "ticketKey": ticket_key,
        "workflowStage": (options.get("workflow-stage") or "").strip(),
        "agentRole": (options.get("agent-role") or "").strip(),
        "startedUtc": (options.get("started-utc") or "").strip(),
        "finishedUtc": (options.get("finished-utc") or "").strip(),
        "retryCount": int(options.get("retry-count", "0") or 0),
        "outcome": (options.get("outcome") or "").strip(),
        "marker": f"IA generated workflow telemetry: {ticket_key}:{options.get('workflow-stage') or ''}",
        "createdAtUtc": datetime.now(timezone.utc).isoformat(),
    }
    jsonl_path = _append_jsonl(root, row)
    return {
        "mode": "AppendTelemetry",
        "valid": True,
        "action": "appended",
        "jsonlPath": str(jsonl_path),
        "marker": row["marker"],
    }
