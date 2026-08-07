"""Request human reviewers on a Gitea pull request — the deterministic
mechanism behind the §11.5 reviewer handoff (AI review first, then human
reviewers).

Previously reviewer assignment was purely skill-orchestrated: every run
re-derived the reviewer list and hand-rolled the REST calls, so a PR could
slip through with no reviewers requested. This module makes the operation a
single CLI command (`gitea request-reviewers`) that:

1. Reads the Gitea connection from `.codex/client-tools.local.json`
   (`gitea.baseUrl`, `gitea.apiToken`, `gitea.owner`, `gitea.repo`).
2. Resolves the reviewer list in priority order:
   - `gitea.reviewers` (explicit list in client-tools) — used as-is after
     trimming empty values;
   - `pr.reviewers` from the project profile — an explicit array is used
     as-is; the value `"all"` lists repository collaborators via the Gitea
     API;
   - fallback: `gitea.provisioning.users` (the provisioned lab users such
     as FirstUser/SecondUser, added as repo collaborators by setup-lab).
3. Excludes the PR author and the authenticated automation user, and
   normalizes collaborator responses (Gitea may return an array or a single
   object; use `login` first, then `username`).
4. POSTs `requested_reviewers`, re-fetches the PR to verify the reviewers
   are present, and retries once on failure.

When no eligible reviewers can be resolved the command fails loudly — the
agent must document the gap (per `_shared/delivery-contract-review.md`)
instead of silently handoff without reviewers.
"""

from __future__ import annotations

import http.client
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ._shared import REPO_ROOT, load_project_profile, nested, parse_pairs, read_json

_PLACEHOLDER_MARKERS = ("replace-with", "changeme", "your-")


def _load_gitea_config(root: Path) -> tuple[dict[str, Any], str | None]:
    """Load the gitea client config; returns (gitea_dict, error_or_None)."""
    client = read_json(root / ".codex" / "client-tools.local.json", optional=True)
    gitea = (client or {}).get("gitea", {}) if client else {}
    token = str(gitea.get("apiToken", "") or "")
    if not token or any(m in token.lower() for m in _PLACEHOLDER_MARKERS):
        return gitea, (
            "Gitea apiToken is missing or a placeholder in "
            ".codex/client-tools.local.json — run setup-lab provisioning first."
        )
    return gitea, None


def _normalize_collaborator(item: Any) -> str:
    """login first, then username (Gitea may return array or single object)."""
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        return str(item.get("login") or item.get("username") or "").strip()
    return ""


def _fetch_collaborators(gitea: dict[str, Any]) -> tuple[list[str], str | None]:
    """GET repo collaborators; returns (logins, error_or_None)."""
    base_url = str(gitea.get("baseUrl", "")).rstrip("/")
    token = str(gitea.get("apiToken", ""))
    owner, repo = gitea.get("owner"), gitea.get("repo")
    if not base_url or not owner or not repo:
        return [], "Gitea baseUrl, owner, and repo are required in client-tools.local.json."
    parsed = urlparse(base_url)
    try:
        conn = http.client.HTTPConnection(parsed.hostname or "localhost", parsed.port or 3000, timeout=15)
        conn.request(
            "GET",
            f"/api/v1/repos/{owner}/{repo}/collaborators",
            headers={"Authorization": f"token {token}"},
        )
        resp = conn.getresponse()
        body = resp.read().decode("utf-8", "replace")
        conn.close()
        if resp.status != 200:
            return [], f"GET collaborators returned HTTP {resp.status}: {body[:200]}"
        data = json.loads(body)
        if isinstance(data, dict):
            data = [data]
        logins = [u for u in (_normalize_collaborator(x) for x in data) if u]
        return logins, None
    except Exception as ex:  # network errors must fail loudly, not skip the gate
        return [], f"Could not list Gitea collaborators: {ex}"


def _fetch_pr_author(gitea: dict[str, Any], pr_number: str) -> tuple[str, str | None]:
    """GET the PR to learn its author (excluded from reviewer assignment)."""
    base_url = str(gitea.get("baseUrl", "")).rstrip("/")
    token = str(gitea.get("apiToken", ""))
    owner, repo = gitea.get("owner"), gitea.get("repo")
    parsed = urlparse(base_url)
    try:
        conn = http.client.HTTPConnection(parsed.hostname or "localhost", parsed.port or 3000, timeout=15)
        conn.request(
            "GET",
            f"/api/v1/repos/{owner}/{repo}/pulls/{pr_number}",
            headers={"Authorization": f"token {token}"},
        )
        resp = conn.getresponse()
        body = resp.read().decode("utf-8", "replace")
        conn.close()
        if resp.status != 200:
            return "", f"GET pull {pr_number} returned HTTP {resp.status}"
        data = json.loads(body)
        author = _normalize_collaborator(data.get("user"))
        return author, None
    except Exception as ex:
        return "", f"Could not fetch PR {pr_number}: {ex}"


