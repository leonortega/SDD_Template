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
import re
from pathlib import Path
from typing import Any

PORTS_FILE = Path("infra/deployment/ports.json")
APPS_FILE = Path("infra/deployment/apps.json")
ROLES_FILE = Path("infra/deployment/roles.json")
KIND_CONFIG = Path("infra/k8s/kind-config.yaml")
OVERLAY_DIR = Path("infra/k8s/overlays")

# Host ports consumed by the rest of the lab stack. kind extraPortMappings
# must never reuse them — a collision surfaces as an opaque bind failure at
# `kind create` time instead of an actionable validation error. Keep this in
# sync with the compose files:
#   infra/gitea/compose.yml         3000 (web), 2222 (ssh), 8123 (runner admin)
#   infra/nexus/compose.yml         8088 (web), 5001 (Docker registry)
#   infra/openproject/compose.yml   8080 (web)
#   infra/monitoring/compose.yml    3001 (Grafana), 8090 (probe), 8888 (Dozzle), 5341 (Seq)
RESERVED_HOST_PORTS: frozenset[int] = frozenset(
    {3000, 2222, 8123, 8088, 5001, 8080, 3001, 8090, 8888, 5341}
)

# ── Role registry (config-driven, ADR-0004) ─────────────────────────────
# infra/deployment/roles.json is the single source of truth for the role
# vocabulary and its port ranges: which roles exist, where their host-port
# blocks start, their nodePort offsets, and their default container port.
# Consumers add roles (worker, scheduler, ...) there — no Python changes.
# _DEFAULT_ROLES below mirrors the shipped file and is used only as a
# fallback when the file is absent (bare checkout, unit fixtures); it must
# stay in sync with the committed infra/deployment/roles.json.
#   web: host 8081+, nodePort offset 80, container 80
#   api: host 5002+, nodePort offset 500, container 5000
#   database: host 5432+, nodePort offset 700, container 5432
_DEFAULT_ROLES: dict[str, dict[str, Any]] = {
    "web": {
        "hostPortBase": 8081,
        "nodePortOffset": 80,
        "containerPort": 80,
        "portEnv": False,
        "healthCheck": "http",
    },
    "api": {
        "hostPortBase": 5002,
        "nodePortOffset": 500,
        "containerPort": 5000,
        "portEnv": True,
        "healthCheck": "http",
    },
    "database": {
        "hostPortBase": 5432,
        "nodePortOffset": 700,
        "containerPort": 5432,
        "portEnv": False,
        "healthCheck": "tcp",
    },
}

# Host ports are allocated per ROLE in blocks of 10 anchored at the role
# base: block 0 = [base, base+9], block 1 = [base+10, base+19], ... When a
# block is full (or its slots collide with RESERVED_HOST_PORTS), the next
# block of 10 is used — the scheme scales past 10 ports of a role.
#   web: 8081-8090, 8091-8100, ...
#   api: 5002-5011, 5012-5021, ...
#   database: 5432-5441, 5442-5451, ...
HOST_PORT_BLOCK = 10

# NodePorts are allocated per ENV per ROLE in blocks of 10 anchored at
# env_code*1000 + role_offset. Environment codes keep the ranges disjoint
# (dev 30xxx, qa 31xxx, prod 32xxx) so nodePorts stay cluster-unique.
#   dev:  web 30080-30089, ... | api 30500-30509, ... | database 30700-30709, ...
#   qa:   web 31080-31089, ... | api 31500-31509, ... | database 31700-31709, ...
#   prod: web 32080-32089, ... | api 32500-32509, ... | database 32700-32709, ...
NODE_PORT_BLOCK = 10
ENV_NODE_CODES: dict[str, int] = {"dev": 30, "qa": 31, "prod": 32}
_NODE_PORT_UPPER = 32768  # K8s NodePort range ends at 32767 (exclusive bound)

# Kubernetes Service names must be DNS-1123 labels (no dots): the shared
# engine once shipped as ``db.internal`` and only failed on the real apply
# (`kubectl apply --dry-run=client` does not validate names server-side).
# Any ``serviceName`` override must satisfy this too, since it becomes the
# Service patch's metadata.name.
_DNS1123_LABEL = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")

