"""SDD lab health probe — serves real service health as JSON for Grafana.

The Grafana "Service Health" panel (Infinity datasource) polls this endpoint on
every refresh. Each probe runs concurrently against the target from inside the
Docker network (host.docker.internal reaches the host, where kind nodePorts are
published). Runs as the `health-probe` compose service on port 8090.

Direct URLs use `localhost` with the host-remapped port (valid on the host when
the service is deployed). Unreachable endpoints are reported as "Not deployed"
so the dashboard never lies: green means the /health endpoint actually responds.

Endpoints:
    GET /health  -> {"services": [ {...}, ... ]}
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen

HOST = "0.0.0.0"
PORT = 8090
TIMEOUT_SECONDS = 4.0

# env | service label | probe url (reachable from inside the container) | direct url (host) | health path | k8s nodePort
# PROD host ports follow the DEV->QA convention; no PROD cluster is configured yet.
SERVICES = [
    {"env": "DEV", "service": "Frontend (React)", "probeUrl": "http://host.docker.internal:8081", "directUrl": "http://localhost:8081", "healthPath": "/health", "nodePort": "30080"},
    {"env": "DEV", "service": "Backend (.NET API)", "probeUrl": "http://host.docker.internal:5002", "directUrl": "http://localhost:5002", "healthPath": "/health", "nodePort": "30500"},
    {"env": "QA", "service": "Frontend (React)", "probeUrl": "http://host.docker.internal:8082", "directUrl": "http://localhost:8082", "healthPath": "/health", "nodePort": "30081"},
    {"env": "QA", "service": "Backend (.NET API)", "probeUrl": "http://host.docker.internal:5003", "directUrl": "http://localhost:5003", "healthPath": "/health", "nodePort": "30501"},
    {"env": "PROD", "service": "Frontend (React)", "probeUrl": "http://host.docker.internal:8083", "directUrl": "http://localhost:8083", "healthPath": "/health", "nodePort": "30082"},
    {"env": "PROD", "service": "Backend (.NET API)", "probeUrl": "http://host.docker.internal:5004", "directUrl": "http://localhost:5004", "healthPath": "/health", "nodePort": "30502"},
]


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
