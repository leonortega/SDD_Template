"""Tests for the full-setup module."""

from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def tool_installer_mocks() -> list[patch]:
    """Patch all 7 tool_installer functions used by Stage 3 with defaults."""
    dummy_ok = {"valid": True, "actions": [], "findings": []}
    return [
        patch("tools.sdd_cli.tool_installer.install_codegraph", return_value=dummy_ok),
        patch("tools.sdd_cli.tool_installer.ensure_codebase_memory", return_value=dummy_ok),
        patch("tools.sdd_cli.tool_installer.install_claw_compactor", return_value=dummy_ok),
        patch("tools.sdd_cli.tool_installer.install_monorepo_docs_search", return_value=dummy_ok),
        patch("tools.sdd_cli.tool_installer.install_playwright_mcp", return_value=dummy_ok),
        patch("tools.sdd_cli.tool_installer.ensure_quality_tools", return_value=dummy_ok),
        patch("tools.sdd_cli.tool_installer.validate_manifest", return_value=dummy_ok),
    ]


@pytest.fixture
def guidance_mocks() -> list[patch]:
    """Patch setup_project_guidance used by Stage 4."""
    dummy_guidance = {
        "valid": True,
        "foundSkills": ["owner/repo@skill-1"],
        "installResults": [],
        "actions": [],
        "findings": [],
    }
    return [
        patch("tools.sdd_cli.guidance.setup_project_guidance",
               return_value=dummy_guidance),
    ]


# ── Stage 3: Tool Installation (remaining) ──────────────────────────────


def test_stage3_tool_installation_dry_run(tmp_path: Path) -> None:
    """stage3 returns valid=True in dry-run mode with no real calls."""
    from tools.sdd_cli.full_setup import stage3_tool_installation

    dummy_ok = {"valid": True, "actions": [], "findings": []}
    with patch("tools.sdd_cli.tool_installer.install_codegraph", return_value=dummy_ok):
        with patch("tools.sdd_cli.tool_installer.ensure_codebase_memory", return_value=dummy_ok):
            with patch("tools.sdd_cli.tool_installer.install_claw_compactor", return_value=dummy_ok):
                with patch("tools.sdd_cli.tool_installer.install_monorepo_docs_search", return_value=dummy_ok):
                    with patch("tools.sdd_cli.tool_installer.install_playwright_mcp", return_value=dummy_ok):
                        with patch("tools.sdd_cli.tool_installer.validate_manifest", return_value=dummy_ok):
                            result = stage3_tool_installation(tmp_path, dry_run=True)
    assert result["valid"] is True
    assert len(result["steps"]) == 7
    for step in result["steps"]:
        assert step.get("valid") is True
        assert "OK" in step.get("message", "")


def test_stage3_tool_installation_success(tmp_path: Path) -> None:
    """stage3 returns valid when all installers succeed."""
    from tools.sdd_cli.full_setup import stage3_tool_installation

    dummy_ok = {"valid": True, "actions": [], "findings": []}
    with patch("tools.sdd_cli.tool_installer.install_codegraph", return_value=dummy_ok):
        with patch("tools.sdd_cli.tool_installer.ensure_codebase_memory", return_value=dummy_ok):
            with patch("tools.sdd_cli.tool_installer.install_claw_compactor", return_value=dummy_ok):
                with patch("tools.sdd_cli.tool_installer.install_monorepo_docs_search", return_value=dummy_ok):
                    with patch("tools.sdd_cli.tool_installer.install_playwright_mcp", return_value=dummy_ok):
                        with patch("tools.sdd_cli.tool_installer.validate_manifest", return_value=dummy_ok):
                            result = stage3_tool_installation(tmp_path, dry_run=False)

    assert result["valid"] is True
    assert len(result["steps"]) == 7
    assert all(s.get("valid") for s in result["steps"])


def test_stage3_tool_installation_partial_failure(tmp_path: Path) -> None:
    """stage3 propagates individual tool failures without halting."""
    from tools.sdd_cli.full_setup import stage3_tool_installation

    dummy_ok = {"valid": True, "actions": [], "findings": []}
    dummy_fail = {"valid": False, "actions": [], "findings": [
        {"path": "tools/codegraph", "key": "verify", "message": "npx not available", "severity": "error"}
    ]}
    with patch("tools.sdd_cli.tool_installer.install_codegraph", return_value=dummy_fail):
        with patch("tools.sdd_cli.tool_installer.ensure_codebase_memory", return_value=dummy_ok):
            with patch("tools.sdd_cli.tool_installer.install_claw_compactor", return_value=dummy_ok):
                with patch("tools.sdd_cli.tool_installer.install_monorepo_docs_search", return_value=dummy_fail):
                    with patch("tools.sdd_cli.tool_installer.install_playwright_mcp", return_value=dummy_ok):
                        with patch("tools.sdd_cli.tool_installer.validate_manifest", return_value=dummy_ok):
                            result = stage3_tool_installation(tmp_path, dry_run=False)

    assert result["valid"] is False
    assert len(result["steps"]) == 7
    assert result["steps"][0]["valid"] is False
    assert result["steps"][1]["valid"] is False
    assert result["steps"][2]["valid"] is True
    assert result["steps"][3]["valid"] is True
    assert result["steps"][4]["valid"] is True
    assert result["steps"][5]["valid"] is True
    assert result["steps"][6]["valid"] is True


