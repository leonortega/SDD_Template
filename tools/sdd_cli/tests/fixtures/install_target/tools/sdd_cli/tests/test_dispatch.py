"""Integration tests for all CLI subcommand dispatches.

Run with: python -m unittest tools.sdd_cli.tests.test_dispatch -v
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
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
        # Accept 0 or 1 — prereqs like node/npm may not be in PATH
        self.assertIn(rc, (0, 1))
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
        self.assertIn("install-playwright-mcp", output)
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
                rc = cli.main(
                    [
                        "dev-flow",
                        "validate-commit-message",
                        "--root",
                        str(root),
                        "--message",
                        "[SDD] maintenance",
                    ]
                )
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
            rc = cli.main(
                [
                    "dev-flow",
                    "detect-adversarial-trigger",
                    "--risk-level",
                    "high",
                ]
            )
        self.assertEqual(0, rc)
        result = json.loads(stdout.getvalue())
        self.assertTrue(result["trigger"])

    def test_parse_workload_forecast_missing_file(self) -> None:
        """dev-flow parse-workload-forecast with missing file returns valid=False."""
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            rc = cli.main(
                [
                    "dev-flow",
                    "parse-workload-forecast",
                    "--tasks-path",
                    "/nonexistent/tasks.md",
                ]
            )
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
                rc = cli.main(
                    [
                        "dev-flow",
                        "ensure-delivery-context",
                        "--root",
                        str(root),
                        "--values-json",
                        json.dumps({"ticketKey": "ABC-1", "branch": "feat/test"}),
                    ]
                )
            self.assertEqual(0, rc)
            result = json.loads(stdout.getvalue())
            self.assertTrue(result["valid"])
            lock = root / ".codex" / "delivery-context.local.json"
            self.assertTrue(lock.exists())
            data = json.loads(lock.read_text(encoding="utf-8"))
            self.assertEqual("ABC-1", data["ticketKey"])


class GuidanceDispatchTests(unittest.TestCase):
    """Test guidance subcommand dispatch."""

    def test_discover_dry_run(self) -> None:
        """guidance discover --dry-run true works (internet-only, no results in dry-run)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / ".codex"
            codex.mkdir(parents=True)
            # Stack values come from the profile; dry-run never searches the internet.
            (codex / "project-profile.local.json").write_text(
                json.dumps({
                    "stack": {
                        "frontend": {"applies": True, "value": "react"},
                        "backend": {"applies": False, "value": ""},
                        "database": {"applies": False, "value": ""},
                    }
                }),
                encoding="utf-8",
            )
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = cli.main(
                    [
                        "guidance",
                        "discover",
                        "--root",
                        str(root),
                        "--dry-run",
                        "true",
                    ]
                )
            self.assertEqual(0, rc)
            result = json.loads(stdout.getvalue())
            self.assertTrue(result["valid"])
            self.assertIn("react", result["stackTags"])
            # Dry-run: internet search produces no skills (never reads local manifest).
            self.assertEqual(0, result["skillCount"])
            self.assertEqual([], result["foundSkills"])


class StackTestsDispatchTests(unittest.TestCase):
    """Test stack-tests subcommand dispatch."""

    def test_stack_tests_dry_run(self) -> None:
        """stack-tests --dry-run true works with no stack (skips cleanly)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                # --root is a top-level option: it must precede the subcommand.
                rc = cli.main(
                    [
                        "--root",
                        str(root),
                        "stack-tests",
                        "--dry-run",
                        "true",
                    ]
                )
            self.assertEqual(0, rc)
            self.assertIn("Stack tests: OK", stdout.getvalue())

    def test_stack_tests_dry_run_with_profile(self) -> None:
        """stack-tests --dry-run true reports commands for configured frameworks."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / ".codex"
            codex.mkdir(parents=True)
            (codex / "project-profile.local.json").write_text(
                json.dumps({"stack": {"testFrameworks": ["pytest"]}}),
                encoding="utf-8",
            )
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = cli.main(
                    [
                        "--root",
                        str(root),
                        "stack-tests",
                        "--dry-run",
                        "true",
                    ]
                )
            self.assertEqual(0, rc)
            self.assertIn("Stack tests: OK", stdout.getvalue())
            self.assertIn("pytest", stdout.getvalue())


