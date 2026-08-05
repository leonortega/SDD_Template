"""Canonical kind/K8s port configuration (single source of truth).

Reads infra/deployment/ports.json and derives every port-dependent artifact
so infra/k8s/kind-config.yaml, the per-env service patches, and validation
never drift from each other.

Generated artifacts (kept in git so the lab works without running this):
  - infra/k8s/kind-config.yaml         extraPortMappings (hostPort -> nodePort)
  - infra/k8s/overlays/{env}/service-patch.yaml  per-env nodePorts

Callers:
  - k8s_lab.scaffold_k8s        writes/regenerates the artifacts
  - package-deploy.yml          NodePort validation step reads ports.json
  - environment_lab             setup-lab validation
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PORTS_FILE = Path("infra/deployment/ports.json")
KIND_CONFIG = Path("infra/k8s/kind-config.yaml")
OVERLAY_DIR = Path("infra/k8s/overlays")


def load_ports(root: Path) -> dict[str, Any]:
    """Load and validate the canonical ports.json."""
    path = root / PORTS_FILE
    if not path.exists():
        raise FileNotFoundError(f"{path} missing — cannot derive port configuration")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # Structural validation (explicit raises — never bare asserts, so it also
    # runs under `python -O` and fails with a clear message).
    if data.get("version") != 1:
        raise ValueError(f"{path}: ports.json version must be 1, got {data.get('version')}")
    if not data.get("appPorts"):
        raise ValueError(f"{path}: 'appPorts' is missing or empty")
    envs = data.get("environments")
    if not envs:
        raise ValueError(f"{path}: 'environments' is missing or empty")

    # NodePorts are cluster-scoped: must be unique across ALL environments.
    seen: dict[int, str] = {}
    for env, apps in envs.items():
        for app, cfg in apps.items():
            np = cfg["nodePort"]
            if np in seen:
                raise ValueError(
                    f"{path}: NodePort collision - {np} used by {seen[np]} and {env}/{app}"
                )
            seen[np] = f"{env}/{app}"
    return data


def env_apps(data: dict[str, Any]) -> list[tuple[str, str]]:
    """Return sorted (env, appId) pairs defined in ports.json."""
    return sorted(
        (env, app)
        for env in data["environments"]
        for app in data["environments"][env]
    )


def node_ports(data: dict[str, Any]) -> list[tuple[int, str, str]]:
    """Return [(nodePort, env, appId)] sorted by nodePort."""
    return sorted(
        (cfg["nodePort"], env, app)
        for env, apps in data["environments"].items()
        for app, cfg in apps.items()
    )


def host_ports(data: dict[str, Any]) -> list[tuple[int, str, str]]:
    """Return [(hostPort, env, appId)] sorted by hostPort."""
    return sorted(
        (cfg["hostPort"], env, app)
        for env, apps in data["environments"].items()
        for app, cfg in apps.items()
    )


def kind_config_yaml(data: dict[str, Any]) -> str:
    """Render infra/k8s/kind-config.yaml (extraPortMappings) from ports.json.

    Environment/app order follows the canonical environments dict (dev, qa,
    prod) with app order from each env entry, so output is stable and matches
    the committed file ordering.
    """
    role_label = {"frontend": "web", "backend": "api"}
    lines = [
        "# Kind cluster config for sdd-cluster",
        "# extraPortMappings enable direct host access to NodePort services",
        "# without needing kubectl port-forward.",
        "#",
        "# Host port -> NodePort -> Service",
    ]
    for env, apps in data["environments"].items():
        for app, cfg in apps.items():
            role = role_label.get(app, "web")
            lines.append(
                f"#  {cfg['hostPort']}    ->  {cfg['nodePort']}   -> {app} {env.upper()} ({role})"
            )
    lines.append("# NodePorts are per-environment and cluster-scoped (per-env fix, PR #6).")
    lines.append("# Generated from infra/deployment/ports.json (tools/sdd_cli/k8s_ports.py).")
    lines.append("# Note: 5001 is reserved by Nexus Docker registry (infra/nexus/compose.yml)")
    lines.append("kind: Cluster")
    lines.append("apiVersion: kind.x-k8s.io/v1alpha4")
    lines.append("nodes:")
    lines.append("  - role: control-plane")
    lines.append("    extraPortMappings:")
    for env, apps in data["environments"].items():
        for app, cfg in apps.items():
            lines.append("      - containerPort: %d" % cfg["nodePort"])
            lines.append("        hostPort: %d" % cfg["hostPort"])
            lines.append("        protocol: TCP")
    return "\n".join(lines) + "\n"


def service_patch_yaml(data: dict[str, Any], env: str) -> str:
    """Render infra/k8s/overlays/{env}/service-patch.yaml from ports.json."""
    blocks = []
    for app in data["environments"][env]:
        cfg = data["environments"][env][app]
        container_port = data["appPorts"].get(app, 80)
        blocks.append(
            "apiVersion: v1\n"
            "kind: Service\n"
            "metadata:\n"
            f"  name: {app}\n"
            "spec:\n"
            "  ports:\n"
            "    - port: %d\n"
            "      targetPort: %d\n"
            "      protocol: TCP\n"
            "      nodePort: %d" % (container_port, container_port, cfg["nodePort"])
        )
    return "\n---\n".join(blocks) + "\n"


def render_all(root: Path) -> dict[str, Path]:
    """Return {label: path} for every artifact derived from ports.json."""
    data = load_ports(root)
    return {
        "kind-config": root / KIND_CONFIG,
        **{
            f"service-patch-{env}": root / OVERLAY_DIR / env / "service-patch.yaml"
            for env in data["environments"]
        },
    }


def write_artifacts(root: Path) -> dict[str, Path]:
    """Regenerate all port-derived artifacts from ports.json (idempotent).

    Files are written with LF endings (matching the git index) so re-runs and
    `git status` stay clean on Windows checkouts.
    """
    data = load_ports(root)
    targets = render_all(root)
    (root / OVERLAY_DIR).mkdir(parents=True, exist_ok=True)
    for env in data["environments"]:
        (root / OVERLAY_DIR / env).mkdir(parents=True, exist_ok=True)
    (root / KIND_CONFIG).parent.mkdir(parents=True, exist_ok=True)

    (root / KIND_CONFIG).write_text(kind_config_yaml(data), encoding="utf-8")
    for env in data["environments"]:
        (root / OVERLAY_DIR / env / "service-patch.yaml").write_text(
            service_patch_yaml(data, env), encoding="utf-8"
        )
    return targets
