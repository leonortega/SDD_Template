"""Full setup orchestration: prereqs, lab setup, tools, guidance.

Usage:
    python -m tools.sdd_cli full-setup [--dry-run true]
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from ._shared import REPO_ROOT, add_bucket_item, configure_result, run_native


# ── Main entry point ─────────────────────────────────────────────────────


def run_full_setup(
    args: list[str] | None = None,
    *,
    root: Path | None = None,
    dry_run: bool = False,
) -> int:
    """Orchestrate all 4 stages of the full setup.

    Args:
        args: Optional flat arg list (e.g. from argparse remainder).
        root: Repository root (overrides --root in args).
        dry_run: If True, skip side-effect steps (overrides --dry-run in args).

    Stages:
        1. Prerequisites
        2. Lab setup
        3. Tool installation (remaining)
        4. Project guidance
    """
    from ._shared import parse_pairs

    options = parse_pairs(args) if args else {}
    effective_root = root or Path(options.get("root", REPO_ROOT))
    effective_dry_run = dry_run or options.get("dry-run", "false").lower() == "true"

    stages: list[dict[str, Any]] = []

    # ── Stage 1: Prerequisites ──────────────────────────────────────────
    stage1 = stage1_prerequisites(effective_root, effective_dry_run)
    stages.append(stage1)

    # ── Stage 2: Lab Setup ──────────────────────────────────────────────
    stage2 = stage2_lab_setup(effective_root, effective_dry_run)
    stages.append(stage2)

    # ── Stage 3: Tool Installation (remaining) ──────────────────────────
    stage3 = stage3_tool_installation(effective_root, effective_dry_run)
    stages.append(stage3)

    # ── Stage 4: Project Guidance ───────────────────────────────────────
    stage4 = stage4_project_guidance(effective_root, effective_dry_run)
    stages.append(stage4)

    # ── Aggregate results ───────────────────────────────────────────────
    all_valid = all(s.get("valid", True) for s in stages)
    failed_stages = [
        {"stage": s.get("mode", "?"), "errors": [
            f["message"] for f in s.get("findings", []) if f.get("severity") == "error"
        ]}
        for s in stages
        if not s.get("valid", True)
    ]

    result: dict[str, Any] = {
        "valid": all_valid,
        "stages": stages,
        "failed_stages": failed_stages,
    }

    # ── Print summary ───────────────────────────────────────────────────
    import json

    print(json.dumps(result, indent=2))

    total_stages = len(stages)
    completed = sum(1 for s in stages if s.get("valid", True))
    print("\n" + "=" * 60)
    if all_valid:
        print(f"  FULL SETUP - {completed}/{total_stages} stages complete ✓")
    else:
        print(f"  FULL SETUP - {completed}/{total_stages} stages complete, {total_stages - completed} with errors ✗")
    print("=" * 60)

    if failed_stages:
        print(f"\n  {len(failed_stages)} stage(s) reported errors:")
        for fs in failed_stages:
            stage_name = fs.get("stage", "?")
            for err in fs.get("errors", []):
                print(f"    ✗ [{stage_name}] {err}")
        print("\n  ℹ  Fix the issues above and re-run `full-setup`.")
        print("     The command is idempotent — completed steps will be skipped.\n")

    return 0 if all_valid else 1


# ── Stage 1: Prerequisites ──────────────────────────────────────────────


def stage1_prerequisites(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Stage 1: Check and guide prerequisites.

    Checks:
        - Python 3.11+
        - Node.js + npm
        - PowerShell execution policy (Windows only)
        - Docker Desktop (required for lab)
    """
    result = configure_result("Stage1-Prerequisites", dry_run, write_enabled=False)
    steps: list[dict[str, Any]] = []

    # 1a. Python version
    python_check = _check_python()
    steps.append(python_check)
    if not python_check.get("valid", True):
        add_bucket_item(
            result["findings"],
            "system/python",
            "python.version",
            f"Python {python_check.get('required', '3.11')}+ required, "
            f"found {python_check.get('current', '?')}. "
            "Download from https://www.python.org/downloads/",
            "error",
        )

    # 1b. Node.js + npm
    node_check = _check_node()
    steps.append(node_check)
    if not node_check.get("valid", True):
        add_bucket_item(
            result["findings"],
            "system/node",
            "node.missing",
            "Node.js and npm are required. "
            "Download from https://nodejs.org/",
            "error",
        )

    # 1c. PowerShell execution policy (Windows only)
    ps_check = _enable_powershell()
    steps.append(ps_check)
    if not ps_check.get("valid", True):
        add_bucket_item(
            result["findings"],
            "system/powershell",
            "powershell.policy",
            ps_check.get("message", "PowerShell execution policy could not be set."),
            "warning",
        )

    # 1d. Docker Desktop
    docker_check = _check_docker()
    steps.append(docker_check)
    if not docker_check.get("valid", True):
        add_bucket_item(
            result["findings"],
            "system/docker",
            "docker.missing",
            "Docker is required. Install Docker Desktop from https://www.docker.com/products/docker-desktop/",
            "error",
        )

    result["steps"] = steps
    result["valid"] = not any(
        item.get("severity") == "error" for item in result["findings"]
    )
    return result


