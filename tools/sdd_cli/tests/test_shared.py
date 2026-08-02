"""Unit tests for shared utility functions consolidated in _shared.py."""

from __future__ import annotations

import http
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.sdd_cli._shared import (
    find_meta,
    get_high_risk_patterns,
    http_json,
    normalize_stack_domain,
    profile_audit_findings,
    remove_empty_parents,
)


class NormalizeStackDomainTests(unittest.TestCase):
    """Tests for normalize_stack_domain — normalizes stack values into applies/value dicts."""

    def test_applies_for_non_empty_value(self) -> None:
        result = normalize_stack_domain("React + TypeScript")
        self.assertEqual({"applies": True, "value": "React + TypeScript"}, result)

    def test_does_not_apply_for_empty_string(self) -> None:
        result = normalize_stack_domain("")
        self.assertEqual({"applies": False, "value": ""}, result)

    def test_does_not_apply_for_none(self) -> None:
        result = normalize_stack_domain(None)
        self.assertEqual({"applies": False, "value": ""}, result)

    def test_does_not_apply_for_keywords(self) -> None:
        keywords = ("none", "no", "n/a", "na", "not applicable")
        for kw in keywords:
            with self.subTest(keyword=kw):
                result = normalize_stack_domain(kw)
                self.assertEqual({"applies": False, "value": ""}, result)

    def test_handles_dict_input_with_value(self) -> None:
        result = normalize_stack_domain({"value": "PostgreSQL", "notes": "Primary DB"})
        self.assertEqual(
            {"applies": True, "value": "PostgreSQL", "notes": "Primary DB"}, result
        )

    def test_handles_dict_input_ignores_empty_notes(self) -> None:
        result = normalize_stack_domain({"value": "SQLite", "notes": ""})
        self.assertEqual({"applies": True, "value": "SQLite"}, result)

    def test_handles_dict_input_missing_notes(self) -> None:
        result = normalize_stack_domain({"value": "MongoDB"})
        self.assertEqual({"applies": True, "value": "MongoDB"}, result)

    def test_strips_whitespace(self) -> None:
        result = normalize_stack_domain("  Vue.js  ")
        self.assertEqual({"applies": True, "value": "Vue.js"}, result)

    def test_case_insensitive_empty_check(self) -> None:
        result = normalize_stack_domain("NONE")
        self.assertEqual({"applies": False, "value": ""}, result)

    def test_handles_dict_with_non_applies_value(self) -> None:
        result = normalize_stack_domain({"value": "none"})
        self.assertEqual({"applies": False, "value": ""}, result)


class FindMetaTests(unittest.TestCase):
    """Tests for find_meta — extracts metadata lines from markdown-like body text."""

    def test_extracts_simple_label(self) -> None:
        body = "- Type: Pattern\n- Status: Active\n"
        self.assertEqual("Pattern", find_meta(body, "Type"))

    def test_returns_empty_string_for_missing_label(self) -> None:
        body = "- Type: Pattern\n"
        self.assertEqual("", find_meta(body, "Status"))

    def test_handles_empty_body(self) -> None:
        self.assertEqual("", find_meta("", "Type"))

    def test_extracts_label_with_special_characters(self) -> None:
        body = "- Last verified: 2026-06-25\n"
        self.assertEqual("2026-06-25", find_meta(body, "Last verified"))

    def test_extracts_label_with_colon_in_value(self) -> None:
        body = "- Source: https://example.com:8080\n"
        self.assertEqual("https://example.com:8080", find_meta(body, "Source"))


class RemoveEmptyParentsTests(unittest.TestCase):
    """Tests for remove_empty_parents — cleans up empty parent directories."""

    def test_removes_empty_parent_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            leaf = base / "a" / "b" / "c"
            leaf.mkdir(parents=True)
            self.assertTrue(leaf.exists())
            leaf.rmdir()
            remove_empty_parents(leaf, base)
            self.assertFalse((base / "a").exists())

    def test_stops_at_stop_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            leaf = base / "a" / "b" / "c"
            leaf.mkdir(parents=True)
            leaf.rmdir()
            remove_empty_parents(leaf, base / "a")
            self.assertTrue((base / "a").exists())
            self.assertFalse((base / "a" / "b").exists())

    def test_does_not_remove_non_empty_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            leaf = base / "a" / "b"
            leaf.mkdir(parents=True)
            (base / "a" / "keep").write_text("keep me", encoding="utf-8")
            leaf.rmdir()
            remove_empty_parents(leaf, base)
            self.assertTrue((base / "a").exists())

    def test_noop_when_path_is_stop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            remove_empty_parents(base, base)
            self.assertTrue(base.exists())


class ProfileAuditFindingsTests(unittest.TestCase):
    """Tests for profile_audit_findings — returns findings for missing profile/schema."""

    def test_returns_warning_when_profile_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".codex").mkdir()
            findings = profile_audit_findings(root)
            keys = {item["key"] for item in findings}
            self.assertIn("missing.profile", keys)
            self.assertIn("missing.schema", keys)

    def test_returns_no_findings_when_both_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / ".codex"
            codex.mkdir()
            (codex / "project-profile.json").write_text("{}", encoding="utf-8")
            (codex / "project-profile.schema.json").write_text("{}", encoding="utf-8")
            findings = profile_audit_findings(root)
            self.assertEqual([], findings)

    def test_returns_warning_when_schema_missing_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / ".codex"
            codex.mkdir()
            (codex / "project-profile.json").write_text("{}", encoding="utf-8")
            findings = profile_audit_findings(root)
            keys = {item["key"] for item in findings}
            self.assertNotIn("missing.profile", keys)
            self.assertIn("missing.schema", keys)


