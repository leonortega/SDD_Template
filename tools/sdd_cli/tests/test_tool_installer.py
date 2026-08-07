"""Tests for the shared HTTP Gitea MCP registration and idempotent sync."""

from __future__ import annotations

import json
import sys
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


def test_ensure_quality_tools_auto_installs_trunk(tmp_path: Path) -> None:
    """Trunk probe fails → launcher auto-installed into node_modules, no warning."""
    from tools.sdd_cli.tool_installer import ensure_quality_tools

    (tmp_path / "lefthook.yml").write_text(
        "pre-commit:\n  commands: {}\n", encoding="utf-8"
    )

    calls: dict[str, int] = {"trunk_checks": 0}

    def fake_run(command, root, timeout=30):
        joined = " ".join(command)
        if "trunk" in joined and "install" not in joined:
            calls["trunk_checks"] += 1
            if calls["trunk_checks"] == 1:
                return {"returncode": 127, "stdout": "", "stderr": "not found"}
            return {"returncode": 0, "stdout": "1.25.0", "stderr": ""}
        if "npm" in joined and "install" in joined:
            return {"returncode": 0, "stdout": "added 1 package", "stderr": ""}
        if "gitleaks" in joined or "trivy" in joined:
            return {"returncode": 0, "stdout": "ok", "stderr": ""}
        # Coverage probes / anything else: report success.
        return {"returncode": 0, "stdout": "", "stderr": ""}

    with patch(
        "tools.sdd_cli.tool_installer.run_native", side_effect=fake_run
    ), patch(
        "tools.sdd_cli.tool_installer.install_lefthook",
        return_value={"valid": True, "actions": [], "findings": []},
    ):
        result = ensure_quality_tools(tmp_path, dry_run=False)

    assert result["valid"] is True
    assert not any(
        f.get("path") == "trunk" and f.get("severity") == "warning"
        for f in result["findings"]
    )
    assert any("auto-installed" in a.get("message", "") for a in result["actions"])
    # The npm install must not create a package.json (stack-agnostic template).
    assert not (tmp_path / "package.json").exists()


def test_ensure_quality_tools_trunk_install_failure_warns(tmp_path: Path) -> None:
    """Trunk probe fails AND install fails → warning finding is preserved."""
    from tools.sdd_cli.tool_installer import ensure_quality_tools

    (tmp_path / "lefthook.yml").write_text(
        "pre-commit:\n  commands: {}\n", encoding="utf-8"
    )

    def fake_run(command, root, timeout=30):
        joined = " ".join(command)
        if "npm" in joined and "install" in joined:
            return {"returncode": 1, "stdout": "", "stderr": "E404 registry down"}
        return {"returncode": 127, "stdout": "", "stderr": "missing"}

    with patch(
        "tools.sdd_cli.tool_installer.run_native", side_effect=fake_run
    ), patch(
        "tools.sdd_cli.tool_installer.install_lefthook",
        return_value={"valid": True, "actions": [], "findings": []},
    ):
        result = ensure_quality_tools(tmp_path, dry_run=False)

    assert any(
        f.get("path") == "trunk" and f.get("severity") == "warning"
        for f in result["findings"]
    )


def _seed_extension_settings(tmp_path: Path) -> Path | None:
    """Pre-create the VS Code extension settings file (Windows only).

    The installer only syncs legacy Cline locations that already exist, so a
    test simulating the VS Code extension must seed the file first. Returns
    None off-Windows (the extension path is never touched there).
    """
    if not sys.platform.startswith("win"):
        return None
    ext_path = (
        tmp_path
        / "appdata"
        / "Code"
        / "User"
        / "globalStorage"
        / "saoudrizwan.claude-dev"
        / "settings"
        / "cline_mcp_settings.json"
    )
    ext_path.parent.mkdir(parents=True, exist_ok=True)
    ext_path.write_text('{"mcpServers": {}}', encoding="utf-8")
    return ext_path


