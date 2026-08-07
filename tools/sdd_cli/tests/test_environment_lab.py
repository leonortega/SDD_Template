"""Tests for environment_lab Nexus EULA handling."""

from __future__ import annotations

import json
from unittest.mock import patch

DISCLAIMER = (
    "Use of Sonatype Nexus Repository - Community Edition is governed by the "
    "End User License Agreement at https://links.sonatype.com/products/nxrm/ce-eula. "
    "By returning the value from \u2018accepted:false\u2019 to \u2018accepted:true\u2019, you "
    "acknowledge that you have read and agree to the End User License Agreement "
    "at https://links.sonatype.com/products/nxrm/ce-eula."
)

NOT_ACCEPTED = '{"accepted" : false, "disclaimer" : "' + DISCLAIMER + '"}'
ACCEPTED = '{"accepted" : true, "disclaimer" : "' + DISCLAIMER + '"}'

BASE = "http://localhost:8088"
AUTH = ("admin", "admin123")


def _call(sequence):
    from tools.sdd_cli.environment_lab import _accept_nexus_eula

    with patch(
        "tools.sdd_cli.environment_lab.http_json", side_effect=sequence
    ) as mock_api:
        result = _accept_nexus_eula(BASE, AUTH[0], AUTH[1])
    return result, mock_api


def test_already_accepted_is_noop() -> None:
    """GET returns accepted:true — no POST is attempted."""
    (ok, detail), mock_api = _call([(200, ACCEPTED)])
    assert ok is True
    assert "already accepted" in detail
    assert mock_api.call_count == 1
    assert mock_api.call_args.args[0] == "GET"
    assert mock_api.call_args.args[1].endswith("/service/rest/v1/system/eula")


def test_two_step_accept_posts_disclaimer_unchanged() -> None:
    """Not accepted: POSTs the same body back with accepted flipped."""
    (ok, detail), mock_api = _call([(200, NOT_ACCEPTED), (204, "")])
    assert ok is True
    assert "accepted via /system/eula" in detail
    assert mock_api.call_count == 2

    get_call, post_call = mock_api.call_args_list
    assert get_call.args[0] == "GET"
    assert post_call.args[0] == "POST"
    assert post_call.args[1].endswith("/service/rest/v1/system/eula")

    # The exact disclaimer (smart quotes included) must be echoed back.
    # http_json serializes the dict itself, so the mock receives the dict.
    body = post_call.kwargs["body"]
    assert body["accepted"] is True
    assert body["disclaimer"] == DISCLAIMER


def test_post_failure_returns_false() -> None:
    (ok, detail), mock_api = _call([(200, NOT_ACCEPTED), (500, "boom")])
    assert ok is False
    assert "POST /system/eula returned 500" in detail


def test_legacy_fallback_when_system_eula_missing() -> None:
    """Pre-3.92 Nexus: /system/eula 404s, falls back to one-shot endpoint."""
    (ok, detail), mock_api = _call([(404, ""), (204, "")])
    assert ok is True
    assert "legacy endpoint" in detail
    assert mock_api.call_count == 2
    legacy_call = mock_api.call_args_list[1]
    assert legacy_call.args[1].endswith("/service/rest/v1/editions/eula/accept")
    assert legacy_call.kwargs["body"] == {"eulaAccepted": True}


def test_legacy_already_accepted() -> None:
    (ok, detail), _ = _call([(404, ""), (400, "already accepted")])
    assert ok is True
    assert "already accepted (legacy endpoint)" in detail


def test_get_http_error_returns_false() -> None:
    (ok, detail), _ = _call([(500, "server error")])
    assert ok is False
    assert "GET /system/eula returned 500" in detail


def test_connection_error_returns_false() -> None:
    (ok, detail), _ = _call([(0, "Connection refused")])
    assert ok is False
    assert "GET /system/eula returned 0" in detail


def test_invalid_json_returns_false() -> None:
    (ok, detail), _ = _call([(200, "not json")])
    assert ok is False
    assert "Could not parse EULA response" in detail


def test_non_dict_json_returns_false() -> None:
    (ok, detail), _ = _call([(200, "[1, 2, 3]")])
    assert ok is False
    assert "Unexpected EULA response shape" in detail


# ── provision_grafana_token ─────────────────────────────────────────────


def _write_monitoring_env(tmp_path, body: str = "SEQ_URL=http://localhost:5341\n") -> Path:
    monitoring = tmp_path / "infra" / "monitoring"
    monitoring.mkdir(parents=True)
    env = monitoring / "variables.env"
    env.write_text(body, encoding="utf-8")
    return env


def test_provision_grafana_token_keeps_existing(tmp_path) -> None:
    """Token already set → no API call, audit action, file untouched."""
    from tools.sdd_cli.environment_lab import provision_grafana_token

    env = _write_monitoring_env(
        tmp_path, "GRAFANA_SERVICE_ACCOUNT_TOKEN=glsa-real-token\n"
    )
    with patch("tools.sdd_cli.environment_lab.http_json") as mock_api:
        result = provision_grafana_token(tmp_path, dry_run=False)
    assert result["valid"] is True
    mock_api.assert_not_called()
    assert any("keeping existing value" in a["message"] for a in result["actions"])
    assert "glsa-real-token" in env.read_text(encoding="utf-8")


