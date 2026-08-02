"""Run the stack's product tests (unit, integration, architecture) and the
coverage gate locally.

Used by the lefthook pre-push hook so the CI image stays lean: stack
runtimes (.NET SDK, Go, ...) live on the developer machine, not in
`sdd-e2e-ci:local`. The test levels follow `.codex/skills/_shared/
test-requirements.md` (unit/integration/architecture).

Coverage gate: after a framework's tests pass, coverage runs with the
configurable threshold `coverage.minimumPercent` from
`.codex/quality.local.json` (fallback `.codex/quality.example.json`, default
`80`). Coverage below the threshold fails the gate. Frameworks with no
coverage command mapped report a gap step (non-blocking) — the CI workflow
remains the authoritative coverage gate for those, per the delivery contract.

Rule (authority level 5): never assume a tech stack. Frameworks come from
`project-profile.local.json → stack.testFrameworks`; commands are mapped per
framework. If no stack is configured, this reports and exits 0.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from ._shared import REPO_ROOT, load_project_profile, parse_pairs, quality_coverage_minimum

# Per-framework (install_cmd, test_cmd) pairs covering the three test levels.
# IMPORTANT: pytest is Python-only. .NET test frameworks (xunit, nunit,
# mstest) run via `dotnet test`, which requires the .NET SDK locally — never
# map a .NET framework to pytest.
_COMMANDS: dict[str, tuple[list[str], list[str]]] = {
    "pytest": (
        ["python3", "-m", "pip", "install", "-r", "requirements.txt"],
        ["python3", "-m", "pytest", "test/unit", "test/integration", "test/architecture", "-q"],
    ),
    "vitest": (
        ["npm", "ci"],
        ["npx", "vitest", "run", "test/unit", "test/integration", "test/architecture"],
    ),
    "jest": (
        ["npm", "ci"],
        ["npx", "jest", "test/unit", "test/integration", "test/architecture"],
    ),
    # .NET test frameworks all run through the dotnet CLI.
    "dotnet": (["dotnet", "restore"], ["dotnet", "test"]),
    "xunit": (["dotnet", "restore"], ["dotnet", "test"]),
    "nunit": (["dotnet", "restore"], ["dotnet", "test"]),
    "mstest": (["dotnet", "restore"], ["dotnet", "test"]),
}

# Per-framework coverage commands that fail the gate when coverage is below
# `{threshold}` (substituted at runtime from quality config, default 80).
# pytest requires pytest-cov; vitest/jest require their coverage provider;
# .NET uses coverlet properties (`/p:CollectCoverage` + `/p:Threshold`).
_COVERAGE_COMMANDS: dict[str, list[str]] = {
    "pytest": [
        "python3", "-m", "pytest", "test/unit", "test/integration", "test/architecture",
        "--cov=.", "--cov-fail-under={threshold}", "-q",
    ],
    "vitest": [
        "npx", "vitest", "run", "test/unit", "test/integration", "test/architecture",
        "--coverage", "--coverage.thresholds.lines={threshold}",
    ],
    "jest": [
        "npx", "jest", "test/unit", "test/integration", "test/architecture",
        "--coverage", "--coverageThreshold", '{"global":{"lines":{threshold}}}',
    ],
    "dotnet": [
        "dotnet", "test",
        "/p:CollectCoverage=true", "/p:CoverletOutputFormat=cobertura",
        "/p:Threshold={threshold}", "/p:ThresholdType=line",
    ],
}

# .NET framework names normalize to the single "dotnet" entry (also covers
# values like "xunit.net", "xunit.v3", "nunit3").
_DOTNET_PREFIXES = ("dotnet", "xunit", "nunit", "mstest")

_DEFAULT_THRESHOLD = 80


def _normalize_framework(fw: Any) -> str:
    key = str(fw).lower().strip()
    if key.startswith(_DOTNET_PREFIXES):
        return "dotnet"
    return key


def _read_coverage_threshold(root: Path) -> int:
    """Coverage minimum percent via the shared quality config chain."""
    return quality_coverage_minimum(root, _DEFAULT_THRESHOLD)


def run_stack_tests(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Run all configured stack test levels + coverage gate. Returns a report dict."""
    result: dict[str, Any] = {
        "mode": "StackTests",
        "dryRun": dry_run,
        "valid": True,
        "skipped": False,
        "frameworks": [],
        "steps": [],
    }

    profile = load_project_profile(root)
    stack = profile.get("stack") or {}
    frameworks = stack.get("testFrameworks") or []
    result["frameworks"] = list(frameworks)

    if not frameworks:
        result["skipped"] = True
        result["steps"].append({
            "command": "stack-tests",
            "message": (
                "No stack.testFrameworks configured — product tests and coverage "
                "skipped. Configure the stack (set-project-stack) to enable test gates."
            ),
            "valid": True,
        })
        return result

    threshold = _read_coverage_threshold(root)
    result["coverageThreshold"] = threshold

    failed = False
    for fw in frameworks:
        entry = _COMMANDS.get(_normalize_framework(fw))
        if not entry:
            # Configured-but-unmapped frameworks fail loudly (never a silent
            # pass with zero tests executed).
            print(f"WARNING: no command mapped for framework {fw!r} — add it to _COMMANDS.")
            result["steps"].append({
                "command": f"stack-tests/{fw}",
                "message": f"No command mapped for framework {fw!r} — add it to _COMMANDS in stack_tests.py.",
                "valid": False,
            })
            failed = True
            continue

        install_cmd, test_cmd = entry
        coverage_cmd = _COVERAGE_COMMANDS.get(_normalize_framework(fw))
        if coverage_cmd:
            label_cmd = " ".join(part.replace("{threshold}", str(threshold)) for part in coverage_cmd)
            coverage_label = f" and coverage (threshold {threshold}%) via {label_cmd}"
        else:
            coverage_label = " (no coverage command mapped — CI is the coverage gate)"

        if dry_run:
            result["steps"].append({
                "command": f"stack-tests/{fw}",
                "message": (
                    f"Would install deps ({' '.join(install_cmd)}), "
                    f"run tests ({' '.join(test_cmd)}){coverage_label}."
                ),
                "valid": True,
            })
            continue

        print(f"Installing deps for {fw}: {' '.join(install_cmd)}")
        if subprocess.call(install_cmd) != 0:
            result["steps"].append({
                "command": f"stack-tests/{fw}/install",
                "message": f"Dependency install failed for {fw}.",
                "valid": False,
            })
            failed = True
            continue

        print(f"Running {fw} tests (unit/integration/architecture): {' '.join(test_cmd)}")
        if subprocess.call(test_cmd) != 0:
            result["steps"].append({
                "command": f"stack-tests/{fw}/test",
                "message": f"Test run failed for {fw}.",
                "valid": False,
            })
            failed = True
            continue

        result["steps"].append({
            "command": f"stack-tests/{fw}",
            "message": f"{fw} tests passed (unit/integration/architecture).",
            "valid": True,
        })

        # Coverage gate: only after this framework's tests pass.
        if not coverage_cmd:
            result["steps"].append({
                "command": f"stack-tests/{fw}/coverage",
                "message": (
                    f"No coverage command mapped for {fw} — coverage gate skipped; "
                    "CI remains the authoritative coverage gate."
                ),
                "valid": True,
            })
            continue

        run_cmd = [part.replace("{threshold}", str(threshold)) for part in coverage_cmd]
        print(f"Running {fw} coverage (threshold {threshold}%): {' '.join(run_cmd)}")
        if subprocess.call(run_cmd) != 0:
            result["steps"].append({
                "command": f"stack-tests/{fw}/coverage",
                "message": f"Coverage below {threshold}% for {fw} — coverage gate FAILED.",
                "valid": False,
            })
            failed = True
        else:
            result["steps"].append({
                "command": f"stack-tests/{fw}/coverage",
                "message": f"{fw} coverage passed (threshold {threshold}%).",
                "valid": True,
            })

    # Unmapped frameworks already set failed=True above, so a configured stack
    # with zero mapped entries can never pass silently.
    result["valid"] = not failed
    if failed:
        print("FAILED: one or more product test or coverage gates failed.")
    return result


def print_result(result: dict[str, Any], dry_run: bool) -> None:
    """Print the stack-tests summary + per-step status (shared by CLI entry points)."""
    print(f"Stack tests: {'OK' if result.get('valid') else 'FAILED'}"
          + (f" (coverage threshold {result.get('coverageThreshold', _DEFAULT_THRESHOLD)}%)" if result.get("frameworks") else "")
          + (" (dry-run, nothing executed)" if dry_run else ""))
    for step in result.get("steps", []):
        status = "OK" if step.get("valid") else "FAIL"
        print(f"  [{status}] {step.get('message')}")


def run_stack_tests_cli(args: list[str]) -> int:
    """CLI entry point for the stack-tests command (free-form args)."""
    options = parse_pairs(args)
    root = Path(options.get("root", REPO_ROOT))
    dry_run = options.get("dry-run", "false").lower() == "true"
    result = run_stack_tests(root, dry_run)
    print_result(result, dry_run)
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(run_stack_tests_cli(sys.argv[1:]))
