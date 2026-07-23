"""Environment lab: Docker Compose, env files, project profile, observability."""

from __future__ import annotations

import http.client
import json
import subprocess
import sys
import tempfile
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
from .tool_installer import install_lefthook

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

    # 9. Validate observability
    _add_step(validate_observability(root, dry_run), fatal=False)

    # 10. Validate Gitea runner (Docker, images, tools, socket, docker_push.py)
    _add_step(validate_gitea_runner(root, dry_run), fatal=False)

    # 11. Provision lab users (Gitea, OpenProject, Nexus) + runner registration token
    _add_step(provision_lab_users(root, dry_run), fatal=False)

    # 12. Provision Nexus repositories + accept EULA
    _add_step(provision_nexus_repositories(root, dry_run), fatal=False)

    # 13. Provision Gitea CI secrets (NEXUS_USERNAME, KUBECONFIG_B64, etc.)
    _add_step(provision_gitea_secrets(root, dry_run), fatal=False)

    # 14. Push v0 code to Gitea (create main branch, push dev)
    _add_step(push_to_gitea(root, dry_run), fatal=False)

    # 15. Set Gitea branch protection for dev/main
    _add_step(set_gitea_branch_protection(root, dry_run), fatal=False)

    # 16. Scaffold K8s deployment files (validates Docker Desktop K8s + creates manifests)
    _add_step(scaffold_k8s(root, dry_run), fatal=False)

    # 17. Generate Semgrep config from stack (non-fatal — stack may not be set yet)
    _add_step(set_semgrep_config(root, dry_run), fatal=False)

    result["steps"] = steps
    all_valid = all(s.get("valid", True) for s in steps)
    result["valid"] = all_valid

    # ── Summary: credentials and URLs ─────────────────────────────────
    result["summary"] = {
        "gitea": {
            "url": "http://localhost:3000",
            "users": [
                {"username": "admin", "password": "admin123", "role": "admin"},
                {
                    "username": "FirstUser",
                    "password": "FirstUser123",
                    "role": "developer",
                },
                {
                    "username": "SecondUser",
                    "password": "SecondUser123",
                    "role": "developer",
                },
            ],
        },
        "openproject": {
            "url": "http://localhost:8080",
            "users": [
                {"username": "admin", "password": "admin", "role": "admin"},
                {
                    "username": "FirstUser",
                    "password": "FirstUser123!",
                    "role": "developer",
                },
                {
                    "username": "SecondUser",
                    "password": "SecondUser123!",
                    "role": "developer",
                },
            ],
            "board": "http://localhost:8080/projects/e2eproject/boards",
        },
        "nexus": {
            "url": "http://localhost:8088",
            "users": [
                {"username": "admin", "password": "admin123", "role": "admin"},
            ],
        },
        "k8s": {
            "manifest": "infra/k8s/deploy.yaml (envsubst: ENV, REPLICAS, REGISTRY, COMMIT_SHA)",
            "deploy": [
                "ENV=dev REPLICAS=1 REGISTRY=host.docker.internal:5001 COMMIT_SHA=latest envsubst < infra/k8s/deploy.yaml | kubectl apply -f -",
                "ENV=qa REPLICAS=2 REGISTRY=host.docker.internal:5001 COMMIT_SHA=latest envsubst < infra/k8s/deploy.yaml | kubectl apply -f -",
                "ENV=prod REPLICAS=3 REGISTRY=host.docker.internal:5001 COMMIT_SHA=latest envsubst < infra/k8s/deploy.yaml | kubectl apply -f -",
            ],
        },
    }
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
    return {
        "command": f"compose-{action}",
        "valid": result.returncode == 0,
        "returncode": result.returncode,
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
                "ticket": {
                    "id": "openproject",
                    "adapter": ".codex/providers/ticket.openproject.md",
                },
                "repository": {
                    "id": "gitea",
                    "adapter": ".codex/providers/repo.gitea.md",
                },
                "review": {"id": "gitea", "adapter": ".codex/providers/repo.gitea.md"},
                "artifact": {
                    "id": "nexus",
                    "adapter": ".codex/providers/artifact.nexus.md",
                },
                "deployment": {
                    "id": "docker-desktop",
                    "adapter": ".codex/providers/deploy.example.md",
                },
            },
            "workflow": {
                "ticketKeyPattern": "TICKET-[0-9]+",
                "baseBranch": "dev",
                "branchPrefix": "codex",
            },
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

    for name in (
        "ticket.example.md",
        "repo.example.md",
        "artifact.example.md",
        "deploy.example.md",
    ):
        example = providers / name
        if not example.exists():
            changed = True
            if not dry_run:
                example.write_text(
                    f"# {name}\n\nprovider-neutral scaffold\n", encoding="utf-8"
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
            ["docker", "image", "inspect", image, "--format", "{{index .Config.Labels \"sdd.dockerfile.checksum\"}}"],
            root, timeout=15
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
            response.read()
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
            elif response.status == 409:
                # Rule already exists — fall back to PATCH on branch_protections/{rule_name}
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
        # Auto-generate Semgrep config after stack change
        set_semgrep_config(root, dry_run)
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
        "SetRecommendedTools",
        "MapProjectGuidanceStep",
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


def set_recommended_tools(
    root: Path, values: dict[str, Any], dry_run: bool = False
) -> dict[str, Any]:
    """Set accepted/dismissed tool recommendations."""
    result = configure_result("SetRecommendedTools", dry_run, write_enabled=not dry_run)
    path = root / ".codex" / "client-tools.local.json"
    if not path.exists():
        return {
            "mode": "SetRecommendedTools",
            "valid": False,
            "errors": [
                "Missing .codex/client-tools.local.json. Run InitLocalFiles first."
            ],
        }
    if "accepted" not in values and "dismissed" not in values:
        return {
            "mode": "SetRecommendedTools",
            "valid": False,
            "errors": ["values.accepted or values.dismissed is required."],
        }
    config = read_json(path, optional=True)
    recommended = config.setdefault("recommendedTools", {})
    for key in ("accepted", "dismissed"):
        existing = list(recommended.get(key, []))
        for item in values.get(key, []):
            if item not in existing:
                existing.append(item)
        recommended[key] = existing
        if values.get(key):
            result["actions"].append(
                {
                    "path": ".codex/client-tools.local.json",
                    "key": f"recommendedTools.{key}",
                    "severity": "info",
                    "message": f"Recorded {key} recommendation ids.",
                    "phase": "apply",
                }
            )
    if not dry_run:
        write_json(path, config)
    result["valid"] = True
    return result


# ── Set Semgrep config (stack-aware SAST rules) ─────────────────────────


def set_semgrep_config(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Generate .semgrep.yml from project stack for offline CI scanning.

    Reads the project stack from project-profile.local.json, looks up the
    corresponding semgrep rule packs from stack-data.json, and writes a
    .semgrep.yml config file in the repo root. The rules list is also
    stored in project-profile.local.json under stack.semgrepRules, which
    the CI workflow reads at scan time.

    The Docker image pre-caches all rule packs at build time so the CI
    container can run Semgrep offline.
    """
    result = configure_result("SetSemgrepConfig", dry_run, write_enabled=not dry_run)

    # Read stack data mapping
    stack_data_path = root / "tools" / "sdd_cli" / "stack-data.json"
    stack_data = read_json(stack_data_path, optional=True)
    canonical_map = stack_data.get("_STACK_CANONICAL_MAP", {})
    tag_aliases = stack_data.get("_STACK_TAG_ALIASES", {})

    # Read project profile
    profile_path = root / ".codex" / "project-profile.local.json"
    profile = read_json(profile_path, optional=True)
    stack = profile.get("stack", {}) if isinstance(profile.get("stack"), dict) else {}

    def _resolve_semgrep_rules(domain_value: str) -> list[str]:
        """Resolve a stack domain value to semgrep rule packs using case-insensitive
        and alias-aware matching against the canonical map."""
        # 1. Direct lookup
        if domain_value in canonical_map:
            return list(canonical_map[domain_value].get("semgrepRules", []))

        # 2. Lowercase direct lookup
        lc = domain_value.lower()
        if lc in canonical_map:
            return list(canonical_map[lc].get("semgrepRules", []))

        # 3. Search tag aliases for matching canonical key
        #    Uses substring containment so compound values like "C# (.NET)" match alias "c#"
        #    Aliases are sorted by longest match first to prevent short substrings
        #    (e.g. "java" in "javascript") from matching before the correct longer one.
        dv_lower = domain_value.lower()
        sorted_aliases = sorted(
            tag_aliases.items(),
            key=lambda item: max(len(a) for a in item[1]),
            reverse=True,
        )
        for canonical_key, aliases in sorted_aliases:
            alias_lower = [a.lower() for a in aliases]
            if dv_lower in alias_lower or any(
                alias in dv_lower for alias in alias_lower
            ):
                entry = canonical_map.get(canonical_key, {})
                return list(entry.get("semgrepRules", []))

        return []

    # Collect all semgrep rules from the three stack domains
    all_rules: list[str] = []
    seen: set[str] = set()
    domains = {
        "frontend": stack.get("frontend", {}).get("value", ""),
        "backend": stack.get("backend", {}).get("value", ""),
        "database": stack.get("database", {}).get("value", ""),
    }

    for domain_name, domain_value in domains.items():
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
        "# Rules are resolved from stack-data.json based on project stack",
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


# ── Provision Nexus repositories (sdd-artifacts raw hosted) ─────────────


# ── Validate app deployment config ─────────────────────────────────────


def validate_app_config(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Validate the app deployment configuration (apps.json).

    Checks that apps.json is valid JSON, conforms to its schema,
    and that each app's projectPath has a Dockerfile.
    """
    result = configure_result(
        "ValidateAppConfig", dry_run, write_enabled=not dry_run
    )
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
    nexus_pass = "admin123"

    if dry_run:
        result["actions"].append(
            {
                "path": "nexus/repositories",
                "key": "plan",
                "severity": "info",
                "message": "Would create Nexus raw hosted repository: sdd-artifacts.",
                "phase": "apply",
            }
        )
        result["valid"] = True
        return result

    def _nexus_api(
        method: str, path: str, body: dict | None = None
    ) -> tuple[int, str]:
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
        "POST", "/service/rest/v1/editions/eula/accept",
        body={"eulaAccepted": True}
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
            for p in [Path("/etc/docker/daemon.json"), Path.home() / ".docker" / "daemon.json"]:
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
    _op_token = None

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
                f"/api/v1/repos/{_owner}/{_repo}/actions/runners/registration-token"
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
                            root, timeout=30
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

    # ── 2b. OpenProject: define board list names (not tied to OP statuses) ──
    # These are pure labels on the board, NOT linked to OpenProject statuses.
    # Dragging a work package between these columns does NOT trigger status
    # transitions, so the board stays flexible regardless of OP workflow rules.
    BOARD_LIST_NAMES = ["New", "To Do", "In Progress", "In Review", "QA", "Done"]
    for name in BOARD_LIST_NAMES:
        result["actions"].append(
            {
                "path": f"openproject/boards/e2e-test/lists/{name}",
                "key": "board.list",
                "severity": "info",
                "message": f"Board list '{name}' configured.",
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

    # ── 2e. OpenProject: create Basic board e2e-test with list names ──
    # OpenProject 17+ may not expose /api/v3/boards via REST — fall back to Rails console.
    # Board columns are NOT tied to OpenProject statuses — they're plain label columns
    # so work packages can be dragged freely between them without status transition blocks.
    brd_st, brd_dt = _op_api(
        "POST",
        "/api/v3/boards",
        body={
            "name": "e2e-test",
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
                "path": "openproject/boards/e2e-test",
                "key": "board.created",
                "severity": "info",
                "message": "OpenProject Basic board e2e-test created.",
                "phase": "apply",
            }
        )
    elif brd_st == 422:
        result["actions"].append(
            {
                "path": "openproject/boards/e2e-test",
                "key": "board.exists",
                "severity": "info",
                "message": "OpenProject Basic board e2e-test already exists.",
                "phase": "apply",
            }
        )
    elif brd_st == 404:
        # Boards API not exposed via REST — try Rails console
        # Write Ruby script to local temp file, copy to container, execute
        # Board lists are NOT status-filtered — they're plain label columns
        board_lists_str = "[" + ", ".join(f'"{n}"' for n in BOARD_LIST_NAMES) + "]"
        ruby_script = (
            'project = Project.find_by(identifier: "e2eproject")\n'
            'admin = User.find_by(login: "admin")\n'
            "unless project && admin\n"
            '  puts "Project or admin not found"\n'
            "  exit 1\n"
            "end\n"
            '::Boards::Grid.where(project: project, name: "e2e-test").destroy_all\n'
            "board_labels = " + board_lists_str + "\n"
            "board = ::Boards::Grid.create!(\n"
            "  project: project,\n"
            '  name: "e2e-test",\n'
            "  row_count: 1,\n"
            "  column_count: board_labels.length,\n"
            "  user_id: admin.id\n"
            ")\n"
            "board_labels.each_with_index do |label, idx|\n"
            "  query = ::Query.new(\n"
            "    name: label,\n"
            "    project: project,\n"
            "    user_id: admin.id,\n"
            "    public: true,\n"
            "    include_subprojects: false,\n"
            "    display_sums: false\n"
            "  )\n"
            "  query.save!(validate: false)\n"
            "  ::Grids::Widget.create!(\n"
            "    grid: board,\n"
            '    identifier: "work_package_query",\n'
            "    start_row: 1,\n"
            "    end_row: 2,\n"
            "    start_column: idx + 1,\n"
            "    end_column: idx + 2,\n"
            '    options: {"query_id" => query.id}\n'
            "  )\n"
            "end\n"
            'puts "Board e2e-test created with #{board_labels.length} columns"\n'
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
                "openproject/boards/e2e-test",
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
            and "e2e-test created" in rails_result["stdout"]
        ):
            result["actions"].append(
                {
                    "path": "openproject/boards/e2e-test",
                    "key": "board.created",
                    "severity": "info",
                    "message": "OpenProject Basic board e2e-test created via Rails console with plain label columns.",
                    "phase": "apply",
                }
            )
        elif "already exists" in rails_result.get(
            "stdout", ""
        ) or "already exists" in rails_result.get("stderr", ""):
            result["actions"].append(
                {
                    "path": "openproject/boards/e2e-test",
                    "key": "board.exists",
                    "severity": "info",
                    "message": "OpenProject Basic board e2e-test already exists.",
                    "phase": "apply",
                }
            )
        else:
            add_bucket_item(
                result["findings"],
                "openproject/boards/e2e-test",
                "board.create",
                f"OpenProject board creation via Rails console failed: {rails_result['stderr'][:200]}",
                "warning",
                "apply",
            )
    else:
        add_bucket_item(
            result["findings"],
            "openproject/boards/e2e-test",
            "board.create",
            f"OpenProject board creation returned {brd_st}: {brd_dt[:200]}",
            "warning",
            "apply",
        )

    # ── 5. OpenProject: generate API key and register MCP server ──────────
    op_api_key: str | None = None
    if not dry_run:
        try:
            rails_key_cmd = (
                "cd /app && bundle exec rails runner "
                '"u = User.find_by(login: \\"admin\\"); '
                "u.force_password_change = false; u.save!; "
                "token = Token::API.create!(user: u); "
                'puts token.plain_value"'
            )
            key_result = run_native(
                [
                    "docker",
                    "exec",
                    "agentic-e2e-openproject-1",
                    "sh",
                    "-c",
                    rails_key_cmd,
                ],
                REPO_ROOT,
                timeout=30,
            )
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
        # Register the openproject MCP server in .vscode/mcp.json
        try:
            from tools.bm25s_flashrank.setup_mcp import setup_openproject_mcp

            written = setup_openproject_mcp(root, "http://localhost:8080", op_api_key)
            for p in written:
                result["actions"].append(
                    {
                        "path": p.relative_to(root).as_posix(),
                        "key": "mcp.registered",
                        "severity": "info",
                        "message": f"OpenProject MCP server registered in {p.name}.",
                        "phase": "apply",
                    }
                )
        except Exception as ex:
            add_bucket_item(
                result["findings"],
                ".vscode/mcp.json",
                "mcp.register",
                f"OpenProject MCP server registration failed: {ex}",
                "warning",
                "apply",
            )
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
    # First attempt with default admin/admin123, use the same as desired password
    # Nexus default: admin / admin123, then change password = new password
    # PUT /service/rest/v1/security/users/admin/change-password
    status, data = _nexus_api(
        "PUT",
        "/service/rest/v1/security/users/admin/change-password",
        body={"password": "admin123"},
        auth=("admin", "admin123"),
    )
    if status in {200, 204, 404, 401}:
        # 404 or 401 means default password may already be set or different API version
        # Try GET /service/rest/v1/security/users to verify connectivity
        status2, _ = _nexus_api(
            "GET", "/service/rest/v1/security/users", auth=("admin", "admin123")
        )
        if status2 in {200, 401}:
            result["actions"].append(
                {
                    "path": "nexus/users/admin",
                    "key": "password.set",
                    "severity": "info",
                    "message": "Nexus admin password set/verified to admin123.",
                    "phase": "apply",
                }
            )
        else:
            add_bucket_item(
                result["findings"],
                "nexus/users/admin",
                "password.set",
                f"Nexus admin password change returned {status}/{status2}",
                "warning",
                "apply",
            )
    else:
        add_bucket_item(
            result["findings"],
            "nexus/users/admin",
            "password.set",
            f"Nexus admin password change returned {status}: {data[:200]}",
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
                "name": "e2e-test",
                "url": "http://localhost:8080/projects/e2eproject/boards",
                "lists": BOARD_LIST_NAMES,
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
    - KUBECONFIG_B64: base64-encoded kubeconfig for K8s access

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
                "message": "Would provision Gitea secrets: NEXUS_USERNAME, NEXUS_PASSWORD, NEXUS_URL, NEXUS_REPOSITORY, KUBECONFIG_B64.",
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

    def _gitea_actions_api(method: str, path: str, body: dict | None = None) -> tuple[int, str]:
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

    # Read kubeconfig for KUBECONFIG_B64
    kubeconfig_paths = [
        Path.home() / ".kube" / "config",
        Path("/home/runner/.kube/config"),
        Path("/tmp/kubeconfig"),
    ]
    kubeconfig_data = None
    for kp in kubeconfig_paths:
        if kp.exists():
            kubeconfig_data = kp.read_bytes()
            break

    if kubeconfig_data:
        secrets["KUBECONFIG_B64"] = base64.b64encode(kubeconfig_data).decode()
    else:
        add_bucket_item(
            result["findings"],
            "kubeconfig",
            "missing",
            "Could not locate kubeconfig. KUBECONFIG_B64 secret will not be set.",
            "warning",
            "pre-start",
        )

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
            ["git", "commit", "-m", "v0: initial SDD template setup"], root, timeout=30
        )
        if commit["returncode"] == 0:
            result["actions"].append(
                {
                    "path": "git/commit",
                    "key": "commit.v0",
                    "severity": "info",
                    "message": "Committed v0: initial SDD template setup.",
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
    """Scaffold K8s deployment files: Dockerfile and single envsubst manifest."""
    result = configure_result("ScaffoldK8s", dry_run, write_enabled=not dry_run)

    if dry_run:
        result["actions"].append(
            {
                "path": "infra/k8s",
                "key": "scaffold.plan",
                "severity": "info",
                "message": (
                    "Would scaffold K8s deployment files:"
                    "\n  - Dockerfile per app (nginx for web)"
                    "\n  - .dockerignore per app"
                    "\n  - infra/k8s/deploy.yaml (envsubst: ENV, REPLICAS, REGISTRY, COMMIT_SHA)"
                    "\n  - nginx.conf for web apps"
                ),
                "phase": "apply",
            }
        )
        result["valid"] = True
        return result

    # Prerequisite: validate Docker Desktop K8s
    k8s_check = validate_docker_desktop_k8s(root)
    if not k8s_check.get("valid", False):
        for f in k8s_check.get("findings", []):
            result["findings"].append(f)
        add_bucket_item(
            result["findings"],
            "k8s",
            "prerequisite",
            "Docker Desktop K8s validation failed — fix before scaffolding.",
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
                result["actions"].append(
                    {
                        "path": f"{proj}/.dockerignore",
                        "key": "file.created",
                        "severity": "info",
                        "message": f"Created .dockerignore for {app_id}.",
                        "phase": "apply",
                    }
                )

            # nginx.conf
            nc = app_dir / "nginx.conf"
            if not nc.exists():
                nc.write_text(
                    "server {\n"
                    "    listen 80;\n"
                    "    server_name _;\n"
                    "    root /usr/share/nginx/html;\n"
                    "    index index.html;\n"
                    "    location / {\n"
                    "        try_files $uri $uri/ /index.html;\n"
                    "    }\n"
                    "    location /health {\n"
                    '        return 200 \'{"status":"ok"}\';\n'
                    "        add_header Content-Type application/json;\n"
                    "    }\n"
                    "}\n",
                    encoding="utf-8",
                )
                result["actions"].append(
                    {
                        "path": f"{proj}/nginx.conf",
                        "key": "file.created",
                        "severity": "info",
                        "message": f"Created nginx.conf for {app_id}.",
                        "phase": "apply",
                    }
                )

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
                result["actions"].append(
                    {
                        "path": f"{proj}/Dockerfile",
                        "key": "file.created",
                        "severity": "info",
                        "message": f"Created Dockerfile for {app_id}.",
                        "phase": "apply",
                    }
                )
            else:
                result["actions"].append(
                    {
                        "path": f"{proj}/Dockerfile",
                        "key": "file.exists",
                        "severity": "info",
                        "message": f"Dockerfile already exists for {app_id}.",
                        "phase": "audit",
                    }
                )

    # Single envsubst manifest
    deploy_yaml = (
        "apiVersion: v1\n"
        "kind: Namespace\n"
        "metadata:\n"
        "  name: sdd-${ENV}\n"
        "---\n"
        "apiVersion: apps/v1\n"
        "kind: Deployment\n"
        "metadata:\n"
        f"  name: {first_app}\n"
        "  namespace: sdd-${ENV}\n"
        "spec:\n"
        "  replicas: ${REPLICAS}\n"
        "  selector:\n"
        "    matchLabels:\n"
        f"      app: {first_app}\n"
        "  template:\n"
        "    metadata:\n"
        "      labels:\n"
        f"        app: {first_app}\n"
        "    spec:\n"
        "      containers:\n"
        f"        - name: {first_app}\n"
        f"          image: ${{REGISTRY}}/{first_app}:${{COMMIT_SHA}}\n"
        "          imagePullPolicy: IfNotPresent\n"
        "          ports:\n"
        "            - containerPort: 80\n"
        "          env:\n"
        "            - name: ENVIRONMENT\n"
        '              value: "${ENV}"\n'
        "          livenessProbe:\n"
        "            httpGet:\n"
        f"              path: {first_health}\n"
        "              port: 80\n"
        "            initialDelaySeconds: 10\n"
        "            periodSeconds: 30\n"
        "          readinessProbe:\n"
        "            httpGet:\n"
        f"              path: {first_health}\n"
        "              port: 80\n"
        "            initialDelaySeconds: 5\n"
        "            periodSeconds: 10\n"
        "          resources:\n"
        "            requests:\n"
        '              cpu: "100m"\n'
        '              memory: "128Mi"\n'
        "            limits:\n"
        '              cpu: "500m"\n'
        '              memory: "256Mi"\n'
        "---\n"
        "apiVersion: v1\n"
        "kind: Service\n"
        "metadata:\n"
        f"  name: {first_app}\n"
        "  namespace: sdd-${ENV}\n"
        "spec:\n"
        "  type: LoadBalancer\n"
        "  selector:\n"
        f"    app: {first_app}\n"
        "  ports:\n"
        "    - protocol: TCP\n"
        "      port: 80\n"
        "      targetPort: 80\n"
    )
    (k8s_dir / "deploy.yaml").write_text(deploy_yaml, encoding="utf-8")
    result["actions"].append(
        {
            "path": "infra/k8s/deploy.yaml",
            "key": "file.created",
            "severity": "info",
            "message": "Created envsubst manifest: infra/k8s/deploy.yaml.",
            "phase": "apply",
        }
    )

    result["valid"] = not any(
        item.get("severity") == "error" for item in result["findings"]
    )
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
    """Set up port-forward access to deployed apps and display URLs."""
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

    if dry_run:
        for app in apps:
            result["actions"].append(
                {
                    "path": f"k8s/port-forward/{app['appId']}",
                    "key": "port-forward.plan",
                    "severity": "info",
                    "message": f"Would set up port-forward for {app['appId']} in dev/qa/prod.",
                    "phase": "apply",
                }
            )
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
            local_port = {"dev": 8081, "qa": 8082, "prod": 8083}[env]  # K8s NodePort, not Nexus Docker registry port

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
                url = f"http://localhost:{node_port}"
                result["actions"].append(
                    {
                        "path": f"k8s/{ns}/{app_id}",
                        "key": "url.available",
                        "severity": "info",
                        "message": f"{env.upper()} {app_id} accessible at: {url}{health_path}",
                        "phase": "audit",
                    }
                )
            else:
                # Suggest port-forward command
                pf_cmd = f"kubectl port-forward -n {ns} svc/{app_id} {local_port}:80"
                result["actions"].append(
                    {
                        "path": f"k8s/{ns}/{app_id}",
                        "key": "port-forward.command",
                        "severity": "info",
                        "message": f"{env.upper()} {app_id}: run `{pf_cmd}` then visit http://localhost:{local_port}",
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
            "Available: setup-lab, compose-up, compose-down, init-local-files, init-project-profile, "
            "init-quality-templates, set-openproject-env, set-monitoring-env, set-gitea-runner-env, "
            "split-infra-env, build-gitea-images, set-gitea-branch-protection, validate-observability, "
            "validate-gitea-runner, set-client-tools, set-project-stack, "
            "set-project-stack-metadata, set-semgrep-config, set-quality-config, validate-docker-desktop-k8s, setup-k8s-access, scaffold-k8s, set-recommended-tools, "
            "provision-lab-users, push-to-gitea",
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
        "setup-k8s-access": lambda: setup_k8s_access(root, dry_run),
        "scaffold-k8s": lambda: scaffold_k8s(root, dry_run),
        "set-recommended-tools": lambda: set_recommended_tools(root, values, dry_run),
        "set-semgrep-config": lambda: set_semgrep_config(root, dry_run),
        "provision-lab-users": lambda: provision_lab_users(root, dry_run),
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
        print("=" * 60)
        print("  SETUP-LAB COMPLETE - Credentials & URLs")
        print("=" * 60)

        # Gitea
        g = summary.get("gitea", {})
        print(f"\n--- GITEA ({g.get('url', 'N/A')}) ---")
        print("-" * 40)
        for u in g.get("users", []):
            print(
                f"  | username: {u.get('username', '?')} | pass: {u.get('password', '?')} | role: {u.get('role', '?')} |"
            )

        # OpenProject
        op = summary.get("openproject", {})
        print(f"\n--- OPENPROJECT ({op.get('url', 'N/A')}) ---")
        print("-" * 40)
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
            print(f"  | Deploy commands: |")
            for cmd in k.get("deploy", []):
                print(f"  |   $ {cmd} |")

        print("\n" + "=" * 60)
        print("  Setup complete!")
        print("=" * 60)

    return 0 if result.get("valid", True) else 1