def test_stage3_tool_installation_exception(tmp_path: Path) -> None:
    """stage3 handles an installer raising an exception."""
    from tools.sdd_cli.full_setup import stage3_tool_installation

    dummy_ok = {"valid": True, "actions": [], "findings": []}
    with patch("tools.sdd_cli.tool_installer.install_codegraph",
               side_effect=RuntimeError("Network error")):
        with patch("tools.sdd_cli.tool_installer.ensure_codebase_memory", return_value=dummy_ok):
            with patch("tools.sdd_cli.tool_installer.install_claw_compactor", return_value=dummy_ok):
                with patch("tools.sdd_cli.tool_installer.install_monorepo_docs_search", return_value=dummy_ok):
                    with patch("tools.sdd_cli.tool_installer.install_playwright_mcp", return_value=dummy_ok):
                        with patch("tools.sdd_cli.tool_installer.validate_manifest", return_value=dummy_ok):
                            result = stage3_tool_installation(tmp_path, dry_run=False)

    assert result["valid"] is False
    assert result["steps"][0]["valid"] is False
    assert "Network error" in result["steps"][0].get("message", "")
    assert result["steps"][1]["valid"] is True


# ── run_full_setup ───────────────────────────────────────────────────────


def test_run_full_setup_help(capsys: Any, tool_installer_mocks: Any, guidance_mocks: Any) -> None:
    """full-setup with no args runs prereqs stage and prints valid/invalid."""
    from tools.sdd_cli.full_setup import run_full_setup

    mock_lab_ok = {"valid": True, "steps": [], "summary": {}}

    with patch.object(sys, "version_info", (3, 15)):
        with patch(
            "tools.sdd_cli.full_setup.run_native",
            return_value={"returncode": 0, "stdout": "v20.0.0", "stderr": ""},
        ):
            with patch("tools.sdd_cli.environment_lab.setup_lab",
                       return_value=mock_lab_ok):
                with contextlib.ExitStack() as stack:
                    for m in tool_installer_mocks + guidance_mocks:
                        stack.enter_context(m)
                    with patch("sys.platform", "linux"):
                        rc = run_full_setup([])
    captured = capsys.readouterr()
    output = captured.out
    assert "Stage1-Prerequisites" in output or "FULL SETUP" in output
    assert rc == 0


def test_run_full_setup_dry_run(capsys: Any, tool_installer_mocks: Any, guidance_mocks: Any) -> None:
    """full-setup --dry-run true runs without side effects."""
    from tools.sdd_cli.full_setup import run_full_setup

    with patch.object(sys, "version_info", (3, 15)):
        with patch(
            "tools.sdd_cli.full_setup.run_native",
            return_value={"returncode": 0, "stdout": "v20.0.0", "stderr": ""},
        ):
            with contextlib.ExitStack() as stack:
                for m in tool_installer_mocks + guidance_mocks:
                    stack.enter_context(m)
                with patch("sys.platform", "linux"):
                    rc = run_full_setup(["--dry-run", "true"])
    captured = capsys.readouterr()
    assert rc == 0


def test_run_full_setup_python_fails(capsys: Any, tool_installer_mocks: Any, guidance_mocks: Any) -> None:
    """full-setup returns 1 when Python version is too old."""
    from tools.sdd_cli.full_setup import run_full_setup

    mock_lab_ok = {"valid": True, "steps": [], "summary": {}}

    with patch.object(sys, "version_info", (3, 9)):  # Too old
        with patch(
            "tools.sdd_cli.full_setup.run_native",
            return_value={"returncode": 0, "stdout": "v20.0.0", "stderr": ""},
        ):
            with patch("tools.sdd_cli.environment_lab.setup_lab",
                       return_value=mock_lab_ok):
                with contextlib.ExitStack() as stack:
                    for m in tool_installer_mocks + guidance_mocks:
                        stack.enter_context(m)
                    with patch("sys.platform", "linux"):
                        rc = run_full_setup([])
    assert rc == 1


