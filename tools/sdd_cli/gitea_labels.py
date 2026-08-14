"""Manage Gitea PR labels deterministically — the mechanism behind the review-label
steps in `dev-flow-pr-review-agent` and `dev-flow-pr-review-feedback-loop`.

The bug being fixed: repeated review loops re-applied labels without checking the
PR's current state, and repo-level label DEFINITIONS with the same name
accumulated multiple ids (each run re-created the label). Gitea enforces one
assignment per label id, but NOT one per label name — so a PR could end up with
`agent-reviewed` twice (two label ids with the same name, each assigned
separately). Observed: same labels defined 3x at repo level and 3x on one PR.

This module makes label state a single idempotent CLI command (`gitea labels`):

1. Reads the Gitea connection from `.template/client-tools.local.json`
   (`gitea.baseUrl`, `gitea.apiToken`, `gitea.owner`, `gitea.repo`).
2. Lists repo label DEFINITIONS and dedupes them by name — keeps the first
   (lowest-id) definition per name and deletes the extra definitions, so a name
   always resolves to exactly one canonical label id.
3. Lists the PR's current labels and diffs against the requested state — labels
   already present (or already absent) are left untouched (idempotent no-op).
4. Applies/removes only the delta, always by the canonical label id, then
   re-fetches to verify (retries once on verification mismatch).

Usage:

    gitea labels --pr 2 --add agent-reviewed --remove needs-tests,needs-changes
    gitea labels --pr 2 --add agent-reviewed --dry-run true
    gitea labels --pr 2 --remove agent-reviewed

Multiple names are comma/whitespace separated (`split_list`). A name is only
added if missing and only removed if present — every run is idempotent.
"""

from __future__ import annotations

import http.client
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ._shared import REPO_ROOT, parse_pairs, split_list
from .gitea_reviewers import _load_gitea_config

# Deterministic colors (mirror dev-flow-pr-review-agent §4). Hex without '#'.
_DEFAULT_COLORS: dict[str, str] = {
    "agent-reviewed": "5319e7",
    "needs-tests": "fbca04",
    "needs-changes": "d73a4a",
}
_FALLBACK_COLOR = "0e8a16"  # deterministic green for any other label name


def _name_key(name: Any) -> str:
    """Case-insensitive label-name key (Gitea label names are unique by name)."""
    return str(name or "").strip().lower()


