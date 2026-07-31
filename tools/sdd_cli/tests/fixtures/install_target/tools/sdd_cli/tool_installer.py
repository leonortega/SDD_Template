"""Tool installer: lefthook, MCP servers, quality tools."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ._shared import (
    REPO_ROOT,
    CliError,
    add_bucket_item,
    configure_result,
    get_sdd_tool_preserve_files,
    git_text,
    parse_pairs,
    read_env_file,
    read_json,
    remove_empty_parents,
    run_native,
    write_json,
)

# ── Lefthook ──────────────────────────────────────────────────────────────


def install_lefthook(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Install lefthook binary and git hooks."""
    result = configure_result("InstallLefthook", dry_run, write_enabled=not dry_run)
    lefthook_yml = root / "lefthook.yml"
    if not lefthook_yml.exists():
        add_bucket_item(
            result["findings"],
            "lefthook.yml",
            "config.missing",
            "lefthook.yml is missing.",
            "warning",
            "pre-start",
        )
        result["valid"] = False
        return result
    lefthook_path = _resolve_lefthook()
    if lefthook_path is None:
        result["actions"].append(
            {
                "path": "lefthook",
                "key": "install",
                "severity": "info",
                "message": "lefthook binary not found. Attempting auto-install.",
                "phase": "apply",
            }
        )
        if dry_run:
            result["actions"].append(
                {
                    "path": "lefthook",
                    "key": "install",
                    "severity": "info",
                    "message": "Would download and install lefthook to user-local bin.",
                    "phase": "apply",
                }
            )
            result["valid"] = True
            return result
        lefthook_path = _install_lefthook_user_local(root, result)
        if lefthook_path is None:
            result["valid"] = False
            return result
    if dry_run:
        result["actions"].append(
            {
                "path": "lefthook",
                "key": "install",
                "severity": "info",
                "message": f"Would run {lefthook_path} install.",
                "phase": "apply",
            }
        )
        result["valid"] = True
        return result
    # Skip lefthook install if there's no .git directory (fresh template install, no repo yet)
    if not (root / ".git").exists():
        result["actions"].append(
            {
                "path": "lefthook",
                "key": "install",
                "severity": "info",
                "message": "No .git directory found — skipping lefthook install (init git repo first).",
                "phase": "audit",
            }
        )
        result["valid"] = True
        return result

    install = run_native([lefthook_path, "install"], root, timeout=30)
    if install["returncode"] == 0:
        result["actions"].append(
            {
                "path": "lefthook",
                "key": "install",
                "severity": "info",
                "message": "Lefthook git hooks installed.",
                "phase": "apply",
            }
        )
        # Verify hooks are active by checking the git hooks directory
        git_hooks = root / ".git" / "hooks" / "pre-commit"
        if git_hooks.exists():
            result["actions"].append(
                {
                    "path": ".git/hooks/pre-commit",
                    "key": "verify",
                    "severity": "info",
                    "message": "Lefthook pre-commit hook is active.",
                    "phase": "apply",
                }
            )
        else:
            # lefthook may use different hook file names; check for the lefthook wrapper
            lefthook_hook = root / ".git" / "hooks" / "lefthook"
            if lefthook_hook.exists():
                result["actions"].append(
                    {
                        "path": ".git/hooks/lefthook",
                        "key": "verify",
                        "severity": "info",
                        "message": "Lefthook wrapper hook is active.",
                        "phase": "apply",
                    }
                )
            else:
                add_bucket_item(
                    result["findings"],
                    ".git/hooks",
                    "verify",
                    "Could not verify lefthook git hooks — check .git/hooks/ for expected files.",
                    "warning",
                    "post-start",
                )
    else:
        add_bucket_item(
            result["findings"],
            "lefthook",
            "install",
            f"Could not install lefthook: {install['stderr']}",
            "error",
            "apply",
        )
        result["valid"] = False
        return result
    result["valid"] = True
    return result


