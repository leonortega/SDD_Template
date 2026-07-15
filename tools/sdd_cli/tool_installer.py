"""Tool installer: lefthook, codegraph, codebase-memory, claw-compactor, quality tools."""

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
        add_bucket_item(result["findings"], "lefthook.yml", "config.missing",
                        "lefthook.yml is missing.", "warning", "pre-start")
        result["valid"] = False
        return result
    lefthook_path = _resolve_lefthook()
    if lefthook_path is None:
        result["actions"].append({"path": "lefthook", "key": "install", "severity": "info",
                                  "message": "lefthook binary not found. Attempting auto-install.", "phase": "apply"})
        if dry_run:
            result["actions"].append({"path": "lefthook", "key": "install", "severity": "info",
                                      "message": "Would download and install lefthook to user-local bin.", "phase": "apply"})
            result["valid"] = True
            return result
        lefthook_path = _install_lefthook_user_local(root, result)
        if lefthook_path is None:
            result["valid"] = False
            return result
    if dry_run:
        result["actions"].append({"path": "lefthook", "key": "install", "severity": "info",
                                  "message": f"Would run {lefthook_path} install.", "phase": "apply"})
        result["valid"] = True
        return result
    install = run_native([lefthook_path, "install"], root, timeout=30)
    if install["returncode"] == 0:
        result["actions"].append({"path": "lefthook", "key": "install", "severity": "info",
                                  "message": "Lefthook git hooks installed.", "phase": "apply"})
    else:
        add_bucket_item(result["findings"], "lefthook", "install",
                        f"Could not install lefthook: {install['stderr']}", "error", "apply")
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
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "bin"
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
        add_bucket_item(result["findings"], "lefthook", "platform.unsupported",
                        f"Unsupported platform/arch for lefthook auto-install: {sys.platform}", "error", "apply")
        return None
    bin_dir = _lefthook_user_bin()
    bin_name = "lefthook.exe" if platform_name == "windows" else "lefthook"
    destination = bin_dir / bin_name
    if destination.exists():
        result["actions"].append({"path": str(destination), "key": "install", "severity": "info",
                                  "message": "lefthook binary already exists.", "phase": "apply"})
        return str(destination)
    try:
        import urllib.request
        api_url = "https://api.github.com/repos/evilmartians/lefthook/releases/latest"
        req = urllib.request.Request(api_url, headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "sdd-cli",
        })
        with urllib.request.urlopen(req, timeout=30) as response:
            release = json.loads(response.read().decode("utf-8"))
        tag = release.get("tag_name", "")
        tag_without_v = tag[1:] if tag.startswith("v") else tag
        platform_capitalized = platform_name.capitalize()
        if platform_name == "windows":
            asset_name = f"lefthook_{tag_without_v}_{platform_capitalized}_{arch}.exe"
        else:
            asset_name = f"lefthook_{tag_without_v}_{platform_capitalized}_{arch}"
        download_url = f"https://github.com/evilmartians/lefthook/releases/download/{tag}/{asset_name}"
        result["actions"].append({"path": "lefthook", "key": "download", "severity": "info",
                                  "message": f"Downloading lefthook from {download_url}.", "phase": "apply"})
        with urllib.request.urlopen(download_url, timeout=60) as response:
            data = response.read()
        if not data:
            add_bucket_item(result["findings"], "lefthook", "download",
                            "Downloaded lefthook payload was empty.", "error", "apply")
            return None
        bin_dir.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        if platform_name != "windows":
            destination.chmod(destination.stat().st_mode | 0o111)
        result["actions"].append({"path": str(destination), "key": "install", "severity": "info",
                                  "message": f"Installed lefthook to {destination}.", "phase": "apply"})
        return str(destination)
    except Exception as ex:
        add_bucket_item(result["findings"], "lefthook", "install",
                        f"Could not install lefthook: {ex}", "error", "apply")
        return None


# ── Codegraph MCP ────────────────────────────────────────────────────────

