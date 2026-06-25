from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON_REQUIRES = (3, 11)
SEARCH_PLAN_ID = "project-guidance-search-plan"
STANDARD_STAGES = [
    "dev-flow-start-ticket",
    "dev-flow-implement-ticket",
    "dev-flow-pr-review-agent",
    "dev-flow-pr-review-feedback-loop",
    "dev-ops-post-merge-deploy",
    "dev-ops-deploy-qa",
]
ALLOWLISTED_LOCAL_CONFIG = [
    ".codex/client-tools.local.json",
    ".codex/project-profile.local.json",
    ".codex/quality.local.json",
    ".codex/tool-recommendations.local.json",
]
RANCHER_PORTS = [
    ("dev", "web", 18081),
    ("dev", "api", 18082),
    ("qa", "web", 18083),
    ("qa", "api", 18084),
    ("prod", "web", 18085),
    ("prod", "api", 18086),
]
DISCOVERY_SOURCE_PRIORITY = [
    "repo-local",
    "openai-official",
    "tool-official",
    "technology-owner",
    "skills-cli",
    "marketplace",
    "community",
]
SDD_TOOL_MANIFEST = ".codex/sdd-tool-version.json"
SDD_TOOL_VERSION_PATTERN = re.compile(r"^v\d+\.\d+\.\d+$")
SDD_TOOL_INCLUDE_FILES = [
    "AGENTS.md",
    "README.md",
    ".gitignore",
    ".codex/client-tools.common.json",
    ".codex/config.toml",
    ".codex/delivery-policy.json",
    ".codex/project-profile.json",
    ".codex/project-profile.schema.json",
    ".codex/quality.common.json",
    ".codex/tool-recommendations.common.json",
    "openspec/config.yaml",
]
SDD_TOOL_INCLUDE_DIRS = [
    ".codex/providers",
    ".codex/skills",
    ".gitea/workflows",
    "docs",
    "infra",
    "tools",
]
SDD_TOOL_EXCLUDE_PARTS = {
    "__pycache__",
    ".git",
    ".pytest_cache",
    ".codex/memory",
    ".codex/agent-evals",
    ".codex/ponytail",
    "openspec/changes",
    "tools/sdd_cli/tests",
}
SDD_TOOL_EXCLUDE_SEGMENTS = {"data", "logs"}
SDD_TOOL_EXCLUDE_SUFFIXES = {".pyc", ".pyo"}
SDD_TOOL_PRESERVE_FILES = {
    ".codex/client-tools.local.json",
    ".codex/project-profile.local.json",
    ".codex/quality.local.json",
    ".codex/tool-recommendations.local.json",
}


class CliError(RuntimeError):
    pass


Runner = Callable[[list[str], Path | None, dict[str, str] | None], int]


@dataclass
class TicketReadinessResult:
    status: str
    missing: list[str]


