"""Shared helpers and constants for SDD CLI modules."""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, NoReturn
from urllib.parse import urlparse

# ── Core constants ───────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parents[2]
# Single Python floor: the CLI gate (cli.py), prereqs, and full_setup all
# require 3.11+ — keep one constant in sync (was (3, 14), which wrongly
# rejected 3.11-3.13 runtimes and contradicted the CLI message).
PYTHON_REQUIRES = (3, 11)

STANDARD_STAGES = [
    "dev-flow-start-ticket",
    "dev-flow-propose-change",
    "dev-flow-implement-ticket",
    "dev-flow-verify-change",
    "dev-flow-pr-review-agent",
    "dev-flow-pr-review-feedback-loop",
    "dev-ops-post-merge-deploy",
    "dev-ops-deploy-qa",
    "qa-gate",
    "dev-flow-archive-change",
    "dev-flow-file-qa-bug",
    "dev-ops-deploy-prod",
    "dev-ops-rollback-prod",
    "dev-ops-hotfix-prod",
    # dev-flow-continue-implementation is intentionally NOT listed: it is a resume
    # router that records a telemetry row only when it performs meaningful routing
    # work, so it is not part of the standard linear flow the timing table renders.
]
# ── Generic JSON cache (lazy-loading helper) ──────────────────────────

_JSON_CACHE: dict[str, dict[str, Any]] = {}


def _load_json_cache(path: Path) -> dict[str, Any]:
    """Load a JSON file, caching by its resolved string path."""
    key = str(path.resolve())
    if key not in _JSON_CACHE:
        _JSON_CACHE[key] = json.loads(path.read_text(encoding="utf-8"))
    return _JSON_CACHE[key]


# ── Misc constants (lazy-loaded from JSON) ─────────────────────────────

_MISC_DATA_PATH = Path(__file__).parent / "misc-data.json"


def get_high_risk_patterns() -> list[str]:
    return list(_load_json_cache(_MISC_DATA_PATH)["HIGH_RISK_PATTERNS"])


def get_allowlisted_local_config() -> list[str]:
    return list(_load_json_cache(_MISC_DATA_PATH)["ALLOWLISTED_LOCAL_CONFIG"])


# ── SDD tool manifest constants (lazy-loaded from JSON) ────────────────

_SDD_TOOL_DATA_PATH = Path(__file__).parent / "sdd-tool-data.json"


def get_sdd_tool_manifest() -> str:
    return str(_load_json_cache(_SDD_TOOL_DATA_PATH)["SDD_TOOL_MANIFEST"])


def get_sdd_tool_include_dirs() -> list[str]:
    return list(_load_json_cache(_SDD_TOOL_DATA_PATH)["SDD_TOOL_INCLUDE_DIRS"])


def get_sdd_tool_include_empty_dirs() -> list[str]:
    return list(_load_json_cache(_SDD_TOOL_DATA_PATH)["SDD_TOOL_INCLUDE_EMPTY_DIRS"])


def get_sdd_tool_tool_files() -> list[str]:
    return list(_load_json_cache(_SDD_TOOL_DATA_PATH)["SDD_TOOL_TOOL_FILES"])


def get_sdd_tool_exclude_parts() -> set[str]:
    return set(_load_json_cache(_SDD_TOOL_DATA_PATH)["SDD_TOOL_EXCLUDE_PARTS"])


def get_sdd_tool_exclude_segments() -> set[str]:
    return set(_load_json_cache(_SDD_TOOL_DATA_PATH)["SDD_TOOL_EXCLUDE_SEGMENTS"])


def get_sdd_tool_exclude_suffixes() -> set[str]:
    return set(_load_json_cache(_SDD_TOOL_DATA_PATH)["SDD_TOOL_EXCLUDE_SUFFIXES"])


def get_sdd_tool_preserve_files() -> set[str]:
    return set(_load_json_cache(_SDD_TOOL_DATA_PATH)["SDD_TOOL_PRESERVE_FILES"])


def get_sdd_tool_preserve_example_files() -> set[str]:
    return set(_load_json_cache(_SDD_TOOL_DATA_PATH)["SDD_TOOL_PRESERVE_EXAMPLE_FILES"])


