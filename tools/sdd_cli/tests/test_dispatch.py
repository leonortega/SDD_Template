"""Integration tests for all CLI subcommand dispatches.

Run with: python -m unittest tools.sdd_cli.tests.test_dispatch -v
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path


from tools.sdd_cli import cli


class TopLevelDispatchTests(unittest.TestCase):
    """Test that top-level subcommands parse and dispatch correctly."""

    def test_fallback_shows_available_commands(self) -> None:
        """Running with no args shows available commands."""
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            rc = cli.main([])
        self.assertEqual(1, rc)
        self.assertIn("environment-lab", stderr.getvalue())
        self.assertIn("dev-flow", stderr.getvalue())
        self.assertIn("guidance", stderr.getvalue())
        self.assertIn("memory-search", stderr.getvalue())
        self.assertIn("tool-installer", stderr.getvalue())
        self.assertIn("template-installer", stderr.getvalue())
        self.assertIn("prereqs", stderr.getvalue())

    def test_prereqs_check_dispatches(self) -> None:
        """prereqs check runs without crashing."""
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            rc = cli.main(["prereqs", "check"])
        self.assertEqual(0, rc)
        output = stdout.getvalue()
        self.assertIn("python", output)
        self.assertIn("node", output)

    def test_environment_lab_no_args(self) -> None:
        """environment-lab with no args shows available subcommands."""
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            rc = cli.main(["environment-lab"])
        self.assertEqual(1, rc)
        output = stderr.getvalue()
        self.assertIn("setup-lab", output)
        self.assertIn("compose-up", output)
        self.assertIn("init-local-files", output)
        self.assertIn("validate-gitea-runner", output)

    def test_guidance_no_args(self) -> None:
        """guidance with no args shows available subcommands."""
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            rc = cli.main(["guidance"])
        self.assertEqual(1, rc)
        output = stderr.getvalue()
        self.assertIn("discover", output)
        self.assertIn("map", output)
        self.assertIn("acquire", output)
        self.assertIn("write-skill-index", output)

    def test_dev_flow_no_args(self) -> None:
        """dev-flow with no args shows available subcommands."""
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            rc = cli.main(["dev-flow"])
        self.assertEqual(1, rc)
        output = stderr.getvalue()
        self.assertIn("validate-commit-message", output)
        self.assertIn("parse-workload-forecast", output)
        self.assertIn("detect-adversarial-trigger", output)
        self.assertIn("audit-skill-contracts", output)

    def test_memory_search_no_args(self) -> None:
        """memory-search with no args shows usage."""
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            rc = cli.main(["memory-search"])
        self.assertEqual(1, rc)
        self.assertIn("Usage", stderr.getvalue())

    def test_tool_installer_no_args(self) -> None:
        """tool-installer with no args shows available subcommands."""
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            rc = cli.main(["tool-installer"])
        self.assertEqual(1, rc)
        output = stderr.getvalue()
        self.assertIn("ensure-codebase-memory", output)
        self.assertIn("ensure-quality-tools", output)
        self.assertIn("install-lefthook", output)

    def test_template_installer_no_args(self) -> None:
        """template-installer with no args shows usage."""
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            rc = cli.main(["template-installer"])
        self.assertEqual(1, rc)
        self.assertIn("Usage", stderr.getvalue())


class DevFlowDispatchTests(unittest.TestCase):
    """Test specific dev-flow subcommand dispatch."""

    def test_validate_commit_message(self) -> None:
        """dev-flow validate-commit-message works."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".codex").mkdir()
            (root / ".codex" / "project-profile.json").write_text(
                json.dumps({"workflow": {"ticketKeyPattern": "ABC-[0-9]+"}}),
                encoding="utf-8",
            )
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = cli.main([
                    "dev-flow", "validate-commit-message",
                    "--root", str(root),
                    "--message", "[SDD] maintenance",
                ])
            self.assertEqual(0, rc)
            result = json.loads(stdout.getvalue())
            self.assertTrue(result["valid"])

    def test_unknown_subcommand_fails(self) -> None:
        """Unknown dev-flow subcommand shows error."""
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            rc = cli.main(["dev-flow", "bogus-command"])
        self.assertEqual(1, rc)
        self.assertIn("Unknown dev-flow subcommand: bogus-command", stderr.getvalue())

    def test_detect_adversarial_trigger(self) -> None:
        """dev-flow detect-adversarial-trigger works."""
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            rc = cli.main([
                "dev-flow", "detect-adversarial-trigger",
                "--risk-level", "high",
            ])
        self.assertEqual(0, rc)
        result = json.loads(stdout.getvalue())
        self.assertTrue(result["trigger"])

    def test_parse_workload_forecast_missing_file(self) -> None:
        """dev-flow parse-workload-forecast with missing file returns valid=False."""
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            rc = cli.main([
                "dev-flow", "parse-workload-forecast",
                "--tasks-path", "/nonexistent/tasks.md",
            ])
        self.assertEqual(1, rc)
        result = json.loads(stdout.getvalue())
        self.assertFalse(result["valid"])
        self.assertIn("not found", result["error"])

    def test_ensure_delivery_context(self) -> None:
        """dev-flow ensure-delivery-context works."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = cli.main([
                    "dev-flow", "ensure-delivery-context",
                    "--root", str(root),
                    "--values-json", json.dumps({"ticketKey": "ABC-1", "branch": "feat/test"}),
                ])
            self.assertEqual(0, rc)
            result = json.loads(stdout.getvalue())
            self.assertTrue(result["valid"])
            lock = root / ".codex" / "delivery-context.local.json"
            self.assertTrue(lock.exists())
            data = json.loads(lock.read_text(encoding="utf-8"))
            self.assertEqual("ABC-1", data["ticketKey"])

    def test_initialize_telemetry(self) -> None:
        """dev-flow init-telemetry works."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = cli.main([
                    "dev-flow", "init-telemetry",
                    "--ticket-key", "ABC-1",
                    "--root", str(root),
                ])
            self.assertEqual(0, rc)
            result = json.loads(stdout.getvalue())
            self.assertTrue(result["exists"])

    def test_append_telemetry(self) -> None:
        """dev-flow append-telemetry works."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # First initialize
            cli.main(["dev-flow", "init-telemetry", "--ticket-key", "ABC-1", "--root", str(root)])
            # Then append
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = cli.main([
                    "dev-flow", "append-telemetry",
                    "--ticket-key", "ABC-1",
                    "--root", str(root),
                    "--input-json", json.dumps({
                        "workflowStage": "test",
                        "agentRole": "tester",
                        "startedUtc": "2026-07-13T10:00:00Z",
                        "finishedUtc": "2026-07-13T10:01:00Z",
                        "retryCount": 0,
                        "outcome": "PASS",
                    }),
                ])
            self.assertEqual(0, rc)
            result = json.loads(stdout.getvalue())
            self.assertTrue(result["appended"])


class GuidanceDispatchTests(unittest.TestCase):
    """Test guidance subcommand dispatch."""

    def test_write_skill_index_dry_run(self) -> None:
        """guidance write-skill-index --dry-run true works."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / ".codex" / "skills" / "test-skill"
            skills.mkdir(parents=True)
            (skills / "SKILL.md").write_text(
                "---\nname: test-skill\ndescription: A test skill\n---\n\n# Test\n\nContent\n",
                encoding="utf-8",
            )
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = cli.main([
                    "guidance", "write-skill-index",
                    "--root", str(root),
                    "--dry-run", "true",
                ])
            self.assertEqual(0, rc)
            result = json.loads(stdout.getvalue())
            self.assertTrue(result["valid"])
            self.assertEqual(1, result["skillCount"])


