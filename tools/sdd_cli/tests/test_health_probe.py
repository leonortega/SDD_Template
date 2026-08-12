"""Tests for infra/monitoring/health_probe.py (database TCP check + per-env rows).

The probe serves the JSON that feeds the Grafana Service Health panel. The
shared database (role `database`, healthCheck tcp) must appear once per
environment and be checked with a TCP connect instead of an HTTP GET.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

PROBE = Path(__file__).resolve().parents[3] / "infra" / "monitoring"
sys.path.insert(0, str(PROBE))

import health_probe  # noqa: E402


def _ports() -> dict:
    return {
        "dev": {"database": {"hostPort": 5432, "nodePort": 30700, "role": "database"}},
        "qa": {"database": {"hostPort": 5433, "nodePort": 31700, "role": "database"}},
        "prod": {
            "database": {"hostPort": 5434, "nodePort": 32700, "role": "database"}
        },
    }


def test_build_services_emits_database_row_per_env() -> None:
    services = health_probe.build_services(_ports())
    assert [s["env"] for s in services] == ["DEV", "QA", "PROD"]
    for s in services:
        assert s["service"] == "Database"
        assert s["check"] == "tcp"
        assert s["healthPath"] == "tcp"
        assert s["nodePort"].isdigit()


def test_build_services_http_apps_keep_http_check() -> None:
    ports = {
        "dev": {
            "app-web": {"hostPort": 8081, "nodePort": 30080, "role": "web"},
        }
    }
    services = health_probe.build_services(ports)
    assert len(services) == 1
    assert services[0]["check"] == "http"
    assert services[0]["healthPath"] == "/health"
    assert "externalUrl" in services[0]


def test_probe_tcp_success_marks_up() -> None:
    service = health_probe.build_services(_ports())[0]
    with patch("socket.create_connection") as mock_conn:
        mock_conn.return_value.__enter__ = lambda self: self
        mock_conn.return_value.__exit__ = lambda *a: False
        result = health_probe.probe(service)
    assert result["status"] == "UP"
    assert result["http"] == "TCP"


def test_probe_tcp_refused_is_not_deployed() -> None:
    service = health_probe.build_services(_ports())[0]
    with patch("socket.create_connection", side_effect=OSError("refused")):
        result = health_probe.probe(service)
    assert result["status"] == "Not deployed"
    assert result["http"] == "-"