# ── Error / runner types ────────────────────────────────────────────────


class CliError(RuntimeError):
    pass


Runner = Callable[[list[str], Path | None, dict[str, str] | None], int]


# ── SDD tool helpers ─────────────────────────────────────────────────────


_GIT_IGNORED_CACHE: dict[str, set[str]] = {}


def _git_ignored_untracked(source: Path) -> set[str]:
    """Return gitignored-and-untracked relative paths (posix) under source.

    The template's `.gitignore` is treated as an extra blacklist: local-only
    files (secrets, runtime DB state, generated artifacts) are never installed.
    Tracked files — even ones matching an ignore rule — and untracked files
    that are not ignored are deliberately kept, so the walk stays
    exclusion-based (blacklist), not a git whitelist.

    The blacklist only activates when ``source`` is the root of a git
    worktree (path alignment requires repo-root-relative paths); otherwise
    an empty set is returned and the rule exclusions still apply.
    """
    key = str(source.resolve())
    if key in _GIT_IGNORED_CACHE:
        return _GIT_IGNORED_CACHE[key]
    result: set[str] = set()
    top = run_native(["git", "rev-parse", "--show-toplevel"], source, timeout=30)
    if top["returncode"] == 0 and top["stdout"]:
        toplevel = Path(top["stdout"].strip()).resolve()
        if toplevel == source.resolve():
            listed = run_native(
                ["git", "ls-files", "--others", "--exclude-standard", "--ignored"],
                toplevel,
                timeout=60,
            )
            if listed["returncode"] == 0:
                result = {line for line in listed["stdout"].splitlines() if line}
    _GIT_IGNORED_CACHE[key] = result
    return result


def walk_sdd_source_files(source: Path) -> list[str]:
    """Walk source directory using os.scandir, skipping excluded directories
    entirely during traversal instead of walking them and filtering after.

    Exclusion stays blacklist-based: rule exclusions (parts, segments,
    suffixes) plus gitignored-and-untracked local files are skipped, while
    every tracked file and untracked-but-not-ignored file is included.

    Returns sorted list of relative posix paths for all non-excluded files.
    """
    files: list[str] = []
    exclude_parts = get_sdd_tool_exclude_parts()
    exclude_segments = get_sdd_tool_exclude_segments()
    exclude_suffixes = get_sdd_tool_exclude_suffixes()
    ignored_untracked = _git_ignored_untracked(source)

    stack: list[tuple[Path, str]] = [(source, "")]
    while stack:
        dir_path, rel_prefix = stack.pop()
        try:
            with os.scandir(str(dir_path)) as entries:
                for entry in entries:
                    entry_rel = (
                        f"{rel_prefix}/{entry.name}" if rel_prefix else entry.name
                    )

                    # Check exclusion BEFORE recursing into subdirectories
                    excluded = False
                    for part in exclude_parts:
                        if entry_rel.startswith(part) or f"/{part}/" in f"/{entry_rel}/":
                            excluded = True
                            break
                    if excluded:
                        continue

                    if entry.is_dir(follow_symlinks=False):
                        stack.append((Path(entry.path), entry_rel))
                    elif entry.is_file():
                        # Exclude by segment
                        excluded = False
                        for segment in exclude_segments:
                            if (
                                f"/{segment}/" in f"/{entry_rel}/"
                                or entry_rel == segment
                            ):
                                excluded = True
                                break
                        if excluded:
                            continue
                        # Exclude by suffix
                        if any(
                            entry_rel.endswith(suffix) for suffix in exclude_suffixes
                        ):
                            continue
                        # Exclude gitignored-and-untracked local files
                        if entry_rel in ignored_untracked:
                            continue
                        files.append(entry_rel)
        except PermissionError:
            continue
    return sorted(files)


def sdd_tool_files(source: Path) -> list[str]:
    """List all managed files in the SDD tool source.

    Uses walk_sdd_source_files for efficient directory traversal that
    skips excluded directories (e.g. node_modules, .git) entirely.
    """
    files = walk_sdd_source_files(source)
    # Skip only the root README.md; subdirectory README files are managed.
    return [f for f in files if f != "README.md"]


