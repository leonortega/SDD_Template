"""SDD lab health probe — serves real service health as JSON for Grafana.

The Grafana "Service Health" panel (Infinity datasource) polls this endpoint on
every refresh. Each probe runs concurrently against the target from inside the
Docker network, reaching the kind node directly
(sdd-cluster-control-plane:<nodePort>) — NOT host extraPortMappings, which are
only bound at cluster creation time and go stale when kind-config changes.
Runs as the `health-probe` compose service on port 8090.

Direct URLs use `localhost` with the host-remapped port (valid on the host when
the service is deployed). Unreachable endpoints are reported as "Not deployed"
so the dashboard never lies: green means the /health endpoint actually responds.

NodePorts and host ports come from the canonical infra/deployment/ports.json
(mounted read-only by infra/monitoring/compose.yml). When that file is not
available (e.g. running the script standalone outside the lab), the probe
falls back to the hardcoded default port map below — keeping the service
self-contained.

Endpoints:
    GET /health  -> {"services": [ {...}, ... ]}
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

HOST = "0.0.0.0"
PORT = 8090
TIMEOUT_SECONDS = 4.0

# Default port map (used only when infra/deployment/ports.json is unavailable).
# NodePorts are per-environment and cluster-scoped (per-env fix, PR #6):
#   DEV  30080/30500 | QA  31080/31500 | PROD  32080/32500
# The probe reaches the kind node directly (sdd-cluster-control-plane:<nodePort>)
# instead of relying on host-port extraPortMappings.
_DEFAULT_PORTS = {
    "dev": {"frontend": {"hostPort": 8081, "nodePort": 30080}, "backend": {"hostPort": 5002, "nodePort": 30500}},
    "qa": {"frontend": {"hostPort": 8082, "nodePort": 31080}, "backend": {"hostPort": 5003, "nodePort": 31500}},
    "prod": {"frontend": {"hostPort": 8083, "nodePort": 32080}, "backend": {"hostPort": 5004, "nodePort": 32500}},
}

# Canonical source of truth: infra/deployment/ports.json (see tools/sdd_cli/k8s_ports.py).
_PORTS_FILE = Path("/app/ports.json")
_SERVICE_LABELS = {"frontend": "Frontend (React)", "backend": "Backend (.NET API)"}


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


def build_services(ports: dict | None = None) -> list[dict]:
    """Build the probe target list from the port map (canonical or fallback).

    Returns the same schema the Grafana dashboard consumes: env label, service
    label, probe URL (kind node DNS), direct URL (localhost host port), health
    path, and the K8s nodePort.
    """
    ports = ports if ports is not None else _load_ports()
    services = []
    for env, apps in ports.items():
        for app_id, cfg in apps.items():
            node_port = cfg["nodePort"]
            host_port = cfg["hostPort"]
            services.append(
                {
                    "env": env.upper(),
                    "service": _SERVICE_LABELS.get(app_id, app_id.title()),
                    "probeUrl": f"http://sdd-cluster-control-plane:{node_port}",
                    "directUrl": f"http://localhost:{host_port}",
                    "healthPath": "/health",
                    "nodePort": str(node_port),
                }
            )
    # Stable ordering: DEV, QA, PROD × frontend, backend.
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
    target = service["probeUrl"] + service["healthPath"]
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