def test_run_full_setup_node_fails(capsys: Any, tool_installer_mocks: Any, guidance_mocks: Any) -> None:
    """full-setup returns 1 when Node.js is missing."""
    from tools.sdd_cli.full_setup import run_full_setup

    mock_lab_ok = {"valid": True, "steps": [], "summary": {}}

    with patch.object(sys, "version_info", (3, 15)):
        with patch(
            "tools.sdd_cli.full_setup.run_native",
            side_effect=[
                {"returncode": 127, "stdout": "", "stderr": "node not found"},
                {"returncode": 127, "stdout": "", "stderr": "npm not found"},
                {"returncode": 0, "stdout": "v20.0.0", "stderr": ""},
            ],
        ):
            with patch("tools.sdd_cli.environment_lab.setup_lab",
                       return_value=mock_lab_ok):
                with contextlib.ExitStack() as stack:
                    for m in tool_installer_mocks + guidance_mocks:
                        stack.enter_context(m)
                    with patch("sys.platform", "linux"):
                        rc = run_full_setup([])
    assert rc == 1


def test_run_full_setup_docker_fails(capsys: Any, tool_installer_mocks: Any, guidance_mocks: Any) -> None:
    """full-setup returns 1 when Docker is missing."""
    from tools.sdd_cli.full_setup import run_full_setup

    mock_lab_ok = {"valid": True, "steps": [], "summary": {}}

    with patch.object(sys, "version_info", (3, 15)):
        with patch(
            "tools.sdd_cli.full_setup.run_native",
            side_effect=[
                {"returncode": 0, "stdout": "v20.0.0", "stderr": ""},
                {"returncode": 0, "stdout": "10.0.0", "stderr": ""},
                {"returncode": 1, "stdout": "", "stderr": "docker not found"},
            ],
        ):
            with patch("tools.sdd_cli.environment_lab.setup_lab",
                       return_value=mock_lab_ok):
                with contextlib.ExitStack() as stack:
                    for m in tool_installer_mocks + guidance_mocks:
                        stack.enter_context(m)
                    with patch("sys.platform", "linux"):
                        rc = run_full_setup([])
    assert rc == 1


# ── Stage 2: Lab Setup ────────────────────────────────────────────────────


def test_stage2_lab_setup_dry_run() -> None:
    """stage2 returns valid=True with no side effects in dry-run mode."""
    from tools.sdd_cli.full_setup import stage2_lab_setup

    result = stage2_lab_setup(Path("."), dry_run=True)
    assert result["valid"] is True
    assert "Would run setup-lab" in str(result.get("actions", []))


def test_stage2_lab_setup_success() -> None:
    """stage2 returns valid when setup_lab succeeds."""
    from tools.sdd_cli.full_setup import stage2_lab_setup

    mock_lab_result = {
        "valid": True,
        "steps": [
            {"command": "init-local-files", "valid": True},
            {"command": "compose-up", "valid": True},
            {"command": "provision-users", "valid": True},
        ],
        "summary": {"gitea": {"url": "http://localhost:3000"}},
    }

    with patch("tools.sdd_cli.environment_lab.setup_lab",
               return_value=mock_lab_result) as mock_setup_lab:
        result = stage2_lab_setup(Path("."), dry_run=False)

    assert result["valid"] is True
    mock_setup_lab.assert_called_once_with(Path("."), dry_run=False)
    assert result["substeps"] == mock_lab_result["steps"]
    assert result["lab_summary"] == mock_lab_result["summary"]


def test_stage2_lab_setup_failure() -> None:
    """stage2 propagates setup_lab failures as findings."""
    from tools.sdd_cli.full_setup import stage2_lab_setup

    mock_lab_result = {
        "valid": False,
        "steps": [
            {"command": "init-local-files", "valid": True},
            {"command": "compose-up", "valid": False, "message": "docker compose up failed with exit code 1"},
            {"command": "provision-users", "valid": False, "errors": ["OpenProject not reachable"]},
        ],
        "summary": {},
    }

    with patch("tools.sdd_cli.environment_lab.setup_lab",
               return_value=mock_lab_result) as mock_setup_lab:
        result = stage2_lab_setup(Path("."), dry_run=False)

    assert result["valid"] is False
    mock_setup_lab.assert_called_once()
    failed_findings = [f for f in result.get("findings", []) if f.get("severity") == "error"]
    assert len(failed_findings) >= 2
    assert any("compose-up" in f.get("path", "") for f in failed_findings)
    assert any("provision-users" in f.get("path", "") for f in failed_findings)