def _fetch_requested_reviewers(gitea: dict[str, Any], pr_number: str) -> list[str]:
    """Re-fetch the PR and return its current requested_reviewers."""
    base_url = str(gitea.get("baseUrl", "")).rstrip("/")
    token = str(gitea.get("apiToken", ""))
    owner, repo = gitea.get("owner"), gitea.get("repo")
    parsed = urlparse(base_url)
    try:
        conn = http.client.HTTPConnection(parsed.hostname or "localhost", parsed.port or 3000, timeout=15)
        conn.request(
            "GET",
            f"/api/v1/repos/{owner}/{repo}/pulls/{pr_number}",
            headers={"Authorization": f"token {token}"},
        )
        resp = conn.getresponse()
        body = resp.read().decode("utf-8", "replace")
        conn.close()
        if resp.status != 200:
            return []
        data = json.loads(body)
        requested = data.get("requested_reviewers") or []
        return [u for u in (_normalize_collaborator(x) for x in requested) if u]
    except Exception:
        return []


def resolve_reviewers(
    gitea: dict[str, Any],
    profile: dict[str, Any],
    pr_number: str,
    dry_run: bool,
    findings: list[dict[str, Any]],
) -> list[str]:
    """Resolve the eligible reviewer list in priority order.

    Priority: gitea.reviewers (client-tools) → pr.reviewers (profile; "all"
    expands to repo collaborators) → gitea.provisioning.users. The PR author
    and automation user are always excluded. Never raises; appends findings.
    """
    # 1. Explicit gitea.reviewers in client-tools.local.json
    explicit = gitea.get("reviewers")
    if isinstance(explicit, list) and explicit:
        return [str(u).strip() for u in explicit if str(u).strip()]

    # 2. pr.reviewers from the project profile
    pr_reviewers = nested(profile, "pr", "reviewers")
    if isinstance(pr_reviewers, list) and pr_reviewers:
        return [str(u).strip() for u in pr_reviewers if str(u).strip()]
    if pr_reviewers == "all":
        if dry_run:
            return []  # API calls are skipped in dry-run; report can't resolve
        collaborators, err = _fetch_collaborators(gitea)
        if err:
            findings.append(
                {"key": "gitea.reviewers.resolve", "severity": "warning",
                 "message": f"pr.reviewers=all but collaborators could not be listed: {err}"}
            )
            return []
        author, _ = _fetch_pr_author(gitea, pr_number)
        return [u for u in collaborators if u != author]

    # 3. Fallback: provisioned lab users (repo collaborators by design)
    provisioning_users = (gitea.get("provisioning") or {}).get("users") or []
    if provisioning_users:
        return [str(u.get("username", "")).strip() for u in provisioning_users if str(u.get("username", "")).strip()]

    findings.append(
        {"key": "gitea.reviewers.resolve", "severity": "warning",
         "message": (
            "No reviewers configured: set gitea.reviewers or pr.reviewers, or "
            "provision lab users. Handoff must document the reviewer gap."
        )}
    )
    return []


