"""Tests for k8s_ports: canonical ports.json validation + artifact generation.

Covers the hardening added to load_ports (nodePort AND hostPort uniqueness,
reserved lab-port collisions), deterministic artifact rendering, and a guard
that the committed infra/k8s artifacts never drift from the generator output.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.sdd_cli.k8s_ports import (
    RESERVED_HOST_PORTS,
    assign_app_ports,
    assign_app_ports_to_file,
    env_node_block,
    kind_config_yaml,
    load_ports,
    role_host_base,
    role_host_block,
    service_patch_yaml,
    write_artifacts,
)

def _valid_ports() -> dict:
    """Fresh, deeply-independent ports fixture per call (tests mutate nested
    entries — a shared module-level dict would corrupt later tests)."""
    return {
        "version": 1,
        "registry": "host.docker.internal:5001",
        "appPorts": {"frontend": 80, "backend": 5000},
        "environments": {
            "dev": {
                "frontend": {"hostPort": 8081, "nodePort": 30080},
                "backend": {"hostPort": 5002, "nodePort": 30500},
            },
            "qa": {
                "frontend": {"hostPort": 8082, "nodePort": 31080},
                "backend": {"hostPort": 5003, "nodePort": 31500},
            },
            "prod": {
                "frontend": {"hostPort": 8083, "nodePort": 32080},
                "backend": {"hostPort": 5004, "nodePort": 32500},
            },
        },
    }


def _write_ports(root: Path, data: dict) -> Path:
    path = root / "infra" / "deployment" / "ports.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _read_artifact(path: Path) -> str:
    """Read a committed artifact, normalizing CRLF so Windows checkouts
    compare cleanly against the LF-only generator output."""
    return path.read_text(encoding="utf-8").replace("\r\n", "\n").strip()


# ── load_ports validation ────────────────────────────────────────────────


def test_load_ports_accepts_valid(tmp_path: Path) -> None:
    _write_ports(tmp_path, _valid_ports())
    data = load_ports(tmp_path)
    assert data["environments"]["prod"]["frontend"]["hostPort"] == 8083


def test_load_ports_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_ports(tmp_path)


def test_load_ports_bad_version(tmp_path: Path) -> None:
    data = _valid_ports()
    data["version"] = 2
    _write_ports(tmp_path, data)
    with pytest.raises(ValueError, match="version must be 1"):
        load_ports(tmp_path)


def test_load_ports_nodeport_collision_across_envs(tmp_path: Path) -> None:
    """NodePorts are cluster-scoped — the same nodePort in two envs must fail."""
    data = _valid_ports()
    data["environments"]["qa"]["frontend"]["nodePort"] = 30080  # dup of dev
    _write_ports(tmp_path, data)
    with pytest.raises(ValueError, match="NodePort collision"):
        load_ports(tmp_path)


def test_load_ports_hostport_collision_across_envs(tmp_path: Path) -> None:
    """HostPorts are host-scoped — the same hostPort in two envs must fail."""
    data = _valid_ports()
    data["environments"]["qa"]["frontend"]["hostPort"] = 8081  # dup of dev
    _write_ports(tmp_path, data)
    with pytest.raises(ValueError, match="hostPort collision"):
        load_ports(tmp_path)


@pytest.mark.parametrize("reserved", sorted(RESERVED_HOST_PORTS))
def test_load_ports_reserved_hostport_rejected(tmp_path: Path, reserved: int) -> None:
    """hostPorts must not collide with lab compose services (RESERVED_HOST_PORTS)."""
    data = _valid_ports()
    data["environments"]["prod"]["backend"]["hostPort"] = reserved
    _write_ports(tmp_path, data)
    with pytest.raises(ValueError, match="RESERVED_HOST_PORTS"):
        load_ports(tmp_path)


def test_reserved_host_ports_cover_lab_services() -> None:
    """Every lab compose host port must be reserved (keeps the guard honest)."""
    # Gitea, Nexus, OpenProject, monitoring host ports from their compose files.
    lab_ports = {3000, 2222, 8123, 8088, 5001, 8080, 3001, 8090, 8888, 5341}
    assert lab_ports.issubset(RESERVED_HOST_PORTS)


# ── Artifact generation ──────────────────────────────────────────────────


def test_kind_config_yaml_renders_all_mappings(tmp_path: Path) -> None:
    _write_ports(tmp_path, _valid_ports())
    text = kind_config_yaml(load_ports(tmp_path))
    assert "hostPort: 8081" in text and "containerPort: 30080" in text
    assert "hostPort: 5004" in text and "containerPort: 32500" in text
    # Deterministic: same input → identical output.
    assert kind_config_yaml(load_ports(tmp_path)) == text


def test_service_patch_yaml_per_env(tmp_path: Path) -> None:
    _write_ports(tmp_path, _valid_ports())
    dev = service_patch_yaml(load_ports(tmp_path), "dev")
    assert "name: frontend" in dev and "nodePort: 30080" in dev
    assert "name: backend" in dev and "nodePort: 30500" in dev
    prod = service_patch_yaml(load_ports(tmp_path), "prod")
    assert "nodePort: 32080" in prod and "nodePort: 32500" in prod
    # Deterministic.
    assert service_patch_yaml(load_ports(tmp_path), "dev") == dev


def test_write_artifacts_idempotent(tmp_path: Path) -> None:
    """Regenerating artifacts twice must not change the files (drift-free)."""
    _write_ports(tmp_path, _valid_ports())
    first = write_artifacts(tmp_path)
    before = {p: p.read_bytes() for p in first.values()}
    write_artifacts(tmp_path)
    for path, content in before.items():
        assert path.read_bytes() == content, f"{path} changed on re-run"


# ── kind port drift detection (k8s_lab) ──────────────────────────────────


def _mock_run(returncode: int, stdout: str) -> object:
    return {"returncode": returncode, "stdout": stdout, "stderr": ""}


def test_kind_port_drift_none_when_no_kind_node(tmp_path: Path) -> None:
    """docker port failing (no kind node / docker down) → no drift warning."""
    from unittest.mock import patch

    from tools.sdd_cli.k8s_lab import _kind_port_drift

    with patch(
        "tools.sdd_cli.k8s_lab.run_native",
        return_value=_mock_run(1, ""),
    ):
        assert _kind_port_drift(tmp_path) is None


def test_kind_port_drift_matches_config(tmp_path: Path) -> None:
    """Live mappings equal kind-config.yaml → no warning."""
    from unittest.mock import patch

    from tools.sdd_cli.k8s_lab import _kind_port_drift

    cfg = tmp_path / "infra" / "k8s" / "kind-config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(
        "kind: Cluster\n"
        "apiVersion: kind.x-k8s.io/v1alpha4\n"
        "nodes:\n"
        "  - role: control-plane\n"
        "    extraPortMappings:\n"
        "      - containerPort: 30080\n"
        "        hostPort: 8081\n",
        encoding="utf-8",
    )
    with patch(
        "tools.sdd_cli.k8s_lab.run_native",
        return_value=_mock_run(0, "30080/tcp -> 0.0.0.0:8081\n"),
    ):
        assert _kind_port_drift(tmp_path) is None


def test_kind_port_drift_detects_mismatch(tmp_path: Path) -> None:
    """Live mappings differ from config → warning names both sides + recreate."""
    from unittest.mock import patch

    from tools.sdd_cli.k8s_lab import _kind_port_drift

    cfg = tmp_path / "infra" / "k8s" / "kind-config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(
        "kind: Cluster\n"
        "apiVersion: kind.x-k8s.io/v1alpha4\n"
        "nodes:\n"
        "  - role: control-plane\n"
        "    extraPortMappings:\n"
        "      - containerPort: 30080\n"
        "        hostPort: 8081\n"
        "      - containerPort: 30500\n"
        "        hostPort: 5002\n",
        encoding="utf-8",
    )
    with patch(
        "tools.sdd_cli.k8s_lab.run_native",
        return_value=_mock_run(
            0, "30080/tcp -> 0.0.0.0:8081\n30500/tcp -> 0.0.0.0:9999\n"
        ),
    ):
        warning = _kind_port_drift(tmp_path)
        assert warning is not None
        assert "9999" in warning and "5002" in warning
        assert "kind delete cluster" in warning


# ── Committed artifact drift guard ───────────────────────────────────────


def test_committed_artifacts_match_generator() -> None:
    """The committed infra/k8s files must equal what the generator produces
    from the shipped ports.json — any mismatch fails CI loudly."""
    from tools.sdd_cli._shared import REPO_ROOT

    root = REPO_ROOT
    data = load_ports(root)
    assert kind_config_yaml(data).strip() == _read_artifact(
        root / "infra" / "k8s" / "kind-config.yaml"
    )
    for env in data["environments"]:
        patch_path = root / "infra" / "k8s" / "overlays" / env / "service-patch.yaml"
        assert service_patch_yaml(data, env).strip() == _read_artifact(
            patch_path
        ), f"{patch_path} drifted from ports.json — run k8s_ports.write_artifacts"


# ── Role/env port ranges (blocks of 10) ──────────────────────────────────


def test_role_host_block_math() -> None:
    """Web/api host-port blocks of 10 anchored at the role bases."""
    assert role_host_block("web", 0) == (8081, 8090)
    assert role_host_block("web", 1) == (8091, 8100)
    assert role_host_block("api", 0) == (5002, 5011)
    assert role_host_block("api", 1) == (5012, 5021)


def test_env_node_block_math() -> None:
    """Per-env per-role nodePort blocks of 10 anchored at env_code*1000+offset."""
    assert env_node_block("dev", "web", 0) == (30080, 30089)
    assert env_node_block("dev", "api", 0) == (30500, 30509)
    assert env_node_block("qa", "web", 0) == (31080, 31089)
    assert env_node_block("prod", "api", 1) == (32510, 32519)


def test_role_host_base_unknown_raises() -> None:
    with pytest.raises(ValueError, match="no host-port range"):
        role_host_base("worker")


def test_assign_app_ports_web_sequential() -> None:
    """A new web app gets the next free host slots (8084/8085/8086) and the
    first free nodePort in each env's web range (30081/31081/32081)."""
    got = assign_app_ports(_valid_ports(), "frontend-admin", "web")
    assert got == {
        "dev": {"hostPort": 8084, "nodePort": 30081},
        "qa": {"hostPort": 8085, "nodePort": 31081},
        "prod": {"hostPort": 8086, "nodePort": 32081},
    }


