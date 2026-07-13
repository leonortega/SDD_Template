"""Shared helpers and constants for SDD CLI modules."""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON_REQUIRES = (3, 11)
SEARCH_PLAN_ID = "project-guidance-search-plan"
STANDARD_STAGES = [
    "dev-flow-start-ticket",
    "dev-flow-implement-ticket",
    "dev-flow-pr-review-agent",
    "dev-flow-pr-review-feedback-loop",
    "dev-ops-post-merge-deploy",
    "dev-ops-deploy-qa",
]
ALLOWLISTED_LOCAL_CONFIG = [
    ".codex/client-tools.local.json",
    ".codex/project-profile.local.json",
    ".codex/quality.local.json",
    ".codex/tool-recommendations.local.json",
]
RANCHER_PORTS = [
    ("dev", "web", 18081),
    ("dev", "api", 18082),
    ("qa", "web", 18083),
    ("qa", "api", 18084),
    ("prod", "web", 18085),
    ("prod", "api", 18086),
]
DISCOVERY_SOURCE_PRIORITY = [
    "repo-local",
    "openai-official",
    "tool-official",
    "technology-owner",
    "skills-cli",
    "marketplace",
    "community",
]
SDD_TOOL_MANIFEST = ".codex/sdd-tool-version.json"
SDD_TOOL_VERSION_PATTERN = re.compile(r"^v\d+\.\d+\.\d+$")
SDD_TOOL_INCLUDE_FILES = [
    ".dockerignore",
    ".editorconfig",
    ".gitattributes",
    ".gitignore",
    "AGENTS.md",
    "lefthook.yml",
    ".codex/client-tools.example.json",
    ".codex/config.toml",
    ".codex/delivery-policy.json",
    ".codex/memory/MEMORY.md",
    ".codex/memory/memory_summary.md",
    ".codex/memory/retrieval-policy.md",
    ".codex/project-profile.example.json",
    ".codex/project-profile.schema.json",
    ".codex/quality.example.json",
    ".codex/tool-recommendations.example.json",
    "openspec/config.yaml",
]
SDD_TOOL_INCLUDE_DIRS = [
    ".agents",
    ".cline",
    ".codex/providers",
    ".codex/skills",
    ".gitea/workflows",
    "docs",
    "infra",
    "tools",
    "tools/bm25s_flashrank",
    ".vscode",
]
SDD_TOOL_INCLUDE_EMPTY_DIRS = [
    ".clinerules",
]
SDD_TOOL_TOOL_FILES = [
    ".cline/create_skill_links.py",
]
SDD_TOOL_EXCLUDE_PARTS = {
    "__pycache__",
    ".git",
    ".pytest_cache",
    ".codex/agent-evals",
    ".codex/ponytail",
    "openspec/changes",
    "tools/sdd_cli/tests",
}
SDD_TOOL_EXCLUDE_SEGMENTS = {"data", "logs", "pgdata"}
SDD_TOOL_EXCLUDE_SUFFIXES = {".pyc", ".pyo"}
SDD_TOOL_PRESERVE_FILES = {
    ".codex/client-tools.local.json",
    ".codex/environment-urls.local.json",
    ".codex/project-profile.local.json",
    ".codex/quality.local.json",
    ".codex/tool-recommendations.local.json",
    ".codex/memory/MEMORY.md",
    ".codex/memory/memory_summary.md",
    ".codex/memory/retrieval-policy.md",
}
RANCHER_DESKTOP_CONTEXT = "rancher-desktop"


class CliError(RuntimeError):
    pass


Runner = Callable[[list[str], Path | None, dict[str, str] | None], int]


def is_preserved_local_json(relative: str) -> bool:
    """Return True if the relative path is a *.local.json file that should be preserved."""
    return relative.endswith(".local.json")