class HighRiskPatternsTests(unittest.TestCase):
    """Tests for get_high_risk_patterns() result."""

    def test_is_a_list(self) -> None:
        patterns = get_high_risk_patterns()
        self.assertIsInstance(patterns, list)

    def test_contains_expected_patterns(self) -> None:
        patterns = get_high_risk_patterns()
        expected = {"auth", "deploy", "secret", "docker", "k8s"}
        self.assertTrue(expected.issubset(set(patterns)))

    def test_all_patterns_are_lowercase(self) -> None:
        for pattern in get_high_risk_patterns():
            with self.subTest(pattern=pattern):
                self.assertEqual(pattern, pattern.lower())


class HttpJsonTests(unittest.TestCase):
    """Tests for http_json — bearer/basic/no-auth header handling and error path.

    The connection classes are patched out (no network); only header assembly,
    request wiring, and the (0, error) fallback are exercised.
    """

    @staticmethod
    def _fake_connection(captured: dict) -> type:
        class FakeResponse:
            status = 200

            def read(self) -> bytes:
                return b'{"ok": true}'

        class FakeConnection:
            def __init__(self, host, port=None, timeout=None) -> None:
                captured["host"] = host
                captured["port"] = port
                captured["timeout"] = timeout

            def request(self, method, path, body=None, headers=None) -> None:
                captured["method"] = method
                captured["path"] = path
                captured["body"] = body
                captured["headers"] = headers

            def getresponse(self) -> FakeResponse:
                return FakeResponse()

            def close(self) -> None:
                pass

        return FakeConnection

    def test_bearer_auth_sets_authorization_header(self) -> None:
        captured: dict = {}
        FakeConnection = self._fake_connection(captured)
        with patch.object(http.client, "HTTPConnection", FakeConnection):
            status, data = http_json(
                "POST",
                "http://localhost:8080/api/v3/work_packages",
                body={"subject": "x"},
                bearer="tok-123",
            )
        self.assertEqual(status, 200)
        self.assertEqual(data, '{"ok": true}')
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["path"], "/api/v3/work_packages")
        self.assertEqual(captured["body"], '{"subject": "x"}')
        self.assertEqual(captured["host"], "localhost")
        self.assertEqual(captured["port"], 8080)
        self.assertEqual(
            captured["headers"]["Authorization"], "Bearer tok-123"
        )

    def test_bearer_wins_over_basic_auth(self) -> None:
        captured: dict = {}
        FakeConnection = self._fake_connection(captured)
        with patch.object(http.client, "HTTPConnection", FakeConnection):
            http_json(
                "GET",
                "http://localhost:3000/api/v1/user",
                basic=("user", "pass"),
                bearer="tok-456",
            )
        self.assertEqual(
            captured["headers"]["Authorization"], "Bearer tok-456"
        )

    def test_basic_auth_sets_base64_authorization_header(self) -> None:
        import base64

        captured: dict = {}
        FakeConnection = self._fake_connection(captured)
        with patch.object(http.client, "HTTPConnection", FakeConnection):
            http_json(
                "GET",
                "http://localhost:8088/service/rest/v1/status",
                basic=("admin", "pass123"),
            )
        expected = "Basic " + base64.b64encode(b"admin:pass123").decode()
        self.assertEqual(captured["headers"]["Authorization"], expected)

    def test_no_auth_sets_no_authorization_header(self) -> None:
        captured: dict = {}
        FakeConnection = self._fake_connection(captured)
        with patch.object(http.client, "HTTPConnection", FakeConnection):
            http_json("GET", "http://localhost:3000/api/health")
        self.assertNotIn("Authorization", captured["headers"])

    def test_https_uses_https_connection_class(self) -> None:
        captured: dict = {}
        FakeConnection = self._fake_connection(captured)
        with patch.object(http.client, "HTTPSConnection", FakeConnection):
            http_json("GET", "https://host.docker.internal:6443/api")
        self.assertEqual(captured["host"], "host.docker.internal")
        self.assertEqual(captured["port"], 6443)

    def test_query_string_is_preserved_in_request_path(self) -> None:
        captured: dict = {}
        FakeConnection = self._fake_connection(captured)
        with patch.object(http.client, "HTTPConnection", FakeConnection):
            http_json("GET", "http://localhost:8088/service?name=foo&x=1")
        self.assertEqual(captured["path"], "/service?name=foo&x=1")

    def test_connection_failure_returns_zero_status(self) -> None:
        class ExplodingConnection:
            def __init__(self, host, port=None, timeout=None) -> None:
                pass

            def request(self, method, path, body=None, headers=None) -> None:
                raise ConnectionRefusedError("boom")

        with patch.object(http.client, "HTTPConnection", ExplodingConnection):
            status, err = http_json(
                "GET", "http://localhost:3000/api/v1/user"
            )
        self.assertEqual(status, 0)
        self.assertIn("boom", err)


if __name__ == "__main__":
    unittest.main()
