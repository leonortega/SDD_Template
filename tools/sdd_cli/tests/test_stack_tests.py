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

_PYTHON_PROBE_OK = {"returncode": 0, "stdout": "Python 3.12.0", "stderr": ""}


def _make_profile(root: Path, frameworks: list[str]) -> None:
    codex = root / ".codex"
    codex.mkdir(parents=True, exist_ok=True)
    (codex / "project-profile.local.json").write_text(
        json.dumps({"stack": {"testFrameworks": frameworks}}),
        encoding="utf-8",
    )


def _make_test_dirs(root: Path) -> None:
    """Create the canonical test dirs so pytest/vitest/jest run, not skip."""
    for directory in ("test/unit", "test/integration", "test/architecture"):
        (root / directory).mkdir(parents=True, exist_ok=True)


class TestRunStackTests:
    def test_skips_when_no_stack(self, tmp_path: Path) -> None:
        result = stack_tests.run_stack_tests(tmp_path, dry_run=False)
        assert result["valid"] is True
        assert result["skipped"] is True
        assert result["frameworks"] == []

    def test_dry_run_reports_commands_without_executing(self, tmp_path: Path) -> None:
        _make_profile(tmp_path, ["pytest", "xunit"])
        _make_test_dirs(tmp_path)
        with patch(
            "tools.sdd_cli.stack_tests.subprocess.call"
        ) as mock_call, patch(
            "tools.sdd_cli.stack_tests.run_native", return_value=_PYTHON_PROBE_OK
        ):
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
        _make_test_dirs(tmp_path)
        with patch(
            "tools.sdd_cli.stack_tests.subprocess.call", return_value=0
        ) as mock_call, patch(
            "tools.sdd_cli.stack_tests.run_native", return_value=_PYTHON_PROBE_OK
        ):
            result = stack_tests.run_stack_tests(tmp_path, dry_run=False)

        assert result["valid"] is True
        # install + test + coverage for pytest
        assert mock_call.call_count == 3
        calls = [c.args[0] for c in mock_call.call_args_list]
        # native_command resolves python3 → python3.cmd/.exe on Windows
        assert calls[0][0].startswith("python3") and "install" in calls[0]
        assert calls[1][0].startswith("python3") and "pytest" in calls[1]
        # coverage uses the same resolved interpreter as install/test
        assert calls[2][0].startswith("python3")
        # Resolved test paths are appended to the canonical dirs.
        assert calls[1][-3:] == ["test/unit", "test/integration", "test/architecture"]
        # Coverage command embeds the default threshold 80
        assert "--cov-fail-under=80" in calls[2]
        assert any(
            s["command"] == "stack-tests/pytest/coverage" and s["valid"]
            for s in result["steps"]
        )

    def test_pytest_missing_dirs_skips_not_runs_repo_wide(self, tmp_path: Path) -> None:
        """No canonical test dirs → non-blocking gap, nothing executed."""
        _make_profile(tmp_path, ["pytest"])
        with patch("tools.sdd_cli.stack_tests.subprocess.call") as mock_call, patch(
            "tools.sdd_cli.stack_tests.run_native", return_value=_PYTHON_PROBE_OK
        ):
            result = stack_tests.run_stack_tests(tmp_path, dry_run=False)

        assert result["valid"] is True
        mock_call.assert_not_called()  # never pytest repo-wide
        assert any(
            "no test/unit|integration|architecture" in s["message"]
            for s in result["steps"]
        )

    def test_vitest_runs_in_package_root(self, tmp_path: Path) -> None:
        """npm ci + vitest run from src/frontend; no canonical dirs → config discovery."""
        _make_profile(tmp_path, ["vitest"])
        src = tmp_path / "src" / "frontend"
        src.mkdir(parents=True, exist_ok=True)
        (src / "package-lock.json").write_text("{}", encoding="utf-8")
        (src / "package.json").write_text("{}", encoding="utf-8")
        (src / "src").mkdir(parents=True, exist_ok=True)  # colocated test (scaffold layout)
        (src / "src" / "App.test.tsx").write_text("", encoding="utf-8")

        with patch(
            "tools.sdd_cli.stack_tests.subprocess.call", return_value=0
        ) as mock_call:
            result = stack_tests.run_stack_tests(tmp_path, dry_run=False)

        assert result["valid"] is True
        assert mock_call.call_count == 3  # npm ci + vitest run + vitest coverage
        calls = mock_call.call_args_list
        # npm ci runs with cwd = src/frontend
        assert Path(calls[0].kwargs["cwd"]) == src
        assert calls[0].args[0][-1] == "ci"
        # vitest run: no hardcoded test/unit paths (config-driven discovery)
        vitest_cmd = calls[1].args[0]
        assert "vitest" in vitest_cmd
        assert "test/unit" not in vitest_cmd
        assert Path(calls[1].kwargs["cwd"]) == src
        # coverage command runs from the same package root
        assert "--coverage" in calls[2].args[0]
        assert Path(calls[2].kwargs["cwd"]) == src

    def test_vitest_canonical_dirs_resolved_inside_package_root(
        self, tmp_path: Path
    ) -> None:
        """Canonical dirs under src/frontend (not repo root) get appended,
        relative to the package root — commands still run with cwd = package root."""
        _make_profile(tmp_path, ["vitest"])
        src = tmp_path / "src" / "frontend"
        src.mkdir(parents=True, exist_ok=True)
        (src / "package-lock.json").write_text("{}", encoding="utf-8")
        (src / "package.json").write_text("{}", encoding="utf-8")
        (src / "test" / "unit").mkdir(parents=True, exist_ok=True)
        (src / "test" / "integration").mkdir(parents=True, exist_ok=True)

        with patch(
            "tools.sdd_cli.stack_tests.subprocess.call", return_value=0
        ) as mock_call:
            result = stack_tests.run_stack_tests(tmp_path, dry_run=False)

        assert result["valid"] is True
        calls = mock_call.call_args_list
        vitest_cmd = calls[1].args[0]
        # Paths are package-root-relative, not repo-root-relative
        assert "test/unit" in vitest_cmd and "test/integration" in vitest_cmd
        assert str(tmp_path / "test" / "unit") not in " ".join(vitest_cmd)
        assert Path(calls[1].kwargs["cwd"]) == src
        assert Path(calls[2].kwargs["cwd"]) == src

    def test_vitest_missing_lockfile_fails_loudly(self, tmp_path: Path) -> None:
        """Configured JS/TS stack without any package-lock.json → gate fails."""
        _make_profile(tmp_path, ["vitest"])
        with patch("tools.sdd_cli.stack_tests.subprocess.call") as mock_call:
            result = stack_tests.run_stack_tests(tmp_path, dry_run=False)

        assert result["valid"] is False
        mock_call.assert_not_called()
        assert any(
            "no package-lock.json found" in s["message"] for s in result["steps"]
        )

    def test_missing_executable_reports_127_not_crash(self, tmp_path: Path) -> None:
        """FileNotFoundError (e.g. python3 missing) → clean FAIL, no traceback."""
        _make_profile(tmp_path, ["pytest"])
        _make_test_dirs(tmp_path)
        with patch(
            "tools.sdd_cli.stack_tests.subprocess.call",
            side_effect=FileNotFoundError,
        ), patch(
            "tools.sdd_cli.stack_tests.run_native", return_value=_PYTHON_PROBE_OK
        ):
            result = stack_tests.run_stack_tests(tmp_path, dry_run=False)

        assert result["valid"] is False
        assert any(
            "not found on PATH" in s["message"] for s in result["steps"]
        )

    def test_coverage_default_threshold_80(self, tmp_path: Path) -> None:
        """No quality config -> threshold defaults to 80 (dry-run reports it)."""
        _make_profile(tmp_path, ["pytest"])
        _make_test_dirs(tmp_path)
        with patch(
            "tools.sdd_cli.stack_tests.run_native", return_value=_PYTHON_PROBE_OK
        ):
            result = stack_tests.run_stack_tests(tmp_path, dry_run=True)
        assert result["coverageThreshold"] == 80
        assert "threshold 80%" in result["steps"][0]["message"]

    def test_coverage_threshold_from_quality_config(self, tmp_path: Path) -> None:
        """quality.local.json -> coverage.minimumPercent overrides the default."""
        _make_profile(tmp_path, ["pytest"])
        _make_test_dirs(tmp_path)
        codex = tmp_path / ".codex"
        (codex / "quality.local.json").write_text(
            json.dumps({"coverage": {"minimumPercent": 75}}),
            encoding="utf-8",
        )
        with patch(
            "tools.sdd_cli.stack_tests.run_native", return_value=_PYTHON_PROBE_OK
        ):
            result = stack_tests.run_stack_tests(tmp_path, dry_run=True)
        assert result["coverageThreshold"] == 75
        assert "threshold 75%" in result["steps"][0]["message"]

    def test_coverage_fails_below_threshold(self, tmp_path: Path) -> None:
        """Coverage command exit != 0 fails the gate (install ok, test ok, coverage fails)."""
        _make_profile(tmp_path, ["pytest"])
        _make_test_dirs(tmp_path)
        with patch(
            "tools.sdd_cli.stack_tests.subprocess.call",
            side_effect=[0, 0, 1],  # install ok, test ok, coverage fails
        ) as mock_call, patch(
            "tools.sdd_cli.stack_tests.run_native", return_value=_PYTHON_PROBE_OK
        ):
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
        _make_test_dirs(tmp_path)
        with patch(
            "tools.sdd_cli.stack_tests._COVERAGE_COMMANDS",
            {},
        ), patch(
            "tools.sdd_cli.stack_tests.subprocess.call", return_value=0
        ) as mock_call, patch(
            "tools.sdd_cli.stack_tests.run_native", return_value=_PYTHON_PROBE_OK
        ):
            result = stack_tests.run_stack_tests(tmp_path, dry_run=False)

        assert result["valid"] is True
        assert mock_call.call_count == 2  # install + test only, no coverage
        assert any(
            "No coverage command mapped" in s["message"]
            for s in result["steps"]
        )

    def test_fails_when_test_fails(self, tmp_path: Path) -> None:
        _make_profile(tmp_path, ["pytest"])
        _make_test_dirs(tmp_path)
        with patch(
            "tools.sdd_cli.stack_tests.subprocess.call",
            side_effect=[0, 1],  # install ok, test fails
        ) as mock_call, patch(
            "tools.sdd_cli.stack_tests.run_native", return_value=_PYTHON_PROBE_OK
        ):
            result = stack_tests.run_stack_tests(tmp_path, dry_run=False)

        assert result["valid"] is False
        assert mock_call.call_count == 2
        assert any(not s["valid"] for s in result["steps"])

    def test_fails_when_install_fails(self, tmp_path: Path) -> None:
        _make_profile(tmp_path, ["pytest"])
        _make_test_dirs(tmp_path)
        with patch(
            "tools.sdd_cli.stack_tests.subprocess.call",
            side_effect=[1, 0],  # install fails, test never runs
        ) as mock_call, patch(
            "tools.sdd_cli.stack_tests.run_native", return_value=_PYTHON_PROBE_OK
        ):
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
        _make_test_dirs(tmp_path)
        with patch(
            "tools.sdd_cli.stack_tests.subprocess.call", return_value=0
        ), patch(
            "tools.sdd_cli.stack_tests.run_native", return_value=_PYTHON_PROBE_OK
        ):
            rc = stack_tests.run_stack_tests_cli(["--root", str(tmp_path), "--dry-run", "true"])
        assert rc == 0

    def test_returns_one_when_failed(self, tmp_path: Path) -> None:
        _make_profile(tmp_path, ["pytest"])
        _make_test_dirs(tmp_path)
        with patch(
            "tools.sdd_cli.stack_tests.subprocess.call",
            side_effect=[0, 1],
        ), patch(
            "tools.sdd_cli.stack_tests.run_native", return_value=_PYTHON_PROBE_OK
        ):
            rc = stack_tests.run_stack_tests_cli(["--root", str(tmp_path)])
        assert rc == 1

    def test_returns_zero_when_no_stack(self, tmp_path: Path) -> None:
        rc = stack_tests.run_stack_tests_cli(["--root", str(tmp_path), "--dry-run", "true"])
        assert rc == 0