def test_register_http_entry_kept_flat_with_cline_translation(tmp_path: Path) -> None:
    """Http entries stay flat; Cline files get streamableHttp, VS Code keeps http.

    Cline's schema rejects "type": "http" for remote servers ([Invalid MCP
    settings schema.], cline issue #7091) and documents "streamableHttp"
    instead, while VS Code's native .vscode/mcp.json schema uses "http".
    """
    from tools.sdd_cli.tool_installer import _register_mcp_entry

    result = {"actions": [], "findings": []}
    entry = {
        "type": "http",
        "url": "http://localhost:8123/mcp",
        "headers": {"Authorization": "Bearer tok-123"},
    }
    ext_path = _seed_extension_settings(tmp_path)
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
    assert cfg["servers"]["gitea"] == entry  # VS Code schema keeps type=http

    cline_path = tmp_path / "home" / ".cline" / "data" / "settings" / "cline_mcp_settings.json"
    cline = json.loads(cline_path.read_text(encoding="utf-8"))
    cline_entry = cline["mcpServers"]["gitea"]
    assert cline_entry == {**entry, "type": "streamableHttp"}  # flat, translated
    assert cline_entry["url"] == "http://localhost:8123/mcp"
    assert cline_entry["headers"] == {"Authorization": "Bearer tok-123"}

    # The VS Code extension settings file gets the same translated entry.
    if ext_path is not None:
        ext = json.loads(ext_path.read_text(encoding="utf-8"))
        assert ext["mcpServers"]["gitea"]["type"] == "streamableHttp"


def test_install_gitea_mcp_writes_streamable_http_to_cline(tmp_path: Path) -> None:
    """install_gitea_mcp writes streamableHttp to Cline files, http to VS Code."""
    from tools.sdd_cli.tool_installer import install_gitea_mcp

    _write_client_tools(tmp_path, token="tok-123")
    ext_path = _seed_extension_settings(tmp_path)
    with patch("pathlib.Path.home", return_value=tmp_path / "home"), patch(
        "os.environ", {"APPDATA": str(tmp_path / "appdata")}
    ), patch("tools.sdd_cli.tool_installer._sync_gitea_mcp_container"):
        result = install_gitea_mcp(tmp_path, dry_run=False)

    assert result["valid"] is True
    cfg = json.loads((tmp_path / ".vscode" / "mcp.json").read_text(encoding="utf-8"))
    assert cfg["servers"]["gitea"]["type"] == "http"
    assert cfg["servers"]["gitea"]["url"] == "http://localhost:8123/mcp"

    cline_path = tmp_path / "home" / ".cline" / "data" / "settings" / "cline_mcp_settings.json"
    cline = json.loads(cline_path.read_text(encoding="utf-8"))
    assert cline["mcpServers"]["gitea"]["type"] == "streamableHttp"
    assert cline["mcpServers"]["gitea"]["url"] == "http://localhost:8123/mcp"
    assert cline["mcpServers"]["gitea"]["headers"] == {
        "Authorization": "Bearer tok-123"
    }
    if ext_path is not None:
        ext = json.loads(ext_path.read_text(encoding="utf-8"))
        assert ext["mcpServers"]["gitea"]["type"] == "streamableHttp"


