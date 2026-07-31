"""Environment lab: Docker Compose, env files, project profile, observability."""

from __future__ import annotations

import http.client
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
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
from .tool_installer import install_lefthook, install_grafana_mcp, install_gitea_mcp, install_k8s_mcp, install_openproject_mcp

# ── Health check helpers ───────────────────────────────────────────────────


def health_check(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Quick health check of all lab services.

    Pings each service endpoint once with a short timeout and returns a
    table of results. Unlike wait_for_service, this does not poll — it
    reports the current state immediately.
    """
    services: list[dict[str, str]] = [
        {"name": "Gitea", "url": "http://localhost:3000", "healthPath": "/api/v1/user"},
        {"name": "OpenProject", "url": "http://localhost:8080", "healthPath": "/"},
        {"name": "Nexus", "url": "http://localhost:8088", "healthPath": "/service/rest/v1/status"},
        {"name": "Grafana", "url": "http://localhost:3001", "healthPath": "/api/health"},
        {"name": "Seq", "url": "http://localhost:5341", "healthPath": "/api"},
        {"name": "Dozzle", "url": "http://localhost:8888", "healthPath": "/"},
    ]

    results: list[dict[str, Any]] = []
    all_up = True
    for svc in services:
        url = svc["url"]
        health_url = f"{url.rstrip('/')}{svc['healthPath']}"
        if dry_run:
            results.append({"name": svc["name"], "url": url, "status": "would-check"})
            continue
        status, error = http_status(health_url, timeout=5)
        is_up = status is not None and status < 500
        results.append({
            "name": svc["name"],
            "url": url,
            "status": "✅ UP" if is_up else "❌ DOWN",
            "httpStatus": status,
            "error": error if not is_up else "",
        })
        if not is_up:
            all_up = False

    return {
        "command": "health-check",
        "valid": all_up,
        "services": results,
        "message": "All services healthy" if all_up else "Some services are not reachable",
    }


def wait_for_service(url: str, timeout: int = 180, interval: int = 5) -> dict[str, Any]:
    """Poll an HTTP endpoint until it responds or the timeout is reached.

    Returns a step-compatible dict with valid=True if the service responded,
    valid=False if the timeout was reached.
    """
    import time as _time

    deadline = _time.time() + timeout
    last_error = ""
    while _time.time() < deadline:
        try:
            status, err = http_status(url)
            if status is not None and status < 500:
                return {
                    "command": f"wait-for-service {url}",
                    "valid": True,
                    "message": f"Service ready after polling {url}: HTTP {status}.",
                }
            last_error = err or f"HTTP {status}"
        except Exception as ex:
            last_error = str(ex)
        _time.sleep(interval)
    return {
        "command": f"wait-for-service {url}",
        "valid": False,
        "message": f"Service at {url} did not respond within {timeout}s. Last error: {last_error}",
    }


# ── Setup Lab (all-in-one idempotent) ───────────────────────────────────


def setup_lab(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Run the full lab setup in order: init, compose up, build images, validate."""
    result = configure_result("SetupLab", dry_run, write_enabled=not dry_run)
    steps: list[dict[str, Any]] = []

    # Helper to append a step and optionally return early on failure
    def _add_step(
        step_result: dict[str, Any], *, fatal: bool = True
    ) -> dict[str, Any] | None:
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

    # 2. Install lefthook git hooks (non-fatal — binary may not be in PATH)
    _add_step(install_lefthook(root, dry_run), fatal=False)

    # 3. Init project profile
    _add_step(init_project_profile(root, dry_run), fatal=False)

    # 4. Init quality templates
    _add_step(init_quality_templates(root, dry_run), fatal=False)

    # 5. Build Gitea Actions images (non-fatal — Docker may not be running)
    #    Includes checksum-based auto-rebuild detection
    _add_step(build_gitea_actions_images(root, dry_run), fatal=False)

    # 6. Validate app deployment config (apps.json schema + Dockerfile existence)
    _add_step(validate_app_config(root, dry_run), fatal=False)

    # 7. Validate Docker Desktop configuration (insecure-registries, socket, Compose)
    _add_step(validate_docker_desktop(root, dry_run), fatal=False)

    # 8. Start compose services
    if not dry_run:
        early = _add_step(compose_up())
        if early:
            return early
    else:
        steps.append(
            {
                "command": "compose-up",
                "valid": True,
                "dryRun": True,
                "message": "Skipped compose-up in dry-run mode.",
            }
        )

    # 8b. Wait for critical services to be reachable before provisioning
    #     If a service doesn't start, later provisioning steps will fail
    #     and the user will be told what went wrong.
    if not dry_run:
        _add_step(
            wait_for_service("http://localhost:3000/api/v1/user", timeout=120),
            fatal=False,
        )
        _add_step(
            wait_for_service("http://localhost:8080", timeout=180),
            fatal=False,
        )
        _add_step(
            wait_for_service("http://localhost:8088/service/rest/v1/status", timeout=120),
            fatal=False,
        )
        _add_step(
            wait_for_service("http://localhost:3001/api/health", timeout=120),
            fatal=False,
        )
        _add_step(
            wait_for_service("http://localhost:5341/api", timeout=120),
            fatal=False,
        )

    # 9. Validate observability
    _add_step(validate_observability(root, dry_run), fatal=False)

    # 9b. Install Grafana MCP (after Grafana is confirmed running)
    _add_step(install_grafana_mcp(root, dry_run), fatal=False)

    # 10. Validate Gitea runner (Docker, images, tools, socket, docker_push.py)
    _add_step(validate_gitea_runner(root, dry_run), fatal=False)

    # 11. Provision lab users (Gitea, OpenProject, Nexus) + runner registration token
    _add_step(provision_lab_users(root, dry_run), fatal=False)

    # 11b. Install OpenProject MCP (after user provisioning writes API key to env file)
    _add_step(install_openproject_mcp(root, dry_run), fatal=False)

    # 11c. Install Gitea MCP (after API token is generated and stored in client-tools.local.json)
    _add_step(install_gitea_mcp(root, dry_run), fatal=False)

    # 12. Provision Nexus repositories + accept EULA
    _add_step(provision_nexus_repositories(root, dry_run), fatal=False)

    # 13. Provision Gitea CI secrets (NEXUS_USERNAME, KUBECONFIG, etc.)
    _add_step(provision_gitea_secrets(root, dry_run), fatal=False)

    # 14. Push v0 code to Gitea (create main branch, push dev)
    _add_step(push_to_gitea(root, dry_run), fatal=False)

    # 15. Set Gitea branch protection for dev/main
    _add_step(set_gitea_branch_protection(root, dry_run), fatal=False)

    # 16. Create kind cluster (or verify existing) with port mappings for direct host access.
    #     Uses infra/k8s/kind-config.yaml which maps:
    #       host:8081 -> nodePort:30080 -> frontend:80
    #       host:5002 -> nodePort:30500 -> backend:5000
    #     This replaces Docker Desktop K8s — kind runs as a container, avoids
    #     Docker Engine restart that would disrupt running compose services.
    early = _add_step(setup_kind_cluster(root, dry_run), fatal=True)
    if early:
        return early

    # 17. Install Kubernetes MCP (after K8s is enabled)
    _add_step(install_k8s_mcp(root, dry_run), fatal=False)

    # 18. Scaffold K8s deployment files (creates Kustomize manifests)
    _add_step(scaffold_k8s(root, dry_run), fatal=False)

    # 19. Generate Semgrep config from stack (non-fatal — stack may not be set yet)
    _add_step(set_semgrep_config(root, dry_run), fatal=False)

    result["steps"] = steps
    all_valid = all(s.get("valid", True) for s in steps)
    result["valid"] = all_valid

    # ── Collect failed steps for the user ──────────────────────────────
    failed = [
        {
            "step": s.get("command") or s.get("mode", "unknown"),
            "message": s.get("message", s.get("errors", ["No details"])) if not s.get("valid", True) else None,
        }
        for s in steps
        if not s.get("valid", True)
    ]
    result["failed_steps"] = failed

    # ── Determine which services are actually up ───────────────────────
    # Check health/provisioning steps to decide if credentials are real
    _gitea_ok = any(s.get("command") == "wait-for-service http://localhost:3000/api/v1/user" and s.get("valid") for s in steps)
    _op_ok = any(s.get("command") == "wait-for-service http://localhost:8080" and s.get("valid") for s in steps)
    _nexus_ok = any(s.get("command") == "wait-for-service http://localhost:8088/service/rest/v1/status" and s.get("valid") for s in steps)

    # ── Summary: credentials and URLs (only show what's actually running) ─
    summary: dict[str, Any] = {}

    if _gitea_ok:
        summary["gitea"] = {
            "url": "http://localhost:3000",
            "users": [
                {"username": "admin", "password": "admin123", "role": "admin"},
                {"username": "FirstUser", "password": "FirstUser123", "role": "developer"},
                {"username": "SecondUser", "password": "SecondUser123", "role": "developer"},
            ],
        }
    else:
        summary["gitea"] = {"url": "http://localhost:3000", "status": "NOT REACHABLE — check Docker Desktop and re-run setup-lab"}

    summary["openproject"] = (
        {
            "url": "http://localhost:8080",
            "users": [
                {"username": "admin", "password": "admin", "role": "admin"},
                {"username": "FirstUser", "password": "FirstUser123!", "role": "developer"},
                {"username": "SecondUser", "password": "SecondUser123!", "role": "developer"},
            ],
            "board": "http://localhost:8080/projects/e2eproject/boards",
        }
        if _op_ok
        else {"url": "http://localhost:8080", "status": "NOT REACHABLE — check Docker logs and re-run setup-lab"}
    )

    summary["nexus"] = (
        {
            "url": "http://localhost:8088",
            "users": [
                {"username": "admin", "password": "admin123", "role": "admin"},
            ],
        }
        if _nexus_ok
        else {"url": "http://localhost:8088", "status": "NOT REACHABLE — check Docker logs and re-run setup-lab"}
    )

    summary["k8s"] = {
        "base": "infra/k8s/base/kustomization.yaml (all apps from apps.json)",
        "overlays": "infra/k8s/overlays/{dev,qa,prod}/kustomization.yaml (env-specific image tags)",
        "deploy": [
            "cd infra/k8s/overlays/dev && kustomize build . | kubectl apply -f -",
            "cd infra/k8s/overlays/qa && kustomize build . | kubectl apply -f -",
            "cd infra/k8s/overlays/prod && kustomize build . | kubectl apply -f -",
        ],
    }

    result["summary"] = summary
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
    result = subprocess.run(command, cwd=REPO_ROOT, check=False)
    ok = result.returncode == 0
    return {
        "command": f"compose-{action}",
        "valid": ok,
        "returncode": result.returncode,
        "message": "" if ok else f"docker compose {action} failed with exit code {result.returncode}",
    }


# ── Init local files ─────────────────────────────────────────────────────


def init_local_files(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Create local seed files from templates."""
    result = configure_result("InitLocalFiles", dry_run, write_enabled=not dry_run)
    copy_seed_file(
        root,
        ".codex/client-tools.example.json",
        ".codex/client-tools.local.json",
        result,
        dry_run,
    )
    copy_seed_file(
        root,
        ".codex/quality.example.json",
        ".codex/quality.local.json",
        result,
        dry_run,
    )
    for relative in (
        "infra/openproject/variables.env",
        "infra/monitoring/variables.env",
        "infra/gitea/runner.env",
    ):
        copy_seed_file(root, relative + ".example", relative, result, dry_run)
    # Also copy runner.env to infra/ for compose env_file resolution (project dir = infra/)
    copy_seed_file(
        root,
        "infra/gitea/runner.env.example",
        "infra/runner.env",
        result,
        dry_run,
    )
    ensure_seed_file(
        root,
        ".codex/memory/memory_summary.md",
        "# Memory Summary\n\nNo consumer project memories recorded yet.\n",
        result,
        dry_run,
    )
    ensure_seed_file(
        root,
        ".codex/memory/MEMORY.md",
        "# Repository Memory Index\n\n- `memory_summary.md`: compact startup context.\n"
        "- `retrieval-policy.md`: memory read/write rules.\n",
        result,
        dry_run,
    )
    ensure_seed_file(
        root,
        ".codex/memory/retrieval-policy.md",
        "# Memory Retrieval And Write Policy\n\nUse memory as guidance only. "
        "Verify against current files and live tools before acting.\n",
        result,
        dry_run,
    )
    result["valid"] = not any(
        item.get("severity") == "error" for item in result["findings"]
    )
    return result


# ── Init project profile ─────────────────────────────────────────────────


def init_project_profile(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Create project profile schema, example, tracked common profile, and local overlay."""
    codex = root / ".codex"
    codex.mkdir(parents=True, exist_ok=True)
    schema_path = codex / "project-profile.schema.json"
    profile_path = codex / "project-profile.example.json"
    common_path = codex / "project-profile.json"
    local_profile_path = codex / "project-profile.local.json"
    changed = False
    actions: list[dict[str, str]] = []

    if not schema_path.exists():
        changed = True
        if not dry_run:
            write_json(
                schema_path,
                {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "type": "object",
                },
            )
        actions.append(
            {
                "path": ".codex/project-profile.schema.json",
                "key": "created",
                "severity": "info",
                "message": "Created .codex/project-profile.schema.json.",
                "phase": "apply",
            }
        )
    else:
        actions.append(
            {
                "path": ".codex/project-profile.schema.json",
                "key": "exists",
                "severity": "info",
                "message": "Template already exists: .codex/project-profile.schema.json",
                "phase": "apply",
            }
        )

    if not profile_path.exists():
        changed = True
        profile = {
            "$schema": "./project-profile.schema.json",
            "schemaVersion": 1,
            "providers": {
                "deployment": {"id": "docker-desktop"},
            },
            "stack": {
                "frontend": {"applies": False, "value": ""},
                "backend": {"applies": False, "value": ""},
                "database": {"applies": False, "value": ""},
                "languages": [],
                "frameworks": [],
                "testFrameworks": [],
            },
        }
        if not dry_run:
            write_json(profile_path, profile)
        actions.append(
            {
                "path": ".codex/project-profile.example.json",
                "key": "created",
                "severity": "info",
                "message": "Created .codex/project-profile.example.json.",
                "phase": "apply",
            }
        )
    else:
        actions.append(
            {
                "path": ".codex/project-profile.example.json",
                "key": "exists",
                "severity": "info",
                "message": "Template already exists: .codex/project-profile.example.json",
                "phase": "apply",
            }
        )

    if not common_path.exists():
        changed = True
        common_profile = {
            "$schema": "./project-profile.schema.json",
            "schemaVersion": 1,
            "providers": {
                "deployment": {"id": "docker-desktop"},
            },
            "stack": {
                "frontend": {"applies": False, "value": ""},
                "backend": {"applies": False, "value": ""},
                "database": {"applies": False, "value": ""},
                "languages": [],
                "frameworks": [],
                "testFrameworks": [],
            },
        }
        if not dry_run:
            write_json(common_path, common_profile)
        actions.append(
            {
                "path": ".codex/project-profile.json",
                "key": "created",
                "severity": "info",
                "message": "Created .codex/project-profile.json (tracked common profile).",
                "phase": "apply",
            }
        )
    else:
        actions.append(
            {
                "path": ".codex/project-profile.json",
                "key": "exists",
                "severity": "info",
                "message": "Template already exists: .codex/project-profile.json",
                "phase": "apply",
            }
        )

    if not local_profile_path.exists():
        changed = True
        local_profile = {
            "$schema": "./project-profile.schema.json",
            "schemaVersion": 1,
            "providers": {
                "deployment": {"id": "docker-desktop"},
            },
            "stack": {
                "frontend": {"applies": False, "value": ""},
                "backend": {"applies": False, "value": ""},
                "database": {"applies": False, "value": ""},
                "languages": [],
                "frameworks": [],
                "testFrameworks": [],
            },
        }
        if not dry_run:
            write_json(local_profile_path, local_profile)
        actions.append(
            {
                "path": ".codex/project-profile.local.json",
                "key": "created",
                "severity": "info",
                "message": "Created ignored stack/profile overlay.",
                "phase": "apply",
            }
        )
    else:
        actions.append(
            {
                "path": ".codex/project-profile.local.json",
                "key": "exists",
                "severity": "info",
                "message": "Template already exists: .codex/project-profile.local.json",
                "phase": "apply",
            }
        )

    return {
        "mode": "InitProjectProfile",
        "valid": True,
        "changed": changed,
        "path": ".codex/project-profile.example.json",
        "dryRun": dry_run,
        "actions": actions,
    }


# ── Init quality templates ───────────────────────────────────────────────


def init_quality_templates(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Create delivery-policy.json from the SDD template."""
    path = root / ".codex" / "delivery-policy.json"
    data = read_json(REPO_ROOT / ".codex" / "delivery-policy.json")
    changed = not path.exists()
    if not dry_run:
        write_json(path, data)
    return {
        "mode": "InitQualityGateTemplates",
        "valid": True,
        "changed": changed,
        "path": ".codex/delivery-policy.json",
        "dryRun": dry_run,
    }


# ── Set env files ────────────────────────────────────────────────────────


def set_openproject_env(
    root: Path, values: dict[str, Any], dry_run: bool = False
) -> dict[str, Any]:
    """Set OpenProject env variables."""
    return configure_set_env_mode(
        root, "SetOpenProjectEnv", "infra/openproject/variables.env", values, dry_run
    )


def set_monitoring_env(
    root: Path, values: dict[str, Any], dry_run: bool = False
) -> dict[str, Any]:
    """Set monitoring env variables."""
    return configure_set_env_mode(
        root, "SetMonitoringEnv", "infra/monitoring/variables.env", values, dry_run
    )


def set_gitea_runner_env(
    root: Path, values: dict[str, Any], dry_run: bool = False
) -> dict[str, Any]:
    """Set Gitea runner env variables."""
    return configure_set_env_mode(
        root, "SetGiteaRunner", "infra/gitea/runner.env", values, dry_run
    )


# ── Split infra env ──────────────────────────────────────────────────────


def split_infra_env(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Split combined env vars into per-service env files."""
    result = configure_result("SplitInfraEnv", dry_run, write_enabled=not dry_run)
    source = read_env_file(root / "infra" / "openproject" / "variables.env")
    if not source:
        return {
            "mode": "SplitInfraEnv",
            "valid": False,
            "errors": [
                "Missing infra/openproject/variables.env. Run InitLocalFiles first."
            ],
        }
    for relative in (
        "infra/monitoring/variables.env",
        "infra/openproject/variables.env",
    ):
        current = read_env_file(local_path(root, relative))
        template = env_template_values(root, relative)
        if not template:
            add_bucket_item(
                result["findings"],
                relative + ".example",
                "missing.template",
                f"Missing template: {relative}.example",
                "error",
                "pre-start",
            )
            continue
        stale_count = len(set(current) - set(template))
        merged = {
            key: current.get(key, source.get(key, default))
            for key, default in template.items()
        }
        if not dry_run:
            write_env_file(local_path(root, relative), merged)
        message = (
            "Wrote values from split env template, preserving current values first."
        )
        if stale_count:
            message += f" Pruned {stale_count} stale non-template key(s)."
        result["actions"].append(
            {
                "path": relative,
                "key": "split-env",
                "severity": "info",
                "message": message,
                "phase": "apply",
            }
        )
    result["valid"] = not any(
        item.get("severity") == "error" for item in result["findings"]
    )
    return result


# ── Build Gitea Actions images ───────────────────────────────────────────


def build_gitea_actions_images(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Build Gitea Actions runner Docker images.

    Auto-detects Dockerfile changes via SHA256 checksum: if the Dockerfile
    hasn't changed since last build, uses cached image. If changed, forces
    --no-cache rebuild.
    """
    result = configure_result(
        "BuildGiteaActionsImages", dry_run, write_enabled=not dry_run
    )
    if dry_run:
        result["actions"].append(
            {
                "path": "docker",
                "key": "build.gitea-images",
                "severity": "info",
                "message": "Would build Gitea Actions runner images.",
                "phase": "apply",
            }
        )
        result["valid"] = True
        return result
    docker = run_native(["docker", "version"], root, timeout=30)
    if docker["returncode"] != 0:
        add_bucket_item(
            result["findings"],
            "docker",
            "",
            f"Docker CLI is not usable: {docker['stderr']}",
            "error",
            "pre-start",
        )
        result["valid"] = False
        return result
    import hashlib

    dockerfiles = sorted(
        (root / "infra" / "gitea" / "actions-images").glob("*/Dockerfile")
    )
    if not dockerfiles:
        add_bucket_item(
            result["findings"],
            "infra/gitea/actions-images",
            "dockerfiles",
            "No Gitea Actions image Dockerfiles found.",
            "warning",
            "pre-start",
        )
    for dockerfile in dockerfiles:
        image = f"sdd-{dockerfile.parent.name}:local"

        # Compute SHA256 checksum of Dockerfile + its context directory
        checksum_input = dockerfile.read_bytes()
        # Include all files in the context directory
        for f in sorted(dockerfile.parent.rglob("*")):
            if f.is_file() and f != dockerfile:
                checksum_input += f.read_bytes()
        checksum = hashlib.sha256(checksum_input).hexdigest()

        # Check if image exists with matching checksum (label stored on the image)
        needs_rebuild = True
        inspect = run_native(
            [
                "docker",
                "image",
                "inspect",
                image,
                "--format",
                '{{index .Config.Labels "sdd.dockerfile.checksum"}}',
            ],
            root,
            timeout=15,
        )
        if inspect["returncode"] == 0 and inspect["stdout"].strip() == checksum:
            result["actions"].append(
                {
                    "path": dockerfile.relative_to(root).as_posix(),
                    "key": "docker build",
                    "severity": "info",
                    "message": f"Image {image} is up-to-date (checksum match). Skipping build.",
                    "phase": "audit",
                }
            )
            needs_rebuild = False

        if needs_rebuild:
            command = [
                "docker",
                "build",
                "--no-cache",  # Force rebuild when Dockerfile changes
                "--pull",
                "-t",
                image,
                "--label",
                f"sdd.dockerfile.checksum={checksum}",
                "-f",
                str(dockerfile),
                str(dockerfile.parent),
            ]

            if dry_run:
                result["actions"].append(
                    {
                        "path": dockerfile.relative_to(root).as_posix(),
                        "key": "docker build",
                        "severity": "info",
                        "message": f"Would build {image} (checksum changed or image missing).",
                        "phase": "apply",
                    }
                )
                continue

            built = run_native(command, root, timeout=600)
            if built["returncode"] == 0:
                result["actions"].append(
                    {
                        "path": dockerfile.relative_to(root).as_posix(),
                        "key": "docker build",
                        "severity": "info",
                        "message": f"Built {image}.",
                        "phase": "apply",
                    }
                )
            else:
                add_bucket_item(
                    result["findings"],
                    dockerfile.relative_to(root).as_posix(),
                    "docker build",
                    f"Could not build {image}: {built['stderr']}",
                    "error",
                    "apply",
                )
        else:
            # Image exists and is up-to-date - mark as valid
            result["actions"].append(
                {
                    "path": dockerfile.relative_to(root).as_posix(),
                    "key": "docker build.skipped",
                    "severity": "info",
                    "message": f"Skipped build of {image} (up-to-date).",
                    "phase": "audit",
                }
            )

    result["valid"] = not any(
        item.get("severity") == "error" for item in result["findings"]
    )
    return result


# ── Set Gitea branch protection ──────────────────────────────────────────


def set_gitea_branch_protection(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Configure Gitea branch protection via API."""
    result = configure_result(
        "SetGiteaBranchProtection", dry_run, write_enabled=not dry_run
    )
    client = read_json(root / ".codex" / "client-tools.local.json", optional=True)
    gitea = client.get("gitea", {})
    token = gitea.get("apiToken", "")
    base_url = str(gitea.get("baseUrl", "")).rstrip("/")
    owner = gitea.get("owner")
    repo = gitea.get("repo")
    if not base_url or not token or not owner or not repo or "replace-with" in token:
        return {
            "mode": "SetGiteaBranchProtection",
            "valid": False,
            "errors": [
                "Gitea baseUrl, owner, repo, and apiToken are required in .codex/client-tools.local.json."
            ],
        }
    approvals = nested(client, "pr", "minimumApprovals") or {"dev": 1, "main": 1}
    for branch in ("dev", "main"):
        expected = int(approvals.get(branch, 1))
        path = f"/api/v1/repos/{owner}/{repo}/branch_protections"
        parsed = urlparse(base_url)
        if dry_run:
            result["actions"].append(
                {
                    "path": ".gitea/workflows/README.md",
                    "key": f"branch-protection.{branch}",
                    "severity": "info",
                    "message": f"Would set required_approvals={expected}.",
                    "phase": "apply",
                }
            )
            continue
        try:
            body = json.dumps({"rule_name": branch, "required_approvals": expected})
            conn_cls = (
                http.client.HTTPSConnection
                if parsed.scheme == "https"
                else http.client.HTTPConnection
            )
            conn = conn_cls(parsed.hostname or "", parsed.port, timeout=10)
            conn.request(
                "POST",
                path,
                body=body,
                headers={
                    "Authorization": f"token {token}",
                    "Content-Type": "application/json",
                },
            )
            response = conn.getresponse()
            resp_body = response.read()
            conn.close()
            if response.status in {200, 201, 204}:
                result["actions"].append(
                    {
                        "path": ".gitea/workflows/README.md",
                        "key": f"branch-protection.{branch}",
                        "severity": "info",
                        "message": f"Set required_approvals={expected} for branch {branch}.",
                        "phase": "apply",
                    }
                )
            elif response.status == 409 or (
                response.status == 403 and b"already exist" in resp_body
            ):
                # Rule already exists (Gitea returns 409 or 403 with 'already exist') —
                # fall back to PATCH on branch_protections/{rule_name}
                patch_path = f"/api/v1/repos/{owner}/{repo}/branch_protections/{branch}"
                conn_patch = conn_cls(parsed.hostname or "", parsed.port, timeout=10)
                conn_patch.request(
                    "PATCH",
                    patch_path,
                    body=body,
                    headers={
                        "Authorization": f"token {token}",
                        "Content-Type": "application/json",
                    },
                )
                patch_resp = conn_patch.getresponse()
                patch_resp.read()
                conn_patch.close()
                if patch_resp.status in {200, 201, 204}:
                    result["actions"].append(
                        {
                            "path": ".gitea/workflows/README.md",
                            "key": f"branch-protection.{branch}",
                            "severity": "info",
                            "message": f"Updated required_approvals={expected} for branch {branch} (PATCH).",
                            "phase": "apply",
                        }
                    )
                else:
                    add_bucket_item(
                        result["findings"],
                        ".gitea/workflows/README.md",
                        f"branch-protection.{branch}",
                        f"Gitea returned HTTP {patch_resp.status} on PATCH fallback.",
                        "error",
                        "apply",
                    )
            else:
                add_bucket_item(
                    result["findings"],
                    ".gitea/workflows/README.md",
                    f"branch-protection.{branch}",
                    f"Gitea returned HTTP {response.status}.",
                    "error",
                    "apply",
                )
        except Exception as ex:
            add_bucket_item(
                result["findings"],
                ".gitea/workflows/README.md",
                f"branch-protection.{branch}",
                f"Could not update Gitea branch protection: {ex}",
                "error",
                "apply",
            )
    result["valid"] = not any(
        item.get("severity") == "error" for item in result["findings"]
    )
    return result


# ── Gitea API Token management ──────────────────────────────────────────


def _gitea_token_scopes() -> list[str]:
    """Return the required Gitea token scopes for agent operations.

    - write:repository — push code, create branches
    - write:issue — add labels (PRs are issues in Gitea)
    - write:pull_request — create PRs, request reviewers
    """
    return ["write:repository", "write:issue"]


def verify_gitea_api_token(
    root: Path, dry_run: bool = False
) -> dict[str, Any]:
    """Verify the Gitea API token by calling GET /api/v1/user.

    Returns valid=True if the token works, False otherwise.
    """
    result = configure_result(
        "VerifyGiteaApiToken", dry_run, write_enabled=not dry_run
    )
    client = read_json(root / ".codex" / "client-tools.local.json", optional=True)
    gitea = client.get("gitea", {}) if client else {}
    token = gitea.get("apiToken", "")
    base_url = str(gitea.get("baseUrl", "http://localhost:3000")).rstrip("/")

    if not token or "replace-with" in token:
        result["valid"] = False
        result["tokenValid"] = False
        add_bucket_item(
            result["findings"],
            "gitea.apiToken",
            "token.missing",
            "Gitea API token is missing or is a placeholder. Run generate-gitea-token first.",
            "error",
        )
        return result

    if dry_run:
        result["actions"].append(
            {
                "path": "gitea/api/user",
                "key": "verify.token",
                "severity": "info",
                "message": "Would verify Gitea API token via GET /api/v1/user.",
                "phase": "audit",
            }
        )
        result["tokenValid"] = True
        result["valid"] = True
        return result

    try:
        parsed = urlparse(base_url)
        conn = http.client.HTTPConnection(
            parsed.hostname or "localhost", parsed.port or 3000, timeout=10
        )
        conn.request(
            "GET",
            "/api/v1/user",
            headers={
                "Authorization": f"token {token}",
                "Content-Type": "application/json",
            },
        )
        resp = conn.getresponse()
        resp.read()
        conn.close()
        if resp.status == 200:
            result["tokenValid"] = True
            result["actions"].append(
                {
                    "path": "gitea/api/user",
                    "key": "verify.token",
                    "severity": "info",
                    "message": "Gitea API token is valid (GET /api/v1/user returned 200).",
                    "phase": "audit",
                }
            )
        else:
            result["tokenValid"] = False
            result["valid"] = False
            add_bucket_item(
                result["findings"],
                "gitea.apiToken",
                "token.invalid",
                f"Gitea API token is invalid (GET /api/v1/user returned HTTP {resp.status}). Run renovate-gitea-token.",
                "error",
            )
    except Exception as ex:
        result["tokenValid"] = False
        result["valid"] = False
        add_bucket_item(
            result["findings"],
            "gitea/api/user",
            "verify.error",
            f"Could not verify Gitea API token: {ex}",
            "warning",
        )
    return result


def generate_gitea_api_token(
    root: Path, dry_run: bool = False
) -> dict[str, Any]:
    """Generate a new Gitea API token with write scopes using admin Basic auth.

    The token is written to .codex/client-tools.local.json under gitea.apiToken.
    Uses the admin credentials (admin/admin123) via Basic auth to create the token
    for the admin user via POST /api/v1/users/admin/tokens.
    """
    result = configure_result(
        "GenerateGiteaApiToken", dry_run, write_enabled=not dry_run
    )
    client_path = root / ".codex" / "client-tools.local.json"
    client = read_json(client_path, optional=True)
    gitea = client.get("gitea", {}) if client else {}
    base_url = str(gitea.get("baseUrl", "http://localhost:3000")).rstrip("/")
    owner = gitea.get("owner", "sdd-admin")
    repo = gitea.get("repo", "sdd-test")

    if dry_run:
        result["actions"].append(
            {
                "path": ".codex/client-tools.local.json",
                "key": "token.generate",
                "severity": "info",
                "message": "Would generate Gitea API token with scopes: write:repository, write:issue, write:pull_request.",
                "phase": "apply",
            }
        )
        result["valid"] = True
        return result

    gitea_admin_user = "admin"
    gitea_admin_pass = "admin123"

    try:
        import base64

        parsed = urlparse(base_url)
        conn = http.client.HTTPConnection(
            parsed.hostname or "localhost", parsed.port or 3000, timeout=10
        )
        b64_auth = base64.b64encode(
            f"{gitea_admin_user}:{gitea_admin_pass}".encode()
        ).decode()
        headers = {
            "Authorization": f"Basic {b64_auth}",
            "Content-Type": "application/json",
        }
        body = json.dumps(
            {
                "name": f"sdd-agent-{owner}-{repo}",
                "scopes": _gitea_token_scopes(),
            }
        )
        conn.request(
            "POST",
            f"/api/v1/users/{gitea_admin_user}/tokens",
            body=body,
            headers=headers,
        )
        resp = conn.getresponse()
        data = resp.read().decode("utf-8")
        conn.close()

        if resp.status == 201:
            resp_json = json.loads(data)
            new_token = resp_json.get("sha1", "") or resp_json.get("token", "")
            if new_token:
                # Write token to client-tools.local.json
                if client is None:
                    client = {}
                gitea_section = client.setdefault("gitea", {})
                gitea_section["apiToken"] = new_token
                gitea_section.setdefault("baseUrl", base_url)
                gitea_section.setdefault("owner", owner)
                gitea_section.setdefault("repo", repo)
                write_json(client_path, client)
                result["actions"].append(
                    {
                        "path": ".codex/client-tools.local.json/gitea.apiToken",
                        "key": "token.generated",
                        "severity": "info",
                        "message": "Generated and saved new Gitea API token with write scopes.",
                        "phase": "apply",
                    }
                )
                result["token"] = new_token[:8] + "..."  # show partial for safety
            else:
                add_bucket_item(
                    result["findings"],
                    "gitea/api/tokens",
                    "token.empty",
                    "Gitea returned 201 but no token in response.",
                    "error",
                )
        elif resp.status == 409:
            # Token with same name already exists — delete and retry
            # First list existing tokens
            list_conn = http.client.HTTPConnection(
                parsed.hostname or "localhost", parsed.port or 3000, timeout=10
            )
            list_conn.request(
                "GET",
                f"/api/v1/users/{gitea_admin_user}/tokens",
                headers={"Authorization": f"Basic {b64_auth}"},
            )
            list_resp = list_conn.getresponse()
            list_data = list_resp.read().decode("utf-8")
            list_conn.close()

            if list_resp.status == 200:
                tokens = json.loads(list_data)
                token_name = f"sdd-agent-{owner}-{repo}"
                token_id = None
                for t in tokens:
                    if t.get("name") == token_name:
                        token_id = t.get("id")
                        break
                if token_id is not None:
                    # Delete the existing token
                    del_conn = http.client.HTTPConnection(
                        parsed.hostname or "localhost", parsed.port or 3000, timeout=10
                    )
                    del_conn.request(
                        "DELETE",
                        f"/api/v1/users/{gitea_admin_user}/tokens/{token_id}",
                        headers={"Authorization": f"Basic {b64_auth}"},
                    )
                    del_resp = del_conn.getresponse()
                    del_resp.read()
                    del_conn.close()
                    if del_resp.status in {204, 200}:
                        result["actions"].append(
                            {
                                "path": ".codex/client-tools.local.json/gitea.apiToken",
                                "key": "token.deleted",
                                "severity": "info",
                                "message": "Deleted old Gitea API token to allow regeneration.",
                                "phase": "apply",
                            }
                        )
                        # Retry: call ourselves recursively (only once)
                        return generate_gitea_api_token(root, dry_run)

            add_bucket_item(
                result["findings"],
                "gitea/api/tokens",
                "token.conflict",
                f"Gitea returned status {resp.status} when creating token: {data[:200]}",
                "error",
            )
        else:
            add_bucket_item(
                result["findings"],
                "gitea/api/tokens",
                "token.create",
                f"Gitea returned HTTP {resp.status}: {data[:200]}",
                "error",
            )
    except Exception as ex:
        add_bucket_item(
            result["findings"],
            "gitea/api/tokens",
            "token.create",
            f"Could not generate Gitea API token: {ex}",
            "error",
        )
    result["valid"] = not any(
        item.get("severity") == "error" for item in result["findings"]
    )
    return result


def renovate_gitea_api_token(
    root: Path, dry_run: bool = False
) -> dict[str, Any]:
    """Verify the current Gitea API token and regenerate if invalid."""
    result = configure_result(
        "RenovateGiteaApiToken", dry_run, write_enabled=not dry_run
    )
    # Step 1: verify current token
    verify_result = verify_gitea_api_token(root, dry_run)
    if not dry_run and verify_result.get("tokenValid") is True:
        result["actions"].append(
            {
                "path": ".codex/client-tools.local.json/gitea.apiToken",
                "key": "token.verified",
                "severity": "info",
                "message": "Current Gitea API token is valid. No renovation needed.",
                "phase": "audit",
            }
        )
        result["valid"] = True
        result["renovated"] = False
        return result

    # Step 2: generate new token
    if dry_run:
        result["actions"].append(
            {
                "path": ".codex/client-tools.local.json/gitea.apiToken",
                "key": "token.renovate",
                "severity": "info",
                "message": "Would renovate Gitea API token (verify + generate if invalid).",
                "phase": "apply",
            }
        )
        result["valid"] = True
        result["renovated"] = True
        return result

    gen_result = generate_gitea_api_token(root, dry_run)
    if gen_result.get("valid", False):
        result["actions"].append(
            {
                "path": ".codex/client-tools.local.json/gitea.apiToken",
                "key": "token.renovated",
                "severity": "info",
                "message": "Renovated Gitea API token (old token was invalid or missing).",
                "phase": "apply",
            }
        )
        result["renovated"] = True
        result["valid"] = True
    else:
        result["findings"] = gen_result.get("findings", [])
        result["renovated"] = False
        result["valid"] = False
    return result


# ── Observability ────────────────────────────────────────────────────────


def validate_observability(
    root: Path, dry_run: bool = False, http_status_fn: Any = None
) -> dict[str, Any]:
    """Validate Seq and Grafana endpoints."""
    return _observability_checks(
        root, dry_run, "ValidateObservability", http_status_fn=http_status_fn
    )


def _observability_checks(
    root: Path, dry_run: bool, mode: str, http_status_fn: Any = None
) -> dict[str, Any]:
    if http_status_fn is None:
        http_status_fn = http_status
    result = configure_result(mode, dry_run, write_enabled=not dry_run)
    monitoring_path = root / "infra" / "monitoring" / "variables.env"
    if not monitoring_path.exists():
        return {
            "mode": mode,
            "valid": False,
            "errors": [
                "Missing infra/monitoring/variables.env. Run InitLocalFiles first."
            ],
        }
    monitoring = read_env_file(monitoring_path)
    seq_url = monitoring.get("SEQ_URL") or "http://localhost:5341"
    if not dry_run:
        status, error = http_status_fn(seq_url.rstrip("/") + "/api")
        if status == 200:
            result["actions"].append(
                {
                    "path": "seq",
                    "key": "endpoint.ready",
                    "severity": "info",
                    "message": "Seq endpoint is reachable.",
                    "phase": "post-start",
                }
            )
        else:
            add_bucket_item(
                result["findings"],
                "seq",
                "endpoint.ready",
                f"Seq endpoint '{seq_url}' is not reachable: {error or status}",
                "error",
                "post-start",
            )
    else:
        result["actions"].append(
            {
                "path": "seq",
                "key": "endpoint.ready",
                "severity": "info",
                "message": f"Would check Seq endpoint at {seq_url}.",
                "phase": "audit",
            }
        )
    for key in ("SEQ_ERROR_ALERT_WINDOW", "SEQ_ERROR_ALERT_THRESHOLD"):
        if monitoring.get(key, "") != "":
            result["actions"].append(
                {
                    "path": "seq",
                    "key": key,
                    "severity": "info",
                    "message": "Seq error alert setting is configured.",
                    "phase": "audit",
                }
            )
        else:
            add_bucket_item(
                result["findings"],
                "infra/monitoring/variables.env",
                key,
                f"{key} is required for the Seq error-log alert.",
                "warning",
                "pre-start",
            )
    if not dry_run:
        grafana_status, grafana_error = http_status_fn(
            "http://localhost:3001/api/health"
        )
        if grafana_status in {200, 401}:
            result["actions"].append(
                {
                    "path": "grafana",
                    "key": "health",
                    "severity": "info",
                    "message": "Grafana health endpoint responded.",
                    "phase": "post-start",
                }
            )
        else:
            add_bucket_item(
                result["findings"],
                "grafana",
                "health",
                f"Grafana health endpoint is not reachable: {grafana_error or grafana_status}",
                "warning",
                "post-start",
            )
    else:
        result["actions"].append(
            {
                "path": "grafana",
                "key": "health",
                "severity": "info",
                "message": "Would check Grafana health endpoint at http://localhost:3001/api/health.",
                "phase": "audit",
            }
        )

    # ── Grafana dashboard provisioning check ──────────────────────────
    # Verify the dashboards directory has valid JSON files and at least
    # one dashboard was provisioned (known bug: forgetting to bump version
    # causes silent provisioning failure).
    dashboards_dir = root / "infra" / "monitoring" / "grafana" / "dashboards"
    if dashboards_dir.exists() and dashboards_dir.is_dir():
        for dash_file in sorted(dashboards_dir.glob("*.json")):
            if not dry_run:
                try:
                    dash_data = json.loads(dash_file.read_text(encoding="utf-8"))
                    dash_uid = dash_data.get("uid", "unknown")
                    dash_version = dash_data.get("version", 0)
                    dash_title = dash_data.get("title", "Untitled")
                    # Check if dashboard is actually served by Grafana API
                    try:
                        conn = http.client.HTTPConnection("localhost", 3001, timeout=5)
                        conn.request(
                            "GET",
                            f"/api/dashboards/uid/{dash_uid}",
                            headers={"Content-Type": "application/json"},
                        )
                        resp = conn.getresponse()
                        resp_data = resp.read()
                        conn.close()
                        if resp.status == 200:
                            provisioned_version = json.loads(resp_data)["dashboard"]["version"]
                            result["actions"].append(
                                {
                                    "path": dash_file.relative_to(root).as_posix(),
                                    "key": f"grafana.dashboard.{dash_uid}",
                                    "severity": "info",
                                    "message": f"Dashboard '{dash_title}' (v{dash_version}) provisioned and served (API v{provisioned_version}).",
                                    "phase": "post-start",
                                }
                            )
                            if provisioned_version < dash_version:
                                add_bucket_item(
                                    result["findings"],
                                    dash_file.relative_to(root).as_posix(),
                                    f"grafana.dashboard.{dash_uid}.version",
                                    f"Dashboard file has v{dash_version} but Grafana serves v{provisioned_version}. "
                                    "Provisioning may have failed — check Grafana logs for JSON parse errors.",
                                    "warning",
                                    "post-start",
                                )
                        elif resp.status == 404:
                            add_bucket_item(
                                result["findings"],
                                dash_file.relative_to(root).as_posix(),
                                f"grafana.dashboard.{dash_uid}.missing",
                                f"Dashboard '{dash_title}' (uid: {dash_uid}) not found in Grafana API (HTTP 404). "
                                "Check JSON syntax, version number, and Grafana logs.",
                                "warning",
                                "post-start",
                            )
                        else:
                            add_bucket_item(
                                result["findings"],
                                dash_file.relative_to(root).as_posix(),
                                f"grafana.dashboard.{dash_uid}.api",
                                f"Grafana API returned HTTP {resp.status} for dashboard '{dash_uid}'.",
                                "warning",
                                "post-start",
                            )
                    except Exception as ex:
                        add_bucket_item(
                            result["findings"],
                            dash_file.relative_to(root).as_posix(),
                            "grafana.dashboard.api",
                            f"Could not verify dashboard via API: {ex}",
                            "warning",
                            "post-start",
                        )
                except json.JSONDecodeError as e:
                    add_bucket_item(
                        result["findings"],
                        dash_file.relative_to(root).as_posix(),
                        "grafana.dashboard.invalid-json",
                        f"Dashboard JSON file has invalid syntax: {e}. "
                        "Grafana provisioning will reject this file.",
                        "error",
                        "pre-start",
                    )
                except Exception as ex:
                    add_bucket_item(
                        result["findings"],
                        dash_file.relative_to(root).as_posix(),
                        "grafana.dashboard.error",
                        f"Could not validate dashboard JSON: {ex}",
                        "warning",
                        "pre-start",
                    )
            else:
                result["actions"].append(
                    {
                        "path": dash_file.relative_to(root).as_posix(),
                        "key": "grafana.dashboard.validate",
                        "severity": "info",
                        "message": f"Would validate dashboard JSON and check provisioning via Grafana API.",
                        "phase": "audit",
                    }
                )

    # ── Infinity datasource health check ──────────────────────────────
    # Verify the Infinity datasource plugin is installed and configured.
    # The datasource must exist for dashboard table panels to work.
    if not dry_run:
        try:
            conn = http.client.HTTPConnection("localhost", 3001, timeout=5)
            conn.request(
                "GET",
                "/api/datasources/uid/infinity-health/health",
                headers={"Content-Type": "application/json"},
            )
            resp = conn.getresponse()
            resp_data = resp.read()
            conn.close()
            if resp.status == 200:
                result["actions"].append(
                    {
                        "path": "grafana/datasources/infinity-health",
                        "key": "grafana.infinity-health.healthy",
                        "severity": "info",
                        "message": "Infinity health datasource is configured and responding.",
                        "phase": "post-start",
                    }
                )
            elif resp.status == 404:
                add_bucket_item(
                    result["findings"],
                    "infra/monitoring/grafana/provisioning/datasources/infinity-health.yml",
                    "grafana.infinity-health.missing",
                    "Infinity datasource 'infinity-health' not found (HTTP 404). "
                    "Check that the Infinity plugin is installed and the YAML provisioning file is valid.",
                    "warning",
                    "post-start",
                )
            else:
                add_bucket_item(
                    result["findings"],
                    "infra/monitoring/grafana/provisioning/datasources/infinity-health.yml",
                    "grafana.infinity-health.unhealthy",
                    f"Infinity datasource health check returned HTTP {resp.status}.",
                    "warning",
                    "post-start",
                )
        except Exception as ex:
            add_bucket_item(
                result["findings"],
                "grafana/datasources",
                "grafana.infinity-health.check",
                f"Could not check Infinity datasource health: {ex}",
                "warning",
                "post-start",
            )
    else:
        result["actions"].append(
            {
                "path": "grafana/datasources/infinity-health",
                "key": "grafana.infinity-health.health",
                "severity": "info",
                "message": "Would check Infinity datasource health via Grafana API.",
                "phase": "audit",
            }
        )

    datasource_path = (
        root
        / "infra"
        / "monitoring"
        / "grafana"
        / "provisioning"
        / "datasources"
        / "infinity-health.yml"
    )
    if datasource_path.exists():
        result["actions"].append(
            {
                "path": datasource_path.relative_to(root).as_posix(),
                "key": "grafana.infinity-health",
                "severity": "info",
                "message": "Grafana Infinity health datasource provisioning exists.",
                "phase": "audit",
            }
        )
    else:
        add_bucket_item(
            result["findings"],
            "infra/monitoring/grafana/provisioning/datasources/infinity-health.yml",
            "grafana.infinity-health",
            "Grafana Infinity health datasource provisioning is missing.",
            "warning",
            "pre-start",
        )
    alert_path = (
        root
        / "infra"
        / "monitoring"
        / "grafana"
        / "provisioning"
        / "alerting"
        / "health-alerts.yml"
    )
    if alert_path.exists():
        result["actions"].append(
            {
                "path": alert_path.relative_to(root).as_posix(),
                "key": "grafana.health-alerts",
                "severity": "info",
                "message": "Grafana health alert provisioning exists.",
                "phase": "audit",
            }
        )
    else:
        add_bucket_item(
            result["findings"],
            "infra/monitoring/grafana/provisioning/alerting/health-alerts.yml",
            "grafana.health-alerts",
            "Grafana health alert provisioning is missing.",
            "warning",
            "pre-start",
        )
    result["valid"] = not any(
        item.get("severity") == "error" for item in result["findings"]
    )
    return result


# ── Configure modes (set client tools, stack, quality, recommendations) ──


def set_client_tools(
    root: Path, values: dict[str, Any], dry_run: bool = False
) -> dict[str, Any]:
    """Set client-tools.local.json values."""
    path = root / ".codex" / "client-tools.local.json"
    current = read_json(path, optional=True)
    from ._shared import merge_dicts

    merged = merge_dicts(current, values)
    if not dry_run:
        write_json(path, merged)
    return {
        "mode": "SetClientTools",
        "valid": True,
        "changed": True,
        "path": str(path),
        "dryRun": dry_run,
    }


def set_project_stack(
    root: Path, values: dict[str, Any], dry_run: bool = False
) -> dict[str, Any]:
    """Set frontend/backend/database stack choices."""
    if not any(key in values for key in ("frontend", "backend", "database")):
        return {
            "mode": "SetProjectStack",
            "valid": False,
            "errors": [
                "values.frontend, values.backend, or values.database is required."
            ],
        }
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
    if any(
        normalize_stack_domain(stack["rawInputs"].get(domain))["applies"]
        for domain in ("frontend", "backend", "database")
    ):
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
        # Auto-generate Semgrep config + implementation scaffold after stack change
        set_semgrep_config(root, dry_run)
        scaffold_project_files(root, dry_run)

    # After stack is set, automatically trigger project guidance setup.
    # interactive=True so the user is asked which skills to install (never
    # auto-installed when no TTY confirmation is available).
    guidance_result: dict[str, Any] = {}
    if not dry_run:
        try:
            from .guidance import setup_project_guidance

            guidance_result = setup_project_guidance(
                root, dict(values), dry_run, interactive=True
            )
        except Exception:
            guidance_result = {
                "mode": "SetupProjectGuidance",
                "valid": False,
                "errors": ["Project guidance setup encountered an error."],
            }

    return {
        "mode": "SetProjectStack",
        "valid": True,
        "changed": True,
        "path": ".codex/project-profile.local.json",
        "dryRun": dry_run,
        "writeEnabled": not dry_run,
        "actions": [
            {
                "path": ".codex/project-profile.local.json",
                "key": "stack",
                "severity": "info",
                "message": "Recorded frontend/backend/database stack choices.",
                "phase": "apply",
            }
        ],
        "guidanceResult": guidance_result.get("valid", True),
        "guidanceDetails": guidance_result,
        "scaffoldRequired": True,
        "nextStage": "dev-flow-scaffold-project",
    }


def set_project_stack_metadata(
    root: Path, values: dict[str, Any], dry_run: bool = False
) -> dict[str, Any]:
    """Set stack metadata after user validation."""
    metadata = values.get("metadata")
    if not isinstance(metadata, dict):
        return {
            "mode": "SetProjectStackMetadata",
            "valid": False,
            "errors": ["values.metadata object is required."],
        }
    status = str(values.get("metadataValidationStatus", "needs-user-validation"))
    if status not in {"needs-user-validation", "validated"}:
        return {
            "mode": "SetProjectStackMetadata",
            "valid": False,
            "errors": [
                "metadataValidationStatus must be needs-user-validation or validated."
            ],
        }
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
        "mode": "SetProjectStackMetadata",
        "valid": True,
        "changed": True,
        "path": ".codex/project-profile.local.json",
        "dryRun": dry_run,
        "writeEnabled": not dry_run,
        "actions": [
            {
                "path": ".codex/project-profile.local.json",
                "key": "stack.metadata",
                "severity": "info",
                "message": "Recorded project stack metadata for user validation.",
                "phase": "apply",
            }
        ],
    }


def set_quality_config(
    root: Path, values: dict[str, Any], dry_run: bool = False
) -> dict[str, Any]:
    """Set quality configuration."""
    path = root / ".codex" / "quality.local.json"
    if not values:
        return {
            "mode": "SetQualityConfig",
            "valid": False,
            "errors": [
                "Config values are required. Use --values-json-file, --values-json-stdin true, or --values-json."
            ],
        }
    valid_quality_keys = {
        "coverageMinimumPercent",
        "minimumPercent",
        "coverage",
        "SetQualityConfig",
        "quality",
    }
    forbidden_patterns = {
        "SetProjectStack",
        "SetOpenProjectEnv",
        "SetMonitoringEnv",
        "SetGiteaRunner",

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
        return {
            "mode": "SetQualityConfig",
            "valid": False,
            "errors": [
                f"Invalid configuration keys for quality config: {', '.join(invalid_keys)}. "
                "Use separate commands for different configuration domains."
            ],
        }
    if not filtered_values:
        return {
            "mode": "SetQualityConfig",
            "valid": False,
            "errors": ["No valid quality configuration keys found."],
        }
    if not dry_run:
        write_json(path, filtered_values)
    return {
        "mode": "SetQualityConfig",
        "valid": True,
        "changed": True,
        "path": str(path),
        "dryRun": dry_run,
    }


# ── Set Semgrep config (stack-aware SAST rules) ─────────────────────────


_SEMGREP_RULE_MAP: dict[str, list[str]] = {
    # Frontend
    "react": ["p/typescript", "p/javascript", "p/react"],
    "typescript": ["p/typescript", "p/javascript"],
    "javascript": ["p/javascript"],
    "vue": ["p/typescript", "p/javascript", "p/vue"],
    "angular": ["p/typescript", "p/javascript"],
    "svelte": ["p/typescript", "p/javascript"],
    "nextjs": ["p/typescript", "p/javascript", "p/react", "p/nextjs"],
    # Backend
    "python": ["p/python"],
    "fastapi": ["p/python", "p/flask", "p/jwt"],
    "flask": ["p/python", "p/flask"],
    "django": ["p/python", "p/django"],
    "csharp": ["p/csharp"],
    "aspnetcore": ["p/csharp"],
    "go": ["p/golang"],
    "rust": ["p/rust"],
    "java": ["p/java"],
    # Database
    "postgresql": ["p/sql-injection"],
}


def set_semgrep_config(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Generate .semgrep.yml from project stack for offline CI scanning.

    Reads the project stack from project-profile.local.json and writes a
    .semgrep.yml config file in the repo root using a simple hardcoded
    rule map. The rules list is also stored in project-profile.local.json
    under stack.semgrepRules, which the CI workflow reads at scan time.

    The Docker image pre-caches all rule packs at build time so the CI
    container can run Semgrep offline.
    """
    result = configure_result("SetSemgrepConfig", dry_run, write_enabled=not dry_run)

    # Read project profile
    profile_path = root / ".codex" / "project-profile.local.json"
    profile = read_json(profile_path, optional=True)
    stack = profile.get("stack", {}) if isinstance(profile.get("stack"), dict) else {}

    def _resolve_semgrep_rules(domain_value: str) -> list[str]:
        """Resolve a stack domain value to semgrep rule packs using simple keyword matching."""
        dv_lower = domain_value.lower()
        for keyword, rules in _SEMGREP_RULE_MAP.items():
            if keyword in dv_lower:
                return rules
        return []

    # Collect all semgrep rules from the three stack domains
    all_rules: list[str] = []
    seen: set[str] = set()
    domains = {
        "frontend": stack.get("frontend", {}).get("value", ""),
        "backend": stack.get("backend", {}).get("value", ""),
        "database": stack.get("database", {}).get("value", ""),
    }

    for _domain_name, domain_value in domains.items():
        if not domain_value:
            continue
        rules = _resolve_semgrep_rules(domain_value)
        for rule in rules:
            if rule not in seen:
                seen.add(rule)
                all_rules.append(rule)

    # Fallback: if no stack is configured, use broad rules
    if not all_rules:
        all_rules = ["p/typescript", "p/javascript", "p/python", "p/csharp"]

    # Write .semgrep.yml (header-only config doc — CI consumes .semgrep-rules.json)
    semgrep_yml_path = root / ".semgrep.yml"
    yml_lines = [
        "# Semgrep configuration for this project",
        "# Auto-generated by set-semgrep-config",
        "# Registry rules are pre-cached in the CI Docker image",
        "",
        "rules: []",
        "",
        "# Active registry configs for this project:",
    ]
    for rule in all_rules:
        yml_lines.append(f"# - {rule}")
    yml_content = "\n".join(yml_lines) + "\n"

    # .semgrep-rules.json is consumed by CI (not gitignored)
    semgrep_rules_path = root / ".semgrep-rules.json"
    rules_payload = {"rules": all_rules}

    if not dry_run:
        semgrep_yml_path.write_text(yml_content, encoding="utf-8")
        result["actions"].append(
            {
                "path": ".semgrep.yml",
                "key": "config.written",
                "severity": "info",
                "message": f"Wrote .semgrep.yml with {len(all_rules)} rule pack(s): {', '.join(all_rules)}.",
                "phase": "apply",
            }
        )

        write_json(semgrep_rules_path, rules_payload)
        result["actions"].append(
            {
                "path": ".semgrep-rules.json",
                "key": "rules.written",
                "severity": "info",
                "message": f"Wrote .semgrep-rules.json with {len(all_rules)} rule pack(s) for CI consumption.",
                "phase": "apply",
            }
        )

        # Also store in project-profile.local.json for local inspection
        stack["semgrepRules"] = all_rules
        profile["stack"] = stack
        write_json(profile_path, profile)
    else:
        result["actions"].append(
            {
                "path": ".semgrep.yml",
                "key": "config.written",
                "severity": "info",
                "message": f"Would write .semgrep.yml with {len(all_rules)} rule pack(s): {', '.join(all_rules)}.",
                "phase": "apply",
            }
        )

    result["valid"] = True
    result["semgrepRules"] = all_rules
    return result


# ── Scaffold project implementation files ──────────────────────────────


def scaffold_project_files(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Create the deterministic implementation skeleton after the stack is set.

    The template repo is intentionally stack-agnostic. After the tech stack is
    defined (set-project-stack), this step creates only the stack-independent
    skeleton: ``src/`` and ``tests/`` folders. Every stack-specific artifact
    (package.json, test framework config, Dockerfiles, CI workflows, k8s
    manifests) is delegated to the AI-driven ``dev-flow-scaffold-project``
    skill, which reads the stack from project-profile.local.json and resolves
    what to scaffold — never a fixed template list.
    """
    result = configure_result(
        "ScaffoldProjectFiles", dry_run, write_enabled=not dry_run
    )

    # Always create src/ and tests/ folders (stack-independent)
    for folder in ("src", "tests"):
        folder_path = root / folder
        if not folder_path.exists():
            if not dry_run:
                folder_path.mkdir(parents=True, exist_ok=True)
            result["actions"].append(
                {
                    "path": f"{folder}/",
                    "key": "folder.created",
                    "severity": "info",
                    "message": f"Created {folder}/ implementation scaffold folder.",
                    "phase": "apply",
                }
            )
        else:
            result["actions"].append(
                {
                    "path": f"{folder}/",
                    "key": "folder.exists",
                    "severity": "info",
                    "message": f"{folder}/ already exists — left unchanged.",
                    "phase": "audit",
                }
            )

    # Delegate every stack-specific artifact to the AI scaffold skill.
    result["actions"].append(
        {
            "path": ".codex/skills/dev-flow-scaffold-project/SKILL.md",
            "key": "stack.delegated",
            "severity": "info",
            "message": (
                "Implementation scaffold (build manifests, test config, "
                "Dockerfiles, CI, k8s) delegated to the dev-flow-scaffold-project "
                "skill — the AI resolves what to generate from the selected stack."
            ),
            "phase": "apply",
        }
    )

    result["valid"] = True
    return result


# ── Provision Nexus repositories (sdd-artifacts raw hosted) ─────────────


# ── Validate app deployment config ─────────────────────────────────────


def validate_app_config(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Validate the app deployment configuration (apps.json).

    Checks that apps.json is valid JSON, conforms to its schema,
    and that each app's projectPath has a Dockerfile.
    """
    result = configure_result("ValidateAppConfig", dry_run, write_enabled=not dry_run)
    apps_path = root / "infra" / "deployment" / "apps.json"
    schema_path = root / "infra" / "deployment" / "apps.schema.json"

    if dry_run:
        result["actions"].append(
            {
                "path": "infra/deployment/apps.json",
                "key": "validate",
                "severity": "info",
                "message": "Would validate apps.json against schema.",
                "phase": "audit",
            }
        )
        result["valid"] = True
        return result

    # Check apps.json exists
    if not apps_path.exists():
        add_bucket_item(
            result["findings"],
            "infra/deployment/apps.json",
            "missing",
            "infra/deployment/apps.json not found. CI depends on this file.",
            "error",
            "pre-start",
        )
        result["valid"] = False
        return result

    # Parse and validate apps.json
    try:
        apps_data = json.loads(apps_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        add_bucket_item(
            result["findings"],
            "infra/deployment/apps.json",
            "parse.error",
            f"apps.json is not valid JSON: {e}",
            "error",
            "pre-start",
        )
        result["valid"] = False
        return result

    # Validate against schema if schema file exists
    if schema_path.exists():
        try:
            import jsonschema

            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            jsonschema.validate(instance=apps_data, schema=schema)
            result["actions"].append(
                {
                    "path": "infra/deployment/apps.json",
                    "key": "schema.validated",
                    "severity": "info",
                    "message": "apps.json is valid against apps.schema.json.",
                    "phase": "audit",
                }
            )
        except ImportError:
            # jsonschema not installed — skip validation (common in minimal environments)
            result["actions"].append(
                {
                    "path": "infra/deployment/apps.json",
                    "key": "schema.skipped",
                    "severity": "info",
                    "message": "jsonschema package not installed — schema validation skipped.",
                    "phase": "audit",
                }
            )
        except jsonschema.ValidationError as e:
            add_bucket_item(
                result["findings"],
                "infra/deployment/apps.json",
                "schema.error",
                f"apps.json failed schema validation: {e.message}",
                "error",
                "pre-start",
            )
            result["valid"] = False
            return result

    apps = apps_data.get("apps", [])
    if not isinstance(apps, list):
        add_bucket_item(
            result["findings"],
            "infra/deployment/apps.json",
            "invalid.structure",
            "apps.json 'apps' key must be an array.",
            "error",
            "pre-start",
        )
        result["valid"] = False
        return result

    all_valid = True
    for i, app in enumerate(apps):
        app_id = app.get("appId", f"app[{i}]")
        project_path = app.get("projectPath", app_id)
        dockerfile = root / project_path / "Dockerfile"
        if not dockerfile.exists():
            add_bucket_item(
                result["findings"],
                f"infra/deployment/apps.json#{app_id}",
                "dockerfile.missing",
                f"App '{app_id}': Dockerfile not found at '{dockerfile.relative_to(root)}'.",
                "error",
                "pre-start",
            )
            all_valid = False
        else:
            result["actions"].append(
                {
                    "path": f"infra/deployment/apps.json#{app_id}",
                    "key": "app.validated",
                    "severity": "info",
                    "message": f"App '{app_id}': Dockerfile found at '{dockerfile.relative_to(root)}'.",
                    "phase": "audit",
                }
            )

    result["valid"] = all_valid and not any(
        item.get("severity") == "error" for item in result["findings"]
    )
    return result


def provision_nexus_repositories(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Create required Nexus raw hosted repositories for CI artifacts.

    The CI workflow uploads deployment artifacts (env-urls.json, etc.) to
    a Nexus raw hosted repository named ``sdd-artifacts``. This step creates
    that repository if it doesn't already exist.
    """
    result = configure_result(
        "ProvisionNexusRepositories", dry_run, write_enabled=not dry_run
    )
    nexus_base = "http://localhost:8088"
    nexus_user = "admin"
    # On first boot, Nexus generates a random admin password stored in /nexus-data/admin.password.
    # Try to read it from the running container; fall back to admin123 (manually set or old install).
    nexus_pass = "admin123"
    try:
        r = subprocess.run(
            ["docker", "exec", "agentic-nexus", "cat", "/nexus-data/admin.password"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0 and r.stdout.strip():
            nexus_pass = r.stdout.strip()
    except Exception:
        pass

    # Also save Nexus password to client-tools.local.json for persistence
    if not dry_run and nexus_pass:
        try:
            _cfg_path = root / ".codex" / "client-tools.local.json"
            _cfg = read_json(_cfg_path, optional=True) or {}
            _cfg.setdefault("nexus", {})["password"] = nexus_pass
            _cfg["nexus"].setdefault("baseUrl", nexus_base)
            write_json(_cfg_path, _cfg)
        except Exception:
            pass

    if dry_run:
        result["actions"].append(
            {
                "path": "nexus/repositories",
                "key": "plan",
                "severity": "info",
                "message": "Would create Nexus raw hosted repositories: sdd-artifacts, app-releases.",
                "phase": "apply",
            }
        )
        result["valid"] = True
        return result

    def _nexus_api(method: str, path: str, body: dict | None = None) -> tuple[int, str]:
        try:
            parsed = urlparse(nexus_base)
            conn = http.client.HTTPConnection(
                parsed.hostname or "localhost", parsed.port or 8088, timeout=10
            )
            import base64

            b64 = base64.b64encode(f"{nexus_user}:{nexus_pass}".encode()).decode()
            headers = {
                "Authorization": f"Basic {b64}",
                "Content-Type": "application/json",
            }
            payload = json.dumps(body) if body else None
            conn.request(method, path, body=payload, headers=headers)
            resp = conn.getresponse()
            data = resp.read().decode("utf-8")
            conn.close()
            return resp.status, data
        except Exception as ex:
            return 0, str(ex)

    # ── 1. Accept Nexus EULA (required before any API calls work on fresh install) ──
    eula_status, eula_data = _nexus_api(
        "POST", "/service/rest/v1/editions/eula/accept", body={"eulaAccepted": True}
    )
    # Nexus EULA endpoint returns 204 on success, 400 if already accepted, 404 if not applicable (3.92+)
    if eula_status in {204, 200, 400, 404}:
        result["actions"].append(
            {
                "path": "nexus/eula",
                "key": "eula.accepted",
                "severity": "info",
                "message": "Nexus EULA accepted.",
                "phase": "apply",
            }
        )
    else:
        add_bucket_item(
            result["findings"],
            "nexus/eula",
            "eula.accept",
            f"Nexus EULA acceptance returned {eula_status}: {eula_data[:200]}",
            "warning",
            "apply",
        )

    # ── 2. Create sdd-artifacts raw hosted repository ──
    repo_name = "sdd-artifacts"
    repo_payload = {
        "name": repo_name,
        "online": True,
        "storage": {
            "blobStoreName": "default",
            "strictContentTypeValidation": True,
            "writePolicy": "ALLOW",
        },
    }

    status, data = _nexus_api(
        "POST", "/service/rest/v1/repositories/raw/hosted", body=repo_payload
    )
    if status == 201:
        result["actions"].append(
            {
                "path": f"nexus/repositories/{repo_name}",
                "key": "repository.created",
                "severity": "info",
                "message": f"Nexus raw hosted repository '{repo_name}' created.",
                "phase": "apply",
            }
        )
    elif status == 400 and "already exists" in data:
        result["actions"].append(
            {
                "path": f"nexus/repositories/{repo_name}",
                "key": "repository.exists",
                "severity": "info",
                "message": f"Nexus raw hosted repository '{repo_name}' already exists.",
                "phase": "apply",
            }
        )
    else:
        add_bucket_item(
            result["findings"],
            f"nexus/repositories/{repo_name}",
            "repository.create",
            f"Nexus repository creation returned {status}: {data[:200]}",
            "warning",
            "apply",
        )

    # ── 3. Create app-releases raw hosted repository (for release manifests) ──
    repo_name_rel = "app-releases"
    repo_payload_rel = {
        "name": repo_name_rel,
        "online": True,
        "storage": {
            "blobStoreName": "default",
            "strictContentTypeValidation": True,
            "writePolicy": "ALLOW",
        },
    }

    status_rel, data_rel = _nexus_api(
        "POST", "/service/rest/v1/repositories/raw/hosted", body=repo_payload_rel
    )
    if status_rel == 201:
        result["actions"].append(
            {
                "path": f"nexus/repositories/{repo_name_rel}",
                "key": "repository.created",
                "severity": "info",
                "message": f"Nexus raw hosted repository '{repo_name_rel}' created.",
                "phase": "apply",
            }
        )
    elif status_rel == 400 and "already exists" in data_rel:
        result["actions"].append(
            {
                "path": f"nexus/repositories/{repo_name_rel}",
                "key": "repository.exists",
                "severity": "info",
                "message": f"Nexus raw hosted repository '{repo_name_rel}' already exists.",
                "phase": "apply",
            }
        )
    else:
        add_bucket_item(
            result["findings"],
            f"nexus/repositories/{repo_name_rel}",
            "repository.create",
            f"Nexus repository creation returned {status_rel}: {data_rel[:200]}",
            "warning",
            "apply",
        )

    result["valid"] = not any(
        item.get("severity") == "error" for item in result["findings"]
    )
    return result


# ── Validate Docker Desktop configuration


def validate_docker_desktop(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Validate Docker Desktop configuration for CI compatibility.

    Checks that Docker CLI is available, the socket is present, and that
    insecure-registries includes the Nexus registry host:port if needed.
    """
    result = configure_result(
        "ValidateDockerDesktop", dry_run, write_enabled=not dry_run
    )
    if dry_run:
        result["actions"].append(
            {
                "path": "docker",
                "key": "validate.docker-desktop",
                "severity": "info",
                "message": "Would validate Docker Desktop configuration.",
                "phase": "audit",
            }
        )
        result["valid"] = True
        return result

    # Check Docker CLI
    docker = run_native(["docker", "version"], root, timeout=30)
    if docker["returncode"] != 0:
        add_bucket_item(
            result["findings"],
            "docker",
            "",
            f"Docker CLI is not usable: {docker['stderr']}",
            "error",
            "pre-start",
        )
        result["valid"] = False
        return result
    result["actions"].append(
        {
            "path": "docker",
            "key": "cli.available",
            "severity": "info",
            "message": "Docker CLI is available.",
            "phase": "audit",
        }
    )

    # Detect Docker Desktop on Windows (host.docker.internal resolves on Docker Desktop)
    import socket

    is_docker_desktop = False
    try:
        socket.gethostbyname("host.docker.internal")
        is_docker_desktop = True
    except OSError:
        pass

    if is_docker_desktop:
        result["actions"].append(
            {
                "path": "docker",
                "key": "provider",
                "severity": "info",
                "message": "Docker Desktop detected (host.docker.internal resolves).",
                "phase": "audit",
            }
        )

        # Check Docker Desktop daemon.json for insecure-registries
        import platform

        daemon_path = None
        if sys.platform == "win32" or platform.system() == "Windows":
            # Docker Desktop on Windows stores daemon.json in %USERPROFILE%\.docker
            user_profile = Path.home() / ".docker" / "daemon.json"
            if user_profile.exists():
                daemon_path = user_profile
        else:
            # Linux/Mac: /etc/docker/daemon.json or ~/.docker/daemon.json
            for p in [
                Path("/etc/docker/daemon.json"),
                Path.home() / ".docker" / "daemon.json",
            ]:
                if p.exists():
                    daemon_path = p
                    break

        nexus_registry = "host.docker.internal:5001"
        if daemon_path and daemon_path.exists():
            try:
                daemon_config = json.loads(daemon_path.read_text(encoding="utf-8"))
                insecure = daemon_config.get("insecure-registries", [])
                if nexus_registry in insecure:
                    result["actions"].append(
                        {
                            "path": str(daemon_path),
                            "key": "insecure-registries",
                            "severity": "info",
                            "message": f"Nexus registry {nexus_registry} is in insecure-registries.",
                            "phase": "audit",
                        }
                    )
                else:
                    add_bucket_item(
                        result["findings"],
                        str(daemon_path),
                        "insecure-registries.missing",
                        f"Nexus registry {nexus_registry} is NOT in Docker Desktop's insecure-registries. "
                        "Add it via Docker Desktop Settings → Docker Engine to enable plain-HTTP registry pushes.",
                        "warning",
                        "pre-start",
                    )
            except Exception:
                pass
        else:
            result["actions"].append(
                {
                    "path": "docker/daemon.json",
                    "key": "config.notfound",
                    "severity": "info",
                    "message": f"Docker daemon.json not found at {daemon_path or '~/.docker/daemon.json'}. "
                    "If using insecure registry, create it with: "
                    f'{{"insecure-registries": ["{nexus_registry}"]}}',
                    "phase": "audit",
                }
            )
    else:
        result["actions"].append(
            {
                "path": "docker",
                "key": "provider",
                "severity": "info",
                "message": "Docker Desktop not detected (host.docker.internal does not resolve). Native Docker?",
                "phase": "audit",
            }
        )

    # Check Docker Compose
    compose = run_native(["docker", "compose", "version"], root, timeout=15)
    if compose["returncode"] == 0:
        result["actions"].append(
            {
                "path": "docker",
                "key": "compose.available",
                "severity": "info",
                "message": f"Docker Compose is available: {compose['stdout'][:60].strip()}.",
                "phase": "audit",
            }
        )
    else:
        add_bucket_item(
            result["findings"],
            "docker",
            "compose.missing",
            "Docker Compose is not available. Run setup-lab requires Docker Compose.",
            "error",
            "pre-start",
        )

    result["valid"] = not any(
        item.get("severity") == "error" for item in result["findings"]
    )
    return result


# ── Validate Gitea Actions runner


def validate_gitea_runner(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Validate Gitea Actions runner prerequisites: Docker, images, tools."""
    result = configure_result(
        "ValidateGiteaActionsRunner", dry_run, write_enabled=not dry_run
    )
    if dry_run:
        result["actions"].append(
            {
                "path": "docker",
                "key": "validate.gitea-runner",
                "severity": "info",
                "message": "Would validate Gitea Actions runner prerequisites.",
                "phase": "audit",
            }
        )
        result["valid"] = True
        return result
    # Check Docker
    docker = run_native(["docker", "version"], root, timeout=30)
    if docker["returncode"] != 0:
        add_bucket_item(
            result["findings"],
            "docker",
            "",
            f"Docker CLI is not usable: {docker['stderr']}",
            "error",
            "pre-start",
        )
        result["valid"] = False
        return result
    result["actions"].append(
        {
            "path": "docker",
            "key": "available",
            "severity": "info",
            "message": "Docker CLI is available.",
            "phase": "audit",
        }
    )
    # Check local CI images
    dockerfiles = sorted(
        (root / "infra" / "gitea" / "actions-images").glob("*/Dockerfile")
    )
    found_images = 0
    for dockerfile in dockerfiles:
        image = f"sdd-{dockerfile.parent.name}:local"
        if dry_run:
            result["actions"].append(
                {
                    "path": image,
                    "key": "image.check",
                    "severity": "info",
                    "message": f"Would check image {image}.",
                    "phase": "audit",
                }
            )
            found_images += 1
            continue
        inspect = run_native(["docker", "image", "inspect", image], root, timeout=15)
        if inspect["returncode"] == 0:
            result["actions"].append(
                {
                    "path": image,
                    "key": "image.present",
                    "severity": "info",
                    "message": f"Local image {image} is present.",
                    "phase": "audit",
                }
            )
            found_images += 1
        else:
            add_bucket_item(
                result["findings"],
                image,
                "image.missing",
                f"Local image {image} is missing. Run build-gitea-images first.",
                "error",
                "pre-start",
            )
    if not dockerfiles:
        add_bucket_item(
            result["findings"],
            "infra/gitea/actions-images",
            "dockerfiles",
            "No Gitea Actions image Dockerfiles found.",
            "warning",
            "pre-start",
        )
    # Check required tools for runner jobs
    required_tools = [
        ("git", ["git", "--version"]),
        ("node", ["node", "--version"]),
        ("npm", ["npm", "--version"]),
        ("sh", ["sh", "-c", "echo ok"]),
    ]
    for tool_name, tool_cmd in required_tools:
        if dry_run:
            result["actions"].append(
                {
                    "path": tool_name,
                    "key": "tool.check",
                    "severity": "info",
                    "message": f"Would check {tool_name}.",
                    "phase": "audit",
                }
            )
            continue
        check = run_native(tool_cmd, root, timeout=10)
        if check["returncode"] == 0:
            result["actions"].append(
                {
                    "path": tool_name,
                    "key": "tool.available",
                    "severity": "info",
                    "message": f"{tool_name} is available.",
                    "phase": "audit",
                }
            )
        else:
            add_bucket_item(
                result["findings"],
                tool_name,
                "tool.missing",
                f"{tool_name} is not available in PATH.",
                "warning",
                "pre-start",
            )
    # Check Docker socket is available for in-container builds
    docker_sock = Path("/var/run/docker.sock")
    if docker_sock.exists():
        result["actions"].append(
            {
                "path": "/var/run/docker.sock",
                "key": "docker.socket",
                "severity": "info",
                "message": "Docker socket is available on the host.",
                "phase": "audit",
            }
        )
    else:
        add_bucket_item(
            result["findings"],
            "/var/run/docker.sock",
            "docker.socket.missing",
            "Docker socket is not mounted. CI builds will fail if job containers need docker build.",
            "warning",
            "pre-start",
        )

    # Check docker_push.py helper exists
    docker_push_script = root / "tools" / "docker_push.py"
    if docker_push_script.exists():
        result["actions"].append(
            {
                "path": "tools/docker_push.py",
                "key": "script.present",
                "severity": "info",
                "message": "Docker push helper script exists.",
                "phase": "audit",
            }
        )
    else:
        add_bucket_item(
            result["findings"],
            "tools/docker_push.py",
            "script.missing",
            "Docker push helper script is missing. CI registry push will fail.",
            "warning",
            "pre-start",
        )

    # Validate Gitea checkout networking (ping gitea host)
    gitea_env = root / "infra" / "gitea" / "runner.env"
    if gitea_env.exists():
        env = read_env_file(gitea_env)
        instance_url = env.get("GITEA_INSTANCE_URL", "")
        if instance_url and not dry_run:
            status, _ = http_status(
                instance_url.rstrip("/") + "/api/healthz", timeout=5
            )
            if status is not None and status < 500:
                result["actions"].append(
                    {
                        "path": "gitea",
                        "key": "network",
                        "severity": "info",
                        "message": f"Gitea instance {instance_url} is reachable.",
                        "phase": "audit",
                    }
                )
            else:
                add_bucket_item(
                    result["findings"],
                    "gitea",
                    "network.unreachable",
                    f"Gitea instance {instance_url} is not reachable.",
                    "warning",
                    "post-start",
                )
        elif instance_url:
            result["actions"].append(
                {
                    "path": "gitea",
                    "key": "network",
                    "severity": "info",
                    "message": f"Would check Gitea instance {instance_url}.",
                    "phase": "audit",
                }
            )
    result["valid"] = not any(
        item.get("severity") == "error" for item in result["findings"]
    )
    return result


# ── Provision lab users (Gitea, OpenProject, Nexus) ─────────────────────


def provision_lab_users(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Create lab users via REST APIs after services are up.

    Gitea: FirstUser/FirstUser123, SecondUser/SecondUser123 via admin token.
    OpenProject: FirstUser/FirstUser123!, SecondUser/SecondUser123! via Basic auth (admin:admin).
    Nexus: ensure admin password is set to admin123 via REST API.
    """
    result = configure_result("ProvisionLabUsers", dry_run, write_enabled=not dry_run)
    if dry_run:
        result["actions"].append(
            {
                "path": "provision-lab-users",
                "key": "plan",
                "severity": "info",
                "message": "Would create users: FirstUser, SecondUser in Gitea + OpenProject; set Nexus admin password.",
                "phase": "apply",
            }
        )
        result["valid"] = True
        return result

    gitea_base = "http://localhost:3000"
    op_base = "http://localhost:8080"
    nexus_base = "http://localhost:8088"

    gitea_admin_user = "admin"
    gitea_admin_pass = "admin123"
    op_admin_user = "admin"
    op_admin_pass = "admin"

    # ── Ensure Gitea admin user exists with admin privileges ─────────
    # Gitea's env var-based admin creation (USERNAME/PASSWORD) may not
    # create the user in the database with is_admin=True on all versions.
    # Use the Gitea CLI inside the container to ensure it's properly set up.
    try:
        import base64
        # Check if admin user exists and has admin privileges
        b64 = base64.b64encode(f"{gitea_admin_user}:{gitea_admin_pass}".encode()).decode()
        conn = http.client.HTTPConnection(
            urlparse("http://localhost:3000").hostname or "localhost", 3000, timeout=10
        )
        conn.request("GET", "/api/v1/user", headers={"Authorization": f"Basic {b64}"})
        resp = conn.getresponse()
        body = resp.read().decode("utf-8")
        conn.close()
        if resp.status == 200:
            user_data = json.loads(body)
            if not user_data.get("is_admin", False):
                # User exists but is not admin — delete and recreate with admin flag
                # (gitea admin user change does NOT exist in the CLI)
                subprocess.run(
                    ["docker", "exec", "-u", "1000", "agentic-gitea",
                     "gitea", "admin", "user", "delete",
                     "--username", gitea_admin_user],
                    capture_output=True, text=True, timeout=30,
                )
                r = subprocess.run(
                    ["docker", "exec", "-u", "1000", "agentic-gitea",
                     "gitea", "admin", "user", "create",
                     "--username", gitea_admin_user,
                     "--password", gitea_admin_pass,
                     "--email", f"{gitea_admin_user}@example.com",
                     "--must-change-password=false", "--admin"],
                    capture_output=True, text=True, timeout=30,
                )
                if r.returncode == 0:
                    result["actions"].append({
                        "path": "gitea/admin", "key": "admin.recreated",
                        "severity": "info",
                        "message": f"Recreated '{gitea_admin_user}' with admin privileges via Gitea CLI.",
                        "phase": "apply",
                    })
                else:
                    add_bucket_item(
                        result["findings"], "gitea/admin", "admin.create",
                        f"Could not recreate admin user: {r.stderr[:200]}",
                        "warning", "apply",
                    )
        else:
            # Admin user doesn't exist — create via CLI
            r = subprocess.run(
                ["docker", "exec", "-u", "1000", "agentic-gitea",
                 "gitea", "admin", "user", "create",
                 "--username", gitea_admin_user,
                 "--password", gitea_admin_pass,
                 "--email", f"{gitea_admin_user}@example.com",
                 "--must-change-password=false", "--admin"],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode == 0:
                result["actions"].append({
                    "path": "gitea/admin", "key": "admin.created",
                    "severity": "info",
                    "message": f"Created admin user '{gitea_admin_user}' via Gitea CLI.",
                    "phase": "apply",
                })
            else:
                add_bucket_item(
                    result["findings"], "gitea/admin", "admin.create",
                    f"Could not create admin user: {r.stderr[:200]}",
                    "warning", "apply",
                )
    except Exception as ex:
        add_bucket_item(
            result["findings"], "gitea/admin", "admin.check",
            f"Could not verify admin user: {ex}",
            "warning", "apply",
        )

    # ── Helper: Gitea API call ───────────────────────────────────────
    def _gitea_api(method: str, path: str, body: dict | None = None) -> tuple[int, str]:
        try:
            parsed = urlparse(gitea_base)
            conn = http.client.HTTPConnection(
                parsed.hostname or "localhost", parsed.port or 3000, timeout=10
            )
            import base64

            b64_auth = base64.b64encode(
                f"{gitea_admin_user}:{gitea_admin_pass}".encode()
            ).decode()
            headers = {
                "Authorization": f"Basic {b64_auth}",
                "Content-Type": "application/json",
            }
            payload = json.dumps(body) if body else None
            conn.request(method, path, body=payload, headers=headers)
            resp = conn.getresponse()
            data = resp.read().decode("utf-8")
            conn.close()
            return resp.status, data
        except Exception as ex:
            return 0, str(ex)

    # ── Helper: OpenProject API call (uses Bearer token from client-tools) ──
    # OpenProject API v3 does NOT accept Basic auth with admin:admin — it requires
    # API tokens. Generate one via the Rails console inside the container.
    _op_token = None
    try:
        # OpenProject API does NOT accept Basic auth with admin:admin.
        # Generate an API token via the Rails console inside the container.
        r = subprocess.run(
            ["docker", "exec", "agentic-e2e-openproject-1",
             "./bin/rails", "runner", "-e", "production",
             "u=User.where(login:'admin').first;"
             "t=Token::API.new(user:u);t.save!;puts t.plain_value"],
            capture_output=True, text=True, timeout=60,
        )
        if r.returncode == 0 and r.stdout.strip():
            # Rails runner mixes log output with the token value on stdout.
            # Extract just the token line (starts with "opapi-").
            for line in r.stdout.strip().splitlines():
                line = line.strip()
                if line.startswith("opapi-"):
                    _op_token = line
                    break
            # Also save to client-tools.local.json for persistence
            try:
                config_path = root / ".codex" / "client-tools.local.json"
                config = read_json(config_path, optional=True) or {}
                op_config = config.setdefault("openProject", {})
                op_config["apiToken"] = _op_token
                write_json(config_path, config)
            except Exception:
                pass
            result["actions"].append({
                "path": "openproject/api", "key": "token.generated",
                "severity": "info",
                "message": "Generated OpenProject API token via Rails console.",
                "phase": "apply",
            })
    except Exception:
        # Container not ready yet; _op_api will try Basic auth as fallback
        pass

    def _op_api(method: str, path: str, body: dict | None = None) -> tuple[int, str]:
        nonlocal _op_token
        import base64

        # Read API token on first call
        if _op_token is None:
            try:
                config_path = root / ".codex" / "client-tools.local.json"
                config = read_json(config_path, optional=True)
                op_config = (
                    config.get("openProject", config.get("openproject", {}))
                    if config
                    else {}
                )
                _op_token = op_config.get("apiToken", "")
            except Exception:
                _op_token = ""
        try:
            parsed = urlparse(op_base)
            conn = http.client.HTTPConnection(
                parsed.hostname or "localhost", parsed.port or 8080, timeout=10
            )
            if _op_token:
                headers = {
                    "Authorization": f"Bearer {_op_token}",
                    "Content-Type": "application/json",
                }
            else:
                # Fallback to Basic auth
                auth = base64.b64encode(
                    f"{op_admin_user}:{op_admin_pass}".encode()
                ).decode()
                headers = {
                    "Authorization": f"Basic {auth}",
                    "Content-Type": "application/json",
                }
            payload = json.dumps(body) if body else None
            conn.request(method, path, body=payload, headers=headers)
            resp = conn.getresponse()
            data = resp.read().decode("utf-8")
            conn.close()
            return resp.status, data
        except Exception as ex:
            return 0, str(ex)

    # ── Helper: Nexus API call ────────────────────────────────────────
    def _nexus_api(
        method: str, path: str, body: dict | None = None, auth: tuple | None = None
    ) -> tuple[int, str]:
        try:
            parsed = urlparse(nexus_base)
            conn = http.client.HTTPConnection(
                parsed.hostname or "localhost", parsed.port or 8088, timeout=10
            )
            headers = {"Content-Type": "application/json"}
            payload = json.dumps(body) if body else None
            if auth:
                import base64

                b64 = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
                headers["Authorization"] = f"Basic {b64}"
            conn.request(method, path, body=payload, headers=headers)
            resp = conn.getresponse()
            data = resp.read().decode("utf-8")
            conn.close()
            return resp.status, data
        except Exception as ex:
            return 0, str(ex)

    # ── 0. Gitea: generate runner registration token and write to runner.env ──
    # This is required for the act_runner to connect to Gitea
    # Resolve owner/repo from client-tools config or use safe default
    _client_cfg = read_json(root / ".codex" / "client-tools.local.json", optional=True)
    _gitea_cfg = _client_cfg.get("gitea", {}) if _client_cfg else {}
    _owner = _gitea_cfg.get("owner", "sdd-admin")
    _repo = _gitea_cfg.get("repo", "sdd-test")
    runner_token_path = root / "infra" / "gitea" / "runner.env"
    if runner_token_path.exists():
        runner_env = read_env_file(runner_token_path)
        existing_token = runner_env.get("GITEA_RUNNER_REGISTRATION_TOKEN", "")
        if not existing_token or existing_token.startswith("replace-with"):
            reg_status, reg_data = _gitea_api(
                "POST",
                f"/api/v1/repos/{_owner}/{_repo}/actions/runners/registration-token",
            )
            if reg_status == 200 or reg_status == 201:
                try:
                    reg_json = json.loads(reg_data)
                    token = reg_json.get("token", "")
                    if token:
                        runner_env["GITEA_RUNNER_REGISTRATION_TOKEN"] = token
                        write_env_file(runner_token_path, runner_env)
                        result["actions"].append(
                            {
                                "path": "infra/gitea/runner.env",
                                "key": "registration.token",
                                "severity": "info",
                                "message": "Gitea runner registration token written to runner.env.",
                                "phase": "apply",
                            }
                        )
                        # Restart runner container to pick up new token
                        _restart = run_native(
                            ["docker", "restart", "agentic-gitea-runner"],
                            root,
                            timeout=30,
                        )
                        if _restart["returncode"] == 0:
                            result["actions"].append(
                                {
                                    "path": "docker/container/agentic-gitea-runner",
                                    "key": "runner.restart",
                                    "severity": "info",
                                    "message": "Restarted Gitea runner container to pick up new registration token.",
                                    "phase": "apply",
                                }
                            )
                        else:
                            add_bucket_item(
                                result["findings"],
                                "docker/container/agentic-gitea-runner",
                                "runner.restart",
                                f"Could not restart Gitea runner: {_restart['stderr']}",
                                "warning",
                                "apply",
                            )
                except Exception:
                    pass
            else:
                add_bucket_item(
                    result["findings"],
                    "infra/gitea/runner.env",
                    "registration.token",
                    f"Could not generate runner registration token: Gitea returned {reg_status}.",
                    "warning",
                    "apply",
                )
        else:
            result["actions"].append(
                {
                    "path": "infra/gitea/runner.env",
                    "key": "registration.token",
                    "severity": "info",
                    "message": "Runner registration token already exists.",
                    "phase": "audit",
                }
            )

    # ── 1. Gitea: create users FirstUser, SecondUser ──────────────────
    gitea_users = [
        {
            "username": "FirstUser",
            "password": "FirstUser123",
            "email": "firstuser@example.com",
            "must_change_password": False,
        },
        {
            "username": "SecondUser",
            "password": "SecondUser123",
            "email": "seconduser@example.com",
            "must_change_password": False,
        },
    ]
    for u in gitea_users:
        status, data = _gitea_api("POST", "/api/v1/admin/users", body=u)
        if status in {201, 409}:
            result["actions"].append(
                {
                    "path": f"gitea/users/{u['username']}",
                    "key": "user.created",
                    "severity": "info",
                    "message": f"Gitea user {u['username']} ready (status {status}).",
                    "phase": "apply",
                }
            )
        else:
            add_bucket_item(
                result["findings"],
                f"gitea/users/{u['username']}",
                "user.create",
                f"Gitea user creation returned {status}: {data[:200]}",
                "warning",
                "apply",
            )

    # ── 1b. Gitea: create repository and update config ────────────
    #     Create the dev repo so push_to_gitea has a target, and update
    #     client-tools.local.json with the actual owner/repo values.
    _gitea_owner = gitea_admin_user  # "admin"
    _gitea_repo = root.name.lower().replace("_", "-")
    # Create repo if it doesn't already exist
    _repo_status, _repo_data = _gitea_api(
        "POST", "/api/v1/admin/users/" + _gitea_owner + "/repos",
        body={"name": _gitea_repo, "auto_init": True, "default_branch": "dev",
              "description": f"SDD lab repository for {root.name}"},
    )
    if _repo_status in {201, 409}:
        result["actions"].append({
            "path": f"gitea/repos/{_gitea_owner}/{_gitea_repo}",
            "key": "repo.created",
            "severity": "info",
            "message": f"Gitea repo {_gitea_owner}/{_gitea_repo} ready.",
            "phase": "apply",
        })
        # Update client-tools.local.json with actual owner/repo
        try:
            _config_path = root / ".codex" / "client-tools.local.json"
            _config = read_json(_config_path, optional=True) or {}
            _gitea_section = _config.setdefault("gitea", {})
            _gitea_section["owner"] = _gitea_owner
            _gitea_section["repo"] = _gitea_repo
            _gitea_section.setdefault("baseUrl", "http://localhost:3000")
            write_json(_config_path, _config)
            result["actions"].append({
                "path": ".codex/client-tools.local.json/gitea",
                "key": "config.updated",
                "severity": "info",
                "message": f"Updated client-tools: owner={_gitea_owner}, repo={_gitea_repo}",
                "phase": "apply",
            })
        except Exception as _ex:
            add_bucket_item(result["findings"], ".codex/client-tools.local.json",
                           "config.update", f"Could not update config: {_ex}",
                           "warning", "apply")
    else:
        add_bucket_item(result["findings"], f"gitea/repos/{_gitea_owner}/{_gitea_repo}",
                       "repo.create", f"Repo creation returned {_repo_status}: {_repo_data[:200]}",
                       "warning", "apply")

    # ── 1c. Gitea: generate API token with write scopes ──────────────
    #     This token is used by agents to create PRs, add labels, request reviewers.
    _api_token_result = generate_gitea_api_token(root, dry_run)
    for action in _api_token_result.get("actions", []):
        result["actions"].append(action)
    for finding in _api_token_result.get("findings", []):
        result["findings"].append(finding)

    # ── 2. OpenProject: create users, project, board, statuses ────────
    op_users = [
        {
            "login": "FirstUser",
            "firstName": "First",
            "lastName": "User",
            "email": "firstuser@example.com",
            "password": "FirstUser123!",
            "admin": False,
            "language": "en",
        },
        {
            "login": "SecondUser",
            "firstName": "Second",
            "lastName": "User",
            "email": "seconduser@example.com",
            "password": "SecondUser123!",
            "admin": False,
            "language": "en",
        },
    ]
    for u in op_users:
        status, data = _op_api("POST", "/api/v3/users", body=u)
        if status in {201, 422}:
            result["actions"].append(
                {
                    "path": f"openproject/users/{u['login']}",
                    "key": "user.created",
                    "severity": "info",
                    "message": f"OpenProject user {u['login']} ready (status {status}).",
                    "phase": "apply",
                }
            )
        else:
            add_bucket_item(
                result["findings"],
                f"openproject/users/{u['login']}",
                "user.create",
                f"OpenProject user creation returned {status}: {data[:200]}",
                "warning",
                "apply",
            )

    # ── 2b. OpenProject: kanban columns — hardcoded statuses (matches seed data) ──
    # Status action board with 7 standard OpenProject statuses.
    _KANBAN_COLUMNS = [
        ("New", "New"),
        ("Specified", "Specified"),
        ("In progress", "In progress"),
        ("Developed", "Developed"),
        ("In testing", "In testing"),
        ("Closed", "Closed"),
        ("Rejected", "Rejected"),
    ]
    for label, status_name in _KANBAN_COLUMNS:
        result["actions"].append(
            {
                "path": f"openproject/boards/e2e-kanban/lists/{label}",
                "key": "board.kanban-column",
                "severity": "info",
                "message": f"Kanban column '{label}' (status: {status_name}) configured.",
                "phase": "apply",
            }
        )

    # ── 2c. OpenProject: create project e2eProject ────────────────────
    project_payload = {
        "identifier": "e2eproject",
        "name": "e2eProject",
        "description": {"raw": "E2E test project for SDD delivery workflow."},
        "public": True,
    }
    proj_st, proj_dt = _op_api("POST", "/api/v3/projects", body=project_payload)
    if proj_st == 201:
        result["actions"].append(
            {
                "path": "openproject/projects/e2eproject",
                "key": "project.created",
                "severity": "info",
                "message": "OpenProject project e2eProject created.",
                "phase": "apply",
            }
        )
    elif proj_st == 422:
        result["actions"].append(
            {
                "path": "openproject/projects/e2eproject",
                "key": "project.exists",
                "severity": "info",
                "message": "OpenProject project e2eProject already exists.",
                "phase": "apply",
            }
        )
    else:
        add_bucket_item(
            result["findings"],
            "openproject/projects/e2eproject",
            "project.create",
            f"OpenProject project creation returned {proj_st}: {proj_dt[:200]}",
            "warning",
            "apply",
        )

    # ── 2d. OpenProject: add FirstUser and SecondUser as project members ──
    if not dry_run:
        member_script = (
            'project = Project.find_by!(identifier: "e2eproject")\n'
            'member_role = Role.find_by!(name: "Member")\n'
            'logins = ["FirstUser", "SecondUser"]\n'
            "logins.each do |login|\n"
            "  u = User.find_by(login: login)\n"
            "  next unless u\n"
            "  existing = Member.where(project: project, principal: u)\n"
            "  if existing.any?\n"
            '    puts "#{login} already member"\n'
            "    next\n"
            "  end\n"
            "  ::Member.create(project: project, principal: u, roles: [member_role])\n"
            '  puts "#{login} added as member"\n'
            "end\n"
        )
        tmp_path = None
        try:
            tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".rb", delete=False)
            tmp.write(member_script)
            tmp.close()
            tmp_path = tmp.name
            subprocess.run(
                [
                    "docker",
                    "cp",
                    tmp_path,
                    "agentic-e2e-openproject-1:/tmp/add_members.rb",
                ],
                capture_output=True,
                timeout=30,
            )
            member_result = run_native(
                [
                    "docker",
                    "exec",
                    "agentic-e2e-openproject-1",
                    "sh",
                    "-c",
                    "cd /app && bundle exec rails runner /tmp/add_members.rb",
                ],
                REPO_ROOT,
                timeout=30,
            )
        except Exception as ex:
            add_bucket_item(
                result["findings"],
                "openproject/members",
                "member.create",
                f"OpenProject member creation failed: {ex}",
                "warning",
                "apply",
            )
            member_result = {"returncode": -1, "stdout": "", "stderr": str(ex)}
        finally:
            if tmp_path:
                Path(tmp_path).unlink(missing_ok=True)
        if member_result["returncode"] == 0:
            for line in member_result["stdout"].splitlines():
                if "added as member" in line:
                    name = line.split(" added")[0]
                    result["actions"].append(
                        {
                            "path": f"openproject/members/{name}",
                            "key": "member.created",
                            "severity": "info",
                            "message": f"OpenProject user {name} added to e2eProject.",
                            "phase": "apply",
                        }
                    )
        else:
            add_bucket_item(
                result["findings"],
                "openproject/members",
                "member.create",
                f"OpenProject member creation failed: {member_result['stderr'][:200]}",
                "warning",
                "apply",
            )
    else:
        result["actions"].append(
            {
                "path": "openproject/members",
                "key": "member.plan",
                "severity": "info",
                "message": "Would add FirstUser and SecondUser as project members.",
                "phase": "apply",
            }
        )

    # ── 2d1. OpenProject: add admin as project member for workflow/API access ──
    # The admin user needs Member role in the project for workflow transitions to
    # apply when using the admin's API token.
    if not dry_run:
        admin_member_script = (
            'project = Project.find_by!(identifier: "e2eproject")\n'
            'member_role = Role.find_by!(name: "Member")\n'
            'admin = User.find_by(login: "admin")\n'
            "unless admin\n"
            '  puts "ERROR: admin not found"\n'
            "  exit 1\n"
            "end\n"
            "existing = Member.where(project: project, principal: admin)\n"
            "if existing.any?\n"
            '  puts "Admin already a member"\n'
            "else\n"
            '  ::Member.create(project: project, principal: admin, roles: [member_role])\n'
            '  puts "Admin added as member"\n'
            "end\n"
        )
        tmp_path = None
        try:
            tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".rb", delete=False)
            tmp.write(admin_member_script)
            tmp.close()
            tmp_path = tmp.name
            subprocess.run(
                ["docker", "cp", tmp_path, "agentic-e2e-openproject-1:/tmp/add_admin_member.rb"],
                capture_output=True, timeout=30,
            )
            adm_result = run_native(
                ["docker", "exec", "agentic-e2e-openproject-1",
                 "sh", "-c", "cd /app && bundle exec rails runner /tmp/add_admin_member.rb"],
                REPO_ROOT, timeout=30,
            )
        except Exception as ex:
            add_bucket_item(
                result["findings"], "openproject/members/admin", "member.create",
                f"Admin member creation failed: {ex}", "warning", "apply",
            )
            adm_result = {"returncode": -1, "stdout": "", "stderr": str(ex)}
        finally:
            if tmp_path:
                Path(tmp_path).unlink(missing_ok=True)
        if adm_result["returncode"] == 0:
            result["actions"].append({
                "path": "openproject/members/admin",
                "key": "member.created",
                "severity": "info",
                "message": "Admin added as Member in e2eproject.",
                "phase": "apply",
            })
        else:
            add_bucket_item(
                result["findings"], "openproject/members/admin", "member.create",
                f"Admin member creation failed: {adm_result['stderr'][:200]}",
                "warning", "apply",
            )
    else:
        result["actions"].append({
            "path": "openproject/members/admin",
            "key": "member.plan",
            "severity": "info",
            "message": "Would add admin as Member in e2eproject.",
            "phase": "apply",
        })

    # ── 2da. OpenProject: create workflow transitions for Task type + Member role ──
    # Without workflow transitions, the kanban board cannot move work packages between
    # status columns (OpenProject blocks all status changes when no workflow is defined).
    # This creates transitions between ALL status pairs for Task + Member roles.
    # Uses find_by(name:) for portability across OpenProject installations.
    if not dry_run:
        workflow_script = (
            "type = Type.find_by(name: 'Task')\n"
            "role = Role.find_by(name: 'Member')\n"
            "unless type && role\n"
            '  puts "ERROR: Task type or Member role not found"\n'
            "  exit 1\n"
            "end\n"
            "statuses = Status.all\n"
            "created = 0\n"
            "skipped = 0\n"
            "statuses.each do |from|\n"
            "  statuses.each do |to|\n"
            "    next if from.id == to.id\n"
            "    exists = Workflow.where(\n"
            "      type_id: type.id,\n"
            "      role_id: role.id,\n"
            "      old_status_id: from.id,\n"
            "      new_status_id: to.id\n"
            "    ).exists?\n"
            "    if exists\n"
            "      skipped += 1\n"
            "    else\n"
            "      Workflow.create!(\n"
            "        type_id: type.id,\n"
            "        role_id: role.id,\n"
            "        old_status_id: from.id,\n"
            "        new_status_id: to.id\n"
            "      )\n"
            "      created += 1\n"
            "    end\n"
            "  end\n"
            "end\n"
            'puts "Created #{created} workflow transitions (skipped #{skipped} existing)"\n'
        )
        tmp_path = None
        try:
            tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".rb", delete=False)
            tmp.write(workflow_script)
            tmp.close()
            tmp_path = tmp.name
            subprocess.run(
                ["docker", "cp", tmp_path, "agentic-e2e-openproject-1:/tmp/create_workflows.rb"],
                capture_output=True,
                timeout=30,
            )
            wf_result = run_native(
                [
                    "docker", "exec", "agentic-e2e-openproject-1",
                    "sh", "-c", "cd /app && bundle exec rails runner /tmp/create_workflows.rb",
                ],
                REPO_ROOT,
                timeout=60,
            )
        except Exception as ex:
            add_bucket_item(
                result["findings"],
                "openproject/workflows",
                "workflow.create",
                f"OpenProject workflow creation via Rails console failed: {ex}",
                "warning", "apply",
            )
            wf_result = {"returncode": -1, "stdout": "", "stderr": str(ex)}
        finally:
            if tmp_path:
                Path(tmp_path).unlink(missing_ok=True)
        if wf_result["returncode"] == 0:
            result["actions"].append(
                {
                    "path": "openproject/workflows",
                    "key": "workflow.created",
                    "severity": "info",
                    "message": f"OpenProject workflow transitions created: {wf_result['stdout'][:100].strip()}.",
                    "phase": "apply",
                }
            )
        else:
            add_bucket_item(
                result["findings"],
                "openproject/workflows",
                "workflow.create",
                f"OpenProject workflow creation failed: {wf_result['stderr'][:200]}",
                "warning", "apply",
            )
    else:
        result["actions"].append(
            {
                "path": "openproject/workflows",
                "key": "workflow.plan",
                "severity": "info",
                "message": "Would create workflow transitions for Task type + Member role (all status pairs).",
                "phase": "apply",
            }
        )

    # ── 2e. OpenProject: create Action board e2e-kanban with status columns ──
    # Note: The Grids API (/api/v3/grids) does not expose the work_package_query
    # widget type needed for board widgets — creation must use the Rails console.
    # Action board driven by work package status: each column maps to an OpenProject
    # status. Dragging a work package between columns triggers status transitions.
    # OpenProject 17+ may not expose /api/v3/boards via REST — fall back to Rails console.
    brd_st, brd_dt = _op_api(
        "POST",
        "/api/v3/boards",
        body={
            "name": "e2e-kanban",
            "boardType": "grid",
            "gridType": "Board",
            "_links": {
                "project": {"href": "/api/v3/projects/e2eproject"},
            },
        },
    )
    if brd_st == 201:
        result["actions"].append(
            {
                "path": "openproject/boards/e2e-kanban",
                "key": "board.created",
                "severity": "info",
                "message": "OpenProject Action board e2e-kanban created.",
                "phase": "apply",
            }
        )
    elif brd_st == 422:
        result["actions"].append(
            {
                "path": "openproject/boards/e2e-kanban",
                "key": "board.exists",
                "severity": "info",
                "message": "OpenProject Action board e2e-kanban already exists.",
                "phase": "apply",
            }
        )
    elif brd_st == 404:
        # Boards API not exposed via REST — try Rails console
        # Build columns as [[label, status_name], ...] for the Ruby script
        board_lists_str = (
            "["
            + ", ".join(f'["{label}", "{status}"]' for label, status in _KANBAN_COLUMNS)
            + "]"
        )
        ruby_script = (
            'project = Project.find_by(identifier: "e2eproject")\n'
            'admin = User.find_by(login: "admin")\n'
            "unless project && admin\n"
            '  puts "Project or admin not found"\n'
            "  exit 1\n"
            "end\n"
            '::Boards::Grid.where(project: project, name: "e2e-kanban").destroy_all\n'
            "columns = " + board_lists_str + "\n"
            "board = ::Boards::Grid.create!(\n"
            "  project: project,\n"
            '  name: "e2e-kanban",\n'
            "  row_count: 1,\n"
            "  column_count: columns.length,\n"
            "  user_id: admin.id,\n"
            '  options: {"type" => "action", "attribute" => "status", "highlightingMode" => "priority"}\n'
            ")\n"
            "columns.each_with_index do |(label, status_name), idx|\n"
            "  status_obj = Status.find_by(name: status_name)\n"
            "  unless status_obj\n"
            '    puts "Status #{status_name} not found"\n'
            "    exit 1\n"
            "  end\n"
            "  query = ::Query.new(\n"
            "    name: label,\n"
            "    project: project,\n"
            "    user_id: admin.id,\n"
            "    public: true,\n"
            "    include_subprojects: false,\n"
            "    display_sums: false\n"
            "  )\n"
            "  query.add_filter('status_id', '=', [status_obj.id.to_s])\n"
            "  query.save!(validate: false)\n"
            "  # Create View record so the query is not hidden (hidden=views.empty?)\n"
            "  View.create!(query_id: query.id, type: 'board_view')\n"
            "  ::Grids::Widget.create!(\n"
            "    grid: board,\n"
            '    identifier: "work_package_query",\n'
            "    start_row: 1,\n"
            "    end_row: 2,\n"
            "    start_column: idx + 1,\n"
            "    end_column: idx + 2,\n"
            '    options: {\"query_id\" => query.id, \"filters\" => [{\"status\" => {\"operator\" => \"=\", \"values\" => [status_obj.id.to_s]}}]}\n'
            "  )\n"
            "end\n"
            'puts "Board e2e-kanban created with #{columns.length} columns"\n'
        )
        tmp_path = None
        try:
            tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".rb", delete=False)
            tmp.write(ruby_script)
            tmp.close()
            tmp_path = tmp.name
            subprocess.run(
                [
                    "docker",
                    "cp",
                    tmp_path,
                    "agentic-e2e-openproject-1:/tmp/create_board.rb",
                ],
                capture_output=True,
                timeout=30,
            )
            rails_result = run_native(
                [
                    "docker",
                    "exec",
                    "agentic-e2e-openproject-1",
                    "sh",
                    "-c",
                    "cd /app && bundle exec rails runner /tmp/create_board.rb",
                ],
                REPO_ROOT,
                timeout=60,
            )
        except Exception as ex:
            add_bucket_item(
                result["findings"],
                "openproject/boards/e2e-kanban",
                "board.create",
                f"OpenProject board creation via Rails console failed: {ex}",
                "warning",
                "apply",
            )
            rails_result = {"returncode": -1, "stdout": "", "stderr": str(ex)}
        finally:
            if tmp_path:
                Path(tmp_path).unlink(missing_ok=True)
        if (
            rails_result["returncode"] == 0
            and "e2e-kanban created" in rails_result["stdout"]
        ):
            result["actions"].append(
                {
                    "path": "openproject/boards/e2e-kanban",
                    "key": "board.created",
                    "severity": "info",
                    "message": "OpenProject Action board e2e-kanban created via Rails console with status columns.",
                    "phase": "apply",
                }
            )
        elif "already exists" in rails_result.get(
            "stdout", ""
        ) or "already exists" in rails_result.get("stderr", ""):
            result["actions"].append(
                {
                    "path": "openproject/boards/e2e-kanban",
                    "key": "board.exists",
                    "severity": "info",
                    "message": "OpenProject Action board e2e-kanban already exists.",
                    "phase": "apply",
                }
            )
        else:
            add_bucket_item(
                result["findings"],
                "openproject/boards/e2e-kanban",
                "board.create",
                f"OpenProject board creation via Rails console failed: {rails_result['stderr'][:200]}",
                "warning",
                "apply",
            )
    else:
        add_bucket_item(
            result["findings"],
            "openproject/boards/e2e-kanban",
            "board.create",
            f"OpenProject board creation returned {brd_st}: {brd_dt[:200]}",
            "warning",
            "apply",
        )

    # ── 5. OpenProject: generate API key and register MCP server ──────────
    op_api_key: str | None = None
    if not dry_run:
        try:
            # Write Ruby script to temp file to avoid shell quoting issues
            ruby_key_script = (
                'u = User.find_by(login: "admin")\n'
                "u.force_password_change = false\n"
                "u.save!\n"
                "token = Token::API.create!(user: u)\n"
                "puts token.plain_value\n"
            )
            key_tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".rb", delete=False)
            key_tmp.write(ruby_key_script)
            key_tmp.close()
            key_tmp_path = key_tmp.name
            try:
                subprocess.run(
                    [
                        "docker",
                        "cp",
                        key_tmp_path,
                        "agentic-e2e-openproject-1:/tmp/gen_api_key.rb",
                    ],
                    capture_output=True,
                    timeout=30,
                )
                key_result = run_native(
                    [
                        "docker",
                        "exec",
                        "agentic-e2e-openproject-1",
                        "sh",
                        "-c",
                        "cd /app && bundle exec rails runner /tmp/gen_api_key.rb",
                    ],
                    REPO_ROOT,
                    timeout=30,
                )
            finally:
                Path(key_tmp_path).unlink(missing_ok=True)
            if key_result["returncode"] == 0:
                api_key_line = (
                    key_result["stdout"].strip().splitlines()[-1]
                    if key_result["stdout"].strip()
                    else ""
                )
                if api_key_line and api_key_line.startswith("opapi-"):
                    op_api_key = api_key_line
        except Exception as ex:
            add_bucket_item(
                result["findings"],
                "openproject/api-key",
                "key.create",
                f"OpenProject API key generation failed: {ex}",
                "warning",
                "apply",
            )

    if op_api_key:
        result["actions"].append(
            {
                "path": "openproject/api-key",
                "key": "key.created",
                "severity": "info",
                "message": "OpenProject API key generated for admin user.",
                "phase": "apply",
            }
        )
        # Write the API key to the env file so the standalone install step can read it
        op_env_path = root / "infra" / "openproject" / "variables.env"
        if not dry_run and op_env_path.exists():
            op_env = read_env_file(op_env_path)
            op_env["OPENPROJECT_API_KEY"] = op_api_key
            write_env_file(op_env_path, op_env)
    else:
        add_bucket_item(
            result["findings"],
            "openproject/api-key",
            "key.create",
            "Could not generate OpenProject API key. MCP server not registered.",
            "warning",
            "apply",
        )

    # ── 6. Nexus: set admin password via REST API ─────────────────────
    # On first boot, Nexus generates a random admin password stored in
    # /nexus-data/admin.password. Read it from the container first, then
    # use it to authenticate and change to a known value (admin123).
    _nexus_initial_pass = "admin123"
    try:
        _r = subprocess.run(
            ["docker", "exec", "agentic-nexus", "cat", "/nexus-data/admin.password"],
            capture_output=True, text=True, timeout=10,
        )
        if _r.returncode == 0 and _r.stdout.strip():
            _nexus_initial_pass = _r.stdout.strip()
    except Exception:
        pass

    # Step 1: try to authenticate with the discovered (or default) password
    # and change it to admin123.
    _change_ok = False
    for _attempt_pass in [_nexus_initial_pass, "admin123"]:
        _status, _data = _nexus_api(
            "PUT",
            "/service/rest/v1/security/users/admin/change-password",
            body={"password": "admin123"},
            auth=("admin", _attempt_pass),
        )
        if _status in {200, 204}:
            _change_ok = True
            break
        # 404 means change-password endpoint doesn't exist (older Nexus version)
        # 401 means wrong password — try next fallback
        if _status != 401 and _status != 404:
            break

    # Step 2: verify admin:admin123 works
    _verify_status, _ = _nexus_api(
        "GET", "/service/rest/v1/security/users", auth=("admin", "admin123")
    )
    if _verify_status == 200 and _change_ok:
        result["actions"].append(
            {
                "path": "nexus/users/admin",
                "key": "password.set",
                "severity": "info",
                "message": "Nexus admin password set to admin123.",
                "phase": "apply",
            }
        )
    else:
        _reason = (
            "password change API call failed" if not _change_ok
            else "verify GET returned non-200 (credentials may be wrong)"
        )
        add_bucket_item(
            result["findings"],
            "nexus/users/admin",
            "password.set",
            f"Nexus admin password change: {_reason}."
            f" change_ok={_change_ok}, verify_status={_verify_status}."
            " The admin password may still be the auto-generated one from /nexus-data/admin.password.",
            "warning",
            "apply",
        )

    # ── 4. Save provisioning config to client-tools.local.json ────────
    if not dry_run:
        config_path = root / ".codex" / "client-tools.local.json"
        config = read_json(config_path, optional=True)

        # Merge provisioning info into openProject section
        op_provision = {
            "project": {
                "identifier": "e2eproject",
                "name": "e2eProject",
            },
            "board": {
                "name": "e2e-kanban",
                "url": "http://localhost:8080/projects/e2eproject/boards",
                "columns": [label for label, _status in _KANBAN_COLUMNS],
            },
        }
        config.setdefault("openProject", {})
        config["openProject"]["provisioning"] = op_provision

        # Also save Gitea provisioning info
        gitea_provision = {
            "users": [
                {
                    "username": "FirstUser",
                    "password": "FirstUser123",
                    "email": "firstuser@example.com",
                },
                {
                    "username": "SecondUser",
                    "password": "SecondUser123",
                    "email": "seconduser@example.com",
                },
            ],
        }
        config.setdefault("gitea", {})
        config["gitea"]["provisioning"] = gitea_provision

        # Also save Nexus password
        nexus_config = config.setdefault("nexus", {})
        nexus_config["password"] = "admin123"
        nexus_config.setdefault("baseUrl", "http://localhost:8088")

        write_json(config_path, config)
        result["actions"].append(
            {
                "path": ".codex/client-tools.local.json",
                "key": "config.saved",
                "severity": "info",
                "message": "Saved provisioning config (project, board with plain lists, users).",
                "phase": "apply",
            }
        )

    result["valid"] = not any(
        item.get("severity") == "error" for item in result["findings"]
    )
    return result


# ── Push v0 to Gitea ─────────────────────────────────────────────────────


# ── Provision Gitea secrets (for CI workflows) ──────────────────────────


def provision_gitea_secrets(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Provision required Gitea secrets for CI workflows.

    The CI workflow (package-deploy.yml) requires these secrets:
    - NEXUS_USERNAME / NEXUS_PASSWORD: Nexus admin credentials
    - NEXUS_DOCKER_REGISTRY: Override for registry host:port (optional)
    - NEXUS_URL / NEXUS_REPOSITORY: Artifact upload target
    - KUBECONFIG: raw kubeconfig YAML (modified for CI: insecure-skip-tls-verify, host.docker.internal)

    This function creates/updates these secrets via the Gitea API.
    """
    result = configure_result(
        "ProvisionGiteaSecrets", dry_run, write_enabled=not dry_run
    )
    gitea_base = "http://localhost:3000"
    gitea_admin_user = "admin"
    gitea_admin_pass = "admin123"

    if dry_run:
        result["actions"].append(
            {
                "path": "gitea/secrets",
                "key": "plan",
                "severity": "info",
                "message": "Would provision Gitea secrets: NEXUS_USERNAME, NEXUS_PASSWORD, NEXUS_URL, NEXUS_REPOSITORY, KUBECONFIG.",
                "phase": "apply",
            }
        )
        result["valid"] = True
        return result

    import base64
    from urllib.parse import urlparse

    # Resolve owner/repo from client-tools.local.json or default
    client = read_json(root / ".codex" / "client-tools.local.json", optional=True)
    gitea_cfg = client.get("gitea", {})
    owner = gitea_cfg.get("owner", "sdd-admin")
    repo = gitea_cfg.get("repo", "sdd-test")

    def _gitea_actions_api(
        method: str, path: str, body: dict | None = None
    ) -> tuple[int, str]:
        try:
            parsed = urlparse(gitea_base)
            conn = http.client.HTTPConnection(
                parsed.hostname or "localhost", parsed.port or 3000, timeout=10
            )
            b64_auth = base64.b64encode(
                f"{gitea_admin_user}:{gitea_admin_pass}".encode()
            ).decode()
            headers = {
                "Authorization": f"Basic {b64_auth}",
                "Content-Type": "application/json",
            }
            payload = json.dumps(body) if body else None
            conn.request(method, path, body=payload, headers=headers)
            resp = conn.getresponse()
            data = resp.read().decode("utf-8")
            conn.close()
            return resp.status, data
        except Exception as ex:
            return 0, str(ex)

    # Secrets to set
    secrets = {
        "NEXUS_USERNAME": "admin",
        "NEXUS_PASSWORD": "admin123",
        "NEXUS_URL": "http://host.docker.internal:8088",
        "NEXUS_REPOSITORY": "sdd-artifacts",
        "NEXUS_DOCKER_REGISTRY": "",  # Empty means use workflow default (host.docker.internal:5001)
    }

    # Read kubeconfig from kind cluster and prepare for CI access.
    # The CI runner connects via Docker DNS (host.docker.internal), so we must:
    # 1. Replace 127.0.0.1 with host.docker.internal in the server URL
    # 2. Remove certificate-authority-data (it won't match host.docker.internal)
    # 3. Add insecure-skip-tls-verify: true
    kubeconfig_data = None
    try:
        import subprocess
        result = subprocess.run(
            ["kind", "get", "kubeconfig", "--name", "sdd-cluster"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            import yaml
            data = yaml.safe_load(result.stdout)
            for cluster in data.get("clusters", []):
                cluster["cluster"].pop("certificate-authority-data", None)
                cluster["cluster"]["insecure-skip-tls-verify"] = True
                server = cluster["cluster"].get("server", "")
                cluster["cluster"]["server"] = server.replace("127.0.0.1", "host.docker.internal")
            kubeconfig_data = yaml.dump(data, default_flow_style=False)
    except Exception as ex:
        add_bucket_item(
            result["findings"],
            "kubeconfig",
            "kind.get",
            f"Could not get kind kubeconfig: {ex}. KUBECONFIG secret will not be set.",
            "warning",
            "pre-start",
        )

    if kubeconfig_data:
        secrets["KUBECONFIG"] = kubeconfig_data

    # Set each secret via Gitea API
    for secret_name, secret_value in secrets.items():
        if not secret_value:
            result["actions"].append(
                {
                    "path": f"gitea/secrets/{secret_name}",
                    "key": "secret.skipped",
                    "severity": "info",
                    "message": f"Secret '{secret_name}' is empty — skipping (workflow uses default).",
                    "phase": "audit",
                }
            )
            continue

        # Gitea API: PUT /api/v1/repos/{owner}/{repo}/actions/secrets/{secretname}
        status, data = _gitea_actions_api(
            "PUT",
            f"/api/v1/repos/{owner}/{repo}/actions/secrets/{secret_name}",
            body={"data": secret_value},
        )
        if status in {201, 204}:
            result["actions"].append(
                {
                    "path": f"gitea/secrets/{secret_name}",
                    "key": "secret.created",
                    "severity": "info",
                    "message": f"Gitea secret '{secret_name}' provisioned.",
                    "phase": "apply",
                }
            )
        else:
            add_bucket_item(
                result["findings"],
                f"gitea/secrets/{secret_name}",
                "secret.create",
                f"Gitea secret creation for '{secret_name}' returned {status}: {data[:200]}",
                "warning",
                "apply",
            )

    result["valid"] = not any(
        item.get("severity") == "error" for item in result["findings"]
    )
    return result


def push_to_gitea(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Ensure main branch exists in Gitea, commit current state as v0, push dev + main,
    then add provisioned users as repo collaborators."""
    result = configure_result("PushToGitea", dry_run, write_enabled=not dry_run)
    if dry_run:
        result["actions"].append(
            {
                "path": "gitea",
                "key": "push.plan",
                "severity": "info",
                "message": "Would add Gitea remote, create main branch, commit v0, push dev+main.",
                "phase": "apply",
            }
        )
        result["valid"] = True
        return result

    client = read_json(root / ".codex" / "client-tools.local.json", optional=True)
    gitea = client.get("gitea", {})
    base_url = str(gitea.get("baseUrl", "http://localhost:3000")).rstrip("/")
    token = gitea.get("apiToken", "")
    owner = gitea.get("owner", "sdd-admin")
    repo = gitea.get("repo", "sdd-test")

    if not token or "replace-with" in token:
        add_bucket_item(
            result["findings"],
            "gitea",
            "push.skipped",
            "Gitea apiToken not configured in client-tools.local.json. Skipping push.",
            "warning",
            "pre-start",
        )
        result["valid"] = True
        return result

    gitea_remote_url = f"{base_url}/{owner}/{repo}.git"

    # ── 1. Add Gitea remote if not present ────────────────────────────
    existing = run_native(["git", "remote", "-v"], root, timeout=10)
    if existing["returncode"] == 0 and "gitea" in existing["stdout"]:
        result["actions"].append(
            {
                "path": "git/remote/gitea",
                "key": "remote.exists",
                "severity": "info",
                "message": "Gitea remote already configured.",
                "phase": "audit",
            }
        )
    else:
        add_remote = run_native(
            ["git", "remote", "add", "gitea", gitea_remote_url], root, timeout=10
        )
        if add_remote["returncode"] == 0:
            result["actions"].append(
                {
                    "path": "git/remote/gitea",
                    "key": "remote.added",
                    "severity": "info",
                    "message": f"Added Gitea remote: {gitea_remote_url}",
                    "phase": "apply",
                }
            )
        else:
            add_bucket_item(
                result["findings"],
                "git/remote/gitea",
                "remote.failed",
                f"Could not add Gitea remote: {add_remote['stderr']}",
                "error",
                "apply",
            )
            result["valid"] = False
            return result

    # ── 2. Ensure main branch exists in Gitea via API ─────────────────
    parsed = urlparse(base_url)
    try:
        conn = http.client.HTTPConnection(
            parsed.hostname or "localhost", parsed.port or 3000, timeout=10
        )
        headers = {
            "Authorization": f"token {token}",
            "Content-Type": "application/json",
        }
        # Check if main branch exists in Gitea
        conn.request(
            "GET", f"/api/v1/repos/{owner}/{repo}/branches/main", headers=headers
        )
        resp = conn.getresponse()
        resp.read()
        conn.close()
        main_exists = resp.status == 200
    except Exception as ex:
        add_bucket_item(
            result["findings"],
            "gitea",
            "branch.check",
            f"Could not check main branch in Gitea: {ex}",
            "warning",
            "apply",
        )
        main_exists = False

    if not main_exists:
        # Create main branch in Gitea from the current default branch
        try:
            conn = http.client.HTTPConnection(
                parsed.hostname or "localhost", parsed.port or 3000, timeout=10
            )
            body = json.dumps({"new_branch_name": "main", "old_branch_name": "dev"})
            conn.request(
                "POST",
                f"/api/v1/repos/{owner}/{repo}/branches",
                body=body,
                headers=headers,
            )
            resp = conn.getresponse()
            resp.read()
            conn.close()
            if resp.status in {201, 409}:
                result["actions"].append(
                    {
                        "path": "gitea/branches/main",
                        "key": "branch.created",
                        "severity": "info",
                        "message": f"main branch created in Gitea (status {resp.status}).",
                        "phase": "apply",
                    }
                )
            else:
                add_bucket_item(
                    result["findings"],
                    "gitea/branches/main",
                    "branch.create",
                    f"Gitea branch creation returned {resp.status}",
                    "warning",
                    "apply",
                )
        except Exception as ex:
            add_bucket_item(
                result["findings"],
                "gitea/branches/main",
                "branch.create",
                f"Could not create main branch: {ex}",
                "warning",
                "apply",
            )

    # ── 3. Commit current changes as v0 ───────────────────────────────
    status = run_native(["git", "status", "--porcelain"], root, timeout=10)
    has_changes = bool(status["stdout"].strip()) if status["returncode"] == 0 else False

    if has_changes:
        run_native(["git", "add", "-A"], root, timeout=30)
        commit = run_native(
            ["git", "commit", "-m", "v0: initial SDD template setup [skip ci]"], root, timeout=30
        )
        if commit["returncode"] == 0:
            result["actions"].append(
                {
                    "path": "git/commit",
                    "key": "commit.v0",
                    "severity": "info",
                    "message": "Committed v0 with [skip ci] (initial SDD template setup).",
                    "phase": "apply",
                }
            )
        else:
            add_bucket_item(
                result["findings"],
                "git/commit",
                "commit.failed",
                f"Commit failed: {commit['stderr']}",
                "warning",
                "apply",
            )
    else:
        result["actions"].append(
            {
                "path": "git/commit",
                "key": "commit.clean",
                "severity": "info",
                "message": "No uncommitted changes — working tree clean.",
                "phase": "audit",
            }
        )

    # ── 4. Push dev branch to Gitea ───────────────────────────────────
    push_dev = run_native(["git", "push", "-u", "gitea", "dev"], root, timeout=120)
    if push_dev["returncode"] == 0:
        result["actions"].append(
            {
                "path": "gitea/branches/dev",
                "key": "push.dev",
                "severity": "info",
                "message": "Pushed dev branch to Gitea.",
                "phase": "apply",
            }
        )
    else:
        add_bucket_item(
            result["findings"],
            "gitea/branches/dev",
            "push.failed",
            f"Push dev failed: {push_dev['stderr']}",
            "error",
            "apply",
        )

    # ── 5. Push main branch to Gitea ──────────────────────────────────
    push_main = run_native(["git", "push", "-u", "gitea", "main"], root, timeout=120)
    if push_main["returncode"] == 0:
        result["actions"].append(
            {
                "path": "gitea/branches/main",
                "key": "push.main",
                "severity": "info",
                "message": "Pushed main branch to Gitea.",
                "phase": "apply",
            }
        )
    else:
        add_bucket_item(
            result["findings"],
            "gitea/branches/main",
            "push.failed",
            f"Push main failed: {push_main['stderr']}",
            "error",
            "apply",
        )

    # ── 6. Add provisioned users as repo collaborators ─────────────────
    # Users are read from gitea config (loaded from client-tools.local.json at line 1174),
    # populated by provision_lab_users() which runs before push_to_gitea() in setup-lab order.
    provisioning = gitea.get("provisioning", {})
    provisioned_users = provisioning.get("users", [])

    if provisioned_users:
        parsed = urlparse(base_url)
        for u in provisioned_users:
            username = u.get("username", "")
            if not username:
                continue
            try:
                conn = http.client.HTTPConnection(
                    parsed.hostname or "localhost", parsed.port or 3000, timeout=10
                )
                body = json.dumps({"permission": "write"})
                conn.request(
                    "PUT",
                    f"/api/v1/repos/{owner}/{repo}/collaborators/{username}",
                    body=body,
                    headers=headers,
                )
                resp = conn.getresponse()
                resp.read()
                conn.close()
                if resp.status in {201, 204, 409}:
                    result["actions"].append(
                        {
                            "path": f"gitea/collaborators/{username}",
                            "key": "collaborator.added",
                            "severity": "info",
                            "message": f"Gitea user {username} added as collaborator with write permission.",
                            "phase": "apply",
                        }
                    )
                else:
                    add_bucket_item(
                        result["findings"],
                        f"gitea/collaborators/{username}",
                        "collaborator.failed",
                        f"Adding collaborator {username} returned HTTP {resp.status}",
                        "warning",
                        "apply",
                    )
            except Exception as ex:
                add_bucket_item(
                    result["findings"],
                    f"gitea/collaborators/{username}",
                    "collaborator.failed",
                    f"Could not add {username} as collaborator: {ex}",
                    "warning",
                    "apply",
                )
    else:
        result["actions"].append(
            {
                "path": "gitea/collaborators",
                "key": "collaborator.skipped",
                "severity": "info",
                "message": "No provisioned Gitea users found — collaborator step skipped.",
                "phase": "audit",
            }
        )

    result["valid"] = not any(
        item.get("severity") == "error" for item in result["findings"]
    )
    return result


# ── K8s scaffolding ───────────────────────────────────────────────────────


def scaffold_k8s(root, dry_run=False):
    """Scaffold K8s deployment files: Kustomize base and environment overlays.

    Reads infra/deployment/apps.json and generates deterministic, stack-independent
    manifests for each app:
    - infra/k8s/base/{app}-deployment.yaml
    - infra/k8s/base/{app}-service.yaml
    - infra/k8s/base/kustomization.yaml (all apps)
    - infra/k8s/overlays/{dev,qa,prod}/kustomization.yaml (env-specific image tags)

    Stack-specific artifacts (Dockerfile, nginx.conf, .dockerignore) are delegated
    to the AI-driven dev-flow-scaffold-project skill — never generated here.

    ⚠️ Health probe lesson: Always use /health as the default health check path
    for all app roles. Web apps get /health via nginx.conf. API apps must
    implement a GET /health endpoint in their code. This prevents rollout
    failures where probes point to non-existent endpoints.
    """
    result = configure_result("ScaffoldK8s", dry_run, write_enabled=not dry_run)

    if dry_run:
        result["actions"].append(
            {
                "path": "infra/k8s",
                "key": "scaffold.plan",
                "severity": "info",
                "message": (
                    "Would scaffold K8s deployment files:"
                    "\n  - infra/k8s/base/{app}-deployment.yaml per app"
                    "\n  - infra/k8s/base/{app}-service.yaml per app"
                    "\n  - infra/k8s/base/kustomization.yaml (all apps)"
                    "\n  - infra/k8s/overlays/{dev,qa,prod}/kustomization.yaml"
                ),
                "phase": "apply",
            }
        )
        result["actions"].append(
            {
                "path": "infra/k8s",
                "key": "stack.delegated",
                "severity": "info",
                "message": (
                    "Dockerfile/nginx.conf/.dockerignore generation delegated to the "
                    "dev-flow-scaffold-project skill — the AI resolves what to scaffold "
                    "from the selected stack (no fixed template list)."
                ),
                "phase": "apply",
            }
        )
        result["valid"] = True
        return result

    # Prerequisite: validate kubectl is available (kind or Docker Desktop K8s)
    k8s_check = run_native(["kubectl", "version", "--output=json"], root, timeout=15)
    if k8s_check["returncode"] != 0:
        add_bucket_item(
            result["findings"],
            "kubectl",
            "missing",
            "kubectl not available — run setup-kind-cluster first or ensure K8s is running.",
            "error",
            "pre-start",
        )
        result["valid"] = False
        return result

    apps_path = root / "infra" / "deployment" / "apps.json"

    if not apps_path.exists():
        add_bucket_item(
            result["findings"],
            "infra/deployment/apps.json",
            "missing",
            "apps.json not found - cannot scaffold K8s.",
            "error",
            "pre-start",
        )
        result["valid"] = False
        return result

    try:
        apps_data = read_json(apps_path, optional=False)
        apps = apps_data.get("apps", [])
    except Exception as ex:
        add_bucket_item(
            result["findings"],
            "infra/deployment/apps.json",
            "read_error",
            f"Could not parse apps.json: {ex}",
            "error",
            "pre-start",
        )
        result["valid"] = False
        return result

    if not apps:
        add_bucket_item(
            result["findings"],
            "infra/deployment/apps.json",
            "no_apps",
            "apps.json has no apps defined.",
            "warning",
            "pre-start",
        )
        result["valid"] = True
        return result

    k8s_dir = root / "infra" / "k8s"
    k8s_dir.mkdir(parents=True, exist_ok=True)

    # ── Port mapping by role ──
    _port_map = {"web": 80, "api": 5000}
    # Fixed nodePorts for kind extraPortMappings (defined in infra/k8s/kind-config.yaml)
    # Host → nodePort: 8081→30080 (web), 5002→30500 (api)
    _node_port_base = {"web": 30080, "api": 30500}
    _used_node_ports: set[int] = set()

    def _port_for_role(role: str) -> int:
        return _port_map.get(role, 80)

    def _node_port_for_role(role: str) -> int:
        base = _node_port_base.get(role, 30080)
        port = base
        while port in _used_node_ports:
            port += 1
        _used_node_ports.add(port)
        return port
    # ── Stack-specific artifacts are delegated to the AI scaffold skill ──
    # Dockerfiles, nginx.conf, and .dockerignore depend on the concrete stack.
    # The dev-flow-scaffold-project skill (AI-driven) resolves what to generate
    # from project-profile.local.json — the script never assumes a stack and
    # only emits deterministic, stack-independent Kustomize manifests below.
    result["actions"].append(
        {
            "path": "infra/k8s",
            "key": "stack.delegated",
            "severity": "info",
            "message": (
                "Dockerfile/nginx.conf/.dockerignore generation delegated to the "
                "dev-flow-scaffold-project skill — the AI resolves what to scaffold "
                "from the selected stack (no fixed template list)."
            ),
            "phase": "apply",
        }
    )

    # ── Generate Kustomize base manifests (one Deployment + Service per app) ──
    base_dir = k8s_dir / "base"
    base_dir.mkdir(parents=True, exist_ok=True)
    base_resources = []

    for app in apps:
        app_id = app["appId"]
        role = app.get("role", "web")
        port = _port_for_role(role)
        health_path = "/health"  # Always use /health — nginx.conf has it for web, api apps must implement it

        # Deployment YAML
        dep_file = f"{app_id}-deployment.yaml"
        dep_path = base_dir / dep_file
        if not dep_path.exists():
            dep_yaml = (
                "apiVersion: apps/v1\n"
                "kind: Deployment\n"
                "metadata:\n"
                f"  name: {app_id}\n"
                "spec:\n"
                "  replicas: 1\n"
                "  selector:\n"
                "    matchLabels:\n"
                f"      app: {app_id}\n"
                "  template:\n"
                "    metadata:\n"
                "      labels:\n"
                f"        app: {app_id}\n"
                "    spec:\n"
                "      containers:\n"
                f"        - name: {app_id}\n"
                f"          image: host.docker.internal:5001/{app_id}\n"
                "          imagePullPolicy: IfNotPresent\n"
                "          ports:\n"
                f"            - containerPort: {port}\n"
            )
            # Stack-independent PORT env for api-role apps — the AI scaffold
            # skill generates the Dockerfile that consumes it (ASPNETCORE_URLS,
            # uvicorn port, etc.). The script never assumes a runtime.
            if role == "api":
                dep_yaml += (
                    "          env:\n"
                    '            - name: PORT\n'
                    f'              value: "{port}"\n'
                )
            dep_yaml += (
                "          livenessProbe:\n"
                "            httpGet:\n"
                f"              path: {health_path}\n"
                f"              port: {port}\n"
                "            initialDelaySeconds: 10\n"
                "            periodSeconds: 30\n"
                "          readinessProbe:\n"
                "            httpGet:\n"
                f"              path: {health_path}\n"
                f"              port: {port}\n"
                "            initialDelaySeconds: 5\n"
                "            periodSeconds: 10\n"
                "          resources:\n"
                "            requests:\n"
                '              cpu: "100m"\n'
                '              memory: "128Mi"\n'
                "            limits:\n"
                '              cpu: "500m"\n'
                '              memory: "256Mi"\n'
            )
            dep_path.write_text(dep_yaml, encoding="utf-8")
            result["actions"].append(
                {
                    "path": f"infra/k8s/base/{dep_file}",
                    "key": "file.created",
                    "severity": "info",
                    "message": f"Created K8s Deployment for {app_id} (role={role}, port={port}).",
                    "phase": "apply",
                }
            )
        else:
            result["actions"].append(
                {
                    "path": f"infra/k8s/base/{dep_file}",
                    "key": "file.exists",
                    "severity": "info",
                    "message": f"Deployment YAML already exists for {app_id}.",
                    "phase": "audit",
                }
            )

        # Service YAML
        svc_file = f"{app_id}-service.yaml"
        svc_path = base_dir / svc_file
        if not svc_path.exists():
            node_port = _node_port_for_role(role)
            svc_yaml = (
                "apiVersion: v1\n"
                "kind: Service\n"
                "metadata:\n"
                f"  name: {app_id}\n"
                "spec:\n"
                "  type: NodePort\n"
                "  selector:\n"
                f"    app: {app_id}\n"
                "  ports:\n"
                "    - protocol: TCP\n"
                f"      port: {port}\n"
                f"      targetPort: {port}\n"
                f"      nodePort: {node_port}\n"
            )
            svc_path.write_text(svc_yaml, encoding="utf-8")
            result["actions"].append(
                {
                    "path": f"infra/k8s/base/{svc_file}",
                    "key": "file.created",
                    "severity": "info",
                    "message": f"Created K8s Service for {app_id} (LoadBalancer, port {port}).",
                    "phase": "apply",
                }
            )
        else:
            result["actions"].append(
                {
                    "path": f"infra/k8s/base/{svc_file}",
                    "key": "file.exists",
                    "severity": "info",
                    "message": f"Service YAML already exists for {app_id}.",
                    "phase": "audit",
                }
            )

        base_resources.append(f"  - {dep_file}")
        base_resources.append(f"  - {svc_file}")

    # Base kustomization.yaml
    base_kustomization = base_dir / "kustomization.yaml"
    if not base_kustomization.exists():
        kustomize_yaml = (
            "apiVersion: kustomize.config.k8s.io/v1beta1\n"
            "kind: Kustomization\n"
            "resources:\n"
            + "\n".join(base_resources)
            + "\n"
            "commonLabels:\n"
            "  app.kubernetes.io/managed-by: sdd-cli\n"
        )
        base_kustomization.write_text(kustomize_yaml, encoding="utf-8")
        app_names = ", ".join(a["appId"] for a in apps)
        result["actions"].append(
            {
                "path": "infra/k8s/base/kustomization.yaml",
                "key": "file.created",
                "severity": "info",
                "message": f"Created base kustomization.yaml with {len(apps)} app(s): {app_names}.",
                "phase": "apply",
            }
        )
    else:
        result["actions"].append(
            {
                "path": "infra/k8s/base/kustomization.yaml",
                "key": "file.exists",
                "severity": "info",
                "message": "Base kustomization.yaml already exists — add new apps manually if needed.",
                "phase": "audit",
            }
        )

    # ── Generate environment overlays (dev, qa, prod) ──
    registry = "host.docker.internal:5001"
    for env_name in ("dev", "qa", "prod"):
        overlay_dir = k8s_dir / "overlays" / env_name
        overlay_dir.mkdir(parents=True, exist_ok=True)

        overlay_file = overlay_dir / "kustomization.yaml"
        if not overlay_file.exists():
            image_entries = []
            for app in apps:
                app_id = app["appId"]
                image_entries.append(
                    f"  - name: {registry}/{app_id}\n"
                    "    newTag: latest\n"
                )

            overlay_yaml = (
                "apiVersion: kustomize.config.k8s.io/v1beta1\n"
                "kind: Kustomization\n"
                f"namespace: sdd-{env_name}\n"
                "resources:\n"
                "  - ../../base\n"
                "images:\n"
                + "".join(image_entries)
            )
            overlay_file.write_text(overlay_yaml, encoding="utf-8")
            count = len(apps)
            label = "entry" if count == 1 else "entries"
            result["actions"].append(
                {
                    "path": f"infra/k8s/overlays/{env_name}/kustomization.yaml",
                    "key": "file.created",
                    "severity": "info",
                    "message": f"Created {env_name} overlay kustomization.yaml with {count} app image {label}.",
                    "phase": "apply",
                }
            )
        else:
            result["actions"].append(
                {
                    "path": f"infra/k8s/overlays/{env_name}/kustomization.yaml",
                    "key": "file.exists",
                    "severity": "info",
                    "message": f"{env_name} overlay already exists.",
                    "phase": "audit",
                }
            )

    result["valid"] = not any(
        item.get("severity") == "error" for item in result["findings"]
    )
    return result  # ── kind cluster setup ────────────────────────────────────────────────


def setup_kind_cluster(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Create a kind cluster with extraPortMappings for direct host access.

    Uses infra/k8s/kind-config.yaml which defines fixed nodePort → host port mappings:
      host:8081 → nodePort:30080 → frontend:80
      host:5002 → nodePort:30500 → backend:5000

    This replaces Docker Desktop K8s — kind runs as a Docker container, avoids
    Docker Engine restart, and requires no Docker Desktop Kubernetes toggle.

    Steps:
    1. Install kind if not present (Windows/macOS/Linux)
    2. Create kind cluster 'sdd-cluster' with infra/k8s/kind-config.yaml
    3. Save kubeconfig for CI access (replace 127.0.0.1 with host.docker.internal)
    4. Connect to Docker networks for CI access
    """
    result = configure_result(
        "SetupKindCluster", dry_run, write_enabled=not dry_run
    )

    if dry_run:
        result["actions"].append(
            {
                "path": "kind",
                "key": "cluster.create",
                "severity": "info",
                "message": "Would create kind cluster 'sdd-cluster' with extraPortMappings (8081→frontend, 5002→backend).",
                "phase": "apply",
            }
        )
        result["valid"] = True
        return result

    # ── 1. Check if kubectl is already connected to a cluster ──
    kubectl_check = run_native(["kubectl", "version", "--output=json"], root, timeout=15)
    if kubectl_check["returncode"] == 0:
        try:
            k8s_info = json.loads(kubectl_check["stdout"])
            server = k8s_info.get("serverVersion", {})
            git_version = server.get("gitVersion", "unknown")

            # Check if it's a kind cluster
            current_ctx = run_native(
                ["kubectl", "config", "current-context"], root, timeout=5
            )
            ctx_name = current_ctx["stdout"].strip() if current_ctx["returncode"] == 0 else "unknown"

            result["actions"].append(
                {
                    "path": "kubectl",
                    "key": "cluster.ready",
                    "severity": "info",
                    "message": f"K8s cluster is already reachable (context={ctx_name}, v{git_version}).",
                    "phase": "audit",
                }
            )
            cluster_exists = True
        except (json.JSONDecodeError, KeyError):
            cluster_exists = False
    else:
        cluster_exists = False

    if not cluster_exists:
        # ── 2. Ensure kind is installed ──
        kind_check = run_native(["kind", "version"], root, timeout=10)
        if kind_check["returncode"] != 0:
            import platform

            pf = platform.system().lower()
            result["actions"].append(
                {
                    "path": "kind",
                    "key": "binary.install",
                    "severity": "info",
                    "message": "kind not found — installing v0.32.0...",
                    "phase": "apply",
                }
            )
            if pf == "windows":
                install_cmd = [
                    "winget", "install", "Kubernetes.kind", "--accept-package-agreements"
                ]
                install = run_native(install_cmd, root, timeout=120)
                if install["returncode"] != 0:
                    add_bucket_item(
                        result["findings"],
                        "kind",
                        "install.failed",
                        "Could not install kind via winget. Download manually from https://kind.sigs.k8s.io/docs/user/quick-start/",
                        "error",
                        "pre-start",
                    )
                    result["valid"] = False
                    return result
            elif pf == "darwin":
                run_native(["brew", "install", "kind"], root, timeout=120)
            else:
                # Linux — direct download
                kind_url = (
                    "https://kind.sigs.k8s.io/dl/v0.32.0/kind-linux-amd64"
                )
                run_native(
                    [
                        "curl", "-fsSL", "-o", "/usr/local/bin/kind", kind_url,
                        "&&", "chmod", "+x", "/usr/local/bin/kind",
                    ],
                    root,
                    timeout=60,
                )

        # Verify kind is now available
        kind_check2 = run_native(["kind", "version"], root, timeout=10)
        if kind_check2["returncode"] != 0:
            add_bucket_item(
                result["findings"],
                "kind",
                "not.found",
                "kind is still not available after install attempt. Install manually: https://kind.sigs.k8s.io/docs/user/quick-start/",
                "error",
                "pre-start",
            )
            result["valid"] = False
            return result
        else:
            result["actions"].append(
                {
                    "path": "kind",
                    "key": "binary.installed",
                    "severity": "info",
                    "message": f"kind is available: {kind_check2['stdout'].strip()}.",
                    "phase": "audit",
                }
            )

        # ── 3. Check if sdd-cluster already exists ──
        clusters = run_native(["kind", "get", "clusters"], root, timeout=15)
        if clusters["returncode"] == 0 and "sdd-cluster" in clusters["stdout"]:
            result["actions"].append(
                {
                    "path": "kind/sdd-cluster",
                    "key": "cluster.exists",
                    "severity": "info",
                    "message": "Cluster 'sdd-cluster' already exists. Skipping creation.",
                    "phase": "audit",
                }
            )
        else:
            # ── 4. Create kind cluster with extraPortMappings ──
            kind_config = root / "infra" / "k8s" / "kind-config.yaml"
            if not kind_config.exists():
                add_bucket_item(
                    result["findings"],
                    "infra/k8s/kind-config.yaml",
                    "missing",
                    "kind-config.yaml not found — run scaffold-k8s first or create it manually.",
                    "error",
                    "pre-start",
                )
                result["valid"] = False
                return result

            result["actions"].append(
                {
                    "path": "kind/sdd-cluster",
                    "key": "cluster.create",
                    "severity": "info",
                    "message": "Creating kind cluster 'sdd-cluster' with extraPortMappings...",
                    "phase": "apply",
                }
            )
            create = run_native(
                ["kind", "create", "cluster", "--name", "sdd-cluster", "--config", str(kind_config)],
                root,
                timeout=300,
            )
            if create["returncode"] != 0:
                add_bucket_item(
                    result["findings"],
                    "kind/sdd-cluster",
                    "create.failed",
                    f"kind create cluster failed: {create['stderr']}",
                    "error",
                    "apply",
                )
                result["valid"] = False
                return result

            result["actions"].append(
                {
                    "path": "kind/sdd-cluster",
                    "key": "cluster.created",
                    "severity": "info",
                    "message": "kind cluster 'sdd-cluster' created successfully.",
                    "phase": "apply",
                }
            )

        # ── 5. Save kubeconfig for CI access ──
        # Get kubeconfig
        kc_get = run_native(
            ["kind", "get", "kubeconfig", "--name", "sdd-cluster"], root, timeout=15
        )
        if kc_get["returncode"] == 0 and kc_get["stdout"]:
            kc_data = kc_get["stdout"]

            # Replace 127.0.0.1:<port> with host.docker.internal:<port> for CI container access
            # Use YAML-safe approach: replace server address and strip CA data
            kc_lines = kc_data.splitlines()
            kc_ci_lines = []
            skip_ca = False
            for line in kc_lines:
                stripped = line.strip()
                if "127.0.0.1" in line and "server:" in line:
                    kc_ci_lines.append("    server: https://host.docker.internal:6443")
                elif "certificate-authority-data:" in stripped:
                    kc_ci_lines.append("    insecure-skip-tls-verify: true")
                    skip_ca = True
                elif skip_ca and (stripped.startswith("-") or "client-" in stripped or "user:" in stripped or stripped == "" or not stripped):
                    skip_ca = False
                    kc_ci_lines.append(line)
                elif skip_ca and stripped and not stripped.startswith("#"):
                    # Skip CA data lines (PEM content)
                    continue
                else:
                    kc_ci_lines.append(line)
            kc_ci = "\n".join(kc_ci_lines)

            # Write CI kubeconfig
            kc_path = root / "infra" / "k8s" / "kind-kubeconfig-ci.yaml"
            if not dry_run:
                kc_path.write_text(kc_ci, encoding="utf-8")
                result["actions"].append(
                    {
                        "path": "infra/k8s/kind-kubeconfig-ci.yaml",
                        "key": "kubeconfig.written",
                        "severity": "info",
                        "message": "Saved CI kubeconfig (host.docker.internal endpoint, insecure-skip-tls-verify).",
                        "phase": "apply",
                    }
                )

            # Merge into default kubeconfig for local access
            merge = run_native(
                ["kind", "export", "kubeconfig", "--name", "sdd-cluster"],
                root,
                timeout=15,
            )
            if merge["returncode"] == 0:
                result["actions"].append(
                    {
                        "path": "~/.kube/config",
                        "key": "kubeconfig.merged",
                        "severity": "info",
                        "message": "Merged kind kubeconfig into ~/.kube/config.",
                        "phase": "apply",
                    }
                )

    # ── 6. Connect to Docker networks for CI access and Grafana monitoring ──
    # Grafana's Infinity datasource queries kind nodePorts directly using
    # Docker DNS (sdd-cluster-control-plane:<nodePort>). Without this network
    # connection, Grafana can't reach kind's kube-proxy iptables rules.
    #
    # The CI runner containers also need access to Gitea and Nexus via
    # host.docker.internal or Docker DNS.
    for network in ("agentic-e2e_gitea", "agentic-e2e_nexus", "agentic-e2e_monitoring"):
        connect = run_native(
            ["docker", "network", "connect", network, "sdd-cluster-control-plane"],
            root,
            timeout=15,
        )
        if connect["returncode"] == 0:
            result["actions"].append(
                {
                    "path": f"docker/{network}",
                    "key": "network.connected",
                    "severity": "info",
                    "message": f"Connected sdd-cluster-control-plane to {network}.",
                    "phase": "apply",
                }
            )
        # Non-fatal if network doesn't exist yet

    # ── 7. Connect Grafana to the kind network (so dashboard DNS names resolve) ──
    # The Grafana Health Check Board uses sdd-cluster-control-plane:<nodePort> URLs.
    # These resolve via Docker DNS when Grafana is on the same network as the kind node.
    # The compose.yml only attaches to 'monitoring' network, so we add 'kind' network
    # at runtime. This is idempotent — 'already connected' is a non-error.
    grafana_connect = run_native(
        ["docker", "network", "connect", "kind", "agentic-grafana"],
        root,
        timeout=15,
    )
    if grafana_connect["returncode"] == 0:
        result["actions"].append(
            {
                "path": "docker/kind",
                "key": "grafana.network_connected",
                "severity": "info",
                "message": "Connected agentic-grafana to kind network for health check queries.",
                "phase": "apply",
            }
        )
    else:
        output_lower = (grafana_connect.get("stdout", "") + grafana_connect.get("stderr", "")).lower()
        if "already" in output_lower:
            result["actions"].append(
                {
                    "path": "docker/kind",
                    "key": "grafana.network_already_connected",
                    "severity": "info",
                    "message": "Grafana is already connected to kind network.",
                    "phase": "audit",
                }
            )
        else:
            add_bucket_item(
                result["findings"],
                "docker/kind",
                "grafana.network_connect_failed",
                f"Could not connect Grafana to kind network: {grafana_connect.get('stderr', '')[:200]}",
                "warning",
                "apply",
            )

    result["valid"] = not any(
        item.get("severity") == "error" for item in result["findings"]
    )
    return result
    if kind_check["returncode"] != 0:
        import platform

        pf = platform.system().lower()
        result["actions"].append(
            {
                "path": "kind",
                "key": "binary.install",
                "severity": "info",
                "message": "kind not found — installing v0.32.0...",
                "phase": "apply",
            }
        )
        if pf == "windows":
            install_cmd = [
                "winget", "install", "Kubernetes.kind", "--accept-package-agreements"
            ]
            install = run_native(install_cmd, root, timeout=120)
            if install["returncode"] != 0:
                add_bucket_item(
                    result["findings"],
                    "kind",
                    "install.failed",
                    "Could not install kind via winget. Download manually from https://kind.sigs.k8s.io/docs/user/quick-start/",
                    "error",
                    "pre-start",
                )
                result["valid"] = False
                return result
        elif pf == "darwin":
            run_native(["brew", "install", "kind"], root, timeout=120)
        else:
            # Linux — direct download
            kind_url = (
                "https://kind.sigs.k8s.io/dl/v0.32.0/kind-linux-amd64"
            )
            run_native(
                [
                    "curl", "-fsSL", "-o", "/usr/local/bin/kind", kind_url,
                    "&&", "chmod", "+x", "/usr/local/bin/kind",
                ],
                root,
                timeout=60,
            )

    # Verify kind is now available
    kind_check2 = run_native(["kind", "version"], root, timeout=10)
    if kind_check2["returncode"] != 0:
        add_bucket_item(
            result["findings"],
            "kind",
            "not.found",
            "kind is still not available after install attempt. Install manually: https://kind.sigs.k8s.io/docs/user/quick-start/",
            "error",
            "pre-start",
        )
        result["valid"] = False
        return result
    else:
        result["actions"].append(
            {
                "path": "kind",
                "key": "binary.installed",
                "severity": "info",
                "message": f"kind is available: {kind_check2['stdout'].strip()}.",
                "phase": "audit",
            }
        )

    # ── 3. Check if sdd-cluster already exists ──
    clusters = run_native(["kind", "get", "clusters"], root, timeout=15)
    if clusters["returncode"] == 0 and "sdd-cluster" in clusters["stdout"]:
        result["actions"].append(
            {
                "path": "kind/sdd-cluster",
                "key": "cluster.exists",
                "severity": "info",
                "message": "Cluster 'sdd-cluster' already exists. Skipping creation.",
                "phase": "audit",
            }
        )
    else:
        # ── 4. Create kind cluster with extraPortMappings ──
        kind_config = root / "infra" / "k8s" / "kind-config.yaml"
        if not kind_config.exists():
            add_bucket_item(
                result["findings"],
                "infra/k8s/kind-config.yaml",
                "missing",
                "kind-config.yaml not found — run scaffold-k8s first or create it manually.",
                "error",
                "pre-start",
            )
            result["valid"] = False
            return result

        result["actions"].append(
            {
                "path": "kind/sdd-cluster",
                "key": "cluster.create",
                "severity": "info",
                "message": "Creating kind cluster 'sdd-cluster' with extraPortMappings...",
                "phase": "apply",
            }
        )
        create = run_native(
            ["kind", "create", "cluster", "--name", "sdd-cluster", "--config", str(kind_config)],
            root,
            timeout=300,
        )
        if create["returncode"] != 0:
            add_bucket_item(
                result["findings"],
                "kind/sdd-cluster",
                "create.failed",
                f"kind create cluster failed: {create['stderr']}",
                "error",
                "apply",
            )
            result["valid"] = False
            return result

        result["actions"].append(
            {
                "path": "kind/sdd-cluster",
                "key": "cluster.created",
                "severity": "info",
                "message": "kind cluster 'sdd-cluster' created successfully.",
                "phase": "apply",
            }
        )

    # ── 5. Save kubeconfig for CI access ──
    # Get kubeconfig
    kc_get = run_native(
        ["kind", "get", "kubeconfig", "--name", "sdd-cluster"], root, timeout=15
    )
    if kc_get["returncode"] == 0 and kc_get["stdout"]:
        kc_data = kc_get["stdout"]

        # Replace 127.0.0.1:<port> with host.docker.internal:<port> for CI container access
        # Use YAML-safe approach: replace server address and strip CA data
        kc_lines = kc_data.splitlines()
        kc_ci_lines = []
        skip_ca = False
        for line in kc_lines:
            stripped = line.strip()
            if "127.0.0.1" in line and "server:" in line:
                kc_ci_lines.append("    server: https://host.docker.internal:6443")
            elif "certificate-authority-data:" in stripped:
                kc_ci_lines.append("    insecure-skip-tls-verify: true")
                skip_ca = True
            elif skip_ca and (stripped.startswith("-") or "client-" in stripped or "user:" in stripped or stripped == "" or not stripped):
                skip_ca = False
                kc_ci_lines.append(line)
            elif skip_ca and stripped and not stripped.startswith("#"):
                # Skip CA data lines (PEM content)
                continue
            else:
                kc_ci_lines.append(line)
        kc_ci = "\n".join(kc_ci_lines)

        # Write CI kubeconfig
        kc_path = root / "infra" / "k8s" / "kind-kubeconfig-ci.yaml"
        if not dry_run:
            kc_path.write_text(kc_ci, encoding="utf-8")
            result["actions"].append(
                {
                    "path": "infra/k8s/kind-kubeconfig-ci.yaml",
                    "key": "kubeconfig.written",
                    "severity": "info",
                    "message": "Saved CI kubeconfig (host.docker.internal endpoint, insecure-skip-tls-verify).",
                    "phase": "apply",
                }
            )

        # Merge into default kubeconfig for local access
        merge = run_native(
            ["kind", "export", "kubeconfig", "--name", "sdd-cluster"],
            root,
            timeout=15,
        )
        if merge["returncode"] == 0:
            result["actions"].append(
                {
                    "path": "~/.kube/config",
                    "key": "kubeconfig.merged",
                    "severity": "info",
                    "message": "Merged kind kubeconfig into ~/.kube/config.",
                    "phase": "apply",
                }
            )

    # ── 6. Connect to Docker networks for CI access ──
    for network in ("agentic-e2e_gitea", "agentic-e2e_nexus"):
        connect = run_native(
            ["docker", "network", "connect", network, "sdd-cluster-control-plane"],
            root,
            timeout=15,
        )
        if connect["returncode"] == 0:
            result["actions"].append(
                {
                    "path": f"docker/{network}",
                    "key": "network.connected",
                    "severity": "info",
                    "message": f"Connected sdd-cluster-control-plane to {network}.",
                    "phase": "apply",
                }
            )
        # Non-fatal if network doesn't exist yet

    result["valid"] = not any(
        item.get("severity") == "error" for item in result["findings"]
    )
    return result


# ── Docker Desktop K8s enablement (legacy fallback) ─────────────────────


def enable_docker_desktop_k8s(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Enable Kubernetes in Docker Desktop if not already running.

    Checks if K8s is already accessible via kubectl. If not, looks at the
    Docker Desktop settings.json to see if K8s is disabled in config, and
    if so, enables it programmatically. If Docker Desktop needs a restart
    to pick up the change, warns the user.

    This runs BEFORE compose_up() so that any Docker restart happens before
    our containers start, not after.
    """
    result = configure_result(
        "EnableDockerDesktopK8s", dry_run, write_enabled=not dry_run
    )
    if dry_run:
        result["actions"].append(
            {
                "path": "docker-desktop",
                "key": "k8s.enable",
                "severity": "info",
                "message": "Would check K8s status and enable if needed.",
                "phase": "audit",
            }
        )
        result["valid"] = True
        return result

    # ── 1. Check if K8s is already accessible ──
    kubectl = run_native(["kubectl", "version", "--output=json"], root, timeout=15)
    if kubectl["returncode"] == 0:
        try:
            k8s_info = json.loads(kubectl["stdout"])
            server = k8s_info.get("serverVersion", {})
            git_version = server.get("gitVersion", "unknown")
            result["actions"].append(
                {
                    "path": "docker-desktop",
                    "key": "k8s.enable",
                    "severity": "info",
                    "message": f"Kubernetes is already running (v{git_version}).",
                    "phase": "audit",
                }
            )
            result["valid"] = True
            return result
        except (json.JSONDecodeError, KeyError):
            pass

    # ── 2. Not running — check Docker Desktop settings ──
    # On Windows, settings are in one of several possible locations:
    #   %APPDATA%\Docker\settings-store.json  (Docker Desktop 4.37+)
    #   %APPDATA%\Docker\settings.json        (Docker Desktop 4.34 and earlier)
    # The key can be either:
    #   "kubernetes": {"enabled": true}       (nested, newer format)
    #   "kubernetesEnabled": true             (flat, older format)
    settings_path = None
    import platform

    if sys.platform == "win32" or platform.system() == "Windows":
        base_dirs = [
            Path(os.environ.get("APPDATA", "")),
            Path.home() / "AppData" / "Roaming",
            Path(os.environ.get("LOCALAPPDATA", "")),
            Path(os.environ.get("PROGRAMDATA", "")),
        ]
        # Try settings-store.json first (newer), then settings.json (older)
        for settings_name in ("settings-store.json", "settings.json"):
            for base in base_dirs:
                candidate = base / "Docker" / settings_name
                if candidate.exists():
                    settings_path = candidate
                    break
            if settings_path:
                break

    if settings_path is None or not settings_path.exists():
        add_bucket_item(
            result["findings"],
            "docker-desktop",
            "k8s.enable",
            "Docker Desktop settings file not found — cannot auto-enable K8s. "
            "Enable Kubernetes manually in Docker Desktop Settings → Kubernetes → Enable Kubernetes, "
            "then re-run setup-lab.",
            "error",
            "pre-start",
        )
        result["valid"] = False  # K8s is required
        return result

    # ── 3. Read settings file to check K8s state ──
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as ex:
        add_bucket_item(
            result["findings"],
            str(settings_path),
            "k8s.enable",
            f"Could not parse Docker Desktop settings: {ex}. "
            "Enable Kubernetes manually in Docker Desktop Settings.",
            "error",
            "pre-start",
        )
        result["valid"] = False
        return result

    # Read K8s state: try nested "kubernetes.enabled" (newer) then flat "KubernetesEnabled" (older)
    k8s_section = settings.get("kubernetes", {})
    if isinstance(k8s_section, dict):
        k8s_enabled = k8s_section.get("enabled", False)
    else:
        k8s_enabled = False
    if not k8s_enabled:
        k8s_enabled = settings.get("KubernetesEnabled", False)

    if k8s_enabled:
        # K8s is enabled in settings but kubectl is not responding — Docker Desktop
        # may need a restart to recover the cluster. Fall through to the restart
        # logic instead of erroring out.
        result["actions"].append(
            {
                "path": "docker-desktop",
                "key": "k8s.restart",
                "severity": "info",
                "message": "K8s is enabled in settings but not responding. Restarting Docker Desktop to recover cluster...",
                "phase": "apply",
            }
        )

    # ── 4. Enable K8s in settings file ──
    # Write both formats for backward compatibility
    settings["KubernetesEnabled"] = True
    if "kubernetes" not in settings or not isinstance(settings["kubernetes"], dict):
        settings["kubernetes"] = {}
    settings["kubernetes"]["enabled"] = True
    try:
        settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        result["actions"].append(
            {
                "path": str(settings_path),
                "key": "k8s.enable",
                "severity": "info",
                "message": "Set kubernetes.enabled=true in Docker Desktop settings.",
                "phase": "apply",
            }
        )
    except OSError as ex:
        add_bucket_item(
            result["findings"],
            str(settings_path),
            "k8s.enable",
            f"Could not write Docker Desktop settings: {ex}. "
            "Enable Kubernetes manually in Docker Desktop Settings → Kubernetes → Enable Kubernetes, "
            "then re-run setup-lab.",
            "error",
            "pre-start",
        )
        result["valid"] = False
        return result

    # ── 5. Restart Docker Desktop to pick up K8s enablement ──
    # Use `docker desktop stop` / `docker desktop start` CLI (Docker Desktop 4.37+)
    # Falls back to killing the process if CLI is not available
    result["actions"].append(
        {
            "path": "docker",
            "key": "k8s.restart",
            "severity": "info",
            "message": "Stopping Docker Desktop to enable K8s...",
            "phase": "apply",
        }
    )
    # Try docker desktop CLI first (Docker Desktop 4.37+), fallback to taskkill
    stop_cmd = run_native(["docker", "desktop", "stop"], root, timeout=30)
    if stop_cmd["returncode"] != 0:
        # Fallback: taskkill
        taskkill = run_native(
            ["taskkill", "/F", "/IM", "Docker Desktop.exe"], root, timeout=15
        )
        if taskkill["returncode"] != 0:
            add_bucket_item(
                result["findings"],
                "docker-desktop",
                "k8s.restart",
                "Could not stop Docker Desktop. Close it manually (right-click tray icon → Quit), "
                "then re-run setup-lab.",
                "error",
                "pre-start",
            )
            result["valid"] = False
            return result
    # Wait for Docker process to fully exit
    time.sleep(5)

    # Start Docker Desktop via CLI
    result["actions"].append(
        {
            "path": "docker",
            "key": "k8s.restart",
            "severity": "info",
            "message": "Starting Docker Desktop (K8s enabled)...",
            "phase": "apply",
        }
    )
    start_cmd = run_native(["docker", "desktop", "start"], root, timeout=30)
    if start_cmd["returncode"] != 0:
        # Fallback: try launching Docker Desktop executable directly
        dd_exe = shutil.which("docker")
        if dd_exe:
            dd_exe_path = Path(dd_exe).parent.parent / "Docker Desktop.exe"
        else:
            dd_exe_path = Path("C:/Program Files/Docker/Docker/Docker Desktop.exe")
        if dd_exe_path.exists():
            subprocess.Popen(
                [str(dd_exe_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.DETACHED_PROCESS if sys.platform == "win32" else 0,
            )
        else:
            add_bucket_item(
                result["findings"],
                "docker-desktop",
                "k8s.restart",
                "Could not start Docker Desktop. Start it manually from the Start Menu, "
                "then re-run setup-lab.",
                "error",
                "pre-start",
            )
            result["valid"] = False
            return result
    time.sleep(5)

    # ── 6. Wait for Docker daemon to be ready (up to 120s) ──
    result["actions"].append(
        {
            "path": "docker",
            "key": "k8s.restart",
            "severity": "info",
            "message": "Waiting for Docker daemon to start (up to 120s)...",
            "phase": "apply",
        }
    )
    daemon_ready = False
    for _attempt in range(24):  # 24 * 5 = 120 seconds
        time.sleep(5)
        check = run_native(
            ["docker", "info", "--format", "{{.ServerVersion}}"], root, timeout=10
        )
        if check["returncode"] == 0 and check["stdout"].strip():
            daemon_ready = True
            break
    if not daemon_ready:
        add_bucket_item(
            result["findings"],
            "docker",
            "k8s.restart",
            "Docker daemon did not become ready within 120s after restart. "
            "Check Docker Desktop manually, wait for it to finish starting, then re-run setup-lab.",
            "error",
            "pre-start",
        )
        result["valid"] = False
        return result

    # ── 7. Wait for K8s to be ready (up to 180s) ──
    result["actions"].append(
        {
            "path": "docker",
            "key": "k8s.restart",
            "severity": "info",
            "message": f"Docker daemon ready (v{check['stdout'].strip()}). Waiting for K8s cluster (up to 180s)...",
            "phase": "apply",
        }
    )

    k8s_ready = False
    git_version = "unknown"
    for _attempt in range(18):  # 18 * 10 = 180 seconds
        time.sleep(10)
        k_check = run_native(["kubectl", "version", "--output=json"], root, timeout=10)
        if k_check["returncode"] == 0:
            try:
                k8s_info = json.loads(k_check["stdout"])
                server = k8s_info.get("serverVersion", {})
                git_version = server.get("gitVersion", "unknown")
                k8s_ready = True
                break
            except (json.JSONDecodeError, KeyError):
                pass

    if not k8s_ready:
        add_bucket_item(
            result["findings"],
            "docker-desktop",
            "k8s.restart",
            "Kubernetes did not become ready within 180s after Docker Desktop restart. "
            "Wait for the K8s cluster to finish initializing in Docker Desktop, then re-run setup-lab.",
            "error",
            "pre-start",
        )
        result["valid"] = False
        return result

    result["actions"].append(
        {
            "path": "docker-desktop",
            "key": "k8s.enable",
            "severity": "info",
            "message": f"Kubernetes is now running (v{git_version}).",
            "phase": "apply",
        }
    )

    # Also update the K8s context to docker-desktop
    run_native(["kubectl", "config", "use-context", "docker-desktop"], root, timeout=10)

    result["valid"] = True
    return result


# ── Docker Desktop K8s validation ────────────────────────────────────────


def validate_docker_desktop_k8s(root, dry_run=False):
    """Check if Docker Desktop K8s is enabled and accessible."""
    result = configure_result("ValidateDockerDesktopK8s", dry_run, write_enabled=False)

    if dry_run:
        result["actions"].append(
            {
                "path": "docker-desktop",
                "key": "k8s.validate",
                "severity": "info",
                "message": "Would check if Docker Desktop K8s is enabled.",
                "phase": "audit",
            }
        )
        result["valid"] = True
        return result

    # Check kubectl
    kubectl = run_native(["kubectl", "version", "--output=json"], root, timeout=15)
    if kubectl["returncode"] != 0:
        add_bucket_item(
            result["findings"],
            "kubectl",
            "missing",
            "kubectl not found or not working. Enable K8s in Docker Desktop Settings.",
            "error",
            "pre-start",
        )
        result["valid"] = False
        return result

    # Try to parse server version
    try:
        k8s_info = json.loads(kubectl["stdout"])
        server = k8s_info.get("serverVersion", {})
        git_version = server.get("gitVersion", "unknown")
        result["actions"].append(
            {
                "path": "docker-desktop",
                "key": "k8s.server",
                "severity": "info",
                "message": f"Docker Desktop K8s is running (v{git_version}).",
                "phase": "audit",
            }
        )
    except (json.JSONDecodeError, KeyError):
        result["actions"].append(
            {
                "path": "docker-desktop",
                "key": "k8s.server",
                "severity": "info",
                "message": "Docker Desktop K8s is running (version unknown).",
                "phase": "audit",
            }
        )

    # Check cluster info
    cluster = run_native(
        ["kubectl", "cluster-info", "--request-timeout=5s"], root, timeout=10
    )
    if cluster["returncode"] != 0:
        add_bucket_item(
            result["findings"],
            "k8s",
            "cluster.unreachable",
            "K8s cluster is not reachable via kubectl.",
            "error",
            "post-start",
        )
        result["valid"] = False
        return result

    # Check if this is Docker Desktop (check context name)
    ctx = run_native(["kubectl", "config", "current-context"], root, timeout=5)
    context_name = ctx["stdout"].strip() if ctx["returncode"] == 0 else "unknown"
    if "docker" in context_name.lower() or "desktop" in context_name.lower():
        result["actions"].append(
            {
                "path": "k8s",
                "key": "context",
                "severity": "info",
                "message": f"K8s context is '{context_name}' (Docker Desktop).",
                "phase": "audit",
            }
        )
    else:
        add_bucket_item(
            result["findings"],
            "k8s",
            "context.warning",
            f"K8s context is '{context_name}' - expected Docker Desktop context.",
            "warning",
            "audit",
        )

    result["valid"] = not any(
        item.get("severity") == "error" for item in result["findings"]
    )
    return result


# ── K8s access setup (port-forward) ─────────────────────────────────────


def setup_k8s_access(root, dry_run=False):
    """Discover deployed app URLs via kind extraPortMappings (no kubectl port-forward needed).

    The kind cluster is configured with extraPortMappings in infra/k8s/kind-config.yaml:
      host:8081 → kind-node:30080 → frontend:80
      host:5002 → kind-node:30500 → backend:5000

    These mappings make services directly accessible at localhost without port-forward.
    """
    result = configure_result("SetupK8sAccess", dry_run, write_enabled=not dry_run)
    apps_path = root / "infra" / "deployment" / "apps.json"

    if not apps_path.exists():
        add_bucket_item(
            result["findings"],
            "infra/deployment/apps.json",
            "missing",
            "apps.json not found.",
            "error",
            "pre-start",
        )
        result["valid"] = False
        return result

    try:
        apps_data = read_json(apps_path, optional=False)
        apps = apps_data.get("apps", [])
    except Exception as ex:
        add_bucket_item(
            result["findings"],
            "infra/deployment/apps.json",
            "read_error",
            f"Could not parse: {ex}",
            "error",
            "pre-start",
        )
        result["valid"] = False
        return result

    if not apps:
        add_bucket_item(
            result["findings"],
            "infra/deployment/apps.json",
            "no_apps",
            "No apps defined.",
            "warning",
            "pre-start",
        )
        result["valid"] = True
        return result

    # Map app roles to their kind extraPortMapping host ports (defined in kind-config.yaml)
    # Role-based defaults: web→8081, api→5002
    _HOST_PORT_MAP: dict[str, int] = {
        "frontend": 8081,
        "backend": 5002,
    }

    if dry_run:
        for app in apps:
            result["actions"].append(
                {
                    "path": f"k8s/url/{app['appId']}",
                    "key": "url.discover",
                    "severity": "info",
                    "message": f"Would discover URL for {app['appId']} via extraPortMapping.",
                    "phase": "apply",
                }
            )
        result["valid"] = True
        return result

    # Validate K8s first
    k8s_valid = run_native(["kubectl", "version", "--output=json"], root, timeout=15)
    if k8s_valid["returncode"] != 0:
        add_bucket_item(
            result["findings"],
            "kubectl",
            "missing",
            "kubectl not available — run setup-kind-cluster first.",
            "error",
            "pre-start",
        )
        result["valid"] = False
        return result

    for app in apps:
        app_id = app["appId"]
        health_path = app.get("healthPath", "/health")
        role = app.get("role", "web")

        for env in ("dev", "qa", "prod"):
            ns = f"sdd-{env}"

            # Determine host port from app-specific map or role default
            host_port = _HOST_PORT_MAP.get(app_id)
            if host_port is None:
                # Fallback: suggest port-forward if no extraPortMapping is configured
                host_port = {"dev": 8081, "qa": 8082, "prod": 8084}[env]

            # Check if namespace exists
            ns_check = run_native(
                ["kubectl", "get", "ns", ns, "--request-timeout=3s"], root, timeout=10
            )
            if ns_check["returncode"] != 0:
                result["actions"].append(
                    {
                        "path": f"k8s/{ns}",
                        "key": "namespace.missing",
                        "severity": "info",
                        "message": f"Namespace {ns} does not exist yet - deploy first.",
                        "phase": "audit",
                    }
                )
                continue

            # Check if service exists
            svc_check = run_native(
                [
                    "kubectl",
                    "-n",
                    ns,
                    "get",
                    "svc",
                    app_id,
                    "-o",
                    "jsonpath={.spec.ports[0].nodePort}",
                    "--request-timeout=3s",
                ],
                root,
                timeout=10,
            )

            if svc_check["returncode"] == 0 and svc_check["stdout"].strip():
                node_port = svc_check["stdout"].strip()
                # Show direct URL via the kind extraPortMapping host port
                url = f"http://localhost:{host_port}"
                result["actions"].append(
                    {
                        "path": f"k8s/{ns}/{app_id}",
                        "key": "url.available",
                        "severity": "info",
                        "message": (
                            f"{env.upper()} {app_id} accessible at: {url}{health_path}\
"
                            f" (kind nodePort {node_port} mapped to host:{host_port})"
                        ),
                        "phase": "audit",
                    }
                )
            else:
                # Service not deployed — show expected URL if extraPortMapping exists
                if app_id in _HOST_PORT_MAP:
                    url = f"http://localhost:{host_port}"
                    result["actions"].append(
                        {
                            "path": f"k8s/{ns}/{app_id}",
                            "key": "url.pending",
                            "severity": "info",
                            "message": f"{env.upper()} {app_id}: service not deployed yet — will be accessible at {url}{health_path} after deployment.",
                            "phase": "audit",
                        }
                    )
                else:
                    # Unknown app — suggest port-forward as fallback
                    pf_cmd = f"kubectl port-forward -n {ns} svc/{app_id} {host_port}:80"
                    result["actions"].append(
                        {
                            "path": f"k8s/{ns}/{app_id}",
                            "key": "port-forward.command",
                            "severity": "info",
                            "message": f"{env.upper()} {app_id}: run `{pf_cmd}` then visit http://localhost:{host_port}",
                            "phase": "audit",
                        }
                    )

    result["valid"] = not any(
        item.get("severity") == "error" for item in result["findings"]
    )
    return result


# ── CLI entry point ──────────────────────────────────────────────────────


def run_environment_lab(args: list[str]) -> int:
    """CLI entry point for environment-lab commands."""
    import json as _json

    from ._shared import parse_pairs

    if not args:
        print(
            "Available: setup-lab, compose-up, compose-down, health-check, init-local-files, init-project-profile, "
            "init-quality-templates, set-openproject-env, set-monitoring-env, set-gitea-runner-env, "
            "split-infra-env, build-gitea-images, set-gitea-branch-protection, validate-observability, "
            "validate-gitea-runner, set-client-tools, set-project-stack, "
            "set-project-stack-metadata, set-semgrep-config, set-quality-config, "
            "validate-docker-desktop-k8s, setup-kind-cluster, setup-k8s-access, scaffold-k8s, "
            "provision-lab-users, push-to-gitea, verify-gitea-token, generate-gitea-token, renovate-gitea-token",
            file=sys.stderr,
        )
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
        "set-gitea-branch-protection": lambda: set_gitea_branch_protection(
            root, dry_run
        ),
        "validate-observability": lambda: validate_observability(root, dry_run),
        "validate-gitea-runner": lambda: validate_gitea_runner(root, dry_run),
        "set-client-tools": lambda: set_client_tools(root, values, dry_run),
        "set-project-stack": lambda: set_project_stack(root, values, dry_run),
        "set-project-stack-metadata": lambda: set_project_stack_metadata(
            root, values, dry_run
        ),
        "set-quality-config": lambda: set_quality_config(root, values, dry_run),
        "validate-docker-desktop-k8s": lambda: validate_docker_desktop_k8s(
            root, dry_run
        ),
        "setup-kind-cluster": lambda: setup_kind_cluster(root, dry_run),
        "setup-k8s-access": lambda: setup_k8s_access(root, dry_run),
        "scaffold-k8s": lambda: scaffold_k8s(root, dry_run),

        "set-semgrep-config": lambda: set_semgrep_config(root, dry_run),
        "verify-gitea-token": lambda: verify_gitea_api_token(root, dry_run),
        "generate-gitea-token": lambda: generate_gitea_api_token(root, dry_run),
        "renovate-gitea-token": lambda: renovate_gitea_api_token(root, dry_run),
        "provision-lab-users": lambda: provision_lab_users(root, dry_run),
        "health-check": lambda: health_check(root, dry_run),
        "push-to-gitea": lambda: push_to_gitea(root, dry_run),
    }

    handler = handlers.get(subcommand)
    if handler is None:
        print(f"Unknown environment-lab subcommand: {subcommand}", file=sys.stderr)
        return 1

    result = handler()
    print(_json.dumps(result, indent=2))

    # ── Pretty-print summary if present (e.g. setup-lab) ────────────
    summary = result.get("summary")
    if summary:
        failed_steps = result.get("failed_steps", [])
        all_valid = result.get("valid", True)

        # Only print the 'COMPLETE' banner if all steps succeeded
        if all_valid:
            print("=" * 60)
            print("  SETUP-LAB COMPLETE ✓")
            print("=" * 60)
        else:
            print("=" * 60)
            print("  SETUP-LAB FINISHED WITH ERRORS ✗")
            print("=" * 60)

        # Gitea
        g = summary.get("gitea", {})
        gitea_status = g.get("status", "")
        print(f"\n--- GITEA ({g.get('url', 'N/A')}) ---")
        print("-" * 40)
        if gitea_status and "NOT REACHABLE" in gitea_status:
            print(f"  ⚠ {gitea_status}")
        else:
            for u in g.get("users", []):
                print(
                    f"  | username: {u.get('username', '?')} | pass: {u.get('password', '?')} | role: {u.get('role', '?')} |"
                )

        # OpenProject
        op = summary.get("openproject", {})
        op_status = op.get("status", "")
        print(f"\n--- OPENPROJECT ({op.get('url', 'N/A')}) ---")
        print("-" * 40)
        if op_status and "NOT REACHABLE" in op_status:
            print(f"  ⚠ {op_status}")
        else:
            for u in op.get("users", []):
                print(
                    f"  | username: {u.get('username', '?')} | pass: {u.get('password', '?')} | role: {u.get('role', '?')} |"
                )
            board_url = op.get("board", "")
            if board_url:
                print(f"  | Basic Board: {board_url} |")

        # Nexus
        nx = summary.get("nexus", {})
        print(f"\n--- NEXUS ({nx.get('url', 'N/A')}) ---")
        print("-" * 40)
        for u in nx.get("users", []):
            print(
                f"  | username: {u.get('username', '?')} | pass: {u.get('password', '?')} | role: {u.get('role', '?')} |"
            )

        # K8s
        k = summary.get("k8s", {})
        if k:
            print("\n--- KUBERNETES ---")
            print("-" * 40)
            print(f"  | Manifest: {k.get('manifest', 'N/A')} |")
            print("  | Deploy commands: |")
            for cmd in k.get("deploy", []):
                print(f"  |   $ {cmd} |")

        # ── Error summary banner ────────────────────────────────────────
        if not all_valid and failed_steps:
            print("\n" + "!" * 60)
            print("  SETUP-LAB FINISHED WITH ERRORS")
            print("!" * 60)
            print(f"\n  {len(failed_steps)} step(s) failed or reported issues:")
            for fs in failed_steps:
                msg = fs.get("message", "No details")
                if isinstance(msg, list):
                    msg = "; ".join(msg)
                print(f"    ✗ {fs.get('step', '?')}: {msg[:300]}")
            print("\n  ℹ  Common fixes:")
            print("     - Check Docker Desktop is running and healthy")
            print('     - Run `docker compose logs` to check container errors')
            print("     - Re-run `setup-lab` — it is idempotent and will skip completed steps")
            print("     - If a service (Gitea, OpenProject, Nexus) is not reachable,")
            print("       check its container logs and ensure it started correctly")
            print("!" * 60)
            print()
        else:
            print("\n" + "=" * 60)
            print("  Setup complete! All steps passed.")
            print("=" * 60)

    return 0 if result.get("valid", True) else 1
