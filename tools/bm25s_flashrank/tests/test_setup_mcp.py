import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools.bm25s_flashrank import setup_mcp


class SetupMcpTests(unittest.TestCase):
    def test_write_workspace_mcp_config_persists_for_copilot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            vscode_dir = repo_root / ".vscode"
            vscode_dir.mkdir(parents=True, exist_ok=True)

            config = setup_mcp.build_mcp_config(
                r"C:\Users\marce\.mcp_shared_venv\Scripts\python.exe",
                r"C:\LeonRepository\SDD_Template\tools\bm25s_flashrank\mcp_doc_research.py",
            )
            written_paths = setup_mcp.write_workspace_mcp_config(repo_root, config)

            # .vscode/mcp.json is always written
            self.assertIn(vscode_dir / "mcp.json", written_paths)
            # Cline path is environment-dependent, so only check it's a Path if present
            for wp in written_paths:
                self.assertIsInstance(wp, Path)

            copilot = json.loads((vscode_dir / "mcp.json").read_text(encoding="utf-8"))
            self.assertEqual(
                r"C:\Users\marce\.mcp_shared_venv\Scripts\python.exe",
                copilot["servers"]["monorepo-docs-search"]["command"],
            )
            self.assertEqual(
                r"C:\LeonRepository\SDD_Template\tools\bm25s_flashrank\mcp_doc_research.py",
                copilot["servers"]["monorepo-docs-search"]["args"][0],
            )
            self.assertEqual(
                "stdio", copilot["servers"]["monorepo-docs-search"]["type"]
            )

    def test_documentation_search_handles_numpy_style_indices(self) -> None:
        import numpy as np

        class DummyRetriever:
            def retrieve(self, query_tokens, k):
                return np.array([0, 1]), None

        sample_data = [
            ("docs/dummy.md", "Example content A"),
            ("docs/dummy2.md", "Example content B"),
        ]
        with patch(
            "tools.bm25s_flashrank.mcp_doc_research.build_monorepo_index",
            return_value=(DummyRetriever(), sample_data),
        ):
            result = __import__(
                "tools.bm25s_flashrank.mcp_doc_research",
                fromlist=["search_documentation"],
            ).search_documentation("example", None, True)

        self.assertIn(os.path.join("docs", "dummy.md"), result)
        self.assertIn(os.path.join("docs", "dummy2.md"), result)

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
            pid_file = repo_root / ".vscode" / ".mcp_monorepo_docs_search.pid"
            self.assertEqual("4242", pid_file.read_text(encoding="utf-8"))

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
            self.assertIn("test-server", copilot["servers"])
            self.assertEqual("stdio", copilot["servers"]["test-server"]["type"])
            self.assertEqual("node", copilot["servers"]["test-server"]["command"])
            self.assertEqual(
                "/path/to/server.js", copilot["servers"]["test-server"]["args"][0]
            )
            self.assertEqual(
                "test-key", copilot["servers"]["test-server"]["env"]["API_KEY"]
            )

    def test_register_mcp_server_preserves_existing_servers(self) -> None:
        """register_mcp_server preserves existing MCP entries."""
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            vscode_dir = repo_root / ".vscode"
            vscode_dir.mkdir(parents=True, exist_ok=True)
            existing = {
                "servers": {
                    "existing-server": {
                        "type": "stdio",
                        "command": "python",
                        "args": ["existing.py"],
                    }
                }
            }
            (vscode_dir / "mcp.json").write_text(json.dumps(existing), encoding="utf-8")

            server_config = {"command": "node", "args": ["new.js"]}
            setup_mcp.register_mcp_server(repo_root, "new-server", server_config)

            copilot = json.loads((vscode_dir / "mcp.json").read_text(encoding="utf-8"))
            self.assertIn("existing-server", copilot["servers"])
            self.assertIn("new-server", copilot["servers"])

    def test_setup_openproject_mcp_builds_config(self) -> None:
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
            config = copilot["servers"]["openproject"]
            self.assertEqual("node", config["command"])
            self.assertIn("index.js", config["args"][0])
            self.assertEqual("http://op:8080", config["env"]["OPENPROJECT_BASE_URL"])
            self.assertEqual("opapi-test-key", config["env"]["OPENPROJECT_API_KEY"])


if __name__ == "__main__":
    unittest.main()
