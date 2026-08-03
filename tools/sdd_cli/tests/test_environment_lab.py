"""Tests for environment_lab Nexus EULA handling."""

from __future__ import annotations

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