def install_codegraph(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Verify codegraph via npx and ensure .codex/config.toml has MCP config."""
    result = configure_result("InstallCodegraph", dry_run, write_enabled=not dry_run)
    npx_check = run_native(["npx", "--version"], root, timeout=10)
    if npx_check["returncode"] != 0:
        add_bucket_item(result["findings"], "npx", "missing",
                        f"npx is not available: {npx_check['stderr']}", "error", "pre-start")
        result["valid"] = False
        return result
    verify_command = ["npx", "--yes", "@colbymchenry/codegraph@1.1.1", "--version"]
    if dry_run:
        result["actions"].append({"path": "npx", "key": "verify-codegraph", "severity": "info",
                                  "message": f"Would verify codegraph: {' '.join(verify_command)}", "phase": "apply"})
        result["valid"] = True
        return result
    verify = run_native(verify_command, root, timeout=60)
    if verify["returncode"] != 0:
        add_bucket_item(result["findings"], "codegraph", "verify",
                        f"Could not verify codegraph: {verify['stderr']}", "error", "apply")
        result["valid"] = False
        return result
    result["actions"].append({"path": "npx", "key": "verify-codegraph", "severity": "info",
                              "message": f"Codegraph verified: {verify['stdout']}", "phase": "apply"})
    config_path = root / ".codex" / "config.toml"
    config_dir = config_path.parent
    if not config_dir.exists():
        if not dry_run:
            config_dir.mkdir(parents=True, exist_ok=True)
        result["actions"].append({"path": ".codex/config.toml", "key": "directory", "severity": "info",
                                  "message": "Created .codex directory.", "phase": "apply"})
    codegraph_config_present = False
    if config_path.exists():
        existing_content = config_path.read_text(encoding="utf-8")
        if "[mcp_servers.codegraph]" in existing_content:
            codegraph_config_present = True
    if not codegraph_config_present:
        if dry_run:
            result["actions"].append({"path": ".codex/config.toml", "key": "codegraph-config", "severity": "info",
                                      "message": "Would add codegraph MCP config to .codex/config.toml.", "phase": "apply"})
        else:
            codegraph_section = """[mcp_servers.codegraph]
command = "npx"
args = ["--yes", "@colbymchenry/codegraph@1.1.1", "serve", "--mcp"]

[mcp_servers.codegraph.env]
CODEGRAPH_TELEMETRY = "0"
DO_NOT_TRACK = "1"

"""
            if config_path.exists():
                existing_content = config_path.read_text(encoding="utf-8")
                config_path.write_text(existing_content + "\n" + codegraph_section, encoding="utf-8")
            else:
                config_path.write_text(codegraph_section, encoding="utf-8")
            result["actions"].append({"path": ".codex/config.toml", "key": "codegraph-config", "severity": "info",
                                      "message": "Added codegraph MCP server configuration to .codex/config.toml.", "phase": "apply"})
    else:
        result["actions"].append({"path": ".codex/config.toml", "key": "codegraph-config", "severity": "info",
                                  "message": "Codegraph MCP server configuration already present.", "phase": "apply"})
    result["valid"] = True
    return result


# ── Codebase-memory MCP ──────────────────────────────────────────────────

def install_codebase_memory(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Register codebase-memory-mcp in .vscode/mcp.json."""
    result = configure_result("InstallCodebaseMemory", dry_run, write_enabled=not dry_run)
    mcp_path = root / ".vscode" / "mcp.json"
    shim_path = root / "tools" / "codebase_memory_mcp" / "mcp_cap_shim.py"
    if not shim_path.exists():
        add_bucket_item(result["findings"], "tools/codebase_memory_mcp/mcp_cap_shim.py", "missing.shim",
                        "codebase-memory-mcp shim script not found. Run tools/codebase_memory_mcp/install.ps1 first.",
                        "error", "pre-start")
        result["valid"] = False
        return result
    server_name = "codebase-memory-mcp"
    expected_entry = {
        "type": "stdio",
        "command": sys.executable,
        "args": [str(shim_path)],
    }
    if not mcp_path.exists():
        if dry_run:
            result["actions"].append({"path": ".vscode/mcp.json", "key": "create", "severity": "info",
                                      "message": f"Would create .vscode/mcp.json with {server_name}.", "phase": "apply"})
            result["valid"] = True
            return result
        config: dict[str, Any] = {"servers": {}}
    else:
        try:
            config = read_json(mcp_path, optional=False)
        except Exception:
            add_bucket_item(result["findings"], ".vscode/mcp.json", "parse.error",
                            "Could not parse existing .vscode/mcp.json.", "error", "pre-start")
            result["valid"] = False
            return result
    servers = config.get("servers", {})
    if not isinstance(servers, dict):
        add_bucket_item(result["findings"], ".vscode/mcp.json", "invalid.servers",
                        "servers key must be a JSON object.", "error", "pre-start")
        result["valid"] = False
        return result
    existing = servers.get(server_name)
    if existing == expected_entry:
        result["actions"].append({"path": ".vscode/mcp.json", "key": server_name, "severity": "info",
                                  "message": f"{server_name} is already configured in .vscode/mcp.json.", "phase": "apply"})
        result["valid"] = True
        return result
    if existing is not None:
        changed_keys = [k for k in expected_entry if existing.get(k) != expected_entry[k]]
        result["actions"].append({"path": ".vscode/mcp.json", "key": server_name, "severity": "info",
                                  "message": f"Updating {server_name} config (changed: {', '.join(changed_keys)}).", "phase": "apply"})
    else:
        result["actions"].append({"path": ".vscode/mcp.json", "key": server_name, "severity": "info",
                                  "message": f"Adding {server_name} server to .vscode/mcp.json.", "phase": "apply"})
    if not dry_run:
        servers[server_name] = expected_entry
        config["servers"] = servers
        mcp_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(mcp_path, config)
    result["valid"] = True
    return result


# ── Claw-compactor ───────────────────────────────────────────────────────

def install_claw_compactor(root: Path, version: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    """Install claw-compactor into the shared MCP venv."""
    user_home = Path.home()
    mcp_python = user_home / ".mcp_shared_venv" / "Scripts" / "python.exe"
    if not mcp_python.exists():
        return {"command": "install-claw", "valid": False,
                "error": f"MCP shared venv not found at {mcp_python}. Run the MCP server setup first."}
    pip_args = [str(mcp_python), "-m", "pip", "install"]
    if version:
        pip_args += [f"claw-compactor=={version}"]
    else:
        pip_args += ["claw-compactor"]
    result = configure_result("InstallClawCompactor", dry_run, write_enabled=not dry_run)
    if dry_run:
        result["actions"].append({"path": str(mcp_python), "key": "pip-install", "severity": "info",
                                  "message": f"Would install claw-compactor{'==' + version if version else ''}.", "phase": "apply"})
        result["valid"] = True
        return result
    install_result = subprocess.run(pip_args, capture_output=True, text=True)
    if install_result.returncode != 0:
        add_bucket_item(result["findings"], "claw-compactor", "pip-install",
                        f"Could not install claw-compactor: {install_result.stderr.strip()}", "error", "apply")
        result["valid"] = False
        return result
    result["actions"].append({"path": str(mcp_python), "key": "pip-install", "severity": "info",
                              "message": install_result.stdout.strip(), "phase": "apply"})
    check = subprocess.run(
        [str(mcp_python), "-m", "claw_compactor.cli", "--help"],
        capture_output=True, text=True,
    )
    if check.returncode == 0:
        result["actions"].append({"path": str(mcp_python), "key": "verify", "severity": "info",
                                  "message": "claw-compactor installed and verified.", "phase": "apply"})
    else:
        add_bucket_item(result["findings"], "claw-compactor", "verify",
                        "claw-compactor installed but CLI verification failed.", "warning", "apply")
    result["valid"] = True
    return result


# ── SDD Tool install/update ──────────────────────────────────────────────

def install_or_update_sdd_tool(
    source: Path, target: Path, version: str | None, action: str, dry_run: bool = False,
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
    collisions = _unmanaged_collisions(source, target, files, owned, preserve_examples=SDD_TOOL_PRESERVE_EXAMPLE_FILES)
    if collisions:
        raise CliError("Refusing to overwrite unmanaged files: " + ", ".join(collisions[:10]))
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
        if dst.exists() and relative not in SDD_TOOL_PRESERVE_FILES and relative not in SDD_TOOL_PRESERVE_EXAMPLE_FILES and not is_preserved_local_json(relative):
            dst.unlink()
            removed.append(relative)
            remove_empty_parents(dst.parent, target)
    checksum = sdd_tool_checksum(target, files)
    git_bootstrap = _ensure_local_git_repo(target)
    manifest = {
        "schemaVersion": 1,
        "tool": "sdd-tool",
        "version": version or _latest_sdd_tool_version(source),
        "sourceRepo": git_text(source, ["config", "--get", "remote.origin.url"]) or str(source),
        "sourceCommit": git_text(source, ["rev-parse", "HEAD"]),
        "installedAtUtc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "checksumSha256": checksum,
        "managedFiles": files,
        "preservedFiles": sorted(SDD_TOOL_PRESERVE_FILES | SDD_TOOL_PRESERVE_EXAMPLE_FILES),
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


# ── Ensure codebase memory ───────────────────────────────────────────────

def ensure_codebase_memory(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Ensure .codex/memory/ files exist and codebase-memory-mcp is configured."""
    result = configure_result("EnsureCodebaseMemory", dry_run, write_enabled=not dry_run)
    memory_dir = root / ".codex" / "memory"
    if not memory_dir.exists():
        if dry_run:
            result["actions"].append({"path": ".codex/memory/", "key": "directory", "severity": "info",
                                      "message": "Would create .codex/memory/ directory.", "phase": "apply"})
        else:
            memory_dir.mkdir(parents=True, exist_ok=True)
            result["actions"].append({"path": ".codex/memory/", "key": "directory", "severity": "info",
                                      "message": "Created .codex/memory/ directory.", "phase": "apply"})
    seed_files = {
        ".codex/memory/memory_summary.md": "# Memory Summary\n\nNo consumer project memories recorded yet.\n",
        ".codex/memory/MEMORY.md": "# Repository Memory Index\n\n- `memory_summary.md`: compact startup context.\n"
        "- `retrieval-policy.md`: memory read/write rules.\n",
        ".codex/memory/retrieval-policy.md": "# Memory Retrieval And Write Policy\n\nUse memory as guidance only. "
        "Verify against current files and live tools before acting.\n",
    }
    for relative, content in seed_files.items():
        path = root / relative
        if path.exists():
            result["actions"].append({"path": relative, "key": "exists", "severity": "info",
                                      "message": "Memory seed file already exists.", "phase": "audit"})
            continue
        if not dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        result["actions"].append({"path": relative, "key": "created", "severity": "info",
                                  "message": "Created memory seed file.", "phase": "apply"})
    # Also ensure codebase-memory-mcp is configured in .vscode/mcp.json
    mcp_result = install_codebase_memory(root, dry_run)
    for action in mcp_result.get("actions", []):
        result["actions"].append(action)
    for finding in mcp_result.get("findings", []):
        result["findings"].append(finding)
    if not mcp_result.get("valid", True):
        result["valid"] = False
    else:
        result["valid"] = not any(item.get("severity") == "error" for item in result["findings"])
    return result


# ── Ensure quality tools ─────────────────────────────────────────────────

def ensure_quality_tools(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Ensure quality tools are installed: lefthook, gitleaks, trivy, coverage."""
    result = configure_result("EnsureQualityTools", dry_run, write_enabled=not dry_run)
    # Lefthook
    lf_result = install_lefthook(root, dry_run)
    for action in lf_result.get("actions", []):
        result["actions"].append(action)
    for finding in lf_result.get("findings", []):
        result["findings"].append(finding)
    if not lf_result.get("valid", True):
        result["warnings"].append({"path": "lefthook", "key": "install", "severity": "warning",
                                    "message": "Lefthook installation had issues; continuing with other checks.", "phase": "apply"})
    # Gitleaks (skip in dry-run)
    if not dry_run:
        gitleaks_check = run_native(["gitleaks", "version"], root, timeout=10)
        if gitleaks_check["returncode"] == 0:
            result["actions"].append({"path": "gitleaks", "key": "check", "severity": "info",
                                      "message": f"Gitleaks available: {gitleaks_check['stdout']}", "phase": "audit"})
        else:
            add_bucket_item(result["findings"], "gitleaks", "missing",
                            "Gitleaks is not installed. Install from https://github.com/gitleaks/gitleaks/releases",
                            "warning", "pre-start")
    else:
        result["actions"].append({"path": "gitleaks", "key": "check", "severity": "info",
                                  "message": "Would check gitleaks availability.", "phase": "audit"})
    # Trivy (skip in dry-run)
    if not dry_run:
        trivy_check = run_native(["trivy", "--version"], root, timeout=10)
        if trivy_check["returncode"] == 0:
            result["actions"].append({"path": "trivy", "key": "check", "severity": "info",
                                      "message": f"Trivy available: {trivy_check['stdout'][:60]}", "phase": "audit"})
        else:
            add_bucket_item(result["findings"], "trivy", "missing",
                            "Trivy is not installed. Install from https://github.com/aquasecurity/trivy/releases",
                            "warning", "pre-start")
    else:
        result["actions"].append({"path": "trivy", "key": "check", "severity": "info",
                                  "message": "Would check trivy availability.", "phase": "audit"})
    # Coverage tool (dotnet or pytest or jest depending on project; skip in dry-run)
    if not dry_run:
        for tool_cmd, tool_name in [(["dotnet", "--version"], "dotnet"),
                                     (["pytest", "--version"], "pytest"),
                                     (["npx", "jest", "--version"], "jest")]:
            check = run_native(tool_cmd, root, timeout=10)
            if check["returncode"] == 0:
                result["actions"].append({"path": tool_name, "key": "check", "severity": "info",
                                          "message": f"{tool_name} available: {check['stdout'][:60]}", "phase": "audit"})
                break
    else:
        result["actions"].append({"path": "coverage", "key": "check", "severity": "info",
                                  "message": "Would check coverage tool availability.", "phase": "audit"})
    result["valid"] = not any(item.get("severity") == "error" for item in result["findings"])
    return result


# ── Tool installer entry point ───────────────────────────────────────────

def run_tool_installer(args: list[str]) -> int:
    """CLI entry point for tool-installer commands."""
    import json as _json
    if not args:
        print("Available: install-lefthook, install-codegraph, install-codebase-memory, "
              "install-claw, ensure-codebase-memory, ensure-quality-tools, "
              "install-sdd-template, update-sdd-template", file=sys.stderr)
        return 1
    subcommand = args[0]
    options = parse_pairs(args[1:])
    root = Path(options.get("root", REPO_ROOT))
    dry_run = options.get("dry-run", "false").lower() == "true"
    handlers: dict[str, Any] = {
        "install-lefthook": lambda: install_lefthook(root, dry_run),
        "install-codegraph": lambda: install_codegraph(root, dry_run),
        "install-codebase-memory": lambda: install_codebase_memory(root, dry_run),
        "install-claw": lambda: install_claw_compactor(
            root, version=options.get("version"), dry_run=dry_run,
        ),
        "ensure-codebase-memory": lambda: ensure_codebase_memory(root, dry_run),
        "ensure-quality-tools": lambda: ensure_quality_tools(root, dry_run),
    }
    if subcommand in ("install-sdd-template", "update-sdd-template"):
        source = Path(options.get("source", REPO_ROOT))
        target = Path(options.get("target", root))
        version = options.get("version")
        result = install_or_update_sdd_tool(source, target, version, subcommand.split("-")[1], dry_run)
        print(_json.dumps(result, indent=2))
        return 0
    handler = handlers.get(subcommand)
    if not handler:
        print(f"Unknown tool-installer subcommand: {subcommand}", file=sys.stderr)
        return 1
    result = handler()
    print(_json.dumps(result, indent=2))
    return 0 if result.get("valid", False) else 1


# ── Private helpers ──────────────────────────────────────────────────────


def _ensure_local_git_repo(root: Path) -> dict[str, Any]:
    result = {"initialized": False, "branch": "", "remoteConfigured": False}
    try:
        if not (root / ".git").exists():
            completed = subprocess.run(["git", "init", "-b", "dev"], cwd=root, check=False, capture_output=True, text=True)
            if completed.returncode != 0:
                completed = subprocess.run(["git", "init"], cwd=root, check=False, capture_output=True, text=True)
                if completed.returncode != 0:
                    raise CliError(f"Could not initialize local Git repository: {completed.stderr.strip() or completed.stdout.strip()}")
                subprocess.run(["git", "checkout", "-B", "dev"], cwd=root, check=False, capture_output=True, text=True)
            result["initialized"] = True
        branch = git_text(root, ["branch", "--show-current"])
        if branch != "dev":
            subprocess.run(["git", "checkout", "-B", "dev"], cwd=root, check=False, capture_output=True, text=True)
            branch = git_text(root, ["branch", "--show-current"])
        result["branch"] = branch
        result["remoteConfigured"] = bool(git_text(root, ["remote"]))
    except OSError as ex:
        raise CliError(f"Could not initialize local Git repository: {ex}")
    return result


def _latest_sdd_tool_version(source: Path) -> str:
    tags = git_text(source, ["tag", "--list", "v*"])
    versions: list[tuple[int, int, int, str]] = []
    for tag in tags.splitlines():
        match = __import__("re").match(r"^v(\d+)\.(\d+)\.(\d+)$", tag.strip())
        if match:
            versions.append((int(match.group(1)), int(match.group(2)), int(match.group(3)), tag.strip()))
    if not versions:
        raise CliError("No final release tags found. Pass --version vMAJOR.MINOR.PATCH or create a release tag first.")
    return max(versions)[3]


def _unmanaged_collisions(
    source: Path, target: Path, files: list[str], owned: set[str], *, preserve_examples: set[str],
) -> list[str]:
    collisions: list[str] = []
    managed = set(files)
    preserve = get_sdd_tool_preserve_files()
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(source).as_posix()
        if relative in managed or relative in preserve or relative in owned:
            continue
        if relative in preserve_examples:
            continue
        dst = target / relative
        if dst.exists() and dst.read_bytes() != path.read_bytes():
            collisions.append(relative)
    for relative in files:
        dst = target / relative
        if not dst.exists() or relative in owned:
            continue
        if relative in preserve or relative in preserve_examples:
            continue
        if dst.read_bytes() != (source / relative).read_bytes():
            collisions.append(relative)
    return collisions
