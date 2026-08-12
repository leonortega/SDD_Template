"""Tests for the Kustomize overlay validation gate (tools/sdd_cli/k8s_validate.py).

Ported from SDD_Test with the pr-validation.yml gate (E2EPROJECT-37 finding 3):
renders every env overlay and asserts buildability, cluster-scoped NodePort
uniqueness, and drift against infra/deployment/ports.json.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.sdd_cli import k8s_validate

REPO_ROOT = Path(__file__).resolve().parents[3]

# DEV-flavored render: app-web/app-api both pinned to DEV nodePorts.
RENDERED = """\
apiVersion: v1
kind: Service
metadata:
  name: app-web
spec:
  ports:
    - port: 80
      targetPort: 80
      nodePort: 30080
---
apiVersion: v1
kind: Service
metadata:
  name: app-api
spec:
  ports:
    - port: 5000
      targetPort: 5000
      nodePort: 30500
"""


def _write_overlay_dirs(tmp_path) -> None:
    """Minimal overlay dirs in the ADR-0002 composed shape (kustomize is mocked
    in these tests, so the relative refs never need to resolve)."""
    for env in ("dev", "qa", "prod"):
        overlay = tmp_path / "infra" / "k8s" / "overlays" / env
        overlay.mkdir(parents=True)
        (overlay / "kustomization.yaml").write_text(
            "resources:\n  - ../../shared/database\n"
            "  - ../../../../apps/app-web/deploy\n",
            encoding="utf-8",
        )
    (tmp_path / "infra" / "k8s" / "shared" / "database").mkdir(parents=True)
    (tmp_path / "infra" / "k8s" / "shared" / "database" / "kustomization.yaml").write_text(
        "resources:\n  - statefulset.yaml\n", encoding="utf-8"
    )


# Fixture ports with concrete apps (the shipped ports.json is empty —
# ADR-0005 — so these overlay tests seed their own canonical config).
FIXTURE_PORTS = {
    "version": 1,
    "registry": "host.docker.internal:5001",
    "appPorts": {"app-web": 80, "app-api": 5000},
    "environments": {
        "dev": {
            "app-web": {"hostPort": 8081, "nodePort": 30080, "role": "web"},
            "app-api": {"hostPort": 5002, "nodePort": 30500, "role": "api"},
        },
        "qa": {
            "app-web": {"hostPort": 8082, "nodePort": 31080, "role": "web"},
            "app-api": {"hostPort": 5003, "nodePort": 31500, "role": "api"},
        },
        "prod": {
            "app-web": {"hostPort": 8083, "nodePort": 32080, "role": "web"},
            "app-api": {"hostPort": 5004, "nodePort": 32500, "role": "api"},
        },
    },
}


def _write_ports_dict(tmp_path, data: dict) -> None:
    dst = tmp_path / "infra" / "deployment" / "ports.json"
    dst.parent.mkdir(parents=True)
    dst.write_text(json.dumps(data), encoding="utf-8")


def test_dry_run_plans_without_running_kustomize(tmp_path) -> None:
    result = k8s_validate.validate_overlays(tmp_path, dry_run=True)
    assert result["valid"] is True
    assert any(a["key"] == "validate.plan" for a in result["actions"])


def test_missing_pyyaml_is_a_loud_error(tmp_path) -> None:
    with patch.object(k8s_validate, "_yaml", None):
        result = k8s_validate.validate_overlays(tmp_path, dry_run=False)
    assert result["valid"] is False
    assert any(f.get("key") == "missing" for f in result["findings"])


def test_collision_and_drift_are_detected(tmp_path) -> None:
    """Every env renders the DEV nodePorts → cross-env collision + ports.json drift."""
    pytest.importorskip("yaml")
    _write_overlay_dirs(tmp_path)
    _write_ports_dict(tmp_path, FIXTURE_PORTS)  # qa/prod canonical ≠ DEV render → drift

    calls: list[str] = []

    def fake_run_native(command, root, timeout=30):
        env = str(command[-1]).replace("\\", "/").split("/")[-1]
        calls.append(env)
        return {"returncode": 0, "stdout": RENDERED, "stderr": ""}

    with patch("tools.sdd_cli.k8s_validate.run_native", side_effect=fake_run_native):
        result = k8s_validate.validate_overlays(tmp_path, dry_run=False)

    assert calls == ["dev", "qa", "prod"]
    keys = {f.get("key") for f in result["findings"]}
    assert "nodeport.collision" in keys
    assert "nodeport.drift" in keys
    assert result["valid"] is False


def test_clean_overlays_pass(tmp_path) -> None:
    """Rendered nodePorts matching ports.json → no findings, valid=True."""
    pytest.importorskip("yaml")
    _write_overlay_dirs(tmp_path)
    _write_ports_dict(tmp_path, FIXTURE_PORTS)

    ports = json.loads((tmp_path / "infra" / "deployment" / "ports.json").read_text())

    def fake_run_native(command, root, timeout=30):
        env = str(command[-1]).replace("\\", "/").split("/")[-1]
        docs = []
        for app, cfg in ports["environments"][env].items():
            app_port = ports["appPorts"].get(app, 80)
            docs.append(
                f"apiVersion: v1\nkind: Service\nmetadata:\n  name: {app}\n"
                f"spec:\n  ports:\n    - port: {app_port}\n"
                f"      targetPort: {app_port}\n      nodePort: {cfg['nodePort']}\n"
            )
        return {"returncode": 0, "stdout": "\n---\n".join(docs), "stderr": ""}

    with patch("tools.sdd_cli.k8s_validate.run_native", side_effect=fake_run_native):
        result = k8s_validate.validate_overlays(tmp_path, dry_run=False)

    assert result["valid"] is True
    assert result["findings"] == []


def test_drift_matches_service_name_override(tmp_path) -> None:
    """A ports.json entry rendered under its serviceName override (the shared
    database registers as 'database' but its Service renders as 'db.internal')
    must match the canonical nodePort instead of being flagged as missing."""
    pytest.importorskip("yaml")
    _write_overlay_dirs(tmp_path)
    # Database role: nodePortOffset 700 + 1000 per env (dev 30700, qa 31700,
    # prod 32700); hostPort must also be unique across envs.
    ports = {
        "version": 1,
        "registry": "host.docker.internal:5001",
        "appPorts": {},
        "environments": {
            env: {
                "database": {
                    "hostPort": 5432 + i,
                    "nodePort": 30700 + i * 1000,
                    "role": "database",
                    "serviceName": "db.internal",
                }
            }
            for i, env in enumerate(("dev", "qa", "prod"))
        },
    }
    _write_ports_dict(tmp_path, ports)

    def fake_run_native(command, root, timeout=30):
        env = str(command[-1]).replace("\\", "/").split("/")[-1]
        cfg = ports["environments"][env]["database"]
        doc = (
            "apiVersion: v1\nkind: Service\nmetadata:\n  name: db.internal\n"
            "spec:\n  ports:\n    - port: 5432\n      targetPort: 5432\n"
            f"      nodePort: {cfg['nodePort']}\n"
        )
        return {"returncode": 0, "stdout": doc, "stderr": ""}

    with patch("tools.sdd_cli.k8s_validate.run_native", side_effect=fake_run_native):
        result = k8s_validate.validate_overlays(tmp_path, dry_run=False)

    assert result["valid"] is True, [f["message"] for f in result["findings"]]
    assert result["findings"] == []


# ── Committed overlay composition guard (ADR-0002) ───────────────────────


def test_committed_overlays_compose_app_deploy_dirs() -> None:
    """Every committed env overlay composes apps/<appId>/deploy via relative
    Kustomize refs that resolve on disk — the infra/k8s/base/ layout is gone,
    and the shared database resource (ADR-0003) resolves to its own dir."""
    yaml = pytest.importorskip("yaml")
    root = REPO_ROOT
    for env in ("dev", "qa", "prod"):
        kus = root / "infra" / "k8s" / "overlays" / env / "kustomization.yaml"
        data = yaml.safe_load(kus.read_text(encoding="utf-8"))
        resources = data.get("resources") or []
        assert resources, f"{env} overlay lists no composed resources"
        for res in resources:
            assert res != "../../base", f"{env} still references the deleted base dir"
            target = (kus.parent / res).resolve()
            assert (target / "kustomization.yaml").is_file(), (
                f"{env}: {res} does not resolve to a kustomization dir"
            )
    # ADR-0003: the shared database dir is composed into every env overlay.
    for env in ("dev", "qa", "prod"):
        kus = root / "infra" / "k8s" / "overlays" / env / "kustomization.yaml"
        data = yaml.safe_load(kus.read_text(encoding="utf-8"))
        assert "../../shared/database" in (data.get("resources") or []), (
            f"{env} overlay does not compose the shared database"
        )
    assert (root / "infra" / "k8s" / "shared" / "database" / "kustomization.yaml").is_file()
    assert not (root / "infra" / "k8s" / "base").exists(), "infra/k8s/base/ must be deleted"