def _role_for_app(root: Path, app_id: str) -> str | None:
    """Role fallback for an appId from the apps.json registry.

    The registry (infra/deployment/apps.json) is the canonical appId -> role
    source (ADR-0002). Only reached for ports.json entries that omit the
    explicit ``role`` key; ports.schema.json requires ``role``, so a missing
    one is a config error surfaced by load_ports.
    """
    try:
        apps_path = root / APPS_FILE
        if apps_path.exists():
            apps = json.loads(apps_path.read_text(encoding="utf-8")).get("apps", [])
            for app in apps:
                if app.get("appId") == app_id and app.get("role"):
                    return app["role"]
    except (OSError, ValueError):
        pass
    return None


def load_roles(root: Path) -> dict[str, dict[str, Any]]:
    """Load the role registry from infra/deployment/roles.json.

    The shipped file defines the built-in roles (web, api); consumers add
    their own (worker, scheduler, ...) with their port ranges without
    touching Python. A missing file (bare checkout / unit fixtures) falls
    back to the shipped defaults below; a present-but-invalid file raises
    ValueError so a config typo never silently re-defaults.
    """
    path = root / ROLES_FILE
    if not path.exists():
        return _DEFAULT_ROLES
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as ex:
        raise ValueError(f"{path}: invalid JSON: {ex}") from ex
    if data.get("version") != 1:
        raise ValueError(
            f"{path}: roles.json version must be 1, got {data.get('version')}"
        )
    roles = data.get("roles")
    if not isinstance(roles, dict) or not roles:
        raise ValueError(f"{path}: 'roles' object is missing or empty")
    for name, cfg in roles.items():
        if not isinstance(cfg, dict):
            raise ValueError(f"{path}: role {name!r} must be an object")
        for key in ("hostPortBase", "nodePortOffset", "containerPort"):
            if not isinstance(cfg.get(key), int):
                raise ValueError(
                    f"{path}: role {name!r} must define integer {key!r}"
                )
    return roles


def _role_bases(roles: dict[str, dict[str, Any]]) -> dict[str, int]:
    return {name: cfg["hostPortBase"] for name, cfg in roles.items()}


def _role_offsets(roles: dict[str, dict[str, Any]]) -> dict[str, int]:
    return {name: cfg["nodePortOffset"] for name, cfg in roles.items()}


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
    if "appPorts" not in data:
        raise ValueError(f"{path}: 'appPorts' key is missing")
    # Empty per-app assignments are valid: the template ships no reference apps
    # (ADR-0005), and the port scheme lives in infra/deployment/roles.json.
    envs = data.get("environments")
    if not envs:
        raise ValueError(f"{path}: 'environments' is missing or empty")

    # NodePorts are cluster-scoped: must be unique across ALL environments.
    seen_node: dict[int, str] = {}
    # HostPorts are host-scoped: must be unique across ALL environments too.
    seen_host: dict[int, str] = {}
    roles = load_roles(root)
    for env, apps in envs.items():
        for app, cfg in apps.items():
            np = cfg["nodePort"]
            if np in seen_node:
                raise ValueError(
                    f"{path}: NodePort collision - {np} used by {seen_node[np]} and {env}/{app}"
                )
            seen_node[np] = f"{env}/{app}"
            hp = cfg["hostPort"]
            if hp in seen_host:
                raise ValueError(
                    f"{path}: hostPort collision - {hp} used by {seen_host[hp]} and {env}/{app}"
                )
            seen_host[hp] = f"{env}/{app}"
            if hp in RESERVED_HOST_PORTS:
                raise ValueError(
                    f"{path}: hostPort {hp} for {env}/{app} collides with a lab "
                    f"service port (RESERVED_HOST_PORTS) — pick a free host port."
                )
            # Range checks: every app must resolve to a known role, and its
            # ports must stay inside the role/env block scheme. The role
            # vocabulary comes from infra/deployment/roles.json (ADR-0004).
            service = cfg.get("serviceName", app)
            if len(service) > 63 or not _DNS1123_LABEL.match(service):
                raise ValueError(
                    f"{path}: {env}/{app} serviceName {service!r} is not a valid "
                    "DNS-1123 label (lowercase alphanumerics and '-', no dots) — "
                    "kubectl apply will reject the Service patch."
                )
            role = cfg.get("role") or _role_for_app(root, app)
            if not role:
                raise ValueError(
                    f"{path}: {env}/{app} is missing a role — add \"role\" "
                    f"({', '.join(sorted(roles))}) or register the appId in apps.json."
                )
            if role not in roles:
                raise ValueError(
                    f"{path}: {env}/{app} has unknown role {role!r} — register it "
                    f"in infra/deployment/roles.json before assigning ports "
                    f"(known: {', '.join(sorted(roles))})."
                )
            base_hp = role_host_base(role, roles)
            if hp < base_hp:
                raise ValueError(
                    f"{path}: hostPort {hp} for {env}/{app} is below the {role!r} "
                    f"host-port range base {base_hp} (blocks of 10 "
                    f"starting at {base_hp})."
                )
            if env in ENV_NODE_CODES:
                base = env_node_base(env, role, roles)
                upper = min((ENV_NODE_CODES[env] + 1) * 1000, _NODE_PORT_UPPER)
                if not base <= np < upper:
                    raise ValueError(
                        f"{path}: nodePort {np} for {env}/{app} is outside the "
                        f"{role!r} {env} nodePort range [{base}, {upper}) "
                        f"(blocks of 10 starting at {base})."
                    )
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


