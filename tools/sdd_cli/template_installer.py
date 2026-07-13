"""Template installer: install/update SDD template into consumer repositories."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from ._shared import REPO_ROOT, CliError
from .tool_installer import install_or_update_sdd_tool


def run_template_installer(args: list[str]) -> int:
    """CLI entry point for template-installer commands."""
    import json as _json
    if not args or args[0] not in ("install", "update"):
        print("Usage: template-installer <install|update> --target PATH [--source PATH] [--version X.Y.Z] [--dry-run]", file=sys.stderr)
        return 1
    action = args[0]
    options = _parse_pairs(args[1:])
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


def _parse_pairs(items: list[str]) -> dict[str, str]:
    from ._shared import trim_remainder
    args = trim_remainder(items)
    pairs: dict[str, str] = {}
    index = 0
    while index < len(args):
        key = args[index]
        if not key.startswith("--"):
            raise CliError(f"Expected --option, got: {key}")
        if index + 1 >= len(args):
            raise CliError(f"Missing value for option {key}")
        pairs[key[2:]] = args[index + 1]
        index += 2
    return pairs