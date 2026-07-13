import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools.bm25s_flashrank import setup_mcp


class SetupMcpTests(unittest.TestCase):
    def test_write_workspace_mcp_config_persists_for_cline_and_copilot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            vscode_dir = repo_root / ".vscode"
            vscode_dir.mkdir(parents=True, exist_ok=True)
            (vscode_dir / "cline_mcp_settings.json").write_text(
                json.dumps({"mcpServers": {"codegraph": {"command": "npx"}}}),
                encoding="utf-8",
            )

            config = setup_mcp.build_mcp_config(r"C:\Users\marce\.mcp_shared_venv\Scripts\python.exe", r"C:\LeonRepository\SDD_Template\tools\bm25s_flashrank\mcp_doc_research.py")
            written_paths = setup_mcp.write_workspace_mcp_config(repo_root, config)

            self.assertEqual({vscode_dir / "cline_mcp_settings.json", vscode_dir / "mcp.json", vscode_dir / "settings.json", repo_root / ".cline" / "mcp_settings.json"}, set(written_paths))

            cline = json.loads((vscode_dir / "cline_mcp_settings.json").read_text(encoding="utf-8"))
            self.assertEqual(r"C:\Users\marce\.mcp_shared_venv\Scripts\python.exe", cline["mcpServers"]["monorepo-docs-search"]["command"])
            self.assertEqual(r"C:\LeonRepository\SDD_Template\tools\bm25s_flashrank\mcp_doc_research.py", cline["mcpServers"]["monorepo-docs-search"]["args"][0])
            self.assertEqual("npx", cline["mcpServers"]["codegraph"]["command"])

            copilot = json.loads((vscode_dir / "mcp.json").read_text(encoding="utf-8"))
            self.assertEqual(r"C:\Users\marce\.mcp_shared_venv\Scripts\python.exe", copilot["servers"]["monorepo-docs-search"]["command"])
            self.assertEqual(r"C:\LeonRepository\SDD_Template\tools\bm25s_flashrank\mcp_doc_research.py", copilot["servers"]["monorepo-docs-search"]["args"][0])
            self.assertEqual("stdio", copilot["servers"]["monorepo-docs-search"]["type"])

    def test_documentation_search_handles_numpy_style_indices(self) -> None:
        import numpy as np

        class DummyRetriever:
            def retrieve(self, query_tokens, k):
                return np.array([0, 1]), None

        sample_data = [("docs/dummy.md", "Example content A"), ("docs/dummy2.md", "Example content B")]
        with patch("tools.bm25s_flashrank.mcp_doc_research.build_monorepo_index", return_value=(DummyRetriever(), sample_data)):
            result = __import__("tools.bm25s_flashrank.mcp_doc_research", fromlist=["search_documentation"]).search_documentation("example", None, True)

        self.assertIn(os.path.join("docs", "dummy.md"), result)
        self.assertIn(os.path.join("docs", "dummy2.md"), result)

    def test_auto_start_mcp_writes_pid_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            (repo_root / ".vscode").mkdir(parents=True, exist_ok=True)
            config = setup_mcp.build_mcp_config("/tmp/python.exe", "/tmp/server.py")

            fake_process = SimpleNamespace(pid=4242)
            with patch("tools.bm25s_flashrank.setup_mcp.os.path.exists", side_effect=lambda path: True), patch("tools.bm25s_flashrank.setup_mcp.subprocess.Popen", return_value=fake_process) as popen:
                started = setup_mcp.auto_start_mcp(repo_root, config)

            self.assertTrue(started)
            self.assertEqual(1, popen.call_count)
            pid_file = repo_root / ".vscode" / ".mcp_monorepo_docs_search.pid"
            self.assertEqual("4242", pid_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