class EnvironmentLabDispatchTests(unittest.TestCase):
    """Test environment-lab subcommand dispatch."""

    def test_setup_lab_delegates_to_full_setup(self) -> None:
        """environment-lab setup-lab now delegates to full-setup."""
        from unittest.mock import patch

        with patch("tools.sdd_cli.full_setup.run_full_setup",
                   return_value=0) as mock_full:
            rc = cli.main(["environment-lab", "setup-lab", "--dry-run", "true"])

        self.assertEqual(0, rc)
        mock_full.assert_called_once()
        # Should pass remaining args and root
        args, kwargs = mock_full.call_args
        self.assertEqual(["--dry-run", "true"], args[0])
        self.assertIn("root", kwargs)

    def test_other_envlab_commands_still_work(self) -> None:
        """Other environment-lab subcommands still dispatch normally."""
        from unittest.mock import patch

        with patch("tools.sdd_cli.full_setup.run_full_setup") as mock_full:
            rc = cli.main(["environment-lab", "init-local-files", "--dry-run", "true"])

        # Should NOT have delegated to full-setup
        mock_full.assert_not_called()

    def test_init_local_files_creates_memory_seeds(self) -> None:
        """environment-lab init-local-files works."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / ".codex"
            codex.mkdir()
            (codex / "client-tools.example.json").write_text("{}", encoding="utf-8")
            (codex / "quality.example.json").write_text("{}", encoding="utf-8")
            (root / "infra" / "openproject").mkdir(parents=True)
            (root / "infra" / "openproject" / "variables.env.example").write_text(
                "OPENPROJECT_HOST=\n", encoding="utf-8"
            )
            (root / "infra" / "monitoring").mkdir(parents=True)
            (root / "infra" / "monitoring" / "variables.env.example").write_text(
                "SEQ_URL=\n", encoding="utf-8"
            )

            (root / "infra" / "gitea").mkdir(parents=True)
            (root / "infra" / "gitea" / "runner.env.example").write_text(
                "GITEA_INSTANCE_URL=\n", encoding="utf-8"
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = cli.main(
                    [
                        "environment-lab",
                        "init-local-files",
                        "--root",
                        str(root),
                    ]
                )
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
                rc = cli.main(
                    [
                        "environment-lab",
                        "init-project-profile",
                        "--root",
                        str(root),
                    ]
                )
            self.assertEqual(0, rc)
            self.assertTrue((root / ".codex" / "project-profile.example.json").exists())

    def test_init_quality_templates(self) -> None:
        """environment-lab init-quality-templates works."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = cli.main(
                    [
                        "environment-lab",
                        "init-quality-templates",
                        "--root",
                        str(root),
                    ]
                )
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
            (grafana / "datasources" / "infinity-health.yml").write_text(
                "datasource", encoding="utf-8"
            )
            (grafana / "alerting").mkdir(parents=True)
            (grafana / "alerting" / "health-alerts.yml").write_text(
                "alerts", encoding="utf-8"
            )
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = cli.main(
                    [
                        "environment-lab",
                        "validate-observability",
                        "--root",
                        str(root),
                        "--dry-run",
                        "true",
                    ]
                )
            self.assertEqual(0, rc)  # Dry-run skips HTTP checks


