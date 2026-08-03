"""Prerequisites: Python, Node.js, PowerShell execution policy."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from ._shared import (
    PYTHON_REQUIRES,
    REPO_ROOT,
    CliError,
    native_command,
    run_native,
)


def check_python() -> dict[str, Any]:
    """Check Python version meets minimum requirement."""
    version = sys.version_info[:2]
    ok = version >= PYTHON_REQUIRES
    return {
        "command": "check-python",
        "valid": ok,
        "current": f"{version[0]}.{version[1]}",
        "required": f"{PYTHON_REQUIRES[0]}.{PYTHON_REQUIRES[1]}",
        "python": sys.executable,
    }


def install_python() -> dict[str, Any]:
    """Guide user to install Python 3.11+."""
    result = check_python()
    if result["valid"]:
        return result
    raise CliError(
        f"Python {result['required']}+ is required (found {result['current']}). "
        "Download from https://www.python.org/downloads/ or use your package manager."
    )


def check_node() -> dict[str, Any]:
    """Check if Node.js is available."""
    node = run_native(["node", "--version"], REPO_ROOT, timeout=10)
    # On Windows, Python subprocess cannot start a bare "npm" (a .cmd file)
    # with shell=False — always invoke the explicit npm.cmd name.
    npm = run_native(native_command("npm") + ["--version"], REPO_ROOT, timeout=20)
    return {
        "command": "check-node",
        "valid": node["returncode"] == 0 and npm["returncode"] == 0,
        "nodeVersion": node["stdout"] if node["returncode"] == 0 else "",
        "npmVersion": npm["stdout"] if npm["returncode"] == 0 else "",
    }


def _node_bin_dir() -> str | None:
    """Directory containing the resolved node executable, or None."""
    try:
        out = run_native(
            ["node", "-e", "console.log(process.execPath)"], REPO_ROOT, timeout=10
        )
    except Exception:
        return None
    if out.get("returncode") != 0 or not out.get("stdout", "").strip():
        return None
    line = out["stdout"].strip().splitlines()[-1].strip()
    try:
        return str(Path(line).resolve().parent)
    except Exception:
        return None


def _npm_candidates() -> list[Path]:
    """Plausible locations for npm (npm.cmd on Windows), in priority order."""
    candidates: list[Path] = []
    exe_dir = _node_bin_dir()
    if exe_dir:
        candidates.append(Path(exe_dir) / "npm.cmd")
        candidates.append(Path(exe_dir) / "npm")
    program_files = os.environ.get("ProgramFiles")
    if program_files:
        candidates.append(Path(program_files) / "nodejs" / "npm.cmd")
    return candidates


def _add_dir_to_user_path(win_dir: str) -> bool:
    """Add a directory to the user PATH (Windows) and the current process.

    Uses PowerShell ``[Environment]::SetEnvironmentVariable`` — unlike
    ``setx``, it does not truncate PATH at 1024 characters. Returns True on
    success (or when the directory is already present).
    """
    if sys.platform != "win32":
        return False
    # PowerShell single-quoted strings escape a literal quote by doubling it;
    # this keeps an unusual path (e.g. one containing a quote) from breaking
    # out of the interpolated script.
    escaped = win_dir.replace("'", "''")
    script = (
        "$ErrorActionPreference='Stop'; "
        f"$d='{escaped}'; "
        "$p=[Environment]::GetEnvironmentVariable('Path','User'); "
        "if ($p -and (($p -split ';') -contains $d)) { Write-Output 'ok'; exit 0 } "
        "$p = if ($p) { $p.TrimEnd(';') + ';' + $d } else { $d }; "
        "[Environment]::SetEnvironmentVariable('Path', $p, 'User'); "
        "Write-Output 'ok'"
    )
    result = run_native(
        ["powershell", "-NoProfile", "-Command", script], REPO_ROOT, timeout=30
    )
    if result["returncode"] != 0:
        return False
    # Make the change visible to this process and its children right away.
    os.environ["PATH"] = win_dir + os.pathsep + os.environ.get("PATH", "")
    return True


def install_node() -> dict[str, Any]:
    """Guide the user to install Node.js, or repair a missing npm PATH entry."""
    result = check_node()
    if result["valid"]:
        return result
    if result.get("nodeVersion") and not result.get("npmVersion"):
        # Node is present but npm cannot be invoked: try to locate npm next
        # to node.exe and add its folder to the user PATH, then re-check.
        for candidate in _npm_candidates():
            if candidate.exists() and _add_dir_to_user_path(str(candidate.parent)):
                refreshed = check_node()
                if refreshed["valid"]:
                    refreshed["message"] = (
                        f"npm found at {candidate} and its folder was added to "
                        "the user PATH. Re-run `prereqs check` to confirm."
                    )
                    return refreshed
        raise CliError(
            f"Node.js found ({result['nodeVersion'].strip()}) but npm was not "
            "found on PATH. Install Node.js LTS (includes npm) from "
            "https://nodejs.org/ or add npm to PATH manually."
        )
    raise CliError(
        "Node.js and npm are required. "
        "Download from https://nodejs.org/ or use your package manager."
    )


def enable_powershell_execution_policy() -> dict[str, Any]:
    """Enable PowerShell script execution (RemoteSigned)."""
    if sys.platform != "win32":
        return {
            "command": "enable-powershell",
            "valid": True,
            "message": "Not Windows; skipped.",
        }
    result = run_native(
        [
            "powershell",
            "-Command",
            "Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force",
        ],
        REPO_ROOT,
        timeout=30,
    )
    return {
        "command": "enable-powershell",
        "valid": result["returncode"] == 0,
        "message": (
            "PowerShell execution policy set to RemoteSigned."
            if result["returncode"] == 0
            else result["stderr"]
        ),
    }


def run_prereqs(args: list[str]) -> int:
    """CLI entry point for prereqs commands."""
    if not args or args[0] == "check":
        results = {
            "python": check_python(),
            "node": check_node(),
            "powershell": enable_powershell_execution_policy(),
        }
        import json

        print(json.dumps(results, indent=2))
        all_valid = all(r["valid"] for r in results.values())
        return 0 if all_valid else 1

    subcommands = {
        "install-python": install_python,
        "install-node": install_node,
        "enable-powershell": enable_powershell_execution_policy,
    }
    handler = subcommands.get(args[0])
    if handler is None:
        print(f"Unknown prereqs subcommand: {args[0]}", file=sys.stderr)
        print(
            "Available: check, install-python, install-node, enable-powershell",
            file=sys.stderr,
        )
        return 1

    import json

    result = handler()
    print(json.dumps(result, indent=2))
    return 0 if result.get("valid", False) else 1
