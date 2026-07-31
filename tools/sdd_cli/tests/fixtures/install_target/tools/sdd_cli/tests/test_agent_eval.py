"""Tests for the agent-eval runner: loud failures and result counting."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from tools.sdd_cli import cli
from tools.sdd_cli._shared import CliError
from tools.sdd_cli.agent_eval import run_eval


class _FakeResult:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _fake_run(results: str | None, *, returncode: int = 0, stderr: str = ""):
    """Build a subprocess.run replacement for the two npx invocations."""

    def fake(cmd: list[str], **kwargs):
        if "--version" in cmd:
            return _FakeResult()
        out_idx = cmd.index("--output")
        out_path = Path(cmd[out_idx + 1])
        if results is not None:
            out_path.write_text(results, encoding="utf-8")
        return _FakeResult(returncode=returncode, stderr=stderr)

    return fake


def _make_root(tmp_path: Path) -> Path:
    """Create a minimal eval config so run_eval gets past the config check."""
    config = tmp_path / ".codex" / "agent-evals" / "promptfooconfig.yaml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("prompts: []\n", encoding="utf-8")
    return tmp_path


def test_run_eval_raises_when_no_results_file(tmp_path: Path) -> None:
    """promptfoo exit != 0 and no results file -> loud CliError, not '0 passed'."""
    root = _make_root(tmp_path)
    fake = _fake_run(None, returncode=1, stderr="EBUSY/EPERM on onnxruntime-node")
    with patch("tools.sdd_cli.agent_eval.subprocess.run", side_effect=fake):
        with pytest.raises(CliError) as exc:
            run_eval(root)
    assert "no results file" in str(exc.value)
    assert "EBUSY" in str(exc.value)


def test_run_eval_raises_when_results_file_unparseable(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    fake = _fake_run("{not json")
    with patch("tools.sdd_cli.agent_eval.subprocess.run", side_effect=fake):
        with pytest.raises(CliError) as exc:
            run_eval(root)
    assert "could not be parsed" in str(exc.value)


def test_run_eval_raises_when_zero_tests(tmp_path: Path) -> None:
    """An empty results array is a loud failure, not '0 tests passed'."""
    root = _make_root(tmp_path)
    fake = _fake_run("[]")
    with patch("tools.sdd_cli.agent_eval.subprocess.run", side_effect=fake):
        with pytest.raises(CliError) as exc:
            run_eval(root)
    assert "0 test results" in str(exc.value)


def test_run_eval_counts_pass_fail_and_cleans_tmp(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    payload = '[{"pass": true}, {"pass": false}, {"pass": true}]'
    fake = _fake_run(payload)
    with patch("tools.sdd_cli.agent_eval.subprocess.run", side_effect=fake):
        result = run_eval(root)
    assert result["total"] == 3
    assert result["passed"] == 2
    assert result["failed"] == 1
    assert result["valid"] is False
    assert not (root / ".codex" / "agent-evals" / "results.tmp.json").exists()


def test_run_eval_handles_dict_results_key(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    fake = _fake_run('{"results": [{"pass": true}]}')
    with patch("tools.sdd_cli.agent_eval.subprocess.run", side_effect=fake):
        result = run_eval(root)
    assert result["total"] == 1
    assert result["passed"] == 1
    assert result["valid"] is True


def test_run_eval_invalid_when_promptfoo_exits_nonzero_even_if_all_pass(
    tmp_path: Path,
) -> None:
    """A non-zero promptfoo exit (crash-after-write) must not report success."""
    root = _make_root(tmp_path)
    fake = _fake_run('[{"pass": true}]', returncode=1)
    with patch("tools.sdd_cli.agent_eval.subprocess.run", side_effect=fake):
        result = run_eval(root)
    assert result["total"] == 1
    assert result["passed"] == 1
    assert result["valid"] is False
    assert result["returncode"] == 1


def test_run_eval_stale_results_file_removed_before_run(tmp_path: Path) -> None:
    """A stale tmp file from a previous run must not mask a failed run."""
    root = _make_root(tmp_path)
    stale = root / ".codex" / "agent-evals" / "results.tmp.json"
    stale.write_text('[{"pass": true}]', encoding="utf-8")
    fake = _fake_run(None, returncode=1)
    with patch("tools.sdd_cli.agent_eval.subprocess.run", side_effect=fake):
        with pytest.raises(CliError):
            run_eval(root)
    assert not stale.exists()


def test_cli_agent_eval_run_fails_loudly(capsys: pytest.CaptureFixture) -> None:
    """cli.main exits 1 with the CliError message on stderr when promptfoo
    produces no results file (regression for the '0 tests passed' bug)."""
    fake = _fake_run(None, returncode=1, stderr="EBUSY")
    with patch("tools.sdd_cli.agent_eval.subprocess.run", side_effect=fake):
        rc = cli.main(["agent-eval", "run"])
    captured = capsys.readouterr()
    assert rc == 1
    assert "no results file" in captured.err
    assert "0 tests passed" not in captured.out