class ToolInstallerDispatchTests(unittest.TestCase):
    """Test tool-installer subcommand dispatch."""

    def test_ensure_quality_tools_dry_run(self) -> None:
        """tool-installer ensure-quality-tools --dry-run true works."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "lefthook.yml").write_text(
                "commit-msg:\n  commands:\n    test:\n      run: echo ok\n",
                encoding="utf-8",
            )
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = cli.main(
                    [
                        "tool-installer",
                        "ensure-quality-tools",
                        "--root",
                        str(root),
                        "--dry-run",
                        "true",
                    ]
                )
            self.assertEqual(0, rc)  # Dry-run skips external tool checks

    def test_coverage_probe_commands_follow_stack_frameworks(self) -> None:
        """ensure-quality-tools coverage probe is stack-driven, not hardcoded."""
        from tools.sdd_cli.tool_installer import _coverage_probe_commands

        # No stack configured → falls back to the classic tri-list.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            probes = _coverage_probe_commands(root)
            names = [name for _, name in probes]
            self.assertEqual(["dotnet", "pytest", "jest"], names)

            # pytest stack → only pytest probed (no dotnet/jest fallback).
            codex = root / ".codex"
            codex.mkdir()
            (codex / "project-profile.local.json").write_text(
                json.dumps({"stack": {"testFrameworks": ["pytest"]}}),
                encoding="utf-8",
            )
            probes = _coverage_probe_commands(root)
            names = [name for _, name in probes]
            self.assertEqual(["pytest"], names)

            # .NET variants normalize to the single dotnet probe.
            (codex / "project-profile.local.json").write_text(
                json.dumps({"stack": {"testFrameworks": ["xunit", "nunit"]}}),
                encoding="utf-8",
            )
            probes = _coverage_probe_commands(root)
            names = [name for _, name in probes]
            self.assertEqual(["dotnet"], names)

            # Mixed stack → deduplicated probes in profile order.
            (codex / "project-profile.local.json").write_text(
                json.dumps({"stack": {"testFrameworks": ["jest", "pytest"]}}),
                encoding="utf-8",
            )
            probes = _coverage_probe_commands(root)
            names = [name for _, name in probes]
            self.assertEqual(["jest", "pytest"], names)

            # Configured-but-unmapped framework → falls back to the tri-list.
            (codex / "project-profile.local.json").write_text(
                json.dumps({"stack": {"testFrameworks": ["golang"]}}),
                encoding="utf-8",
            )
            probes = _coverage_probe_commands(root)
            names = [name for _, name in probes]
            self.assertEqual(["dotnet", "pytest", "jest"], names)

    def test_install_lefthook_dry_run(self) -> None:
        """tool-installer install-lefthook --dry-run true works."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "lefthook.yml").write_text(
                "pre-commit:\n  commands:\n    test:\n      run: echo ok\n",
                encoding="utf-8",
            )
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = cli.main(
                    [
                        "tool-installer",
                        "install-lefthook",
                        "--root",
                        str(root),
                        "--dry-run",
                        "true",
                    ]
                )
            self.assertEqual(0, rc)
            result = json.loads(stdout.getvalue())
            self.assertTrue(result["valid"])

    def test_install_skill_dry_run_validates_repo_format(self) -> None:
        """tool-installer install-skill --dry-run true validates repo format."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = cli.main(
                    [
                        "tool-installer",
                        "install-skill",
                        "--root",
                        str(root),
                        "--repo",
                        "owner/repo",
                        "--skill-path",
                        "path/to/skill",
                        "--skill-name",
                        "test-skill",
                        "--dry-run",
                        "true",
                    ]
                )
            self.assertEqual(0, rc)
            result = json.loads(stdout.getvalue())
            self.assertTrue(result["dryRun"])
            self.assertEqual("test-skill", result["skillName"])

    def test_install_skill_rejects_invalid_repo(self) -> None:
        """tool-installer install-skill rejects invalid repo format."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = cli.main(
                    [
                        "tool-installer",
                        "install-skill",
                        "--root",
                        str(root),
                        "--repo",
                        "invalid-format",
                        "--skill-path",
                        "test",
                        "--skill-name",
                        "test",
                    ]
                )
            self.assertEqual(1, rc)
            result = json.loads(stdout.getvalue())
            self.assertFalse(result["valid"])
            self.assertIn("Invalid repo format", str(result))

    def test_tool_installer_available_includes_install_skill(self) -> None:
        """tool-installer with no args lists install-skill."""
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            rc = cli.main(["tool-installer"])
        self.assertEqual(1, rc)
        self.assertIn("install-skill", stderr.getvalue())

    def test_list_skills_dry_run_with_config(self) -> None:
        """tool-installer list-skills --dry-run true with source config works."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / ".codex"
            codex.mkdir()
            (codex / "skill-sources.json").write_text(
                json.dumps({
                    "sources": [
                        {
                            "name": "test-source",
                            "repo": "test/test",
                            "path": "skills",
                            "branch": "main",
                            "description": "Test source",
                        }
                    ]
                }),
                encoding="utf-8",
            )
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = cli.main(
                    [
                        "tool-installer",
                        "list-skills",
                        "--root",
                        str(root),
                        "--dry-run",
                        "true",
                    ]
                )
            self.assertEqual(0, rc)
            result = json.loads(stdout.getvalue())
            self.assertTrue(result["valid"])
            self.assertIn("sources", result)
            self.assertIn("skills", result)

    def test_list_skills_uses_example_config_when_no_local(self) -> None:
        """list-skills falls back to .codex/skill-sources.example.json."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / ".codex"
            codex.mkdir()
            # Only create the example file, not the local one
            (codex / "skill-sources.example.json").write_text(
                json.dumps({
                    "sources": [
                        {
                            "name": "example-source",
                            "repo": "example/example",
                            "path": "skills",
                            "branch": "main",
                            "description": "Example source",
                        }
                    ]
                }),
                encoding="utf-8",
            )
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = cli.main(
                    [
                        "tool-installer",
                        "list-skills",
                        "--root",
                        str(root),
                        "--dry-run",
                        "true",
                    ]
                )
            self.assertEqual(0, rc)
            result = json.loads(stdout.getvalue())
            self.assertTrue(result["valid"])

    def test_install_skill_with_source(self) -> None:
        """tool-installer install-skill --source works with dry-run."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / ".codex"
            codex.mkdir()
            (codex / "skill-sources.json").write_text(
                json.dumps({
                    "sources": [
                        {
                            "name": "test-skills",
                            "repo": "owner/skills-repo",
                            "path": "skills/my-skill",
                            "branch": "main",
                            "description": "Test",
                        }
                    ]
                }),
                encoding="utf-8",
            )
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = cli.main(
                    [
                        "tool-installer",
                        "install-skill",
                        "--root",
                        str(root),
                        "--source",
                        "test-skills",
                        "--skill-name",
                        "my-skill",
                        "--dry-run",
                        "true",
                    ]
                )
            self.assertEqual(0, rc)
            result = json.loads(stdout.getvalue())
            # The source resolves the repo and path, then dry-run reports it
            self.assertTrue(result["valid"])
            self.assertEqual("my-skill", result["skillName"])


    def test_ensure_mcp_servers_dry_run(self) -> None:
        """tool-installer ensure-mcp-servers --dry-run true works without side effects."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = cli.main(
                    [
                        "tool-installer",
                        "ensure-mcp-servers",
                        "--root",
                        str(root),
                        "--dry-run",
                        "true",
                    ]
                )
            self.assertEqual(0, rc)
            result = json.loads(stdout.getvalue())
            self.assertTrue(result["valid"])
            self.assertEqual("EnsureMCPServers", result["mode"])

    def test_ensure_mcp_servers_checks_all_mcp_targets(self) -> None:
        """ensure_mcp_servers runs every install_*_mcp installer."""
        from unittest.mock import patch

        from tools.sdd_cli.tool_installer import ensure_mcp_servers

        dummy = {"valid": True, "actions": [], "findings": []}
        with patch("tools.sdd_cli.tool_installer.install_playwright_mcp", return_value=dummy) as pw, patch(
            "tools.sdd_cli.tool_installer.install_grafana_mcp", return_value=dummy
        ) as gf, patch(
            "tools.sdd_cli.tool_installer.install_k8s_mcp", return_value=dummy
        ) as k8s, patch(
            "tools.sdd_cli.tool_installer.install_gitea_mcp", return_value=dummy
        ) as gt, patch(
            "tools.sdd_cli.tool_installer.install_openproject_mcp", return_value=dummy
        ) as op:
            result = ensure_mcp_servers(Path("."), dry_run=True)

        self.assertTrue(result["valid"])
        pw.assert_called_once()
        gf.assert_called_once()
        k8s.assert_called_once()
        gt.assert_called_once()
        op.assert_called_once()

    def test_stack_tests_bare_dry_run_flag(self) -> None:
        """stack-tests --dry-run (no value) works like --dry-run true."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = cli.main(
                    [
                        "--root",
                        str(root),
                        "stack-tests",
                        "--dry-run",
                    ]
                )
            self.assertEqual(0, rc)
            self.assertIn("Stack tests: OK", stdout.getvalue())


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
                rc = cli.main(
                    [
                        "memory-search",
                        "search",
                        "--root",
                        str(root),
                        "--list-topics",
                        "--json",
                    ]
                )
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
                rc = cli.main(
                    [
                        "environment-lab",
                        "validate-gitea-runner",
                        "--root",
                        str(root),
                        "--dry-run",
                        "true",
                    ]
                )
            self.assertEqual(0, rc)


if __name__ == "__main__":
    unittest.main()