@dataclass
class DeliveryRiskResult:
    level: str
    reasons: list[str]


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < PYTHON_REQUIRES:
        print("Python 3.11+ is required.", file=sys.stderr)
        return 2

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except CliError as ex:
        print(str(ex), file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m tools.sdd_cli")
    sub = parser.add_subparsers(dest="command", required=True)

    infra = sub.add_parser("infra")
    infra_sub = infra.add_subparsers(dest="action", required=True)
    infra_sub.add_parser("up").set_defaults(func=lambda args: infra_compose("up"))
    infra_sub.add_parser("down").set_defaults(func=lambda args: infra_compose("down"))

    azure = sub.add_parser("azure")
    azure_sub = azure.add_subparsers(dest="action", required=True)
    deploy = azure_sub.add_parser("deploy-environments")
    deploy.add_argument("--location", default="westcentralus")
    deploy.add_argument("--dev-rg", default="rg-agentic-dev")
    deploy.add_argument("--qa-rg", default="rg-agentic-qa")
    deploy.add_argument("--prod-rg", default="rg-agentic-prod")
    deploy.add_argument("--what-if", action="store_true")
    deploy.set_defaults(func=azure_deploy_environments)

    memory = sub.add_parser("memory")
    memory_sub = memory.add_subparsers(dest="action", required=True)
    search = memory_sub.add_parser("search")
    search.add_argument("--query", action="append", default=[])
    search.add_argument("--list-topics", action="store_true")
    search.add_argument("--json", action="store_true", dest="as_json")
    search.add_argument("--root", default=str(REPO_ROOT))
    search.set_defaults(func=memory_search)

    hooks = sub.add_parser("hooks")
    hooks_sub = hooks.add_subparsers(dest="action", required=True)
    validate = hooks_sub.add_parser("validate-commit-message")
    validate.add_argument("message_file")
    validate.add_argument("--root", default=str(REPO_ROOT))
    validate.set_defaults(func=validate_commit_message)

    delivery = sub.add_parser("delivery")
    delivery.add_argument("mode")
    delivery.add_argument("options", nargs=argparse.REMAINDER)
    delivery.set_defaults(func=delivery_mode)

    configure = sub.add_parser("configure")
    configure.add_argument("mode", nargs="?", default="Audit")
    configure.add_argument("options", nargs=argparse.REMAINDER)
    configure.set_defaults(func=configure_mode)

    tool = sub.add_parser("tool")
    tool_sub = tool.add_subparsers(dest="action", required=True)
    for action in ("install", "update"):
        command = tool_sub.add_parser(action)
        command.add_argument("--version")
        command.add_argument("--target", required=True)
        command.add_argument("--source", default=str(REPO_ROOT))
        command.set_defaults(func=tool_install_or_update)

    return parser


def default_runner(command: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> int:
    return subprocess.run(command, cwd=cwd, env=env, check=False).returncode


def infra_compose(action: str, runner: Runner = default_runner) -> int:
    infra = REPO_ROOT / "infra"
    command = [
        "docker",
        "compose",
        "--env-file",
        str(infra / "openproject" / "variables.env"),
        "--env-file",
        str(infra / "monitoring" / "variables.env"),
        "-f",
        str(infra / "compose.yml"),
        "--project-directory",
        str(infra),
    ]
    command += ["up", "-d", "--remove-orphans"] if action == "up" else ["down"]
    return runner(command, REPO_ROOT, None)


def azure_deploy_environments(args: argparse.Namespace, runner: Runner = default_runner) -> int:
    azure_dir = REPO_ROOT / "infra" / "azure"
    template = azure_dir / "main.bicep"
    deployments = [
        ("dev", args.dev_rg, azure_dir / "dev.parameters.json"),
        ("qa", args.qa_rg, azure_dir / "qa.parameters.json"),
        ("prod", args.prod_rg, azure_dir / "prod.parameters.json"),
    ]

    code = runner(["az", "account", "show", "--output", "none"], REPO_ROOT, None)
    if code:
        return code

    for env_name, group, parameters in deployments:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        deployment_name = f"agentic-{env_name}-{stamp}"
        if args.what_if:
            if runner(["az", "group", "show", "--name", group, "--output", "none"], REPO_ROOT, None):
                print(
                    f"WhatIf: resource group '{group}' would be created in '{args.location}'. "
                    f"Skipping deployment what-if for '{env_name}' until the group exists."
                )
                continue
            command = [
                "az",
                "deployment",
                "group",
                "what-if",
                "--resource-group",
                group,
                "--name",
                deployment_name,
                "--template-file",
                str(template),
                "--parameters",
                str(parameters),
            ]
        else:
            create = [
                "az",
                "group",
                "create",
                "--name",
                group,
                "--location",
                args.location,
                "--tags",
                "project=agentic-e2e",
                f"env={env_name}",
                "managedBy=bicep",
                "--output",
                "none",
            ]
            code = runner(create, REPO_ROOT, None)
            if code:
                return code
            command = [
                "az",
                "deployment",
                "group",
                "create",
                "--resource-group",
                group,
                "--name",
                deployment_name,
                "--template-file",
                str(template),
                "--parameters",
                str(parameters),
                "--output",
                "table",
            ]
        code = runner(command, REPO_ROOT, None)
        if code:
            return code
    return 0


def memory_search(args: argparse.Namespace) -> int:
    result = search_memory(Path(args.root), args.query, args.list_topics)
    print(json.dumps(result, indent=2) if not isinstance(result, list) or args.as_json else "\n".join(" | ".join(str(row.get(key, "")) for key in row) for row in result))
    return 0


def validate_commit_message(args: argparse.Namespace) -> int:
    root = Path(args.root)
    message = Path(args.message_file).read_text(encoding="utf-8")
    pattern = read_ticket_pattern(root)
    allowed = re.compile(rf"^(\[SDD\] .+|{pattern}: .+|openspec/[a-z0-9][a-z0-9-]*: .+)", re.MULTILINE)
    if allowed.search(message):
        return 0
    print(
        f"Commit message must start with a ticket matching '{pattern}', OpenSpec id, or [SDD] for direct SDD repo maintenance, for example: E2EPROJECT-1: initialize product shell",
        file=sys.stderr,
    )
    return 1


def delivery_mode(args: argparse.Namespace) -> int:
    options = parse_pairs(args.options)
    output = run_delivery_mode(args.mode, options)
    if output is not None:
        print(output if isinstance(output, str) else json.dumps(output, indent=2))
    return 0


def configure_mode(args: argparse.Namespace) -> int:
    options = parse_configure_options(args.options)
    root = Path(options.get("root", REPO_ROOT))
    values = json.loads(options["values-json"]) if options.get("values-json") else {}
    result = run_configure_mode(args.mode, root, values, dry_run=options.get("dry-run", "false").lower() == "true")
    print(json.dumps(result, indent=2))
    return 0 if result.get("valid", True) else 1


def tool_install_or_update(args: argparse.Namespace) -> int:
    result = install_sdd_tool(Path(args.source), Path(args.target), args.version, args.action)
    print(json.dumps(result, indent=2))
    return 0


def parse_configure_options(args: list[str]) -> dict[str, str]:
    normalized = trim_remainder(args)
    options: dict[str, str] = {}
    index = 0
    while index < len(normalized):
        key = normalized[index]
        if key == "--dry-run":
            options["dry-run"] = "true"
            index += 1
            continue
        if key in {"--root", "--values-json"} and index + 1 < len(normalized):
            options[key[2:]] = normalized[index + 1]
            index += 2
            continue
        fail(f"Unsupported configure option: {key}")
    return options


def run_configure_mode(mode: str, root: Path, values: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    modes = {
        "AcquireProjectGuidance": configure_acquire_project_guidance,
        "Audit": configure_audit,
        "AuditQualityGates": configure_audit_quality_gates,
        "AuditRecommendedTools": configure_audit_recommended_tools,
        "DiscoverProjectGuidance": configure_discover_project_guidance,
        "EnsureDeliveryContext": configure_ensure_delivery_context,
        "InitProjectProfile": configure_init_project_profile,
        "InitQualityGateTemplates": configure_init_quality_templates,
        "MapProjectGuidanceStep": configure_map_project_guidance_step,
        "SetClientTools": configure_set_client_tools,
        "SetQualityConfig": configure_set_quality_config,
        "SyncWorktreeLocalConfig": configure_sync_worktree_local_config,
        "ValidateGiteaActionsRunner": configure_validate_runner,
    }
    handler = modes.get(mode)
    if handler is None:
        return {
            "mode": mode,
            "valid": False,
            "errors": [f"Unsupported native configure mode: {mode}"],
            "nextAction": "Port this mode into tools/sdd_cli before using it; PowerShell fallback is intentionally disabled.",
        }
    return handler(root, values, dry_run)


def install_sdd_tool(source: Path, target: Path, version: str | None, action: str) -> dict[str, Any]:
    source = source.resolve()
    target = target.resolve()
    if source == target:
        fail("Target must be a consumer repository, not the tool repository.")
    version = version or latest_sdd_tool_version(source)
    if not SDD_TOOL_VERSION_PATTERN.match(version):
        fail("Tool version must use vMAJOR.MINOR.PATCH, for example v0.1.0.")
    if action not in {"install", "update"}:
        fail(f"Unsupported tool action: {action}")
    if not source.exists():
        fail(f"Tool source does not exist: {source}")
    target.mkdir(parents=True, exist_ok=True)

    files = sdd_tool_files(source)
    old_manifest = read_json(target / SDD_TOOL_MANIFEST, optional=True)
    old_managed = set(old_manifest.get("managedFiles", []))
    owned = old_managed | ({SDD_TOOL_MANIFEST} if old_manifest else set())
    if action == "update" and not old_manifest:
        fail(f"Cannot update before install. Missing {SDD_TOOL_MANIFEST}.")
    if action == "install" and old_manifest:
        action = "update"

    collisions = unmanaged_collisions(source, target, files, owned)
    if collisions:
        fail("Refusing to overwrite unmanaged files: " + ", ".join(collisions[:10]))

    changed: list[str] = []
    for relative in files:
        src = source / relative
        dst = target / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        before = dst.read_bytes() if dst.exists() else None
        shutil.copy2(src, dst)
        if before != dst.read_bytes():
            changed.append(relative)

    new_managed = set(files)
    removed: list[str] = []
    for relative in sorted(old_managed - new_managed):
        dst = target / relative
        if dst.exists() and relative not in SDD_TOOL_PRESERVE_FILES:
            dst.unlink()
            removed.append(relative)
            remove_empty_parents(dst.parent, target)

    checksum = sdd_tool_checksum(target, files)
    manifest = {
        "schemaVersion": 1,
        "tool": "sdd-tool",
        "version": version,
        "sourceRepo": git_text(source, ["config", "--get", "remote.origin.url"]) or str(source),
        "sourceCommit": git_text(source, ["rev-parse", "HEAD"]),
        "installedAtUtc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "checksumSha256": checksum,
        "managedFiles": files,
        "preservedFiles": sorted(SDD_TOOL_PRESERVE_FILES),
    }
    write_json(target / SDD_TOOL_MANIFEST, manifest)
    return {
        "action": action,
        "version": version,
        "target": str(target),
        "managedFileCount": len(files),
        "changedFileCount": len(changed),
        "removedFileCount": len(removed),
        "manifest": SDD_TOOL_MANIFEST,
        "checksumSha256": checksum,
    }


def sdd_tool_files(root: Path) -> list[str]:
    files: set[str] = set()
    for relative in SDD_TOOL_INCLUDE_FILES:
        path = root / relative
        if path.exists() and not is_sdd_tool_excluded(relative):
            files.add(relative.replace("\\", "/"))
    for dirname in SDD_TOOL_INCLUDE_DIRS:
        base = root / dirname
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file():
                relative = path.relative_to(root).as_posix()
                if not is_sdd_tool_excluded(relative):
                    files.add(relative)
    return sorted(files)


def latest_sdd_tool_version(source: Path) -> str:
    tags = git_text(source, ["tag", "--list", "v*"])
    versions: list[tuple[int, int, int, str]] = []
    for tag in tags.splitlines():
        match = re.match(r"^v(\d+)\.(\d+)\.(\d+)$", tag.strip())
        if match:
            versions.append((int(match.group(1)), int(match.group(2)), int(match.group(3)), tag.strip()))
    if not versions:
        fail("No final release tags found. Pass --version vMAJOR.MINOR.PATCH or create a release tag first.")
    return max(versions)[3]


def is_sdd_tool_excluded(relative: str) -> bool:
    normalized = relative.replace("\\", "/")
    if Path(normalized).suffix in SDD_TOOL_EXCLUDE_SUFFIXES:
        return True
    if set(normalized.split("/")) & SDD_TOOL_EXCLUDE_SEGMENTS:
        return True
    return any(normalized == part or normalized.startswith(part + "/") for part in SDD_TOOL_EXCLUDE_PARTS)


def unmanaged_collisions(source: Path, target: Path, files: list[str], owned: set[str]) -> list[str]:
    collisions: list[str] = []
    for relative in files:
        dst = target / relative
        if not dst.exists() or relative in owned:
            continue
        if dst.read_bytes() != (source / relative).read_bytes():
            collisions.append(relative)
    return collisions


def sdd_tool_checksum(root: Path, files: list[str]) -> str:
    digest = hashlib.sha256()
    for relative in files:
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update((root / relative).read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def remove_empty_parents(path: Path, stop: Path) -> None:
    path = path.resolve()
    stop = stop.resolve()
    while path != stop and str(path).startswith(str(stop)):
        try:
            path.rmdir()
        except OSError:
            return
        path = path.parent


def git_text(root: Path, args: list[str]) -> str:
    try:
        result = subprocess.run(["git", *args], cwd=root, check=False, capture_output=True, text=True)
    except OSError:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def run_delivery_mode(mode: str, options: dict[str, str]) -> Any:
    if mode == "ReadProjectProfile":
        return read_ticket_pattern_from_profile(Path(require(options, "path")))
    if mode == "ReadDeliveryPolicy":
        path = Path(require(options, "path"))
        data = read_json(path)
        return nested(data, "workflow", "ticketKeyPattern") or data.get("ticketKeyPattern") or fail("delivery policy must define ticketKeyPattern.")
    if mode == "ExtractTicketKey":
        return extract_ticket_key(require(options, "message"), require(options, "pattern"), options.get("fallback", ""))
    if mode == "ReadCoverageThreshold":
        path = Path(require(options, "path"))
        fallback = int(options.get("fallback", "80"))
        if not path.exists():
            return str(fallback)
        data = read_json(path)
        return str(nested(data, "coverage", "minimumPercent") or fallback)
    if mode == "ReadCoberturaLineRate":
        root = ET.parse(require(options, "path")).getroot()
        rate = root.attrib.get("line-rate")
        if rate is None:
            fail(f"Could not read line-rate from {options['path']}.")
        return f"{round(float(rate) * 100, 2):.2f}"
    if mode == "ValidateReleaseManifest":
        result = validate_release_manifest(Path(require(options, "path")))
        if not result["valid"]:
            print(json.dumps(result, indent=2))
            raise SystemExit(1)
        return result
    if mode == "CreateReleaseManifest":
        create_release_manifest(options)
        return None
    if mode == "CreateArtifactPointer":
        create_artifact_pointer(options)
        return None
    if mode == "ArtifactPaths":
        return artifact_paths(require(options, "commit-sha"), options.get("deployment-provider"))
    if mode == "CheckGitIgnored":
        return {"path": require(options, "path"), "ignored": check_git_ignored(Path(options.get("root", REPO_ROOT)), require(options, "path"))}
    if mode == "NextRcVersion":
        return next_rc_version_output(options.get("tags", ""), options.get("target-version"))
    if mode == "ValidateTicketLock":
        return validate_ticket_lock(Path(options.get("path", Path(REPO_ROOT) / ".codex" / "delivery-context.local.json")), options)
    if mode == "ValidateDeploymentLane":
        return validate_deployment_lane(Path(options.get("path", Path(REPO_ROOT) / ".codex" / "parallel-delivery.local.json")), options)
    if mode == "ValidateParallelDeliveryDryRun":
        return validate_parallel_delivery_dry_run(Path(options.get("repo-root", REPO_ROOT)), require(options, "input-json"))
    if mode == "InitializeWorkflowTelemetry":
        return initialize_workflow_telemetry(Path(options.get("repo-root", REPO_ROOT)), require(options, "ticket-key"))
    if mode == "AppendWorkflowTelemetry":
        return append_workflow_telemetry(Path(options.get("repo-root", REPO_ROOT)), require(options, "ticket-key"), require(options, "input-json"))
    if mode == "ReadWorkflowTelemetry":
        return read_workflow_telemetry(Path(options.get("repo-root", REPO_ROOT)), require(options, "ticket-key"), options.get("input-json", "{}"))
    if mode == "ReadOpenProjectTimeTelemetry":
        return read_openproject_time_telemetry(require(options, "ticket-key"), require(options, "input-json"))
    if mode == "RenderOpenProjectTimeTelemetryComment":
        return render_openproject_time_telemetry_comment(require(options, "ticket-key"), require(options, "input-json"))
    if mode == "RenderTicketComment":
        return render_ticket_comment(require(options, "type"), require(options, "input-json"))
    if mode == "UpdateReleaseManifest":
        update_release_manifest(Path(require(options, "path")), require(options, "input-json"))
        return None
    if mode == "AuditSkillContracts":
        return audit_skill_contracts(Path(options.get("root", REPO_ROOT)), include_configure=options.get("include-configure", "false").lower() == "true")
    if mode == "ClassifyTicketReadiness":
        return asdict(classify_ticket_readiness(options.get("title", ""), options.get("description", "")))
    if mode == "ClassifyDeliveryRisk":
        paths = split_list(options.get("paths", ""))
        return asdict(classify_delivery_risk(paths, options.get("context", ""), int(options.get("changed-lines", "0"))))
    fail(f"Unsupported delivery mode: {mode}")


def configure_audit(root: Path, values: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    result = new_configure_result("Audit", dry_run, write_enabled=False)
    profile_path = root / ".codex" / "project-profile.json"
    if not profile_path.exists():
        add_bucket_item(result["findings"], ".codex/project-profile.json", "InitProjectProfile", "Run InitProjectProfile before provider-specific setup.", "error", "pre-start")
    if not (root / ".codex" / "project-profile.schema.json").exists():
        add_bucket_item(result["findings"], ".codex/project-profile.schema.json", "InitProjectProfile", "Run InitProjectProfile before provider-specific setup.", "error", "pre-start")

    client_tools = read_json(root / ".codex" / "client-tools.local.json", optional=True)
    result["actions"].append({"path": ".codex/client-tools.local.json", "key": "inferred.local-values", "severity": "info", "message": "Would set inferred local client tool value defaults during explicit setup.", "phase": "audit"})

    minimum = nested(client_tools, "pr", "minimumApprovals")
    if isinstance(minimum, dict):
        for branch in ("dev", "main"):
            value = minimum.get(branch)
            if not isinstance(value, int) or value < 0:
                add_bucket_item(
                    result["findings"],
                    ".codex/client-tools.local.json",
                    f"pr.minimumApprovals.{branch}",
                    f"pr.minimumApprovals.{branch} must be greater than or equal to 0.",
                    "warning",
                )

    state = read_json(root / ".codex" / "parallel-delivery.local.json", optional=True)
    for ticket in state.get("tickets", []):
        worktree = ticket.get("worktreePath")
        if not worktree:
            continue
        worktree_path = Path(worktree)
        if not worktree_path.is_absolute():
            worktree_path = root / worktree_path
        for relative in [".codex/client-tools.local.json", ".codex/quality.local.json"]:
            if not (worktree_path / relative).exists():
                add_bucket_item(
                    result["findings"],
                    relative,
                    "missing.worktree-runtime-config",
                    f"Ticket worktree is missing required local runtime file '{relative}'.",
                    "warning",
                )
    monitoring_root = root / "infra" / "monitoring"
    alert_path = monitoring_root / "grafana" / "provisioning" / "alerting" / "health-alerts.yml"
    if monitoring_root.exists() and not alert_path.exists():
        add_bucket_item(result["findings"], "infra/monitoring/grafana/provisioning/alerting/health-alerts.yml", "grafana.health-alerts", "Grafana health alert provisioning is missing.", "warning")
    return result


def configure_audit_quality_gates(root: Path, values: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    result = new_configure_result("AuditQualityGates", dry_run, write_enabled=False)
    result["actions"].append({"path": ".codex/client-tools.local.json", "key": "inferred.local-values", "severity": "info", "message": "Would set inferred local client tool value defaults during explicit setup.", "phase": "audit"})
    policy = read_json(root / ".codex" / "delivery-policy.json", optional=True)
    if policy and "agentOptimization" not in policy:
        add_bucket_item(result["findings"], ".codex/delivery-policy.json", "agentOptimization", "delivery-policy.json should define agentOptimization.", "warning")
    profile = load_project_profile(root)
    required = [gate.get("id") for gate in nested(profile, "quality", "gates") or [] if gate.get("required")]
    result["requiredGates"] = required
    result["valid"] = True
    return result


def configure_validate_runner(root: Path, values: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    checks = {
        "workflowDirectory": (root / ".gitea" / "workflows").exists(),
        "runnerExample": (root / "infra" / "gitea" / "runner.env.example").exists(),
        "lefthook": (root / "lefthook.yml").exists(),
    }
    return {"mode": "ValidateGiteaActionsRunner", "valid": all(checks.values()), "checks": checks}


def configure_init_project_profile(root: Path, values: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    codex = root / ".codex"
    providers = codex / "providers"
    codex.mkdir(parents=True, exist_ok=True)
    providers.mkdir(parents=True, exist_ok=True)
    schema_path = codex / "project-profile.schema.json"
    profile_path = codex / "project-profile.json"
    local_profile_path = codex / "project-profile.local.json"
    changed = False
    actions: list[dict[str, str]] = []

    if not schema_path.exists():
        changed = True
        if not dry_run:
            write_json(schema_path, {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object"})
        actions.append({"path": ".codex/project-profile.schema.json", "key": "created", "severity": "info", "message": "Created .codex/project-profile.schema.json.", "phase": "apply"})
    else:
        actions.append({"path": ".codex/project-profile.schema.json", "key": "exists", "severity": "info", "message": "Template already exists: .codex/project-profile.schema.json", "phase": "apply"})

    if not profile_path.exists():
        changed = True
        profile = {
            "$schema": "./project-profile.schema.json",
            "schemaVersion": 1,
            "providers": {
                "ticket": {"id": "example-ticket", "adapter": ".codex/providers/ticket.example.md"},
                "repository": {"id": "example-repository", "adapter": ".codex/providers/repository.example.md"},
                "review": {"id": "example-review", "adapter": ".codex/providers/repository.example.md"},
                "artifact": {"id": "example-artifact", "adapter": ".codex/providers/artifact.example.md"},
                "deployment": {"id": "example-deployment", "adapter": ".codex/providers/deployment.example.md"},
            },
            "workflow": {"ticketKeyPattern": "TICKET-[0-9]+", "baseBranch": "dev", "branchPrefix": "codex"},
            "quality": {"coverageMinimumPercent": 80, "gates": []},
            "adapters": {
                "ticket": ".codex/providers/ticket.example.md",
                "repository": ".codex/providers/repository.example.md",
                "review": ".codex/providers/repository.example.md",
                "artifact": ".codex/providers/artifact.example.md",
                "deployment": ".codex/providers/deployment.example.md",
            },
        }
        if not dry_run:
            write_json(profile_path, profile)
        actions.append({"path": ".codex/project-profile.json", "key": "created", "severity": "info", "message": "Created .codex/project-profile.json.", "phase": "apply"})
    else:
        actions.append({"path": ".codex/project-profile.json", "key": "exists", "severity": "info", "message": "Template already exists: .codex/project-profile.json", "phase": "apply"})

    if not local_profile_path.exists():
        changed = True
        local_profile = {
            "$schema": "./project-profile.schema.json",
            "stack": {"languages": [], "frameworks": [], "testFrameworks": []},
            "adapters": {},
        }
        if not dry_run:
            write_json(local_profile_path, local_profile)
        actions.append({"path": ".codex/project-profile.local.json", "key": "created", "severity": "info", "message": "Created ignored stack/profile overlay.", "phase": "apply"})
    else:
        actions.append({"path": ".codex/project-profile.local.json", "key": "exists", "severity": "info", "message": "Template already exists: .codex/project-profile.local.json", "phase": "apply"})

    for name in ("ticket.example.md", "repository.example.md", "artifact.example.md", "deployment.example.md"):
        example = providers / name
        if not example.exists():
            changed = True
            if not dry_run:
                example.write_text(f"# {name}\n\nprovider-neutral scaffold\n", encoding="utf-8")

    return {"mode": "InitProjectProfile", "valid": True, "changed": changed, "path": ".codex/project-profile.json", "dryRun": dry_run, "actions": actions}


def configure_init_quality_templates(root: Path, values: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    path = root / ".codex" / "delivery-policy.json"
    data = read_json(REPO_ROOT / ".codex" / "delivery-policy.json")
    changed = not path.exists()
    if not dry_run:
        write_json(path, data)
    return {"mode": "InitQualityGateTemplates", "valid": True, "changed": changed, "path": ".codex/delivery-policy.json", "dryRun": dry_run}


def configure_set_quality_config(root: Path, values: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    path = root / ".codex" / "quality.local.json"
    if not values:
        return {"mode": "SetQualityConfig", "valid": False, "errors": ["--values-json is required."]}
    if not dry_run:
        write_json(path, values)
    return {"mode": "SetQualityConfig", "valid": True, "changed": True, "path": str(path), "dryRun": dry_run}


def configure_set_client_tools(root: Path, values: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    path = root / ".codex" / "client-tools.local.json"
    current = read_json(path, optional=True)
    merged = merge_dicts(current, values)
    if not dry_run:
        write_json(path, merged)
    return {"mode": "SetClientTools", "valid": True, "changed": True, "path": str(path), "dryRun": dry_run}


def configure_sync_worktree_local_config(root: Path, values: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    result = new_configure_result("SyncWorktreeLocalConfig", dry_run, write_enabled=not dry_run)
    worktrees = [Path(path) for path in values.get("worktreePaths", [])]
    for relative in ALLOWLISTED_LOCAL_CONFIG:
        source = root / relative
        required = relative != ".codex/tool-recommendations.local.json"
        if required and not source.exists():
            add_bucket_item(result["findings"], relative, "missing.required-source", f"Coordinator checkout is missing required local runtime file '{relative}'.", "error")
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
            result["actions"].append({"path": relative, "key": "sync.local-runtime-config", "severity": "info", "message": message, "phase": "apply"})
    result["valid"] = True
    return result


def configure_ensure_delivery_context(root: Path, values: dict[str, Any], dry_run: bool) -> dict[str, Any]:
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
        "actions": [{"path": ".codex/delivery-context.local.json", "key": "ensure-delivery-context", "severity": "info", "message": f"Create or update ticket context lock for {ticket_key}.", "phase": "apply"}],
    }


def configure_audit_recommended_tools(root: Path, values: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    detected = detect_stack_tags(root)
    topics = build_research_topics(detected)
    recommendations = build_recommendations(root, detected, topics)
    decisions = nested(read_json(root / ".codex" / "client-tools.local.json", optional=True), "recommendedTools") or {}
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
    return {
        "mode": "AuditRecommendedTools",
        "valid": True,
        "writeEnabled": False,
        "detectedTags": detected,
        "researchTopics": topics,
        "actions": [{"path": ".", "key": "detectedStack", "severity": "info", "message": f"Detected stack: {', '.join(detected)}", "phase": "audit"}],
        "findings": findings,
        "recommendations": filtered,
    }


def configure_discover_project_guidance(root: Path, values: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    audit = configure_audit_recommended_tools(root, values, dry_run)
    recommendations = [item for item in audit["recommendations"] if item["id"] != SEARCH_PLAN_ID]
    missing_skills = [item for item in recommendations if item.get("type") == "skill" and item.get("detected", True) and not item.get("targetExists", False)]
    suggested_guidance = [item for item in recommendations if item.get("type") != "skill"]
    user_added = normalize_added_guidance(values.get("additionalSkills", []))
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
            persisted = merge_dicts(existing_by_id.get(item.get("id"), {}), ensure_used_in_steps(item))
            persisted_recommendations.append(persisted)
        payload = {
            "schemaVersion": 1,
            "mode": "guarded-auto",
            "sourceCatalog": ".codex/tool-recommendations.common.json",
            "detectedTags": audit["detectedTags"],
            "researchTopics": audit["researchTopics"],
            "accepted": existing_catalog.get("accepted", []),
            "dismissed": existing_catalog.get("dismissed", []),
            "recommendations": persisted_recommendations,
            "notRecommended": merge_catalog_items(existing_catalog.get("notRecommended", []), [item for item in recommendations if item["id"] == "openproject-mcp-for-ticket-delivery"]),
        }
        write_json(local_path, payload)
        actions.append({"path": ".codex/tool-recommendations.local.json", "key": "persist-local-catalog", "severity": "info", "message": "Persist local project guidance catalog.", "phase": "apply"})
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
        "discoverySourcePriority": DISCOVERY_SOURCE_PRIORITY,
        "localRecommendationsPath": ".codex/tool-recommendations.local.json",
        "nextUserQuestion": "I researched extra useful skills, MCPs, plugins, tools, references, practices, and standards. Confirm these suggestions to record and install/configure supported items now, dismiss any you do not want, or name anything I missed.",
        "actions": actions,
    }


def configure_map_project_guidance_step(root: Path, values: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    if not values.get("workflowStep"):
        return {"mode": "MapProjectGuidanceStep", "valid": False, "errors": ["values.workflowStep is required."]}
    path = root / ".codex" / "tool-recommendations.local.json"
    current = load_tool_recommendations_catalog(root)
    if not current:
        current = {
            "schemaVersion": 1,
            "mode": "guarded-auto",
            "sourceCatalog": ".codex/tool-recommendations.common.json",
            "detectedTags": [],
            "researchTopics": [],
            "recommendations": [ensure_used_in_steps(item) for item in build_recommendations(root, detect_stack_tags(root), build_research_topics(detect_stack_tags(root))) if item["id"] != SEARCH_PLAN_ID],
            "notRecommended": [],
        }
    ids = set(values.get("recommendationIds", []))
    for item in current.get("recommendations", []):
        if item.get("id") not in ids:
            continue
        used = item.setdefault("usedInSteps", [])
        step = values["workflowStep"]
        if step not in used:
            used.append(step)
    if not dry_run:
        write_json(path, current)
    return {"mode": "MapProjectGuidanceStep", "valid": True, "writeEnabled": not dry_run, "changed": True, "path": str(path), "dryRun": dry_run}


def configure_acquire_project_guidance(root: Path, values: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    result = new_configure_result("AcquireProjectGuidance", dry_run, write_enabled=not dry_run)
    final_guidance = values.get("finalConfirmedGuidance", [])
    restart_items: list[str] = []
    for item in final_guidance:
        if "installCommand" in item:
            raise CliError(f"{item.get('name', item.get('id', 'guidance'))} rejects installCommand.")
        name = item.get("name", item.get("id", "guidance"))
        if item.get("installPreference") == "docker-preferred":
            docker = item.get("dockerAlternative")
            if docker and docker.get("image"):
                result["actions"].append({"path": name, "key": "docker-preferred", "severity": "info", "message": f"Use Docker-preferred runtime {docker['image']}.", "phase": "plan"})
            else:
                result["warnings"].append({"path": name, "key": "docker-preferred.blocked", "severity": "warning", "message": "Docker-preferred metadata is incomplete.", "phase": "plan"})
        if item.get("userActionRequired"):
            result["warnings"].append({"path": name, "key": "guarded-install-plan", "severity": "warning", "message": "User action is required for this guarded install.", "phase": "plan"})
        if item.get("installMethod") == "manual-copy" and item.get("sourceKind") is None:
            result["warnings"].append({"path": name, "key": "validation", "severity": "warning", "message": "manual-copy guidance should include sourceKind.", "phase": "plan"})
        if item.get("requiresIdeRestart"):
            restart_items.append(f"{name} [ide-restart]")
        if item.get("requiresSystemReboot"):
            restart_items.append(f"{name} [system-reboot]")
    if restart_items:
        result["findings"].append({"path": ".", "key": "important.restart-summary", "severity": "info", "message": f"complete all feasible installs first, then restart/reboot for: {', '.join(restart_items)}.", "phase": "handoff"})
    result["valid"] = True
    return result


def search_memory(root: Path, queries: list[str], list_topics: bool) -> Any:
    memory_root = root / ".codex" / "memory"
    if not memory_root.exists():
        raise CliError(f"Memory root not found: {memory_root}")
    skip = {"MEMORY.md", "memory_summary.md", "retrieval-policy.md"}
    entries: list[dict[str, str]] = []
    for path in sorted(memory_root.glob("*.md")):
        if path.name in skip:
            continue
        content = path.read_text(encoding="utf-8")
        for match in re.finditer(r"(?ms)^##\s+(.+?)\n(.*?)(?=^##\s+|\Z)", content):
            body = match.group(2)
            plain = re.sub(r"(?m)^-\s+(Type|Status|Source|Last verified):.+$", "", body)
            plain = re.sub(r"\s+", " ", plain).strip()
            entries.append(
                {
                    "file": path.relative_to(root).as_posix(),
                    "title": match.group(1).strip(),
                    "type": find_meta(body, "Type"),
                    "status": find_meta(body, "Status"),
                    "source": find_meta(body, "Source"),
                    "lastVerified": find_meta(body, "Last verified"),
                    "excerpt": plain[:240] + ("..." if len(plain) > 240 else ""),
                }
            )
    if list_topics:
        return [{k: row[k] for k in ("file", "title", "type", "status", "lastVerified")} for row in entries]
    terms = [term.strip() for query in queries for term in query.split(",") if term.strip()]
    if terms:
        return [row for row in entries if all(term.lower() in " ".join(row.values()).lower() for term in terms)]
    return {
        "memoryRoot": memory_root.relative_to(root).as_posix(),
        "usage": "python -m tools.sdd_cli memory search --query term1 --query term2 or --list-topics",
        "files": [path.relative_to(root).as_posix() for path in sorted(memory_root.glob("*.md"))],
    }


def read_ticket_pattern(root: Path) -> str:
    profile = load_project_profile(root)
    pattern = nested(profile, "workflow", "ticketKeyPattern")
    if pattern:
        return pattern
    policy = root / ".codex" / "delivery-policy.json"
    data = read_json(policy, optional=True)
    return data.get("ticketKeyPattern", "E2EPROJECT-[0-9]+")


def read_ticket_pattern_from_profile(path: Path) -> str:
    pattern = nested(read_json(path), "workflow", "ticketKeyPattern")
    if not pattern:
        fail(f"{path.name} must define workflow.ticketKeyPattern.")
    return pattern


def extract_ticket_key(message: str, pattern: str, fallback: str = "") -> str:
    first = message.replace("\r\n", "\n").split("\n", 1)[0]
    direct = re.match(rf"^({pattern}): ", first)
    if direct:
        return direct.group(1)
    merge = re.match(rf"^Merge pull request '({pattern}):", first)
    return merge.group(1) if merge else fallback


def validate_release_manifest(path: Path) -> dict[str, Any]:
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


def artifact_paths(commit: str, provider: str | None) -> dict[str, str]:
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


def selected_deployment_provider(root: Path) -> str:
    profile = load_project_profile(root)
    return nested(profile, "providers", "deployment", "id") or "azure-appservice"


def check_git_ignored(root: Path, path: str) -> bool:
    completed = subprocess.run(["git", "check-ignore", path], cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    return completed.returncode == 0


def next_rc_version_output(tags_text: str, target_version: str | None) -> dict[str, str]:
    finals: list[tuple[int, int, int]] = []
    rcs: list[tuple[int, int, int, int]] = []
    for tag in split_list(tags_text.replace(" ", "\n")):
        if match := re.match(r"^v(\d+)\.(\d+)\.(\d+)$", tag):
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


def validate_ticket_lock(path: Path, options: dict[str, str]) -> dict[str, Any]:
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


def validate_deployment_lane(path: Path, options: dict[str, str]) -> dict[str, Any]:
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
    return {"path": str(path), "active": True, "valid": not errors, "errors": errors, "deploymentLanePolicy": policy}


def validate_parallel_delivery_dry_run(root: Path, input_json: str) -> dict[str, Any]:
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
    return {"valid": not errors, "errors": errors, "activeTicketCount": active_count, "deploymentLanePolicy": policy}


def telemetry_path(root: Path) -> Path:
    return root / ".codex" / "agent-telemetry.local.jsonl"


def initialize_workflow_telemetry(root: Path, ticket_key: str) -> dict[str, Any]:
    path = telemetry_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.exists()
    path.write_text("", encoding="utf-8")
    return {"exists": path.exists(), "cleared": existed, "ticketKey": ticket_key, "path": str(path)}


def append_workflow_telemetry(root: Path, ticket_key: str, input_json: str) -> dict[str, Any]:
    path = telemetry_path(root)
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
    context = json.loads(input_json)
    rows = []
    path = telemetry_path(root)
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("ticketKey") == ticket_key:
                rows.append(row)
    stages = collapse_stages(rows)
    return {
        "ticketKey": ticket_key,
        "status": context.get("status", ""),
        "currentRoute": context.get("currentRoute", ""),
        "totalElapsedMilliseconds": sum(stage.get("elapsedMilliseconds", 0) for stage in stages),
        "stages": stages,
    }


def read_openproject_time_telemetry(ticket_key: str, input_json: str) -> dict[str, Any]:
    data = json.loads(input_json)
    rows: list[dict[str, Any]] = []
    for entry in data.get("timeEntries", []):
        raw = nested(entry, "comment", "raw") or ""
        parsed = parse_time_comment(raw, ticket_key)
        if parsed:
            rows.append(parsed)
    stages = collapse_stages(rows)
    return {
        "ticketKey": ticket_key,
        "status": data.get("status", ""),
        "currentRoute": data.get("currentRoute", ""),
        "totalElapsedMilliseconds": sum(stage.get("elapsedMilliseconds", 0) for stage in stages),
        "stages": stages,
    }


def render_openproject_time_telemetry_comment(ticket_key: str, input_json: str) -> str:
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


def collapse_stages(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def render_ticket_comment(comment_type: str, input_json: str) -> str:
    data = json.loads(input_json)
    if comment_type == "WorkflowTiming":
        total = int(data.get("totalElapsedMilliseconds", 0) or sum(int(item.get("elapsedMilliseconds", 0) or 0) for item in data.get("stages", [])))
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
        return "\n".join(
            [
                f"IA generated PROD deployment: {data.get('finalReleaseVersion', 'unknown')}",
                "",
                f"**Status:** {data.get('status', '')}",
                f"- Primary ticket: `{data.get('ticketKey', '')}` ({data.get('ticketState', '')})",
                f"- Included tickets: {tickets}",
                f"- Lineage: `{commit}` -> `{data.get('sourceRcVersion', '')}` -> `{data.get('finalReleaseVersion', '')}`",
                f"**PROD URL:** [open production]({data.get('prodUrl', '')})",
            ]
        )
    marker = {
        "QADeployment": "IA generated QA deployment",
        "E2EQA": "IA generated E2E QA",
    }.get(comment_type, f"IA generated {comment_type}")
    return f"{marker}: {data.get('ticketKey', data.get('finalReleaseVersion', 'unknown'))}\n\n**Status:** {data.get('status', '')}"


def update_release_manifest(path: Path, input_json: str) -> None:
    data = read_json(path, optional=True)
    data.update(json.loads(input_json))
    write_json(path, data)


def audit_skill_contracts(root: Path, include_configure: bool = False) -> dict[str, Any]:
    skill_root = root / ".codex" / "skills"
    results: list[dict[str, Any]] = []
    provider_specific_findings: list[str] = []
    required_sections = ["Overview", "Shared Context", "Workflow", "Output", "Failure Rules"]
    required_terms = [".codex/skills/_shared/delivery-contract.md", "docs/context-management.md", "ticket", "validation", "handoff"]
    support_skill_names = {"caveman", "domain-modeling", "grill-me", "grill-with-docs", "grilling", "ponytail", "ponytail-audit", "ponytail-debt", "ponytail-help", "ponytail-review"}
    profile_findings = profile_audit_findings(root)
    for path in sorted(skill_root.rglob("SKILL.md")):
        skill_name = path.parent.name
        if skill_name in support_skill_names:
            continue
        if not include_configure and skill_name.startswith("configure-"):
            continue
        content = path.read_text(encoding="utf-8")
        missing_sections = [section for section in required_sections if not re.search(rf"(?m)^##\s+{re.escape(section)}\s*$", content)]
        missing_terms = [term for term in required_terms if term not in content]
        results.append({"path": path.relative_to(root).as_posix(), "passed": not missing_sections and not missing_terms, "missingSections": missing_sections, "missingTerms": missing_terms})
    return {
        "checked": len(results),
        "passed": sum(1 for item in results if item["passed"]),
        "failed": sum(1 for item in results if not item["passed"]),
        "profilePassed": not profile_findings,
        "profileFindings": profile_findings,
        "providerSpecificPassed": not provider_specific_findings,
        "providerSpecificFindings": provider_specific_findings,
        "results": results,
    }


def profile_audit_findings(root: Path) -> list[str]:
    findings: list[str] = []
    profile_path = root / ".codex" / "project-profile.json"
    schema_path = root / ".codex" / "project-profile.schema.json"
    if not profile_path.exists():
        findings.append("Missing .codex/project-profile.json.")
    else:
        profile = load_project_profile(root)
        if not isinstance(profile.get("schemaVersion"), int) or profile.get("schemaVersion", 0) < 1:
            findings.append("project-profile.json schemaVersion must be at least 1.")
        if not nested(profile, "workflow", "ticketKeyPattern"):
            findings.append("project-profile.json must define workflow.ticketKeyPattern.")
        adapters = profile.get("adapters")
        if adapters is None:
            findings.append("project-profile.json must define adapters.")
        else:
            for name, adapter_path in adapters.items():
                if not adapter_path:
                    findings.append(f"Adapter '{name}' has an empty path.")
                    continue
                if os.path.isabs(adapter_path):
                    findings.append(f"Adapter '{name}' must use a repo-relative path.")
                    continue
                resolved = (root / adapter_path).resolve()
                if not str(resolved).startswith(str(root.resolve())):
                    findings.append(f"Adapter '{name}' resolves outside the repository.")
                    continue
                if not resolved.exists():
                    findings.append(f"Adapter '{name}' path does not exist: {adapter_path}.")
    if not schema_path.exists():
        findings.append("Missing .codex/project-profile.schema.json.")
    return findings


def classify_ticket_readiness(title: str, description: str) -> TicketReadinessResult:
    missing: list[str] = []
    normalized = description.lower()
    if len(description.strip()) < 15:
        missing.append("user-visible goal")
    if "acceptance" not in normalized:
        missing.append("acceptance criteria")
    if "validation" not in normalized and "test" not in normalized:
        missing.append("validation expectation")
    if not missing:
        return TicketReadinessResult("ready", [])
    if "user-visible goal" in missing:
        return TicketReadinessResult("blocked", missing)
    return TicketReadinessResult("refinable", missing)


def classify_delivery_risk(paths: list[str], context: str, changed_lines: int) -> DeliveryRiskResult:
    risks: list[str] = []
    joined = " ".join(paths + [context]).lower()
    high_terms = ["auth", "authorization", "migration", "deployment", "secret", "public api", "/health", "release", "rollback", "hotfix", ".gitea/workflows"]
    if any(term in joined for term in high_terms):
        risks.append("Touches deployment or release surface.")
        return DeliveryRiskResult("high", risks)
    if all(path.startswith("docs/") for path in paths) and changed_lines <= 20:
        return DeliveryRiskResult("low", ["Localized documentation-only change."])
    return DeliveryRiskResult("standard", ["Normal implementation or test work."])


def detect_stack_tags(root: Path) -> list[str]:
    tags: list[str] = []
    if (root / "package.json").exists():
        tags.append("node")
    if (root / "tsconfig.json").exists() or any(root.rglob("*.ts")) or any(root.rglob("*.tsx")):
        tags.append("typescript")
    if any_contains(root, ["src", "."], ["*.tsx", "package.json"], "react"):
        tags.extend(["react", "web-ui"])
    if (root / "pyproject.toml").exists() or any(root.rglob("*.py")):
        tags.append("python")
    if (root / "pom.xml").exists() or (root / "build.gradle").exists() or (root / "build.gradle.kts").exists():
        tags.append("java")
    if (root / "Dockerfile").exists() or any(root.rglob("compose.yml")):
        tags.append("docker")
    if any(root.rglob("*.tf")):
        tags.append("terraform")
    if any_contains(root, ["."], ["*.yaml", "*.yml"], "apiVersion:|kind: Deployment|kind: Service"):
        tags.append("kubernetes")
    if any_contains(root, ["src", "docs", "openspec"], ["*.md", "*.yaml", "*.yml"], "REST|API"):
        tags.append("rest-api")
    if (root / ".codex" / "quality.common.json").exists():
        tags.extend(["coverage", "security"])
    if (root / "infra" / "openproject").exists():
        tags.append("openproject")
    if (root / "infra" / "gitea").exists():
        tags.append("gitea")
    if (root / ".gitea" / "workflows").exists():
        tags.append("gitea-actions-runner")
    if (root / "infra" / "nexus").exists():
        tags.extend(["nexus", "nexus-artifacts"])
    deployment = selected_deployment_provider(root)
    if deployment == "rancher-desktop":
        tags.append("rancher-desktop")
    if (root / "infra" / "monitoring" / "grafana").exists():
        tags.append("grafana")
    if any_contains(root, ["infra", ".codex", "docs"], ["*.json", "*.md", "*.yml", "*.yaml"], "Seq"):
        tags.append("seq")
    if (root / ".codex" / "skills" / "playwright" / "SKILL.md").exists():
        tags.extend(["e2e", "browser-e2e", "playwright-guidance"])
    if (root / "openspec").exists():
        tags.append("openspec")
    if (root / ".codex" / "skills" / "tdd" / "SKILL.md").exists():
        tags.extend(["clean-code", "architecture-guidance"])
    return sorted(set(tags))


def build_research_topics(detected: list[str]) -> list[dict[str, Any]]:
    topics: list[dict[str, Any]] = []
    definitions = [
        ("web-ui", ["react", "web-ui"], "Web UI"),
        ("rest-api", ["rest-api", "python", "java"], "REST/API"),
        ("qa-testing", ["coverage", "browser-e2e", "playwright-guidance"], "QA / Testing"),
        ("security", ["security"], "Security"),
        ("delivery-tools", ["openproject", "gitea", "gitea-actions-runner", "nexus-artifacts", "rancher-desktop", "grafana", "seq"], "Delivery tools and environments"),
        ("containers-iac", ["docker", "terraform", "kubernetes"], "Containers / IaC"),
        ("code-standards", ["clean-code", "architecture-guidance"], "Code standards and architecture"),
    ]
    for topic_id, requires, area in definitions:
        matched = [tag for tag in requires if tag in detected]
        if matched:
            topics.append({"id": topic_id, "area": area, "matchedTags": matched})
    return topics


def build_recommendations(root: Path, detected: list[str], topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    catalog = load_tool_recommendations_catalog(root)
    catalog_items = [ensure_used_in_steps(item) for item in catalog.get("recommendations", [])]
    recommendations = [
        {
            "id": SEARCH_PLAN_ID,
            "name": "Project guidance search plan",
            "type": "guidance-search-plan",
            "installMethod": "research-then-guarded-install",
            "sourceDiscovery": "official-first-internet-search",
            "discoverySourcePriority": DISCOVERY_SOURCE_PRIORITY,
            "topics": topics,
        },
        skill_recommendation(root, "openai-security-best-practices-skill", "OpenAI security best practices skill", ".codex/skills/security-best-practices/SKILL.md", "https://github.com/openai/skills/tree/main/skills/.curated/security-best-practices", "openai-official", detected, ["security"], ["https://github.com/openai/skills/tree/main/skills/.curated/security-best-practices"], ["https://owasp.org/www-project-top-ten/"]),
        skill_recommendation(root, "openai-playwright-skill", "OpenAI Playwright skill", ".codex/skills/playwright/SKILL.md", "https://github.com/openai/skills/tree/main/skills/.curated/playwright", "openai-official", detected, ["browser-e2e", "playwright-guidance"], ["https://github.com/openai/skills/tree/main/skills/.curated/playwright"], ["https://playwright.dev/docs/best-practices"]),
        *catalog_items,
        {
            "id": "clean-code-practice-guidance",
            "name": "Clean code practice guidance",
            "type": "practice",
            "usedInSteps": [],
        },
        {
            "id": "qa-automation-practice-guidance",
            "name": "QA automation practice guidance",
            "type": "practice",
            "usedInSteps": [],
        },
        {
            "id": "security-review-standard-guidance",
            "name": "Security review standard guidance",
            "type": "standard",
            "usedInSteps": [],
        },
        {
            "id": "openproject-mcp-for-ticket-delivery",
            "name": "OpenProject MCP for ticket delivery",
            "type": "not-recommended",
            "message": "OpenProject MCP is intentionally not recommended because repo-local skills must use the configured OpenProject API.",
        },
    ]
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in recommendations:
        if not item or item.get("id") in seen:
            continue
        seen.add(item["id"])
        output.append(item)
    return output


def skill_recommendation(
    root: Path,
    item_id: str,
    name: str,
    target: str,
    source: str,
    source_kind: str,
    detected: list[str],
    requires: list[str],
    candidate_skill_sources: list[str],
    official_sources: list[str],
) -> dict[str, Any]:
    matched = all(tag in detected for tag in requires)
    target_exists = (root / target).exists()
    return {
        "id": item_id,
        "name": name,
        "type": "skill",
        "detected": matched,
        "target": target,
        "targetExists": target_exists,
        "requiresUserConfirmation": True,
        "installStatus": "installed" if target_exists else "proposed",
        "sourceDiscovery": "official-first-internet-search",
        "sourceKind": source_kind,
        "source": source,
        "installMethod": "manual-copy",
        "candidateSkillSources": candidate_skill_sources,
        "officialSkillSources": candidate_skill_sources,
        "officialSources": official_sources,
        "usedInSteps": [],
    }


def recommendation_from_catalog(root: Path, item_id: str) -> dict[str, Any] | None:
    catalog = load_tool_recommendations_catalog(root)
    for item in catalog.get("recommendations", []):
        if item.get("id") == item_id:
            return ensure_used_in_steps(item)
    return None


def ensure_used_in_steps(item: dict[str, Any]) -> dict[str, Any]:
    clone = json.loads(json.dumps(item))
    clone.setdefault("usedInSteps", [])
    return clone


def build_stack_context_findings(root: Path, detected: list[str]) -> list[dict[str, str]]:
    context_text = "\n".join(
        (root / path).read_text(encoding="utf-8")
        for path in ["docs/architecture.md", "docs/development.md", "docs/deployment.md", "openspec/config.yaml"]
        if (root / path).exists()
    )
    findings: list[dict[str, str]] = []
    checks: dict[str, str] = {}
    for tag, pattern in checks.items():
        if tag in detected and not re.search(pattern, context_text, re.IGNORECASE):
            findings.append({"path": "docs/, openspec/config.yaml", "key": f"stack-context.{tag}", "severity": "warning", "message": f"Detected stack tag '{tag}' but durable docs/OpenSpec context do not mention it."})
    for item in build_recommendations(root, detected, build_research_topics(detected)):
        if item.get("type") == "skill" and item.get("detected") and not item.get("targetExists"):
            findings.append({"path": item.get("target", "."), "key": f"skill-gap.{item['id']}", "severity": "warning", "message": f"Detected stack suggests missing skill '{item['id']}'."})
    return findings


def normalize_added_guidance(items: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, str):
            normalized.append({"name": item})
        elif isinstance(item, dict):
            normalized.append(item)
    return normalized


def parse_time_comment(raw: str, ticket_key: str) -> dict[str, Any] | None:
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


def new_configure_result(mode: str, dry_run: bool, write_enabled: bool) -> dict[str, Any]:
    return {"mode": mode, "dryRun": dry_run, "writeEnabled": write_enabled, "actions": [], "findings": [], "recommendations": [], "warnings": [], "valid": True}


def add_bucket_item(bucket: list[dict[str, str]], path: str, key: str, message: str, severity: str, phase: str = "post-start") -> None:
    bucket.append({"path": path, "key": key, "severity": severity, "phase": phase, "message": message})


def any_contains(root: Path, directories: list[str], patterns: list[str], regex: str) -> bool:
    compiled = re.compile(regex, re.IGNORECASE)
    for directory in directories:
        base = root / directory
        if not base.exists():
            continue
        for pattern in patterns:
            for path in base.rglob(pattern):
                try:
                    if compiled.search(path.read_text(encoding="utf-8", errors="ignore")):
                        return True
                except OSError:
                    continue
    return False


def merge_dicts(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    output = json.loads(json.dumps(left))
    for key, value in right.items():
        if isinstance(value, dict) and isinstance(output.get(key), dict):
            output[key] = merge_dicts(output[key], value)
        else:
            output[key] = value
    return output


def load_project_profile(root: Path) -> dict[str, Any]:
    base = read_json(root / ".codex" / "project-profile.json", optional=True)
    local = read_json(root / ".codex" / "project-profile.local.json", optional=True)
    return merge_dicts(base, local)


def load_tool_recommendations_catalog(root: Path) -> dict[str, Any]:
    base = read_json(root / ".codex" / "tool-recommendations.common.json", optional=True)
    local = read_json(root / ".codex" / "tool-recommendations.local.json", optional=True)
    merged = merge_dicts({key: value for key, value in base.items() if key not in {"recommendations", "notRecommended"}}, {key: value for key, value in local.items() if key not in {"recommendations", "notRecommended"}})
    merged["recommendations"] = merge_catalog_items(base.get("recommendations", []), local.get("recommendations", []))
    merged["notRecommended"] = merge_catalog_items(base.get("notRecommended", []), local.get("notRecommended", []))
    return {key: value for key, value in merged.items() if value not in ({}, [])}


def merge_catalog_items(base_items: list[dict[str, Any]], local_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    positions: dict[str, int] = {}
    for item in base_items:
        item_id = item.get("id")
        if not item_id:
            continue
        positions[item_id] = len(output)
        output.append(ensure_used_in_steps(item))
    for item in local_items:
        item_id = item.get("id")
        if not item_id:
            continue
        if item_id in positions:
            output[positions[item_id]] = merge_dicts(output[positions[item_id]], ensure_used_in_steps(item))
        else:
            positions[item_id] = len(output)
            output.append(ensure_used_in_steps(item))
    return output


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def min_text(left: str | None, right: str | None) -> str:
    if not left:
        return right or ""
    if not right:
        return left
    return min(left, right)


def max_text(left: str | None, right: str | None) -> str:
    if not left:
        return right or ""
    if not right:
        return left
    return max(left, right)


def format_duration(milliseconds: int) -> str:
    if milliseconds <= 0:
        return "no time"
    total_seconds = milliseconds // 1000
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {seconds:02d}s"
    if minutes:
        seconds_text = "00" if seconds == 0 else str(seconds)
        return f"{minutes}m {seconds_text}s"
    return f"{seconds}s"


def parse_pairs(items: list[str]) -> dict[str, str]:
    args = trim_remainder(items)
    pairs: dict[str, str] = {}
    index = 0
    while index < len(args):
        key = args[index]
        if not key.startswith("--"):
            fail(f"Expected --option, got: {key}")
        if index + 1 >= len(args):
            fail(f"Missing value for option {key}")
        pairs[key[2:]] = args[index + 1]
        index += 2
    return pairs


def trim_remainder(items: list[str]) -> list[str]:
    return items[1:] if items and items[0] == "--" else items


def split_list(value: str) -> list[str]:
    return [item for item in re.split(r"[\s,]+", value.strip()) if item]


def sh_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def nested(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def read_json(path: Path, optional: bool = False) -> dict[str, Any]:
    if optional and not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def find_meta(body: str, label: str) -> str:
    match = re.search(rf"(?m)^-\s+{re.escape(label)}:\s*(.+)$", body)
    return match.group(1).strip() if match else ""


def require(options: dict[str, str], key: str) -> str:
    value = options.get(key)
    if not value:
        fail(f"Missing required option: --{key}")
    return value


def fail(message: str) -> Any:
    raise CliError(message)