def sdd_tool_checksum(root: Path, files: list[str]) -> str:
    """Compute SHA-256 checksum of managed files."""
    sha = hashlib.sha256()
    for relative in sorted(files):
        path = root / relative
        if path.exists():
            sha.update(path.read_bytes())
    return sha.hexdigest()


def is_preserved_local_json(relative: str) -> bool:
    """Return True if the relative path is a *.local.json file that should be preserved."""
    return relative.endswith(".local.json")


# ── General helpers ──────────────────────────────────────────────────────


def fail(message: str) -> NoReturn:
    """Raise CliError with the given message."""
    raise CliError(message)


def require(options: dict[str, str], key: str) -> str:
    """Get a required option, raising CliError if missing."""
    value = options.get(key)
    if not value:
        fail(f"Missing required option: --{key}")
    return value


def read_json(path: Path, optional: bool = False) -> dict[str, Any]:
    """Read a JSON file, returning {} if optional and file does not exist."""
    if optional and not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    """Write a JSON file with pretty-printing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def nested(data: dict[str, Any], *keys: str) -> Any:
    """Safely traverse nested dict keys, returning None for missing keys."""
    current: Any = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def merge_dicts(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge two dicts (right takes priority for non-dict values)."""
    output = json.loads(json.dumps(left))
    for key, value in right.items():
        if isinstance(value, dict) and isinstance(output.get(key), dict):
            output[key] = merge_dicts(output[key], value)
        else:
            output[key] = value
    return output


def split_list(value: str) -> list[str]:
    """Split a comma/whitespace-separated string into a list of items."""
    return [item for item in re.split(r"[\s,]+", value.strip()) if item]


def trim_remainder(items: list[str]) -> list[str]:
    """Strip a leading '--' separator from a list if present."""
    return items[1:] if items and items[0] == "--" else items


def parse_pairs(items: list[str]) -> dict[str, str]:
    """Parse CLI --key value pairs from a list; boolean flags get value 'true'."""
    args = trim_remainder(items)
    pairs: dict[str, str] = {}
    index = 0
    while index < len(args):
        key = args[index]
        if not key.startswith("--"):
            fail(f"Expected --option, got: {key}")
        # Boolean flag: next arg is missing or starts with --
        if index + 1 >= len(args) or args[index + 1].startswith("--"):
            pairs[key[2:]] = "true"
            index += 1
        else:
            pairs[key[2:]] = args[index + 1]
            index += 2
    return pairs


def format_duration(milliseconds: int) -> str:
    """Format milliseconds as a human-readable duration string."""
    if milliseconds <= 0:
        return "no time"
    total_seconds = milliseconds // 1000
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {seconds:02d}s"
    if minutes:
        seconds_text = "00" if seconds == 0 else str(seconds)
        return f"{minutes}m {seconds_text}s"
    return f"{seconds}s"


def parse_time(value: str | None) -> datetime | None:
    """Parse an ISO 8601 datetime string, returning None if empty."""
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def min_text(left: str | None, right: str | None) -> str:
    """Return the lexicographically smaller of two strings, treating None as ""."""
    if not left:
        return right or ""
    if not right:
        return left
    return min(left, right)


def max_text(left: str | None, right: str | None) -> str:
    """Return the lexicographically larger of two strings, treating None as ""."""
    if not left:
        return right or ""
    if not right:
        return left
    return max(left, right)


def find_meta(body: str, label: str) -> str:
    """Extract a metadata value by label from markdown-style - Key: Value lines."""
    match = re.search(rf"(?m)^-\s+{re.escape(label)}:\s*(.+)$", body)
    return (match.group(1) or "").strip() if match else ""


def native_command(name: str) -> list[str]:
    """Return the invocation Python subprocess can start on this platform.

    With ``shell=False`` on Windows, CreateProcess does not resolve
    ``.cmd``/``.bat`` files via PATHEXT: a bare ``npm`` or ``npx`` raises
    FileNotFoundError even when the tool is on PATH. Always use the explicit
    ``.cmd`` name there; non-Windows shells resolve the bare name fine.
    """
    return [f"{name}.cmd"] if sys.platform == "win32" else [name]


