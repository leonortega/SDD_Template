from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON_REQUIRES = (3, 11)
E2E_IMAGE = "agentic/e2e-ci:playwright-1.57.0-1"


class CliError(RuntimeError):
    pass


Runner = Callable[[list[str], Path | None, dict[str, str] | None], int]


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

    e2e = sub.add_parser("e2e")
    e2e_sub = e2e.add_subparsers(dest="action", required=True)
    docker = e2e_sub.add_parser("docker")
    docker.add_argument("playwright_args", nargs=argparse.REMAINDER)
    docker.set_defaults(func=e2e_docker)

    delivery = sub.add_parser("delivery")
    delivery.add_argument("mode")
    delivery.add_argument("options", nargs=argparse.REMAINDER)
    delivery.set_defaults(func=delivery_mode)

    configure = sub.add_parser("configure")
    configure.add_argument("mode", nargs="?", default="Audit")
    configure.add_argument("options", nargs=argparse.REMAINDER)
    configure.set_defaults(func=configure_mode)

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
                print(f"WhatIf: resource group '{group}' would be created in '{args.location}'. Skipping deployment what-if for '{env_name}' until the group exists.")
                continue
            command = [
                "az", "deployment", "group", "what-if",
                "--resource-group", group,
                "--name", deployment_name,
                "--template-file", str(template),
                "--parameters", str(parameters),
            ]
        else:
            create = [
                "az", "group", "create",
                "--name", group,
                "--location", args.location,
                "--tags", "project=agentic-e2e", f"env={env_name}", "managedBy=bicep",
                "--output", "none",
            ]
            code = runner(create, REPO_ROOT, None)
            if code:
                return code
            command = [
                "az", "deployment", "group", "create",
                "--resource-group", group,
                "--name", deployment_name,
                "--template-file", str(template),
                "--parameters", str(parameters),
                "--output", "table",
            ]
        code = runner(command, REPO_ROOT, None)
        if code:
            return code
    return 0


def e2e_docker(args: argparse.Namespace, runner: Runner = default_runner) -> int:
    config = read_json(REPO_ROOT / ".codex" / "client-tools.local.json", optional=True)
    site_url = os.environ.get("E2E_SITE_URL") or nested(config, "azure", "qa", "siteUrl")
    api_url = os.environ.get("E2E_API_URL") or nested(config, "azure", "qa", "apiUrl")
    if not site_url or not api_url:
        raise CliError("E2E_SITE_URL and E2E_API_URL are required, or set azure.qa.siteUrl/apiUrl in .codex/client-tools.local.json.")

    if runner(["docker", "image", "inspect", E2E_IMAGE], REPO_ROOT, None):
        raise CliError(f"Docker image '{E2E_IMAGE}' is missing. Run config infra / BuildGiteaActionsImages before local Docker E2E.")

    test_command = ["npm", "ci", "&&", "npx", "playwright", "test", *trim_remainder(args.playwright_args)]
    shell_command = " ".join(sh_quote(part) for part in test_command)
    env = os.environ.copy()
    env["E2E_SITE_URL"] = site_url
    env["E2E_API_URL"] = api_url
    command = [
        "docker", "run", "--rm", "--ipc=host",
        "-e", f"E2E_SITE_URL={site_url}",
        "-e", f"E2E_API_URL={api_url}",
        "-v", f"{REPO_ROOT.as_posix()}:/workspace",
        "-w", "/workspace/tests/SDDTemplate.E2ETests",
        E2E_IMAGE,
        "bash", "-lc", shell_command,
    ]
    return runner(command, REPO_ROOT, env)


def memory_search(args: argparse.Namespace) -> int:
    result = search_memory(Path(args.root), args.query, args.list_topics)
    if args.as_json:
        print(json.dumps(result, indent=2))
    elif isinstance(result, dict):
        print(json.dumps(result, indent=2))
    else:
        for row in result:
            print(" | ".join(str(row.get(key, "")) for key in row))
    return 0