class EnvironmentLabDispatchTests(unittest.TestCase):
    """Test environment-lab subcommand dispatch."""

    def test_init_local_files_creates_memory_seeds(self) -> None:
        """environment-lab init-local-files works."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / ".codex"
            codex.mkdir()
            (codex / "client-tools.example.json").write_text("{}", encoding="utf-8")
            (codex / "quality.example.json").write_text("{}", encoding="utf-8")
            (root / "infra" / "openproject").mkdir(parents=True)
            (root / "infra" / "openproject" / "variables.env.example").write_text("OPENPROJECT_HOST=\n", encoding="utf-8")
            (root / "infra" / "monitoring").mkdir(parents=True)
            (root / "infra" / "monitoring" / "variables.env.example").write_text("SEQ_URL=\n", encoding="utf-8")

            (root / "infra" / "gitea").mkdir(parents=True)
            (root / "infra" / "gitea" / "runner.env.example").write_text("GITEA_INSTANCE_URL=\n", encoding="utf-8")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = cli.main([
                    "environment-lab", "init-local-files",
                    "--root", str(root),
                ])
            self.assertEqual(0, rc)
            result = json.loads(stdout.getvalue())
            self.assertTrue(result["valid"])
            self.assertTrue((root / ".codex" / "memory" / "MEMORY.md").exists())

    def test_init_project_profile(self) -> None:
        """environment-lab init-project-profile works."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = cli.main([
                    "environment-lab", "init-project-profile",
                    "--root", str(root),
                ])
            self.assertEqual(0, rc)
            self.assertTrue((root / ".codex" / "project-profile.example.json").exists())

    def test_init_quality_templates(self) -> None:
        """environment-lab init-quality-templates works."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = cli.main([
                    "environment-lab", "init-quality-templates",
                    "--root", str(root),
                ])
            self.assertEqual(0, rc)
            result = json.loads(stdout.getvalue())
            self.assertTrue(result.get("changed", False))

    def test_dry_run_validate_observability(self) -> None:
        """environment-lab validate-observability --dry-run true works."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            monitoring = root / "infra" / "monitoring"
            monitoring.mkdir(parents=True)
            (monitoring / "variables.env").write_text(
                "SEQ_URL=http://localhost:5341\nSEQ_ERROR_ALERT_WINDOW=1m\nSEQ_ERROR_ALERT_THRESHOLD=0\n",
                encoding="utf-8",
            )
            grafana = monitoring / "grafana" / "provisioning"
            (grafana / "datasources").mkdir(parents=True)
            (grafana / "datasources" / "infinity-health.yml").write_text("datasource", encoding="utf-8")
            (grafana / "alerting").mkdir(parents=True)
            (grafana / "alerting" / "health-alerts.yml").write_text("alerts", encoding="utf-8")
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = cli.main([
                    "environment-lab", "validate-observability",
                    "--root", str(root),
                    "--dry-run", "true",
                ])
            self.assertEqual(0, rc)  # Dry-run skips HTTP checks


