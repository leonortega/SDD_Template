"""Environment lab: Docker Compose, env files, project profile, observability."""

from __future__ import annotations

import http.client
import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ._shared import (
    REPO_ROOT,
    add_bucket_item,
    configure_result,
    configure_set_env_mode,
    copy_seed_file,
    ensure_seed_file,
    env_template_values,
    http_status,
    local_path,
    nested,
    normalize_stack_domain,
    read_env_file,
    read_json,
    run_native,
    write_env_file,
    write_json,
)


# ── Setup Lab (all-in-one idempotent) ───────────────────────────────────

def setup_lab(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Run the full lab setup in order: init, compose up, build images, validate."""
    result = configure_result("SetupLab", dry_run, write_enabled=not dry_run)
    steps: list[dict[str, Any]] = []

    # Helper to append a step and optionally return early on failure
    def _add_step(step_result: dict[str, Any], *, fatal: bool = True) -> dict[str, Any] | None:
        steps.append(step_result)
        if fatal and not dry_run and not step_result.get("valid", True):
            result["steps"] = steps
            result["valid"] = False
            return result
        return None

    # 1. Init local files
    early = _add_step(init_local_files(root, dry_run))
    if early:
        return early

    # 2. Init project profile
    _add_step(init_project_profile(root, dry_run), fatal=False)

    # 3. Init quality templates
    _add_step(init_quality_templates(root, dry_run), fatal=False)

    # 4. Build Gitea Actions images
    early = _add_step(build_gitea_actions_images(root, dry_run))
    if early:
        return early

    # 5. Start compose services
    if not dry_run:
        early = _add_step(compose_up())
        if early:
            return early
    else:
        steps.append({"command": "compose-up", "valid": True, "dryRun": True,
                      "message": "Skipped compose-up in dry-run mode."})

    # 6. Set Gitea branch protection is skipped (requires configured API token — run separately)

    # 7. Validate observability
    _add_step(validate_observability(root, dry_run), fatal=False)

    # 8. Validate Gitea runner
    _add_step(validate_gitea_runner(root, dry_run), fatal=False)

    result["steps"] = steps
    all_valid = all(s.get("valid", True) for s in steps)
    result["valid"] = all_valid
    return result


# ── Docker Compose ───────────────────────────────────────────────────────

def compose_up() -> dict[str, Any]:
    """Start Docker Compose services."""
    return _compose("up")


def compose_down() -> dict[str, Any]:
    """Stop Docker Compose services."""
    return _compose("down")


def _compose(action: str) -> dict[str, Any]:
    infra = REPO_ROOT / "infra"
    command = [
        "docker",
        "compose",
        "--env-file", str(infra / "openproject" / "variables.env"),
        "--env-file", str(infra / "monitoring" / "variables.env"),
        "-f", str(infra / "compose.yml"),
        "--project-directory", str(infra),
    ]
    command += ["up", "-d", "--remove-orphans"] if action == "up" else ["down"]
    result = subprocess.run(command, cwd=REPO_ROOT, check=False)
    return {
        "command": f"compose-{action}",
        "valid": result.returncode == 0,
        "returncode": result.returncode,
    }


# ── Init local files ─────────────────────────────────────────────────────

def init_local_files(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Create local seed files from templates."""
    result = configure_result("InitLocalFiles", dry_run, write_enabled=not dry_run)
    copy_seed_file(root, ".codex/client-tools.example.json", ".codex/client-tools.local.json", result, dry_run)
    copy_seed_file(root, ".codex/quality.example.json", ".codex/quality.local.json", result, dry_run)
    for relative in (
        "infra/openproject/variables.env",
        "infra/monitoring/variables.env",
        "infra/gitea/runner.env",
    ):
        copy_seed_file(root, relative + ".example", relative, result, dry_run)
    ensure_seed_file(root, ".codex/memory/memory_summary.md",
                     "# Memory Summary\n\nNo consumer project memories recorded yet.\n", result, dry_run)
    ensure_seed_file(root, ".codex/memory/MEMORY.md",
                     "# Repository Memory Index\n\n- `memory_summary.md`: compact startup context.\n"
                     "- `retrieval-policy.md`: memory read/write rules.\n", result, dry_run)
    ensure_seed_file(root, ".codex/memory/retrieval-policy.md",
                     "# Memory Retrieval And Write Policy\n\nUse memory as guidance only. "
                     "Verify against current files and live tools before acting.\n", result, dry_run)
    result["valid"] = not any(item.get("severity") == "error" for item in result["findings"])
    return result


# ── Init project profile ─────────────────────────────────────────────────

def init_project_profile(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Create project profile schema, example, and local overlay."""
    codex = root / ".codex"
    providers = codex / "providers"
    codex.mkdir(parents=True, exist_ok=True)
    providers.mkdir(parents=True, exist_ok=True)
    schema_path = codex / "project-profile.schema.json"
    profile_path = codex / "project-profile.example.json"
    local_profile_path = codex / "project-profile.local.json"
    changed = False
    actions: list[dict[str, str]] = []

    if not schema_path.exists():
        changed = True
        if not dry_run:
            write_json(schema_path, {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
            })
        actions.append({"path": ".codex/project-profile.schema.json", "key": "created",
                        "severity": "info", "message": "Created .codex/project-profile.schema.json.", "phase": "apply"})
    else:
        actions.append({"path": ".codex/project-profile.schema.json", "key": "exists",
                        "severity": "info", "message": "Template already exists: .codex/project-profile.schema.json", "phase": "apply"})

    if not profile_path.exists():
        changed = True
        profile = {
            "$schema": "./project-profile.schema.json",
            "schemaVersion": 1,
            "stack": {
                "frontend": {"applies": False, "value": ""},
                "backend": {"applies": False, "value": ""},
                "database": {"applies": False, "value": ""},
                "languages": [],
                "frameworks": [],
                "testFrameworks": [],
            },
            "providers": {
                "ticket": {"id": "openproject", "adapter": ".codex/providers/ticket.openproject.md"},
                "repository": {"id": "gitea", "adapter": ".codex/providers/repo.gitea.md"},
                "review": {"id": "gitea", "adapter": ".codex/providers/repo.gitea.md"},
                "artifact": {"id": "nexus", "adapter": ".codex/providers/artifact.nexus.md"},
                "deployment": {"id": "docker-desktop", "adapter": ".codex/providers/deploy.example.md"},
            },
            "workflow": {"ticketKeyPattern": "TICKET-[0-9]+", "baseBranch": "dev", "branchPrefix": "codex"},
            "quality": {"coverageMinimumPercent": 80, "gates": []},
            "adapters": {
                "ticket": ".codex/providers/ticket.openproject.md",
                "repository": ".codex/providers/repo.gitea.md",
                "review": ".codex/providers/repo.gitea.md",
                "artifact": ".codex/providers/artifact.nexus.md",
                "deployment": ".codex/providers/deploy.example.md",
            },
        }
        if not dry_run:
            write_json(profile_path, profile)
        actions.append({"path": ".codex/project-profile.example.json", "key": "created",
                        "severity": "info", "message": "Created .codex/project-profile.example.json.", "phase": "apply"})
    else:
        actions.append({"path": ".codex/project-profile.example.json", "key": "exists",
                        "severity": "info", "message": "Template already exists: .codex/project-profile.example.json", "phase": "apply"})

    if not local_profile_path.exists():
        changed = True
        local_profile = {
            "$schema": "./project-profile.schema.json",
            "stack": {
                "frontend": {"applies": False, "value": ""},
                "backend": {"applies": False, "value": ""},
                "database": {"applies": False, "value": ""},
                "languages": [],
                "frameworks": [],
                "testFrameworks": [],
            },
            "adapters": {},
        }
        if not dry_run:
            write_json(local_profile_path, local_profile)
        actions.append({"path": ".codex/project-profile.local.json", "key": "created",
                        "severity": "info", "message": "Created ignored stack/profile overlay.", "phase": "apply"})
    else:
        actions.append({"path": ".codex/project-profile.local.json", "key": "exists",
                        "severity": "info", "message": "Template already exists: .codex/project-profile.local.json", "phase": "apply"})

    for name in ("ticket.example.md", "repo.example.md", "artifact.example.md", "deploy.example.md"):
        example = providers / name
        if not example.exists():
            changed = True
            if not dry_run:
                example.write_text(f"# {name}\n\nprovider-neutral scaffold\n", encoding="utf-8")

    return {"mode": "InitProjectProfile", "valid": True, "changed": changed,
            "path": ".codex/project-profile.example.json", "dryRun": dry_run, "actions": actions}


# ── Init quality templates ───────────────────────────────────────────────

def init_quality_templates(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Create delivery-policy.json from the SDD template."""
    path = root / ".codex" / "delivery-policy.json"
    data = read_json(REPO_ROOT / ".codex" / "delivery-policy.json")
    changed = not path.exists()
    if not dry_run:
        write_json(path, data)
    return {"mode": "InitQualityGateTemplates", "valid": True, "changed": changed,
            "path": ".codex/delivery-policy.json", "dryRun": dry_run}


# ── Set env files ────────────────────────────────────────────────────────

def set_openproject_env(root: Path, values: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    """Set OpenProject env variables."""
    return configure_set_env_mode(root, "SetOpenProjectEnv", "infra/openproject/variables.env", values, dry_run)


def set_monitoring_env(root: Path, values: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    """Set monitoring env variables."""
    return configure_set_env_mode(root, "SetMonitoringEnv", "infra/monitoring/variables.env", values, dry_run)


def set_gitea_runner_env(root: Path, values: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    """Set Gitea runner env variables."""
    return configure_set_env_mode(root, "SetGiteaRunner", "infra/gitea/runner.env", values, dry_run)


# ── Split infra env ──────────────────────────────────────────────────────

def split_infra_env(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Split combined env vars into per-service env files."""
    result = configure_result("SplitInfraEnv", dry_run, write_enabled=not dry_run)
    source = read_env_file(root / "infra" / "openproject" / "variables.env")
    if not source:
        return {"mode": "SplitInfraEnv", "valid": False,
                "errors": ["Missing infra/openproject/variables.env. Run InitLocalFiles first."]}
    for relative in ("infra/monitoring/variables.env", "infra/openproject/variables.env"):
        current = read_env_file(local_path(root, relative))
        template = env_template_values(root, relative)
        if not template:
            add_bucket_item(result["findings"], relative + ".example", "missing.template",
                            f"Missing template: {relative}.example", "error", "pre-start")
            continue
        stale_count = len(set(current) - set(template))
        merged = {key: current.get(key, source.get(key, default)) for key, default in template.items()}
        if not dry_run:
            write_env_file(local_path(root, relative), merged)
        message = "Wrote values from split env template, preserving current values first."
        if stale_count:
            message += f" Pruned {stale_count} stale non-template key(s)."
        result["actions"].append({"path": relative, "key": "split-env", "severity": "info",
                                  "message": message, "phase": "apply"})
    result["valid"] = not any(item.get("severity") == "error" for item in result["findings"])
    return result


# ── Build Gitea Actions images ───────────────────────────────────────────

def build_gitea_actions_images(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Build Gitea Actions runner Docker images."""
    result = configure_result("BuildGiteaActionsImages", dry_run, write_enabled=not dry_run)
    if dry_run:
        result["actions"].append({"path": "docker", "key": "build.gitea-images", "severity": "info",
                                  "message": "Would build Gitea Actions runner images.", "phase": "apply"})
        result["valid"] = True
        return result
    docker = run_native(["docker", "version"], root, timeout=30)
    if docker["returncode"] != 0:
        add_bucket_item(result["findings"], "docker", "", f"Docker CLI is not usable: {docker['stderr']}", "error", "pre-start")
        result["valid"] = False
        return result
    dockerfiles = sorted((root / "infra" / "gitea" / "actions-images").glob("*/Dockerfile"))
    if not dockerfiles:
        add_bucket_item(result["findings"], "infra/gitea/actions-images", "dockerfiles",
                        "No Gitea Actions image Dockerfiles found.", "warning", "pre-start")
    for dockerfile in dockerfiles:
        image = f"sdd-{dockerfile.parent.name}:local"
        command = ["docker", "build", "--pull", "-t", image, "-f", str(dockerfile), str(dockerfile.parent)]
        if dry_run:
            result["actions"].append({"path": dockerfile.relative_to(root).as_posix(), "key": "docker build",
                                      "severity": "info", "message": f"Would build {image}.", "phase": "apply"})
            continue
        built = run_native(command, root, timeout=600)
        if built["returncode"] == 0:
            result["actions"].append({"path": dockerfile.relative_to(root).as_posix(), "key": "docker build",
                                      "severity": "info", "message": f"Built {image}.", "phase": "apply"})
        else:
            add_bucket_item(result["findings"], dockerfile.relative_to(root).as_posix(), "docker build",
                            f"Could not build {image}: {built['stderr']}", "error", "apply")
    result["valid"] = not any(item.get("severity") == "error" for item in result["findings"])
    return result


# ── Set Gitea branch protection ──────────────────────────────────────────

def set_gitea_branch_protection(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Configure Gitea branch protection via API."""
    result = configure_result("SetGiteaBranchProtection", dry_run, write_enabled=not dry_run)
    client = read_json(root / ".codex" / "client-tools.local.json", optional=True)
    gitea = client.get("gitea", {})
    token = gitea.get("apiToken", "")
    base_url = str(gitea.get("baseUrl", "")).rstrip("/")
    owner = gitea.get("owner")
    repo = gitea.get("repo")
    if not base_url or not token or not owner or not repo or "replace-with" in token:
        return {"mode": "SetGiteaBranchProtection", "valid": False,
                "errors": ["Gitea baseUrl, owner, repo, and apiToken are required in .codex/client-tools.local.json."]}
    approvals = nested(client, "pr", "minimumApprovals") or {"dev": 1, "main": 1}
    for branch in ("dev", "main"):
        expected = int(approvals.get(branch, 1))
        path = f"/api/v1/repos/{owner}/{repo}/branch_protections/{branch}"
        parsed = urlparse(base_url)
        if dry_run:
            result["actions"].append({"path": ".gitea/workflows/README.md", "key": f"branch-protection.{branch}",
                                      "severity": "info", "message": f"Would set required_approvals={expected}.", "phase": "apply"})
            continue
        try:
            body = json.dumps({"required_approvals": expected})
            conn_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
            conn = conn_cls(parsed.hostname or "", parsed.port, timeout=10)
            conn.request("PATCH", path, body=body,
                         headers={"Authorization": f"token {token}", "Content-Type": "application/json"})
            response = conn.getresponse()
            response.read()
            conn.close()
            if response.status not in {200, 201, 204}:
                add_bucket_item(result["findings"], ".gitea/workflows/README.md", f"branch-protection.{branch}",
                                f"Gitea returned HTTP {response.status}.", "error", "apply")
            else:
                result["actions"].append({"path": ".gitea/workflows/README.md", "key": f"branch-protection.{branch}",
                                          "severity": "info", "message": f"Set required_approvals={expected}.", "phase": "apply"})
        except Exception as ex:
            add_bucket_item(result["findings"], ".gitea/workflows/README.md", f"branch-protection.{branch}",
                            f"Could not update Gitea branch protection: {ex}", "error", "apply")
    result["valid"] = not any(item.get("severity") == "error" for item in result["findings"])
    return result


# ── Observability ────────────────────────────────────────────────────────

def validate_observability(root: Path, dry_run: bool = False, http_status_fn: Any = None) -> dict[str, Any]:
    """Validate Seq and Grafana endpoints."""
    return _observability_checks(root, dry_run, "ValidateObservability", http_status_fn=http_status_fn)


def _observability_checks(root: Path, dry_run: bool, mode: str, http_status_fn: Any = None) -> dict[str, Any]:
    if http_status_fn is None:
        http_status_fn = http_status
    result = configure_result(mode, dry_run, write_enabled=not dry_run)
    monitoring_path = root / "infra" / "monitoring" / "variables.env"
    if not monitoring_path.exists():
        return {"mode": mode, "valid": False, "errors": ["Missing infra/monitoring/variables.env. Run InitLocalFiles first."]}
    monitoring = read_env_file(monitoring_path)
    seq_url = monitoring.get("SEQ_URL") or "http://localhost:5341"
    if not dry_run:
        status, error = http_status_fn(seq_url.rstrip("/") + "/api")
        if status == 200:
            result["actions"].append({"path": "seq", "key": "endpoint.ready", "severity": "info",
                                      "message": "Seq endpoint is reachable.", "phase": "post-start"})
        else:
            add_bucket_item(result["findings"], "seq", "endpoint.ready",
                            f"Seq endpoint '{seq_url}' is not reachable: {error or status}", "error", "post-start")
    else:
        result["actions"].append({"path": "seq", "key": "endpoint.ready", "severity": "info",
                                  "message": f"Would check Seq endpoint at {seq_url}.", "phase": "audit"})
    for key in ("SEQ_ERROR_ALERT_WINDOW", "SEQ_ERROR_ALERT_THRESHOLD"):
        if monitoring.get(key, "") != "":
            result["actions"].append({"path": "seq", "key": key, "severity": "info",
                                      "message": "Seq error alert setting is configured.", "phase": "audit"})
        else:
            add_bucket_item(result["findings"], "infra/monitoring/variables.env", key,
                            f"{key} is required for the Seq error-log alert.", "warning", "pre-start")
    if not dry_run:
        grafana_status, grafana_error = http_status_fn("http://localhost:3001/api/health")
        if grafana_status in {200, 401}:
            result["actions"].append({"path": "grafana", "key": "health", "severity": "info",
                                      "message": "Grafana health endpoint responded.", "phase": "post-start"})
        else:
            add_bucket_item(result["findings"], "grafana", "health",
                            f"Grafana health endpoint is not reachable: {grafana_error or grafana_status}", "warning", "post-start")
    else:
        result["actions"].append({"path": "grafana", "key": "health", "severity": "info",
                                  "message": "Would check Grafana health endpoint at http://localhost:3001/api/health.", "phase": "audit"})
    datasource_path = root / "infra" / "monitoring" / "grafana" / "provisioning" / "datasources" / "infinity-health.yml"
    if datasource_path.exists():
        result["actions"].append({"path": datasource_path.relative_to(root).as_posix(), "key": "grafana.infinity-health",
                                  "severity": "info", "message": "Grafana Infinity health datasource provisioning exists.", "phase": "audit"})
    else:
        add_bucket_item(result["findings"], "infra/monitoring/grafana/provisioning/datasources/infinity-health.yml",
                        "grafana.infinity-health", "Grafana Infinity health datasource provisioning is missing.", "warning", "pre-start")
    alert_path = root / "infra" / "monitoring" / "grafana" / "provisioning" / "alerting" / "health-alerts.yml"
    if alert_path.exists():
        result["actions"].append({"path": alert_path.relative_to(root).as_posix(), "key": "grafana.health-alerts",
                                  "severity": "info", "message": "Grafana health alert provisioning exists.", "phase": "audit"})
    else:
        add_bucket_item(result["findings"], "infra/monitoring/grafana/provisioning/alerting/health-alerts.yml",
                        "grafana.health-alerts", "Grafana health alert provisioning is missing.", "warning", "pre-start")
    result["valid"] = not any(item.get("severity") == "error" for item in result["findings"])
    return result


# ── Configure modes (set client tools, stack, quality, recommendations) ──

def set_client_tools(root: Path, values: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    """Set client-tools.local.json values."""
    path = root / ".codex" / "client-tools.local.json"
    current = read_json(path, optional=True)
    from ._shared import merge_dicts
    merged = merge_dicts(current, values)
    if not dry_run:
        write_json(path, merged)
    return {"mode": "SetClientTools", "valid": True, "changed": True,
            "path": str(path), "dryRun": dry_run}


def set_project_stack(root: Path, values: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    """Set frontend/backend/database stack choices."""
    if not any(key in values for key in ("frontend", "backend", "database")):
        return {"mode": "SetProjectStack", "valid": False,
                "errors": ["values.frontend, values.backend, or values.database is required."]}
    path = root / ".codex" / "project-profile.local.json"
    current = read_json(path, optional=True)
    stack_raw = current.get("stack")
    stack: dict[str, Any] = stack_raw if isinstance(stack_raw, dict) else {}

    for domain in ("frontend", "backend", "database"):
        if domain in values:
            stack[domain] = normalize_stack_domain(values.get(domain))
    stack.setdefault("languages", [])
    stack.setdefault("frameworks", [])
    stack.setdefault("testFrameworks", [])
    stack["rawInputs"] = {
        domain: nested(stack, domain, "value") or ""
        for domain in ("frontend", "backend", "database")
    }
    if any(normalize_stack_domain(stack["rawInputs"].get(domain))["applies"]
           for domain in ("frontend", "backend", "database")):
        stack["metadataValidationStatus"] = "needs-user-validation"
    else:
        stack["metadataValidationStatus"] = "validated"
    stack["languages"] = sorted(set(stack.get("languages", [])))
    stack["frameworks"] = sorted(set(stack.get("frameworks", [])))
    stack["testFrameworks"] = sorted(set(stack.get("testFrameworks", [])))
    stack["selectionRecorded"] = True
    current["$schema"] = current.get("$schema", "./project-profile.schema.json")
    current["stack"] = stack
    if not dry_run:
        write_json(path, current)
    return {
        "mode": "SetProjectStack", "valid": True, "changed": True,
        "path": ".codex/project-profile.local.json", "dryRun": dry_run,
        "writeEnabled": not dry_run,
        "actions": [{"path": ".codex/project-profile.local.json", "key": "stack", "severity": "info",
                     "message": "Recorded frontend/backend/database stack choices.", "phase": "apply"}],
    }


def set_project_stack_metadata(root: Path, values: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    """Set stack metadata after user validation."""
    metadata = values.get("metadata")
    if not isinstance(metadata, dict):
        return {"mode": "SetProjectStackMetadata", "valid": False,
                "errors": ["values.metadata object is required."]}
    status = str(values.get("metadataValidationStatus", "needs-user-validation"))
    if status not in {"needs-user-validation", "validated"}:
        return {"mode": "SetProjectStackMetadata", "valid": False,
                "errors": ["metadataValidationStatus must be needs-user-validation or validated."]}
    path = root / ".codex" / "project-profile.local.json"
    current = read_json(path, optional=True)
    stack_raw = current.get("stack")
    stack: dict[str, Any] = stack_raw if isinstance(stack_raw, dict) else {}
    stack["metadata"] = metadata
    stack["metadataValidationStatus"] = status
    current["$schema"] = current.get("$schema", "./project-profile.schema.json")
    current["stack"] = stack
    if not dry_run:
        write_json(path, current)
    return {
        "mode": "SetProjectStackMetadata", "valid": True, "changed": True,
        "path": ".codex/project-profile.local.json", "dryRun": dry_run,
        "writeEnabled": not dry_run,
        "actions": [{"path": ".codex/project-profile.local.json", "key": "stack.metadata", "severity": "info",
                     "message": "Recorded project stack metadata for user validation.", "phase": "apply"}],
    }


def set_quality_config(root: Path, values: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    """Set quality configuration."""
    path = root / ".codex" / "quality.local.json"
    if not values:
        return {"mode": "SetQualityConfig", "valid": False,
                "errors": ["Config values are required. Use --values-json-file, --values-json-stdin true, or --values-json."]}
    valid_quality_keys = {"coverageMinimumPercent", "minimumPercent", "coverage", "SetQualityConfig", "quality"}
    forbidden_patterns = {
        "SetProjectStack", "SetOpenProjectEnv", "SetMonitoringEnv",
        "SetGiteaRunner", "SetRecommendedTools", "MapProjectGuidanceStep",
    }
    filtered_values = {}
    invalid_keys = []
    for key, value in values.items():
        if any(pattern in key for pattern in forbidden_patterns):
            invalid_keys.append(key)
        elif any(valid_key in key for valid_key in valid_quality_keys):
            filtered_values[key] = value
        elif isinstance(value, dict):
            nested_invalid = []
            nested_filtered = {}
            for nested_key, nested_value in value.items():
                if any(pattern in nested_key for pattern in forbidden_patterns):
                    nested_invalid.append(f"{key}.{nested_key}")
                elif any(valid_key in nested_key for valid_key in valid_quality_keys):
                    nested_filtered[nested_key] = nested_value
            if nested_invalid:
                invalid_keys.extend(nested_invalid)
            if nested_filtered:
                filtered_values[key] = nested_filtered
    if invalid_keys:
        return {"mode": "SetQualityConfig", "valid": False,
                "errors": [f"Invalid configuration keys for quality config: {', '.join(invalid_keys)}. "
                           "Use separate commands for different configuration domains."]}
    if not filtered_values:
        return {"mode": "SetQualityConfig", "valid": False,
                "errors": ["No valid quality configuration keys found."]}
    if not dry_run:
        write_json(path, filtered_values)
    return {"mode": "SetQualityConfig", "valid": True, "changed": True,
            "path": str(path), "dryRun": dry_run}


def set_recommended_tools(root: Path, values: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    """Set accepted/dismissed tool recommendations."""
    result = configure_result("SetRecommendedTools", dry_run, write_enabled=not dry_run)
    path = root / ".codex" / "client-tools.local.json"
    if not path.exists():
        return {"mode": "SetRecommendedTools", "valid": False,
                "errors": ["Missing .codex/client-tools.local.json. Run InitLocalFiles first."]}
    if "accepted" not in values and "dismissed" not in values:
        return {"mode": "SetRecommendedTools", "valid": False,
                "errors": ["values.accepted or values.dismissed is required."]}
    config = read_json(path, optional=True)
    recommended = config.setdefault("recommendedTools", {})
    for key in ("accepted", "dismissed"):
        existing = list(recommended.get(key, []))
        for item in values.get(key, []):
            if item not in existing:
                existing.append(item)
        recommended[key] = existing
        if values.get(key):
            result["actions"].append({"path": ".codex/client-tools.local.json", "key": f"recommendedTools.{key}",
                                      "severity": "info", "message": f"Recorded {key} recommendation ids.", "phase": "apply"})
    if not dry_run:
        write_json(path, config)
    result["valid"] = True
    return result


# ── Validate Gitea Actions runner ───────────────────────────────────────

def validate_gitea_runner(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Validate Gitea Actions runner prerequisites: Docker, images, tools."""
    result = configure_result("ValidateGiteaActionsRunner", dry_run, write_enabled=not dry_run)
    if dry_run:
        result["actions"].append({"path": "docker", "key": "validate.gitea-runner", "severity": "info",
                                  "message": "Would validate Gitea Actions runner prerequisites.", "phase": "audit"})
        result["valid"] = True
        return result
    # Check Docker
    docker = run_native(["docker", "version"], root, timeout=30)
    if docker["returncode"] != 0:
        add_bucket_item(result["findings"], "docker", "", f"Docker CLI is not usable: {docker['stderr']}", "error", "pre-start")
        result["valid"] = False
        return result
    result["actions"].append({"path": "docker", "key": "available", "severity": "info",
                              "message": "Docker CLI is available.", "phase": "audit"})
    # Check local CI images
    dockerfiles = sorted((root / "infra" / "gitea" / "actions-images").glob("*/Dockerfile"))
    found_images = 0
    for dockerfile in dockerfiles:
        image = f"sdd-{dockerfile.parent.name}:local"
        if dry_run:
            result["actions"].append({"path": image, "key": "image.check", "severity": "info",
                                      "message": f"Would check image {image}.", "phase": "audit"})
            found_images += 1
            continue
        inspect = run_native(["docker", "image", "inspect", image], root, timeout=15)
        if inspect["returncode"] == 0:
            result["actions"].append({"path": image, "key": "image.present", "severity": "info",
                                      "message": f"Local image {image} is present.", "phase": "audit"})
            found_images += 1
        else:
            add_bucket_item(result["findings"], image, "image.missing",
                            f"Local image {image} is missing. Run build-gitea-images first.",
                            "error", "pre-start")
    if not dockerfiles:
        add_bucket_item(result["findings"], "infra/gitea/actions-images", "dockerfiles",
                        "No Gitea Actions image Dockerfiles found.", "warning", "pre-start")
    # Check required tools for runner jobs
    required_tools = [("git", ["git", "--version"]),
                      ("node", ["node", "--version"]),
                      ("npm", ["npm", "--version"]),
                      ("sh", ["sh", "-c", "echo ok"])]
    for tool_name, tool_cmd in required_tools:
        if dry_run:
            result["actions"].append({"path": tool_name, "key": "tool.check", "severity": "info",
                                      "message": f"Would check {tool_name}.", "phase": "audit"})
            continue
        check = run_native(tool_cmd, root, timeout=10)
        if check["returncode"] == 0:
            result["actions"].append({"path": tool_name, "key": "tool.available", "severity": "info",
                                      "message": f"{tool_name} is available.", "phase": "audit"})
        else:
            add_bucket_item(result["findings"], tool_name, "tool.missing",
                            f"{tool_name} is not available in PATH.", "warning", "pre-start")
    # Validate Gitea checkout networking (ping gitea host)
    gitea_env = root / "infra" / "gitea" / "runner.env"
    if gitea_env.exists():
        env = read_env_file(gitea_env)
        instance_url = env.get("GITEA_INSTANCE_URL", "")
        if instance_url and not dry_run:
            status, _ = http_status(instance_url.rstrip("/") + "/api/healthz", timeout=5)
            if status is not None and status < 500:
                result["actions"].append({"path": "gitea", "key": "network", "severity": "info",
                                          "message": f"Gitea instance {instance_url} is reachable.", "phase": "audit"})
            else:
                add_bucket_item(result["findings"], "gitea", "network.unreachable",
                                f"Gitea instance {instance_url} is not reachable.", "warning", "post-start")
        elif instance_url:
            result["actions"].append({"path": "gitea", "key": "network", "severity": "info",
                                      "message": f"Would check Gitea instance {instance_url}.", "phase": "audit"})
    result["valid"] = not any(item.get("severity") == "error" for item in result["findings"])
    return result




# ── K8s scaffolding ───────────────────────────────────────────────────────

def scaffold_k8s(root, dry_run=False):
    """Scaffold K8s deployment files: Dockerfile, manifests, overlays."""
    result = configure_result("ScaffoldK8s", dry_run, write_enabled=not dry_run)

    if dry_run:
        result["actions"].append({"path": "infra/k8s", "key": "scaffold.plan", "severity": "info",
                                  "message": (
                                      "Would scaffold K8s deployment files:"
                                      "\n  - Dockerfile per app (nginx for web)"
                                      "\n  - .dockerignore per app"
                                      "\n  - infra/k8s/base/ (namespace, deployment, service, kustomization)"
                                      "\n  - infra/k8s/overlays/{dev,qa,prod}/ (env overlays)"
                                      "\n  - nginx.conf for web apps"
                                  ),
                                  "phase": "apply"})
        result["valid"] = True
        return result

    # Prerequisite: validate Docker Desktop K8s
    k8s_check = validate_docker_desktop_k8s(root)
    if not k8s_check.get("valid", False):
        for f in k8s_check.get("findings", []):
            result["findings"].append(f)
        add_bucket_item(result["findings"], "k8s", "prerequisite",
                        "Docker Desktop K8s validation failed — fix before scaffolding.",
                        "error", "pre-start")
        result["valid"] = False
        return result

    apps_path = root / "infra" / "deployment" / "apps.json"

    if not apps_path.exists():
        add_bucket_item(result["findings"], "infra/deployment/apps.json", "missing",
                        "apps.json not found - cannot scaffold K8s.",
                        "error", "pre-start")
        result["valid"] = False
        return result

    try:
        apps_data = read_json(apps_path, optional=False)
        apps = apps_data.get("apps", [])
    except Exception as ex:
        add_bucket_item(result["findings"], "infra/deployment/apps.json", "read_error",
                        f"Could not parse apps.json: {ex}", "error", "pre-start")
        result["valid"] = False
        return result

    if not apps:
        add_bucket_item(result["findings"], "infra/deployment/apps.json", "no_apps",
                        "apps.json has no apps defined.",
                        "warning", "pre-start")
        result["valid"] = True
        return result

    k8s_base = root / "infra" / "k8s" / "base"
    k8s_base.mkdir(parents=True, exist_ok=True)
    overlays_dir = root / "infra" / "k8s" / "overlays"

    first_app = apps[0]["appId"]
    first_health = apps[0].get("healthPath", "/health")

    # Generate Dockerfile for each web app
    for app in apps:
        app_id = app["appId"]
        proj = app.get("projectPath", app_id)
        role = app.get("role", "web")
        app_dir = root / proj

        if role == "web":
            # .dockerignore
            di = app_dir / ".dockerignore"
            if not di.exists():
                di.write_text("node_modules/\n.git/\n.env\n*.md\n", encoding="utf-8")
                result["actions"].append({
                    "path": f"{proj}/.dockerignore", "key": "file.created",
                    "severity": "info",
                    "message": f"Created .dockerignore for {app_id}.",
                    "phase": "apply"
                })

            # nginx.conf
            nc = app_dir / "nginx.conf"
            if not nc.exists():
                nc.write_text(
                    'server {\n'
                    '    listen 80;\n'
                    '    server_name _;\n'
                    '    root /usr/share/nginx/html;\n'
                    '    index index.html;\n'
                    '    location / {\n'
                    '        try_files $uri $uri/ /index.html;\n'
                    '    }\n'
                    '    location /health {\n'
                    "        return 200 '{\"status\":\"ok\"}';\n"
                    '        add_header Content-Type application/json;\n'
                    '    }\n'
                    '}\n',
                    encoding="utf-8"
                )
                result["actions"].append({
                    "path": f"{proj}/nginx.conf", "key": "file.created",
                    "severity": "info",
                    "message": f"Created nginx.conf for {app_id}.",
                    "phase": "apply"
                })

            # Dockerfile
            df = app_dir / "Dockerfile"
            if not df.exists():
                dlines = [
                    "# Stage 1: Build\n",
                    "FROM node:20-alpine AS builder\n",
                    "WORKDIR /app\n",
                    "COPY package*.json ./\n",
                    "RUN npm ci\n",
                    "COPY . .\n",
                    "RUN npm run build\n",
                    "\n",
                    "# Stage 2: Serve with nginx\n",
                    "FROM nginx:alpine\n",
                    "COPY --from=builder /app/dist /usr/share/nginx/html\n",
                    "COPY nginx.conf /etc/nginx/conf.d/default.conf\n",
                    "EXPOSE 80\n",
                    "HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
",
                    "  CMD wget -qO- http://localhost/health || exit 1\n",
                    'CMD ["nginx", "-g", "daemon off;"]\n',
                ]
                df.write_text("".join(dlines), encoding="utf-8")
                result["actions"].append({
                    "path": f"{proj}/Dockerfile", "key": "file.created",
                    "severity": "info",
                    "message": f"Created Dockerfile for {app_id}.",
                    "phase": "apply"
                })
            else:
                result["actions"].append({
                    "path": f"{proj}/Dockerfile", "key": "file.exists",
                    "severity": "info",
                    "message": f"Dockerfile already exists for {app_id}.",
                    "phase": "audit"
                })

    # Base manifests
    (k8s_base / "namespace.yaml").write_text(
        "apiVersion: v1\nkind: Namespace\nmetadata:\n  name: sdd-${ENV}\n",
        encoding="utf-8"
    )

    d_lines = [
        "apiVersion: apps/v1\n",
        "kind: Deployment\n",
        "metadata:\n",
        f"  name: {first_app}\n",
        "spec:\n",
        "  replicas: 1\n",
        "  selector:\n",
        "    matchLabels:\n",
        f"      app: {first_app}\n",
        "  template:\n",
        "    metadata:\n",
        "      labels:\n",
        f"        app: {first_app}\n",
        "    spec:\n",
        "      containers:\n",
        f"        - name: {first_app}\n",
        f"          image: host.docker.internal:8083/{first_app}\n",
        "          imagePullPolicy: IfNotPresent\n",
        "          ports:\n",
        "            - containerPort: 80\n",
        "          livenessProbe:\n",
        "            httpGet:\n",
        f"              path: {first_health}\n",
        "              port: 80\n",
        "            initialDelaySeconds: 10\n",
        "            periodSeconds: 30\n",
        "          readinessProbe:\n",
        "            httpGet:\n",
        f"              path: {first_health}\n",
        "              port: 80\n",
        "            initialDelaySeconds: 5\n",
        "            periodSeconds: 10\n",
        "          resources:\n",
        "            requests:\n",
        '              cpu: "100m"\n',
        '              memory: "128Mi"\n',
        "            limits:\n",
        '              cpu: "500m"\n',
        '              memory: "256Mi"\n',
    ]
    (k8s_base / "deployment.yaml").write_text("".join(d_lines), encoding="utf-8")

    s_lines = [
        "apiVersion: v1\n",
        "kind: Service\n",
        "metadata:\n",
        f"  name: {first_app}\n",
        "spec:\n",
        "  type: LoadBalancer\n",
        "  selector:\n",
        f"    app: {first_app}\n",
        "  ports:\n",
        "    - protocol: TCP\n",
        "      port: 80\n",
        "      targetPort: 80\n",
    ]
    (k8s_base / "service.yaml").write_text("".join(s_lines), encoding="utf-8")

    k_lines = [
        "apiVersion: kustomize.config.k8s.io/v1beta1\n",
        "kind: Kustomization\n",
        "resources:\n",
        "  - namespace.yaml\n",
        "  - deployment.yaml\n",
        "  - service.yaml\n",
        "commonLabels:\n",
        "  app.kubernetes.io/managed-by: sdd-cli\n",
    ]
    (k8s_base / "kustomization.yaml").write_text("".join(k_lines), encoding="utf-8")

    # Environment overlays
    for env in ("dev", "qa", "prod"):
        env_dir = overlays_dir / env
        env_dir.mkdir(parents=True, exist_ok=True)
        replicas = {"dev": 1, "qa": 2, "prod": 3}[env]

        c_lines = [
            f"# {env.upper()} config patch\n",
            "apiVersion: apps/v1\n",
            "kind: Deployment\n",
            "metadata:\n",
            f"  name: {first_app}\n",
            "spec:\n",
            f"  replicas: {replicas}\n",
            "  template:\n",
            "    spec:\n",
            "      containers:\n",
            f"        - name: {first_app}\n",
            "          env:\n",
            "            - name: ENVIRONMENT\n",
            f'              value: "{env}"\n',
        ]
        (env_dir / "config-patch.yaml").write_text("".join(c_lines), encoding="utf-8")

        ke_lines = [
            "apiVersion: kustomize.config.k8s.io/v1beta1\n",
            "kind: Kustomization\n",
            f"namespace: sdd-{env}\n",
            "resources:\n",
            "  - ../../base\n",
            "patches:\n",
            "  - path: config-patch.yaml\n",
            "images:\n",
            f"  - name: host.docker.internal:8083/{first_app}\n",
            "    newTag: latest\n",
        ]
        (env_dir / "kustomization.yaml").write_text("".join(ke_lines), encoding="utf-8")

    result["valid"] = not any(item.get("severity") == "error" for item in result["findings"])
    return result



# ── Docker Desktop K8s validation ────────────────────────────────────────

def validate_docker_desktop_k8s(root, dry_run=False):
    """Check if Docker Desktop K8s is enabled and accessible."""
    result = configure_result("ValidateDockerDesktopK8s", dry_run, write_enabled=False)

    if dry_run:
        result["actions"].append({"path": "docker-desktop", "key": "k8s.validate", "severity": "info",
                                  "message": "Would check if Docker Desktop K8s is enabled.",
                                  "phase": "audit"})
        result["valid"] = True
        return result

    # Check kubectl
    kubectl = run_native(["kubectl", "version", "--output=json"], root, timeout=15)
    if kubectl["returncode"] != 0:
        add_bucket_item(result["findings"], "kubectl", "missing",
                        "kubectl not found or not working. Enable K8s in Docker Desktop Settings.",
                        "error", "pre-start")
        result["valid"] = False
        return result

    # Try to parse server version
    try:
        k8s_info = json.loads(kubectl["stdout"])
        server = k8s_info.get("serverVersion", {})
        git_version = server.get("gitVersion", "unknown")
        result["actions"].append({"path": "docker-desktop", "key": "k8s.server", "severity": "info",
                                  "message": f"Docker Desktop K8s is running (v{git_version}).",
                                  "phase": "audit"})
    except (json.JSONDecodeError, KeyError):
        result["actions"].append({"path": "docker-desktop", "key": "k8s.server", "severity": "info",
                                  "message": "Docker Desktop K8s is running (version unknown).",
                                  "phase": "audit"})

    # Check cluster info
    cluster = run_native(["kubectl", "cluster-info", "--request-timeout=5s"], root, timeout=10)
    if cluster["returncode"] != 0:
        add_bucket_item(result["findings"], "k8s", "cluster.unreachable",
                        "K8s cluster is not reachable via kubectl.",
                        "error", "post-start")
        result["valid"] = False
        return result

    # Check if this is Docker Desktop (check context name)
    ctx = run_native(["kubectl", "config", "current-context"], root, timeout=5)
    context_name = ctx["stdout"].strip() if ctx["returncode"] == 0 else "unknown"
    if "docker" in context_name.lower() or "desktop" in context_name.lower():
        result["actions"].append({"path": "k8s", "key": "context", "severity": "info",
                                  "message": f"K8s context is '{context_name}' (Docker Desktop).",
                                  "phase": "audit"})
    else:
        add_bucket_item(result["findings"], "k8s", "context.warning",
                        f"K8s context is '{context_name}' - expected Docker Desktop context.",
                        "warning", "audit")

    result["valid"] = not any(item.get("severity") == "error" for item in result["findings"])
    return result


# ── K8s access setup (port-forward) ─────────────────────────────────────

def setup_k8s_access(root, dry_run=False):
    """Set up port-forward access to deployed apps and display URLs."""
    result = configure_result("SetupK8sAccess", dry_run, write_enabled=not dry_run)
    apps_path = root / "infra" / "deployment" / "apps.json"

    if not apps_path.exists():
        add_bucket_item(result["findings"], "infra/deployment/apps.json", "missing",
                        "apps.json not found.", "error", "pre-start")
        result["valid"] = False
        return result

    try:
        apps_data = read_json(apps_path, optional=False)
        apps = apps_data.get("apps", [])
    except Exception as ex:
        add_bucket_item(result["findings"], "infra/deployment/apps.json", "read_error",
                        f"Could not parse: {ex}", "error", "pre-start")
        result["valid"] = False
        return result

    if not apps:
        add_bucket_item(result["findings"], "infra/deployment/apps.json", "no_apps",
                        "No apps defined.", "warning", "pre-start")
        result["valid"] = True
        return result

    if dry_run:
        for app in apps:
            result["actions"].append({
                "path": f"k8s/port-forward/{app['appId']}", "key": "port-forward.plan",
                "severity": "info",
                "message": f"Would set up port-forward for {app['appId']} in dev/qa/prod.",
                "phase": "apply"
            })
        result["valid"] = True
        return result

    # Validate K8s first
    k8s_valid = validate_docker_desktop_k8s(root)
    if not k8s_valid.get("valid", False):
        for f in k8s_valid.get("findings", []):
            result["findings"].append(f)
        result["valid"] = False
        return result

    for app in apps:
        app_id = app["appId"]
        health_path = app.get("healthPath", "/health")

        for env in ("dev", "qa", "prod"):
            ns = f"sdd-{env}"
            local_port = {"dev": 8081, "qa": 8082, "prod": 8083}[env]

            # Check if namespace exists
            ns_check = run_native(["kubectl", "get", "ns", ns, "--request-timeout=3s"], root, timeout=10)
            if ns_check["returncode"] != 0:
                result["actions"].append({
                    "path": f"k8s/{ns}", "key": "namespace.missing",
                    "severity": "info",
                    "message": f"Namespace {ns} does not exist yet - deploy first.",
                    "phase": "audit"
                })
                continue

            # Check if service exists
            svc_check = run_native(
                ["kubectl", "-n", ns, "get", "svc", app_id,
                 "-o", "jsonpath={.spec.ports[0].nodePort}", "--request-timeout=3s"],
                root, timeout=10
            )

            if svc_check["returncode"] == 0 and svc_check["stdout"].strip():
                node_port = svc_check["stdout"].strip()
                url = f"http://localhost:{node_port}"
                result["actions"].append({
                    "path": f"k8s/{ns}/{app_id}", "key": "url.available",
                    "severity": "info",
                    "message": f"{env.upper()} {app_id} accessible at: {url}{health_path}",
                    "phase": "audit"
                })
            else:
                # Suggest port-forward command
                pf_cmd = f"kubectl port-forward -n {ns} svc/{app_id} {local_port}:80"
                result["actions"].append({
                    "path": f"k8s/{ns}/{app_id}", "key": "port-forward.command",
                    "severity": "info",
                    "message": f"{env.upper()} {app_id}: run `{pf_cmd}` then visit http://localhost:{local_port}",
                    "phase": "audit"
                })

    result["valid"] = not any(item.get("severity") == "error" for item in result["findings"])
    return result

# ── CLI entry point ──────────────────────────────────────────────────────

def run_environment_lab(args: list[str]) -> int:
    """CLI entry point for environment-lab commands."""
    import json as _json
    from ._shared import parse_pairs

    if not args:
        print("Available: setup-lab, compose-up, compose-down, init-local-files, init-project-profile, "
              "init-quality-templates, set-openproject-env, set-monitoring-env, set-gitea-runner-env, "
              "split-infra-env, build-gitea-images, set-gitea-branch-protection, validate-observability, "
              "validate-gitea-runner, set-client-tools, set-project-stack, "
              "set-project-stack-metadata, set-quality-config, validate-docker-desktop-k8s, setup-k8s-access, scaffold-k8s, set-recommended-tools", file=sys.stderr)
        return 1

    subcommand = args[0]
    options = parse_pairs(args[1:]) if len(args) > 1 else {}
    root = Path(options.get("root", REPO_ROOT))
    dry_run = options.get("dry-run", "false").lower() == "true"
    values_raw = options.get("values-json", "{}")
    values = _json.loads(values_raw) if values_raw else {}

    handlers: dict[str, Any] = {
        "setup-lab": lambda: setup_lab(root, dry_run),
        "compose-up": lambda: compose_up(),
        "compose-down": lambda: compose_down(),
        "init-local-files": lambda: init_local_files(root, dry_run),
        "init-project-profile": lambda: init_project_profile(root, dry_run),
        "init-quality-templates": lambda: init_quality_templates(root, dry_run),
        "set-openproject-env": lambda: set_openproject_env(root, values, dry_run),
        "set-monitoring-env": lambda: set_monitoring_env(root, values, dry_run),
        "set-gitea-runner-env": lambda: set_gitea_runner_env(root, values, dry_run),
        "split-infra-env": lambda: split_infra_env(root, dry_run),
        "build-gitea-images": lambda: build_gitea_actions_images(root, dry_run),
        "set-gitea-branch-protection": lambda: set_gitea_branch_protection(root, dry_run),
        "validate-observability": lambda: validate_observability(root, dry_run),
        "validate-gitea-runner": lambda: validate_gitea_runner(root, dry_run),
        "set-client-tools": lambda: set_client_tools(root, values, dry_run),
        "set-project-stack": lambda: set_project_stack(root, values, dry_run),
        "set-project-stack-metadata": lambda: set_project_stack_metadata(root, values, dry_run),
        "set-quality-config": lambda: set_quality_config(root, values, dry_run),
        "validate-docker-desktop-k8s": lambda: validate_docker_desktop_k8s(root, dry_run),
        "setup-k8s-access": lambda: setup_k8s_access(root, dry_run),
        "scaffold-k8s": lambda: scaffold_k8s(root, dry_run),
        "set-recommended-tools": lambda: set_recommended_tools(root, values, dry_run),
    }

    handler = handlers.get(subcommand)
    if handler is None:
        print(f"Unknown environment-lab subcommand: {subcommand}", file=sys.stderr)
        return 1

    result = handler()
    print(_json.dumps(result, indent=2))
    return 0 if result.get("valid", True) else 1