def run_native(command: list[str], root: Path, timeout: int = 30) -> dict[str, Any]:
    """Run a native shell command and return structured output."""
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=os.environ,
            shell=False,
        )
        return {
            "returncode": completed.returncode,
            "stdout": (completed.stdout or "").strip(),
            "stderr": (completed.stderr or "").strip(),
        }
    except FileNotFoundError:
        return {"returncode": 127, "stdout": "", "stderr": f"{command[0]} is missing."}
    except subprocess.TimeoutExpired:
        return {
            "returncode": 124,
            "stdout": "",
            "stderr": f"{command[0]} timed out after {timeout} seconds.",
        }


def http_status(url: str, timeout: int = 5) -> tuple[int | None, str]:
    """Check HTTP status of a URL, returning (status_code, error_message)."""
    try:
        parsed = urlparse(url)
        connection_cls = (
            http.client.HTTPSConnection
            if parsed.scheme == "https"
            else http.client.HTTPConnection
        )
        connection = connection_cls(parsed.hostname or "", parsed.port, timeout=timeout)
        path = (parsed.path or "/") + (("?" + parsed.query) if parsed.query else "")
        connection.request("GET", path)
        response = connection.getresponse()
        response.read()
        connection.close()
        return response.status, ""
    except Exception as ex:
        return None, str(ex)