class ToolInstallerDispatchTests(unittest.TestCase):
    """Test tool-installer subcommand dispatch."""

    def test_ensure_codebase_memory_dry_run(self) -> None:
        """tool-installer ensure-codebase-memory --dry-run true works."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Need tools/codebase_memory_mcp/mcp_cap_shim.py for codebase memory
            shim = root / "tools" / "codebase_memory_mcp"
            shim.mkdir(parents=True)
            (shim / "mcp_cap_shim.py").write_text("# shim", encoding="utf-8")
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = cli.main([
                    "tool-installer", "ensure-codebase-memory",
                    "--root", str(root),
                    "--dry-run", "true",
                ])
            self.assertEqual(0, rc)
            result = json.loads(stdout.getvalue())
            self.assertTrue(result["valid"])

    def test_ensure_quality_tools_dry_run(self) -> None:
        """tool-installer ensure-quality-tools --dry-run true works."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "lefthook.yml").write_text(
                "commit-msg:\n  commands:\n    test:\n      run: echo ok\n",
                encoding="utf-8"
            )
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = cli.main([
                    "tool-installer", "ensure-quality-tools",
                    "--root", str(root),
                    "--dry-run", "true",
                ])
            self.assertEqual(0, rc)  # Dry-run skips external tool checks

    def test_install_lefthook_dry_run(self) -> None:
        """tool-installer install-lefthook --dry-run true works."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "lefthook.yml").write_text("pre-commit:\n  commands:\n    test:\n      run: echo ok\n", encoding="utf-8")
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = cli.main([
                    "tool-installer", "install-lefthook",
                    "--root", str(root),
                    "--dry-run", "true",
                ])
            self.assertEqual(0, rc)
            result = json.loads(stdout.getvalue())
            self.assertTrue(result["valid"])


class MemorySearchDispatchTests(unittest.TestCase):
    """Test memory-search subcommand dispatch."""

    def test_memory_search_list_topics(self) -> None:
        """memory-search search --list-topics works."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            memory = root / ".codex" / "memory"
            memory.mkdir(parents=True)
            (memory / "failure-patterns.md").write_text(
                "## Docker Backend Timeout\n\n- Type: Pattern\n- Status: Active\n- Source: test\n- Last verified: 2026-07-13\n\nDocker failed.\n",
                encoding="utf-8",
            )
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = cli.main([
                    "memory-search", "search",
                    "--root", str(root),
                    "--list-topics",
                    "--json",
                ])
            self.assertEqual(0, rc)
            results = json.loads(stdout.getvalue())
            self.assertIsInstance(results, list)
            self.assertGreaterEqual(len(results), 1)
            self.assertEqual("Docker Backend Timeout", results[0]["title"])


class ValidateGiteaRunnerDispatchTests(unittest.TestCase):
    """Test validate-gitea-runner dispatches."""

    def test_validate_gitea_runner_dry_run(self) -> None:
        """environment-lab validate-gitea-runner --dry-run true works."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Create Dockerfiles for image check
            actions = root / "infra" / "gitea" / "actions-images" / "e2e-ci"
            actions.mkdir(parents=True)
            (actions / "Dockerfile").write_text("FROM alpine\n", encoding="utf-8")
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = cli.main([
                    "environment-lab", "validate-gitea-runner",
                    "--root", str(root),
                    "--dry-run", "true",
                ])
            self.assertEqual(0, rc)


if __name__ == "__main__":
    unittest.main()
