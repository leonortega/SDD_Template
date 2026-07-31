"""Memory search: search repository memory files."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

from ._shared import REPO_ROOT, CliError, find_meta, parse_pairs


def search_memory(root: Path, queries: list[str], list_topics: bool) -> Any:
    """Search memory files in .codex/memory/."""
    memory_root = root / ".codex" / "memory"
    if not memory_root.exists():
        raise CliError(f"Memory root not found: {memory_root}")
    skip = {"MEMORY.md", "memory_summary.md", "retrieval-policy.md"}
    entries: list[dict[str, str]] = []
    for path in sorted(memory_root.glob("*.md")):
        if path.name in skip:
            continue
        content = path.read_text(encoding="utf-8")
        for match in re.finditer(r"(?ms)^##\s+(.+?)\n(.*?)(?=^##\s+|\Z)", content):
            body = match.group(2)
            plain = re.sub(r"(?m)^-\s+(Type|Status|Source|Last verified):.+$", "", body)
            plain = re.sub(r"\s+", " ", plain).strip()
            entries.append(
                {
                    "file": path.relative_to(root).as_posix(),
                    "title": match.group(1).strip(),
                    "type": find_meta(body, "Type"),
                    "status": find_meta(body, "Status"),
                    "source": find_meta(body, "Source"),
                    "lastVerified": find_meta(body, "Last verified"),
                    "excerpt": plain[:240] + ("..." if len(plain) > 240 else ""),
                }
            )
    if list_topics:
        return [
            {k: row[k] for k in ("file", "title", "type", "status", "lastVerified")}
            for row in entries
        ]
    terms = [
        term.strip() for query in queries for term in query.split(",") if term.strip()
    ]
    if terms:
        return [
            row
            for row in entries
            if all(term.lower() in " ".join(row.values()).lower() for term in terms)
        ]
    return {
        "memoryRoot": memory_root.relative_to(root).as_posix(),
        "usage": "python -m tools.sdd_cli.memory_search search --query term1 --query term2 or --list-topics",
        "files": [
            path.relative_to(root).as_posix()
            for path in sorted(memory_root.glob("*.md"))
        ],
    }


# ── CLI entry point ──────────────────────────────────────────────────────


def run_memory_search(args: list[str]) -> int:
    """CLI entry point for memory-search commands."""
    import json as _json

    if not args or args[0] != "search":
        print(
            "Usage: memory-search search [--query TERM] [--list-topics] [--json] [--root PATH]",
            file=sys.stderr,
        )
        return 1
    options = parse_pairs(args[1:])
    root = Path(options.get("root", REPO_ROOT))
    queries = options.get("query", "").split(",") if options.get("query") else []
    list_topics = options.get("list-topics", "false").lower() == "true"
    as_json = options.get("json", "false").lower() == "true"
    try:
        result = search_memory(root, queries, list_topics)
    except CliError as ex:
        print(str(ex), file=sys.stderr)
        return 1
    if as_json or isinstance(result, dict):
        print(_json.dumps(result, indent=2))
    else:
        for row in result:
            print(" | ".join(str(row.get(key, "")) for key in row))
    return 0