def http_json(
    method: str,
    url: str,
    body: dict[str, Any] | None = None,
    basic: tuple[str, str] | None = None,
    bearer: str = "",
    timeout: int = 10,
) -> tuple[int, str]:
    """Perform an HTTP request with optional JSON body and auth.

    Returns ``(status_code, response_body)``; failures (connection, timeout,
    TLS, invalid URL) return ``(0, str(exc))`` so callers can treat 0 as an
    unreachable/unavailable result without raising.

    ``basic`` is a ``(username, password)`` pair for Basic auth; ``bearer`` is
    a raw token for Bearer auth. When both are provided, ``bearer`` wins.
    """
    try:
        parsed = urlparse(url)
        connection_cls = (
            http.client.HTTPSConnection
            if parsed.scheme == "https"
            else http.client.HTTPConnection
        )
        connection = connection_cls(
            parsed.hostname or "localhost", parsed.port, timeout=timeout
        )
        headers = {"Content-Type": "application/json"}
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"
        elif basic:
            import base64

            encoded = base64.b64encode(f"{basic[0]}:{basic[1]}".encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"
        payload = json.dumps(body) if body is not None else None
        request_path = (parsed.path or "/") + (
            ("?" + parsed.query) if parsed.query else ""
        )
        connection.request(method, request_path, body=payload, headers=headers)
        response = connection.getresponse()
        data = response.read().decode("utf-8")
        connection.close()
        return response.status, data
    except Exception as ex:
        return 0, str(ex)


# ── Quality config helpers ───────────────────────────────────────────────


def quality_coverage_minimum(root: Path, fallback: int = 80) -> int:
    """Read the coverage minimum percent from the quality config chain.

    Checks ``.codex/quality.local.json`` then ``.codex/quality.example.json``
    for ``coverage.minimumPercent``; returns ``fallback`` when unset or
    unparseable. Single source of truth for the coverage gate (stack-tests,
    CI, and audit modes all read the same chain).
    """
    for name in ("quality.local.json", "quality.example.json"):
        path = root / ".codex" / name
        if not path.exists():
            continue
        try:
            value = nested(read_json(path), "coverage", "minimumPercent")
        except (ValueError, OSError):
            continue
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                break
    return fallback


# ── Project profile helpers ──────────────────────────────────────────────


def load_project_profile(root: Path) -> dict[str, Any]:
    """Load the project profile, merging base and local overlays."""
    base_path = root / ".codex" / "project-profile.json"
    if not base_path.exists():
        base_path = root / ".codex" / "project-profile.example.json"
    base = read_json(base_path, optional=True)
    local = read_json(root / ".codex" / "project-profile.local.json", optional=True)
    return merge_dicts(base, local)


def selected_deployment_provider(root: Path) -> str:
    """Return the selected deployment provider ID from the project profile."""
    profile = load_project_profile(root)
    return nested(profile, "providers", "deployment", "id") or "docker-desktop"


def normalize_stack_domain(value: Any) -> dict[str, Any]:
    """Normalize a stack domain value into applies/value dict."""
    if isinstance(value, dict):
        raw = str(value.get("value", ""))
        notes = value.get("notes")
    else:
        raw = "" if value is None else str(value)
        notes = None
    clean = raw.strip()
    applies = clean.lower() not in {"", "none", "no", "n/a", "na", "not applicable"}
    result: dict[str, Any] = {"applies": applies, "value": clean if applies else ""}
    if isinstance(notes, str) and notes.strip():
        result["notes"] = notes.strip()
    return result


def read_ticket_pattern(root: Path) -> str:
    """Read the ticket key pattern from project profile, falling back to delivery-policy.json."""
    profile = load_project_profile(root)
    pattern = nested(profile, "workflow", "ticketKeyPattern")
    if pattern:
        return pattern
    policy = read_json(root / ".codex" / "delivery-policy.json", optional=True)
    return policy.get("ticketKeyPattern", "E2EPROJECT-[0-9]+")


def profile_audit_findings(root: Path) -> list[dict[str, str]]:
    """Audit the project profile and return findings."""
    findings: list[dict[str, str]] = []
    if not (root / ".codex" / "project-profile.json").exists():
        add_bucket_item(
            findings,
            ".codex/project-profile.json",
            "missing.profile",
            "Project profile is missing.",
            "warning",
            "pre-start",
        )
    if not (root / ".codex" / "project-profile.schema.json").exists():
        add_bucket_item(
            findings,
            ".codex/project-profile.schema.json",
            "missing.schema",
            "Project profile schema is missing.",
            "warning",
            "pre-start",
        )
    return findings# ── Local file helpers ───────────────────────────────────────────────────


def local_path(root: Path, relative: str) -> Path:
    """Resolve a relative path against root, normalizing OS path separators."""
    return root / relative.replace("/", os.sep)


def ensure_seed_file(
    root: Path,
    relative: str,
    default_text: str,
    result: dict[str, Any],
    dry_run: bool,
) -> None:
    """Create a seed file from default text if it does not already exist."""
    target = local_path(root, relative)
    if target.exists():
        result["actions"].append(
            {
                "path": relative,
                "key": "exists",
                "severity": "info",
                "message": "Template already exists.",
                "phase": "apply",
            }
        )
        return
    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(default_text, encoding="utf-8")
    result["actions"].append(
        {
            "path": relative,
            "key": "created",
            "severity": "info",
            "message": "Created missing local seed file.",
            "phase": "apply",
        }
    )


def copy_seed_file(
    root: Path,
    source_relative: str,
    target_relative: str,
    result: dict[str, Any],
    dry_run: bool,
) -> None:
    """Copy a seed file from source to target, skipping if target exists."""
    source = local_path(root, source_relative)
    target = local_path(root, target_relative)
    if target.exists():
        result["actions"].append(
            {
                "path": target_relative,
                "key": "exists",
                "severity": "info",
                "message": "Local file already exists; preserved.",
                "phase": "apply",
            }
        )
        return
    if not source.exists():
        add_bucket_item(
            result["findings"],
            source_relative,
            "missing.template",
            f"Missing template: {source_relative}",
            "warning",
            "pre-start",
        )
        return
    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    result["actions"].append(
        {
            "path": target_relative,
            "key": "created",
            "severity": "info",
            "message": f"Created from {source_relative}.",
            "phase": "apply",
        }
    )


def configure_result(mode: str, dry_run: bool, write_enabled: bool) -> dict[str, Any]:
    """Create a fresh empty configure result dict."""
    return {
        "mode": mode,
        "dryRun": dry_run,
        "writeEnabled": write_enabled,
        "actions": [],
        "findings": [],
        "recommendations": [],
        "warnings": [],
        "valid": True,
    }


def add_bucket_item(
    bucket: list[dict[str, str]],
    path: str,
    key: str,
    message: str,
    severity: str,
    phase: str = "post-start",
) -> None:
    """Append a structured finding item to a findings bucket list."""
    bucket.append(
        {
            "path": path,
            "key": key,
            "severity": severity,
            "phase": phase,
            "message": message,
        }
    )


# ── Env file helpers ─────────────────────────────────────────────────────


def read_env_file(path: Path) -> dict[str, str]:
    """Read a .env file into a dict of key-value pairs, skipping comments and blanks."""
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def write_env_file(path: Path, values: dict[str, str]) -> None:
    """Write a dict of key-value pairs as a .env file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(f"{key}={value}\n" for key, value in values.items()), encoding="utf-8"
    )


def env_template_keys(root: Path, target_relative: str) -> set[str]:
    """Return the set of expected env keys from a .env.example template."""
    example = local_path(root, target_relative + ".example")
    if not example.exists():
        return set()
    return set(read_env_file(example))


def env_template_values(root: Path, target_relative: str) -> dict[str, str]:
    """Return the full dict from a .env.example template."""
    return read_env_file(local_path(root, target_relative + ".example"))


def add_env_drift_findings(root: Path, result: dict[str, Any]) -> None:
    """Compare env files against templates and add findings for drift."""
    for relative in (
        "infra/openproject/variables.env",
        "infra/monitoring/variables.env",
        "infra/gitea/runner.env",
    ):
        template = env_template_values(root, relative)
        if not template:
            continue
        current = read_env_file(local_path(root, relative))
        missing = sorted(set(template) - set(current))
        stale = sorted(set(current) - set(template))
        if missing:
            add_bucket_item(
                result["findings"],
                relative,
                "env.missing-template-keys",
                f"Missing current template keys: {', '.join(missing[:8])}.",
                "error",
            )
        if stale:
            stale_msg = f"Stale non-template keys present: {', '.join(stale[:8])}."
            if len(stale) > 8:
                stale_msg += f" Plus {len(stale) - 8} more."
            add_bucket_item(
                result["findings"], relative, "env.stale-keys", stale_msg, "warning"
            )


def client_tools_project_identifier_findings(root: Path) -> list[dict[str, str]]:
    """Warn when client-tools.local.json has no usable OpenProject project identifier.

    The OpenProject MCP/ticket flow calls
    ``GET {baseUrl}/api/v3/projects/{projectIdentifier}``, so a missing or
    placeholder value (``replace-with-project-identifier``) produces confusing
    404s instead of an actionable error. Provisioning (``provision_lab_users``,
    setup-lab step 11) fills both the top-level ``projectIdentifier`` and
    ``openProject.provisioning.project.identifier`` with the real identifier
    (e.g. ``e2eproject``). Returns findings only; never raises on unreadable
    files.
    """
    findings: list[dict[str, str]] = []
    path = root / ".codex" / "client-tools.local.json"
    if not path.exists():
        return findings
    try:
        data = read_json(path, optional=True)
    except Exception:
        return findings
    openproject = data.get("openProject", {}) if isinstance(data, dict) else {}
    if not isinstance(openproject, dict):
        return findings
    identifier = str(openproject.get("projectIdentifier", "") or "").strip()
    if not identifier or identifier.startswith("replace-with"):
        add_bucket_item(
            findings,
            ".codex/client-tools.local.json",
            "openProject.projectIdentifier",
            (
                "openProject.projectIdentifier is missing or still a placeholder "
                "('replace-with-project-identifier'). The OpenProject MCP/ticket "
                "flow calls /api/v3/projects/{projectIdentifier} and will 404. "
                "Run provision_lab_users (setup-lab step 11) to provision the "
                "project (e.g. e2eproject)."
            ),
            "warning",
            "audit",
        )
    return findings


def configure_set_env_mode(
    root: Path,
    mode: str,
    target_relative: str,
    values: dict[str, Any],
    dry_run: bool,
) -> dict[str, Any]:
    """Configure environment variables for a specific service from a mode/values payload."""
    result = configure_result(mode, dry_run, write_enabled=not dry_run)
    target = local_path(root, target_relative)
    if not target.exists():
        return {
            "mode": mode,
            "valid": False,
            "errors": [f"Missing {target_relative}. Run InitLocalFiles first."],
        }
    if not values:
        return {
            "mode": mode,
            "valid": False,
            "errors": [
                "Config values are required. Use --values-json-file, --values-json-stdin true, or --values-json.",
            ],
        }
    allowed = env_template_keys(root, target_relative)
    blocked = sorted(key for key in values if allowed and key not in allowed)
    if blocked:
        return {
            "mode": mode,
            "valid": False,
            "errors": [
                f"Unsupported env key(s) for {target_relative}: {', '.join(blocked)}"
            ],
        }
    current = read_env_file(target)
    for key, value in values.items():
        current[str(key)] = str(value)
        result["actions"].append(
            {
                "path": target_relative,
                "key": str(key),
                "severity": "info",
                "message": "Set confirmed value.",
                "phase": "apply",
            }
        )
    if not dry_run:
        write_env_file(target, current)
    result["valid"] = True
    return result


# ── Git helpers ──────────────────────────────────────────────────────────


def git_text(root: Path, args: list[str]) -> str:
    """Run a git command and return stdout, or '' on failure."""
    try:
        result = subprocess.run(  # nosec
            ["git", *args], cwd=root, check=False, capture_output=True, text=True
        )
    except OSError:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def check_git_ignored(root: Path, path: str) -> bool:
    """Check if a path is git-ignored."""
    completed = subprocess.run(
        ["git", "check-ignore", path],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.returncode == 0


def remove_empty_parents(path: Path, stop: Path) -> None:
    """Remove empty parent directories up to (but not including) stop."""
    path = path.resolve()
    stop = stop.resolve()
    while path != stop and str(path).startswith(str(stop)):
        if path.exists():
            try:
                path.rmdir()
            except OSError:
                return
        path = path.parent


# ── Ticket readiness / delivery risk ─────────────────────────────────────


@dataclass
class TicketReadiness:
    """Result of classifying ticket readiness from title/description."""

    status: str = ""
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)


@dataclass
class DeliveryRisk:
    """Result of classifying delivery risk from paths, context, and changed lines."""

    risk: str = "low"
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)


def classify_ticket_readiness(title: str, description: str) -> TicketReadiness:
    """Classify ticket readiness from title and description.

    Returns 'ready' when acceptance criteria and validation are present.
    """
    has_ac = bool(re.search(r"(?i)acceptance\s*criteria", description))
    has_validation = bool(re.search(r"(?i)validation", description))
    if has_ac and has_validation:
        return TicketReadiness(
            status="ready",
            score=1.0,
            reasons=["Has acceptance criteria and validation."],
        )
    if has_ac or has_validation:
        return TicketReadiness(
            status="needs-work", score=0.5, reasons=["Partial readiness markers found."]
        )
    return TicketReadiness(
        status="not-ready",
        score=0.0,
        reasons=["Missing acceptance criteria and validation."],
    )


def classify_delivery_risk(
    paths: list[str], context: str, changed_lines: int
) -> DeliveryRisk:
    """Classify delivery risk from changed paths, context, and line count.

    Returns 'high' when changed lines > 500 or high-risk paths are touched.
    """
    risk = "low"
    score = 0.0
    reasons: list[str] = []
    for p in paths:
        for pattern in get_high_risk_patterns():
            if pattern in p.lower():
                risk = "moderate" if risk == "low" else risk
                score = max(score, 0.4)
                reasons.append(f"High-risk path pattern '{pattern}' in: {p}")
                break
    if changed_lines > 500:
        risk = "high"
        score = max(score, 0.9)
        reasons.append(f"Large diff: {changed_lines} changed lines.")
    elif changed_lines > 200:
        if risk != "high":
            risk = "moderate"
        score = max(score, 0.5)
        reasons.append(f"Moderate diff: {changed_lines} changed lines.")
    if context and "adversarial" in context.lower():
        risk = "high"
        score = max(score, 0.95)
        reasons.append("Adversarial review context.")
    return DeliveryRisk(risk=risk, score=score, reasons=reasons)