def test_stage2_lab_setup_exception() -> None:
    """stage2 handles setup_lab raising an exception."""
    from tools.sdd_cli.full_setup import stage2_lab_setup

    with patch("tools.sdd_cli.environment_lab.setup_lab",
               side_effect=RuntimeError("Docker not running")):
        result = stage2_lab_setup(Path("."), dry_run=False)

    assert result["valid"] is False
    assert any("Docker not running" in f.get("message", "") for f in result.get("findings", []))


# ── Stage 1: Prerequisites ───────────────────────────────────────────────


def test_stage1_prerequisites_all_pass() -> None:
    """All prerequisites pass."""
    from tools.sdd_cli.full_setup import stage1_prerequisites

    with patch.object(sys, "version_info", (3, 15)):
        with patch(
            "tools.sdd_cli.full_setup.run_native",
            return_value={"returncode": 0, "stdout": "v20.0.0", "stderr": ""},
        ):
            with patch("sys.platform", "linux"):
                result = stage1_prerequisites(Path("."))
    assert result["valid"] is True
    assert len(result["steps"]) == 4


def test_stage1_prerequisites_python_fails() -> None:
    """Python version too old sets valid=False."""
    from tools.sdd_cli.full_setup import stage1_prerequisites

    with patch.object(sys, "version_info", (3, 9)):
        with patch(
            "tools.sdd_cli.full_setup.run_native",
            return_value={"returncode": 0, "stdout": "v20.0.0", "stderr": ""},
        ):
            with patch("sys.platform", "linux"):
                result = stage1_prerequisites(Path("."))
    assert result["valid"] is False
    assert any("error" in f.get("severity", "") for f in result["findings"])


def test_stage1_prerequisites_findings_structure() -> None:
    """Findings use the standard add_bucket_item format."""
    from tools.sdd_cli.full_setup import stage1_prerequisites

    with patch.object(sys, "version_info", (3, 9)):
        with patch(
            "tools.sdd_cli.full_setup.run_native",
            return_value={"returncode": 0, "stdout": "v20.0.0", "stderr": ""},
        ):
            with patch("sys.platform", "linux"):
                result = stage1_prerequisites(Path("."))
    assert "findings" in result
    for f in result["findings"]:
        assert "path" in f
        assert "key" in f
        assert "message" in f
        assert "severity" in f


# ── Individual check functions ───────────────────────────────────────────


def test_check_python_ok() -> None:
    """_check_python returns valid for 3.14+."""
    from tools.sdd_cli.full_setup import _check_python

    with patch.object(sys, "version_info", (3, 14)):
        result = _check_python()
    assert result["valid"] is True
    assert result["current"] == "3.14"


def test_check_python_too_old() -> None:
    """_check_python returns invalid for < 3.14."""
    from tools.sdd_cli.full_setup import _check_python

    with patch.object(sys, "version_info", (3, 9)):
        result = _check_python()
    assert result["valid"] is False


def test_check_node_ok() -> None:
    """_check_node returns valid when node and npm respond."""
    from tools.sdd_cli.full_setup import _check_node

    with patch(
        "tools.sdd_cli.full_setup.run_native",
        return_value={"returncode": 0, "stdout": "v20.0.0", "stderr": ""},
    ):
        result = _check_node()
    assert result["valid"] is True
    assert "v20" in result.get("nodeVersion", "")


def test_check_node_missing() -> None:
    """_check_node returns invalid when node is missing."""
    from tools.sdd_cli.full_setup import _check_node

    with patch(
        "tools.sdd_cli.full_setup.run_native",
        return_value={"returncode": 127, "stdout": "", "stderr": "not found"},
    ):
        result = _check_node()
    assert result["valid"] is False


def test_enable_powershell_skips_non_windows() -> None:
    """_enable_powershell skips on non-Windows."""
    from tools.sdd_cli.full_setup import _enable_powershell

    with patch("sys.platform", "linux"):
        result = _enable_powershell()
    assert result["valid"] is True
    assert "skipped" in result.get("message", "")


def test_check_docker_ok() -> None:
    """_check_docker returns valid when docker responds."""
    from tools.sdd_cli.full_setup import _check_docker

    with patch(
        "tools.sdd_cli.full_setup.run_native",
        return_value={"returncode": 0, "stdout": "24.0.0", "stderr": ""},
    ):
        result = _check_docker()
    assert result["valid"] is True
    assert result["version"] == "24.0.0"


