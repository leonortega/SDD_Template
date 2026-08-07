"""Tests for the deterministic Gitea reviewer-assignment command."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from tools.sdd_cli import gitea_reviewers


def _write_client_tools(
    root: Path,
    *,
    token: str = "real-token-123",
    owner: str = "admin",
    repo: str = "sdd-test",
    reviewers: list[str] | None = None,
    provisioning_users: list[dict] | None = None,
) -> None:
    gitea: dict = {
        "baseUrl": "http://localhost:3000",
        "apiToken": token,
        "owner": owner,
        "repo": repo,
    }
    if reviewers is not None:
        gitea["reviewers"] = reviewers
    if provisioning_users is not None:
        gitea["provisioning"] = {"users": provisioning_users}
    codex = root / ".codex"
    codex.mkdir(parents=True, exist_ok=True)
    (codex / "client-tools.local.json").write_text(
        json.dumps({"gitea": gitea}), encoding="utf-8"
    )


def _ok_conn(status: int = 200, body: str = "{}") -> MagicMock:
    resp = MagicMock()
    resp.status = status
    resp.read.return_value = body.encode("utf-8")
    conn = MagicMock()
    conn.getresponse.return_value = resp
    return conn


# ── resolve_reviewers (pure resolution, priority order) ─────────────────


class TestResolveReviewers:
    def test_explicit_gitea_reviewers_win(self) -> None:
        gitea = {"reviewers": ["alice", " bob "], "provisioning": {"users": [{"username": "zed"}]}}
        out = gitea_reviewers.resolve_reviewers(gitea, {}, "1", False, [])
        assert out == ["alice", "bob"]

    def test_profile_pr_reviewers_array(self) -> None:
        gitea: dict = {}
        profile = {"pr": {"reviewers": ["carol", ""]}}
        out = gitea_reviewers.resolve_reviewers(gitea, profile, "1", False, [])
        assert out == ["carol"]

    def test_pr_reviewers_all_expands_collaborators_excluding_author(self) -> None:
        gitea = {"baseUrl": "http://x", "apiToken": "t", "owner": "o", "repo": "r"}
        profile = {"pr": {"reviewers": "all"}}
        with patch(
            "tools.sdd_cli.gitea_reviewers._fetch_collaborators",
            return_value=(["admin", "FirstUser", "SecondUser"], None),
        ), patch(
            "tools.sdd_cli.gitea_reviewers._fetch_pr_author",
            return_value=("admin", None),
        ):
            out = gitea_reviewers.resolve_reviewers(gitea, profile, "2", False, [])
        assert out == ["FirstUser", "SecondUser"]

    def test_dry_run_all_does_not_call_api(self) -> None:
        """dry_run with pr.reviewers=all resolves [] without network calls."""
        gitea = {"baseUrl": "http://x", "apiToken": "t", "owner": "o", "repo": "r"}
        profile = {"pr": {"reviewers": "all"}}
        with patch(
            "tools.sdd_cli.gitea_reviewers._fetch_collaborators",
            return_value=([], None),
        ) as fetch, patch(
            "tools.sdd_cli.gitea_reviewers._fetch_pr_author",
            return_value=("", None),
        ) as author:
            out = gitea_reviewers.resolve_reviewers(gitea, profile, "2", True, [])
        fetch.assert_not_called()
        author.assert_not_called()
        assert out == []

    def test_fallback_to_provisioned_users(self) -> None:
        gitea = {
            "provisioning": {
                "users": [
                    {"username": "FirstUser"},
                    {"username": "SecondUser"},
                    {"username": ""},
                ]
            }
        }
        out = gitea_reviewers.resolve_reviewers(gitea, {}, "1", False, [])
        assert out == ["FirstUser", "SecondUser"]

    def test_no_reviewers_appends_finding(self) -> None:
        findings: list[dict] = []
        out = gitea_reviewers.resolve_reviewers({}, {}, "1", False, findings)
        assert out == []
        assert findings and findings[0]["key"] == "gitea.reviewers.resolve"


# ── request_reviewers (end-to-end report) ───────────────────────────────


class TestRequestReviewers:
    def test_placeholder_token_fails_cleanly(self, tmp_path: Path) -> None:
        _write_client_tools(tmp_path, token="replace-with-gitea-api-token")
        result = gitea_reviewers.request_reviewers(tmp_path, "2", dry_run=False)
        assert result["valid"] is False
        assert any("apiToken" in s["message"] for s in result["steps"])

    def test_placeholder_owner_fails_cleanly(self, tmp_path: Path) -> None:
        _write_client_tools(tmp_path, owner="replace-with-gitea-owner")
        result = gitea_reviewers.request_reviewers(tmp_path, "2", dry_run=False)
        assert result["valid"] is False
        assert any("owner/repo" in s["message"] for s in result["steps"])

    def test_dry_run_previews_no_api_calls(self, tmp_path: Path) -> None:
        _write_client_tools(
            tmp_path,
            provisioning_users=[{"username": "FirstUser"}, {"username": "SecondUser"}],
        )
        with patch(
            "tools.sdd_cli.gitea_reviewers.http.client.HTTPConnection"
        ) as conn_cls:
            result = gitea_reviewers.request_reviewers(tmp_path, "2", dry_run=True)
        conn_cls.assert_not_called()
        assert result["valid"] is True
        assert result["reviewers"] == ["FirstUser", "SecondUser"]
        assert "Would request" in result["steps"][0]["message"]

    def test_no_eligible_reviewers_fails_loudly(self, tmp_path: Path) -> None:
        _write_client_tools(tmp_path)  # no reviewers, no provisioning users
        result = gitea_reviewers.request_reviewers(tmp_path, "2", dry_run=True)
        assert result["valid"] is False
        assert "No eligible reviewers" in result["steps"][0]["message"]

    def test_post_verified_success(self, tmp_path: Path) -> None:
        _write_client_tools(
            tmp_path,
            reviewers=["FirstUser", "SecondUser"],
        )
        with patch(
            "tools.sdd_cli.gitea_reviewers._fetch_requested_reviewers",
            return_value=["FirstUser", "SecondUser"],
        ), patch(
            "tools.sdd_cli.gitea_reviewers.http.client.HTTPConnection",
            return_value=_ok_conn(200),
        ):
            result = gitea_reviewers.request_reviewers(tmp_path, "2", dry_run=False)
        assert result["valid"] is True
        assert result["reviewers"] == ["FirstUser", "SecondUser"]
        assert "verified present" in result["steps"][0]["message"]

    def test_verification_mismatch_retries_then_fails(self, tmp_path: Path) -> None:
        """Gitea ignores the request (empty requested_reviewers) → retry → FAIL."""
        _write_client_tools(
            tmp_path,
            reviewers=["FirstUser"],
        )
        with patch(
            "tools.sdd_cli.gitea_reviewers._fetch_requested_reviewers",
            return_value=[],  # never appears after either attempt
        ), patch(
            "tools.sdd_cli.gitea_reviewers._fetch_pr_author",
            return_value=("admin", None),
        ), patch(
            "tools.sdd_cli.gitea_reviewers.http.client.HTTPConnection",
            return_value=_ok_conn(200),
        ) as conn_cls:
            result = gitea_reviewers.request_reviewers(tmp_path, "2", dry_run=False)
        assert result["valid"] is False
        assert conn_cls.call_count == 2  # retried once
        assert "not verified after retry" in result["steps"][0]["message"]

    def test_excluded_author_filtered(self, tmp_path: Path) -> None:
        _write_client_tools(
            tmp_path,
            reviewers=["admin", "FirstUser"],
        )
        with patch(
            "tools.sdd_cli.gitea_reviewers._fetch_requested_reviewers",
            return_value=["FirstUser"],
        ), patch(
            "tools.sdd_cli.gitea_reviewers.http.client.HTTPConnection",
            return_value=_ok_conn(200),
        ):
            result = gitea_reviewers.request_reviewers(
                tmp_path, "2", dry_run=False, excluded=["admin"]
            )
        assert result["valid"] is True
        assert result["reviewers"] == ["FirstUser"]

    def test_pr_author_excluded_from_explicit_list(self, tmp_path: Path) -> None:
        """Author exclusion applies to explicit lists too, not just "all"."""
        _write_client_tools(
            tmp_path,
            reviewers=["admin", "FirstUser", "SecondUser"],
        )
        with patch(
            "tools.sdd_cli.gitea_reviewers._fetch_pr_author",
            return_value=("admin", None),
        ), patch(
            "tools.sdd_cli.gitea_reviewers._fetch_requested_reviewers",
            return_value=["FirstUser", "SecondUser"],
        ), patch(
            "tools.sdd_cli.gitea_reviewers.http.client.HTTPConnection",
            return_value=_ok_conn(200),
        ):
            result = gitea_reviewers.request_reviewers(tmp_path, "2", dry_run=False)
        assert result["valid"] is True
        assert result["reviewers"] == ["FirstUser", "SecondUser"]
        assert "admin" not in result["reviewers"]


# ── CLI entry point ─────────────────────────────────────────────────────


class TestRequestReviewersCli:
    def test_missing_pr_returns_2(self) -> None:
        assert gitea_reviewers.request_reviewers_cli([]) == 2

    def test_dry_run_returns_zero(self, tmp_path: Path) -> None:
        _write_client_tools(
            tmp_path,
            provisioning_users=[{"username": "FirstUser"}],
        )
        # args[0] is the subcommand name, dropped before parse_pairs
        rc = gitea_reviewers.request_reviewers_cli(
            ["request-reviewers", "--pr", "2", "--dry-run", "true", "--root", str(tmp_path)]
        )
        assert rc == 0
