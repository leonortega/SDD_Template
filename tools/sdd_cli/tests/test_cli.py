from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.sdd_cli import cli


class SddCliTests(unittest.TestCase):
    def test_commit_message_accepts_ticket_openspec_and_sdd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".codex").mkdir()
            (root / ".codex" / "project-profile.json").write_text(
                json.dumps({"workflow": {"ticketKeyPattern": "ABC-[0-9]+"}}),
                encoding="utf-8",
            )
            msg = root / "msg.txt"
            for value in ("ABC-1: change", "openspec/add-thing: change", "[SDD] maintenance"):
                msg.write_text(value, encoding="utf-8")
                self.assertEqual(0, cli.validate_commit_message(arg(root, msg)))
            msg.write_text("plain message", encoding="utf-8")
            self.assertEqual(1, cli.validate_commit_message(arg(root, msg)))

    def test_memory_search_filters_terms_and_json_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            memory = root / ".codex" / "memory"
            memory.mkdir(parents=True)
            (memory / "failure-patterns.md").write_text(
                "## Docker Backend Timeout\n\n- Type: Pattern\n- Status: Active\n- Source: test\n- Last verified: 2026-06-25\n\nDocker failed.\n",
                encoding="utf-8",
            )
            rows = cli.search_memory(root, ["docker"], False)
            self.assertEqual(1, len(rows))
            self.assertEqual("Docker Backend Timeout", rows[0]["title"])

    def test_delivery_modes_cover_common_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = root / "project-profile.json"
            profile.write_text(json.dumps({"workflow": {"ticketKeyPattern": "ABC-[0-9]+"}}), encoding="utf-8")
            self.assertEqual("ABC-[0-9]+", cli.run_delivery_mode("ReadProjectProfile", {"path": str(profile)}))
            self.assertEqual("ABC-123", cli.run_delivery_mode("ExtractTicketKey", {"message": "ABC-123: test", "pattern": "ABC-[0-9]+"}))
            ready = cli.run_delivery_mode("ClassifyTicketReadiness", {
                "title": "Add search",
                "description": "Acceptance criteria: users should search clients. Validation: add tests.",
            })
            self.assertEqual("ready", ready["status"])

    def test_workflow_telemetry_round_trips_and_renders(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = cli.run_delivery_mode("InitializeWorkflowTelemetry", {"repo-root": str(root), "ticket-key": "ABC-1"})
            self.assertTrue(result["exists"])
            cli.run_delivery_mode("AppendWorkflowTelemetry", {
                "repo-root": str(root),
                "ticket-key": "ABC-1",
                "input-json": json.dumps({
                    "workflowStage": "dev-flow-start-ticket",
                    "agentRole": "ticketStarter",
                    "startedUtc": "2026-06-25T10:00:00Z",
                    "finishedUtc": "2026-06-25T10:01:05Z",
                    "retryCount": 1,
                    "outcome": "PASS",
                }),
            })
            read = cli.run_delivery_mode("ReadWorkflowTelemetry", {
                "repo-root": str(root),
                "ticket-key": "ABC-1",
                "input-json": json.dumps({"status": "PASS", "currentRoute": "dev-flow-start-ticket"}),
            })
            self.assertEqual(65000, read["totalElapsedMilliseconds"])
            comment = cli.run_delivery_mode("RenderTicketComment", {"type": "WorkflowTiming", "input-json": json.dumps(read)})
            self.assertIn("IA generated workflow timing: ABC-1", comment)
            self.assertIn("| `dev-flow-start-ticket` | PASS | 1m 5s |", comment)

    def test_configure_audit_is_native_and_unsupported_modes_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for path in (
                "README.md",
                ".codex/delivery-policy.json",
                ".codex/skills/_shared/delivery-contract.md",
                "docs/context-management.md",
                "infra/compose.yml",
                "lefthook.yml",
                "tools/sdd_cli/cli.py",
            ):
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("x", encoding="utf-8")
            profile = root / ".codex" / "project-profile.json"
            profile.parent.mkdir(parents=True, exist_ok=True)
            profile.write_text(json.dumps({"quality": {"gates": [{"id": "restore", "required": True}]}}), encoding="utf-8")

            audit = cli.run_configure_mode("Audit", root, {}, False)
            self.assertTrue(audit["valid"])
            unsupported = cli.run_configure_mode("LegacyOnly", root, {}, False)
            self.assertFalse(unsupported["valid"])
            self.assertIn("PowerShell fallback is intentionally disabled", unsupported["nextAction"])

    def test_project_profile_local_overlay_merges_with_common_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / ".codex"
            codex.mkdir()
            (codex / "project-profile.json").write_text(
                json.dumps({
                    "schemaVersion": 1,
                    "providers": {"deployment": {"id": "rancher-desktop"}},
                    "workflow": {"ticketKeyPattern": "ABC-[0-9]+"},
                    "quality": {"gates": [{"id": "secret-scan", "required": True}]},
                    "adapters": {"deployment": ".codex/providers/deploy.rancher-desktop.md"},
                }),
                encoding="utf-8",
            )
            (codex / "project-profile.local.json").write_text(
                json.dumps({"stack": {"languages": ["python"], "frameworks": [], "testFrameworks": ["unittest"]}}),
                encoding="utf-8",
            )

            profile = cli.load_project_profile(root)
            self.assertEqual(["python"], profile["stack"]["languages"])
            self.assertEqual("ABC-[0-9]+", cli.read_ticket_pattern(root))
            self.assertEqual("rancher-desktop", cli.selected_deployment_provider(root))
            required = cli.run_configure_mode("AuditQualityGates", root, {}, False)
            self.assertEqual(["secret-scan"], required["requiredGates"])

    def test_tool_recommendations_local_overlay_merges_with_example_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / ".codex"
            codex.mkdir()
            (codex / "tool-recommendations.common.json").write_text(
                json.dumps({
                    "schemaVersion": 1,
                    "recommendations": [
                        {"id": "playwright-guidance", "name": "Playwright guidance", "type": "skill", "usedInSteps": []}
                    ],
                }),
                encoding="utf-8",
            )
            (codex / "tool-recommendations.local.json").write_text(
                json.dumps({
                    "recommendations": [
                        {"id": "playwright-guidance", "usedInSteps": ["qa"], "accepted": True},
                        {"id": "custom-guidance", "name": "Custom", "type": "reference", "usedInSteps": ["start"]},
                    ],
                }),
                encoding="utf-8",
            )

            catalog = cli.load_tool_recommendations_catalog(root)
            by_id = {item["id"]: item for item in catalog["recommendations"]}
            self.assertEqual(["qa"], by_id["playwright-guidance"]["usedInSteps"])
            self.assertTrue(by_id["playwright-guidance"]["accepted"])
            self.assertEqual("Custom", by_id["custom-guidance"]["name"])

    def test_infra_up_builds_docker_compose_command(self) -> None:
        calls = []

        def runner(command, cwd, env):
            calls.append(command)
            return 0

        self.assertEqual(0, cli.infra_compose("up", runner))
        self.assertIn("compose", calls[0])
        self.assertEqual(["up", "-d", "--remove-orphans"], calls[0][-3:])

    def test_tool_install_copies_runtime_assets_and_excludes_tool_only_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "tool"
            target = root / "consumer"
            write(source / "README.md", "readme")
            write(source / "AGENTS.md", "agents")
            write(source / ".codex" / "skills" / "demo" / "SKILL.md", "skill")
            write(source / ".codex" / "providers" / "repo.example.md", "provider")
            write(source / ".codex" / "project-profile.json", "{}")
            write(source / "openspec" / "config.yaml", "config")
            write(source / "openspec" / "changes" / "internal" / "tasks.md", "no")
            write(source / "tools" / "sdd_cli" / "cli.py", "tool")
            write(source / "tools" / "sdd_cli" / "tests" / "test_cli.py", "no")
            write(source / ".codex" / "memory" / "MEMORY.md", "no")
            write(source / "infra" / "openproject" / "data" / "runtime.db", "no")

            result = cli.install_sdd_tool(source, target, "v0.1.0", "install")

            self.assertEqual("v0.1.0", result["version"])
            self.assertTrue((target / ".codex" / "skills" / "demo" / "SKILL.md").exists())
            self.assertTrue((target / "tools" / "sdd_cli" / "cli.py").exists())
            self.assertFalse((target / "tools" / "sdd_cli" / "tests" / "test_cli.py").exists())
            self.assertFalse((target / ".codex" / "memory" / "MEMORY.md").exists())
            self.assertFalse((target / "openspec" / "changes" / "internal" / "tasks.md").exists())
            self.assertFalse((target / "infra" / "openproject" / "data" / "runtime.db").exists())
            manifest = json.loads((target / ".codex" / "sdd-tool-version.json").read_text(encoding="utf-8"))
            self.assertIn("tools/sdd_cli/cli.py", manifest["managedFiles"])

    def test_tool_update_replaces_owned_files_and_preserves_consumer_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "tool"
            target = root / "consumer"
            write(source / "README.md", "one")
            write(source / ".codex" / "skills" / "demo" / "SKILL.md", "old")
            write(source / ".codex" / "skills" / "stale" / "SKILL.md", "remove later")
            cli.install_sdd_tool(source, target, "v0.1.0", "install")
            write(target / ".codex" / "project-profile.local.json", '{"stack": "consumer"}')
            write(target / "src" / "app.txt", "product")

            write(source / ".codex" / "skills" / "demo" / "SKILL.md", "new")
            (source / ".codex" / "skills" / "stale" / "SKILL.md").unlink()
            result = cli.install_sdd_tool(source, target, "v0.2.0", "update")

            self.assertEqual("v0.2.0", result["version"])
            self.assertEqual("new", (target / ".codex" / "skills" / "demo" / "SKILL.md").read_text(encoding="utf-8"))
            self.assertFalse((target / ".codex" / "skills" / "stale" / "SKILL.md").exists())
            self.assertEqual('{"stack": "consumer"}', (target / ".codex" / "project-profile.local.json").read_text(encoding="utf-8"))
            self.assertEqual("product", (target / "src" / "app.txt").read_text(encoding="utf-8"))

    def test_tool_install_refuses_unmanaged_collision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "tool"
            target = root / "consumer"
            write(source / "README.md", "tool")
            write(target / "README.md", "consumer")

            with self.assertRaises(cli.CliError):
                cli.install_sdd_tool(source, target, "v0.1.0", "install")

    def test_tool_install_without_version_uses_latest_final_tag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "tool"
            target = root / "consumer"
            write(source / "README.md", "tool")

            def fake_git_text(repo: Path, args: list[str]) -> str:
                if args[:2] == ["tag", "--list"]:
                    return "v0.1.0\nv0.1.7-rc.2\nv0.1.6\nv0.1.7\n"
                return ""

            with patch.object(cli, "git_text", fake_git_text):
                result = cli.install_sdd_tool(source, target, None, "install")

            self.assertEqual("v0.1.7", result["version"])
            manifest = json.loads((target / ".codex" / "sdd-tool-version.json").read_text(encoding="utf-8"))
            self.assertEqual("v0.1.7", manifest["version"])

def arg(root: Path, message: Path):
    return type("Args", (), {"root": str(root), "message_file": str(message)})()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
