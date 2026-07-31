"""Tests for the stack-tests local product-test runner."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from tools.sdd_cli import stack_tests


# ── _normalize_framework ────────────────────────────────────────────────


class TestNormalizeFramework:
    def test_dotnet_variants(self) -> None:
        assert stack_tests._normalize_framework("xunit") == "dotnet"
        assert stack_tests._normalize_framework("xunit.net") == "dotnet"
        assert stack_tests._normalize_framework("xunit.v3") == "dotnet"
        assert stack_tests._normalize_framework("nunit") == "dotnet"
        assert stack_tests._normalize_framework("nunit3") == "dotnet"
        assert stack_tests._normalize_framework("mstest") == "dotnet"
        assert stack_tests._normalize_framework("dotnet") == "dotnet"

    def test_non_dotnet(self) -> None:
        assert stack_tests._normalize_framework("pytest") == "pytest"
        assert stack_tests._normalize_framework("vitest") == "vitest"
        assert stack_tests._normalize_framework("Jest") == "jest"

    def test_unknown_framework_not_in_map(self) -> None:
        assert "golang" not in stack_tests._COMMANDS
        assert stack_tests._normalize_framework("golang") == "golang"


# ── run_stack_tests ─────────────────────────────────────────────────────


def _make_profile(root: Path, frameworks: list[str]) -> None:
    codex = root / ".codex"
    codex.mkdir(parents=True, exist_ok=True)
    (codex / "project-profile.local.json").write_text(
        json.dumps({"stack": {"testFrameworks": frameworks}}),
        encoding="utf-8",
    )


class TestRunStackTests:
    def test_skips_when_no_stack(self, tmp_path: Path) -> None:
        result = stack_tests.run_stack_tests(tmp_path, dry_run=False)
        assert result["valid"] is True
        assert result["skipped"] is True
        assert result["frameworks"] == []

    def test_dry_run_reports_commands_without_executing(self, tmp_path: Path) -> None:
        _make_profile(tmp_path, ["pytest", "xunit"])
        with patch("tools.sdd_cli.stack_tests.subprocess.call") as mock_call:
            result = stack_tests.run_stack_tests(tmp_path, dry_run=True)

        assert result["valid"] is True
        assert result["frameworks"] == ["pytest", "xunit"]
        # Nothing executed in dry-run
        mock_call.assert_not_called()
        # Both frameworks produce a dry-run step
        assert len(result["steps"]) == 2
        messages = " ".join(s["message"] for s in result["steps"])
        assert "pytest" in messages
        assert "dotnet test" in messages

    def test_runs_install_test_and_coverage_per_framework(self, tmp_path: Path) -> None:
        _make_profile(tmp_path, ["pytest"])
        with patch("tools.sdd_cli.stack_tests.subprocess.call", return_value=0) as mock_call:
            result = stack_tests.run_stack_tests(tmp_path, dry_run=False)

        assert result["valid"] is True
        # install + test + coverage for pytest
        assert mock_call.call_count == 3
        calls = [c.args[0] for c in mock_call.call_args_list]
        assert calls[0][0] == "python3" and "install" in calls[0]
        assert calls[1][0] == "python3" and "pytest" in calls[1]
        # Coverage command embeds the default threshold 80
        assert "--cov-fail-under=80" in calls[2]
        assert any(
            s["command"] == "stack-tests/pytest/coverage" and s["valid"]
            for s in result["steps"]
        )

    def test_coverage_default_threshold_80(self, tmp_path: Path) -> None:
        """No quality config -> threshold defaults to 80 (dry-run reports it)."""
        _make_profile(tmp_path, ["pytest"])
        result = stack_tests.run_stack_tests(tmp_path, dry_run=True)
        assert result["coverageThreshold"] == 80
        assert "threshold 80%" in result["steps"][0]["message"]

    def test_coverage_threshold_from_quality_config(self, tmp_path: Path) -> None:
        """quality.local.json -> coverage.minimumPercent overrides the default."""
        _make_profile(tmp_path, ["pytest"])
        codex = tmp_path / ".codex"
        (codex / "quality.local.json").write_text(
            json.dumps({"coverage": {"minimumPercent": 75}}),
            encoding="utf-8",
        )
        result = stack_tests.run_stack_tests(tmp_path, dry_run=True)
        assert result["coverageThreshold"] == 75
        assert "threshold 75%" in result["steps"][0]["message"]

    def test_coverage_fails_below_threshold(self, tmp_path: Path) -> None:
        """Coverage command exit != 0 fails the gate (install ok, test ok, coverage fails)."""
        _make_profile(tmp_path, ["pytest"])
        with patch(
            "tools.sdd_cli.stack_tests.subprocess.call",
            side_effect=[0, 0, 1],  # install ok, test ok, coverage fails
        ) as mock_call:
            result = stack_tests.run_stack_tests(tmp_path, dry_run=False)

        assert result["valid"] is False
        assert mock_call.call_count == 3
        assert any(
            s["command"] == "stack-tests/pytest/coverage" and not s["valid"]
            for s in result["steps"]
        )

    def test_coverage_gap_when_no_command_mapped(self, tmp_path: Path) -> None:
        """Framework with tests but no coverage command -> gap step, gate stays valid."""
        _make_profile(tmp_path, ["pytest"])
        with patch(
            "tools.sdd_cli.stack_tests._COVERAGE_COMMANDS",
            {},
        ), patch("tools.sdd_cli.stack_tests.subprocess.call", return_value=0) as mock_call:
            result = stack_tests.run_stack_tests(tmp_path, dry_run=False)

        assert result["valid"] is True
        assert mock_call.call_count == 2  # install + test only, no coverage
        assert any(
            "No coverage command mapped" in s["message"]
            for s in result["steps"]
        )

    def test_fails_when_test_fails(self, tmp_path: Path) -> None:
        _make_profile(tmp_path, ["pytest"])
        with patch(
            "tools.sdd_cli.stack_tests.subprocess.call",
            side_effect=[0, 1],  # install ok, test fails
        ) as mock_call:
            result = stack_tests.run_stack_tests(tmp_path, dry_run=False)

        assert result["valid"] is False
        assert mock_call.call_count == 2
        assert any(not s["valid"] for s in result["steps"])

    def test_fails_when_install_fails(self, tmp_path: Path) -> None:
        _make_profile(tmp_path, ["pytest"])
        with patch(
            "tools.sdd_cli.stack_tests.subprocess.call",
            side_effect=[1, 0],  # install fails, test never runs
        ) as mock_call:
            result = stack_tests.run_stack_tests(tmp_path, dry_run=False)

        assert result["valid"] is False
        assert mock_call.call_count == 1  # test skipped after install failure

    def test_fails_when_no_framework_mapped(self, tmp_path: Path) -> None:
        """Configured but unmapped frameworks must fail loudly, not pass silently."""
        _make_profile(tmp_path, ["golang"])
        with patch("tools.sdd_cli.stack_tests.subprocess.call") as mock_call:
            result = stack_tests.run_stack_tests(tmp_path, dry_run=False)

        assert result["valid"] is False
        # Nothing was executed because nothing could be mapped
        mock_call.assert_not_called()
        assert any(
            "No command mapped for framework" in s["message"]
            for s in result["steps"]
        )


# ── run_stack_tests_cli ─────────────────────────────────────────────────


class TestRunStackTestsCli:
    def test_returns_zero_when_valid(self, tmp_path: Path) -> None:
        _make_profile(tmp_path, ["pytest"])
        with patch("tools.sdd_cli.stack_tests.subprocess.call", return_value=0):
            rc = stack_tests.run_stack_tests_cli(["--root", str(tmp_path), "--dry-run", "true"])
        assert rc == 0

    def test_returns_one_when_failed(self, tmp_path: Path) -> None:
        _make_profile(tmp_path, ["pytest"])
        with patch(
            "tools.sdd_cli.stack_tests.subprocess.call",
            side_effect=[0, 1],
        ):
            rc = stack_tests.run_stack_tests_cli(["--root", str(tmp_path)])
        assert rc == 1

    def test_returns_zero_when_no_stack(self, tmp_path: Path) -> None:
        rc = stack_tests.run_stack_tests_cli(["--root", str(tmp_path), "--dry-run", "true"])
        assert rc == 0
