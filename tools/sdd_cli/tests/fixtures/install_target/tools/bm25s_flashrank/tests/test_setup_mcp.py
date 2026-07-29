import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools.bm25s_flashrank import setup_mcp


class SetupMcpTests(unittest.TestCase):
    def test_write_workspace_mcp_config_persists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            vscode_dir = repo_root / ".vscode"
            vscode_dir.mkdir(parents=True, exist_ok=True)

            config = setup_mcp.build_mcp_config(
                r"C:\Users\marce\.mcp_shared_venv\Scripts\python.exe",
                r"C:\LeonRepository\SDD_Template\tools\bm25s_flashrank\mcp_doc_research.py",
            )
            written_paths = setup_mcp.write_workspace_mcp_config(repo_root, config)

            self.assertIn(vscode_dir / "mcp.json", written_paths)
            for wp in written_paths:
                self.assertIsInstance(wp, Path)

            copilot = json.loads(
                (vscode_dir / "mcp.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                r"C:\Users\marce\.mcp_shared_venv\Scripts\python.exe",
                copilot["mcpServers"]["monorepo-docs-search"]["command"],
            )
            self.assertEqual(
                r"C:\LeonRepository\SDD_Template\tools\bm25s_flashrank\mcp_doc_research.py",
                copilot["mcpServers"]["monorepo-docs-search"]["args"][0],
            )

    def test_register_mcp_server_writes_to_vscode_mcp_json(self) -> None:
        """register_mcp_server adds a server entry to .vscode/mcp.json."""
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            server_config = {
                "command": "node",
                "args": ["/path/to/server.js"],
                "env": {"API_KEY": "test-key"},
            }
            written = setup_mcp.register_mcp_server(
                repo_root, "test-server", server_config
            )

            self.assertIn(repo_root / ".vscode" / "mcp.json", written)
            copilot = json.loads(
                (repo_root / ".vscode" / "mcp.json").read_text(encoding="utf-8")
            )
            self.assertIn("test-server", copilot["mcpServers"])
            self.assertEqual("node", copilot["mcpServers"]["test-server"]["command"])
            self.assertEqual(
                "/path/to/server.js", copilot["mcpServers"]["test-server"]["args"][0]
            )
            self.assertEqual(
                "test-key", copilot["mcpServers"]["test-server"]["env"]["API_KEY"]
            )

    def test_register_mcp_server_preserves_existing_servers(self) -> None:
        """register_mcp_server preserves existing MCP entries."""
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            vscode_dir = repo_root / ".vscode"
            vscode_dir.mkdir(parents=True, exist_ok=True)
            existing = {
                "mcpServers": {
                    "existing-server": {
                        "command": "python",
                        "args": ["existing.py"],
                    }
                }
            }
            (vscode_dir / "mcp.json").write_text(
                json.dumps(existing), encoding="utf-8"
            )

            server_config = {"command": "node", "args": ["new.js"]}
            setup_mcp.register_mcp_server(repo_root, "new-server", server_config)

            copilot = json.loads(
                (vscode_dir / "mcp.json").read_text(encoding="utf-8")
            )
            self.assertIn("existing-server", copilot["mcpServers"])
            self.assertIn("new-server", copilot["mcpServers"])

    def test_auto_start_mcp_writes_pid_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            (repo_root / ".vscode").mkdir(parents=True, exist_ok=True)
            config = setup_mcp.build_mcp_config("/tmp/python.exe", "/tmp/server.py")

            fake_process = SimpleNamespace(pid=4242)
            with patch(
                "tools.bm25s_flashrank.setup_mcp.os.path.exists",
                side_effect=lambda path: True,
            ), patch(
                "tools.bm25s_flashrank.setup_mcp.subprocess.Popen",
                return_value=fake_process,
            ) as popen:
                started = setup_mcp.auto_start_mcp(repo_root, config)

            self.assertTrue(started)
            self.assertEqual(1, popen.call_count)
            pid_file = (
                repo_root / ".vscode" / ".mcp_monorepo_docs_search.pid"
            )
            self.assertEqual("4242", pid_file.read_text(encoding="utf-8"))

    # ── OpenProject MCP tests ─────────────────────────────────────────

    def test_build_openproject_mcp_config(self) -> None:
        """build_openproject_mcp_config returns correct npx-based config."""
        config = setup_mcp.build_openproject_mcp_config(
            "http://localhost:8080", "test-key-123"
        )
        self.assertEqual("npx", config["command"])
        self.assertEqual(["-y", "openproject-mcp"], config["args"])
        self.assertEqual(
            "http://localhost:8080", config["env"]["OPENPROJECT_URL"]
        )
        self.assertEqual("test-key-123", config["env"]["OPENPROJECT_API_KEY"])

    def test_setup_openproject_mcp_registers_config(self) -> None:
        """setup_openproject_mcp registers the openproject MCP with correct env."""
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            written = setup_mcp.setup_openproject_mcp(
                repo_root, "http://op:8080", "opapi-test-key"
            )

            self.assertIn(repo_root / ".vscode" / "mcp.json", written)
            copilot = json.loads(
                (repo_root / ".vscode" / "mcp.json").read_text(encoding="utf-8")
            )
            config = copilot["mcpServers"]["openproject"]
            self.assertEqual("npx", config["command"])
            self.assertIn("openproject-mcp", config["args"])
            self.assertEqual(
                "http://op:8080", config["env"]["OPENPROJECT_URL"]
            )
            self.assertEqual("opapi-test-key", config["env"]["OPENPROJECT_API_KEY"])

    # ── Gitea MCP tests ───────────────────────────────────────────────

    def test_build_gitea_mcp_config(self) -> None:
        """build_gitea_mcp_config returns Docker-based config with env."""
        config = setup_mcp.build_gitea_mcp_config(
            "http://localhost:3000", "gitea-token-xyz"
        )
        self.assertEqual("docker", config["command"])
        self.assertIn("run", config["args"])
        self.assertIn("--rm", config["args"])
        self.assertIn("-i", config["args"])
        self.assertIn("docker.gitea.com/gitea-mcp-server", config["args"])
        self.assertIn("--host", config["args"])
        self.assertIn("http://localhost:3000", config["args"])
        self.assertEqual(
            "gitea-token-xyz", config["env"]["GITEA_ACCESS_TOKEN"]
        )

    def test_setup_gitea_mcp_registers_config(self) -> None:
        """setup_gitea_mcp registers the gitea MCP in .vscode/mcp.json."""
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            written = setup_mcp.setup_gitea_mcp(
                repo_root, "http://gitea:3000", "test-token"
            )

            self.assertIn(repo_root / ".vscode" / "mcp.json", written)
            copilot = json.loads(
                (repo_root / ".vscode" / "mcp.json").read_text(encoding="utf-8")
            )
            config = copilot["mcpServers"]["gitea"]
            self.assertEqual("docker", config["command"])
            self.assertIn("docker.gitea.com/gitea-mcp-server", config["args"])
            self.assertEqual("test-token", config["env"]["GITEA_ACCESS_TOKEN"])

    # ── Kubernetes MCP tests ──────────────────────────────────────────

    def test_build_k8s_mcp_config_without_kubeconfig(self) -> None:
        """build_k8s_mcp_config returns npx-based config without env."""
        config = setup_mcp.build_k8s_mcp_config()
        self.assertEqual("npx", config["command"])
        self.assertIn("kubernetes-mcp-server@latest", config["args"])
        self.assertNotIn("env", config)

    def test_build_k8s_mcp_config_with_kubeconfig(self) -> None:
        """build_k8s_mcp_config includes KUBECONFIG env when path given."""
        config = setup_mcp.build_k8s_mcp_config("/custom/kube/config")
        self.assertEqual("npx", config["command"])
        self.assertEqual(
            "/custom/kube/config", config["env"]["KUBECONFIG"]
        )

    def test_setup_k8s_mcp_registers_config(self) -> None:
        """setup_k8s_mcp registers the kubernetes MCP in .vscode/mcp.json."""
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            written = setup_mcp.setup_k8s_mcp(repo_root)

            self.assertIn(repo_root / ".vscode" / "mcp.json", written)
            copilot = json.loads(
                (repo_root / ".vscode" / "mcp.json").read_text(encoding="utf-8")
            )
            config = copilot["mcpServers"]["kubernetes"]
            self.assertEqual("npx", config["command"])
            self.assertIn("kubernetes-mcp-server@latest", config["args"])


if __name__ == "__main__":
    unittest.main()