def request_reviewers(
    root: Path,
    pr_number: str,
    dry_run: bool = False,
    excluded: list[str] | None = None,
) -> dict[str, Any]:
    """Request human reviewers on a Gitea PR. Returns a report dict."""
    result: dict[str, Any] = {
        "mode": "GiteaRequestReviewers",
        "dryRun": dry_run,
        "valid": False,
        "prNumber": pr_number,
        "steps": [],
        "findings": [],
    }
    excluded = excluded or []

    gitea, cfg_err = _load_gitea_config(root)
    if cfg_err:
        result["findings"].append({"key": "gitea.apiToken", "severity": "error", "message": cfg_err})
        result["steps"].append({"command": "gitea/request-reviewers", "message": cfg_err, "valid": False})
        return result

    base_url = str(gitea.get("baseUrl", "")).rstrip("/")
    owner, repo = gitea.get("owner"), gitea.get("repo")
    if not owner or not repo or "replace-with" in str(owner) or "replace-with" in str(repo):
        err = "Gitea owner/repo are placeholders in client-tools.local.json — set them first."
        result["findings"].append({"key": "gitea.ownerRepo", "severity": "error", "message": err})
        result["steps"].append({"command": "gitea/request-reviewers", "message": err, "valid": False})
        return result

    profile = load_project_profile(root)
    # The PR author is excluded uniformly across ALL resolution paths (explicit
    # lists included), not only the pr.reviewers="all" expansion. In dry-run no
    # API call is made and the author is treated as unknown.
    pr_author = "" if dry_run else _fetch_pr_author(gitea, pr_number)[0]
    reviewers = resolve_reviewers(gitea, profile, pr_number, dry_run, result["findings"])
    reviewers = [
        u for u in reviewers
        if u and u not in excluded and u != pr_author
    ]

    if not reviewers:
        if dry_run and pr_author == "":
            result["findings"].append({
                "key": "gitea.reviewers.resolve", "severity": "info",
                "message": (
                    "dry-run: reviewer resolution that requires API calls "
                    "(pr.reviewers=all) cannot be previewed — run without "
                    "--dry-run to resolve."
                ),
            })
        msg = (
            f"No eligible reviewers resolved for PR #{pr_number}. Set gitea.reviewers / "
            "pr.reviewers or provision lab users; document the reviewer gap before handoff."
        )
        result["valid"] = False
        result["steps"].append({"command": "gitea/request-reviewers", "message": msg, "valid": False})
        return result

    payload = {"reviewers": reviewers}
    if dry_run:
        result["valid"] = True
        result["reviewers"] = reviewers
        result["steps"].append({
            "command": "gitea/request-reviewers",
            "message": (
                f"Would request reviewers on PR #{pr_number} via "
                f"POST {base_url}/api/v1/repos/{owner}/{repo}/pulls/{pr_number}/"
                f"requested_reviewers: {reviewers}"
            ),
            "valid": True,
        })
        return result

    # POST requested_reviewers, verify, retry once (Gitea may ignore/race).
    token = str(gitea.get("apiToken", ""))
    parsed = urlparse(base_url)
    last_status = None
    for attempt in (1, 2):
        try:
            conn = http.client.HTTPConnection(parsed.hostname or "localhost", parsed.port or 3000, timeout=15)
            conn.request(
                "POST",
                f"/api/v1/repos/{owner}/{repo}/pulls/{pr_number}/requested_reviewers",
                body=json.dumps(payload),
                headers={
                    "Authorization": f"token {token}",
                    "Content-Type": "application/json",
                },
            )
            resp = conn.getresponse()
            resp.read()
            conn.close()
            last_status = resp.status
        except Exception as ex:
            result["findings"].append(
                {"key": "gitea.request-reviewers", "severity": "error",
                 "message": f"POST requested_reviewers failed (attempt {attempt}): {ex}"}
            )
            last_status = None
            continue

        present = _fetch_requested_reviewers(gitea, pr_number)
        if all(u in present for u in reviewers):
            result["valid"] = True
            result["reviewers"] = reviewers
            result["steps"].append({
                "command": "gitea/request-reviewers",
                "message": f"Reviewers requested on PR #{pr_number}: {reviewers} (verified present).",
                "valid": True,
            })
            return result

    # Both attempts failed (or verification never matched).
    msg = (
        f"Reviewer request on PR #{pr_number} not verified after retry "
        f"(last HTTP status: {last_status}). Document the reviewer gap in the PR body "
        "and ticket handoff comment — do not hand off silently."
    )
    result["valid"] = False
    result["reviewers"] = reviewers
    result["steps"].append({"command": "gitea/request-reviewers", "message": msg, "valid": False})
    return result


def print_result(result: dict[str, Any], dry_run: bool) -> None:
    """Print the request-reviewers summary (shared by CLI entry points)."""
    status = "OK" if result.get("valid") else "FAILED"
    print(f"Gitea request-reviewers: {status}" + (" (dry-run)" if dry_run else ""))
    for step in result.get("steps", []):
        flag = "OK" if step.get("valid") else "FAIL"
        print(f"  [{flag}] {step.get('message')}")
    for finding in result.get("findings", []):
        print(f"  [note] {finding.get('message')}")


def request_reviewers_cli(args: list[str]) -> int:
    """CLI entry point: gitea request-reviewers --pr 2 [--dry-run true] [--root PATH]"""
    # args[0] is the subcommand name (e.g. "request-reviewers"); skip it so
    # parse_pairs only sees --key value pairs (same pattern as knowledge-search).
    options = parse_pairs(args[1:])
    pr_number = options.get("pr") or options.get("pr-number")
    if not pr_number:
        print("request-reviewers: --pr <number> is required (e.g. --pr 2).")
        return 2
    root = Path(options.get("root", REPO_ROOT))
    dry_run = options.get("dry-run", "false").lower() in ("true", "1", "yes")
    result = request_reviewers(root, pr_number, dry_run=dry_run)
    print_result(result, dry_run)
    return 0 if result.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(request_reviewers_cli(sys.argv[1:]))