def test_assign_app_ports_api_sequential() -> None:
    """A new api app gets the next free host slots (5005/5006/5007) and
    nodePorts (30501/31501/32501)."""
    got = assign_app_ports(_valid_ports(), "backend-admin", "api")
    assert got == {
        "dev": {"hostPort": 5005, "nodePort": 30501},
        "qa": {"hostPort": 5006, "nodePort": 31501},
        "prod": {"hostPort": 5007, "nodePort": 32501},
    }


def test_assign_app_ports_skips_reserved_host_ports() -> None:
    """Web block 0 (8081-8090) contains reserved 8088/8090 — assignment skips
    them and rolls into block 1 once the block is exhausted."""
    data = {
        "version": 1,
        "registry": "x",
        "appPorts": {},
        "environments": {
            "dev": {
                "a": {"hostPort": 8081, "nodePort": 30080},
                "b": {"hostPort": 8084, "nodePort": 30081},
            },
            "qa": {
                "a": {"hostPort": 8082, "nodePort": 31080},
                "b": {"hostPort": 8085, "nodePort": 31081},
            },
            "prod": {
                "a": {"hostPort": 8083, "nodePort": 32080},
                "b": {"hostPort": 8087, "nodePort": 32081},
            },
        },
    }
    got = assign_app_ports(data, "c", "web")
    # free non-reserved slots in block 0: 8086, 8089 (8088/8090 reserved)
    assert got["dev"]["hostPort"] == 8086
    assert got["qa"]["hostPort"] == 8089
    assert got["prod"]["hostPort"] == 8091  # block 0 exhausted → block 1


