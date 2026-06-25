from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

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

    def test_infra_up_builds_docker_compose_command(self) -> None:
        calls = []

        def runner(command, cwd, env):
            calls.append(command)
            return 0

        self.assertEqual(0, cli.infra_compose("up", runner))
        self.assertIn("compose", calls[0])
        self.assertEqual(["up", "-d", "--remove-orphans"], calls[0][-3:])

    def test_e2e_docker_builds_command_without_running_services(self) -> None:
        calls = []

        def runner(command, cwd, env):
            calls.append(command)
            return 0

        with tempfile.TemporaryDirectory() as tmp:
            config = cli.REPO_ROOT / ".codex" / "client-tools.local.json"
            # This command prefers env vars, so no local secret file needed.
            old_site = cli.os.environ.get("E2E_SITE_URL")
            old_api = cli.os.environ.get("E2E_API_URL")
            cli.os.environ["E2E_SITE_URL"] = "https://site.example.test"
            cli.os.environ["E2E_API_URL"] = "https://api.example.test"
            try:
                self.assertEqual(0, cli.e2e_docker(type("Args", (), {"playwright_args": ["--", "--list"]})(), runner))
            finally:
                restore_env("E2E_SITE_URL", old_site)
                restore_env("E2E_API_URL", old_api)
        self.assertEqual(["docker", "image", "inspect", cli.E2E_IMAGE], calls[0])
        self.assertIn("docker", calls[1][0])
        self.assertIn("--list", calls[1][-1])


def arg(root: Path, message: Path):
    return type("Args", (), {"root": str(root), "message_file": str(message)})()


def restore_env(key: str, value: str | None) -> None:
    if value is None:
        cli.os.environ.pop(key, None)
    else:
        cli.os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
