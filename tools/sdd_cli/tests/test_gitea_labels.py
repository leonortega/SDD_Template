"""Tests for the deterministic idempotent Gitea label command (gitea labels).

Covers the duplicate-label bug: repeated review loops must never produce two
`agent-reviewed` labels on one PR — the command dedupes repo definitions and
diffs the PR's current labels before applying/removing anything.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from tools.sdd_cli import gitea_labels


def _write_client_tools(
    root: Path,
    *,
    token: str = "real-token-123",
    owner: str = "admin",
    repo: str = "sdd-test",
) -> None:
    codex = root / ".template"
    codex.mkdir(parents=True, exist_ok=True)
    (codex / "client-tools.local.json").write_text(
        json.dumps(
            {
                "gitea": {
                    "baseUrl": "http://localhost:3000",
                    "apiToken": token,
                    "owner": owner,
                    "repo": repo,
                }
            }
        ),
        encoding="utf-8",
    )


def _conn(status: int = 200, body: str = "{}") -> MagicMock:
    resp = MagicMock()
    resp.status = status
    resp.read.return_value = body.encode("utf-8")
    conn = MagicMock()
    conn.getresponse.return_value = resp
    return conn


def _label(label_id: int, name: str) -> str:
    return json.dumps({"id": label_id, "name": name})


# ── apply_labels (end-to-end report) ────────────────────────────────────


class TestApplyLabels:
    def test_placeholder_token_fails_cleanly(self, tmp_path: Path) -> None:
        _write_client_tools(tmp_path, token="replace-with-gitea-api-token")
        result = gitea_labels.apply_labels(tmp_path, "2", add=["agent-reviewed"])
        assert result["valid"] is False
        assert any("apiToken" in s["message"] for s in result["steps"])

    def test_placeholder_owner_fails_cleanly(self, tmp_path: Path) -> None:
        _write_client_tools(tmp_path, owner="replace-with-gitea-owner")
        result = gitea_labels.apply_labels(tmp_path, "2", add=["agent-reviewed"])
        assert result["valid"] is False
        assert any("owner/repo" in s["message"] for s in result["steps"])

    def test_dry_run_does_not_call_api(self, tmp_path: Path) -> None:
        _write_client_tools(tmp_path)
        with patch("tools.sdd_cli.gitea_labels.http.client.HTTPConnection") as conn_cls:
            result = gitea_labels.apply_labels(
                tmp_path, "2", add=["agent-reviewed"], remove=["needs-tests"], dry_run=True
            )
        conn_cls.assert_not_called()
        assert result["valid"] is True
        messages = [s["message"] for s in result["steps"]]
        assert any("Would ensure label 'agent-reviewed'" in m for m in messages)
        assert any("Would remove label 'needs-tests'" in m for m in messages)

    def test_add_when_already_present_is_noop(self, tmp_path: Path) -> None:
        """Idempotency: an already-present label triggers no POST/DELETE."""
        _write_client_tools(tmp_path)
        repo = f"[{_label(11, 'agent-reviewed')}]"
        issue = f"[{_label(11, 'agent-reviewed')}]"
        conns = [_conn(200, repo), _conn(200, repo), _conn(200, issue)]
        with patch(
            "tools.sdd_cli.gitea_labels.http.client.HTTPConnection",
            side_effect=conns,
        ) as conn_cls:
            result = gitea_labels.apply_labels(tmp_path, "2", add=["agent-reviewed"])
        assert result["valid"] is True
        assert conn_cls.call_count == 3  # repo dedupe + repo ids + issue labels; no writes
        assert any("already on PR #2 (id 11) — no change" in s["message"] for s in result["steps"])

    def test_add_missing_label_creates_and_applies(self, tmp_path: Path) -> None:
        _write_client_tools(tmp_path)
        conns = [
            _conn(200, "[]"),                      # dedupe: no repo definitions
            _conn(200, "[]"),                      # repo ids: still none
            _conn(200, "[]"),                      # issue labels: none on PR
            _conn(201, _label(21, "agent-reviewed")),  # create repo definition
            _conn(201, "{}"),                      # apply to PR
            _conn(200, f"[{_label(21, 'agent-reviewed')}]"),  # verify present
        ]
        with patch(
            "tools.sdd_cli.gitea_labels.http.client.HTTPConnection",
            side_effect=conns,
        ):
            result = gitea_labels.apply_labels(tmp_path, "2", add=["agent-reviewed"])
        assert result["valid"] is True
        messages = [s["message"] for s in result["steps"]]
        assert any("Created repo label 'agent-reviewed'" in m for m in messages)
        assert any("Applied 'agent-reviewed'" in m and "verified present" in m for m in messages)

    def test_apply_retries_once_on_verification_mismatch(self, tmp_path: Path) -> None:
        """POST succeeds but the first verify GET shows the label missing → retry."""
        _write_client_tools(tmp_path)
        conns = [
            _conn(200, "[]"),                      # dedupe
            _conn(200, "[]"),                      # repo ids
            _conn(200, "[]"),                      # issue labels
            _conn(201, _label(21, "agent-reviewed")),  # create definition
            _conn(201, "{}"),                      # apply attempt 1
            _conn(200, "[]"),                      # verify attempt 1: MISSING
            _conn(201, "{}"),                      # apply attempt 2 (retry)
            _conn(200, f"[{_label(21, 'agent-reviewed')}]"),  # verify attempt 2: present
        ]
        with patch(
            "tools.sdd_cli.gitea_labels.http.client.HTTPConnection",
            side_effect=conns,
        ) as conn_cls:
            result = gitea_labels.apply_labels(tmp_path, "2", add=["agent-reviewed"])
        assert result["valid"] is True
        assert conn_cls.call_count == 8
        assert any("Applied 'agent-reviewed'" in s["message"] for s in result["steps"])

    def test_remove_present_label(self, tmp_path: Path) -> None:
        _write_client_tools(tmp_path)
        repo = f"[{_label(5, 'needs-tests')}]"
        conns = [
            _conn(200, repo),                      # dedupe
            _conn(200, repo),                      # repo ids
            _conn(200, repo),                      # issue labels: present
            _conn(204, "{}"),                      # DELETE from PR
            _conn(200, "[]"),                      # verify absent
        ]
        with patch(
            "tools.sdd_cli.gitea_labels.http.client.HTTPConnection",
            side_effect=conns,
        ):
            result = gitea_labels.apply_labels(tmp_path, "2", remove=["needs-tests"])
        assert result["valid"] is True
        assert any(
            "Removed 'needs-tests'" in s["message"] and "verified absent" in s["message"]
            for s in result["steps"]
        )

    def test_remove_absent_label_is_noop(self, tmp_path: Path) -> None:
        _write_client_tools(tmp_path)
        repo = f"[{_label(5, 'needs-tests')}]"
        conns = [
            _conn(200, repo),                      # dedupe
            _conn(200, repo),                      # repo ids
            _conn(200, "[]"),                      # issue labels: absent
        ]
        with patch(
            "tools.sdd_cli.gitea_labels.http.client.HTTPConnection",
            side_effect=conns,
        ) as conn_cls:
            result = gitea_labels.apply_labels(tmp_path, "2", remove=["needs-tests"])
        assert result["valid"] is True
        assert conn_cls.call_count == 3  # no DELETE
        assert any("not on PR #2 — no change" in s["message"] for s in result["steps"])

    def test_duplicate_definitions_deduped_to_one_canonical_id(self, tmp_path: Path) -> None:
        """The duplicate-label bug: two repo definitions named 'agent-reviewed'
        must collapse to one id, and only that id is applied to the PR."""
        _write_client_tools(tmp_path)
        repo_dups = f"[{_label(11, 'agent-reviewed')}, {_label(22, 'agent-reviewed')}]"
        repo_clean = f"[{_label(11, 'agent-reviewed')}]"
        conns = [
            _conn(200, repo_dups),                 # dedupe: finds the duplicate
            _conn(204, "{}"),                      # DELETE extra definition id 22
            _conn(200, repo_clean),                # repo ids: canonical id 11
            _conn(200, "[]"),                      # issue labels: none
            _conn(201, "{}"),                      # apply id 11
            _conn(200, repo_clean),                # verify present (id 11)
        ]
        with patch(
            "tools.sdd_cli.gitea_labels.http.client.HTTPConnection",
            side_effect=conns,
        ):
            result = gitea_labels.apply_labels(tmp_path, "2", add=["agent-reviewed"])
        assert result["valid"] is True
        assert any(
            "Deleted duplicate repo label definition" in f["message"]
            for f in result["findings"]
        )
        assert any(
            "Applied 'agent-reviewed'" in s["message"] and "(label id 11)" in s["message"]
            for s in result["steps"]
        )

    def test_apply_failure_fails_loudly(self, tmp_path: Path) -> None:
        _write_client_tools(tmp_path)
        conns = [
            _conn(200, "[]"),                      # dedupe
            _conn(200, "[]"),                      # repo ids
            _conn(200, "[]"),                      # issue labels
            _conn(201, _label(21, "agent-reviewed")),  # create definition
            _conn(500, "{}"),                      # apply attempt 1 fails
            _conn(500, "{}"),                      # apply attempt 2 fails
        ]
        with patch(
            "tools.sdd_cli.gitea_labels.http.client.HTTPConnection",
            side_effect=conns,
        ):
            result = gitea_labels.apply_labels(tmp_path, "2", add=["agent-reviewed"])
        assert result["valid"] is False
        assert any(f["key"] == "gitea.labels.apply" for f in result["findings"])
        assert any("Could not apply" in s["message"] for s in result["steps"])


# ── CLI entry point ─────────────────────────────────────────────────────


class TestLabelsCli:
    def test_missing_pr_returns_2(self) -> None:
        assert gitea_labels.labels_cli(["labels", "--add", "agent-reviewed"]) == 2

    def test_missing_add_remove_returns_2(self) -> None:
        assert gitea_labels.labels_cli(["labels", "--pr", "2"]) == 2

    def test_dry_run_returns_zero_and_splits_comma_names(self, tmp_path: Path, capsys) -> None:
        _write_client_tools(tmp_path)
        rc = gitea_labels.labels_cli(
            ["labels", "--pr", "2", "--add", "agent-reviewed,needs-tests",
             "--remove", "needs-changes", "--dry-run", "true", "--root", str(tmp_path)]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "Would ensure label 'agent-reviewed'" in out
        assert "Would ensure label 'needs-tests'" in out
        assert "Would remove label 'needs-changes'" in out

    def test_comma_separated_names_parsed(self, tmp_path: Path) -> None:
        """apply_labels receives already-split names (the CLI splits via split_list)."""
        _write_client_tools(tmp_path)
        repo = f"[{_label(11, 'agent-reviewed')}, {_label(5, 'needs-tests')}]"
        conns = [
            _conn(200, repo),                      # dedupe
            _conn(200, repo),                      # repo ids
            _conn(200, "[]"),                      # issue labels
            _conn(201, "{}"),                      # apply agent-reviewed
            _conn(200, f"[{_label(11, 'agent-reviewed')}]"),  # verify
            _conn(201, "{}"),                      # apply needs-tests
            _conn(200, f"[{_label(11, 'agent-reviewed')}, {_label(5, 'needs-tests')}]"),  # verify
        ]
        with patch(
            "tools.sdd_cli.gitea_labels.http.client.HTTPConnection",
            side_effect=conns,
        ):
            result = gitea_labels.apply_labels(
                tmp_path, "2", add=gitea_labels.split_list("agent-reviewed,needs-tests")
            )
        assert result["valid"] is True
        applied = [s["message"] for s in result["steps"] if "Applied" in s["message"]]
        assert len(applied) == 2