def _resolve_lefthook() -> str | None:
    """Find lefthook binary in PATH or user-local bin."""
    user_bin = _lefthook_user_bin()
    exe = "lefthook.exe" if sys.platform.startswith("win") else "lefthook"
    if (user_bin / exe).exists():
        return str(user_bin / exe)
    for name in ("lefthook", "lefthook.exe"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _lefthook_user_bin() -> Path:
    if sys.platform.startswith("win"):
        return (
            Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
            / "bin"
        )
    return Path.home() / ".local" / "bin"


def _lefthook_platform() -> str | None:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform.startswith("darwin"):
        return "darwin"
    if sys.platform.startswith("linux"):
        return "linux"
    return None


def _lefthook_arch_github() -> str | None:
    machine = platform.machine().lower()
    if sys.platform == "win32":
        env_machine = os.environ.get("PROCESSOR_ARCHITECTURE", "").lower()
        if "arm64" in env_machine or "aarch64" in env_machine:
            return "arm64"
        if "x86" in env_machine or "amd64" in env_machine:
            return "x86_64"
        if "arm64" in machine or "aarch64" in machine:
            return "arm64"
        if "x86" in machine or "amd64" in machine:
            return "x86_64"
        return None
    if "aarch64" in machine or "arm64" in machine:
        return "arm64"
    if "x86_64" in machine or "amd64" in machine:
        return "x86_64"
    if "i386" in machine or "i686" in machine or "x86" in machine:
        return "i386"
    return None


def _install_lefthook_user_local(root: Path, result: dict[str, Any]) -> str | None:
    """Download lefthook binary from GitHub releases."""
    platform_name = _lefthook_platform()
    arch = _lefthook_arch_github()
    if not platform_name or not arch:
        add_bucket_item(
            result["findings"],
            "lefthook",
            "platform.unsupported",
            f"Unsupported platform/arch for lefthook auto-install: {sys.platform}",
            "error",
            "apply",
        )
        return None
    bin_dir = _lefthook_user_bin()
    bin_name = "lefthook.exe" if platform_name == "windows" else "lefthook"
    destination = bin_dir / bin_name
    if destination.exists():
        result["actions"].append(
            {
                "path": str(destination),
                "key": "install",
                "severity": "info",
                "message": "lefthook binary already exists.",
                "phase": "apply",
            }
        )
        return str(destination)
    try:
        import urllib.request

        api_url = "https://api.github.com/repos/evilmartians/lefthook/releases/latest"
        req = urllib.request.Request(
            api_url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "sdd-cli",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as response:  # nosec
            release = json.loads(response.read().decode("utf-8"))
        tag = release.get("tag_name", "")
        tag_without_v = tag[1:] if tag.startswith("v") else tag
        platform_capitalized = platform_name.capitalize()
        if platform_name == "windows":
            asset_name = f"lefthook_{tag_without_v}_{platform_capitalized}_{arch}.exe"
        else:
            asset_name = f"lefthook_{tag_without_v}_{platform_capitalized}_{arch}"
        download_url = f"https://github.com/evilmartians/lefthook/releases/download/{tag}/{asset_name}"
        result["actions"].append(
            {
                "path": "lefthook",
                "key": "download",
                "severity": "info",
                "message": f"Downloading lefthook from {download_url}.",
                "phase": "apply",
            }
        )
        with urllib.request.urlopen(download_url, timeout=60) as response:  # nosec
            data = response.read()
        if not data:
            add_bucket_item(
                result["findings"],
                "lefthook",
                "download",
                "Downloaded lefthook payload was empty.",
                "error",
                "apply",
            )
            return None
        bin_dir.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        if platform_name != "windows":
            destination.chmod(destination.stat().st_mode | 0o111)
        result["actions"].append(
            {
                "path": str(destination),
                "key": "install",
                "severity": "info",
                "message": f"Installed lefthook to {destination}.",
                "phase": "apply",
            }
        )
        return str(destination)
    except Exception as ex:
        add_bucket_item(
            result["findings"],
            "lefthook",
            "install",
            f"Could not install lefthook: {ex}",
            "error",
            "apply",
        )
        return None


# ── SDD Tool install/update ──────────────────────────────────────────────


def install_or_update_sdd_tool(
    source: Path,
    target: Path,
    version: str | None,
    action: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Install or update the SDD template tooling into a consumer repository."""
    from ._shared import (
        get_sdd_tool_include_dirs,
        get_sdd_tool_include_empty_dirs,
        get_sdd_tool_manifest,
        get_sdd_tool_preserve_example_files,
        get_sdd_tool_preserve_files,
        get_sdd_tool_tool_files,
        is_preserved_local_json,
        sdd_tool_checksum,
        sdd_tool_files,
    )

    SDD_TOOL_MANIFEST = get_sdd_tool_manifest()
    SDD_TOOL_INCLUDE_DIRS = get_sdd_tool_include_dirs()
    SDD_TOOL_INCLUDE_EMPTY_DIRS = get_sdd_tool_include_empty_dirs()
    SDD_TOOL_TOOL_FILES = get_sdd_tool_tool_files()
    SDD_TOOL_PRESERVE_FILES = get_sdd_tool_preserve_files()
    SDD_TOOL_PRESERVE_EXAMPLE_FILES = get_sdd_tool_preserve_example_files()
    source = source.resolve()
    target = target.resolve()
    if source == target:
        raise CliError("Target must be a consumer repository, not the tool repository.")
    if action not in ("install", "update"):
        raise CliError(f"Unsupported tool action: {action}")
    if not source.exists():
        raise CliError(f"Tool source does not exist: {source}")
    target.mkdir(parents=True, exist_ok=True)
    files = sdd_tool_files(source)
    old_manifest = read_json(target / SDD_TOOL_MANIFEST, optional=True)
    old_managed = set(old_manifest.get("managedFiles", []))
    owned = old_managed | ({SDD_TOOL_MANIFEST} if old_manifest else set())
    if action == "update" and not old_manifest:
        raise CliError(f"Cannot update before install. Missing {SDD_TOOL_MANIFEST}.")
    if action == "install" and old_manifest:
        action = "update"
    collisions = _unmanaged_collisions(
        source, target, files, owned, preserve_examples=SDD_TOOL_PRESERVE_EXAMPLE_FILES
    )
    if collisions:
        raise CliError(
            "Refusing to overwrite unmanaged files: " + ", ".join(collisions[:10])
        )
    changed: list[str] = []
    for dirname in SDD_TOOL_INCLUDE_DIRS:
        dirpath = target / dirname.replace("/", os.sep)
        if not dirpath.exists():
            dirpath.mkdir(parents=True, exist_ok=True)
            changed.append(dirname + "/")
    for dirname in SDD_TOOL_INCLUDE_EMPTY_DIRS:
        dirpath = target / dirname.replace("/", os.sep)
        if not dirpath.exists():
            dirpath.mkdir(parents=True, exist_ok=True)
            changed.append(dirname + "/")
    for relative in SDD_TOOL_TOOL_FILES:
        src = source / relative
        dst = target / relative
        if src.exists() and (not dst.exists() or dst.read_bytes() != src.read_bytes()):
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            changed.append(relative)
    for relative in files:
        src = source / relative
        dst = target / relative
        preserve = (
            relative in SDD_TOOL_PRESERVE_FILES
            or relative in SDD_TOOL_PRESERVE_EXAMPLE_FILES
            or is_preserved_local_json(relative)
        )
        if preserve and dst.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        before = dst.read_bytes() if dst.exists() else None
        shutil.copy2(src, dst)
        if before != dst.read_bytes():
            changed.append(relative)
    if action == "update":
        new_files = set(files) - old_managed
        for relative in new_files:
            preserve = (
                relative in SDD_TOOL_PRESERVE_FILES
                or relative in SDD_TOOL_PRESERVE_EXAMPLE_FILES
                or is_preserved_local_json(relative)
            )
            if preserve:
                continue
            src = source / relative
            dst = target / relative
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            changed.append(relative)
    new_managed = set(files)
    removed: list[str] = []
    for relative in sorted(old_managed - new_managed):
        dst = target / relative
        if (
            dst.exists()
            and relative not in SDD_TOOL_PRESERVE_FILES
            and relative not in SDD_TOOL_PRESERVE_EXAMPLE_FILES
            and not is_preserved_local_json(relative)
        ):
            dst.unlink()
            removed.append(relative)
            remove_empty_parents(dst.parent, target)
    checksum = sdd_tool_checksum(target, files)
    # Initialize local git repo so lefthook can install hooks.
    # Does NOT copy the source repo's .git — creates a fresh one.
    git_bootstrap = _ensure_local_git_repo(target)
    manifest = {
        "schemaVersion": 1,
        "tool": "sdd-tool",
        "version": version or _latest_sdd_tool_version(source),
        "sourceRepo": git_text(source, ["config", "--get", "remote.gitea.url"])
        or str(source),
        "sourceCommit": git_text(source, ["rev-parse", "HEAD"]),
        "installedAtUtc": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "checksumSha256": checksum,
        "managedFiles": files,
        "preservedFiles": sorted(
            SDD_TOOL_PRESERVE_FILES | SDD_TOOL_PRESERVE_EXAMPLE_FILES
        ),
        "gitBootstrap": git_bootstrap,
    }
    if not dry_run:
        write_json(target / SDD_TOOL_MANIFEST, manifest)
    return {
        "action": action,
        "version": manifest["version"],
        "target": str(target),
        "managedFileCount": len(files),
        "changedFileCount": len(changed),
        "removedFileCount": len(removed),
        "manifest": SDD_TOOL_MANIFEST,
        "checksumSha256": checksum,
        "gitBootstrap": git_bootstrap,
    }


# ── MCP registration helper ──────────────────────────────────────────────


def _register_mcp_entry(
    root: Path,
    mcp_path: Path,
    server_name: str,
    expected_entry: dict[str, Any],
    result: dict[str, Any],
    dry_run: bool = False,
) -> dict[str, Any]:
    """Register a single MCP entry under the mcpServers key.

    Writes to both .vscode/mcp.json and Cline's global MCP settings
    (at %APPDATA%/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json
    on Windows, or ~/.config/... on Linux/macOS).

    Shared helper used by all install_*_mcp functions.
    """
    # ── Helper: build mcp entry dict ──────────────────────────────────
    def _build_entry() -> dict[str, Any]:
        entry: dict[str, Any] = {
            "command": expected_entry["command"],
            "args": expected_entry["args"],
        }
        if "env" in expected_entry:
            entry["env"] = expected_entry["env"]
        if "type" in expected_entry:
            entry["type"] = expected_entry["type"]
        return entry

    # ── Write to .vscode/mcp.json ─────────────────────────────────────
    def _write_vscode() -> bool:
        nonlocal mcp_path
        if not mcp_path.exists():
            cfg: dict[str, Any] = {"mcpServers": {}}
        else:
            try:
                cfg = read_json(mcp_path, optional=False)
            except Exception:
                add_bucket_item(
                    result["findings"],
                    ".vscode/mcp.json",
                    "parse.error",
                    "Could not parse existing .vscode/mcp.json.",
                    "error",
                    "pre-start",
                )
                return False
        servers = cfg.get("mcpServers", {})
        if not isinstance(servers, dict):
            add_bucket_item(
                result["findings"],
                ".vscode/mcp.json",
                "invalid.mcpServers",
                "mcpServers key must be a JSON object.",
                "error",
                "pre-start",
            )
            return False
        existing = servers.get(server_name)
        entry = _build_entry()
        servers[server_name] = entry
        cfg["mcpServers"] = servers
        mcp_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(mcp_path, cfg)
        if existing and existing != entry:
            changed_keys = [k for k in entry if existing.get(k) != entry[k]]
            result["actions"].append({
                "path": ".vscode/mcp.json",
                "key": server_name,
                "severity": "info",
                "message": f"Updated {server_name} in .vscode/mcp.json (changed: {', '.join(changed_keys)}).",
                "phase": "apply",
            })
        else:
            result["actions"].append({
                "path": ".vscode/mcp.json",
                "key": server_name,
                "severity": "info",
                "message": f"Added {server_name} to .vscode/mcp.json.",
                "phase": "apply",
            })
        return True

    # ── Write to Cline global settings ────────────────────────────────
    def _write_cline() -> bool:
        """Write the MCP entry to Cline's global mcp_settings.json."""
        if sys.platform.startswith("win"):
            appdata = os.environ.get("APPDATA")
            if not appdata:
                add_bucket_item(
                    result["findings"],
                    "cline_mcp_settings.json",
                    "env.appdata",
                    "APPDATA env var not found — cannot write Cline MCP settings.",
                    "warning",
                )
                return True  # Non-fatal: .vscode/mcp.json is the primary target
            cline_path = (
                Path(appdata)
                / "Code"
                / "User"
                / "globalStorage"
                / "saoudrizwan.claude-dev"
                / "settings"
                / "cline_mcp_settings.json"
            )
        elif sys.platform == "darwin":
            cline_path = (
                Path.home()
                / "Library"
                / "Application Support"
                / "Code"
                / "User"
                / "globalStorage"
                / "saoudrizwan.claude-dev"
                / "settings"
                / "cline_mcp_settings.json"
            )
        else:
            cline_path = (
                Path.home()
                / ".config"
                / "Code"
                / "User"
                / "globalStorage"
                / "saoudrizwan.claude-dev"
                / "settings"
                / "cline_mcp_settings.json"
            )

        cline_path.parent.mkdir(parents=True, exist_ok=True)
        if not cline_path.exists():
            cline_data: dict[str, Any] = {"mcpServers": {}}
        else:
            try:
                cline_data = read_json(cline_path, optional=True)
            except Exception:
                cline_data = {"mcpServers": {}}
        cline_servers = cline_data.setdefault("mcpServers", {})
        entry = _build_entry()
        cline_servers[server_name] = entry
        cline_data["mcpServers"] = cline_servers
        write_json(cline_path, cline_data)
        result["actions"].append({
            "path": str(cline_path),
            "key": server_name,
            "severity": "info",
            "message": f"Synced {server_name} to Cline global MCP settings.",
            "phase": "apply",
        })
        return True

    if dry_run:
        result["actions"].append({
            "path": ".vscode/mcp.json",
            "key": server_name,
            "severity": "info",
            "message": f"Would register {server_name} in .vscode/mcp.json and Cline settings.",
            "phase": "apply",
        })
        result["valid"] = True
        return result

    vscode_ok = _write_vscode()
    cline_ok = _write_cline()

    result["valid"] = vscode_ok
    return result


# ── Playwright MCP ───────────────────────────────────────────────────────


def install_playwright_mcp(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Register the Playwright MCP server in .vscode/mcp.json.

    Requires Playwright browsers to be installed (npx playwright install chromium).
    """
    result = configure_result(
        "InstallPlaywrightMCP", dry_run, write_enabled=not dry_run
    )
    mcp_path = root / ".vscode" / "mcp.json"
    expected_entry = {
        "command": "npx",
        "args": ["-y", "@playwright/mcp@latest"],
    }
    if dry_run:
        result["actions"].append(
            {
                "path": ".vscode/mcp.json",
                "key": "playwright",
                "severity": "info",
                "message": "Would register playwright MCP server.",
                "phase": "apply",
            }
        )
        result["valid"] = True
        return result
    return _register_mcp_entry(root, mcp_path, "playwright", expected_entry, result, dry_run)


# ── Grafana MCP ──────────────────────────────────────────────────────────


def install_grafana_mcp(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Register the Grafana MCP server in .vscode/mcp.json.

    Reads GRAFANA_SERVICE_ACCOUNT_TOKEN from infra/monitoring/variables.env.
    Requires a running Grafana instance at localhost:3000 or configured URL.
    """
    result = configure_result(
        "InstallGrafanaMCP", dry_run, write_enabled=not dry_run
    )
    mcp_path = root / ".vscode" / "mcp.json"

    # Read grafana env vars
    monitoring_env = root / "infra" / "monitoring" / "variables.env"
    grafana_token = ""
    grafana_url = "http://localhost:3000"
    if monitoring_env.exists():
        env_vars = read_env_file(monitoring_env)
        grafana_token = env_vars.get("GRAFANA_SERVICE_ACCOUNT_TOKEN", "")
        grafana_url = env_vars.get("GRAFANA_URL", "http://localhost:3000")

    if not grafana_token or "replace-with" in grafana_token:
        result["actions"].append(
            {
                "path": "infra/monitoring/variables.env",
                "key": "grafana.token",
                "severity": "warning",
                "message": "GRAFANA_SERVICE_ACCOUNT_TOKEN not configured. Registering server config without token placeholder.",
                "phase": "audit",
            }
        )

    expected_entry: dict[str, Any] = {
        "command": "uvx",
        "args": ["mcp-grafana"],
    }
    env_dict: dict[str, str] = {
        "GRAFANA_URL": grafana_url,
    }
    if grafana_token and "replace-with" not in grafana_token:
        env_dict["GRAFANA_SERVICE_ACCOUNT_TOKEN"] = grafana_token
    expected_entry["env"] = env_dict

    if dry_run:
        result["actions"].append(
            {
                "path": ".vscode/mcp.json",
                "key": "grafana",
                "severity": "info",
                "message": "Would register grafana MCP server.",
                "phase": "apply",
            }
        )
        result["valid"] = True
        return result
    return _register_mcp_entry(root, mcp_path, "grafana", expected_entry, result, dry_run)


# ── Kubernetes MCP ───────────────────────────────────────────────────────


def install_k8s_mcp(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Register the Kubernetes MCP server in .vscode/mcp.json.

    Reads KUBECONFIG env var or defaults to ~/.kube/config.
    Requires a running Kubernetes cluster (e.g. Docker Desktop K8s).
    """
    result = configure_result(
        "InstallK8sMCP", dry_run, write_enabled=not dry_run
    )
    mcp_path = root / ".vscode" / "mcp.json"

    # Determine kubeconfig path
    kubeconfig = os.environ.get("KUBECONFIG", "")
    if not kubeconfig:
        default_kube = Path.home() / ".kube" / "config"
        if default_kube.exists():
            kubeconfig = str(default_kube)

    expected_entry: dict[str, Any] = {
        "command": "npx",
        "args": ["-y", "kubernetes-mcp-server@latest"],
    }
    if kubeconfig:
        expected_entry["env"] = {"KUBECONFIG": kubeconfig}

    if not kubeconfig:
        result["actions"].append(
            {
                "path": "kubeconfig",
                "key": "k8s.kubeconfig",
                "severity": "warning",
                "message": "No kubeconfig found. K8s MCP will use default kubectl context (might fail if no cluster is configured).",
                "phase": "audit",
            }
        )

    if dry_run:
        result["actions"].append(
            {
                "path": ".vscode/mcp.json",
                "key": "kubernetes",
                "severity": "info",
                "message": "Would register kubernetes MCP server.",
                "phase": "apply",
            }
        )
        result["valid"] = True
        return result
    return _register_mcp_entry(root, mcp_path, "kubernetes", expected_entry, result, dry_run)


# ── Gitea MCP ────────────────────────────────────────────────────────────


def install_gitea_mcp(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Register the Gitea MCP server in .vscode/mcp.json.

    Reads Gitea base URL and API token from .codex/client-tools.local.json.
    Requires a running Gitea instance and a valid API token (generated by
    generate_gitea_api_token or provision_lab_users).
    """
    result = configure_result(
        "InstallGiteaMCP", dry_run, write_enabled=not dry_run
    )
    mcp_path = root / ".vscode" / "mcp.json"

    # Read gitea credentials from client-tools.local.json
    client_path = root / ".codex" / "client-tools.local.json"
    gitea_url = "http://localhost:3000"
    gitea_token = ""
    if client_path.exists():
        client = read_json(client_path, optional=True)
        if client:
            gitea_section = client.get("gitea", {})
            gitea_url = str(gitea_section.get("baseUrl", "http://localhost:3000")).rstrip("/")
            gitea_token = gitea_section.get("apiToken", "")

    if not gitea_token or "replace-with" in gitea_token:
        result["actions"].append(
            {
                "path": ".codex/client-tools.local.json",
                "key": "gitea.token",
                "severity": "warning",
                "message": "Gitea API token not configured. Run provision_lab_users or generate_gitea_api_token first.",
                "phase": "audit",
            }
        )

    expected_entry: dict[str, Any] = {
        "command": "docker",
        "args": [
            "run",
            "--rm",
            "-i",
            "docker.gitea.com/gitea-mcp-server",
            "--host",
            gitea_url,
        ],
    }
    if gitea_token and "replace-with" not in gitea_token:
        expected_entry["env"] = {"GITEA_ACCESS_TOKEN": gitea_token}

    if dry_run:
        result["actions"].append(
            {
                "path": ".vscode/mcp.json",
                "key": "gitea",
                "severity": "info",
                "message": "Would register gitea MCP server.",
                "phase": "apply",
            }
        )
        result["valid"] = True
        return result
    return _register_mcp_entry(root, mcp_path, "gitea", expected_entry, result, dry_run)


# ── OpenProject MCP ──────────────────────────────────────────────────────


def install_openproject_mcp(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Register the OpenProject MCP server in .vscode/mcp.json.

    Reads OPENPROJECT_URL and OPENPROJECT_API_KEY from infra/openproject/variables.env.
    Requires a running OpenProject instance at the configured URL.
    """
    result = configure_result(
        "InstallOpenProjectMCP", dry_run, write_enabled=not dry_run
    )
    mcp_path = root / ".vscode" / "mcp.json"

    # Read openproject env vars
    op_env_path = root / "infra" / "openproject" / "variables.env"
    op_url = "http://localhost:8080"
    op_api_key = ""
    if op_env_path.exists():
        env_vars = read_env_file(op_env_path)
        op_url = env_vars.get("OPENPROJECT_URL", "http://localhost:8080")
        op_api_key = env_vars.get("OPENPROJECT_API_KEY", "")

    if not op_api_key or "replace-with" in op_api_key:
        result["actions"].append(
            {
                "path": "infra/openproject/variables.env",
                "key": "openproject.apikey",
                "severity": "warning",
                "message": "OPENPROJECT_API_KEY not configured. Registering server without API key.",
                "phase": "audit",
            }
        )

    env_dict: dict[str, str] = {
        "OPENPROJECT_URL": op_url,
    }
    if op_api_key and "replace-with" not in op_api_key:
        env_dict["OPENPROJECT_API_KEY"] = op_api_key

    expected_entry: dict[str, Any] = {
        "command": "npx",
        "args": ["-y", "openproject-mcp"],
    }
    if env_dict:
        expected_entry["env"] = env_dict

    if dry_run:
        result["actions"].append(
            {
                "path": ".vscode/mcp.json",
                "key": "openproject",
                "severity": "info",
                "message": "Would register openproject MCP server.",
                "phase": "apply",
            }
        )
        result["valid"] = True
        return result
    return _register_mcp_entry(root, mcp_path, "openproject", expected_entry, result, dry_run)


# ── Ensure MCP servers ───────────────────────────────────────────────────


def ensure_mcp_servers(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Register all MCP servers in .vscode/mcp.json.

    Checks every install_*_mcp target: playwright, grafana, kubernetes, gitea,
    and openproject. Service MCPs (grafana/gitea/openproject) read credentials
    from their config files and register the server entry even when credentials
    are missing — the installer reports a warning action so the gap is visible
    without failing the aggregate result.
    """
    result = configure_result("EnsureMCPServers", dry_run, write_enabled=not dry_run)

    results = [
        install_playwright_mcp(root, dry_run),
        install_grafana_mcp(root, dry_run),
        install_k8s_mcp(root, dry_run),
        install_gitea_mcp(root, dry_run),
        install_openproject_mcp(root, dry_run),
    ]
    for r in results:
        for action in r.get("actions", []):
            result["actions"].append(action)
        for finding in r.get("findings", []):
            result["findings"].append(finding)

    result["valid"] = not any(
        item.get("severity") == "error" for item in result["findings"]
    )
    return result


# ── Validate skill manifest ──────────────────────────────────────────────


def validate_manifest(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Validate that every skill in .codex/skills/manifest.json maps to an existing SKILL.md on disk.

    Reads the manifest categories, collects all skill paths, and checks each one
    exists relative to the .codex/skills/ directory. Reports missing skills as errors.
    """
    result = configure_result(
        "ValidateManifest", dry_run, write_enabled=False
    )
    manifest_path = root / ".codex" / "skills" / "manifest.json"
    skills_dir = root / ".codex" / "skills"

    if not manifest_path.exists():
        add_bucket_item(
            result["findings"],
            ".codex/skills/manifest.json",
            "missing.manifest",
            "Manifest file not found at .codex/skills/manifest.json.",
            "error",
            "pre-start",
        )
        result["valid"] = False
        return result

    try:
        manifest = read_json(manifest_path, optional=False)
    except Exception as ex:
        add_bucket_item(
            result["findings"],
            ".codex/skills/manifest.json",
            "parse.error",
            f"Could not parse manifest JSON: {ex}",
            "error",
            "pre-start",
        )
        result["valid"] = False
        return result

    categories = manifest.get("categories", {})
    if not isinstance(categories, dict):
        add_bucket_item(
            result["findings"],
            ".codex/skills/manifest.json",
            "invalid.categories",
            "'categories' key must be a JSON object.",
            "error",
            "pre-start",
        )
        result["valid"] = False
        return result

    total_skills = 0
    missing: list[str] = []
    valid: list[str] = []

    for cat_name, cat_data in categories.items():
        if not isinstance(cat_data, dict):
            continue
        cat_skills = cat_data.get("skills", [])
        if not isinstance(cat_skills, list):
            continue
        for skill_path in cat_skills:
            total_skills += 1
            full_path = skills_dir / skill_path
            if full_path.exists():
                valid.append(f"{cat_name}/{skill_path}")
            else:
                missing.append(f"{cat_name}/{skill_path}")

    result["totalSkills"] = total_skills
    result["validSkills"] = len(valid)
    result["missingSkills"] = len(missing)

    for path in valid:
        result["actions"].append(
            {
                "path": path,
                "key": "skill.exists",
                "severity": "info",
                "message": "SKILL.md found on disk.",
                "phase": "audit",
            }
        )

    for path in missing:
        add_bucket_item(
            result["findings"],
            path,
            "skill.missing",
            f"SKILL.md not found: {skills_dir / path}",
            "error",
            "pre-start",
        )

    result["valid"] = len(missing) == 0
    return result


# ── Ensure quality tools ─────────────────────────────────────────────────

# Test framework → coverage-tool probe command. Normalized keys come from
# stack_tests._normalize_framework (pytest for Python, vitest/jest for JS/TS,
# dotnet for .NET — xunit/nunit/mstest normalize to dotnet).
_FRAMEWORK_COVERAGE_PROBES: dict[str, tuple[list[str], str]] = {
    "pytest": (["pytest", "--version"], "pytest"),
    "vitest": (["npx", "vitest", "--version"], "vitest"),
    "jest": (["npx", "jest", "--version"], "jest"),
    "dotnet": (["dotnet", "--version"], "dotnet"),
}


# Classic fallback when no stack is configured (template state) or every
# declared framework is unmapped (e.g. a custom runner) — the audit still
# probes the common coverage tools.
_FALLBACK_COVERAGE_PROBES: list[tuple[list[str], str]] = [
    (["dotnet", "--version"], "dotnet"),
    (["pytest", "--version"], "pytest"),
    (["npx", "jest", "--version"], "jest"),
]


def _coverage_probe_commands(root: Path) -> list[tuple[list[str], str]]:
    """Coverage-tool probe commands driven by stack.testFrameworks.

    Reads the configured test frameworks from the project profile and returns
    the matching probe commands (normalized via stack_tests so .NET variants
    collapse to dotnet). When no stack is configured (template state) or no
    framework has a mapped probe, falls back to the classic dotnet/pytest/jest
    tri-list so the audit still checks something.
    """
    from ._shared import load_project_profile
    from .stack_tests import _normalize_framework

    profile = load_project_profile(root)
    frameworks = (profile.get("stack") or {}).get("testFrameworks") or []
    probes: list[tuple[list[str], str]] = []
    for fw in frameworks:
        entry = _FRAMEWORK_COVERAGE_PROBES.get(_normalize_framework(fw))
        if entry and entry not in probes:
            probes.append(entry)
    return probes or _FALLBACK_COVERAGE_PROBES


def ensure_quality_tools(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Ensure quality tools are installed: lefthook, gitleaks, trivy, trunk, coverage."""
    result = configure_result("EnsureQualityTools", dry_run, write_enabled=not dry_run)
    # Lefthook
    lf_result = install_lefthook(root, dry_run)
    for action in lf_result.get("actions", []):
        result["actions"].append(action)
    for finding in lf_result.get("findings", []):
        result["findings"].append(finding)
    if not lf_result.get("valid", True):
        result["warnings"].append(
            {
                "path": "lefthook",
                "key": "install",
                "severity": "warning",
                "message": "Lefthook installation had issues; continuing with other checks.",
                "phase": "apply",
            }
        )
    # Gitleaks (skip in dry-run)
    if not dry_run:
        gitleaks_check = run_native(["gitleaks", "version"], root, timeout=10)
        if gitleaks_check["returncode"] == 0:
            result["actions"].append(
                {
                    "path": "gitleaks",
                    "key": "check",
                    "severity": "info",
                    "message": f"Gitleaks available: {gitleaks_check['stdout']}",
                    "phase": "audit",
                }
            )
        else:
            add_bucket_item(
                result["findings"],
                "gitleaks",
                "missing",
                "Gitleaks is not installed. Install from https://github.com/gitleaks/gitleaks/releases",
                "warning",
                "pre-start",
            )
    else:
        result["actions"].append(
            {
                "path": "gitleaks",
                "key": "check",
                "severity": "info",
                "message": "Would check gitleaks availability.",
                "phase": "audit",
            }
        )
    # Trivy (skip in dry-run)
    if not dry_run:
        trivy_check = run_native(["trivy", "--version"], root, timeout=10)
        if trivy_check["returncode"] == 0:
            result["actions"].append(
                {
                    "path": "trivy",
                    "key": "check",
                    "severity": "info",
                    "message": f"Trivy available: {trivy_check['stdout'][:60]}",
                    "phase": "audit",
                }
            )
        else:
            add_bucket_item(
                result["findings"],
                "trivy",
                "missing",
                "Trivy is not installed. Install from https://github.com/aquasecurity/trivy/releases",
                "warning",
                "pre-start",
            )
    else:
        result["actions"].append(
            {
                "path": "trivy",
                "key": "check",
                "severity": "info",
                "message": "Would check trivy availability.",
                "phase": "audit",
            }
        )
    # Trunk (formatting) (skip in dry-run; resolves via npx from node_modules/.bin)
    if not dry_run:
        trunk_check = run_native(
            ["npx", "--yes", "trunk", "--version"], root, timeout=30
        )
        if trunk_check["returncode"] == 0:
            result["actions"].append(
                {
                    "path": "trunk",
                    "key": "check",
                    "severity": "info",
                    "message": f"Trunk available: {trunk_check['stdout'][:60]}",
                    "phase": "audit",
                }
            )
        else:
            add_bucket_item(
                result["findings"],
                "trunk",
                "missing",
                "Trunk is not installed. Install via: npm install -D @trunkio/launcher",
                "warning",
                "pre-start",
            )
    else:
        result["actions"].append(
            {
                "path": "trunk",
                "key": "check",
                "severity": "info",
                "message": "Would check trunk availability.",
                "phase": "audit",
            }
        )
    # Coverage tool — stack-driven: probe only the frameworks declared in
    # stack.testFrameworks (pytest/vitest/jest/dotnet). Falls back to the
    # classic tri-list when no stack is configured. Skip in dry-run.
    if not dry_run:
        for tool_cmd, tool_name in _coverage_probe_commands(root):
            check = run_native(tool_cmd, root, timeout=10)
            if check["returncode"] == 0:
                result["actions"].append(
                    {
                        "path": tool_name,
                        "key": "check",
                        "severity": "info",
                        "message": f"{tool_name} available: {check['stdout'][:60]}",
                        "phase": "audit",
                    }
                )
                break
    else:
        result["actions"].append(
            {
                "path": "coverage",
                "key": "check",
                "severity": "info",
                "message": "Would check coverage tool availability.",
                "phase": "audit",
            }
        )
    result["valid"] = not any(
        item.get("severity") == "error" for item in result["findings"]
    )
    return result


# ── Skill sources config ────────────────────────────────────────────────

_SKILL_SOURCES_CONFIG = ".codex/skill-sources.json"
_SKILL_SOURCES_EXAMPLE = ".codex/skill-sources.example.json"
_SKILL_SOURCES_DEFAULT: list[dict[str, str]] = [
    {
        "name": "awesome-copilot",
        "repo": "github/awesome-copilot",
        "path": "skills",
        "branch": "main",
        "description": "GitHub's awesome-copilot skills collection",
    },
    {
        "name": "anthropics",
        "repo": "anthropics/skills",
        "path": "skills",
        "branch": "main",
        "description": "Anthropic's skills collection",
    },
]


def _load_skill_sources(root: Path) -> list[dict[str, str]]:
    """Load skill sources from .codex/skill-sources.json, falling back to example then defaults."""
    config_path = root / _SKILL_SOURCES_CONFIG
    if config_path.exists():
        config = read_json(config_path, optional=False)
        sources = config.get("sources", []) if isinstance(config, dict) else []
        if isinstance(sources, list) and sources:
            return sources
    example_path = root / _SKILL_SOURCES_EXAMPLE
    if example_path.exists():
        config = read_json(example_path, optional=False)
        sources = config.get("sources", []) if isinstance(config, dict) else []
        if isinstance(sources, list) and sources:
            return sources
    return _SKILL_SOURCES_DEFAULT


def list_available_skills(
    root: Path, github_token: str = "", dry_run: bool = False
) -> dict[str, Any]:
    """List available skills from all configured sources.

    Reads .codex/skill-sources.json, fetches subdirectories under each source's
    skills path from GitHub Contents API, and returns the list of discoverable skills.
    """
    import json as _json
    import urllib.request
    import urllib.error

    result = configure_result(
        "ListAvailableSkills", dry_run, write_enabled=False
    )

    sources = _load_skill_sources(root)
    if not sources:
        return {
            "mode": "ListAvailableSkills",
            "valid": False,
            "errors": ["No skill sources configured. Create .codex/skill-sources.json."],
        }

    if dry_run:
        result["sources"] = sources
        result["skills"] = []
        result["skillCount"] = 0
        result["valid"] = True
        return result

    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "sdd-cli",
    }
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    all_skills: list[dict[str, str]] = []
    errors: list[str] = []

    for source in sources:
        if not isinstance(source, dict):
            continue
        name = source.get("name", "")
        repo = source.get("repo", "")
        skill_path = source.get("path", "skills")
        branch = source.get("branch", "main")

        if not repo or "/" not in repo:
            errors.append(f"Source '{name}' has invalid repo: '{repo}'.")
            continue

        api_url = f"https://api.github.com/repos/{repo}/contents/{skill_path.lstrip('/')}?ref={branch}"
        src_skills: list[str] = []

        try:
            req = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as ex:
            errors.append(f"Source '{name}' returned HTTP {ex.code}: {ex.reason}")
            continue
        except Exception as ex:
            errors.append(f"Source '{name}' could not be fetched: {ex}")
            continue

        try:
            entries = _json.loads(body)
        except _json.JSONDecodeError:
            errors.append(f"Source '{name}' returned unparseable response.")
            continue

        if not isinstance(entries, list):
            errors.append(f"Source '{name}' skill path is not a directory.")
            continue

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if entry.get("type") == "dir":
                dir_name = entry.get("name", "")
                if dir_name and not dir_name.startswith("_"):
                    src_skills.append(dir_name)

        for skill_name in sorted(src_skills):
            skill_info: dict[str, str] = {
                "source": name,
                "repo": repo,
                "path": f"{skill_path}/{skill_name}",
                "name": skill_name,
                "description": f"{source.get('description', '')} -> {skill_name}",
            }
            all_skills.append(skill_info)

        if src_skills:
            result["actions"].append({
                "path": f"{name}",
                "key": "source.scanned",
                "severity": "info",
                "message": f"Found {len(src_skills)} skill(s) in '{name}' ({repo}).",
                "phase": "audit",
            })

    result["sources"] = sources
    result["skills"] = all_skills
    result["skillCount"] = len(all_skills)
    if errors:
        result["errors"] = errors
    result["valid"] = bool(all_skills) or not errors
    return result


# ── Skill copy installer (GitHub raw content) ────────────────────────────


def _resolve_skill_source(
    root: Path, repo: str, skill_path: str, source_name: str
) -> tuple[str, str]:
    """Resolve repo and skill_path from a source name, or return the provided values.

    If source_name is provided, looks up the source from config.
    Falls back to the provided repo/skill_path if source_name is empty or not found.
    """
    if source_name:
        sources = _load_skill_sources(root)
        for src in sources:
            if isinstance(src, dict) and src.get("name") == source_name:
                return src.get("repo", repo), src.get("path", skill_path)
    return repo, skill_path


def install_skill_from_github(
    root: Path,
    repo: str,
    skill_path: str,
    skill_name: str,
    branch: str = "main",
    github_token: str = "",
    source: str = "",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Install a skill folder from GitHub by reading raw content (no cloning).

    Args:
        root: Repository root (skills go under .codex/skills/<skill_name>/)
        repo: GitHub repo in "owner/repo" format (overridden by --source if provided)
        skill_path: Path within the repo to the skill directory (overridden by --source if provided)
        skill_name: Local name for the skill directory under .codex/skills/
        branch: Git branch to fetch from (default "main")
        github_token: Optional GitHub token for authenticated requests (higher rate limit)
        source: Name of a source from .codex/skill-sources.json to look up repo/skill_path
        dry_run: If True, only list what would be installed (no API calls)

    Returns:
        Dict with installed files, errors, and actions.
    """
    # Resolve source lookup if provided
    if source:
        resolved_repo, resolved_path = _resolve_skill_source(root, repo, skill_path, source)
        repo = resolved_repo
        skill_path = resolved_path
    import json as _json
    import urllib.request
    import urllib.error

    result = configure_result(
        "InstallSkill", dry_run, write_enabled=not dry_run
    )

    # ── Validate required options ─────────────────────────────────────
    if not repo or "/" not in repo or repo.count("/") != 1:
        return {
            "mode": "InstallSkill",
            "valid": False,
            "dryRun": dry_run,
            "errors": [f"Invalid repo format: '{repo}'. Expected 'owner/repo'."],
        }

    if not skill_path:
        return {
            "mode": "InstallSkill",
            "valid": False,
            "dryRun": dry_run,
            "errors": ["Missing required option: --skill-path"],
        }

    if not skill_name:
        return {
            "mode": "InstallSkill",
            "valid": False,
            "dryRun": dry_run,
            "errors": ["Missing required option: --skill-name"],
        }

    skills_target = root / ".codex" / "skills" / skill_name
    errors: list[str] = []

    # ── Dry-run: report what would happen (no API calls) ──────────────
    if dry_run:
        result["actions"].append({
            "path": f".codex/skills/{skill_name}",
            "key": "install",
            "severity": "info",
            "message": f"Would fetch skill from github.com/{repo}/{skill_path} (branch: {branch}) into .codex/skills/{skill_name}/ and register in manifest.json.",
            "phase": "apply",
        })
        result["skillName"] = skill_name
        result["installedFileCount"] = 0
        result["skippedFileCount"] = 0
        result["totalFileCount"] = 0
        result["valid"] = True
        return result

    # ── Real mode: fetch from GitHub API ──────────────────────────────
    api_base = f"https://api.github.com/repos/{repo}/contents/{skill_path.lstrip('/')}"
    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "sdd-cli",
    }
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    def _list_github_files(api_url: str, prefix: str = "") -> list[tuple[str, str]]:
        """Recursively list (relative_path, download_url) from GitHub Contents API."""
        items: list[tuple[str, str]] = []
        try:
            url = f"{api_url}?ref={branch}"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as ex:
            if ex.code == 404:
                errors.append(f"Path '{skill_path}' not found in {repo} (HTTP 404).")
            elif ex.code == 403:
                errors.append(f"GitHub API rate limit exceeded. Use --token with a GitHub token.")
            else:
                errors.append(f"GitHub API returned HTTP {ex.code}: {ex.reason}")
            return items
        except Exception as ex:
            errors.append(f"Could not fetch {api_url}: {ex}")
            return items

        try:
            entries = _json.loads(body)
        except _json.JSONDecodeError:
            errors.append(f"Could not parse GitHub API response from {api_url}.")
            return items

        if not isinstance(entries, list):
            if isinstance(entries, dict) and entries.get("type") == "file":
                rel = prefix or entries.get("name", "")
                dl_url = entries.get("download_url", "")
                if dl_url:
                    items.append((rel, dl_url))
            return items

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            entry_name = entry.get("name", "")
            entry_type = entry.get("type", "")
            rel_path = f"{prefix}/{entry_name}" if prefix else entry_name
            if entry_type == "file":
                dl_url = entry.get("download_url", "")
                if dl_url:
                    items.append((rel_path, dl_url))
            elif entry_type == "dir":
                dir_url = entry.get("url", "")
                if dir_url:
                    items.extend(_list_github_files(dir_url, rel_path))
        return items

    files = _list_github_files(api_base)

    if errors:
        result["errors"] = errors
        result["valid"] = False
        return result

    if not files:
        return {
            "mode": "InstallSkill",
            "valid": False,
            "dryRun": dry_run,
            "errors": [f"No files found at '{skill_path}' in {repo}."],
        }

    # ── Download and write files ───────────────────────────────────────
    installed: list[str] = []
    skipped: list[str] = []

    for rel_path, dl_url in files:
        target_path = skills_target / rel_path
        if target_path.exists():
            skipped.append(rel_path)
            continue

        try:
            req = urllib.request.Request(dl_url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp:
                content = resp.read()
        except Exception as ex:
            add_bucket_item(
                result["findings"],
                f".codex/skills/{skill_name}/{rel_path}",
                "download.error",
                f"Could not download {dl_url}: {ex}",
                "error",
                "apply",
            )
            continue

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(content)
        installed.append(rel_path)

        result["actions"].append({
            "path": f".codex/skills/{skill_name}/{rel_path}",
            "key": "install",
            "severity": "info",
            "message": f"Installed ({len(content)} bytes).",
            "phase": "apply",
        })

    if skipped:
        result["actions"].append({
            "path": f".codex/skills/{skill_name}",
            "key": "skip.existing",
            "severity": "info",
            "message": f"Skipped {len(skipped)} existing file(s): {', '.join(skipped[:5])}" + (
                f" plus {len(skipped) - 5} more" if len(skipped) > 5 else ""
            ),
            "phase": "audit",
        })

    # ── Update manifest.json if SKILL.md was installed ─────────────────
    skill_md_installed = any(f.endswith("SKILL.md") for f, _ in files)
    if skill_md_installed:
        manifest_path = root / ".codex" / "skills" / "manifest.json"
        if manifest_path.exists():
            manifest = read_json(manifest_path, optional=False)
            categories = manifest.get("categories", {})
            skill_ref = f"{skill_name}/SKILL.md"
            already_registered = any(
                skill_ref in cat_data.get("skills", [])
                for cat_data in categories.values()
                if isinstance(cat_data, dict)
            )
            if not already_registered:
                community = categories.setdefault("community", {
                    "description": "Community-installed skills from GitHub",
                    "skills": [],
                })
                if isinstance(community, dict):
                    skills_list = community.setdefault("skills", [])
                    if isinstance(skills_list, list) and skill_ref not in skills_list:
                        skills_list.append(skill_ref)
                        write_json(manifest_path, manifest)
                        result["actions"].append({
                            "path": ".codex/skills/manifest.json",
                            "key": "manifest.update",
                            "severity": "info",
                            "message": f"Registered '{skill_ref}' in 'community' category.",
                            "phase": "apply",
                        })
        else:
            manifest = {
                "schemaVersion": "1.0",
                "description": "Skill manifest for this repository.",
                "categories": {
                    "community": {
                        "description": "Community-installed skills from GitHub",
                        "skills": [f"{skill_name}/SKILL.md"],
                    }
                },
            }
            write_json(manifest_path, manifest)
            result["actions"].append({
                "path": ".codex/skills/manifest.json",
                "key": "manifest.created",
                "severity": "info",
                "message": f"Created manifest.json with '{skill_name}' in 'community' category.",
                "phase": "apply",
            })

    result["skillName"] = skill_name
    result["installedFileCount"] = len(installed)
    result["skippedFileCount"] = len(skipped)
    result["totalFileCount"] = len(files)
    result["valid"] = not any(
        item.get("severity") == "error" for item in result.get("findings", [])
    ) and not result.get("errors")
    return result


# ── Hybrid skill installer (npx → GitHub fallback) ───────────────────────


def _install_skill_with_fallback(
    root: Path,
    repo: str,
    skill_path: str,
    skill_name: str,
    branch: str = "main",
    github_token: str = "",
    source: str = "",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Install a skill — try npx skills add first, fall back to GitHub copy.

    Primary: runs ``npx skills add <owner/repo> --skill <skill-name> --yes``
    Fallback: calls :func:`install_skill_from_github` if npx is unavailable
    or the skill can't be found via the npx registry.
    """
    result = configure_result(
        "InstallSkill", dry_run, write_enabled=not dry_run
    )

    # Resolve source lookup if provided
    resolved_repo = repo
    resolved_path = skill_path
    if source:
        res_repo, res_path = _resolve_skill_source(root, repo, skill_path, source)
        resolved_repo = res_repo
        resolved_path = res_path

    # ── Dry-run: report both paths ───────────────────────────────────
    if dry_run:
        result["actions"].append({
            "path": f".codex/skills/{skill_name}",
            "key": "install",
            "severity": "info",
            "message": (
                f"Would try npx skills add first. "
                f"Fallback: fetch from github.com/{resolved_repo}/{resolved_path} "
                f"into .codex/skills/{skill_name}/ and register in manifest.json."
            ),
            "phase": "apply",
        })
        result["skillName"] = skill_name
        result["valid"] = True
        return result

    # ── Try npx skills add first ─────────────────────────────────────
    npx_cmd = ["npx", "skills", "add", resolved_repo, "--skill", skill_name, "--yes"]
    try:
        npx_result = run_native(npx_cmd, root, timeout=60)
        if npx_result["returncode"] == 0:
            result["actions"].append({
                "path": f".codex/skills/{skill_name}",
                "key": "npx.skill.installed",
                "severity": "info",
                "message": f"Skill '{skill_name}' installed via npx skills add.",
                "phase": "apply",
            })
            result["skillName"] = skill_name
            result["method"] = "npx"
            result["valid"] = True
            return result
    except Exception as ex:
        result["actions"].append({
            "path": "npx",
            "key": "npx.fallback",
            "severity": "info",
            "message": f"npx skills add failed: {ex}. Falling back to GitHub copy.",
            "phase": "apply",
        })

    # ── Fallback: GitHub copy ────────────────────────────────────────
    fallback = install_skill_from_github(
        root,
        repo=resolved_repo,
        skill_path=resolved_path,
        skill_name=skill_name,
        branch=branch,
        github_token=github_token,
        source="",
        dry_run=False,
    )
    for action in fallback.get("actions", []):
        result["actions"].append(action)
    for err in fallback.get("errors", []):
        result.setdefault("errors", []).append(err)
    result["skillName"] = fallback.get("skillName", skill_name)
    result["method"] = "github-copy"
    result["valid"] = fallback.get("valid", False)
    return result


# ── Tool installer entry point ───────────────────────────────────────────


def run_tool_installer(args: list[str]) -> int:
    """CLI entry point for tool-installer commands."""
    import json as _json

    if not args:
        print(
            "Available: install-lefthook, install-playwright-mcp, "
            "install-grafana-mcp, install-openproject-mcp, "
            "validate-manifest, install-k8s-mcp, install-gitea-mcp, "
            "install-skill, list-skills, ensure-mcp-servers, "
            "ensure-quality-tools, install-sdd-template, update-sdd-template",
            file=sys.stderr,
        )
        return 1
    subcommand = args[0]
    options = parse_pairs(args[1:])
    root = Path(options.get("root", REPO_ROOT))
    dry_run = options.get("dry-run", "false").lower() == "true"
    handlers: dict[str, Any] = {
        "install-lefthook": lambda: install_lefthook(root, dry_run),
        "install-playwright-mcp": lambda: install_playwright_mcp(root, dry_run),
        "install-grafana-mcp": lambda: install_grafana_mcp(root, dry_run),
        "install-openproject-mcp": lambda: install_openproject_mcp(root, dry_run),
        "install-gitea-mcp": lambda: install_gitea_mcp(root, dry_run),
        "install-k8s-mcp": lambda: install_k8s_mcp(root, dry_run),
        "install-skill": lambda: install_skill_from_github(
            root,
            repo=options.get("repo", ""),
            skill_path=options.get("skill-path", ""),
            skill_name=options.get("skill-name", ""),
            branch=options.get("branch", "main"),
            github_token=options.get("token", ""),
            source=options.get("source", ""),
            dry_run=dry_run,
        ),
        "install-skill": lambda: _install_skill_with_fallback(
            root,
            repo=options.get("repo", ""),
            skill_path=options.get("skill-path", ""),
            skill_name=options.get("skill-name", ""),
            branch=options.get("branch", "main"),
            github_token=options.get("token", ""),
            source=options.get("source", ""),
            dry_run=dry_run,
        ),
        "list-skills": lambda: list_available_skills(
            root,
            github_token=options.get("token", ""),
            dry_run=dry_run,
        ),
        "validate-manifest": lambda: validate_manifest(root, dry_run),
        "ensure-mcp-servers": lambda: ensure_mcp_servers(root, dry_run),
        "ensure-quality-tools": lambda: ensure_quality_tools(root, dry_run),
    }
    if subcommand in ("install-sdd-template", "update-sdd-template"):
        source = Path(options.get("source", REPO_ROOT))
        target = Path(options.get("target", root))
        version = options.get("version")
        result = install_or_update_sdd_tool(
            source, target, version, subcommand.split("-")[1], dry_run
        )
        print(_json.dumps(result, indent=2))
        return 0
    handler = handlers.get(subcommand)
    if not handler:
        print(f"Unknown tool-installer subcommand: {subcommand}", file=sys.stderr)
        return 1
    result = handler()
    print(_json.dumps(result, indent=2))
    return 0 if result.get("valid", False) else 1


def _ensure_local_git_repo(root: Path) -> dict[str, Any]:
    """Initialize a local Git repo in the target so lefthook can install hooks."""
    result = {"initialized": False, "branch": "", "remoteConfigured": False}
    try:
        if not (root / ".git").exists():
            completed = subprocess.run(  # nosec
                ["git", "init", "-b", "dev"],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0:
                completed = subprocess.run(  # nosec
                    ["git", "init"],
                    cwd=root,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if completed.returncode != 0:
                    raise CliError(
                        f"Could not initialize local Git repository: {completed.stderr.strip() or completed.stdout.strip()}"
                    )
                subprocess.run(  # nosec
                    ["git", "checkout", "-B", "dev"],
                    cwd=root,
                    check=False,
                    capture_output=True,
                    text=True,
                )
            result["initialized"] = True
        branch = git_text(root, ["branch", "--show-current"])
        if branch != "dev":
            subprocess.run(  # nosec
                ["git", "checkout", "-B", "dev"],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
            )
            branch = git_text(root, ["branch", "--show-current"])
        result["branch"] = branch
        result["remoteConfigured"] = bool(git_text(root, ["remote"]))
    except OSError as ex:
        raise CliError(f"Could not initialize local Git repository: {ex}") from ex
    return result


def _latest_sdd_tool_version(source: Path) -> str:
    tags = git_text(source, ["tag", "--list", "v*"])
    versions: list[tuple[int, int, int, str]] = []
    for tag in tags.splitlines():
        match = __import__("re").match(r"^v(\d+)\.(\d+)\.(\d+)$", tag.strip())
        if match:
            versions.append(
                (
                    int(match.group(1)),
                    int(match.group(2)),
                    int(match.group(3)),
                    tag.strip(),
                )
            )
    if not versions:
        raise CliError(
            "No final release tags found. Pass --version vMAJOR.MINOR.PATCH or create a release tag first."
        )
    return max(versions)[3]


def _unmanaged_collisions(
    source: Path,
    target: Path,
    files: list[str],
    owned: set[str],
    *,
    preserve_examples: set[str],
) -> list[str]:
    from ._shared import (
        get_sdd_tool_preserve_files,
        walk_sdd_source_files,
    )

    collisions: list[str] = []
    managed = set(files)
    preserve = get_sdd_tool_preserve_files()
    # Uses walk_sdd_source_files which skips excluded dirs (node_modules, etc.)
    # during traversal — much faster than rglob + post-filter.
    for relative in walk_sdd_source_files(source):
        if relative in managed or relative in preserve or relative in owned:
            continue
        if relative in preserve_examples:
            continue
        dst = target / relative
        if dst.exists() and dst.read_bytes() != (source / relative).read_bytes():
            collisions.append(relative)
    for relative in files:
        dst = target / relative
        if not dst.exists():
            continue
        if relative in owned:
            continue
        if relative in preserve or relative in preserve_examples:
            continue
        # Managed files are intentionally overwritten during update
        if relative in managed:
            continue
        if dst.read_bytes() != (source / relative).read_bytes():
            collisions.append(relative)
    return collisions
