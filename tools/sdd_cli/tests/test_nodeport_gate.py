"""Tests for the CI NodePort-validation gate's patch-vs-ports.json cross-check.

The gate logic lives inline in `.gitea/workflows/package-deploy.yml` as a
python3 heredoc. Rather than duplicating the logic here (which would drift),
these tests extract that exact heredoc and exec it against a fixture tree of
`infra/deployment/ports.json` + per-env `service-patch.yaml` files, asserting
it passes on a consistent tree and exits 1 on drift/collisions.

Regression case: the shared database registers under the canonical key
`database` but its service patch targets `db` (serviceName override).
The validator must resolve patches by service name, matching
`k8s_ports.service_patch_yaml`.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = REPO_ROOT / ".gitea" / "workflows" / "package-deploy.yml"

# Canonical ports.json fixture mirroring the committed file's structure,
# including the database serviceName override (db).
PORTS = {
    "version": 1,
    "appPorts": {},
    "environments": {
        "dev": {
            "database": {"hostPort": 5432, "nodePort": 30700, "role": "database", "serviceName": "db"},
            "web": {"hostPort": 8081, "nodePort": 30080, "role": "web"},
            "api": {"hostPort": 5002, "nodePort": 30500, "role": "api"},
        },
        "qa": {
            "database": {"hostPort": 5433, "nodePort": 31700, "role": "database", "serviceName": "db"},
            "web": {"hostPort": 8082, "nodePort": 31080, "role": "web"},
            "api": {"hostPort": 5003, "nodePort": 31500, "role": "api"},
        },
        "prod": {
            "database": {"hostPort": 5434, "nodePort": 32700, "role": "database", "serviceName": "db"},
            "web": {"hostPort": 8083, "nodePort": 32080, "role": "web"},
            "api": {"hostPort": 5004, "nodePort": 32500, "role": "api"},
        },
    },
}

# (env, service name) -> nodePort as the generator emits them (serviceName for
# database, app key otherwise) — the *correct* committed patch shape.
PATCHES = {
    "dev": {"db": 30700, "web": 30080, "api": 30500},
    "qa": {"db": 31700, "web": 31080, "api": 31500},
    "prod": {"db": 32700, "web": 32080, "api": 32500},
}


def _gate_script() -> str:
    """Extract the NodePort-validation heredoc from the workflow file."""
    text = WORKFLOW.read_text(encoding="utf-8")
    for match in re.finditer(r"python3 << 'PYEOF'\n(.*?)\n[ \t]*PYEOF", text, re.DOTALL):
        script = textwrap.dedent(match.group(1))
        if "infra/deployment/ports.json" in script:
            return script
    raise AssertionError("NodePort-validation heredoc not found in package-deploy.yml")


def _write_tree(tmp_path: Path, ports: dict, patches: dict[str, dict[str, int]]) -> None:
    """Write the fixture infra tree (ports.json + per-env service patches)."""
    deployment = tmp_path / "infra" / "deployment"
    deployment.mkdir(parents=True)
    (deployment / "ports.json").write_text(json.dumps(ports), encoding="utf-8")
    for env, services in patches.items():
        overlay = tmp_path / "infra" / "k8s" / "overlays" / env
        overlay.mkdir(parents=True)
        blocks = []
        for service, node_port in services.items():
            blocks.append(
                "apiVersion: v1\n"
                "kind: Service\n"
                "metadata:\n"
                f"  name: {service}\n"
                "spec:\n"
                "  type: NodePort\n"
                "  ports:\n"
                "    - port: 5432\n"
                "      targetPort: 5432\n"
                "      protocol: TCP\n"
                f"      nodePort: {node_port}"
            )
        (overlay / "service-patch.yaml").write_text("\n---\n".join(blocks) + "\n", encoding="utf-8")


def _run_gate(ports: dict, patches: dict[str, dict[str, int]]) -> None:
    """Exec the real gate heredoc against the given fixture tree (chdir'd)."""
    script = _gate_script()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _write_tree(tmp_path, ports, patches)
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            exec(compile(script, "nodeport_gate.py", "exec"), {})
        finally:
            os.chdir(old_cwd)


class NodePortGateTests(unittest.TestCase):
    """Cross-check service patches against the canonical ports.json."""

    def test_consistent_tree_with_service_name_override_passes(self) -> None:
        # Regression: database patch is keyed db (serviceName), not
        # the canonical `database` key — the gate must still match it.
        _run_gate(PORTS, PATCHES)  # no SystemExit == pass

    def test_wrong_nodeport_raises_drift(self) -> None:
        patches = {env: dict(services) for env, services in PATCHES.items()}
        patches["dev"]["web"] = 30081  # differs from ports.json
        with self.assertRaises(SystemExit) as cm:
            _run_gate(PORTS, patches)
        self.assertEqual(1, cm.exception.code)

    def test_missing_patch_entry_raises_drift(self) -> None:
        patches = {env: dict(services) for env, services in PATCHES.items()}
        del patches["dev"]["api"]
        with self.assertRaises(SystemExit) as cm:
            _run_gate(PORTS, patches)
        self.assertEqual(1, cm.exception.code)

    def test_nodeport_collision_across_envs_raises(self) -> None:
        patches = {env: dict(services) for env, services in PATCHES.items()}
        patches["qa"]["web"] = 30080  # collides with dev/web
        with self.assertRaises(SystemExit) as cm:
            _run_gate(PORTS, patches)
        self.assertEqual(1, cm.exception.code)

    def test_canonical_database_key_without_service_name_is_drift(self) -> None:
        # If a patch is (incorrectly) keyed by the canonical key instead of
        # the serviceName, the gate must flag it rather than silently accept.
        patches = {env: dict(services) for env, services in PATCHES.items()}
        for env in ("dev", "qa", "prod"):
            node_port = patches[env].pop("db")
            patches[env]["database"] = node_port
        with self.assertRaises(SystemExit) as cm:
            _run_gate(PORTS, patches)
        self.assertEqual(1, cm.exception.code)


if __name__ == "__main__":
    unittest.main()
