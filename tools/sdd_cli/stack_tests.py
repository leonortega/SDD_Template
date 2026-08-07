"""Run the stack's product tests (unit, integration, architecture) and the
coverage gate locally.

Used by the lefthook pre-push hook so the CI image stays lean: stack
runtimes (.NET SDK, Go, ...) live on the developer machine, not in
`sdd-e2e-ci:local`. The test levels follow `.codex/skills/_shared/
test-requirements.md` (unit/integration/architecture).

The gate is **layout-tolerant**: the AI-driven scaffold (dev-flow-scaffold-project)
chooses the app layout (e.g. package.json under `src/frontend/`, colocated
tests like `src/App.test.tsx`), so the commands must not assume a single
hardcoded layout. Per framework the gate resolves at runtime:

- **pytest** — uses `python3` with a `python` fallback (Windows); runs only
  inside existing canonical test dirs (`test/unit`, `test/integration`,
  `test/architecture`, plus `tests/` variants). When none exist it reports a
  non-blocking gap instead of running pytest repo-wide (which would pick up
  unrelated tests such as `tools/sdd_cli`).
- **vitest / jest** — `npm ci` and the test runner run from the resolved
  package root (the directory containing `package-lock.json`, checked at the
  repo root, `*/` and `src/*/`). When the canonical test dirs are absent the
  runner is invoked without explicit paths so the framework's own config
  discovers tests. A configured JS/TS stack with no lockfile anywhere fails
  loudly (incomplete scaffold).
- **.NET family** (xunit/nunit/mstest/dotnet) — runs from the repo root;
  `dotnet test` discovers the solution/projects.

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

from ._shared import (
    REPO_ROOT,
    load_project_profile,
    native_command,
    parse_pairs,
    quality_coverage_minimum,
    run_native,
)

# Per-framework (install_cmd, test_cmd) pairs covering the three test levels.
# IMPORTANT: pytest is Python-only. .NET test frameworks (xunit, nunit,
# mstest) run via `dotnet test`, which requires the .NET SDK locally — never
# map a .NET framework to pytest.
#
# `{python}` is resolved at runtime to `python3` (POSIX) or `python` (Windows
# fallback). pytest/vitest/jest test paths are appended at runtime from
# `_resolve_test_paths` — see the module docstring on layout tolerance.
_COMMANDS: dict[str, tuple[list[str], list[str]]] = {
    "pytest": (
        ["{python}", "-m", "pip", "install", "-r", "requirements.txt"],
        ["{python}", "-m", "pytest"],
    ),
    "vitest": (
        native_command("npm") + ["ci"],
        native_command("npx") + ["vitest", "run"],
    ),
    "jest": (
        native_command("npm") + ["ci"],
        native_command("npx") + ["jest"],
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
# Test paths are appended at runtime (same resolution as _COMMANDS); npx uses
# native_command so it resolves on Windows.
_COVERAGE_COMMANDS: dict[str, list[str]] = {
    "pytest": [
        "{python}", "-m", "pytest",
        "--cov=.", "--cov-fail-under={threshold}", "-q",
    ],
    "vitest": native_command("npx") + [
        "vitest", "run",
        "--coverage", "--coverage.thresholds.lines={threshold}",
    ],
    "jest": native_command("npx") + [
        "jest", "--coverage",
        "--coverageThreshold", '{"global":{"lines":{threshold}}}',
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

# Canonical test-directory layouts per framework, in priority order. Only
# directories that exist are used; when none exist vitest/jest fall back to
# their own config-driven discovery and pytest reports a non-blocking gap.
_CANONICAL_TEST_DIRS: dict[str, tuple[str, ...]] = {
    "pytest": (
        "test/unit", "test/integration", "test/architecture",
        "tests/unit", "tests/integration", "tests/architecture",
    ),
    "vitest": ("test/unit", "test/integration", "test/architecture"),
    "jest": ("test/unit", "test/integration", "test/architecture"),
}

# Glob patterns (relative to the repo root) locating package-lock.json — the
# JS/TS package root where `npm ci` and vitest/jest must run. Covers the
# scaffold convention (src/frontend, src/backend) plus common top-level
# layouts; bounded, never walks node_modules.
_PACKAGE_ROOT_PATTERNS = (
    "package-lock.json",
    "*/package-lock.json",
    "src/*/package-lock.json",
)


def _normalize_framework(fw: Any) -> str:
    key = str(fw).lower().strip()
    if key.startswith(_DOTNET_PREFIXES):
        return "dotnet"
    return key


def _read_coverage_threshold(root: Path) -> int:
    """Coverage minimum percent via the shared quality config chain."""
    return quality_coverage_minimum(root, _DEFAULT_THRESHOLD)


def _resolve_python(root: Path) -> list[str]:
    """python3 on POSIX; fall back to python when python3 is missing (Windows)."""
    check = run_native(["python3", "--version"], root, timeout=10)
    return ["python3"] if check["returncode"] == 0 else ["python"]


def _resolve_package_root(root: Path) -> Path | None:
    """Directory containing package-lock.json (npm ci / vitest cwd), or None."""
    for pattern in _PACKAGE_ROOT_PATTERNS:
        for lockfile in sorted(root.glob(pattern)):
            return lockfile.parent
    return None


def _resolve_test_paths(root: Path, fw_key: str) -> list[str]:
    """Existing canonical test dirs (test/unit|integration|architecture, ...)."""
    return [
        directory
        for directory in _CANONICAL_TEST_DIRS.get(fw_key, ())
        if (root / directory).is_dir()
    ]


def _call(command: list[str], cwd: Path | None = None) -> int:
    """subprocess.call that never raises FileNotFoundError (reports 127).

    A missing executable (e.g. `python3` on a bare Windows box, an uninstalled
    SDK) previously crashed the whole pre-push hook with a WinError 2 traceback.
    127 lets the gate fail with an actionable message instead.
    """
    try:
        return subprocess.call(command, cwd=cwd)
    except FileNotFoundError:
        return 127


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
        fw_key = _normalize_framework(fw)
        entry = _COMMANDS.get(fw_key)
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
        coverage_cmd = _COVERAGE_COMMANDS.get(fw_key)
        cwd: Path | None = root

        # ── Per-framework runtime resolution (layout tolerance) ──────────
        if fw_key == "pytest":
            py = _resolve_python(root)
            # native_command keeps the resolved interpreter consistent with the
            # probe (python3.exe/.cmd on Windows) — plain subprocess.call would
            # otherwise miss the .cmd resolution and return 127.
            py_exec = native_command(py[0])
            install_cmd = [part.replace("{python}", py_exec[0]) for part in install_cmd]
            test_cmd = [part.replace("{python}", py_exec[0]) for part in test_cmd]
            paths = _resolve_test_paths(root, fw_key)
            if not paths:
                # Never run pytest repo-wide (it would pick up unrelated tests,
                # e.g. tools/sdd_cli). Report the gap; CI remains authoritative.
                result["steps"].append({
                    "command": f"stack-tests/{fw}",
                    "message": (
                        f"{fw}: no test/unit|integration|architecture directories "
                        "found — nothing to run; CI remains the authoritative "
                        "product-test gate."
                    ),
                    "valid": True,
                })
                continue
            test_cmd = test_cmd + paths
            if coverage_cmd:
                coverage_cmd = [
                    part.replace("{python}", py_exec[0]) for part in coverage_cmd
                ] + paths
        elif fw_key in ("vitest", "jest"):
            pkg_root = _resolve_package_root(root)
            if pkg_root is None:
                # A configured JS/TS stack with no lockfile anywhere is an
                # incomplete scaffold — fail loudly, never pass silently.
                result["steps"].append({
                    "command": f"stack-tests/{fw}",
                    "message": (
                        f"{fw}: no package-lock.json found (checked root, */ and "
                        "src/*/) — the scaffold may be incomplete. Run the project "
                        "scaffold before pushing."
                    ),
                    "valid": False,
                })
                failed = True
                continue
            cwd = pkg_root
            # Commands run from the package root, so canonical test paths must
            # be resolved relative to it (colocated layout: src/frontend/test/unit).
            test_cmd = test_cmd + _resolve_test_paths(cwd, fw_key)
            if coverage_cmd:
                coverage_cmd = coverage_cmd + _resolve_test_paths(cwd, fw_key)
        # .NET family: commands run from the repo root (solution/project discovery).

        # Substitute the coverage threshold once for the dry-run label; the
        # real run substitutes it again at execution time.
        if coverage_cmd:
            label_cmd = " ".join(
                part.replace("{threshold}", str(threshold)) for part in coverage_cmd
            )
            coverage_label = f" and coverage (threshold {threshold}%) via {label_cmd}"
        else:
            coverage_label = " (no coverage command mapped — CI is the coverage gate)"

        if dry_run:
            cwd_suffix = f" (cwd: {cwd})" if cwd != root else ""
            result["steps"].append({
                "command": f"stack-tests/{fw}",
                "message": (
                    f"Would install deps ({' '.join(install_cmd)}), "
                    f"run tests ({' '.join(test_cmd)}){coverage_label}{cwd_suffix}."
                ),
                "valid": True,
            })
            continue

        print(f"Installing deps for {fw} (cwd: {cwd}): {' '.join(install_cmd)}")
        install_rc = _call(install_cmd, cwd)
        if install_rc != 0:
            result["steps"].append({
                "command": f"stack-tests/{fw}/install",
                "message": (
                    f"Dependency install failed for {fw}: {install_cmd[0]} not "
                    "found on PATH — install the stack toolchain first."
                    if install_rc == 127
                    else f"Dependency install failed for {fw}."
                ),
                "valid": False,
            })
            failed = True
            continue

        print(f"Running {fw} tests (unit/integration/architecture): {' '.join(test_cmd)}")
        test_rc = _call(test_cmd, cwd)
        if test_rc != 0:
            result["steps"].append({
                "command": f"stack-tests/{fw}/test",
                "message": (
                    f"Test run failed for {fw}: {test_cmd[0]} not found on PATH "
                    "— install the stack toolchain first."
                    if test_rc == 127
                    else f"Test run failed for {fw}."
                ),
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
        coverage_rc = _call(run_cmd, cwd)
        if coverage_rc != 0:
            result["steps"].append({
                "command": f"stack-tests/{fw}/coverage",
                "message": (
                    f"Coverage below {threshold}% for {fw} — coverage gate FAILED."
                    if coverage_rc != 127
                    else f"Coverage gate failed for {fw}: {run_cmd[0]} not found on PATH."
                ),
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
          + (f" (dry-run, nothing executed)" if dry_run else ""))
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
