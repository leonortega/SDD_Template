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

# DEV-flavored render: frontend/backend both pinned to DEV nodePorts.
RENDERED = """\
apiVersion: v1
kind: Service
metadata:
  name: frontend
spec:
  ports:
    - port: 80
      targetPort: 80
      nodePort: 30080
---
apiVersion: v1
kind: Service
metadata:
  name: backend
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
            "resources:\n  - ../../../../apps/frontend/deploy\n", encoding="utf-8"
        )


def _write_canonical_ports(tmp_path) -> None:
    """Seed the repo's own canonical ports.json (valid by construction)."""
    src = REPO_ROOT / "infra" / "deployment" / "ports.json"
    dst = tmp_path / "infra" / "deployment" / "ports.json"
    dst.parent.mkdir(parents=True)
    shutil.copy(src, dst)


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
    _write_canonical_ports(tmp_path)

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
    _write_canonical_ports(tmp_path)

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


# ── Committed overlay composition guard (ADR-0002) ───────────────────────


def test_committed_overlays_compose_app_deploy_dirs() -> None:
    """Every committed env overlay composes apps/<appId>/deploy via relative
    Kustomize refs that resolve on disk — the infra/k8s/base/ layout is gone."""
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
                f"{env}: {res} does not resolve to an app deploy dir"
            )
    assert not (root / "infra" / "k8s" / "base").exists(), "infra/k8s/base/ must be deleted"
