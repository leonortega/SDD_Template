"""Tests for the DNS-1123 Service-name hard gates added from E2EPROJECT-37.

The shared database once shipped as `db.internal`; the name only failed on the
real `kubectl apply` (`must not contain dots`) because `--dry-run=client` does
not validate names server-side. Two gates now catch dotted names earlier:

- `k8s_validate._parse_service_names` + `DNS1123_LABEL` — every rendered
  overlay Service name must be DNS-1123 (run in CI's validate-k8s-overlays).
- `k8s_ports.load_ports` — a ports.json `serviceName` override must be
  DNS-1123 (it becomes the Service patch's metadata.name).
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.sdd_cli import k8s_ports, k8s_validate

# Valid ports.json shape (same as the NodePort gate fixture) with the shared
# engine's serviceName override.
VALID_PORTS = {
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


class Dns1123RegexTests(unittest.TestCase):
    def test_rejects_dotted_name(self) -> None:
        self.assertIsNone(k8s_validate.DNS1123_LABEL.match("db.internal"))

    def test_accepts_valid_names(self) -> None:
        for name in ("db", "api", "web", "a", "a-b-c"):
            self.assertIsNotNone(k8s_validate.DNS1123_LABEL.match(name), name)

    def test_rejects_uppercase_and_leading_trailing_dash(self) -> None:
        self.assertIsNone(k8s_validate.DNS1123_LABEL.match("Db"))
        self.assertIsNone(k8s_validate.DNS1123_LABEL.match("-db"))
        self.assertIsNone(k8s_validate.DNS1123_LABEL.match("db-"))


class ParseServiceNamesTests(unittest.TestCase):
    def test_parses_service_names_only(self) -> None:
        rendered = """\
apiVersion: v1
kind: Service
metadata:
  name: db
---
apiVersion: v1
kind: Service
metadata:
  name: api
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
"""
        self.assertEqual(["db", "api"], k8s_validate._parse_service_names(rendered))


class LoadPortsServiceNameTests(unittest.TestCase):
    def _write_ports(self, data: dict) -> Path:
        """Write ports.json under a temp root; the dir lives until the test ends."""
        tmp_dir = tempfile.mkdtemp(prefix="ports-dns1123-")
        self.addCleanup(shutil.rmtree, tmp_dir, ignore_errors=True)
        root = Path(tmp_dir)
        deployment = root / "infra" / "deployment"
        deployment.mkdir(parents=True)
        (deployment / "ports.json").write_text(json.dumps(data), encoding="utf-8")
        return root

    def test_valid_service_name_passes(self) -> None:
        root = self._write_ports(VALID_PORTS)
        k8s_ports.load_ports(root)  # no raise

    def test_dotted_service_name_raises(self) -> None:
        data = json.loads(json.dumps(VALID_PORTS))  # deep copy
        data["environments"]["dev"]["database"]["serviceName"] = "db.internal"
        root = self._write_ports(data)
        with self.assertRaises(ValueError) as cm:
            k8s_ports.load_ports(root)
        self.assertIn("DNS-1123", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