def test_check_docker_not_found() -> None:
    """_check_docker returns invalid when docker is unavailable."""
    from tools.sdd_cli.full_setup import _check_docker

    with patch(
        "tools.sdd_cli.full_setup.run_native",
        return_value={"returncode": 1, "stdout": "", "stderr": "command not found"},
    ):
        result = _check_docker()
    assert result["valid"] is False
    assert "not responding" in result.get("message", "").lower()


# ── Stage 4: Project Guidance ───────────────────────────────────────────


def test_stage4_project_guidance_no_profile(tmp_path: Path) -> None:
    """stage4 handles missing project profile gracefully."""
    from tools.sdd_cli.full_setup import stage4_project_guidance

    result = stage4_project_guidance(tmp_path, dry_run=False)

    assert result["valid"] is True
    steps = result["steps"]
    assert len(steps) == 2
    # First step: no profile, second: no stack configured
    assert "No project profile configured" in steps[0]["message"]
    assert "No stack configured" in steps[1]["message"]


def test_stage4_project_guidance_with_profile(tmp_path: Path) -> None:
    """stage4 detects stack and searches internet when profile is configured."""
    from tools.sdd_cli.full_setup import stage4_project_guidance

    profile_dir = tmp_path / ".codex"
    profile_dir.mkdir(exist_ok=True)
    profile = {
        "stack": {
            "frontend": {"value": "react", "applies": True},
            "backend": {"value": "fastapi", "applies": True},
            "database": {"value": "postgresql", "applies": True},
        }
    }
    (profile_dir / "project-profile.json").write_text(json.dumps(profile), encoding="utf-8")

    dummy_guidance = {
        "valid": True,
        "foundSkills": ["owner/repo@react-skills", "owner/repo@fastapi-skills"],
        "installResults": [{ "valid": True, "skillName": "react-skills" }],
        "actions": [],
        "findings": [],
    }
    with patch("tools.sdd_cli.guidance.setup_project_guidance",
               return_value=dummy_guidance):
        result = stage4_project_guidance(tmp_path, dry_run=False)

    assert result["valid"] is True
    steps = result["steps"]
    assert len(steps) == 2
    assert "Stack configured" in steps[0]["message"]
    assert "Found 2 skill(s)" in steps[1]["message"]


def test_stage4_project_guidance_no_stack(tmp_path: Path) -> None:
    """stage4 handles profile without fully configured stack."""
    from tools.sdd_cli.full_setup import stage4_project_guidance

    profile_dir = tmp_path / ".codex"
    profile_dir.mkdir(exist_ok=True)
    profile = {
        "stack": {
            "frontend": {"value": "react", "applies": False},
            "backend": {"value": "fastapi", "applies": False},
            "database": {"value": "postgresql", "applies": False},
        }
    }
    (profile_dir / "project-profile.json").write_text(json.dumps(profile), encoding="utf-8")

    result = stage4_project_guidance(tmp_path, dry_run=False)

    assert result["valid"] is True
    steps = result["steps"]
    assert len(steps) == 2
    assert "not fully configured" in steps[0]["message"]
    assert "No stack configured" in steps[1]["message"]


def test_stage4_project_guidance_exception(tmp_path: Path) -> None:
    """stage4 handles setup_project_guidance raising an exception."""
    from tools.sdd_cli.full_setup import stage4_project_guidance

    profile_dir = tmp_path / ".codex"
    profile_dir.mkdir(exist_ok=True)
    profile = {
        "stack": {
            "frontend": {"value": "react", "applies": True},
            "backend": {"value": "fastapi", "applies": True},
            "database": {"value": "postgresql", "applies": True},
        }
    }
    (profile_dir / "project-profile.json").write_text(json.dumps(profile), encoding="utf-8")

    with patch("tools.sdd_cli.guidance.setup_project_guidance",
               side_effect=RuntimeError("Network error")):
        result = stage4_project_guidance(tmp_path, dry_run=False)

    assert result["valid"] is True
    steps = result["steps"]
    assert len(steps) == 2
    assert "Stack configured" in steps[0]["message"]
    assert "Network error" in steps[1]["message"]


# ── CLI wiring ───────────────────────────────────────────────────────────


def test_full_setup_in_cli_help() -> None:
    """full-setup appears in top-level CLI help."""
    from tools.sdd_cli import cli as cli_module

    assert hasattr(cli_module, "_dispatch_full_setup")


def test_full_setup_subcommand_dispatches() -> None:
    """full-setup subcommand dispatches with --dry-run flag."""
    from tools.sdd_cli.cli import _parse_cli

    parsed = _parse_cli(["full-setup", "--dry-run", "true"])
    assert parsed.command == "full-setup"
    assert parsed.dry_run is True
    assert hasattr(parsed, "full_args")
