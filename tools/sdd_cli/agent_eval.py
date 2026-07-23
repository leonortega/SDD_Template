"""
Agent Evaluation CLI — run Promptfoo tests and produce structured output.

Usage:
  python -m tools.sdd_cli agent-eval run
  python -m tools.sdd_cli agent-eval view
  python -m tools.sdd_cli agent-eval ci
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from ._shared import REPO_ROOT, CliError


def run_eval(root: Path | None = None) -> dict[str, Any]:
    """Run Promptfoo evaluation and return structured results.

    Returns a dict with pass/fail count, duration, and per-test details.
    """
    base = root or REPO_ROOT
    config_path = base / ".codex" / "agent-evals" / "promptfooconfig.yaml"

    if not config_path.exists():
        raise CliError(f"Eval config not found: {config_path}")

    # Install promptfoo if not available
    try:
        subprocess.run(  # nosec
            ["npx", "promptfoo", "--version"],
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as err:
        raise CliError(
            "promptfoo is not available. Install with: npm install -g promptfoo"
        ) from err

    # Run eval without cache
    try:
        result = subprocess.run(  # nosec
            [
                "npx",
                "promptfoo",
                "eval",
                "--config",
                str(config_path),
                "--no-cache",
                "--output",
                str(base / ".codex" / "agent-evals" / "results.tmp.json"),
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired as err:
        raise CliError("Eval timed out after 300 seconds.") from err

    stdout = result.stdout or ""
    stderr = result.stderr or ""
    returncode = result.returncode

    # Parse results output
    results_path = base / ".codex" / "agent-evals" / "results.tmp.json"
    results: dict[str, Any] = {
        "returncode": returncode,
        "passed": 0,
        "failed": 0,
        "total": 0,
        "tests": [],
        "stdout_summary": stdout.strip()[:2000],
        "stderr_summary": stderr.strip()[:2000] if stderr else "",
    }

    if results_path.exists():
        try:
            raw = json.loads(results_path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                results["tests"] = raw
                results["total"] = len(raw)
                for test in raw:
                    if test.get("pass"):
                        results["passed"] += 1
                    else:
                        results["failed"] += 1
            elif isinstance(raw, dict):
                results["results_json"] = raw
        except (json.JSONDecodeError, KeyError):
            pass
        results_path.unlink(missing_ok=True)

    results["valid"] = results["failed"] == 0
    return results


def run_ci_eval(root: Path | None = None) -> int:
    """Run evals in CI mode — exits with non-zero on failure.

    Returns 0 if all tests pass, 1 if any fail.
    """
    results = run_eval(root)
    print(json.dumps(results, indent=2))

    if results.get("stdout_summary"):
        print("\n--- stdout ---")
        print(results["stdout_summary"])

    if results.get("stderr_summary"):
        print("\n--- stderr ---")
        print(results["stderr_summary"])

    if results["valid"]:
        print(f"\n✓ All {results['total']} tests passed.")
        return 0
    else:
        print(f"\n✗ {results['failed']}/{results['total']} tests failed.")
        return 1


def show_view(root: Path | None = None) -> int:
    """Open Promptfoo web UI for viewing results."""
    base = root or REPO_ROOT
    try:
        subprocess.run(["npx", "promptfoo", "view"], cwd=base, check=False)  # nosec
        return 0
    except FileNotFoundError:
        print("promptfoo not found. Install with: npm install -g promptfoo")
        return 1


def run_agent_eval(args: list[str]) -> int:
    """CLI entry point for agent-eval subcommands."""
    if not args:
        print("Available: run, view, ci", file=sys.stderr)
        return 1

    subcommand = args[0]

    if subcommand == "run":
        results = run_eval()
        print(json.dumps(results, indent=2))
        return 0 if results["valid"] else 1

    elif subcommand == "ci":
        return run_ci_eval()

    elif subcommand == "view":
        return show_view()

    else:
        print(f"Unknown agent-eval subcommand: {subcommand}", file=sys.stderr)
        print("Available: run, view, ci", file=sys.stderr)
        return 1
