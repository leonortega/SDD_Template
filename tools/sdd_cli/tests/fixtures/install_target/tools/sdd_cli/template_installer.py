"""Template installer: install/update SDD template into consumer repositories."""

from __future__ import annotations

import sys
from pathlib import Path

from ._shared import REPO_ROOT, CliError, parse_pairs
from .tool_installer import install_or_update_sdd_tool


def run_template_installer(args: list[str]) -> int:
    """CLI entry point for template-installer commands."""
    import json as _json

    if not args or args[0] not in ("install", "update"):
        print(
            "Usage: template-installer <install|update> --target PATH [--source PATH] "
            "[--version VERSION] [--dry-run]",
            file=sys.stderr,
        )
        return 1
    action = args[0]
    options = parse_pairs(args[1:])
    source = Path(options.get("source", REPO_ROOT))
    target = Path(options.get("target", REPO_ROOT))
    version = options.get("version")
    dry_run = options.get("dry-run", "false").lower() == "true"
    try:
        result = install_or_update_sdd_tool(source, target, version, action, dry_run)
    except CliError as ex:
        print(str(ex), file=sys.stderr)
        return 1
    print(_json.dumps(result, indent=2))
    return 0