def role_host_base(
    role: str, roles: dict[str, dict[str, Any]] | None = None
) -> int:
    """Base host port for a role (block 0 start). Unknown roles raise.

    ``roles`` optionally supplies the registry from infra/deployment/roles.json
    (load_roles); when omitted the shipped defaults apply.
    """
    bases = _role_bases(roles or _DEFAULT_ROLES)
    try:
        return bases[role]
    except KeyError:
        raise ValueError(
            f"no host-port range defined for role {role!r} "
            f"(known: {sorted(bases)})"
        ) from None


def env_node_base(
    env: str, role: str, roles: dict[str, dict[str, Any]] | None = None
) -> int:
    """Base nodePort for (env, role) — block 0 start.

    ``roles`` optionally supplies the registry from infra/deployment/roles.json
    (load_roles); when omitted the shipped defaults apply.
    """
    offsets = _role_offsets(roles or _DEFAULT_ROLES)
    try:
        return ENV_NODE_CODES[env] * 1000 + offsets[role]
    except KeyError:
        raise ValueError(
            f"no node-port range defined for env={env!r} role={role!r} "
            f"(envs: {sorted(ENV_NODE_CODES)}, roles: {sorted(offsets)})"
        ) from None


def role_host_block(role: str, block: int) -> tuple[int, int]:
    """Inclusive host-port block for a role: [start, end] (10 ports)."""
    start = role_host_base(role) + block * HOST_PORT_BLOCK
    return start, start + HOST_PORT_BLOCK - 1


def env_node_block(env: str, role: str, block: int) -> tuple[int, int]:
    """Inclusive nodePort block for (env, role): [start, end] (10 ports)."""
    start = env_node_base(env, role) + block * NODE_PORT_BLOCK
    return start, start + NODE_PORT_BLOCK - 1


def _first_free(
    used: set[int],
    start: int,
    upper: int,
    reserved: frozenset[int] = frozenset(),
) -> int:
    """First free port in [start, upper) skipping used + reserved (host only)."""
    for port in range(start, upper):
        if port in used or port in reserved:
            continue
        return port
    raise ValueError(f"no free port in [{start}, {upper}) — range exhausted")


def assign_app_ports(
    data: dict[str, Any],
    app_id: str,
    role: str,
    root: Path | None = None,
) -> dict[str, dict[str, int]]:
    """Allocate host/node ports for a new app across dev/qa/prod.

    Host ports come from the role's block sequence (10 per block anchored at
    the role base; reserved lab ports skipped). NodePorts come from the
    (env, role) block sequence (10 per block anchored at env_code*1000 +
    role_offset) — env codes keep them cluster-unique. Returns
    {env: {"hostPort": n, "nodePort": n}} in dev → qa → prod order.

    ``root`` optionally supplies infra/deployment/roles.json so consumer roles
    (worker, scheduler, ...) resolve; when omitted (or the file is absent)
    the shipped web/api defaults apply (ADR-0004).

    Idempotent: when the app already exists in every environment, returns its
    current ports unchanged. Raises when the app exists in only some envs
    (inconsistent ports.json) or the role has no defined range.
    """
    envs = data["environments"]
    present_all = all(app_id in envs.get(env, {}) for env in ENV_NODE_CODES)
    present_some = any(app_id in envs.get(env, {}) for env in ENV_NODE_CODES)
    if present_all:
        return {env: dict(envs[env][app_id]) for env in ENV_NODE_CODES}
    if present_some:
        raise ValueError(f"{app_id} exists in some environments only — ports.json is inconsistent")

    used_host: set[int] = set()
    used_node: set[int] = set()
    for env, apps in envs.items():
        for _app, cfg in apps.items():
            used_host.add(cfg["hostPort"])
            used_node.add(cfg["nodePort"])

    roles = load_roles(root) if root is not None else _DEFAULT_ROLES
    host_base = role_host_base(role, roles)
    allocations: dict[str, dict[str, int]] = {}
    for env in ENV_NODE_CODES:
        host_port = _first_free(used_host, host_base, 65536, RESERVED_HOST_PORTS)
        used_host.add(host_port)
        node_port = _first_free(
            used_node,
            env_node_base(env, role, roles),
            min((ENV_NODE_CODES[env] + 1) * 1000, _NODE_PORT_UPPER),
        )
        used_node.add(node_port)
        allocations[env] = {"hostPort": host_port, "nodePort": node_port}
    return allocations