def default_runner(command: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> int:
    return subprocess.run(command, cwd=cwd, env=env, check=False).returncode


# ── Helpers ──────────────────────────────────────────────────────────────

def fail(message: str) -> Any:
    raise CliError(message)


def require(options: dict[str, str], key: str) -> str:
    value = options.get(key)
    if not value:
        fail(f"Missing required option: --{key}")
    return value


def read_json(path: Path, optional: bool = False) -> dict[str, Any]:
    if optional and not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def nested(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def merge_dicts(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    output = json.loads(json.dumps(left))
    for key, value in right.items():
        if isinstance(value, dict) and isinstance(output.get(key), dict):
            output[key] = merge_dicts(output[key], value)
        else:
            output[key] = value
    return output


def split_list(value: str) -> list[str]:
    return [item for item in re.split(r"[\s,]+", value.strip()) if item]


def trim_remainder(items: list[str]) -> list[str]:
    return items[1:] if items and items[0] == "--" else items


def parse_pairs(items: list[str]) -> dict[str, str]:
    args = trim_remainder(items)
    pairs: dict[str, str] = {}
    index = 0
    while index < len(args):
        key = args[index]
        if not key.startswith("--"):
            fail(f"Expected --option, got: {key}")
        if index + 1 >= len(args):
            fail(f"Missing value for option {key}")
        pairs[key[2:]] = args[index + 1]
        index += 2
    return pairs


def sh_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def format_duration(milliseconds: int) -> str:
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
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def min_text(left: str | None, right: str | None) -> str:
    if not left:
        return right or ""
    if not right:
        return left
    return min(left, right)


def max_text(left: str | None, right: str | None) -> str:
    if not left:
        return right or ""
    if not right:
        return left
    return max(left, right)


def find_meta(body: str, label: str) -> str:
    match = re.search(rf"(?m)^-\s+{re.escape(label)}:\s*(.+)$", body)
    return match.group(1).strip() if match else ""


def any_contains(root: Path, directories: list[str], patterns: list[str], regex: str) -> bool:
    compiled = re.compile(regex, re.IGNORECASE)
    for directory in directories:
        base = root / directory
        if not base.exists():
            continue
        for pattern in patterns:
            for path in base.rglob(pattern):
                try:
                    if compiled.search(path.read_text(encoding="utf-8", errors="ignore")):
                        return True
                except OSError:
                    continue
    return False


def run_native(command: list[str], root: Path, timeout: int = 30) -> dict[str, Any]:
    try:
        command_str = " ".join(f'"{arg}"' if " " in arg else arg for arg in command)
        completed = subprocess.run(
            command_str, cwd=root, check=False, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, env=os.environ, shell=True,
        )
        return {
            "returncode": completed.returncode,
            "stdout": (completed.stdout or "").strip(),
            "stderr": (completed.stderr or "").strip(),
        }
    except FileNotFoundError:
        return {"returncode": 127, "stdout": "", "stderr": f"{command[0]} is missing."}
    except subprocess.TimeoutExpired:
        return {"returncode": 124, "stdout": "", "stderr": f"{command[0]} timed out after {timeout} seconds."}


def http_status(url: str, timeout: int = 5) -> tuple[int | None, str]:
    try:
        parsed = urlparse(url)
        connection_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
        connection = connection_cls(parsed.hostname or "", parsed.port, timeout=timeout)
        path = (parsed.path or "/") + (("?" + parsed.query) if parsed.query else "")
        connection.request("GET", path)
        response = connection.getresponse()
        response.read()
        connection.close()
        return response.status, ""
    except Exception as ex:
        return None, str(ex)


def port_listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.25)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def load_project_profile(root: Path) -> dict[str, Any]:
    base_path = root / ".codex" / "project-profile.json"
    if not base_path.exists():
        base_path = root / ".codex" / "project-profile.example.json"
    base = read_json(base_path, optional=True)
    local = read_json(root / ".codex" / "project-profile.local.json", optional=True)
    return merge_dicts(base, local)


def selected_deployment_provider(root: Path) -> str:
    profile = load_project_profile(root)
    return nested(profile, "providers", "deployment", "id") or "azure-appservice"


def selected_rancher(root: Path) -> bool:
    return selected_deployment_provider(root) == "rancher-desktop"


def rancher_port_mappings() -> list[dict[str, Any]]:
    return [
        {"environment": "dev", "kind": "web", "namespace": "sdd-dev", "service": "web", "localPort": 18081},
        {"environment": "dev", "kind": "api", "namespace": "sdd-dev", "service": "api", "localPort": 18082},
        {"environment": "qa", "kind": "web", "namespace": "sdd-qa", "service": "web", "localPort": 18083},
        {"environment": "qa", "kind": "api", "namespace": "sdd-qa", "service": "api", "localPort": 18084},
        {"environment": "prod", "kind": "web", "namespace": "sdd-prod", "service": "web", "localPort": 18085},
        {"environment": "prod", "kind": "api", "namespace": "sdd-prod", "service": "api", "localPort": 18086},
    ]


def load_tool_recommendations_catalog(root: Path) -> dict[str, Any]:
    base = read_json(root / ".codex" / "tool-recommendations.example.json", optional=True)
    local = read_json(root / ".codex" / "tool-recommendations.local.json", optional=True)
    merged = merge_dicts(
        {key: value for key, value in base.items() if key not in {"recommendations", "notRecommended"}},
        {key: value for key, value in local.items() if key not in {"recommendations", "notRecommended"}},
    )
    merged["recommendations"] = merge_catalog_items(base.get("recommendations", []), local.get("recommendations", []))
    merged["notRecommended"] = merge_catalog_items(base.get("notRecommended", []), local.get("notRecommended", []))
    return {key: value for key, value in merged.items() if value not in ({}, [])}


def merge_catalog_items(base_items: list[dict[str, Any]], local_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    positions: dict[str, int] = {}
    for item in base_items:
        item_id = item.get("id")
        if not item_id:
            continue
        positions[item_id] = len(output)
        output.append(ensure_used_in_steps(item))
    for item in local_items:
        item_id = item.get("id")
        if not item_id:
            continue
        if item_id in positions:
            output[positions[item_id]] = merge_dicts(output[positions[item_id]], ensure_used_in_steps(item))
        else:
            positions[item_id] = len(output)
            output.append(ensure_used_in_steps(item))
    return output


def ensure_used_in_steps(item: dict[str, Any]) -> dict[str, Any]:
    clone = json.loads(json.dumps(item))
    clone.setdefault("usedInSteps", [])
    return clone


# ── Local file helpers ───────────────────────────────────────────────────

def local_path(root: Path, relative: str) -> Path:
    return root / relative.replace("/", os.sep)


def ensure_seed_file(root: Path, relative: str, default_text: str, result: dict[str, Any], dry_run: bool) -> None:
    target = local_path(root, relative)
    if target.exists():
        result["actions"].append({
            "path": relative, "key": "exists", "severity": "info",
            "message": "Template already exists.", "phase": "apply",
        })
        return
    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(default_text, encoding="utf-8")
    result["actions"].append({
        "path": relative, "key": "created", "severity": "info",
        "message": "Created missing local seed file.", "phase": "apply",
    })


def copy_seed_file(root: Path, source_relative: str, target_relative: str, result: dict[str, Any], dry_run: bool) -> None:
    source = local_path(root, source_relative)
    target = local_path(root, target_relative)
    if target.exists():
        result["actions"].append({
            "path": target_relative, "key": "exists", "severity": "info",
            "message": "Local file already exists; preserved.", "phase": "apply",
        })
        return
    if not source.exists():
        add_bucket_item(result["findings"], source_relative, "missing.template",
                        f"Missing template: {source_relative}", "warning", "pre-start")
        return
    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    result["actions"].append({
        "path": target_relative, "key": "created", "severity": "info",
        "message": f"Created from {source_relative}.", "phase": "apply",
    })


def new_configure_result(mode: str, dry_run: bool, write_enabled: bool) -> dict[str, Any]:
    return {
        "mode": mode, "dryRun": dry_run, "writeEnabled": write_enabled,
        "actions": [], "findings": [], "recommendations": [], "warnings": [], "valid": True,
    }


def configure_result(mode: str, dry_run: bool, write_enabled: bool) -> dict[str, Any]:
    return new_configure_result(mode, dry_run, write_enabled)


def add_bucket_item(bucket: list[dict[str, str]], path: str, key: str, message: str, severity: str, phase: str = "post-start") -> None:
    bucket.append({"path": path, "key": key, "severity": severity, "phase": phase, "message": message})


# ── Env file helpers ─────────────────────────────────────────────────────

def read_env_file(path: Path) -> dict[str, str]:
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{key}={value}\n" for key, value in values.items()), encoding="utf-8")


def env_template_keys(root: Path, target_relative: str) -> set[str]:
    example = local_path(root, target_relative + ".example")
    if not example.exists():
        return set()
    return set(read_env_file(example))


def env_template_values(root: Path, target_relative: str) -> dict[str, str]:
    return read_env_file(local_path(root, target_relative + ".example"))


def add_env_drift_findings(root: Path, result: dict[str, Any]) -> None:
    for relative in (
        "infra/openproject/variables.env",
        "infra/monitoring/variables.env",
        "infra/azure/variables.env",
        "infra/gitea/runner.env",
    ):
        template = env_template_values(root, relative)
        if not template:
            continue
        current = read_env_file(local_path(root, relative))
        missing = sorted(set(template) - set(current))
        stale = sorted(set(current) - set(template))
        if missing:
            add_bucket_item(result["findings"], relative, "env.missing-template-keys",
                            f"Missing current template keys: {', '.join(missing[:8])}.", "error")
        if stale:
            add_bucket_item(result["findings"], relative, "env.stale-keys",
                            f"Stale non-template keys present: {', '.join(stale[:8])}."
                            + (f" Plus {len(stale) - 8} more." if len(stale) > 8 else ""), "warning")


def configure_set_env_mode(root: Path, mode: str, target_relative: str, values: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    result = configure_result(mode, dry_run, write_enabled=not dry_run)
    target = local_path(root, target_relative)
    if not target.exists():
        return {"mode": mode, "valid": False, "errors": [f"Missing {target_relative}. Run InitLocalFiles first."]}
    if not values:
        return {"mode": mode, "valid": False, "errors": [
            "Config values are required. Use --values-json-file, --values-json-stdin true, or --values-json.",
        ]}
    allowed = env_template_keys(root, target_relative)
    blocked = sorted(key for key in values if allowed and key not in allowed)
    if blocked:
        return {"mode": mode, "valid": False, "errors": [f"Unsupported env key(s) for {target_relative}: {', '.join(blocked)}"]}
    current = read_env_file(target)
    for key, value in values.items():
        current[str(key)] = str(value)
        result["actions"].append({
            "path": target_relative, "key": str(key), "severity": "info",
            "message": "Set confirmed value.", "phase": "apply",
        })
    if not dry_run:
        write_env_file(target, current)
    result["valid"] = True
    return result


# ── Git helpers ──────────────────────────────────────────────────────────

def git_text(root: Path, args: list[str]) -> str:
    try:
        result = subprocess.run(["git", *args], cwd=root, check=False, capture_output=True, text=True)
    except OSError:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def check_git_ignored(root: Path, path: str) -> bool:
    completed = subprocess.run(
        ["git", "check-ignore", path], cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    return completed.returncode == 0


def remove_empty_parents(path: Path, stop: Path) -> None:
    path = path.resolve()
    stop = stop.resolve()
    while path != stop and str(path).startswith(str(stop)):
        try:
            path.rmdir()
        except OSError:
            return
        path = path.parent