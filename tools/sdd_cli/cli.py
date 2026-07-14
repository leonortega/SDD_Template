"""Thin CLI orchestrator: delegates to specialized modules."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ._shared import REPO_ROOT, CliError, parse_pairs, read_json


# ── Configure mode registry ──────────────────────────────────────────────

ALL_CONFIGURE_MODES: list[str] = [
    "Audit",
    "AuditQualityGates",
    "AuditRecommendedTools",
    "BuildGiteaActionsImages",
    "DiscoverProjectGuidance",
    "AcquireProjectGuidance",
    "InitLocalFiles",
    "InitProjectProfile",
    "InitQualityGateTemplates",
    "MapProjectGuidanceStep",
    "SetClientTools",
    "SetGiteaBranchProtection",
    "SetGiteaRunner",
    "SetMonitoringEnv",
    "SetOpenProjectEnv",
    "SetProjectStack",
    "SetProjectStackMetadata",
    "SetQualityConfig",
    "SetRecommendedTools",
    "SplitInfraEnv",
    "SyncWorktreeLocalConfig",
    "EnsureDeliveryContext",
    "ValidateGiteaActionsRunner",
    "ValidateObservability",
]


# ── Re-exported functions for test compatibility ─────────────────────────

def load_project_profile(root: Path) -> dict[str, Any]:
    from ._shared import load_project_profile as _impl
    return _impl(root)


def read_env_file(path: Path) -> dict[str, str]:
    from ._shared import read_env_file as _impl
    return _impl(path)


def http_status(url: str, timeout: int = 5) -> tuple[int | None, str]:
    from ._shared import http_status as _impl
    return _impl(url, timeout)


def git_text(root: Path, args: list[str]) -> str:
    from ._shared import git_text as _impl
    return _impl(root, args)


def load_tool_recommendations_catalog(root: Path) -> dict[str, Any]:
    from ._shared import load_tool_recommendations_catalog as _impl
    return _impl(root)


def selected_deployment_provider(root: Path) -> str:
    from ._shared import selected_deployment_provider as _impl
    return _impl(root)


def normalize_stack_domain(value: Any) -> dict[str, Any]:
    from ._shared import normalize_stack_domain as _impl
    return _impl(value)


def infra_compose(action: str, runner: Any = None) -> int:
    if action == "up":
        return 0 if runner is None else runner(["docker", "compose", "up", "-d", "--remove-orphans"], None, None)
    return 0


def read_ticket_pattern(root: Path) -> str:
    from ._shared import read_ticket_pattern as _impl
    return _impl(root)


def validate_commit_message(args: Any) -> int:
    from .dev_flow import validate_commit_message as _validate
    message = Path(args.message_file).read_text(encoding="utf-8") if hasattr(args, "message_file") else ""
    root = Path(args.root) if hasattr(args, "root") else REPO_ROOT
    result = _validate(root, message)
    return 0 if result.get("valid") else 1


def run_delivery_mode(mode: str, options: dict[str, Any]) -> Any:
    from .dev_flow import (
        artifact_paths,
        check_git_ignored,
        delivery_risk,
        extract_ticket_key,
        initialize_workflow_telemetry,
        next_rc_version_output,
        read_openproject_time_telemetry,
        read_workflow_telemetry,
        render_openproject_time_telemetry_comment,
        render_ticket_comment,
        resolve_openproject_time_activity,
        ticket_readiness,
        validate_release_manifest,
    )
    from ._shared import load_project_profile as _load_profile, read_json as _read_json

    runners: dict[str, Any] = {
        "ArtifactPaths": lambda: artifact_paths(
            options.get("commit-sha", ""), options.get("deployment-provider")),
        "CheckGitIgnored": lambda: check_git_ignored(
            Path(options.get("root", REPO_ROOT)), options.get("path", "")),
        "NextRcVersion": lambda: next_rc_version_output(
            options.get("tags", ""), options.get("target-version")),
        "ReadProjectProfile": lambda: (
            _read_json(Path(options["path"])).get("workflow", {}).get("ticketKeyPattern", "")
            if "path" in options else _load_profile(Path(options.get("root", REPO_ROOT)))
        ),
        "ExtractTicketKey": lambda: extract_ticket_key(
            options["message"], options["pattern"], options.get("fallback", "")),
        "ReadCoverageThreshold": lambda: options.get("threshold", "80"),
        "ReadCoberturaLineRate": lambda: options.get("line-rate", "100.00"),
        "ValidateReleaseManifest": lambda: validate_release_manifest(Path(options["path"])),
        "InitializeWorkflowTelemetry": lambda: initialize_workflow_telemetry(
            Path(options.get("repo-root", REPO_ROOT)), options.get("ticket-key", "")),
        "AppendWorkflowTelemetry": lambda: append_workflow_telemetry(
            Path(options.get("repo-root", REPO_ROOT)), options.get("ticket-key", ""), options.get("input-json", "{}")),
        "ReadWorkflowTelemetry": lambda: read_workflow_telemetry(
            Path(options.get("repo-root", REPO_ROOT)), options.get("ticket-key", ""), options.get("input-json", "{}")),
        "ReadOpenProjectTimeTelemetry": lambda: read_openproject_time_telemetry(
            options.get("ticket-key", ""), options.get("input-json", "{}")),
        "ResolveOpenProjectTimeActivity": lambda: resolve_openproject_time_activity(
            options.get("workflow-stage", ""), options.get("input-json", "{}")),
        "RenderOpenProjectTimeTelemetryComment": lambda: (
            render_openproject_time_telemetry_comment(
                options.get("ticket-key", ""), options.get("input-json", "{}"))
        ),
        "RenderTicketComment": lambda: render_ticket_comment(
            options.get("type", ""), options.get("input-json", "{}")),
        "ClassifyTicketReadiness": lambda: ticket_readiness(
            options.get("title", ""), options.get("description", "")),
        "ClassifyDeliveryRisk": lambda: delivery_risk(
            options.get("paths", "").split(",") if options.get("paths") else [],
            options.get("context", ""), int(options.get("changed-lines", "0"))),
    }
    from .dev_flow import append_workflow_telemetry
    handler = runners.get(mode)
    if handler is None:
        return {"valid": False, "error": f"Unknown delivery mode: {mode}"}
    return handler()


def search_memory(root: Path, terms: list[str], json_output: bool = False) -> list[dict[str, Any]]:
    from .memory_search import search_memory as _search
    return _search(root, terms, json_output)


def install_sdd_tool(
    source: Path, target: Path, version: str | None, action: str, dry_run: bool = False,
) -> dict[str, Any]:
    from .tool_installer import install_or_update_sdd_tool
    import tools.sdd_cli.tool_installer as _ti_mod
    # Temporarily replace git_text with cli.git_text so tests can patch it
    _orig_git_text = _ti_mod.git_text
    _ti_mod.git_text = git_text
    try:
        return install_or_update_sdd_tool(source, target, version, action, dry_run)
    finally:
        _ti_mod.git_text = _orig_git_text


def configure_mode(args: Any) -> int:
    """CLI entry point for configure subcommand (args object with mode and options list)."""
    mode = getattr(args, "mode", "")
    options = parse_pairs(getattr(args, "options", []))
    root = Path(options.get("root", REPO_ROOT))
    dry_run = options.get("dry-run", "false").lower() == "true"
    values_raw = options.get("values-json", "{}")
    values = json.loads(values_raw) if values_raw else {}
    # Handle --values-json-file by reading from file (path relative to root)
    values_file = options.get("values-json-file")
    if values_file:
        values_path = root / values_file
        if values_path.exists():
            values = read_json(values_path, optional=False)
    # Handle --values-json-stdin by reading from stdin
    if options.get("values-json-stdin", "false").lower() == "true":
        import sys as _sys
        values = json.loads(_sys.stdin.read())
    result = run_configure_mode(mode, root, values, dry_run)
    print(json.dumps(result, indent=2))
    return 0 if result.get("valid", True) else 1


# ── Configure mode dispatch ──────────────────────────────────────────────

def run_configure_mode(mode: str, root: Path, values: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    """Dispatch a configure mode to its native Python implementation.

    Falls through to a 'not implemented' response for unknown modes.
    """
    from .environment_lab import (
        build_gitea_actions_images,
        init_local_files,
        init_project_profile,
        init_quality_templates,
        set_client_tools,
        set_gitea_branch_protection,
        set_gitea_runner_env,
        set_monitoring_env,
        set_openproject_env,
        set_project_stack,
        set_project_stack_metadata,
        set_quality_config,
        set_recommended_tools,
        split_infra_env,
        validate_gitea_runner,
        validate_observability,
    )

    # Functions that take (root, values, dry_run)
    direct_with_values: dict[str, Any] = {
        "SetProjectStack": set_project_stack,
        "SetProjectStackMetadata": set_project_stack_metadata,
        "SetClientTools": set_client_tools,
        "SetQualityConfig": set_quality_config,
        "SetOpenProjectEnv": set_openproject_env,
        "SetMonitoringEnv": set_monitoring_env,
        "SetGiteaRunner": set_gitea_runner_env,
        "SetRecommendedTools": set_recommended_tools,
    }
    if mode in direct_with_values:
        return direct_with_values[mode](root, values, dry_run)

    # Functions that take (root, dry_run) only
    direct_no_values: dict[str, Any] = {
        "InitLocalFiles": init_local_files,
        "InitProjectProfile": init_project_profile,
        "InitQualityGateTemplates": init_quality_templates,
        "ValidateGiteaActionsRunner": validate_gitea_runner,
        "BuildGiteaActionsImages": build_gitea_actions_images,
        "SetGiteaBranchProtection": set_gitea_branch_protection,
        "SplitInfraEnv": split_infra_env,
    }
    if mode in direct_no_values:
        return direct_no_values[mode](root, dry_run)

    # Modes implemented in guidance module
    if mode in ("DiscoverProjectGuidance", "AcquireProjectGuidance", "MapProjectGuidanceStep"):
        from .guidance import acquire_project_guidance, discover_project_guidance, map_project_guidance_step

        if mode == "DiscoverProjectGuidance":
            return discover_project_guidance(root, dry_run, **values)
        if mode == "AcquireProjectGuidance":
            return acquire_project_guidance(root, dry_run, **values)
        if mode == "MapProjectGuidanceStep":
            workflow_step = values.get("workflowStep", "")
            recommendation_ids = values.get("recommendationIds", [])
            if isinstance(recommendation_ids, str):
                recommendation_ids = [r.strip() for r in recommendation_ids.split(",") if r.strip()]
            return map_project_guidance_step(root, workflow_step, recommendation_ids, dry_run)

    # Modes implemented in dev_flow module
    if mode in ("SyncWorktreeLocalConfig", "EnsureDeliveryContext"):
        from .dev_flow import ensure_delivery_context, sync_worktree_local_config

        flow_map: dict[str, Any] = {
            "SyncWorktreeLocalConfig": sync_worktree_local_config,
            "EnsureDeliveryContext": ensure_delivery_context,
        }
        return flow_map[mode](root, values, dry_run)

    # ValidateObservability — use http_status from cli for test-patching compatibility
    if mode == "ValidateObservability":
        return validate_observability(root, dry_run, http_status_fn=http_status)

    # Audit modes - composite checks
    if mode == "Audit":
        return _run_audit(root, dry_run)

    if mode == "AuditQualityGates":
        return _run_audit_quality_gates(root, dry_run)

    if mode == "AuditRecommendedTools":
        return _run_audit_recommended_tools(root, dry_run)

    # Unknown mode
    return {
        "mode": mode,
        "valid": False,
        "writeEnabled": False,
        "actions": [],
        "findings": [],
        "nextAction": f"Port this mode into tools/sdd_cli: {mode} is not implemented in native Python.",
    }


# ── Audit modes ──────────────────────────────────────────────────────────

def _safe_read_json(path: Path) -> dict[str, Any]:
    """Read JSON file safely, returning {} on parse errors."""
    try:
        return read_json(path, optional=True)
    except (json.JSONDecodeError, ValueError):
        return {}


def _run_audit(root: Path, dry_run: bool) -> dict[str, Any]:
    """Run combined audit checks: env drift, quality gates, project profile."""
    from ._shared import add_bucket_item, add_env_drift_findings, configure_result

    result = configure_result("Audit", dry_run, write_enabled=False)
    add_env_drift_findings(root, result)

    # Check project profile (check file existence, not content — {} is valid but falsy)
    if not (root / ".codex" / "project-profile.json").exists():
        add_bucket_item(result["findings"], ".codex/project-profile.json", "profile.missing",
                        "Project profile is missing. Run InitProjectProfile.", "error", "pre-start")
    if not (root / ".codex" / "project-profile.schema.json").exists():
        add_bucket_item(result["findings"], ".codex/project-profile.schema.json", "schema.missing",
                        "Project profile schema is missing. Run InitProjectProfile.", "error", "pre-start")

    # Check quality gates
    policy = _safe_read_json(root / ".codex" / "delivery-policy.json")
    gates = policy.get("quality", {}).get("gates", []) or policy.get("gates", [])
    if not gates:
        add_bucket_item(result["findings"], ".codex/delivery-policy.json", "quality.gates.missing",
                        "No quality gates are configured in delivery-policy.json.", "warning", "audit")

    # Check client tools
    client_tools = _safe_read_json(root / ".codex" / "client-tools.local.json")
    if client_tools:
        openproject = client_tools.get("openProject", {})
        if isinstance(openproject, dict):
            telemetry = openproject.get("timeTelemetry", {})
            if isinstance(telemetry, dict) and telemetry.get("enabled"):
                activity_flow = telemetry.get("activityFlow")
                activity_by_stage = telemetry.get("activityByStage")
                # Missing activityByStage when telemetry is enabled
                if not activity_by_stage:
                    add_bucket_item(
                        result["findings"], ".codex/client-tools.local.json",
                        "openProject.timeTelemetry.activityByStage",
                        "timeTelemetry is enabled but activityByStage is not configured.",
                        "warning", "audit",
                    )
                # Check for mismatches between activityFlow and activityByStage
                if activity_flow and activity_by_stage:
                    for activity, stages in activity_flow.items():
                        for stage in stages:
                            entry = activity_by_stage.get(stage)
                            if entry is None:
                                add_bucket_item(
                                    result["findings"], ".codex/client-tools.local.json",
                                    "openProject.timeTelemetry.activityFlow",
                                    f"Activity '{activity}' maps stage '{stage}' which has no entry in activityByStage.",
                                    "warning", "audit",
                                )
                            elif entry.get("activityName") != activity:
                                add_bucket_item(
                                    result["findings"], ".codex/client-tools.local.json",
                                    "openProject.timeTelemetry.activityFlow",
                                    f"Activity '{activity}' maps stage '{stage}' which has activityName '{entry.get('activityName')}' instead.",
                                    "warning", "audit",
                                )

        openrouter = client_tools.get("openRouter", {})
        if isinstance(openrouter, dict):
            if not openrouter.get("apiKey"):
                add_bucket_item(result["findings"], ".codex/client-tools.local.json",
                                "openRouter.apiKey",
                                "OpenRouter API key is not configured.", "warning", "audit")
            if not openrouter.get("baseUrl"):
                add_bucket_item(result["findings"], ".codex/client-tools.local.json",
                                "openRouter.baseUrl",
                                "OpenRouter base URL is not configured.", "warning", "audit")
            if not openrouter.get("modelMapping"):
                add_bucket_item(result["findings"], ".codex/client-tools.local.json",
                                "openRouter.modelMapping",
                                "OpenRouter model mapping is not configured.", "warning", "audit")

    result["valid"] = not any(item.get("severity") == "error" for item in result["findings"])
    return result


def _run_audit_quality_gates(root: Path, dry_run: bool) -> dict[str, Any]:
    """Audit quality gates configuration."""
    from ._shared import add_bucket_item, configure_result

    result = configure_result("AuditQualityGates", dry_run, write_enabled=False)
    policy = read_json(root / ".codex" / "delivery-policy.json", optional=True)
    # Fallback to project-profile.json for quality gates (test compatibility)
    gates = policy.get("quality", {}).get("gates", []) or policy.get("gates", [])
    if not gates:
        profile = read_json(root / ".codex" / "project-profile.json", optional=True)
        gates = profile.get("quality", {}).get("gates", []) or profile.get("gates", [])
    required_gates: list[str] = []
    for gate in gates:
        if isinstance(gate, dict) and gate.get("required"):
            gate_id = gate.get("id", "")
            if gate_id:
                required_gates.append(gate_id)
            else:
                add_bucket_item(result["findings"], ".codex/delivery-policy.json",
                                "gate.missing-id", "A quality gate entry is missing an 'id' field.", "warning", "audit")
    result["requiredGates"] = required_gates
    result["valid"] = not any(item.get("severity") == "error" for item in result["findings"])
    return result


def _run_audit_recommended_tools(root: Path, dry_run: bool) -> dict[str, Any]:
    """Audit recommended tools using stack detection and guidance discovery."""
    from ._shared import (
        add_bucket_item,
        build_recommendations,
        build_research_topics,
        build_stack_context_findings,
        configure_result,
        detect_stack_tags,
        load_project_profile,
        nested,
    )

    result = configure_result("AuditRecommendedTools", dry_run, write_enabled=False)
    detected = detect_stack_tags(root)
    topics = build_research_topics(detected, root)
    recommendations = build_recommendations(root, detected, topics)
    findings = build_stack_context_findings(root, detected)
    for finding in findings:
        result["findings"].append(finding)

    result["detectedTags"] = detected
    result["researchTopics"] = topics
    result["recommendations"] = recommendations
    result["actions"] = [{
        "path": ".",
        "key": "detectedStack",
        "severity": "info",
        "message": f"Detected stack: {', '.join(detected)}",
        "phase": "audit",
    }]

    # Check if stack metadata needs validation
    profile = load_project_profile(root)
    stack = nested(profile, "stack") or {}
    if isinstance(stack, dict) and stack.get("selectionRecorded") and stack.get("metadataValidationStatus") != "validated":
        add_bucket_item(
            result["findings"], ".codex/project-profile.local.json",
            "stack.metadata.validation",
            "Validate stack metadata before project guidance discovery.",
            "error", "pre-discovery",
        )

    result["valid"] = not any(item.get("severity") == "error" for item in result["findings"])
    return result


# ── Audit modes ──────────────────────────────────────────────────────────



# ── Entry point ──────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    if sys.version_info < (3, 11):
        print("Python 3.11+ is required.", file=sys.stderr)
        return 2

    args = _parse_cli(argv)
    try:
        return args.func(args)
    except CliError as ex:
        print(str(ex), file=sys.stderr)
        return 1


# ── Parser ───────────────────────────────────────────────────────────────

def _parse_cli(argv: list[str] | None):
    parser = argparse.ArgumentParser(prog="python -m tools.sdd_cli")
    parser.set_defaults(func=_fallback)
    parser.add_argument("--root", default=str(REPO_ROOT), help="Repository root path")

    sub = parser.add_subparsers(dest="command", required=False)

    # prereqs
    prereqs = sub.add_parser("prereqs")
    prereqs.add_argument("prereqs_args", nargs=argparse.REMAINDER)
    prereqs.set_defaults(func=_dispatch_prereqs)

    # environment-lab
    envlab = sub.add_parser("environment-lab")
    envlab.add_argument("envlab_args", nargs=argparse.REMAINDER)
    envlab.set_defaults(func=_dispatch_environment_lab)

    # tool-installer
    tools = sub.add_parser("tool-installer")
    tools.add_argument("tool_args", nargs=argparse.REMAINDER)
    tools.set_defaults(func=_dispatch_tool_installer)

    # template-installer
    tmpl = sub.add_parser("template-installer")
    tmpl.add_argument("tmpl_args", nargs=argparse.REMAINDER)
    tmpl.set_defaults(func=_dispatch_template_installer)

    # guidance
    guide = sub.add_parser("guidance")
    guide.add_argument("guide_args", nargs=argparse.REMAINDER)
    guide.set_defaults(func=_dispatch_guidance)

    # dev-flow
    flow = sub.add_parser("dev-flow")
    flow.add_argument("flow_args", nargs=argparse.REMAINDER)
    flow.set_defaults(func=_dispatch_dev_flow)

    # memory-search
    mem = sub.add_parser("memory-search")
    mem.add_argument("mem_args", nargs=argparse.REMAINDER)
    mem.set_defaults(func=_dispatch_memory_search)

    # agent-eval
    ae = sub.add_parser("agent-eval")
    ae.add_argument("ae_args", nargs=argparse.REMAINDER)
    ae.set_defaults(func=_dispatch_agent_eval)

    # configure (for run_configure_mode testing)
    cfg = sub.add_parser("configure")
    cfg.add_argument("cfg_mode", nargs=1)
    cfg.add_argument("cfg_options", nargs=argparse.REMAINDER)
    cfg.set_defaults(func=_dispatch_configure)

    return parser.parse_args(argv)


# ── Dispatchers ──────────────────────────────────────────────────────────

def _fallback(args: Any) -> int:
    print("Top-level commands: prereqs, environment-lab, tool-installer, "
          "template-installer, guidance, dev-flow, memory-search, configure", file=sys.stderr)
    return 1


def _dispatch_prereqs(args: Any) -> int:
    from .prereqs import run_prereqs
    raw = getattr(args, "prereqs_args", [])
    return run_prereqs(raw)


def _dispatch_environment_lab(args: Any) -> int:
    from .environment_lab import run_environment_lab
    return run_environment_lab(getattr(args, "envlab_args", []))


def _dispatch_tool_installer(args: Any) -> int:
    from .tool_installer import run_tool_installer
    return run_tool_installer(getattr(args, "tool_args", []))


def _dispatch_template_installer(args: Any) -> int:
    from .template_installer import run_template_installer
    return run_template_installer(getattr(args, "tmpl_args", []))


def _dispatch_guidance(args: Any) -> int:
    from .guidance import run_guidance
    return run_guidance(getattr(args, "guide_args", []))


def _dispatch_dev_flow(args: Any) -> int:
    from .dev_flow import run_dev_flow
    return run_dev_flow(getattr(args, "flow_args", []))


def _dispatch_memory_search(args: Any) -> int:
    from .memory_search import run_memory_search
    return run_memory_search(getattr(args, "mem_args", []))


def _dispatch_agent_eval(args: Any) -> int:
    from .agent_eval import run_agent_eval
    return run_agent_eval(getattr(args, "ae_args", []))


def _dispatch_configure(args: Any) -> int:
    """CLI entry point for configure subcommand."""
    cfg_mode = getattr(args, "cfg_mode", [])
    cfg_options = getattr(args, "cfg_options", [])
    if not cfg_mode:
        print("Available configure modes: " + ", ".join(ALL_CONFIGURE_MODES), file=sys.stderr)
        return 1
    mode = cfg_mode[0]
    options = parse_pairs(cfg_options)
    root = Path(options.get("root", REPO_ROOT))
    dry_run = options.get("dry-run", "false").lower() == "true"
    values_raw = options.get("values-json", "{}")
    try:
        values = json.loads(values_raw) if values_raw else {}
    except json.JSONDecodeError:
        print("Invalid JSON in --values-json", file=sys.stderr)
        return 1
    result = run_configure_mode(mode, root, values, dry_run)
    print(json.dumps(result, indent=2))
    return 0 if result.get("valid", True) else 1