def test_assign_app_ports_block_rollover() -> None:
    """When block 0 is fully used, allocation rolls to block 1 (next range of 10)."""
    data = {
        "version": 1,
        "registry": "x",
        "appPorts": {},
        "environments": {
            "dev": {"a%d" % i: {"hostPort": 8081 + i, "nodePort": 30080 + i} for i in range(10)},
            "qa": {"a": {"hostPort": 8082, "nodePort": 31080}},
            "prod": {"a": {"hostPort": 8083, "nodePort": 32080}},
        },
    }
    got = assign_app_ports(data, "new", "web")
    assert got["dev"]["hostPort"] == 8091  # first port of block 1
    assert got["dev"]["nodePort"] == 30090  # dev web nodePort block 0 full


def test_assign_app_ports_idempotent_existing() -> None:
    """Assigning an app that already exists returns its current ports unchanged."""
    got = assign_app_ports(_valid_ports(), "frontend", "web")
    assert got["dev"] == {"hostPort": 8081, "nodePort": 30080}
    assert got["prod"] == {"hostPort": 8083, "nodePort": 32080}


def test_assign_app_ports_partial_present_raises() -> None:
    data = _valid_ports()
    del data["environments"]["qa"]["frontend"]
    with pytest.raises(ValueError, match="inconsistent"):
        assign_app_ports(data, "frontend", "web")