def assign_app_ports_to_file(root: Path, app_id: str, role: str, dry_run: bool = False) -> dict[str, Any]:
    """CLI wrapper: assign ports for an app, persist to ports.json, regenerate artifacts."""
    result: dict[str, Any] = {
        "mode": "AssignAppPorts",
        "dryRun": dry_run,
        "valid": False,
        "app": app_id,
        "role": role,
        "actions": [],
        "findings": [],
    }
    try:
        data = load_ports(root)
        allocations = assign_app_ports(data, app_id, role, root)
    except (FileNotFoundError, ValueError) as ex:
        result["findings"].append(
            {"key": "ports.assign", "severity": "error", "message": str(ex)}
        )
        result["actions"].append(
            {"command": "assign-app-ports", "message": str(ex), "valid": False}
        )
        return result

    result["allocations"] = allocations
    if dry_run:
        result["valid"] = True
        result["actions"].append(
            {
                "command": "assign-app-ports",
                "message": f"Would assign {app_id} ({role}): " + json.dumps(allocations),
                "valid": True,
            }
        )
        return result

    for env, cfg in allocations.items():
        data["environments"][env][app_id] = {**cfg, "role": role}
    (root / PORTS_FILE).write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )
    write_artifacts(root)
    result["valid"] = True
    result["actions"].append(
        {
            "command": "assign-app-ports",
            "message": (
                f"Assigned {app_id} ({role}): " + json.dumps(allocations)
                + " — ports.json and generated artifacts updated."
            ),
            "valid": True,
        }
    )
    return result


def kind_config_yaml(
    data: dict[str, Any], roles: dict[str, dict[str, Any]] | None = None
) -> str:
    """Render infra/k8s/kind-config.yaml (extraPortMappings) from ports.json.

    Environment/app order follows the canonical environments dict (dev, qa,
    prod) with app order from each env entry, so output is stable and matches
    the committed file ordering. ``roles`` (load_roles) drives the range
    comments; omitted → shipped defaults (ADR-0004).
    """
    roles = roles or _DEFAULT_ROLES
    host_desc = ", ".join(
        f"{name} from {cfg['hostPortBase']}" for name, cfg in roles.items()
    )
    node_desc = ", ".join(
        f"{env} "
        + "/".join(
            str(ENV_NODE_CODES[env] * 1000 + cfg["nodePortOffset"])
            for cfg in roles.values()
        )
        for env in ("dev", "qa", "prod")
    )
    lines = [
        "# Kind cluster config for sdd-cluster",
        "# extraPortMappings enable direct host access to NodePort services",
        "# without needing kubectl port-forward.",
        "#",
        "# Host port -> NodePort -> Service",
    ]
    for env, apps in data["environments"].items():
        for app, cfg in apps.items():
            role = cfg.get("role", "web")
            lines.append(
                f"#  {cfg['hostPort']}    ->  {cfg['nodePort']}   -> {app} {env.upper()} ({role})"
            )
    lines.append("# NodePorts are per-environment and cluster-scoped (per-env fix, PR #6).")
    lines.append("# Generated from infra/deployment/ports.json (tools/sdd_cli/k8s_ports.py).")
    reserved = ", ".join(str(p) for p in sorted(RESERVED_HOST_PORTS))
    lines.append("# Reserved lab host ports (compose services), hostPorts must avoid:")
    lines.append(f"#   {reserved}")
    lines.append(f"# Host ports: per-role blocks of 10 ({host_desc}).")
    lines.append(f"# NodePorts: per-env per-role blocks of 10 ({node_desc}).")
    lines.append("kind: Cluster")
    lines.append("apiVersion: kind.x-k8s.io/v1alpha4")
    lines.append("nodes:")
    lines.append("  - role: control-plane")
    mappings = [
        (cfg["nodePort"], cfg["hostPort"])
        for env, apps in data["environments"].items()
        for app, cfg in apps.items()
    ]
    if mappings:
        lines.append("    extraPortMappings:")
        for node_port, host_port in mappings:
            lines.append("      - containerPort: %d" % node_port)
            lines.append("        hostPort: %d" % host_port)
            lines.append("        protocol: TCP")
    return "\n".join(lines) + "\n"