def test_prune_junk_mcp_servers_removes_junk_preserves_real(tmp_path: Path) -> None:
    """Junk entries are pruned from .vscode/mcp.json and Cline files; real ones kept."""
    from tools.sdd_cli.tool_installer import _prune_junk_mcp_servers

    vscode = tmp_path / ".vscode" / "mcp.json"
    vscode.parent.mkdir(parents=True)
    vscode.write_text(
        json.dumps(
            {
                "servers": {
                    "gitea": {"type": "http", "url": "http://localhost:8123/mcp"},
                    "new-server": {"command": "echo", "args": ["x"]},
                    "codebase-memory-mcp": {"command": "echo", "args": ["mem"]},
                }
            }
        ),
        encoding="utf-8",
    )
    cline_path = (
        tmp_path / "home" / ".cline" / "data" / "settings" / "cline_mcp_settings.json"
    )
    cline_path.parent.mkdir(parents=True)
    cline_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "test-server": {"command": "echo", "args": ["t"]},
                    "newserver": {"command": "echo", "args": ["n"]},
                    "monorepo-docs-search": {"command": "echo", "args": ["d"]},
                }
            }
        ),
        encoding="utf-8",
    )
    result = {"actions": [], "findings": []}
    with patch("pathlib.Path.home", return_value=tmp_path / "home"), patch(
        "os.environ", {"APPDATA": str(tmp_path / "appdata")}
    ):
        _prune_junk_mcp_servers(tmp_path, result, dry_run=False)

    vscode_cfg = json.loads(vscode.read_text(encoding="utf-8"))
    assert "new-server" not in vscode_cfg["servers"]
    assert "gitea" in vscode_cfg["servers"]
    assert "codebase-memory-mcp" in vscode_cfg["servers"]

    cline_cfg = json.loads(cline_path.read_text(encoding="utf-8"))
    assert "test-server" not in cline_cfg["mcpServers"]
    assert "newserver" not in cline_cfg["mcpServers"]
    assert "monorepo-docs-search" in cline_cfg["mcpServers"]

    pruned = [a for a in result["actions"] if a["key"].startswith("prune.")]
    assert {a["key"] for a in pruned} == {
        "prune.new-server",
        "prune.test-server",
        "prune.newserver",
    }


def test_prune_junk_mcp_servers_dry_run_does_not_write(tmp_path: Path) -> None:
    """Dry-run reports would-remove actions without touching files."""
    from tools.sdd_cli.tool_installer import _prune_junk_mcp_servers

    vscode = tmp_path / ".vscode" / "mcp.json"
    vscode.parent.mkdir(parents=True)
    original = {"servers": {"new-server": {"command": "echo", "args": ["x"]}}}
    vscode.write_text(json.dumps(original), encoding="utf-8")

    result = {"actions": [], "findings": []}
    with patch("pathlib.Path.home", return_value=tmp_path / "home"), patch(
        "os.environ", {"APPDATA": str(tmp_path / "appdata")}
    ):
        _prune_junk_mcp_servers(tmp_path, result, dry_run=True)

    assert json.loads(vscode.read_text(encoding="utf-8")) == original
    assert any(
        a["key"] == "prune.new-server" and "Would remove" in a["message"]
        for a in result["actions"]
    )


def test_ensure_mcp_servers_prune_junk_flag(tmp_path: Path) -> None:
    """prune_junk defaults to True (pruner runs); False skips it."""
    from tools.sdd_cli.tool_installer import ensure_mcp_servers

    dummy = {"valid": True, "actions": [], "findings": []}
    pruned: list[bool] = []

    def fake_prune(root, result, dry_run):
        pruned.append(dry_run)

    with patch(
        "tools.sdd_cli.tool_installer.install_playwright_mcp", return_value=dummy
    ), patch(
        "tools.sdd_cli.tool_installer.install_grafana_mcp", return_value=dummy
    ), patch(
        "tools.sdd_cli.tool_installer.install_k8s_mcp", return_value=dummy
    ), patch(
        "tools.sdd_cli.tool_installer.install_gitea_mcp", return_value=dummy
    ), patch(
        "tools.sdd_cli.tool_installer.install_openproject_mcp", return_value=dummy
    ), patch(
        "tools.sdd_cli.tool_installer._prune_junk_mcp_servers", side_effect=fake_prune
    ):
        ensure_mcp_servers(tmp_path, dry_run=False)
        ensure_mcp_servers(tmp_path, dry_run=False, prune_junk=False)

    assert pruned == [False]  # ran for the default call only
