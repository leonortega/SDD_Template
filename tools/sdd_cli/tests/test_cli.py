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
            for value in (
                "ABC-1: change",
                "openspec/add-thing: change",
                "[SDD] maintenance",
            ):
                msg.write_text(value, encoding="utf-8")
                self.assertEqual(0, cli.validate_commit_message(arg(root, msg)))
            msg.write_text("plain message", encoding="utf-8")
            self.assertEqual(1, cli.validate_commit_message(arg(root, msg)))

    def test_knowledge_search_filters_terms_and_json_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            knowledge = root / "knowledge" / "errors"
            knowledge.mkdir(parents=True)
            (knowledge / "failure-patterns.md").write_text(
                "# Docker Backend Timeout\n\n- Type: Pattern\n- Status: Active\n- Source: test\n- Last verified: 2026-06-25\n\nDocker failed.\n",
                encoding="utf-8",
            )
            rows = cli.search_knowledge(root, ["docker"], False)
            self.assertEqual(1, len(rows))
            self.assertEqual("Docker Backend Timeout", rows[0]["title"])
            self.assertEqual("knowledge", rows[0]["root"])

    def test_knowledge_search_indexes_all_three_roots(self) -> None:
        """knowledge/, docs/, and openspec/specs/ are all searchable KB roots."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            knowledge = root / "knowledge" / "errors"
            knowledge.mkdir(parents=True)
            (knowledge / "failure-patterns.md").write_text(
                "# Docker Backend Timeout\n\nDocker failed.\n",
                encoding="utf-8",
            )
            docs = root / "docs" / "architecture"
            docs.mkdir(parents=True)
            (docs / "deployment.md").write_text(
                "# Deployment\n\n## Environments\n\nDeploy via Nexus.\n",
                encoding="utf-8",
            )
            (root / "docs" / "README.md").write_text(
                "# Docs Index\n\nIgnored index file.\n",
                encoding="utf-8",
            )
            specs = root / "openspec" / "specs" / "checkout"
            specs.mkdir(parents=True)
            (specs / "spec.md").write_text(
                "# Checkout\n\n## Purpose\n\nUsers can pay with a card.\n",
                encoding="utf-8",
            )

            # Search hits the right root; each row tags its source root.
            rows = cli.search_knowledge(root, ["checkout"], False)
            self.assertEqual(1, len(rows))
            self.assertEqual("Checkout", rows[0]["title"])
            self.assertEqual("openspec/specs", rows[0]["root"])
            self.assertEqual(
                "openspec/specs/checkout/spec.md", rows[0]["file"]
            )
            docs_rows = cli.search_knowledge(root, ["nexus"], False)
            self.assertEqual(1, len(docs_rows))
            self.assertEqual("docs", docs_rows[0]["root"])
            self.assertEqual("docs/architecture/deployment.md", docs_rows[0]["file"])

            # Terms from any root match independently.
            self.assertEqual(1, len(cli.search_knowledge(root, ["docker"], False)))
            self.assertEqual(1, len(cli.search_knowledge(root, ["deploy"], False)))

            # No-query dict exposes all roots and the merged file list.
            index = cli.search_knowledge(root, [], False)
            self.assertEqual("knowledge", index["knowledgeRoot"])
            self.assertEqual("docs", index["docsRoot"])
            self.assertEqual("openspec/specs", index["specsRoot"])
            self.assertEqual(
                [
                    "docs/architecture/deployment.md",
                    "knowledge/errors/failure-patterns.md",
                    "openspec/specs/checkout/spec.md",
                ],
                sorted(index["files"]),
            )
            # README index files are excluded from the file list.
            self.assertNotIn("docs/README.md", index["files"])

            # list-topics rows carry root too.
            topics = cli.search_knowledge(root, [], True)
            self.assertEqual(3, len(topics))
            self.assertEqual(
                {"knowledge", "docs", "openspec/specs"},
                {row["root"] for row in topics},
            )

    def test_knowledge_search_docs_and_specs_roots_are_optional(self) -> None:
        """search_knowledge works when docs//openspec/specs/ are absent."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            knowledge = root / "knowledge" / "errors"
            knowledge.mkdir(parents=True)
            (knowledge / "failure-patterns.md").write_text(
                "# Docker Backend Timeout\n\nDocker failed.\n",
                encoding="utf-8",
            )
            index = cli.search_knowledge(root, [], False)
            self.assertIsNone(index["docsRoot"])
            self.assertIsNone(index["specsRoot"])
            self.assertEqual(
                ["knowledge/errors/failure-patterns.md"], index["files"]
            )
            self.assertEqual(1, len(cli.search_knowledge(root, ["docker"], False)))

    def test_classify_knowledge_maps_signals_to_candidate_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = cli.classify_knowledge(
                "Fixed Playwright login timeout",
                ["tests/e2e/login.spec.ts", "src/auth/client.ts"],
                "1 failed, 2 passed",
                root,
            )
            self.assertFalse(result["noChanges"])
            files = [c["file"] for c in result["candidates"]]
            self.assertTrue(any(f.startswith("knowledge/errors/") for f in files))
            self.assertTrue(any(f.startswith("knowledge/fixes/") for f in files))
            self.assertTrue(any(f.startswith("knowledge/implementation/") for f in files))
            self.assertEqual(files, sorted(files))

    def test_classify_knowledge_no_signals_returns_no_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = cli.classify_knowledge(
                "Bump dependency versions",
                ["package.json", "requirements.txt"],
                "all 12 passed",
                root,
            )
            self.assertTrue(result["noChanges"])
            self.assertEqual([], result["candidates"])

    def test_classify_knowledge_docs_paths_map_to_docs_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = cli.classify_knowledge(
                "Document auth API",
                ["docs/api/auth-service.md"],
                "",
                root,
            )
            self.assertFalse(result["noChanges"])
            self.assertIn("docs/api/auth-service.md", result["markers"]["docs"])

    def test_classify_knowledge_spec_only_changes_map_to_the_spec(self) -> None:
        """Archived-spec edits map to the spec itself — no spurious knowledge entries."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = cli.classify_knowledge(
                "Fixed checkout error",
                ["openspec/specs/checkout/spec.md"],
                "1 failed: timeout",
                root,
            )
            self.assertFalse(result["noChanges"])
            # The spec file is the candidate (the KB record), not a new knowledge file.
            self.assertEqual(
                ["openspec/specs/checkout/spec.md"],
                result["markers"]["specs"],
            )
            self.assertEqual([], result["markers"]["knowledge"])
            self.assertEqual([], result["markers"]["docs"])
            files = [c["file"] for c in result["candidates"]]
            self.assertEqual(["openspec/specs/checkout/spec.md"], files)

    def test_classify_knowledge_mixed_spec_and_source_keeps_signals(self) -> None:
        """Spec changes alongside source keep keyword + implementation signals."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = cli.classify_knowledge(
                "Fixed checkout error",
                ["openspec/specs/checkout/spec.md", "src/checkout/api.ts"],
                "1 failed: timeout",
                root,
            )
            self.assertFalse(result["noChanges"])
            self.assertIn(
                "openspec/specs/checkout/spec.md", result["markers"]["specs"]
            )
            # Source + failure signals still fire for the non-spec part.
            self.assertTrue(
                any(f.startswith("knowledge/errors/") for f in result["markers"]["knowledge"])
            )
            self.assertTrue(
                any(f.startswith("knowledge/implementation/") for f in result["markers"]["knowledge"])
            )

    def test_delivery_modes_cover_common_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = root / "project-profile.json"
            profile.write_text(
                json.dumps({"workflow": {"ticketKeyPattern": "ABC-[0-9]+"}}),
                encoding="utf-8",
            )
            self.assertEqual(
                "ABC-[0-9]+",
                cli.run_delivery_mode("ReadProjectProfile", {"path": str(profile)}),
            )
            self.assertEqual(
                "ABC-123",
                cli.run_delivery_mode(
                    "ExtractTicketKey",
                    {"message": "ABC-123: test", "pattern": "ABC-[0-9]+"},
                ),
            )
            ready = cli.run_delivery_mode(
                "ClassifyTicketReadiness",
                {
                    "title": "Add search",
                    "description": "Acceptance criteria: users should search clients. Validation: add tests.",
                },
            )
            self.assertEqual("ready", ready["status"])

    def test_openproject_time_activity_resolves_per_stage_with_default(self) -> None:
        config = {
            "timeTelemetry": {
                "defaultActivityName": "Other",
                "activityByStage": {
                    "dev-flow-implement-ticket": {"activityName": "Development"},
                    "dev-ops-deploy-qa": {"activityId": "4", "activityName": "Testing"},
                },
            }
        }

        development = cli.run_delivery_mode(
            "ResolveOpenProjectTimeActivity",
            {
                "workflow-stage": "dev-flow-implement-ticket",
                "input-json": json.dumps(config),
            },
        )
        fallback = cli.run_delivery_mode(
            "ResolveOpenProjectTimeActivity",
            {
                "workflow-stage": "unknown-stage",
                "input-json": json.dumps(config),
            },
        )
        testing = cli.run_delivery_mode(
            "ResolveOpenProjectTimeActivity",
            {
                "workflow-stage": "dev-ops-deploy-qa",
                "input-json": json.dumps(config),
            },
        )

        self.assertTrue(development["valid"])
        self.assertEqual("Development", development["activityName"])
        self.assertTrue(development["configuredByStage"])
        self.assertEqual("Other", fallback["activityName"])
        self.assertEqual("4", testing["activityId"])

    def test_audit_warns_when_openproject_time_activity_map_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / ".codex" / "project-profile.json", "{}")
            write(root / ".codex" / "project-profile.schema.json", "{}")
            write(
                root / ".codex" / "client-tools.local.json",
                json.dumps(
                    {
                        "openProject": {
                            "timeTelemetry": {
                                "enabled": True,
                                "activityName": "Development",
                            }
                        }
                    }
                ),
            )

            result = cli.run_configure_mode("Audit", root, {}, False)
            findings = {item["key"] for item in result["findings"]}

            self.assertIn("openProject.timeTelemetry.activityByStage", findings)

            write(
                root / ".codex" / "client-tools.local.json",
                json.dumps(
                    {
                        "openProject": {
                            "timeTelemetry": {
                                "enabled": True,
                                "activityFlow": {
                                    "Development": ["dev-flow-implement-ticket"]
                                },
                                "activityByStage": {
                                    "dev-flow-implement-ticket": {
                                        "activityName": "Testing"
                                    }
                                },
                            }
                        }
                    }
                ),
            )
            drift = cli.run_configure_mode("Audit", root, {}, False)
            drift_findings = {item["key"] for item in drift["findings"]}
            self.assertIn("openProject.timeTelemetry.activityFlow", drift_findings)

    def test_configure_audit_is_native_and_unsupported_modes_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for path in (
                "README.md",
                ".codex/delivery-policy.json",
                ".codex/skills/_shared/delivery-contract.md",
                "docs/conventions/context-management.md",
                "infra/compose.yml",
                "lefthook.yml",
                "tools/sdd_cli/cli.py",
            ):
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("x", encoding="utf-8")
            profile = root / ".codex" / "project-profile.json"
            profile.parent.mkdir(parents=True, exist_ok=True)
            profile.write_text(
                json.dumps(
                    {"quality": {"gates": [{"id": "restore", "required": True}]}}
                ),
                encoding="utf-8",
            )
            (root / ".codex" / "project-profile.schema.json").write_text(
                "{}", encoding="utf-8"
            )

            audit = cli.run_configure_mode("Audit", root, {}, False)
            self.assertTrue(audit["valid"])
            unsupported = cli.run_configure_mode("LegacyOnly", root, {}, False)
            self.assertFalse(unsupported["valid"])
            self.assertIn(
                "Port this mode into tools/sdd_cli", unsupported["nextAction"]
            )
            self.assertNotIn("fallback", json.dumps(unsupported).lower())

    def test_all_configure_modes_have_native_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root / ".codex" / "project-profile.json",
                json.dumps({"providers": {"deployment": {"id": "example"}}}),
            )
            write(root / ".codex" / "client-tools.local.json", "{}")
            for mode in cli.ALL_CONFIGURE_MODES:
                result = cli.run_configure_mode(mode, root, {}, True)
                self.assertNotIn(
                    "Mode is not implemented in native Python", json.dumps(result), mode
                )

    def test_discover_project_guidance_returns_stack_tags_and_skills(
        self,
    ) -> None:
        """DiscoverProjectGuidance returns stackTags and internet-found skills."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / ".codex"
            codex.mkdir()
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

            with patch("tools.sdd_cli.guidance._search_stack_tokens") as mock_search:
                mock_search.return_value = (
                    [{"package_skill": "github/awesome-copilot@react"}],
                    [],
                )
                result = cli.run_configure_mode(
                    "DiscoverProjectGuidance", root, {}, False
                )
            self.assertTrue(result["valid"])
            self.assertIn("stackTags", result)
            self.assertIn("react", result["stackTags"])
            self.assertIn("github/awesome-copilot@react", result["foundSkills"])

    def test_project_profile_local_overlay_merges_with_common_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / ".codex"
            codex.mkdir()
            (codex / "project-profile.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "providers": {"deployment": {"id": "docker-desktop"}},
                        "workflow": {"ticketKeyPattern": "ABC-[0-9]+"},
                        "quality": {"gates": [{"id": "secret-scan", "required": True}]},
                    }
                ),
                encoding="utf-8",
            )
            (codex / "project-profile.local.json").write_text(
                json.dumps(
                    {
                        "stack": {
                            "languages": ["python"],
                            "frameworks": [],
                            "testFrameworks": ["unittest"],
                        }
                    }
                ),
                encoding="utf-8",
            )

            profile = cli.load_project_profile(root)
            self.assertEqual(["python"], profile["stack"]["languages"])
            self.assertEqual("ABC-[0-9]+", cli.read_ticket_pattern(root))
            self.assertEqual("docker-desktop", cli.selected_deployment_provider(root))
            required = cli.run_configure_mode("AuditQualityGates", root, {}, False)
            self.assertEqual(["secret-scan"], required["requiredGates"])

    def test_set_project_stack_writes_local_profile_only_and_normalizes_answers(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / ".codex"
            codex.mkdir()
            common = codex / "project-profile.json"
            common.write_text(json.dumps({"schemaVersion": 1}), encoding="utf-8")
            local = codex / "project-profile.local.json"
            local.write_text(
                json.dumps(
                    {
                        "stack": {
                            "languages": ["go"],
                            "frameworks": [],
                            "testFrameworks": ["pytest"],
                        }
                    }
                ),
                encoding="utf-8",
            )
            before_common = common.read_text(encoding="utf-8")

            result = cli.run_configure_mode(
                "SetProjectStack",
                root,
                {
                    "frontend": "React + TypeScript",
                    "backend": "none",
                    "database": "",
                },
            )

            self.assertTrue(result["valid"])
            self.assertEqual(before_common, common.read_text(encoding="utf-8"))
            profile = json.loads(local.read_text(encoding="utf-8"))
            stack = profile["stack"]
            self.assertEqual(
                {"applies": True, "value": "React + TypeScript"}, stack["frontend"]
            )
            self.assertEqual({"applies": False, "value": ""}, stack["backend"])
            self.assertEqual({"applies": False, "value": ""}, stack["database"])
            self.assertEqual(["go"], stack["languages"])
            self.assertEqual([], stack["frameworks"])
            self.assertEqual(["pytest"], stack["testFrameworks"])
            self.assertEqual("needs-user-validation", stack["metadataValidationStatus"])
            self.assertTrue(stack["selectionRecorded"])
            for empty_value in ("", "none", "no", "n/a"):
                self.assertEqual(
                    {"applies": False, "value": ""},
                    cli.normalize_stack_domain(empty_value),
                )

    def test_scaffold_project_files_creates_only_stack_independent_skeleton(
        self,
    ) -> None:
        """ScaffoldProjectFiles creates only src/ and tests/ + delegation marker."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / ".codex"
            codex.mkdir()
            (codex / "project-profile.local.json").write_text(
                json.dumps(
                    {
                        "stack": {
                            "frontend": {"applies": True, "value": "react"},
                            "backend": {"applies": False, "value": ""},
                            "database": {"applies": False, "value": ""},
                        }
                    }
                ),
                encoding="utf-8",
            )

            result = cli.run_configure_mode("ScaffoldProjectFiles", root, {}, False)

            self.assertTrue(result["valid"])
            self.assertTrue((root / "src").is_dir())
            self.assertTrue((root / "tests").is_dir())
            # Stack-specific artifacts are delegated to the AI scaffold skill —
            # the script never generates package.json/playwright for any stack.
            self.assertFalse((root / "e2e").exists())
            self.assertFalse((root / "package.json").exists())
            self.assertFalse((root / "playwright.config.ts").exists())
            keys = {item["key"] for item in result["actions"]}
            self.assertIn("stack.delegated", keys)

    def test_scaffold_project_files_delegates_for_any_stack(self) -> None:
        """Non-JS stacks get the same skeleton + delegation (no stack heuristics)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / ".codex"
            codex.mkdir()
            (codex / "project-profile.local.json").write_text(
                json.dumps(
                    {
                        "stack": {
                            "frontend": {"applies": True, "value": "asp.net"},
                            "backend": {"applies": True, "value": ".net"},
                            "database": {"applies": False, "value": ""},
                        }
                    }
                ),
                encoding="utf-8",
            )

            result = cli.run_configure_mode("ScaffoldProjectFiles", root, {}, False)

            self.assertTrue(result["valid"])
            self.assertTrue((root / "src").is_dir())
            self.assertTrue((root / "tests").is_dir())
            self.assertFalse((root / "package.json").exists())
            self.assertFalse((root / "playwright.config.ts").exists())
            keys = {item["key"] for item in result["actions"]}
            self.assertIn("stack.delegated", keys)

    def test_scaffold_k8s_delegates_dockerfiles_and_keeps_deterministic_manifests(
        self,
    ) -> None:
        """scaffold_k8s records stack.delegated without needing a classified stack."""
        from tools.sdd_cli.environment_lab import scaffold_k8s

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / ".codex"
            codex.mkdir()
            (codex / "project-profile.local.json").write_text(
                json.dumps(
                    {
                        "stack": {
                            "frontend": {"applies": True, "value": "laravel"},
                            "backend": {"applies": True, "value": "spring"},
                            "database": {"applies": True, "value": "postgres"},
                        }
                    }
                ),
                encoding="utf-8",
            )
            (root / "infra" / "deployment").mkdir(parents=True)
            (root / "infra" / "deployment" / "apps.json").write_text(
                json.dumps(
                    {
                        "apps": [
                            {"appId": "front", "role": "web"},
                            {"appId": "back", "role": "api"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            result = scaffold_k8s(root, dry_run=True)

            self.assertTrue(result["valid"])
            keys = {item["key"] for item in result["actions"]}
            self.assertIn("stack.delegated", keys)

    def test_project_stack_discovery_returns_skills_from_internet(
        self,
    ) -> None:
        """DiscoverProjectGuidance searches the internet — never local skills."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / ".codex"
            codex.mkdir()
            (codex / "project-profile.json").write_text(
                json.dumps({"schemaVersion": 1}), encoding="utf-8"
            )
            skills_dir = codex / "skills"
            skills_dir.mkdir()
            # A rich local manifest must NOT influence discover results.
            (skills_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "categories": {
                            "test": {
                                "description": "Test skills",
                                "skills": ["playwright/SKILL.md"],
                            },
                            "core": {
                                "description": "Core skills",
                                "alwaysActive": True,
                                "skills": [],
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            # Patch the internet search during SetProjectStack too (it triggers
            # guidance setup) so the test never fires a real npx skills call.
            with patch("tools.sdd_cli.guidance._search_stack_tokens") as mock_setup_search:
                mock_setup_search.return_value = ([], [])
                cli.run_configure_mode(
                    "SetProjectStack",
                    root,
                    {
                        "frontend": "reactjs",
                        "backend": ".net-core-10",
                        "database": "sqlite",
                    },
                    False,
                )

            with patch("tools.sdd_cli.guidance._search_stack_tokens") as mock_search:
                mock_search.return_value = (
                    [{"package_skill": "internet/repo@stack-skill"}],
                    [],
                )
                result = cli.run_configure_mode(
                    "DiscoverProjectGuidance", root, {}, False
                )
            self.assertTrue(result["valid"])
            self.assertIn("stackTags", result)
            self.assertIn("reactjs", result["stackTags"])
            # Answer comes from the internet, not from the local manifest.
            self.assertIn("internet/repo@stack-skill", result["foundSkills"])
            self.assertNotIn("playwright", result["foundSkills"])

    def test_configure_values_json_file_stdin_inline_and_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".codex").mkdir()
            (root / ".codex" / "project-profile.local.json").write_text(
                "{}", encoding="utf-8"
            )
            values_file = root / "values.json"
            values_file.write_text(json.dumps({"frontend": "none"}), encoding="utf-8")

            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    0,
                    cli.configure_mode(
                        type(
                            "Args",
                            (),
                            {
                                "mode": "SetProjectStack",
                                "options": [
                                    "--root",
                                    str(root),
                                    "--values-json-file",
                                    "values.json",
                                ],
                            },
                        )()
                    ),
                )
            profile = json.loads(
                (root / ".codex" / "project-profile.local.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertFalse(profile["stack"]["frontend"]["applies"])

            with patch(
                "sys.stdin", io.StringIO(json.dumps({"backend": "FastAPI + Python"}))
            ), redirect_stdout(io.StringIO()):
                self.assertEqual(
                    0,
                    cli.configure_mode(
                        type(
                            "Args",
                            (),
                            {
                                "mode": "SetProjectStack",
                                "options": [
                                    "--root",
                                    str(root),
                                    "--values-json-stdin",
                                    "true",
                                ],
                            },
                        )()
                    ),
                )
            profile = json.loads(
                (root / ".codex" / "project-profile.local.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual("FastAPI + Python", profile["stack"]["backend"]["value"])

            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    0,
                    cli.configure_mode(
                        type(
                            "Args",
                            (),
                            {
                                "mode": "SetProjectStack",
                                "options": [
                                    "--root",
                                    str(root),
                                    "--values-json",
                                    json.dumps({"database": "PostgreSQL"}),
                                ],
                            },
                        )()
                    ),
                )
            profile = json.loads(
                (root / ".codex" / "project-profile.local.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual("PostgreSQL", profile["stack"]["database"]["value"])

            stderr = io.StringIO()
            with redirect_stdout(io.StringIO()), redirect_stderr(stderr):
                self.assertEqual(
                    1,
                    cli.main(
                        [
                            "configure",
                            "SetProjectStack",
                            "--root",
                            str(root),
                            "--values-json",
                            "{bad",
                        ]
                    ),
                )
            self.assertIn("Invalid JSON in --values-json", stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())

    def test_tool_install_copies_runtime_assets_and_excludes_tool_only_files(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "tool"
            target = root / "consumer"
            write(source / "README.md", "readme")
            write(source / "AGENTS.md", "agents")
            write(source / ".codex" / "skills" / "demo" / "SKILL.md", "skill")
            write(source / ".codex" / "project-profile.json", "{}")
            write(source / "openspec" / "config.yaml", "config")
            write(source / "openspec" / "changes" / "internal" / "tasks.md", "no")
            write(source / "tools" / "sdd_cli" / "cli.py", "tool")
            write(source / "tools" / "sdd_cli" / "tests" / "test_cli.py", "no")
            write(source / "knowledge" / "README.md", "knowledge")
            write(source / "infra" / "openproject" / "data" / "runtime.db", "no")
            write(
                source
                / "infra"
                / "openproject"
                / "openproject"
                / "pgdata"
                / "base"
                / "1"
                / "2619",
                "no",
            )

            result = cli.install_sdd_tool(source, target, "v0.1.0", "install")

            self.assertEqual("v0.1.0", result["version"])
            self.assertTrue(
                (target / ".codex" / "skills" / "demo" / "SKILL.md").exists()
            )
            self.assertTrue((target / "tools" / "sdd_cli" / "cli.py").exists())
            self.assertFalse(
                (target / "tools" / "sdd_cli" / "tests" / "test_cli.py").exists()
            )
            self.assertTrue((target / "knowledge" / "README.md").exists())
            # Template install should initialize a git repo for lefthook hooks
            self.assertTrue((target / ".git").exists())
            self.assertEqual("dev", cli.git_text(target, ["branch", "--show-current"]))
            self.assertEqual("", cli.git_text(target, ["remote"]))
            self.assertFalse(
                (target / "openspec" / "changes" / "internal" / "tasks.md").exists()
            )
            self.assertFalse(
                (target / "infra" / "openproject" / "data" / "runtime.db").exists()
            )
            self.assertFalse(
                (
                    target
                    / "infra"
                    / "openproject"
                    / "openproject"
                    / "pgdata"
                    / "base"
                    / "1"
                    / "2619"
                ).exists()
            )
            manifest = json.loads(
                (target / ".codex" / "sdd-tool-version.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertIn("tools/sdd_cli/cli.py", manifest["managedFiles"])

    def test_init_local_files_repairs_knowledge_and_env_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / ".codex" / "client-tools.example.json", "{}")
            write(root / ".codex" / "quality.example.json", "{}")
            write(
                root / "infra" / "openproject" / "variables.env.example",
                "OPENPROJECT_HOST=http://localhost\n",
            )
            write(
                root / "infra" / "monitoring" / "variables.env.example",
                "SEQ_URL=http://localhost:5341\n",
            )
            write(
                root / "infra" / "gitea" / "runner.env.example",
                "GITEA_INSTANCE_URL=http://localhost:3001\n",
            )

            result = cli.run_configure_mode("InitLocalFiles", root, {}, False)

            self.assertTrue(result["valid"])
            self.assertTrue((root / "knowledge" / "README.md").exists())
            self.assertTrue((root / "infra" / "openproject" / "variables.env").exists())

    def test_env_update_modes_validate_example_keys_and_preserve_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root / "infra" / "openproject" / "variables.env.example",
                "OPENPROJECT_HOST=\n",
            )
            write(
                root / "infra" / "openproject" / "variables.env",
                "OPENPROJECT_HOST=old\nOTHER=kept\n",
            )

            result = cli.run_configure_mode(
                "SetOpenProjectEnv", root, {"OPENPROJECT_HOST": "new"}, False
            )
            blocked = cli.run_configure_mode(
                "SetOpenProjectEnv", root, {"BAD": "x"}, False
            )

            self.assertTrue(result["valid"])
            self.assertFalse(blocked["valid"])
            env = cli.read_env_file(root / "infra" / "openproject" / "variables.env")
            self.assertEqual("new", env["OPENPROJECT_HOST"])
            self.assertEqual("kept", env["OTHER"])

    def test_split_infra_env_prunes_stale_keys_and_preserves_current_values(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root / "infra" / "openproject" / "variables.env.example",
                "OPENPROJECT_TAG=17\nOPENPROJECT_SECRET_KEY_BASE=placeholder\n",
            )
            write(
                root / "infra" / "monitoring" / "variables.env.example",
                "SEQ_URL=http://localhost:5341\n",
            )
            write(
                root / "infra" / "openproject" / "variables.env",
                "OPENPROJECT_TAG=old\nSECRET_KEY=legacy\nSEQ_URL=http://old:5341\n",
            )
            write(
                root / "infra" / "monitoring" / "variables.env",
                "SEQ_URL=http://keep:5341\n",
            )

            result = cli.run_configure_mode("SplitInfraEnv", root, {}, False)

            self.assertTrue(result["valid"])
            openproject = cli.read_env_file(
                root / "infra" / "openproject" / "variables.env"
            )
            monitoring = cli.read_env_file(
                root / "infra" / "monitoring" / "variables.env"
            )
            self.assertEqual(
                {"OPENPROJECT_TAG", "OPENPROJECT_SECRET_KEY_BASE"}, set(openproject)
            )
            self.assertEqual("old", openproject["OPENPROJECT_TAG"])
            self.assertEqual({"SEQ_URL"}, set(monitoring))
            self.assertEqual("http://keep:5341", monitoring["SEQ_URL"])

    def test_audit_reports_env_template_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / ".codex" / "project-profile.json", "{}")
            write(root / ".codex" / "project-profile.schema.json", "{}")
            write(
                root / "infra" / "openproject" / "variables.env.example",
                "OPENPROJECT_TAG=17\nOPENPROJECT_SECRET_KEY_BASE=placeholder\n",
            )
            write(
                root / "infra" / "openproject" / "variables.env",
                "OPENPROJECT_TAG=17\nSECRET_KEY=legacy\n",
            )

            result = cli.run_configure_mode("Audit", root, {}, False)
            findings = {item["key"]: item["message"] for item in result["findings"]}

            self.assertFalse(result["valid"])
            self.assertIn("env.missing-template-keys", findings)
            self.assertIn(
                "OPENPROJECT_SECRET_KEY_BASE", findings["env.missing-template-keys"]
            )
            self.assertIn("env.stale-keys", findings)
            self.assertIn("SECRET_KEY", findings["env.stale-keys"])

    def test_config_infra_docs_match_openproject_and_runtime(self) -> None:
        repo = Path(__file__).resolve().parents[3]
        compose = (repo / "infra" / "openproject" / "compose.yml").read_text(
            encoding="utf-8"
        )
        configure = (
            repo / ".codex" / "skills" / "configure-dev-environment" / "SKILL.md"
        ).read_text(encoding="utf-8")

        self.assertIn("SECRET_KEY_BASE: ${OPENPROJECT_SECRET_KEY_BASE:", compose)
        self.assertNotIn(
            "OPENPROJECT_SECRET_KEY_BASE: ${OPENPROJECT_SECRET_KEY_BASE:", compose
        )
        self.assertIn("setup-lab", configure)

        self.assertIn("compose-up", configure)
        self.assertIn("set-project-stack", configure)

    def test_setup_lab_dry_run_returns_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / ".codex"
            codex.mkdir()
            (codex / "client-tools.example.json").write_text("{}", encoding="utf-8")
            (codex / "quality.example.json").write_text("{}", encoding="utf-8")
            write(
                root / "lefthook.yml",
                "pre-commit:\n  commands:\n    test:\n      run: echo ok\n",
            )
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

            from tools.sdd_cli.environment_lab import setup_lab

            result = setup_lab(root, dry_run=True)
            self.assertEqual("SetupLab", result["mode"])
            self.assertTrue(result["dryRun"])
            steps = result.get("steps", [])
            # At minimum: init-local-files, init-project-profile, quality-templates should be present
            self.assertGreaterEqual(len(steps), 3)
            # Verify the first few steps (before Docker-dependent ones) are valid
            for step in steps[:3]:
                self.assertTrue(
                    step.get("valid", True),
                    msg=f"Step failed: {step.get('mode', step.get('command', 'unknown'))}",
                )

    def test_seq_grafana_validation_uses_grafana_port_and_checks_provisioning(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root / "infra" / "monitoring" / "variables.env",
                "SEQ_URL=http://localhost:5341\nSEQ_ERROR_ALERT_WINDOW=1m\nSEQ_ERROR_ALERT_THRESHOLD=0\n",
            )
            write(
                root
                / "infra"
                / "monitoring"
                / "grafana"
                / "provisioning"
                / "datasources"
                / "infinity-health.yml",
                "datasource",
            )
            write(
                root
                / "infra"
                / "monitoring"
                / "grafana"
                / "provisioning"
                / "alerting"
                / "health-alerts.yml",
                "alerts",
            )
            seen: list[str] = []

            def fake_http_status(url: str, timeout: int = 5):
                seen.append(url)
                return 200, ""

            with patch.object(cli, "http_status", fake_http_status):
                result = cli.run_configure_mode(
                    "ValidateObservability", root, {}, False
                )

            self.assertTrue(result["valid"])
            self.assertEqual("ValidateObservability", result["mode"])
            self.assertIn("http://localhost:3001/api/health", seen)
            self.assertNotIn("http://localhost:3000/api/health", seen)
            keys = {item["key"] for item in result["actions"]}
            self.assertIn("grafana.infinity-health", keys)
            self.assertIn("grafana.health-alerts", keys)

    def test_tool_update_replaces_owned_files_and_preserves_consumer_files(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "tool"
            target = root / "consumer"
            write(source / "README.md", "one")
            write(source / ".codex" / "skills" / "demo" / "SKILL.md", "old")
            write(source / ".codex" / "skills" / "stale" / "SKILL.md", "remove later")
            cli.install_sdd_tool(source, target, "v0.1.0", "install")
            write(
                target / ".codex" / "project-profile.local.json",
                '{"stack": "consumer"}',
            )
            write(target / "src" / "app.txt", "product")

            write(source / ".codex" / "skills" / "demo" / "SKILL.md", "new")
            (source / ".codex" / "skills" / "stale" / "SKILL.md").unlink()
            result = cli.install_sdd_tool(source, target, "v0.2.0", "update")

            self.assertEqual("v0.2.0", result["version"])
            self.assertEqual(
                "new",
                (target / ".codex" / "skills" / "demo" / "SKILL.md").read_text(
                    encoding="utf-8"
                ),
            )
            self.assertFalse(
                (target / ".codex" / "skills" / "stale" / "SKILL.md").exists()
            )
            self.assertEqual(
                '{"stack": "consumer"}',
                (target / ".codex" / "project-profile.local.json").read_text(
                    encoding="utf-8"
                ),
            )
            self.assertEqual(
                "product", (target / "src" / "app.txt").read_text(encoding="utf-8")
            )

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

            with patch("tools.sdd_cli.tool_installer.git_text", fake_git_text):
                result = cli.install_sdd_tool(source, target, None, "install")

            self.assertEqual("v0.1.7", result["version"])
            manifest = json.loads(
                (target / ".codex" / "sdd-tool-version.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual("v0.1.7", manifest["version"])

    def test_tool_install_end_to_end_from_real_source_tree(self) -> None:
        """E2E: install the real repo source tree into a fresh consumer target.

        Replaces the deleted install_target fixture as the baseline: the target
        must reproduce the source tree exactly — managed files byte-identical,
        exclusions honored, manifest written with a source-matching checksum,
        and git bootstrapped on dev.
        """
        from tools.sdd_cli._shared import REPO_ROOT as real_root
        from tools.sdd_cli._shared import sdd_tool_checksum, sdd_tool_files

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            files = sdd_tool_files(real_root)
            result = cli.install_sdd_tool(real_root, target, "v0.0.0-e2e", "install")

            self.assertEqual("install", result["action"])
            self.assertEqual(len(files), result["managedFileCount"])
            self.assertGreater(len(files), 100)  # real tree is large

            # Key files exist and are byte-identical to the source tree.
            for relative in (
                "AGENTS.md",
                "lefthook.yml",
                ".codex/skills/manifest.json",
                ".codex/skills/docs-knowledge-maintenance/SKILL.md",
                "tools/sdd_cli/cli.py",
                "tools/sdd_cli/knowledge_search.py",
                "knowledge/README.md",
            ):
                self.assertTrue((target / relative).exists(), relative)
                self.assertEqual(
                    (real_root / relative).read_bytes(),
                    (target / relative).read_bytes(),
                    f"byte drift on {relative}",
                )

            # Exclusions honored: tool tests, pyc artifacts, and openspec changes are absent.
            self.assertFalse((target / "tools" / "sdd_cli" / "tests").exists())
            self.assertFalse((target / "openspec" / "changes").exists())
            self.assertFalse(any(p.suffix == ".pyc" for p in target.rglob("*")))

            # Manifest written with the real managed file list. The checksum is
            # compared against the SOURCE tree (every managed file exists there,
            # so a silently-missed copy or byte drift both fail this assertion).
            manifest = json.loads(
                (target / ".codex" / "sdd-tool-version.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual("v0.0.0-e2e", manifest["version"])
            self.assertEqual(len(files), len(manifest["managedFiles"]))
            self.assertIn("tools/sdd_cli/cli.py", manifest["managedFiles"])
            self.assertNotIn(
                "tools/sdd_cli/tests/test_cli.py", manifest["managedFiles"]
            )
            self.assertEqual(
                manifest["checksumSha256"], sdd_tool_checksum(real_root, files)
            )

            # Blacklist semantics: every managed file is a tracked template file.
            # Untracked local files (secrets, runtime DB data, generated output)
            # are gitignored in the source tree and must never ship.
            tracked = set(cli.git_text(real_root, ["ls-files"]).splitlines())
            self.assertLessEqual(set(manifest["managedFiles"]), tracked)
            self.assertNotIn(
                "infra/monitoring/variables.env", manifest["managedFiles"]
            )
            self.assertNotIn(
                ".codex/client-tools.local.json", manifest["managedFiles"]
            )
            self.assertNotIn(".trunk/configs/.markdownlint.yaml", manifest["managedFiles"])

            # Git bootstrapped locally on the dev branch (lefthook-ready).
            self.assertTrue((target / ".git").exists())
            self.assertEqual("dev", cli.git_text(target, ["branch", "--show-current"]))

    def test_tool_update_preserves_legacy_managed_env_files(self) -> None:
        """Update never deletes consumer env files older manifests managed.

        Before the gitignore blacklist, the walk shipped untracked local files
        such as infra/monitoring/variables.env and recorded them in
        managedFiles. An update from a git source must not unlink those
        consumer-configured files just because they are no longer managed.
        """
        import subprocess as sp

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "tool"
            target = root / "consumer"
            source.mkdir(parents=True, exist_ok=True)
            (source / ".gitignore").write_text("*.env\n", encoding="utf-8")
            write(source / "AGENTS.md", "agents")
            write(
                source / "infra" / "monitoring" / "variables.env",
                "SECRET=src\n",
            )
            sp.run(["git", "init", "-q", str(source)], check=True)
            sp.run(["git", "add", "-A"], cwd=str(source), check=True)

            # Simulate an OLD install whose manifest managed the env file.
            write(
                target / ".codex" / "sdd-tool-version.json",
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "tool": "sdd-tool",
                        "version": "v0.1.0",
                        "managedFiles": [
                            "AGENTS.md",
                            "infra/monitoring/variables.env",
                        ],
                        "preservedFiles": [],
                    }
                ),
            )
            write(target / "AGENTS.md", "old agents")
            write(
                target / "infra" / "monitoring" / "variables.env",
                "SECRET=consumer\n",
            )

            result = cli.install_sdd_tool(source, target, "v0.2.0", "update")

            self.assertEqual("v0.2.0", result["version"])
            self.assertEqual(0, result["removedFileCount"])
            self.assertEqual(
                "SECRET=consumer\n",
                (target / "infra" / "monitoring" / "variables.env").read_text(
                    encoding="utf-8"
                ),
            )

    def test_walk_excludes_gitignored_untracked_but_keeps_rest(self) -> None:
        """walk_sdd_source_files treats .gitignore as an extra blacklist.

        Tracked files and untracked-but-not-ignored files are kept; only
        gitignored-and-untracked local files are excluded.
        """
        import subprocess as sp

        from tools.sdd_cli._shared import walk_sdd_source_files

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "tool"
            source.mkdir(parents=True, exist_ok=True)
            (source / "tracked.txt").write_text("t", encoding="utf-8")
            # Tracked-but-ignored file must still be kept (blacklist walk,
            # not a git whitelist) — mirrors .vscode/mcp.json in the real repo.
            (source / "ignored-but-tracked.txt").write_text("x", encoding="utf-8")
            (source / ".gitignore").write_text("*.env\nignored-but-tracked.txt\n", encoding="utf-8")
            (source / "secret.env").write_text("s", encoding="utf-8")
            (source / "kept-untracked.txt").write_text("k", encoding="utf-8")
            sp.run(["git", "init", "-q", str(source)], check=True)
            sp.run(["git", "add", "tracked.txt", ".gitignore"], cwd=str(source), check=True)
            # Force-add the ignored file — mirrors .vscode/mcp.json, which is
            # tracked in the real repo even though .gitignore lists it.
            sp.run(
                ["git", "add", "-f", "ignored-but-tracked.txt"],
                cwd=str(source),
                check=True,
            )

            files = walk_sdd_source_files(source)
            self.assertIn("tracked.txt", files)
            self.assertIn(".gitignore", files)
            self.assertIn("ignored-but-tracked.txt", files)
            self.assertIn("kept-untracked.txt", files)
            self.assertNotIn("secret.env", files)


def arg(root: Path, message: Path):
    return type("Args", (), {"root": str(root), "message_file": str(message)})()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
