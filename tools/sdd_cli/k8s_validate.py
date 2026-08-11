"""Kustomize overlay validation gate.

Deterministic, stack-independent validator that closes the residual QA risk
(E2EPROJECT-37 finding 3): per-env service-patch files can be generated but not
wired into the overlay kustomization.yaml, which makes `kubectl apply` fail with
a cluster-scoped NodePort collision AFTER deployments are created.

The gate renders every environment overlay with `kustomize build` (the exact
command CI uses to deploy) and asserts:

1. **Builds** — every overlay (dev, qa, prod) renders successfully and produces
   non-empty output (catches broken/unwired patches and syntax errors).
2. **NodePort uniqueness** — nodePorts are cluster-scoped, so a port rendered by
   two services across ANY environments is a collision (the QA regression: QA
   inherited DEV nodePorts because its service-patch was never wired).
3. **Canonical drift** — every rendered Service nodePort must match
   infra/deployment/ports.json (the single source of truth); a mismatch means
   the committed manifests and the canonical config have drifted (run
   `k8s_ports.write_artifacts` to regenerate).

Pure function `validate_overlays(root, dry_run)` returns a configure_result
dict; the CLI wires it as `environment-lab validate-k8s-overlays`. CI runs it
in pr-validation.yml — the CI image ships kustomize v5.4.3 + pyyaml.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import yaml as _yaml  # pyyaml — present in the CI image and lab tooling
except ImportError:  # pragma: no cover - only reachable on a broken install
    _yaml = None

from ._shared import add_bucket_item, configure_result, run_native

ENVIRONMENTS = ("dev", "qa", "prod")
OVERLAY_DIR = Path("infra/k8s/overlays")
PORTS_FILE = Path("infra/deployment/ports.json")


def _load_canonical_ports(root: Path) -> dict[str, Any]:
    """Load ports.json, raising on missing/invalid (caller converts to finding)."""
    from .k8s_ports import load_ports

    return load_ports(root)


def _render_overlay(root: Path, env: str) -> dict[str, Any]:
    """Run `kustomize build` for one environment overlay.

    Returns {"ok": bool, "error": str|None, "stdout": str}. ok=False when the
    build fails or produces empty output.
    """
    overlay = root / OVERLAY_DIR / env
    if not overlay.exists():
        return {"ok": False, "error": f"overlay dir missing: {overlay}", "stdout": ""}
    result = run_native(["kustomize", "build", str(overlay)], root, timeout=120)
    stdout = (result.get("stdout") or "").strip()
    if result.get("returncode") != 0 or not stdout:
        err = (result.get("stderr") or "").strip() or "empty kustomize output"
        return {"ok": False, "error": err, "stdout": stdout}
    return {"ok": True, "error": None, "stdout": stdout}


def _parse_node_ports(rendered: str) -> list[tuple[str, int]]:
    """Extract (serviceName, nodePort) from rendered multi-doc YAML.

    Only `Service` docs with a `nodePort` in their ports are considered.
    Raises ValueError on malformed YAML so the caller surfaces a loud finding
    instead of silently skipping a parse bug.
    """
    ports: list[tuple[str, int]] = []
    if _yaml is None:
        return ports
    for doc in _yaml.safe_load_all(rendered):
        if not isinstance(doc, dict) or doc.get("kind") != "Service":
            continue
        name = str(doc.get("metadata", {}).get("name", "?"))
        for port in (doc.get("spec", {}) or {}).get("ports", []) or []:
            np = (port or {}).get("nodePort")
            if np is not None:
                ports.append((name, int(np)))
    return ports


def validate_overlays(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Render every overlay and assert buildability, uniqueness, canonical drift.

    Returns a configure_result dict with valid=False when any check fails, so
    CI (pr-validation.yml) fails the PR before the buggy manifests can deploy.
    """
    result = configure_result("ValidateK8sOverlays", dry_run, write_enabled=False)
    if _yaml is None:
        add_bucket_item(
            result["findings"],
            "pyyaml",
            "missing",
            "pyyaml is required to parse kustomize output - install it (CI image has it).",
            "error",
            "pre-start",
        )
        result["valid"] = False
        return result

    if dry_run:
        result["actions"].append(
            {
                "path": "infra/k8s/overlays",
                "key": "validate.plan",
                "severity": "info",
                "message": (
                    "Would kustomize-build dev/qa/prod overlays and check "
                    "NodePort uniqueness + ports.json drift."
                ),
                "phase": "audit",
            }
        )
        result["valid"] = True
        return result

    # Canonical ports.json (single source of truth)
    try:
        canonical = _load_canonical_ports(root)
    except Exception as ex:
        add_bucket_item(
            result["findings"],
            str(PORTS_FILE),
            "ports.unreadable",
            f"Could not load canonical ports.json: {ex}",
            "error",
            "pre-start",
        )
        canonical = None

    rendered_ports: dict[str, int] = {}  # "env/service" -> nodePort
    seen_node_ports: dict[int, str] = {}  # nodePort -> "env/service" (first owner)

    for env in ENVIRONMENTS:
        built = _render_overlay(root, env)
        if not built["ok"]:
            add_bucket_item(
                result["findings"],
                f"infra/k8s/overlays/{env}",
                "kustomize.build",
                f"{env} overlay failed to render: {built['error']}",
                "error",
                "pre-start",
            )
            continue
        try:
            parsed_ports = _parse_node_ports(built["stdout"])
        except Exception as ex:
            add_bucket_item(
                result["findings"],
                f"infra/k8s/overlays/{env}",
                "kustomize.parse",
                f"{env} rendered output could not be parsed: {ex}",
                "error",
                "pre-start",
            )
            continue
        for service, node_port in parsed_ports:
            key = f"{env}/{service}"
            rendered_ports[key] = node_port
            if node_port in seen_node_ports and seen_node_ports[node_port] != key:
                add_bucket_item(
                    result["findings"],
                    "infra/k8s/overlays",
                    "nodeport.collision",
                    f"NodePort {node_port} collides across environments: "
                    f"{seen_node_ports[node_port]} and {key} (cluster-scoped).",
                    "error",
                    "pre-start",
                )
            else:
                seen_node_ports.setdefault(node_port, key)

    # Canonical drift: every rendered nodePort must match ports.json
    if canonical is not None:
        envs = canonical.get("environments", {})
        for env, apps in envs.items():
            for app, cfg in apps.items():
                expected = int(cfg["nodePort"])
                actual = rendered_ports.get(f"{env}/{app}")
                if actual is None:
                    add_bucket_item(
                        result["findings"],
                        f"infra/k8s/overlays/{env}",
                        "nodeport.missing",
                        f"{env}/{app} renders no nodePort - its service-patch is "
                        "likely unwired (kustomization.yaml must list it).",
                        "error",
                        "pre-start",
                    )
                elif actual != expected:
                    add_bucket_item(
                        result["findings"],
                        f"infra/k8s/overlays/{env}",
                        "nodeport.drift",
                        f"{env}/{app} renders nodePort {actual} but ports.json "
                        f"declares {expected} - regenerate with "
                        "k8s_ports.write_artifacts.",
                        "error",
                        "pre-start",
                    )

    if not result["findings"]:
        summary = ", ".join(
            f"{env}: {sum(1 for k in rendered_ports if k.startswith(env + '/'))} service(s)"
            for env in ENVIRONMENTS
        )
        result["actions"].append(
            {
                "path": "infra/k8s/overlays",
                "key": "validate.passed",
                "severity": "info",
                "message": (
                    "All overlays rendered; NodePorts unique cluster-wide and "
                    f"matching ports.json ({summary})."
                ),
                "phase": "audit",
            }
        )

    result["valid"] = not any(
        item.get("severity") == "error" for item in result["findings"]
    )
    return result