def _api(
    gitea: dict[str, Any],
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
) -> tuple[int | None, Any, str | None]:
    """One HTTP round trip against the Gitea API.

    Returns (status, parsed_json_or_raw_text_or_None, error_or_None). Errors must
    fail loudly (network/permission problems are real gates, not skips).
    """
    base_url = str(gitea.get("baseUrl", "")).rstrip("/")
    token = str(gitea.get("apiToken", ""))
    owner, repo = gitea.get("owner"), gitea.get("repo")
    if not base_url or not owner or not repo:
        return None, None, "Gitea baseUrl, owner, and repo are required in client-tools.local.json."
    parsed = urlparse(base_url)
    try:
        headers = {"Authorization": f"token {token}"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        conn = http.client.HTTPConnection(
            parsed.hostname or "localhost", parsed.port or 3000, timeout=15
        )
        conn.request(
            method,
            path,
            body=json.dumps(body) if body is not None else None,
            headers=headers,
        )
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8", "replace")
        conn.close()
        data: Any = None
        if raw:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                data = raw
        return resp.status, data, None
    except Exception as ex:  # network errors must fail loudly, not skip the gate
        return None, None, f"{method} {path} failed: {ex}"


def _repo_labels_path(gitea: dict[str, Any]) -> str:
    return f"/api/v1/repos/{gitea['owner']}/{gitea['repo']}/labels"


def _issue_labels_path(gitea: dict[str, Any], pr_number: str) -> str:
    return f"/api/v1/repos/{gitea['owner']}/{gitea['repo']}/issues/{pr_number}/labels"


def _fetch_repo_label_ids(gitea: dict[str, Any]) -> tuple[dict[str, int], str | None]:
    """GET repo label definitions → {name_key: canonical_id} (first id per name).

    Duplicate definitions with the same name are NOT deduped here; callers use
    `dedupe_label_definitions` to delete the extras first.
    """
    status, data, err = _api(gitea, "GET", _repo_labels_path(gitea))
    if err or status != 200:
        return {}, f"GET repo labels failed (HTTP {status}): {err}"
    by_name: dict[str, int] = {}
    for label in data or []:
        if not isinstance(label, dict) or not label.get("id"):
            continue
        key = _name_key(label.get("name"))
        if key and key not in by_name:
            by_name[key] = int(label["id"])
    return by_name, None


def _fetch_issue_label_ids(gitea: dict[str, Any], pr_number: str) -> tuple[dict[str, int], str | None]:
    """GET the PR's current labels → {name_key: label_id}."""
    status, data, err = _api(gitea, "GET", _issue_labels_path(gitea, pr_number))
    if err or status != 200:
        return {}, f"GET PR #{pr_number} labels failed (HTTP {status}): {err}"
    current: dict[str, int] = {}
    for label in data or []:
        if not isinstance(label, dict) or not label.get("id"):
            continue
        key = _name_key(label.get("name"))
        if key:
            current[key] = int(label["id"])
    return current, None


def _dedupe_label_definitions(
    gitea: dict[str, Any], findings: list[dict[str, Any]]
) -> None:
    """Delete duplicate repo label DEFINITIONS (same name, multiple ids).

    Keeps the lowest id per name so every future apply resolves the same
    canonical id — the root cause of `agent-reviewed` appearing twice on one PR.
    """
    status, data, err = _api(gitea, "GET", _repo_labels_path(gitea))
    if err or status != 200:
        findings.append(
            {
                "key": "gitea.labels.dedupe",
                "severity": "warning",
                "message": f"Could not list repo labels for dedupe (HTTP {status}): {err}",
            }
        )
        return
    by_name: dict[str, list[dict[str, Any]]] = {}
    for label in data or []:
        if not isinstance(label, dict) or not label.get("id"):
            continue
        by_name.setdefault(_name_key(label.get("name")), []).append(label)
    for key, labels in by_name.items():
        if len(labels) < 2:
            continue
        ordered = sorted(labels, key=lambda l: int(l["id"]))
        keep, extras = ordered[0], ordered[1:]
        for extra in extras:
            status, _, err = _api(
                gitea, "DELETE", f"{_repo_labels_path(gitea)}/{extra['id']}"
            )
            if status in (204, 200):
                findings.append(
                    {
                        "key": "gitea.labels.dedupe",
                        "severity": "warning",
                        "message": (
                            f"Deleted duplicate repo label definition "
                            f"'{keep.get('name')}' id {extra['id']}; kept id {keep['id']}."
                        ),
                    }
                )
            else:
                findings.append(
                    {
                        "key": "gitea.labels.dedupe",
                        "severity": "warning",
                        "message": (
                            f"Could not delete duplicate label definition "
                            f"'{keep.get('name')}' id {extra['id']} (HTTP {status}): {err}"
                        ),
                    }
                )


def _ensure_label_definition(
    gitea: dict[str, Any],
    name: str,
    repo_ids: dict[str, int],
    steps: list[dict[str, Any]],
    findings: list[dict[str, Any]],
) -> int | None:
    """Return the canonical label id for `name`, creating the definition if missing."""
    key = _name_key(name)
    if key in repo_ids:
        return repo_ids[key]
    color = _DEFAULT_COLORS.get(name, _FALLBACK_COLOR)
    status, data, err = _api(
        gitea,
        "POST",
        _repo_labels_path(gitea),
        {
            "name": name,
            "color": color,
            "description": f"Auto-managed by gitea labels ({name}).",
        },
    )
    if err or status not in (200, 201, 204):
        msg = f"Could not create repo label '{name}' (HTTP {status}): {err or data}"
        findings.append({"key": "gitea.labels.create", "severity": "error", "message": msg})
        steps.append({"command": "gitea/labels", "message": msg, "valid": False})
        return None
    new_id = None
    if isinstance(data, dict) and data.get("id"):
        new_id = int(data["id"])
    if new_id is None:
        # POST may not echo the label; re-fetch to resolve the id.
        ids, fetch_err = _fetch_repo_label_ids(gitea)
        if fetch_err or key not in ids:
            msg = f"Label '{name}' created but id could not be resolved: {fetch_err}"
            findings.append({"key": "gitea.labels.create", "severity": "error", "message": msg})
            steps.append({"command": "gitea/labels", "message": msg, "valid": False})
            return None
        new_id = ids[key]
    repo_ids[key] = new_id
    steps.append(
        {
            "command": "gitea/labels",
            "message": f"Created repo label '{name}' (#{color}, id {new_id}).",
            "valid": True,
        }
    )
    return new_id


def _apply_label(
    gitea: dict[str, Any], pr_number: str, label_id: int
) -> tuple[bool, str]:
    """POST the label id onto the PR and verify presence; retries once."""
    path = _issue_labels_path(gitea, pr_number)
    last = "no attempt"
    for attempt in (1, 2):
        status, data, err = _api(gitea, "POST", path, {"labels": [label_id]})
        if err or status not in (200, 201, 204):
            last = f"POST failed (HTTP {status}): {err or data}"
            continue
        status, data, err = _api(gitea, "GET", path)
        if err or status != 200:
            last = f"verify GET failed: {err}"
            continue
        present = [
            l for l in (data or [])
            if isinstance(l, dict) and int(l.get("id") or 0) == label_id
        ]
        if present:
            return True, f"verified present (label id {label_id})"
        last = f"not verified after POST (attempt {attempt})"
    return False, last


def _remove_label(
    gitea: dict[str, Any], pr_number: str, label_id: int
) -> tuple[bool, str]:
    """DELETE the label id from the PR and verify absence; retries once."""
    path = f"{_issue_labels_path(gitea, pr_number)}/{label_id}"
    last = "no attempt"
    for attempt in (1, 2):
        status, data, err = _api(gitea, "DELETE", path)
        if err or status not in (204, 200):
            last = f"DELETE failed (HTTP {status}): {err or data}"
            continue
        status, data, err = _api(gitea, "GET", _issue_labels_path(gitea, pr_number))
        if err or status != 200:
            last = f"verify GET failed: {err}"
            continue
        absent = not any(
            isinstance(l, dict) and int(l.get("id") or 0) == label_id
            for l in (data or [])
        )
        if absent:
            return True, f"verified absent (label id {label_id})"
        last = f"still present after DELETE (attempt {attempt})"
    return False, last


def apply_labels(
    root: Path,
    pr_number: str,
    add: list[str] | None = None,
    remove: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Idempotently reconcile PR labels. Returns a report dict.

    Every label name is a no-op when already in (or already out of) the
    requested state; repo label definitions are deduped so a name always maps to
    one canonical id.
    """
    result: dict[str, Any] = {
        "mode": "GiteaLabels",
        "dryRun": dry_run,
        "valid": False,
        "prNumber": pr_number,
        "steps": [],
        "findings": [],
    }
    add = [n.strip() for n in (add or []) if n.strip()]
    remove = [n.strip() for n in (remove or []) if n.strip()]

    gitea, cfg_err = _load_gitea_config(root)
    if cfg_err:
        result["findings"].append({"key": "gitea.apiToken", "severity": "error", "message": cfg_err})
        result["steps"].append({"command": "gitea/labels", "message": cfg_err, "valid": False})
        return result
    owner, repo = gitea.get("owner"), gitea.get("repo")
    if not owner or not repo or "replace-with" in str(owner) or "replace-with" in str(repo):
        err = "Gitea owner/repo are placeholders in client-tools.local.json — set them first."
        result["findings"].append({"key": "gitea.ownerRepo", "severity": "error", "message": err})
        result["steps"].append({"command": "gitea/labels", "message": err, "valid": False})
        return result

    if dry_run:
        result["valid"] = True
        for name in add:
            result["steps"].append(
                {
                    "command": "gitea/labels",
                    "message": (
                        f"Would ensure label '{name}' on PR #{pr_number} "
                        "(create definition if missing, apply by canonical id)."
                    ),
                    "valid": True,
                }
            )
        for name in remove:
            result["steps"].append(
                {
                    "command": "gitea/labels",
                    "message": (
                        f"Would remove label '{name}' from PR #{pr_number} if present."
                    ),
                    "valid": True,
                }
            )
        return result

    # 1. Dedupe repo label definitions (root cause of duplicate-name labels).
    _dedupe_label_definitions(gitea, result["findings"])
    repo_ids, repo_err = _fetch_repo_label_ids(gitea)
    if repo_err:
        result["findings"].append({"key": "gitea.labels.list", "severity": "error", "message": repo_err})
        result["steps"].append({"command": "gitea/labels", "message": repo_err, "valid": False})
        return result

    # 2. Current PR labels (diff target).
    current, issue_err = _fetch_issue_label_ids(gitea, pr_number)
    if issue_err:
        result["findings"].append({"key": "gitea.labels.list", "severity": "error", "message": issue_err})
        result["steps"].append({"command": "gitea/labels", "message": issue_err, "valid": False})
        return result

    # 3. Adds — only labels not already present.
    for name in add:
        key = _name_key(name)
        if key in current:
            result["steps"].append(
                {
                    "command": "gitea/labels",
                    "message": f"Label '{name}' already on PR #{pr_number} (id {current[key]}) — no change.",
                    "valid": True,
                }
            )
            continue
        label_id = _ensure_label_definition(gitea, name, repo_ids, result["steps"], result["findings"])
        if label_id is None:
            continue
        ok, detail = _apply_label(gitea, pr_number, label_id)
        if ok:
            current[key] = label_id
            result["steps"].append(
                {
                    "command": "gitea/labels",
                    "message": f"Applied '{name}' to PR #{pr_number}; {detail}.",
                    "valid": True,
                }
            )
        else:
            msg = f"Could not apply '{name}' to PR #{pr_number}: {detail}."
            result["findings"].append({"key": "gitea.labels.apply", "severity": "error", "message": msg})
            result["steps"].append({"command": "gitea/labels", "message": msg, "valid": False})

    # 4. Removes — only labels already present.
    for name in remove:
        key = _name_key(name)
        if key not in current:
            result["steps"].append(
                {
                    "command": "gitea/labels",
                    "message": f"Label '{name}' not on PR #{pr_number} — no change.",
                    "valid": True,
                }
            )
            continue
        label_id = current[key]
        ok, detail = _remove_label(gitea, pr_number, label_id)
        if ok:
            current.pop(key, None)
            result["steps"].append(
                {
                    "command": "gitea/labels",
                    "message": f"Removed '{name}' from PR #{pr_number}; {detail}.",
                    "valid": True,
                }
            )
        else:
            msg = f"Could not remove '{name}' from PR #{pr_number}: {detail}."
            result["findings"].append({"key": "gitea.labels.remove", "severity": "error", "message": msg})
            result["steps"].append({"command": "gitea/labels", "message": msg, "valid": False})

    result["valid"] = not any(
        s.get("valid") is False for s in result["steps"]
    )
    return result


def print_result(result: dict[str, Any], dry_run: bool) -> None:
    """Print the labels summary (shared by CLI entry points)."""
    status = "OK" if result.get("valid") else "FAILED"
    print(f"Gitea labels: {status}" + (" (dry-run)" if dry_run else ""))
    for step in result.get("steps", []):
        flag = "OK" if step.get("valid") else "FAIL"
        print(f"  [{flag}] {step.get('message')}")
    for finding in result.get("findings", []):
        print(f"  [note] {finding.get('message')}")


def labels_cli(args: list[str]) -> int:
    """CLI entry point: gitea labels --pr 2 --add a,b [--remove c] [--dry-run true] [--root PATH]"""
    # args[0] is the subcommand name (e.g. "labels"); skip it so parse_pairs only
    # sees --key value pairs (same pattern as request-reviewers).
    options = parse_pairs(args[1:])
    pr_number = options.get("pr") or options.get("pr-number")
    if not pr_number:
        print("labels: --pr <number> is required (e.g. --pr 2).")
        return 2
    root = Path(options.get("root", REPO_ROOT))
    dry_run = options.get("dry-run", "false").lower() in ("true", "1", "yes")
    add = split_list(options.get("add", ""))
    remove = split_list(options.get("remove", ""))
    if not add and not remove:
        print("labels: at least one of --add <names> or --remove <names> is required.")
        return 2
    result = apply_labels(root, pr_number, add=add, remove=remove, dry_run=dry_run)
    print_result(result, dry_run)
    return 0 if result.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(labels_cli(sys.argv[1:]))