# ── Stage 2: Lab Setup ──────────────────────────────────────────────────


def stage2_lab_setup(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Stage 2: Run the full lab setup (Docker Compose, provisioning, K8s).

    Delegates to environment_lab.setup_lab() which handles all 19 sub-steps.
    """
    result = configure_result("Stage2-LabSetup", dry_run, write_enabled=not dry_run)

    if dry_run:
        result["actions"].append({
            "path": "environment-lab",
            "key": "setup-lab.dry-run",
            "severity": "info",
            "message": "Would run setup-lab (Docker Compose, provisioning, K8s).",
            "phase": "apply",
        })
        result["valid"] = True
        return result

    try:
        from .environment_lab import setup_lab

        lab_result = setup_lab(root, dry_run=False)
        lab_valid = lab_result.get("valid", False)

        lab_steps = lab_result.get("steps", [])
        result["substeps"] = lab_steps

        step_count = len(lab_steps)
        step_ok = sum(1 for s in lab_steps if s.get("valid", True))

        if lab_valid:
            result["actions"].append({
                "path": "environment-lab",
                "key": "setup-lab.complete",
                "severity": "info",
                "message": f"Lab setup complete ({step_ok}/{step_count} steps passed).",
                "phase": "apply",
            })
        else:
            add_bucket_item(
                result["findings"],
                "environment-lab",
                "setup-lab.failed",
                f"Lab setup reported failures ({step_ok}/{step_count} steps passed). "
                "Check the setup-lab output above for details, fix issues, and re-run full-setup.",
                "error",
            )
            for s in lab_steps:
                if not s.get("valid", True):
                    step_name = s.get("command") or s.get("mode", "unknown")
                    step_msg = s.get("message", s.get("errors", ["No details"]))
                    if isinstance(step_msg, list):
                        step_msg = "; ".join(step_msg)
                    add_bucket_item(
                        result["findings"],
                        f"setup-lab/{step_name}",
                        "step.failed",
                        f"[{step_name}] {str(step_msg)[:300]}",
                        "error",
                    )

        lab_summary = lab_result.get("summary", {})
        if lab_summary:
            result["lab_summary"] = lab_summary

        result["valid"] = lab_valid

    except Exception as ex:
        add_bucket_item(
            result["findings"],
            "environment-lab",
            "setup-lab.exception",
            f"Lab setup raised an exception: {ex}",
            "error",
        )
        result["valid"] = False

    return result


# ── Stage 3: Tool Installation (remaining) ──────────────────────────────


def stage3_tool_installation(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Stage 3: Install tools not covered by setup-lab.

    The lab already installs: lefthook, grafana-mcp, openproject-mcp, gitea-mcp, k8s-mcp.
    Stage 3 installs the remaining tools:
        1. ensure-mcp-servers (re-ensures ALL MCP registrations in .vscode/mcp.json —
           playwright, grafana, k8s, gitea, openproject; idempotent, the lab already
           installed the service MCPs in stage 2)
        2. quality tools (gitleaks, trivy, trunk, coverage check)
        3. validate-manifest (check skill manifest integrity)
    """
    from .tool_installer import (  # type: ignore[import-not-found]
        ensure_mcp_servers,
        ensure_quality_tools,
        validate_manifest,
    )

    result = configure_result("Stage3-ToolInstallation", dry_run, write_enabled=not dry_run)
    sub_steps: list[dict[str, Any]] = []

    # Order matters:
    #   - ensure-mcp-servers registers every MCP in .vscode/mcp.json
    #   - ensure-quality-tools checks gitleaks, trivy, trunk, coverage (non-MCP)
    installers: list[tuple[str, Any]] = [
        ("ensure-mcp-servers", ensure_mcp_servers),
        ("ensure-quality-tools", ensure_quality_tools),
        ("validate-manifest", validate_manifest),
    ]

    for command_name, func in installers:
        step_result: dict[str, Any] = {"command": command_name}

        try:
            tool_result = func(root, dry_run)
            valid = tool_result.get("valid", False)
            step_result["valid"] = valid
            step_result["message"] = f"{command_name}: {'OK' if valid else 'FAILED'}"

            for action in tool_result.get("actions", []):
                result["actions"].append(action)
            for finding in tool_result.get("findings", []):
                result["findings"].append(finding)

        except Exception as ex:
            step_result["valid"] = False
            step_result["message"] = f"{command_name}: exception - {ex}"
            add_bucket_item(
                result["findings"],
                f"tools/{command_name}",
                f"{command_name}.exception",
                f"{command_name} raised an exception: {ex}",
                "error",
            )

        sub_steps.append(step_result)

    result["steps"] = sub_steps
    result["valid"] = not any(
        item.get("severity") == "error" for item in result["findings"]
    )
    return result


# ── Stage 4: Project Guidance ────────────────────────────────────────────


def stage4_project_guidance(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Stage 4: Interactive project guidance.

    1. Inspect project profile status
    2. Search internet for stack-relevant skills (never local)
    3. Show found skills and ask user which to install (interactive gate)
    4. Install ONLY the user-selected skills via npx skills add

    Non-interactive (CI): reports found skills but NEVER installs — no
    TTY confirmation available means nothing is installed.
    """
    result = configure_result(
        "Stage4-ProjectGuidance", dry_run, write_enabled=not dry_run
    )
    steps: list[dict[str, Any]] = []

    print("\n" + "=" * 60)
    print("  STAGE 4: PROJECT GUIDANCE")
    print("=" * 60)

    # 4a. Project profile status
    from ._shared import load_project_profile

    profile = load_project_profile(root)
    profile_path = root / ".codex" / "project-profile.json"

    stack_values: dict[str, str] = {}

    if profile:
        stack = profile.get("stack", {})
        if isinstance(stack, dict):
            for domain in ("frontend", "backend", "database"):
                entry = stack.get(domain, {})
                if isinstance(entry, dict) and entry.get("applies") is True:
                    val = str(entry.get("value", "")).lower().strip()
                    if val:
                        stack_values[domain] = val

        if stack_values:
            frontend = stack_values.get("frontend", "?")
            backend = stack_values.get("backend", "?")
            database = stack_values.get("database", "?")
            print(f"  [OK] Stack configured: {frontend} / {backend} / {database}")
            steps.append({
                "command": "stage4-profile",
                "title": "Project profile",
                "valid": True,
                "message": f"Stack configured: frontend={frontend}, backend={backend}, database={database}.",
            })
        else:
            print("  [WARN] Stack not fully configured.")
            print("     Run: python -m tools.sdd_cli configure set-project-stack ...")
            steps.append({
                "command": "stage4-profile",
                "title": "Project profile",
                "valid": True,
                "message": "Project profile exists but stack is not fully configured.",
            })
    else:
        if profile_path.exists():
            print("  [WARN] Project profile found but could not be parsed.")
        else:
            print("  [WARN] No project profile found.")
            print("     Run: python -m tools.sdd_cli configure set-project-stack ...")
        steps.append({
            "command": "stage4-profile",
            "title": "Project profile",
            "valid": True,
            "message": "No project profile configured. Run `configure set-project-stack` first.",
        })

    if dry_run or not stack_values:
        if not stack_values:
            print("\n  [WARN] Cannot search for skills: no stack configured.")
        else:
            print(f"\n  (dry-run) Would search internet for stack-relevant skills.")
        steps.append({
            "command": "stage4-guidance",
            "title": "Internet skill search",
            "valid": True,
            "message": "No stack configured or dry-run: skill search skipped.",
        })
        result["steps"] = steps
        result["valid"] = True
        return result

    # 4b. Search internet for stack-relevant skills
    from .guidance import setup_project_guidance

    print("\n  -- Internet Skill Search --")

    try:
        guidance_result = setup_project_guidance(
            root, stack_values, dry_run=False, interactive=True
        )

        found = guidance_result.get("foundSkills", [])
        installs = guidance_result.get("installResults", [])
        installed_count = sum(1 for r in installs if r.get("valid"))

        # Forward actions and findings
        for action in guidance_result.get("actions", []):
            result["actions"].append(action)
        for finding in guidance_result.get("findings", []):
            result["findings"].append(finding)

        steps.append({
            "command": "stage4-guidance",
            "title": "Internet skill search",
            "valid": True,
            "message": f"Found {len(found)} skill(s) online, installed {installed_count}.",
        })

        print(f"\n  [OK] Stage 4 complete. Found {len(found)} skill(s), installed {installed_count}.")

    except Exception as ex:
        print(f"\n  [WARN] Internet skill search error: {ex}")
        steps.append({
            "command": "stage4-guidance",
            "title": "Internet skill search",
            "valid": True,
            "message": f"Internet skill search skipped: {ex}",
        })

    result["steps"] = steps
    result["valid"] = True  # Advisory only — never fails
    return result


# ── Individual prerequisite checks ──────────────────────────────────────


def _check_python() -> dict[str, Any]:
    """Check Python version meets minimum requirement (3.11+).

    Delegates to ``prereqs.check_python`` — single source of truth for the
    prerequisite checks (prereqs.py, full_setup stage 1, environment-lab).
    """
    from .prereqs import check_python

    result = check_python()
    return {
        "command": "prereq-python",
        "title": "Python 3.11+",
        "valid": result["valid"],
        "current": result["current"],
        "required": result["required"],
    }


def _check_node() -> dict[str, Any]:
    """Check if Node.js and npm are available.

    Delegates to ``prereqs.check_node`` — single source of truth.
    """
    from .prereqs import check_node

    result = check_node()
    return {
        "command": "prereq-node",
        "title": "Node.js + npm",
        "valid": result["valid"],
        "nodeVersion": result.get("nodeVersion", ""),
        "npmVersion": result.get("npmVersion", ""),
    }


def _enable_powershell() -> dict[str, Any]:
    """Enable PowerShell script execution (RemoteSigned) on Windows.

    Delegates to ``prereqs.enable_powershell_execution_policy`` — single
    source of truth.
    """
    from .prereqs import enable_powershell_execution_policy

    result = enable_powershell_execution_policy()
    return {
        "command": "prereq-powershell",
        "title": "PowerShell (Windows)",
        "valid": result["valid"],
        "message": result.get("message", ""),
    }


def _check_docker() -> dict[str, Any]:
    """Check if Docker Engine is available and responding.

    Uses `docker info` which returns non-zero when the engine is unreachable
    (unlike `docker version` which returns 0 as long as the CLI binary exists).
    """
    docker_info = run_native(["docker", "info", "--format", "{{.ServerVersion}}"], REPO_ROOT, timeout=15)
    if docker_info["returncode"] == 0 and docker_info["stdout"].strip():
        return {
            "command": "prereq-docker",
            "title": "Docker Desktop",
            "valid": True,
            "version": docker_info["stdout"].strip(),
            "message": "Docker Engine is running.",
        }
    return {
        "command": "prereq-docker",
        "title": "Docker Desktop",
        "valid": False,
        "message": "Docker Engine is not responding. Is Docker Desktop installed and running?",
    }
