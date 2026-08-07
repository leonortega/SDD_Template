"""Unit tests for the standalone workflow telemetry script."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.sdd_cli.workflow_telemetry import (
    _default_activity_name,
    _iso8601_duration,
    _resolve_activity_id,
    append_telemetry_cli,
    render_telemetry_comment,
    telemetry_upsert_cli,
)


class ActivityResolutionTests(unittest.TestCase):
    """Default per-stage activity mapping and config overrides."""

    def test_default_activity_names(self) -> None:
        self.assertEqual("Development", _default_activity_name("dev-ops-deploy-prod"))
        self.assertEqual("Testing", _default_activity_name("dev-flow-verify-change"))
        self.assertEqual("Support", _default_activity_name("dev-ops-rollback-prod"))

    def test_resolve_activity_id_defaults(self) -> None:
        self.assertEqual(3, _resolve_activity_id("dev-ops-deploy-prod", {}))
        self.assertEqual(4, _resolve_activity_id("dev-flow-verify-change", {}))
        self.assertEqual(5, _resolve_activity_id("dev-ops-rollback-prod", {}))

    def test_resolve_activity_id_explicit_wins(self) -> None:
        self.assertEqual(6, _resolve_activity_id("dev-ops-deploy-prod", {}, "6"))
        self.assertIsNone(_resolve_activity_id("dev-ops-deploy-prod", {}, "bogus"))

    def test_resolve_activity_id_config_override(self) -> None:
        config = {
            "timeTelemetry": {
                "activityByStage": {"dev-ops-deploy-prod": {"activityId": 2}}
            }
        }
        self.assertEqual(2, _resolve_activity_id("dev-ops-deploy-prod", config))


class PayloadTests(unittest.TestCase):
    """Duration formatting and the canonical marker comment."""

    def test_iso8601_duration(self) -> None:
        self.assertEqual("PT2H30M", _iso8601_duration(9000))
        self.assertEqual("PT5M", _iso8601_duration(300))
        self.assertEqual("PT45S", _iso8601_duration(45))
        self.assertEqual("PT0S", _iso8601_duration(0))

    def test_comment_marker(self) -> None:
        comment = render_telemetry_comment(
            "ABC-1",
            {
                "workflowStage": "qa-gate",
                "agentRole": "e2eQa",
                "startedUtc": "a",
                "finishedUtc": "b",
                "retryCount": 0,
                "outcome": "PASS",
            },
        )
        self.assertTrue(
            comment.startswith("IA generated workflow telemetry: ABC-1:qa-gate")
        )
        self.assertIn("outcome: PASS", comment)


class UpsertTests(unittest.TestCase):
    """telemetry_upsert_cli end-to-end behavior."""

    @staticmethod
    def _client_tools(root: Path) -> None:
        codex = root / ".codex"
        codex.mkdir(parents=True)
        (codex / "client-tools.local.json").write_text(
            json.dumps(
                {
                    "openProject": {
                        "baseUrl": "http://op:8080",
                        "apiToken": "tok",
                        "projectIdentifier": "e2eproject",
                    }
                }
            ),
            encoding="utf-8",
        )

    def test_dry_run_makes_no_api_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._client_tools(root)
            with patch(
                "tools.sdd_cli.workflow_telemetry.http_json",
                side_effect=AssertionError("dry-run must not call the API"),
            ) as mock:
                result = telemetry_upsert_cli(
                    root,
                    {
                        "ticket-key": "ABC-1",
                        "workflow-stage": "dev-flow-verify-change",
                        "agent-role": "verify",
                        "started-utc": "2026-08-07T10:00:00Z",
                        "finished-utc": "2026-08-07T11:30:00Z",
                        "outcome": "PASS",
                    },
                    dry_run=True,
                )
            self.assertTrue(result["valid"])
            self.assertEqual("dry-run", result["action"])
            raw = result["payload"]["comment"]["raw"]
            self.assertIn(
                "IA generated workflow telemetry: ABC-1:dev-flow-verify-change", raw
            )
            self.assertEqual("PT1H30M", result["payload"]["hours"])
            mock.assert_not_called()

    def test_upsert_posts_time_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._client_tools(root)
            with patch(
                "tools.sdd_cli.workflow_telemetry.http_json",
                return_value=(201, json.dumps({"id": 42})),
            ) as mock:
                result = telemetry_upsert_cli(
                    root,
                    {
                        "ticket-key": "ABC-1",
                        "workflow-stage": "dev-ops-deploy-prod",
                        "agent-role": "deployToProd",
                        "started-utc": "2026-08-07T10:00:00Z",
                        "finished-utc": "2026-08-07T10:05:00Z",
                        "outcome": "DONE",
                        "work-package-id": "7",
                        "user-id": "3",
                    },
                )
            self.assertTrue(result["valid"])
            self.assertEqual("upserted", result["action"])
            self.assertEqual(42, result["timeEntryId"])
            url = mock.call_args.args[1]
            self.assertTrue(url.endswith("/api/v3/time_entries"))
            payload = mock.call_args.kwargs["body"]
            # deploy-prod defaults to Development activity (3)
            self.assertEqual(
                "/api/v3/time_entries/activities/3",
                payload["_links"]["activity"]["href"],
            )
            self.assertEqual("PT5M", payload["hours"])
            mock.assert_called_once()

    def test_fails_loud_when_no_token(self) -> None:
        """Default is fail-loud: no JSONL row is written without the opt-in flag."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = telemetry_upsert_cli(
                root,
                {
                    "ticket-key": "ABC-1",
                    "workflow-stage": "dev-flow-verify-change",
                    "agent-role": "verify",
                    "started-utc": "2026-08-07T10:00:00Z",
                    "finished-utc": "2026-08-07T10:05:00Z",
                    "outcome": "PASS",
                },
            )
            self.assertFalse(result["valid"])
            self.assertTrue(any("upsert failed" in err for err in result["errors"]))
            self.assertFalse(
                (root / ".codex" / "agent-telemetry.local.jsonl").exists()
            )

    def test_jsonl_fallback_opt_in(self) -> None:
        """--jsonl-fallback true records the row instead of failing loud."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = telemetry_upsert_cli(
                root,
                {
                    "ticket-key": "ABC-1",
                    "workflow-stage": "dev-flow-verify-change",
                    "agent-role": "verify",
                    "started-utc": "2026-08-07T10:00:00Z",
                    "finished-utc": "2026-08-07T10:05:00Z",
                    "outcome": "PASS",
                    "jsonl-fallback": "true",
                },
            )
            self.assertTrue(result["valid"])
            self.assertEqual("jsonl-fallback", result["action"])
            jsonl = root / ".codex" / "agent-telemetry.local.jsonl"
            self.assertTrue(jsonl.exists())
            row = json.loads(jsonl.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual("ABC-1", row["ticketKey"])
            self.assertEqual("dev-flow-verify-change", row["workflowStage"])
            self.assertIn("fallbackReason", row)

    def test_rejects_non_iso_timestamps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = telemetry_upsert_cli(
                root,
                {
                    "ticket-key": "ABC-1",
                    "workflow-stage": "dev-flow-verify-change",
                    "agent-role": "verify",
                    "started-utc": "not-a-date",
                    "finished-utc": "2026-08-07T10:05:00Z",
                    "outcome": "PASS",
                },
            )
            self.assertFalse(result["valid"])
            self.assertTrue(
                any("ISO-8601" in err for err in result["errors"])
            )

    def test_missing_required_options(self) -> None:
        result = telemetry_upsert_cli(Path("."), {"ticket-key": "ABC-1"})
        self.assertFalse(result["valid"])
        self.assertTrue(any("workflow-stage" in err for err in result["errors"]))

    def test_append_telemetry_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = append_telemetry_cli(
                root, {"ticket-key": "ABC-1", "workflow-stage": "qa-gate"}
            )
            self.assertTrue(result["valid"])
            self.assertEqual("appended", result["action"])
            self.assertTrue(
                (root / ".codex" / "agent-telemetry.local.jsonl").exists()
            )


if __name__ == "__main__":
    unittest.main()
