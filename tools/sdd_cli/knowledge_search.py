"""Knowledge search: search repository knowledge files."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

from ._shared import REPO_ROOT, CliError, find_meta, parse_pairs


def search_knowledge(root: Path, queries: list[str], list_topics: bool) -> Any:
    """Search knowledge files under knowledge/.

    Indexes one entry per Markdown file (excluding README index files).
    Uses the H1 title when present, falling back to the first H2 section
    or the file stem.
    """
    knowledge_root = root / "knowledge"
    if not knowledge_root.exists():
        raise CliError(f"Knowledge root not found: {knowledge_root}")
    entries: list[dict[str, str]] = []
    for path in sorted(knowledge_root.rglob("*.md")):
        if path.name == "README.md":
            continue
        content = path.read_text(encoding="utf-8")
        title_match = re.search(r"(?m)^#\s+(.+?)\s*$", content)
        if title_match:
            title = title_match.group(1).strip()
        else:
            section_match = re.search(r"(?m)^##\s+(.+?)\s*$", content)
            title = (
                section_match.group(1).strip()
                if section_match
                else path.stem.replace("-", " ").title()
            )
        plain = re.sub(r"(?m)^-\s+(Type|Status|Source|Last verified):.+$", "", content)
        plain = re.sub(r"(?m)^#{1,6}\s+.*$", "", plain)
        plain = re.sub(r"\s+", " ", plain).strip()
        entries.append(
            {
                "file": path.relative_to(root).as_posix(),
                "title": title,
                "type": find_meta(content, "Type"),
                "status": find_meta(content, "Status"),
                "source": find_meta(content, "Source"),
                "lastVerified": find_meta(content, "Last verified"),
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
        "knowledgeRoot": knowledge_root.relative_to(root).as_posix(),
        "usage": "python -m tools.sdd_cli knowledge-search search --query term1 --query term2 or --list-topics",
        "files": [
            path.relative_to(root).as_posix()
            for path in sorted(knowledge_root.rglob("*.md"))
            if path.name != "README.md"
        ],
    }


# ── Knowledge classification (deterministic) ─────────────────────────────

# Keyword → knowledge category mapping (deterministic, no LLM). Mirrors the
# classification table in .codex/skills/docs-knowledge-maintenance/SKILL.md
# and knowledge/README.md#update-process.
CATEGORY_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("errors", ("error", "errors", "failed", "failure", "timeout", "crash", "exception", "traceback")),
    ("fixes", ("fix", "fixed", "fixes", "workaround", "patched", "resolved")),
    ("patterns", ("pattern", "patterns", "idiom", "idioms")),
    ("anti-patterns", ("anti-pattern", "anti pattern", "bad practice")),
    ("troubleshooting", ("troubleshoot", "troubleshooting", "diagnos", "checklist")),
    ("lessons-learned", ("lesson", "lessons", "retrospective", "learned", "qa result", "release lesson", "workflow lesson")),
    ("prompts", ("prompt", "prompts", "reusable prompt")),
    ("references", ("reference", "references", "module map", "project map")),
]

_SLUG_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from",
    "in", "is", "it", "of", "on", "or", "the", "to", "was", "we", "with",
    "fix", "fixed", "fixes", "add", "added", "adding", "update", "updated",
    "updating", "implement", "implemented", "implementing", "support",
    "supported", "create", "created", "creating", "change", "changed",
    "changing",
}


# Source-path prefixes → implementation knowledge candidate.
# Docs paths are handled explicitly in the changed-path loop below.
_IMPLEMENTATION_PREFIXES: tuple[str, ...] = (
    "src/", "app/", "lib/", "packages/", "tools/",
)


# Explicit task-area regexes → docs / lessons candidates.
_TASK_AREA_RULES: list[tuple[str, str, str]] = [
    (r"\b(api|endpoint|contract)\b", "docs-api", "task mentions API surface"),
    (r"\b(architecture|system)\b", "docs-architecture", "task mentions architecture"),
    (r"\b(deploy|deployment|release|rollback|hotfix|qa)\b", "lessons-learned", "task mentions deploy/release/QA lesson area"),
]


_FAILURE_RE = re.compile(r"\b(fail|failed|failure|error|timeout|crash)\b")


def _slug(text: str, fallback: str = "topic") -> str:
    """Derive a deterministic slug from free text (lowercase, hyphen-joined)."""
    words = [
        w
        for w in re.findall(r"[a-z0-9]+", text.lower())
        if len(w) >= 3 and w not in _SLUG_STOPWORDS
    ]
    if not words:
        words = [
            w
            for w in re.findall(r"[a-z0-9]+", fallback.lower())
            if len(w) >= 3 and w not in _SLUG_STOPWORDS
        ]
    return "-".join(words[:4]) or fallback


def classify_knowledge(
    task: str,
    changed_files: list[str],
    test_results: str,
    root: Path | None = None,
) -> dict[str, Any]:
    """Deterministically map task summary + changed files + test results to
    candidate knowledge/docs file paths (or NO_CHANGES).

    Pure rule-based classifier: keyword signals from the task/test results and
    path-prefix signals from the changed files. The LLM never decides the
    target file; this helper returns the candidate paths and the agent updates
    only those files (or reports NO_CHANGES).
    """
    root = root or REPO_ROOT
    blob = f"{task} {test_results}".lower()
    changed_slugs = [Path(p.replace("\\", "/")).stem for p in changed_files]
    slug = _slug(task, _slug(" ".join(changed_slugs)) or "topic")
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(category: str, target: str, signal: str) -> None:
        if target in seen:
            return
        seen.add(target)
        candidates.append(
            {
                "category": category,
                "file": target,
                "signal": signal,
                "exists": (root / target).exists(),
            }
        )

    # 1. Task/test-result keyword signals → knowledge categories.
    for category, keywords in CATEGORY_KEYWORDS:
        matched = next((kw for kw in keywords if kw in blob), None)
        if matched:
            add(
                category,
                f"knowledge/{category}/{slug}.md",
                f"keyword '{matched}' in task/test results",
            )

    # 2. Test failures imply a known error + a validated-fix candidate.
    if _FAILURE_RE.search(test_results.lower()):
        add("errors", f"knowledge/errors/{slug}.md", "test results contain failures")
        add("fixes", f"knowledge/fixes/{slug}.md", "test failures imply a validated fix candidate")

    # 3. Changed-path signals → docs / implementation candidates.
    for path in changed_files:
        lowered = path.replace("\\", "/").lower()
        stem = Path(lowered).stem
        if lowered.startswith("docs/architecture/"):
            target = (
                "docs/architecture/deployment.md"
                if "deployment" in lowered
                else "docs/architecture/system.md"
            )
            add("docs-architecture", target, f"changed path: {path}")
        elif lowered.startswith("docs/api/"):
            add("docs-api", f"docs/api/{stem}.md", f"changed path: {path}")
        elif lowered.startswith("docs/modules/"):
            add("docs-modules", f"docs/modules/{stem}.md", f"changed path: {path}")
        elif lowered.startswith("docs/workflows/"):
            add("docs-workflows", f"docs/workflows/{stem}.md", f"changed path: {path}")
        elif lowered.startswith("docs/adr/"):
            add("docs-adr", f"docs/adr/{stem}.md", f"changed path: {path} (draft only — propose)")
        elif ".codex/skills/" in lowered or "delivery-contract" in lowered:
            add(
                "contract",
                ".codex/skills/_shared/delivery-contract.md",
                f"changed path: {path} (enforceable automation)",
            )
        elif lowered.startswith(_IMPLEMENTATION_PREFIXES):
            add(
                "implementation",
                f"knowledge/implementation/{slug}.md",
                f"changed path: {path}",
            )

    # 4. Explicit task-area keywords → docs / lessons candidates.
    for pattern, category, signal in _TASK_AREA_RULES:
        if re.search(pattern, task.lower()):
            target = (
                "docs/architecture/system.md"
                if category == "docs-architecture"
                else f"docs/{category[5:]}/{slug}.md"
                if category.startswith("docs-")
                else f"knowledge/{category}/{slug}.md"
            )
            add(category, target, signal)

    if not candidates:
        return {
            "valid": True,
            "noChanges": True,
            "decision": "NO_CHANGES",
            "candidates": [],
            "reason": "No reusable knowledge signals: no error/fix/lesson keywords, no knowledge-mapped changed paths, tests pass.",
        }
    candidates.sort(key=lambda c: (c["file"], c["category"]))
    return {
        "valid": True,
        "noChanges": False,
        "decision": "UPDATE",
        "candidates": candidates,
        "markers": {
            "knowledge": sorted(c["file"] for c in candidates if c["file"].startswith("knowledge/")),
            "docs": sorted(c["file"] for c in candidates if c["file"].startswith("docs/")),
            "contract": sorted(c["file"] for c in candidates if c["category"] == "contract"),
        },
        "summary": ", ".join(c["file"] for c in candidates),
    }


# ── CLI entry point ──────────────────────────────────────────────────────


def run_classify(args: list[str]) -> int:
    """CLI entry point for knowledge-search classify."""
    import json as _json

    options = parse_pairs(args)
    task = options.get("task", "")
    changed_files = [
        p.strip()
        for p in options.get("changed-files", "").split(",")
        if p.strip()
    ]
    test_results = options.get("test-results", "")
    root = Path(options.get("root", REPO_ROOT))
    if not task and not changed_files:
        print(
            "Usage: knowledge-search classify --task <summary> --changed-files <a,b> "
            "--test-results <outcome> [--root PATH]",
            file=sys.stderr,
        )
        return 1
    result = classify_knowledge(task, changed_files, test_results, root)
    print(_json.dumps(result, indent=2))
    return 0


def run_knowledge_search(args: list[str]) -> int:
    """CLI entry point for knowledge-search commands."""
    import json as _json

    if not args:
        print(
            "Usage: knowledge-search search [--query TERM] [--list-topics] [--json] [--root PATH] | "
            "knowledge-search classify --task <summary> --changed-files <a,b> --test-results <outcome>",
            file=sys.stderr,
        )
        return 1
    if args[0] == "classify":
        return run_classify(args[1:])
    if args[0] != "search":
        print(
            f"Unknown knowledge-search subcommand: {args[0]}. Expected 'search' or 'classify'.",
            file=sys.stderr,
        )
        return 1
    options = parse_pairs(args[1:])
    root = Path(options.get("root", REPO_ROOT))
    queries = options.get("query", "").split(",") if options.get("query") else []
    list_topics = options.get("list-topics", "false").lower() == "true"
    as_json = options.get("json", "false").lower() == "true"
    try:
        result = search_knowledge(root, queries, list_topics)
    except CliError as ex:
        print(str(ex), file=sys.stderr)
        return 1
    if as_json or isinstance(result, dict):
        print(_json.dumps(result, indent=2))
    else:
        for row in result:
            print(" | ".join(str(row.get(key, "")) for key in row))
    return 0