def test_provision_grafana_token_dry_run(tmp_path) -> None:
    """Dry-run: would-do action, no API call, no write."""
    from tools.sdd_cli.environment_lab import provision_grafana_token

    env = _write_monitoring_env(tmp_path)
    with patch("tools.sdd_cli.environment_lab.http_json") as mock_api:
        result = provision_grafana_token(tmp_path, dry_run=True)
    assert result["valid"] is True
    mock_api.assert_not_called()
    assert any(
        "Would create Grafana service account" in a["message"] for a in result["actions"]
    )
    assert "GRAFANA_SERVICE_ACCOUNT_TOKEN" not in env.read_text(encoding="utf-8")


def test_provision_grafana_token_creates_and_writes(tmp_path) -> None:
    """Missing token → creates SA + token via API, writes both keys to variables.env."""
    from tools.sdd_cli.environment_lab import provision_grafana_token

    env = _write_monitoring_env(tmp_path)
    calls = [
        (201, '{"id": 7, "name": "sdd-agent"}'),  # POST /api/serviceaccounts
        (200, '{"id": 3, "key": "glsa_provisioned-key"}'),  # POST tokens
    ]
    with patch(
        "tools.sdd_cli.environment_lab.http_json", side_effect=calls
    ) as mock_api:
        result = provision_grafana_token(tmp_path, dry_run=False)

    assert result["valid"] is True
    assert mock_api.call_count == 2
    post_sa = mock_api.call_args_list[0]
    assert post_sa.args[0] == "POST"
    assert post_sa.args[1].endswith("/api/serviceaccounts")
    assert post_sa.kwargs["body"]["name"] == "sdd-agent"
    assert post_sa.kwargs["body"]["role"] == "Editor"
    assert post_sa.kwargs["basic"] == ("admin", "admin")

    content = env.read_text(encoding="utf-8")
    assert "GRAFANA_SERVICE_ACCOUNT_TOKEN=glsa_provisioned-key" in content
    assert "GRAFANA_URL=http://localhost:3001" in content
    # Existing key + comments preserved.
    assert "SEQ_URL=http://localhost:5341" in content


def test_provision_grafana_token_sa_conflict_reuses(tmp_path) -> None:
    """SA already exists (409) → search by name, then create token."""
    from tools.sdd_cli.environment_lab import provision_grafana_token

    env = _write_monitoring_env(tmp_path)
    calls = [
        (409, '{"message": "Service account already exists"}'),
        (200, '[{"id": 7, "name": "sdd-agent"}]'),  # GET search
        (200, '{"id": 3, "key": "glsa_provisioned-key"}'),  # POST tokens
    ]
    with patch(
        "tools.sdd_cli.environment_lab.http_json", side_effect=calls
    ) as mock_api:
        result = provision_grafana_token(tmp_path, dry_run=False)

    assert result["valid"] is True
    assert mock_api.call_count == 3
    assert "GRAFANA_SERVICE_ACCOUNT_TOKEN=glsa_provisioned-key" in env.read_text(
        encoding="utf-8"
    )


def test_provision_grafana_token_unreachable_is_nonblocking(tmp_path) -> None:
    """Grafana unreachable → warning finding, valid stays True, keys still synced."""
    from tools.sdd_cli.environment_lab import provision_grafana_token

    env = _write_monitoring_env(tmp_path)
    with patch(
        "tools.sdd_cli.environment_lab.http_json", return_value=(0, "Connection refused")
    ):
        result = provision_grafana_token(tmp_path, dry_run=False)

    assert result["valid"] is True
    assert any(f.get("severity") == "warning" for f in result["findings"])
    # Template keys are still synced (empty token) so Audit drift stays clean.
    content = env.read_text(encoding="utf-8")
    assert "GRAFANA_SERVICE_ACCOUNT_TOKEN=" in content
    assert "GRAFANA_URL=http://localhost:3001" in content


def test_provision_grafana_token_missing_env(tmp_path) -> None:
    """Missing variables.env → error (real run), would-do (dry-run)."""
    from tools.sdd_cli.environment_lab import provision_grafana_token

    result = provision_grafana_token(tmp_path, dry_run=False)
    assert result["valid"] is False
    assert any(f.get("severity") == "error" for f in result["findings"])

    dry = provision_grafana_token(tmp_path, dry_run=True)
    assert dry["valid"] is True
    assert any("would provision" in a["message"].lower() for a in dry["actions"])


# ── validate_client_tools (openProject.projectIdentifier placeholder) ────


def _write_client_tools(tmp_path, openproject: dict) -> None:
    codex = tmp_path / ".codex"
    codex.mkdir(parents=True)
    (codex / "client-tools.local.json").write_text(
        json.dumps({"openProject": openproject}), encoding="utf-8"
    )


def test_validate_client_tools_warns_on_placeholder(tmp_path) -> None:
    """Placeholder projectIdentifier → non-fatal warning finding."""
    from tools.sdd_cli.environment_lab import validate_client_tools

    _write_client_tools(tmp_path, {"projectIdentifier": "replace-with-project-identifier"})
    result = validate_client_tools(tmp_path, dry_run=False)
    assert result["valid"] is True
    assert any(
        f.get("key") == "openProject.projectIdentifier"
        and f.get("severity") == "warning"
        for f in result["findings"]
    )


def test_validate_client_tools_clean_when_identifier_set(tmp_path) -> None:
    """Real projectIdentifier → no findings."""
    from tools.sdd_cli.environment_lab import validate_client_tools

    _write_client_tools(tmp_path, {"projectIdentifier": "e2eproject"})
    result = validate_client_tools(tmp_path, dry_run=False)
    assert result["valid"] is True
    assert not any(
        f.get("key") == "openProject.projectIdentifier" for f in result["findings"]
    )