def test_assign_app_ports_unknown_role_raises() -> None:
    with pytest.raises(ValueError, match="no host-port range"):
        assign_app_ports(_valid_ports(), "worker", "worker")


def test_load_ports_rejects_host_below_role_base(tmp_path: Path) -> None:
    """A web hostPort below the 8081 base (e.g. 7000) is out of range."""
    data = _valid_ports()
    data["environments"]["dev"]["frontend"]["hostPort"] = 7000
    _write_ports(tmp_path, data)
    with pytest.raises(ValueError, match="below the 'web' host-port range"):
        load_ports(tmp_path)


def test_load_ports_rejects_node_outside_env_range(tmp_path: Path) -> None:
    """A dev nodePort in qa's range (31100 >= 31000) is rejected."""
    data = _valid_ports()
    data["environments"]["dev"]["frontend"]["nodePort"] = 31100
    _write_ports(tmp_path, data)
    with pytest.raises(ValueError, match="outside the 'web' dev nodePort range"):
        load_ports(tmp_path)


def test_load_ports_valid_ranges_pass(tmp_path: Path) -> None:
    """The shipped port scheme (web 808x/30xxx, api 500x/30x00) validates clean."""
    _write_ports(tmp_path, _valid_ports())
    assert load_ports(tmp_path) is not None


def test_assign_app_ports_to_file_writes_and_regenerates(tmp_path: Path) -> None:
    """CLI wrapper persists the allocation to ports.json and regenerates artifacts."""
    path = _write_ports(tmp_path, _valid_ports())
    result = assign_app_ports_to_file(tmp_path, "frontend-admin", "web", dry_run=False)
    assert result["valid"] is True
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["environments"]["dev"]["frontend-admin"] == {
        "hostPort": 8084,
        "nodePort": 30081,
        "role": "web",
    }
    kind = tmp_path / "infra" / "k8s" / "kind-config.yaml"
    assert kind.exists()
    assert "hostPort: 8084" in kind.read_text(encoding="utf-8")
    # second (dry-run) call is idempotent and returns the same ports (incl. role)
    again = assign_app_ports_to_file(tmp_path, "frontend-admin", "web", dry_run=True)
    assert again["valid"] is True
    assert again["allocations"]["dev"] == {
        "hostPort": 8084,
        "nodePort": 30081,
        "role": "web",
    }