def validate_commit_message(args: argparse.Namespace) -> int:
    root = Path(args.root)
    message = Path(args.message_file).read_text(encoding="utf-8")
    pattern = read_ticket_pattern(root)
    allowed = re.compile(rf"^(\[SDD\] .+|{pattern}: .+|openspec/[a-z0-9][a-z0-9-]*: .+)", re.MULTILINE)
    if allowed.search(message):
        return 0
    print(
        f"Commit message must start with a ticket matching '{pattern}', OpenSpec id, or [SDD] for direct SDD repo maintenance, for example: E2EPROJECT-1: scaffold blank site",
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
        "Audit": configure_audit,
        "AuditQualityGates": configure_audit_quality_gates,
        "ValidateGiteaActionsRunner": configure_validate_runner,
        "InitProjectProfile": configure_init_project_profile,
        "InitQualityGateTemplates": configure_init_quality_templates,
        "SetQualityConfig": configure_set_quality_config,
        "AuditRecommendedTools": configure_audit_recommended_tools,
        "DiscoverProjectGuidance": configure_discover_project_guidance,
        "MapProjectGuidanceStep": configure_map_project_guidance_step,
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


def configure_audit(root: Path, values: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    required = [
        "README.md",
        ".codex/project-profile.json",
        ".codex/delivery-policy.json",
        ".codex/skills/_shared/delivery-contract.md",
        "docs/context-management.md",
        "infra/compose.yml",
        "lefthook.yml",
        "tools/sdd_cli/cli.py",
    ]
    missing = [path for path in required if not (root / path).exists()]
    return {"mode": "Audit", "valid": not missing, "missing": missing, "runtime": "python"}


def configure_audit_quality_gates(root: Path, values: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    profile = read_json(root / ".codex" / "project-profile.json")
    gates = nested(profile, "quality", "gates") or []
    required = [gate.get("id") for gate in gates if gate.get("required")]
    missing = [name for name in ("restore", "format", "build", "tests", "coverage") if name not in required]
    return {"mode": "AuditQualityGates", "valid": not missing, "requiredGates": required, "missingRequiredDefaults": missing}


def configure_validate_runner(root: Path, values: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    checks = {
        "workflowDirectory": (root / ".gitea" / "workflows").exists(),
        "runnerExample": (root / "infra" / "gitea" / "runner.env.example").exists(),
        "lefthook": (root / "lefthook.yml").exists(),
    }
    return {"mode": "ValidateGiteaActionsRunner", "valid": all(checks.values()), "checks": checks}


def configure_init_project_profile(root: Path, values: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    path = root / ".codex" / "project-profile.json"
    if path.exists():
        return {"mode": "InitProjectProfile", "valid": True, "changed": False, "path": str(path)}
    profile = {
        "$schema": "./project-profile.schema.json",
        "schemaVersion": 1,
        "stack": {"languages": [], "frameworks": [], "testFrameworks": []},
        "providers": {},
        "workflow": {"ticketKeyPattern": "E2EPROJECT-[0-9]+", "baseBranch": "dev", "branchPrefix": "codex"},
        "quality": {"coverageMinimumPercent": 80, "gates": []},
    }
    if not dry_run:
        write_json(path, profile)
    return {"mode": "InitProjectProfile", "valid": True, "changed": True, "path": str(path), "dryRun": dry_run}


def configure_init_quality_templates(root: Path, values: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    path = root / ".codex" / "quality.example.json"
    data = {"coverage": {"minimumPercent": 80}, "format": {"verifyNoChanges": True}}
    changed = not path.exists()
    if changed and not dry_run:
        write_json(path, data)
    return {"mode": "InitQualityGateTemplates", "valid": True, "changed": changed, "path": str(path), "dryRun": dry_run}


def configure_set_quality_config(root: Path, values: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    path = root / ".codex" / "quality.local.json"
    if not values:
        return {"mode": "SetQualityConfig", "valid": False, "errors": ["--values-json is required."]}
    if not dry_run:
        write_json(path, values)
    return {"mode": "SetQualityConfig", "valid": True, "changed": True, "path": str(path), "dryRun": dry_run}


def configure_audit_recommended_tools(root: Path, values: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    catalog = root / ".codex" / "tool-recommendations.example.json"
    return {"mode": "AuditRecommendedTools", "valid": catalog.exists(), "catalog": str(catalog), "runtime": "python"}


def configure_discover_project_guidance(root: Path, values: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    signals = []
    if (root / "global.json").exists():
        signals.append("dotnet-example")
    if (root / "tests" / "SDDTemplate.E2ETests" / "package.json").exists():
        signals.append("playwright-example")
    if (root / "infra" / "compose.yml").exists():
        signals.append("docker-compose")
    return {"mode": "DiscoverProjectGuidance", "valid": True, "signals": signals, "recommendations": []}


def configure_map_project_guidance_step(root: Path, values: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    if not values.get("workflowStep"):
        return {"mode": "MapProjectGuidanceStep", "valid": False, "errors": ["values.workflowStep is required."]}
    path = root / ".codex" / "tool-recommendations.local.json"
    current = read_json(path, optional=True)
    mappings = current.setdefault("stepMappings", [])
    mappings.append(values)
    if not dry_run:
        write_json(path, current)
    return {"mode": "MapProjectGuidanceStep", "valid": True, "changed": True, "path": str(path), "dryRun": dry_run}


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
        commit = require(options, "commit-sha")
        return {
            "canonicalPath": f"app/{commit}/",
            "deployableAppsPath": f"app/{commit}/deployable-apps.json",
            "releaseManifestPath": f"app/{commit}/release.json",
            "commitShaPath": f"app/{commit}/commit.sha",
        }
    if mode == "CheckGitIgnored":
        return {"ignored": check_git_ignored(Path(options.get("root", REPO_ROOT)), require(options, "path"))}
    if mode == "NextRcVersion":
        return next_rc_version(options.get("tags", ""))
    if mode == "ValidateTicketLock":
        return validate_ticket_lock(Path(options.get("path", Path(REPO_ROOT) / ".codex" / "delivery-context.local.json")), options)
    if mode == "ValidateDeploymentLane":
        return validate_deployment_lane(Path(options.get("path", Path(REPO_ROOT) / ".codex" / "parallel-delivery.local.json")), options)
    if mode == "ValidateParallelDeliveryDryRun":
        return {"valid": True, "errors": []}
    if mode == "InitializeWorkflowTelemetry":
        return initialize_workflow_telemetry(Path(options.get("repo-root", REPO_ROOT)), require(options, "ticket-key"))
    if mode == "AppendWorkflowTelemetry":
        return append_workflow_telemetry(Path(options.get("repo-root", REPO_ROOT)), require(options, "ticket-key"), require(options, "input-json"))
    if mode == "ReadWorkflowTelemetry":
        return read_workflow_telemetry(Path(options.get("repo-root", REPO_ROOT)), require(options, "ticket-key"), options.get("input-json", "{}"))
    if mode == "RenderTicketComment":
        return render_ticket_comment(require(options, "type"), require(options, "input-json"))
    if mode == "UpdateReleaseManifest":
        update_release_manifest(Path(require(options, "path")), require(options, "input-json"))
        return None
    if mode == "AuditSkillContracts":
        result = audit_skill_contracts(Path(options.get("root", REPO_ROOT)), include_configure=options.get("include-configure", "false").lower() == "true")
        if result["findings"]:
            return result
        return result
    if mode == "ClassifyTicketReadiness":
        return asdict(classify_ticket_readiness(options.get("title", ""), options.get("description", "")))
    if mode == "ClassifyDeliveryRisk":
        paths = split_list(options.get("paths", ""))
        return asdict(classify_delivery_risk(paths, options.get("context", ""), int(options.get("changed-lines", "0"))))
    fail(f"Unsupported delivery mode: {mode}")


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
            entries.append({
                "file": path.relative_to(root).as_posix(),
                "title": match.group(1).strip(),
                "type": find_meta(body, "Type"),
                "status": find_meta(body, "Status"),
                "source": find_meta(body, "Source"),
                "lastVerified": find_meta(body, "Last verified"),
                "excerpt": plain[:240] + ("..." if len(plain) > 240 else ""),
            })
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
    profile = root / ".codex" / "project-profile.json"
    if profile.exists():
        return read_ticket_pattern_from_profile(profile)
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
    data = {
        "schemaVersion": 1,
        "version": require(options, "version"),
        "artifactCommitSha": commit,
        "canonicalPath": f"app/{commit}/",
        "releaseManifestPath": f"app/{commit}/release.json",
        "ticketKey": ticket,
        "includedTickets": tickets,
        "createdAtUtc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(output, data)


def check_git_ignored(root: Path, path: str) -> bool:
    completed = subprocess.run(["git", "check-ignore", path], cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    return completed.returncode == 0


def next_rc_version(tags_text: str) -> str:
    max_seen = 0
    for tag in split_list(tags_text.replace(" ", "\n")):
        match = re.match(r"^v(\d+)\.(\d+)\.(\d+)-rc\.(\d+)$", tag)
        if match:
            max_seen = max(max_seen, int(match.group(4)))
    return f"v0.1.0-rc.{max_seen + 1}"


def validate_ticket_lock(path: Path, options: dict[str, str]) -> dict[str, Any]:
    if not path.exists():
        return {"valid": False, "errors": [f"Ticket lock not found: {path}"]}
    data = read_json(path)
    errors = []
    for option, field in (("ticket-key", "ticketKey"), ("branch", "branch"), ("commit-sha", "commitSha")):
        expected = options.get(option)
        if expected and data.get(field) and data.get(field) != expected:
            errors.append(f"{field} mismatch: expected {expected}, found {data.get(field)}")
    return {"valid": not errors, "errors": errors}


def validate_deployment_lane(path: Path, options: dict[str, str]) -> dict[str, Any]:
    if not path.exists():
        return {"valid": True, "errors": []}
    data = read_json(path)
    lane = options.get("lane") or options.get("environment")
    ticket = options.get("ticket-key")
    if not lane or not ticket:
        return {"valid": True, "errors": []}
    owner = nested(data, "lanes", lane, "ticketKey")
    errors = [] if not owner or owner == ticket else [f"Deployment lane {lane} is owned by {owner}, not {ticket}."]
    return {"valid": not errors, "errors": errors}


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


def collapse_stages(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        stage = row.get("workflowStage", "unknown")
        current = grouped.setdefault(stage, {"stage": stage, "retryCount": 0, "elapsedMilliseconds": 0})
        current["outcome"] = row.get("outcome", current.get("outcome", ""))
        current["startedUtc"] = min_text(current.get("startedUtc"), row.get("startedUtc"))
        current["finishedUtc"] = max_text(current.get("finishedUtc"), row.get("finishedUtc"))
        current["retryCount"] += int(row.get("retryCount", 0) or 0)
        current["elapsedMilliseconds"] += int(row.get("elapsedMilliseconds", 0) or 0)
    return [grouped[key] for key in sorted(grouped)]


def render_ticket_comment(comment_type: str, input_json: str) -> str:
    data = json.loads(input_json)
    if comment_type == "WorkflowTiming":
        lines = [
            f"IA generated workflow timing: {data.get('ticketKey', '')}",
            "",
            f"**Status:** {data.get('status', '')}",
            f"**Current route:** `{data.get('currentRoute', '')}`",
            f"**Total elapsed:** {format_duration(int(data.get('totalElapsedMilliseconds', 0) or 0))}",
            "",
            "| Stage | Outcome | Duration | Started UTC | Finished UTC |",
            "| --- | --- | --- | --- | --- |",
        ]
        known = {stage["stage"]: stage for stage in data.get("stages", [])}
        for name in standard_stages():
            stage = known.get(name)
            if stage:
                lines.append(f"| `{name}` | {stage.get('outcome', '')} | {format_duration(stage.get('elapsedMilliseconds', 0))} | {stage.get('startedUtc', '-')} | {stage.get('finishedUtc', '-')} |")
            else:
                lines.append(f"| `{name}` | NOT RUN / N/A | no time | - | - |")
        return "\n".join(lines)
    marker = {
        "QADeployment": "IA generated QA deployment",
        "E2EQA": "IA generated E2E QA",
        "ProdDeployment": "IA generated PROD deployment",
    }.get(comment_type, f"IA generated {comment_type}")
    return f"{marker}: {data.get('ticketKey', data.get('finalReleaseVersion', 'unknown'))}\n\n**Status:** {data.get('status', '')}"


def update_release_manifest(path: Path, input_json: str) -> None:
    data = read_json(path, optional=True)
    data.update(json.loads(input_json))
    write_json(path, data)


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


def standard_stages() -> list[str]:
    return [
        "dev-flow-start-ticket",
        "dev-flow-implement-ticket",
        "dev-flow-pr-review-agent",
        "dev-ops-post-merge-deploy",
        "dev-ops-deploy-qa",
        "quality-test-e2e",
    ]


def format_duration(milliseconds: int) -> str:
    if milliseconds <= 0:
        return "no time"
    seconds = milliseconds // 1000
    minutes, second = divmod(seconds, 60)
    hours, minute = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minute}m {second}s"
    if minutes:
        return f"{minutes}m {second}s"
    return f"{second}s"


def audit_skill_contracts(root: Path, include_configure: bool = False) -> dict[str, Any]:
    skills_root = root / ".codex" / "skills"
    findings: list[dict[str, str]] = []
    required = (".codex/skills/_shared/delivery-contract.md", "docs/context-management.md", "validation")
    if not skills_root.exists():
        return {"valid": False, "findings": [{"path": str(skills_root), "message": "skills root missing"}]}
    for skill in sorted(skills_root.glob("*/SKILL.md")):
        name = skill.parent.name
        if name in {"_shared", "caveman"}:
            continue
        if name.startswith("configure-") and not include_configure:
            continue
        text = skill.read_text(encoding="utf-8")
        if name.startswith(("dev-flow-", "dev-ops-", "quality-test-")):
            for term in required:
                if term not in text:
                    findings.append({"path": skill.relative_to(root).as_posix(), "message": f"missing {term}"})
    return {"valid": not findings, "findings": findings}


@dataclass
class TicketReadinessResult:
    status: str
    missing: list[str]


def classify_ticket_readiness(title: str, description: str) -> TicketReadinessResult:
    text = normalize(f"{title}\n{description}")
    missing: list[str] = []
    if not text or len(text) < 30:
        return TicketReadinessResult("blocked", ["user-visible goal", "acceptance criteria", "validation expectation"])
    if not has_any(text, "as a ", "i want", "needs", "should", "must", "add ", "create ", "fix ", "update ", "implement ", "allow ", "prevent "):
        missing.append("user-visible goal")
    if not has_any(text, "acceptance criteria", "given ", "when ", "then ", "- [ ]", "- ", "shall", "must", "should"):
        missing.append("acceptance criteria")
    if not has_any(text, "test", "validate", "verify", "qa", "e2e", "coverage", "health", "curl", "playwright"):
        missing.append("validation expectation")
    if "user-visible goal" in missing or len(missing) >= 3:
        return TicketReadinessResult("blocked", missing)
    return TicketReadinessResult("ready" if not missing else "refinable", missing)


@dataclass
class DeliveryRiskResult:
    level: str
    reasons: list[str]


def classify_delivery_risk(paths: Iterable[str], context: str, changed_lines: int) -> DeliveryRiskResult:
    normalized_paths = [path.replace("\\", "/") for path in paths]
    combined = normalize("\n".join(normalized_paths) + "\n" + context)
    reasons = []
    for term in ("auth", "authorization", "authentication", "secret", "token", "password", "migration", "deployment", "rollback", "hotfix", "public api", "/health", "release.json", "nexus", "azure", "gitea/workflows", "infra/deployment", "infra/azure", "appsettings", "program.cs", ".csproj"):
        if term in combined:
            reasons.append(f"high-risk surface: {term}")
    if changed_lines >= 500:
        reasons.append("large diff >= 500 changed lines")
    if reasons:
        return DeliveryRiskResult("high", reasons)
    non_docs = [path for path in normalized_paths if not (path.startswith("docs/") or path.lower().endswith((".md", ".txt")))]
    if changed_lines > 80 or len(non_docs) > 1:
        return DeliveryRiskResult("standard", ["normal implementation or multi-file review surface"])
    return DeliveryRiskResult("low", ["localized low-risk change"])


def parse_pairs(args: list[str]) -> dict[str, str]:
    args = trim_remainder(args)
    pairs: dict[str, str] = {}
    index = 0
    while index < len(args):
        key = args[index]
        if not key.startswith("--") or index + 1 >= len(args):
            fail(f"Expected --name value, got '{key}'.")
        pairs[key[2:]] = args[index + 1]
        index += 2
    return pairs


def trim_remainder(values: list[str]) -> list[str]:
    return values[1:] if values and values[0] == "--" else values


def read_json(path: Path, optional: bool = False) -> dict[str, Any]:
    if optional and not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def nested(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def find_meta(body: str, key: str) -> str:
    match = re.search(rf"(?m)^-\s+{re.escape(key)}:\s*(.+)$", body)
    return match.group(1).strip() if match else ""


def require(options: dict[str, str], key: str) -> str:
    value = options.get(key)
    if not value:
        fail(f"--{key} is required.")
    return value


def fail(message: str) -> Any:
    raise CliError(message)


def split_list(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,;\n]", value) if item.strip()]


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def has_any(value: str, *needles: str) -> bool:
    return any(needle in value for needle in needles)


def sh_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"
