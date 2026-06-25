from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
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
            (root / ".codex" / "project-profile.schema.json").write_text("{}", encoding="utf-8")

            audit = cli.run_configure_mode("Audit", root, {}, False)
            self.assertTrue(audit["valid"])
            unsupported = cli.run_configure_mode("LegacyOnly", root, {}, False)
            self.assertFalse(unsupported["valid"])
            self.assertIn("Port this mode into tools/sdd_cli", unsupported["nextAction"])
            self.assertNotIn("fallback", json.dumps(unsupported).lower())

    def test_all_configure_modes_have_native_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / ".codex" / "project-profile.json", json.dumps({"providers": {"deployment": {"id": "example"}}}))
            write(root / ".codex" / "client-tools.local.json", "{}")
            for mode in cli.CONFIGURE_MODE_NAMES:
                result = cli.run_configure_mode(mode, root, {}, True)
                self.assertNotIn("Mode is not implemented in native Python", json.dumps(result), mode)

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

    def test_set_project_stack_writes_local_profile_only_and_normalizes_answers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / ".codex"
            codex.mkdir()
            common = codex / "project-profile.json"
            common.write_text(json.dumps({"schemaVersion": 1}), encoding="utf-8")
            local = codex / "project-profile.local.json"
            local.write_text(json.dumps({"stack": {"languages": ["go"], "frameworks": [], "testFrameworks": ["pytest"]}}), encoding="utf-8")
            before_common = common.read_text(encoding="utf-8")

            result = cli.run_configure_mode("SetProjectStack", root, {
                "frontend": "React + TypeScript",
                "backend": "none",
                "database": "",
            })

            self.assertTrue(result["valid"])
            self.assertEqual(before_common, common.read_text(encoding="utf-8"))
            profile = json.loads(local.read_text(encoding="utf-8"))
            stack = profile["stack"]
            self.assertEqual({"applies": True, "value": "React + TypeScript"}, stack["frontend"])
            self.assertEqual({"applies": False, "value": ""}, stack["backend"])
            self.assertEqual({"applies": False, "value": ""}, stack["database"])
            self.assertEqual(["go", "typescript"], stack["languages"])
            self.assertEqual(["react"], stack["frameworks"])
            self.assertEqual(["pytest"], stack["testFrameworks"])
            self.assertTrue(stack["selectionRecorded"])
            for empty_value in ("", "none", "no", "n/a"):
                self.assertEqual({"applies": False, "value": ""}, cli.normalize_stack_domain(empty_value))

    def test_audit_recommended_tools_uses_profile_stack_and_reports_missing_stack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / ".codex"
            codex.mkdir()
            (codex / "project-profile.local.json").write_text(
                json.dumps({"stack": {"frontend": {"applies": True, "value": "React + TypeScript"}, "backend": {"applies": True, "value": "FastAPI + Python"}, "database": {"applies": True, "value": "PostgreSQL"}, "languages": [], "frameworks": [], "testFrameworks": []}}),
                encoding="utf-8",
            )

            audit = cli.run_configure_mode("AuditRecommendedTools", root, {}, False)
            self.assertIn("react", audit["detectedTags"])
            self.assertIn("typescript", audit["detectedTags"])
            self.assertIn("fastapi", audit["detectedTags"])
            self.assertNotIn("stack-context.missing", {item["key"] for item in audit["findings"]})

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".codex").mkdir()
            audit = cli.run_configure_mode("AuditRecommendedTools", root, {}, False)
            findings = {item["key"]: item["message"] for item in audit["findings"]}
            self.assertIn("stack-context.missing", findings)
            self.assertIn("frontend, backend, and database", findings["stack-context.missing"])

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".codex").mkdir()
            cli.run_configure_mode("SetProjectStack", root, {"frontend": "none", "backend": "none", "database": "none"}, False)
            audit = cli.run_configure_mode("AuditRecommendedTools", root, {}, False)
            self.assertNotIn("stack-context.missing", {item["key"] for item in audit["findings"]})

    def test_configure_values_json_file_stdin_inline_and_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".codex").mkdir()
            (root / ".codex" / "project-profile.local.json").write_text("{}", encoding="utf-8")
            values_file = root / "values.json"
            values_file.write_text(json.dumps({"frontend": "none"}), encoding="utf-8")

            with redirect_stdout(io.StringIO()):
                self.assertEqual(0, cli.configure_mode(type("Args", (), {"mode": "SetProjectStack", "options": ["--root", str(root), "--values-json-file", "values.json"]})()))
            profile = json.loads((root / ".codex" / "project-profile.local.json").read_text(encoding="utf-8"))
            self.assertFalse(profile["stack"]["frontend"]["applies"])

            with patch("sys.stdin", io.StringIO(json.dumps({"backend": "FastAPI + Python"}))), redirect_stdout(io.StringIO()):
                self.assertEqual(0, cli.configure_mode(type("Args", (), {"mode": "SetProjectStack", "options": ["--root", str(root), "--values-json-stdin", "true"]})()))
            profile = json.loads((root / ".codex" / "project-profile.local.json").read_text(encoding="utf-8"))
            self.assertEqual("FastAPI + Python", profile["stack"]["backend"]["value"])

            with redirect_stdout(io.StringIO()):
                self.assertEqual(0, cli.configure_mode(type("Args", (), {"mode": "SetProjectStack", "options": ["--root", str(root), "--values-json", json.dumps({"database": "PostgreSQL"})]})()))
            profile = json.loads((root / ".codex" / "project-profile.local.json").read_text(encoding="utf-8"))
            self.assertEqual("PostgreSQL", profile["stack"]["database"]["value"])

            stderr = io.StringIO()
            with redirect_stdout(io.StringIO()), redirect_stderr(stderr):
                self.assertEqual(1, cli.main(["configure", "SetProjectStack", "--root", str(root), "--values-json", "{bad"]))
            self.assertIn("Invalid JSON in --values-json", stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())

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
            write(source / ".codex" / "memory" / "MEMORY.md", "memory")
            write(source / ".codex" / "memory" / "memory_summary.md", "summary")
            write(source / ".codex" / "memory" / "retrieval-policy.md", "policy")
            write(source / "infra" / "openproject" / "data" / "runtime.db", "no")
            write(source / "infra" / "openproject" / "openproject" / "pgdata" / "base" / "1" / "2619", "no")

            result = cli.install_sdd_tool(source, target, "v0.1.0", "install")

            self.assertEqual("v0.1.0", result["version"])
            self.assertTrue((target / ".codex" / "skills" / "demo" / "SKILL.md").exists())
            self.assertTrue((target / "tools" / "sdd_cli" / "cli.py").exists())
            self.assertFalse((target / "tools" / "sdd_cli" / "tests" / "test_cli.py").exists())
            self.assertTrue((target / ".codex" / "memory" / "MEMORY.md").exists())
            self.assertTrue((target / ".codex" / "memory" / "memory_summary.md").exists())
            self.assertTrue((target / ".codex" / "memory" / "retrieval-policy.md").exists())
            self.assertTrue((target / ".git").exists())
            self.assertEqual("", cli.git_text(target, ["remote"]))
            self.assertEqual("dev", cli.git_text(target, ["branch", "--show-current"]))
            self.assertFalse((target / "openspec" / "changes" / "internal" / "tasks.md").exists())
            self.assertFalse((target / "infra" / "openproject" / "data" / "runtime.db").exists())
            self.assertFalse((target / "infra" / "openproject" / "openproject" / "pgdata" / "base" / "1" / "2619").exists())
            manifest = json.loads((target / ".codex" / "sdd-tool-version.json").read_text(encoding="utf-8"))
            self.assertIn("tools/sdd_cli/cli.py", manifest["managedFiles"])

    def test_init_local_files_repairs_memory_and_env_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / ".codex" / "client-tools.common.json", "{}")
            write(root / ".codex" / "quality.common.json", "{}")
            write(root / "infra" / "openproject" / "variables.env.example", "OPENPROJECT_HOST=http://localhost\n")
            write(root / "infra" / "monitoring" / "variables.env.example", "SEQ_URL=http://localhost:5341\n")
            write(root / "infra" / "azure" / "variables.env.example", "AZURE_LOCATION=westcentralus\n")
            write(root / "infra" / "gitea" / "runner.env.example", "GITEA_INSTANCE_URL=http://localhost:3001\n")

            result = cli.run_configure_mode("InitLocalFiles", root, {}, False)

            self.assertTrue(result["valid"])
            self.assertTrue((root / ".codex" / "memory" / "MEMORY.md").exists())
            self.assertTrue((root / ".codex" / "memory" / "memory_summary.md").exists())
            self.assertTrue((root / ".codex" / "memory" / "retrieval-policy.md").exists())
            self.assertTrue((root / "infra" / "openproject" / "variables.env").exists())

    def test_env_update_modes_validate_example_keys_and_preserve_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "infra" / "openproject" / "variables.env.example", "OPENPROJECT_HOST=\n")
            write(root / "infra" / "openproject" / "variables.env", "OPENPROJECT_HOST=old\nOTHER=kept\n")

            result = cli.run_configure_mode("SetOpenProjectEnv", root, {"OPENPROJECT_HOST": "new"}, False)
            blocked = cli.run_configure_mode("SetOpenProjectEnv", root, {"BAD": "x"}, False)

            self.assertTrue(result["valid"])
            self.assertFalse(blocked["valid"])
            env = cli.read_env_file(root / "infra" / "openproject" / "variables.env")
            self.assertEqual("new", env["OPENPROJECT_HOST"])
            self.assertEqual("kept", env["OTHER"])

    def test_split_infra_env_prunes_stale_keys_and_preserves_current_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "infra" / "openproject" / "variables.env.example", "OPENPROJECT_TAG=17\nOPENPROJECT_SECRET_KEY_BASE=placeholder\n")
            write(root / "infra" / "monitoring" / "variables.env.example", "SEQ_URL=http://localhost:5341\nRANCHER_APP_SEQ_URL=http://host.docker.internal:5341\n")
            write(root / "infra" / "azure" / "variables.env.example", "AZURE_LOCATION=westcentralus\n")
            write(root / "infra" / "openproject" / "variables.env", "OPENPROJECT_TAG=old\nSECRET_KEY=legacy\nSEQ_URL=http://old:5341\n")
            write(root / "infra" / "monitoring" / "variables.env", "SEQ_URL=http://keep:5341\nOTELCOL_AZURE_EVENT_HUB_DEV_CONNECTION_STRING=legacy\n")
            write(root / "infra" / "azure" / "variables.env", "OLD_AZURE=value\n")

            result = cli.run_configure_mode("SplitInfraEnv", root, {}, False)

            self.assertTrue(result["valid"])
            openproject = cli.read_env_file(root / "infra" / "openproject" / "variables.env")
            monitoring = cli.read_env_file(root / "infra" / "monitoring" / "variables.env")
            azure = cli.read_env_file(root / "infra" / "azure" / "variables.env")
            self.assertEqual({"OPENPROJECT_TAG", "OPENPROJECT_SECRET_KEY_BASE"}, set(openproject))
            self.assertEqual("old", openproject["OPENPROJECT_TAG"])
            self.assertEqual({"SEQ_URL", "RANCHER_APP_SEQ_URL"}, set(monitoring))
            self.assertEqual("http://keep:5341", monitoring["SEQ_URL"])
            self.assertEqual({"AZURE_LOCATION"}, set(azure))

    def test_audit_reports_env_template_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / ".codex" / "project-profile.json", "{}")
            write(root / ".codex" / "project-profile.schema.json", "{}")
            write(root / "infra" / "openproject" / "variables.env.example", "OPENPROJECT_TAG=17\nOPENPROJECT_SECRET_KEY_BASE=placeholder\n")
            write(root / "infra" / "openproject" / "variables.env", "OPENPROJECT_TAG=17\nSECRET_KEY=legacy\n")

            result = cli.run_configure_mode("Audit", root, {}, False)
            findings = {item["key"]: item["message"] for item in result["findings"]}

            self.assertFalse(result["valid"])
            self.assertIn("env.missing-template-keys", findings)
            self.assertIn("OPENPROJECT_SECRET_KEY_BASE", findings["env.missing-template-keys"])
            self.assertIn("env.stale-keys", findings)
            self.assertIn("SECRET_KEY", findings["env.stale-keys"])

    def test_config_infra_docs_match_openproject_and_trivy_runtime(self) -> None:
        repo = Path(__file__).resolve().parents[3]
        compose = (repo / "infra" / "openproject" / "compose.yml").read_text(encoding="utf-8")
        configure = (repo / ".codex" / "skills" / "configure-dev-environment" / "SKILL.md").read_text(encoding="utf-8")
        legacy = (repo / ".codex" / "skills" / "configure-infra-tools" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("SECRET_KEY_BASE: ${OPENPROJECT_SECRET_KEY_BASE:", compose)
        self.assertNotIn("OPENPROJECT_SECRET_KEY_BASE: ${OPENPROJECT_SECRET_KEY_BASE:", compose)
        self.assertIn("trivy image --download-db-only", configure)
        self.assertIn("trivy image --download-db-only", legacy)
        self.assertNotIn("trivy --download-db-only", configure)
        self.assertNotIn("trivy --download-db-only", legacy)
        self.assertIn("--values-json-stdin true", configure)
        self.assertIn("Do not use per-mode `--help`", configure)
        self.assertIn("Do not bypass the CLI by importing `run_configure_mode`", configure)
        self.assertIn("When the operator forbids PowerShell", configure)
        self.assertIn("ask for values one at a time", configure)
        self.assertIn("Do not batch multiple missing-value questions into one prompt", configure)

    def test_seq_grafana_validation_uses_grafana_port_and_checks_provisioning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "infra" / "monitoring" / "variables.env", "SEQ_URL=http://localhost:5341\nSEQ_ERROR_ALERT_WINDOW=1m\nSEQ_ERROR_ALERT_THRESHOLD=0\n")
            write(root / "infra" / "monitoring" / "grafana" / "provisioning" / "datasources" / "infinity-health.yml", "datasource")
            write(root / "infra" / "monitoring" / "grafana" / "provisioning" / "alerting" / "health-alerts.yml", "alerts")
            seen: list[str] = []

            def fake_http_status(url: str, timeout: int = 5):
                seen.append(url)
                return 200, ""

            with patch.object(cli, "http_status", fake_http_status):
                result = cli.run_configure_mode("ValidateObservability", root, {}, False)

            self.assertTrue(result["valid"])
            self.assertEqual("ValidateObservability", result["mode"])
            self.assertIn("http://localhost:3001/api/health", seen)
            self.assertNotIn("http://localhost:3000/api/health", seen)
            keys = {item["key"] for item in result["actions"]}
            self.assertIn("grafana.infinity-health", keys)
            self.assertIn("grafana.health-alerts", keys)

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
