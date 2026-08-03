"""Tests for the shared HTTP Gitea MCP registration and idempotent sync."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch


def _write_client_tools(root: Path, token: str = "") -> None:
    """Write a client-tools.local.json with an optional gitea apiToken."""
    path = root / ".codex" / "client-tools.local.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {"gitea": {"baseUrl": "http://localhost:3000"}}
    if token:
        data["gitea"]["apiToken"] = token
    path.write_text(json.dumps(data), encoding="utf-8")


def test_install_gitea_mcp_builds_shared_http_entry(tmp_path: Path) -> None:
    """install_gitea_mcp registers ONE shared HTTP endpoint, not a stdio docker run."""
    from tools.sdd_cli.tool_installer import install_gitea_mcp

    _write_client_tools(tmp_path, token="tok-123")
    captured: dict = {}

    def fake_install(root, mode, server_name, expected_entry, dry_run, warnings=None):
        captured["entry"] = expected_entry
        captured["warnings"] = warnings or []
        return {"valid": True, "actions": [], "findings": []}

    with patch(
        "tools.sdd_cli.tool_installer._install_mcp", side_effect=fake_install
    ), patch("tools.sdd_cli.tool_installer._sync_gitea_mcp_container"):
        result = install_gitea_mcp(tmp_path, dry_run=True)

    assert result["valid"] is True
    entry = captured["entry"]
    assert entry["type"] == "http"
    assert entry["url"] == "http://localhost:8123/mcp"
    assert entry["headers"] == {"Authorization": "Bearer tok-123"}
    # No per-client `docker run` stdio command anymore.
    assert "command" not in entry
    assert captured["warnings"] == []


def test_install_gitea_mcp_missing_token_warns(tmp_path: Path) -> None:
    """No token -> no Bearer header and a warning action is recorded."""
    from tools.sdd_cli.tool_installer import install_gitea_mcp

    _write_client_tools(tmp_path, token="")
    captured: dict = {}

    def fake_install(root, mode, server_name, expected_entry, dry_run, warnings=None):
        captured["entry"] = expected_entry
        captured["warnings"] = warnings or []
        return {"valid": True, "actions": [], "findings": []}

    with patch(
        "tools.sdd_cli.tool_installer._install_mcp", side_effect=fake_install
    ), patch("tools.sdd_cli.tool_installer._sync_gitea_mcp_container"):
        install_gitea_mcp(tmp_path, dry_run=True)

    assert "headers" not in captured["entry"]
    assert captured["entry"]["url"] == "http://localhost:8123/mcp"
    assert any("Gitea API token not configured" in w["message"] for w in captured["warnings"])


def test_sync_writes_env_and_recreates_container(tmp_path: Path) -> None:
    """Token change -> both env files written and compose service recreated."""
    from tools.sdd_cli.tool_installer import _sync_gitea_mcp_container

    result = {"actions": [], "findings": []}
    with patch(
        "tools.sdd_cli.tool_installer._container_running", return_value=False
    ) as running, patch(
        "tools.sdd_cli.tool_installer._compose_up_gitea_mcp",
        return_value={"returncode": 0, "stdout": "", "stderr": ""},
    ) as compose_up:
        _sync_gitea_mcp_container(tmp_path, "tok-123", result, dry_run=False)

    assert (tmp_path / "infra" / "gitea" / "mcp.env").read_text(encoding="utf-8") == (
        "GITEA_ACCESS_TOKEN=tok-123\n"
    )
    assert (tmp_path / "infra" / "mcp.env").read_text(encoding="utf-8") == (
        "GITEA_ACCESS_TOKEN=tok-123\n"
    )
    compose_up.assert_called_once()
    assert not any(f.get("severity") == "error" for f in result["findings"])


def test_sync_unchanged_and_running_is_noop(tmp_path: Path) -> None:
    """No token change and container running -> no docker call (idempotent)."""
    from tools.sdd_cli.tool_installer import _sync_gitea_mcp_container

    env_dir = tmp_path / "infra" / "gitea"
    env_dir.mkdir(parents=True)
    (env_dir / "mcp.env").write_text("GITEA_ACCESS_TOKEN=tok-123\n", encoding="utf-8")
    result = {"actions": [], "findings": []}
    with patch(
        "tools.sdd_cli.tool_installer._container_running", return_value=True
    ), patch(
        "tools.sdd_cli.tool_installer._compose_up_gitea_mcp",
        return_value={"returncode": 0, "stdout": "", "stderr": ""},
    ) as compose_up:
        _sync_gitea_mcp_container(tmp_path, "tok-123", result, dry_run=False)

    compose_up.assert_not_called()
    assert result["actions"], "expected an 'already running' audit action"


def test_register_http_entry_not_rewritten_as_stdio(tmp_path: Path) -> None:
    """Http entries keep type=http and are stored flat in Cline settings."""
    from tools.sdd_cli.tool_installer import _register_mcp_entry

    result = {"actions": [], "findings": []}
    entry = {
        "type": "http",
        "url": "http://localhost:8123/mcp",
        "headers": {"Authorization": "Bearer tok-123"},
    }
    with patch("pathlib.Path.home", return_value=tmp_path / "home"), patch(
        "os.environ", {"APPDATA": str(tmp_path / "appdata")}
    ):
        _register_mcp_entry(
            tmp_path,
            tmp_path / ".vscode" / "mcp.json",
            "gitea",
            entry,
            result,
            dry_run=False,
        )

    cfg = json.loads((tmp_path / ".vscode" / "mcp.json").read_text(encoding="utf-8"))
    assert cfg["servers"]["gitea"] == entry  # untouched (no stdio injection)

    cline_path = tmp_path / "home" / ".cline" / "data" / "settings" / "cline_mcp_settings.json"
    cline = json.loads(cline_path.read_text(encoding="utf-8"))
    assert cline["mcpServers"]["gitea"] == entry  # flat, not transport-wrapped
