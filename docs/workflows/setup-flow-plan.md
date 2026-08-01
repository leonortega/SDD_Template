# Setup Flow — Architectural Plan

## Problem

Currently the installation flow is fragmented across multiple CLI commands with no single entry point:

| What                  | Command                                           | File                        |
|-----------------------|---------------------------------------------------|-----------------------------|
| Prerequisites         | `prereqs check` / `prereqs install-python` etc.   | `prereqs.py`                |
| Lab setup             | `environment-lab setup-lab` → now runs `full-setup` | `environment_lab.py`        |
| Tool installation     | `tool-installer install-*` (individual tools)     | `tool_installer.py`         |
| Project guidance      | `guidance discover` / `configure set-project-stack` | `guidance.py` / `cli.py`  |

No single command or document ties them together.

## Proposed Solution

Add a new top-level CLI subcommand: `full-setup`

```bash
python -m tools.sdd_cli full-setup [--dry-run true]
```

It runs 4 stages in order, each with a clear pass/fail summary:

```
full-setup
├── Stage 1: Prerequisites
│   ├── Check Python 3.11+
│   ├── Check Node.js + npm
│   ├── Check PowerShell execution policy (Windows)
│   ├── Check Docker Desktop installed + running
│   └── Offer install guidance for missing items
│
├── Stage 2: Lab Setup (delegates to setup-lab)
│   ├── Init local files
│   ├── Build Gitea Actions images
│   ├── Validate Docker Desktop
│   ├── Compose up (Gitea, OpenProject, Nexus, monitoring)
│   ├── Health checks (all services)
│   ├── Provision users + board
│   ├── Install MCPs (Grafana, Gitea, OpenProject)
│   ├── Push code to Gitea
│   ├── K8s enable + MCP + scaffold
│   └── Semgrep config
│
├── Stage 3: Tool Installation (remaining)
│   ├── ensure-mcp-servers (playwright, grafana, k8s, gitea, openproject)
│   ├── ensure-quality-tools
│   └── validate-manifest
│
└── Stage 4: Project Guidance
    ├── Inspect project profile
    ├── Detect stack (frontend/backend/database)
    ├── Discover relevant skills from manifest
    └── Print guidance
```

## File & Module Design

### New file: `tools/sdd_cli/full_setup.py`

```python
def run_full_setup(root, dry_run) -> int:
    """Orchestrate all 4 stages."""

def stage1_prerequisites(root, dry_run) -> dict[str, Any]:
    """Check and guide prerequisites."""

def stage2_lab_setup(root, dry_run) -> dict[str, Any]:
    """Delegate to setup_lab() in environment_lab.py."""

def stage3_tool_installation(root, dry_run) -> dict[str, Any]:
    """Install all tools not covered by stage 2."""

def stage4_project_guidance(root, dry_run) -> dict[str, Any]:
    """Inspect profile, discover guidance, print next steps."""
```

### CLI wiring in `tools/sdd_cli/cli.py`

```python
# New subparser
full = sub.add_parser("full-setup")
full.add_argument("--dry-run", action="store_true", default=False)
full.add_argument("--root", default=str(REPO_ROOT))
full.add_argument("full_args", nargs=argparse.REMAINDER)
full.set_defaults(func=_dispatch_full_setup)
```

### Reuse, don't duplicate

| Stage | Reuses from              |
|-------|--------------------------|
| 1     | `prereqs.py` (check fns) |
| 2     | `environment_lab.py` (`setup_lab`) |
| 3     | `tool_installer.py` (install fns)  |
| 4     | `guidance.py` (`discover_project_guidance`) |

### Result format

Each stage returns a standard dict:

```python
{
    "stage": "1-template-installation",
    "valid": True/False,
    "steps": [ ... individual step results ... ],
    "warnings": [...],
    "errors": [...]
}
```

The final output aggregates all 4 stages:

```python
{
    "valid": True/False,  # False if any stage failed
    "stages": [stage1_result, stage2_result, ...],
    "failed_stages": [stage names with errors],
}
```

## Benefits

- **Single entry point** for new users: one command, full setup
- **Idempotent**: re-running skips completed steps (via existing dry-run patterns)
- **Visible failures**: each stage reports pass/fail, errors collected and shown
- **Modular**: each stage is a separate function, easy to test and maintain
- **Backward compatible**: existing `setup-lab`, `prereqs check`, etc. remain unchanged

## Notes

- Template installation was originally Stage 1 but was removed — `full-setup` itself is part of the template, so it can only run after the template is already in place.
- `environment-lab setup-lab` now delegates to `full-setup` (the full 4-stage flow) instead of running only the lab setup.
- The old individual commands (`prereqs check`, `environment-lab setup-lab`, `tool-installer install-*`, etc.) remain available for granular control.