def service_patch_yaml(
    data: dict[str, Any], env: str, roles: dict[str, dict[str, Any]] | None = None
) -> str:
    """Render infra/k8s/overlays/{env}/service-patch.yaml from ports.json.

    Each block patches the Service named by ``app`` (or its ``serviceName``
    override — infra services like the shared database register as
    ``database`` but expose ``db``) to the env's NodePort, forcing
    ``type: NodePort`` so kind extraPortMappings can reach it. The container
    port comes from ``appPorts`` when present, else the role's containerPort
    (roles.json / shipped defaults) — the shared database is 5432.
    """
    roles = roles or _DEFAULT_ROLES
    blocks = []
    for app in data["environments"][env]:
        cfg = data["environments"][env][app]
        service = cfg.get("serviceName", app)
        container_port = data["appPorts"].get(
            app, role_container_port(cfg.get("role", "web"), roles)
        )
        blocks.append(
            "apiVersion: v1\n"
            "kind: Service\n"
            "metadata:\n"
            f"  name: {service}\n"
            "spec:\n"
            "  type: NodePort\n"
            "  ports:\n"
            "    - port: %d\n"
            "      targetPort: %d\n"
            "      protocol: TCP\n"
            "      nodePort: %d" % (container_port, container_port, cfg["nodePort"])
        )
    return "\n---\n".join(blocks) + "\n"


def role_container_port(
    role: str, roles: dict[str, dict[str, Any]] | None = None
) -> int:
    """Default container port for a role (scaffold fallback for appPorts)."""
    roles = roles or _DEFAULT_ROLES
    try:
        return int(roles[role]["containerPort"])
    except (KeyError, TypeError):
        raise ValueError(
            f"no container port defined for role {role!r} "
            f"(known: {sorted(roles)})"
        ) from None


def render_all(root: Path) -> dict[str, Path]:
    """Return {label: path} for every artifact derived from ports.json.

    Service patches are only rendered for environments that actually have apps
    (the template ships none — ADR-0005 — so no empty patch files are written).
    """
    data = load_ports(root)
    patch_envs = [env for env, apps in data["environments"].items() if apps]
    return {
        "kind-config": root / KIND_CONFIG,
        **{
            f"service-patch-{env}": root / OVERLAY_DIR / env / "service-patch.yaml"
            for env in patch_envs
        },
    }


def write_artifacts(root: Path) -> dict[str, Path]:
    """Regenerate all port-derived artifacts from ports.json (idempotent).

    Files are written with LF endings (matching the git index) so re-runs and
    `git status` stay clean on Windows checkouts.
    """
    data = load_ports(root)
    roles = load_roles(root)
    targets = render_all(root)
    (root / OVERLAY_DIR).mkdir(parents=True, exist_ok=True)
    for env in data["environments"]:
        (root / OVERLAY_DIR / env).mkdir(parents=True, exist_ok=True)
    (root / KIND_CONFIG).parent.mkdir(parents=True, exist_ok=True)

    (root / KIND_CONFIG).write_text(kind_config_yaml(data, roles), encoding="utf-8")
    for env, apps in data["environments"].items():
        if not apps:
            continue  # no apps in this env (ADR-0005) — no patch to write
        (root / OVERLAY_DIR / env / "service-patch.yaml").write_text(
            service_patch_yaml(data, env, roles), encoding="utf-8"
        )
    return targets
