"""Unit tests for shared utility functions consolidated in _shared.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.sdd_cli._shared import (
    HIGH_RISK_PATTERNS,
    ensure_used_in_steps,
    find_meta,
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
        self.assertEqual({"applies": True, "value": "PostgreSQL", "notes": "Primary DB"}, result)

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


class EnsureUsedInStepsTests(unittest.TestCase):
    """Tests for ensure_used_in_steps — ensures items have a usedInSteps list."""

    def test_adds_used_in_steps_when_missing(self) -> None:
        result = ensure_used_in_steps({"id": "test-skill", "name": "Test"})
        self.assertEqual([], result["usedInSteps"])

    def test_preserves_existing_used_in_steps(self) -> None:
        result = ensure_used_in_steps({"id": "test", "usedInSteps": ["dev-flow"]})
        self.assertEqual(["dev-flow"], result["usedInSteps"])

    def test_does_not_mutate_original_input(self) -> None:
        original = {"id": "test"}
        result = ensure_used_in_steps(original)
        result["usedInSteps"].append("modified")
        self.assertNotIn("usedInSteps", original)

    def test_preserves_other_keys(self) -> None:
        result = ensure_used_in_steps({"id": "test", "name": "Test Skill", "type": "skill"})
        self.assertEqual("test", result["id"])
        self.assertEqual("Test Skill", result["name"])
        self.assertEqual("skill", result["type"])


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
    """Tests for HIGH_RISK_PATTERNS constant."""

    def test_is_a_list(self) -> None:
        self.assertIsInstance(HIGH_RISK_PATTERNS, list)

    def test_contains_expected_patterns(self) -> None:
        expected = {"auth", "deploy", "secret", "docker", "k8s"}
        self.assertTrue(expected.issubset(set(HIGH_RISK_PATTERNS)))

    def test_all_patterns_are_lowercase(self) -> None:
        for pattern in HIGH_RISK_PATTERNS:
            with self.subTest(pattern=pattern):
                self.assertEqual(pattern, pattern.lower())


if __name__ == "__main__":
    unittest.main()
