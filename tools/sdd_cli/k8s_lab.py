"""Kubernetes lab: K8s scaffolding, kind cluster, Docker Desktop K8s."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from ._shared import (
    add_bucket_item,
    configure_result,
    read_json,
    run_native,
)
from .k8s_ports import load_ports

# ── Headlamp (K8s web UI) ────────────────────────────────────────────────


# Headlamp is the lab's Kubernetes web dashboard. On Windows it is a native
# desktop app (winget id Headlamp.Headlamp) that reads ~/.kube/config and
# shows the current kubeconfig context (kind-sdd-cluster after
# setup-kind-cluster). This step is a convenience — it is non-fatal: the
# lab works fine with kubectl + the k8s MCP alone.


def ensure_headlamp(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Ensure the Headlamp K8s web UI is installed (per-platform).

    Installs the Headlamp desktop app when missing:
    - Windows: winget install Headlamp.Headlamp
    - macOS:   brew install --cask headlamp
    - Linux:   snap install headlamp (fallback: direct AppImage download)

    After install it reports the kubeconfig context Headlamp will show, so
    the user can launch it and browse the running kind cluster. Non-fatal:
    a missing Headlamp never fails the lab.
    """
    result = configure_result("EnsureHeadlamp", dry_run, write_enabled=not dry_run)
    if dry_run:
        result["actions"].append(
            {
                "path": "headlamp",
                "key": "install.plan",
                "severity": "info",
                "message": "Would check Headlamp (K8s web UI) and install it if missing.",
                "phase": "apply",
            }
        )
        result["valid"] = True
        return result

    import platform

    pf = platform.system().lower()

    # ── 1. Detect existing install ──
    # Windows desktop app path is resolved at call time (env may differ).
    win_exe = Path(
        os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
    ) / "Programs" / "Headlamp" / "Headlamp.exe"
    headlamp_cli = shutil.which("headlamp")
    installed = headlamp_cli is not None or win_exe.exists() or Path(
        "/Applications/Headlamp.app"
    ).exists()

    if installed:
        version = ""
        if headlamp_cli:
            vcheck = run_native(["headlamp", "--version"], root, timeout=10)
            if vcheck["returncode"] == 0:
                version = vcheck["stdout"].strip()
        ctx = "unknown"
        cctx = run_native(["kubectl", "config", "current-context"], root, timeout=10)
        if cctx["returncode"] == 0:
            ctx = cctx["stdout"].strip()
        result["actions"].append(
            {
                "path": "headlamp",
                "key": "installed",
                "severity": "info",
                "message": (
                    f"Headlamp is already installed{f' (v{version})' if version else ''}. "
                    f"Launch it and select kubeconfig context '{ctx}' to browse the cluster."
                ),
                "phase": "audit",
            }
        )
        result["valid"] = True
        return result

    # ── 2. Install per platform ──
    result["actions"].append(
        {
            "path": "headlamp",
            "key": "binary.install",
            "severity": "info",
            "message": "Headlamp not found — installing...",
            "phase": "apply",
        }
    )
    if pf == "windows":
        install = run_native(
            [
                "winget",
                "install",
                "Headlamp.Headlamp",
                "--accept-package-agreements",
                "--accept-source-agreements",
                "--silent",
            ],
            root,
            timeout=300,
        )
    elif pf == "darwin":
        install = run_native(["brew", "install", "--cask", "headlamp"], root, timeout=300)
    else:
        # Linux: snap first, then AppImage fallback
        install = run_native(["snap", "install", "headlamp"], root, timeout=300)
        if install["returncode"] != 0:
            # Headlamp AppImage (latest release) — amd64 only.
            install = run_native(
                [
                    "curl",
                    "-fsSL",
                    "-o",
                    "/tmp/headlamp.AppImage",
                    "https://github.com/headlamp-k8s/headlamp/releases/latest/download/headlamp-linux-amd64.AppImage",
                    "&&",
                    "chmod",
                    "+x",
                    "/tmp/headlamp.AppImage",
                    "&&",
                    "mv",
                    "/tmp/headlamp.AppImage",
                    "/usr/local/bin/headlamp",
                ],
                root,
                timeout=300,
            )

    if install["returncode"] != 0:
        add_bucket_item(
            result["findings"],
            "headlamp",
            "install.failed",
            (
                "Could not install Headlamp automatically. "
                "Install manually: winget install Headlamp.Headlamp (Windows), "
                "brew install --cask headlamp (macOS), or https://headlamp.dev "
                "(Linux). Non-fatal — the lab works without it."
            ),
            "warning",
            "pre-start",
        )
        result["valid"] = True
        return result

    # ── 3. Report success + context ──
    ctx = "unknown"
    cctx = run_native(["kubectl", "config", "current-context"], root, timeout=10)
    if cctx["returncode"] == 0:
        ctx = cctx["stdout"].strip()
    result["actions"].append(
        {
            "path": "headlamp",
            "key": "binary.installed",
            "severity": "info",
            "message": (
                f"Headlamp installed. Launch it and select kubeconfig context "
                f"'{ctx}' to browse the cluster."
            ),
            "phase": "apply",
        }
    )
    result["valid"] = True
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

    # ── Port mapping by app ──
    # Canonical source of truth: infra/deployment/ports.json
    # (tools/sdd_cli/k8s_ports.py). appPorts holds the container port per app;
    # per-env nodePorts are derived for kind extraPortMappings + overlay service
    # patches. The dev environment values seed the base manifests (overlays
    # override per env).
    _port_map = {"web": 80, "api": 5000}  # role -> container port fallback
    _dev_node_ports: dict[str, int] = {}  # appId -> dev nodePort (canonical)
    try:
        _ports = load_ports(root)
        _dev_cfg = _ports.get("environments", {}).get("dev", {})
        _app_port_map = _ports.get("appPorts", {})
        for _app_id, _cfg in _dev_cfg.items():
            _dev_node_ports[_app_id] = _cfg["nodePort"]
            _port_map[_app_id] = _app_port_map.get(_app_id, _port_map.get(_app_id, 80))
    except (FileNotFoundError, ValueError):
        # Fall back to defaults only when ports.json is missing or invalid
        # (never in the shipped repo) — keeps the scaffold usable in a bare
        # checkout and degrades gracefully instead of crashing.
        pass
    _used_node_ports: set[int] = set()

    def _port_for_role(role: str) -> int:
        return _port_map.get(role, 80)

    def _node_port_for_app(app_id: str) -> int:
        base = _dev_node_ports.get(app_id, 30080)
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
            node_port = _node_port_for_app(app_id)
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

    # ── Port-derived artifacts (kind-config extraPortMappings + per-env
    # service patches) are regenerated from infra/deployment/ports.json so the
    # committed files never drift from the canonical source.
    if not dry_run:
        from .k8s_ports import write_artifacts as _write_ports

        try:
            _targets = _write_ports(root)
            result["actions"].append(
                {
                    "path": "infra/deployment/ports.json",
                    "key": "ports.generated",
                    "severity": "info",
                    "message": (
                        "Regenerated port-derived artifacts from ports.json: "
                        + ", ".join(sorted(str(p.name) for p in _targets.values()))
                        + "."
                    ),
                    "phase": "apply",
                }
            )
        except (FileNotFoundError, ValueError) as e:
            result["actions"].append(
                {
                    "path": "infra/deployment/ports.json",
                    "key": "ports.missing",
                    "severity": "warning",
                    "message": (
                        "ports.json unavailable or invalid (%s) - skipping port "
                        "artifact regeneration." % e
                    ),
                    "phase": "audit",
                }
            )

    result["valid"] = not any(
        item.get("severity") == "error" for item in result["findings"]
    )
    return result
# ── kind cluster setup ────────────────────────────────────────────────


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
