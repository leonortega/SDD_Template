"""Prerequisites: Python, Node.js, PowerShell execution policy."""

from __future__ import annotations

import sys
from typing import Any

from ._shared import PYTHON_REQUIRES, REPO_ROOT, CliError, run_native


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
    npm = run_native(["npm", "--version"], REPO_ROOT, timeout=10)
    return {
        "command": "check-node",
        "valid": node["returncode"] == 0 and npm["returncode"] == 0,
        "nodeVersion": node["stdout"] if node["returncode"] == 0 else "",
        "npmVersion": npm["stdout"] if npm["returncode"] == 0 else "",
    }


def install_node() -> dict[str, Any]:
    """Guide user to install Node.js."""
    result = check_node()
    if result["valid"]:
        return result
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
