"""SDD lab health probe — serves real service health as JSON for Grafana.

The Grafana "Service Health" panel (Infinity datasource) polls this endpoint on
every refresh. Each probe runs concurrently against the EXTERNAL URL users
navigate — the host-remapped port (`http://host.docker.internal:<hostPort>`),
which from the Windows host is the same endpoint as the directUrl shown in the
dashboard (`http://localhost:<hostPort>`). Status therefore reflects real
user-facing reachability, not just internal cluster connectivity.

`host.docker.internal` is provided by Docker Desktop (Windows/macOS) and by the
`extra_hosts` entry in compose.yml on Linux hosts; override with the PROBE_HOST
environment variable when the host address differs.

Runs as the `health-probe` compose service on port 8090.

Direct URLs use `localhost` with the host-remapped port (valid on the host when
the service is deployed). Unreachable endpoints are reported as "Not deployed"
so the dashboard never lies: green means the external /health endpoint actually
responds.

Host ports come from the canonical infra/deployment/ports.json (mounted
read-only by infra/monitoring/compose.yml). When that file is not available
(e.g. running the script standalone outside the lab), the probe falls back to
the hardcoded default port map below — keeping the service self-contained.

Endpoints:
    GET /health  -> {"services": [ {...}, ... ]}
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

HOST = "0.0.0.0"
PORT = 8090
TIMEOUT_SECONDS = 4.0

# Host the probe uses to reach the externally published ports. From inside a
# container, `host.docker.internal` maps to the Docker host where the kind
# extraPortMappings are bound — the same endpoints users navigate on
# localhost:<hostPort>.
PROBE_HOST = os.environ.get("PROBE_HOST", "host.docker.internal")

# Default port map (used only when infra/deployment/ports.json is unavailable).
# The template ships only the shared database (ADR-0003/0005), so the
# standalone fallback carries just its per-env ports — services appear once
# a consumer registers apps and the mounted ports.json carries them all.
_DEFAULT_PORTS: dict = {
    "dev": {
        "database": {"hostPort": 5432, "nodePort": 30700, "role": "database"}
    },
    "qa": {
        "database": {"hostPort": 5433, "nodePort": 31700, "role": "database"}
    },
    "prod": {
        "database": {"hostPort": 5434, "nodePort": 32700, "role": "database"}
    },
}

# Role -> health-check type (mirrors infra/deployment/roles.json healthCheck;
# used when roles.json is not mounted alongside ports.json). Databases and
# other non-HTTP services are checked with a raw TCP connect.
_DEFAULT_ROLE_CHECKS: dict = {"web": "http", "api": "http", "database": "tcp"}

# Canonical source of truth: infra/deployment/ports.json (see tools/sdd_cli/k8s_ports.py).
_PORTS_FILE = Path("/app/ports.json")
_ROLES_FILE = Path("/app/roles.json")
# Optional appId -> display label; unknown apps fall back to the title-cased id.
_SERVICE_LABELS: dict = {"database": "Database"}


def _load_ports() -> dict:
    """Load the canonical port map, falling back to defaults on any error."""
    try:
        if _PORTS_FILE.exists():
            data = json.loads(_PORTS_FILE.read_text(encoding="utf-8"))
            environments = data.get("environments")
            if environments and "dev" in environments:
                return environments
    except (OSError, json.JSONDecodeError):
        pass
    return _DEFAULT_PORTS


def _load_role_checks() -> dict:
    """Load role -> healthCheck from roles.json, falling back to defaults."""
    try:
        if _ROLES_FILE.exists():
            data = json.loads(_ROLES_FILE.read_text(encoding="utf-8"))
            roles = data.get("roles")
            if isinstance(roles, dict):
                return {
                    name: (cfg.get("healthCheck") if isinstance(cfg, dict) else None)
                    for name, cfg in roles.items()
                }
    except (OSError, json.JSONDecodeError):
        pass
    return _DEFAULT_ROLE_CHECKS


def build_services(ports: dict | None = None) -> list[dict]:
    """Build the probe target list from the port map (canonical or fallback).

    Returns the same schema the Grafana dashboard consumes: env label, service
    label, external probe URL (host.docker.internal:<hostPort>), direct URL
    (localhost host port), health path, and the K8s nodePort (display only).
    """
    ports = ports if ports is not None else _load_ports()
    role_checks = _load_role_checks()
    services = []
    for env, apps in ports.items():
        for app_id, cfg in apps.items():
            node_port = cfg["nodePort"]
            host_port = cfg["hostPort"]
            role = cfg.get("role", "web")
            check = role_checks.get(role, "http")
            if check == "tcp":
                services.append(
                    {
                        "env": env.upper(),
                        "service": _SERVICE_LABELS.get(app_id, app_id.title()),
                        "externalHost": PROBE_HOST,
                        "externalPort": host_port,
                        "directUrl": f"http://localhost:{host_port}",
                        "healthPath": "tcp",
                        "nodePort": str(node_port),
                        "check": "tcp",
                    }
                )
            else:
                services.append(
                    {
                        "env": env.upper(),
                        "service": _SERVICE_LABELS.get(app_id, app_id.title()),
                        "externalUrl": f"http://{PROBE_HOST}:{host_port}",
                        "directUrl": f"http://localhost:{host_port}",
                        "healthPath": "/health",
                        "nodePort": str(node_port),
                        "check": "http",
                    }
                )
    # Stable ordering: DEV, QA, PROD.
    order = {"dev": 0, "qa": 1, "prod": 2}
    return sorted(services, key=lambda s: (order.get(s["env"].lower(), 9), s["service"]))


SERVICES = build_services()


def probe(service: dict) -> dict:
    """Return the service dict plus live status and http code."""
    result = {
        "env": service["env"],
        "service": service["service"],
        "directUrl": service["directUrl"],
        "healthPath": service["healthPath"],
        "nodePort": service["nodePort"],
        "status": "Not deployed",
        "http": "-",
    }
    if service.get("check") == "tcp":
        # Non-HTTP service (e.g. the shared database): a TCP connect to the
        # host-remapped port proves reachability — no HTTP status to read.
        import socket

        host = service["externalHost"]
        port = service["externalPort"]
        try:
            with socket.create_connection((host, port), timeout=TIMEOUT_SECONDS):
                result["http"] = "TCP"
                result["status"] = "UP"
        except OSError:
            pass  # refused / timeout / dns -> Not deployed
        return result
    target = service["externalUrl"] + service["healthPath"]
    try:
        with urlopen(Request(target, method="GET"), timeout=TIMEOUT_SECONDS) as resp:
            result["http"] = str(resp.status)
            result["status"] = "UP" if 200 <= resp.status < 400 else "DOWN"
    except Exception:
        pass  # connection refused / timeout / dns -> Not deployed
    return result


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (http.server convention)
        if self.path.split("?")[0] != "/health":
            self.send_response(404)
            self.end_headers()
            return
        with ThreadPoolExecutor(max_workers=len(SERVICES)) as pool:
            rows = list(pool.map(probe, SERVICES))
        body = json.dumps({"services": rows}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # noqa: N802
        pass


if __name__ == "__main__":
    print(f"Health probe listening on http://{HOST}:{PORT}/health", flush=True)
    ThreadingHTTPServer((HOST, PORT), HealthHandler).serve_forever()
