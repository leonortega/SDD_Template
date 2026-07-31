"""Tests for project guidance: internet skill search, manifest updates."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from tools.sdd_cli.guidance import (
    _normalize_stack_value,
    _parse_installs_value,
    _search_skills_internet,
    discover_project_guidance,
    setup_project_guidance,
)


# ── Fixtures ──────────────────────────────────────────────────────────────

_INTERNET_SEARCH_OUTPUT_REACT = """
███████╗██╗  ██╗██╗██╗     ██╗     ███████╗
██╔════╝██║ ██╔╝██║██║     ██║     ██╔════╝

Install with npx skills add <owner/repo@skill>

vercel-labs/agent-skills@vercel-react-best-practices 585.8K installs
└ https://skills.sh/vercel-labs/agent-skills/vercel-react-best-practices

vercel-labs/agent-skills@vercel-react-native-skills 175.7K installs
└ https://skills.sh/vercel-labs/agent-skills/vercel-react-native-skills

github/awesome-copilot@react 100K installs
└ https://skills.sh/github/awesome-copilot/react
"""

_INTERNET_SEARCH_OUTPUT_TYPESCRIPT = """
Install with npx skills add <owner/repo@skill>

vercel-labs/agent-skills@vercel-typescript 300K installs
└ https://skills.sh/vercel-labs/agent-skills/vercel-typescript

github/awesome-copilot@typescript 200K installs
└ https://skills.sh/github/awesome-copilot/typescript
"""

_INTERNET_SEARCH_OUTPUT_PYTHON = """
Install with npx skills add <owner/repo@skill>

microsoft/azure-skills@python-appservice-deploy 89.3K installs
└ https://skills.sh/microsoft/azure-skills/python-appservice-deploy

wshobson/agents@python-performance-optimization 29.9K installs
└ https://skills.sh/wshobson/agents/python-performance-optimization
"""

_INTERNET_SEARCH_OUTPUT_EMPTY = """
Install with npx skills add <owner/repo@skill>

"""


def _make_profile(root: Path, frontend: str = "", backend: str = "", database: str = "") -> None:
    """Create project-profile.local.json with the given stack values."""
    codex = root / ".codex"
    codex.mkdir(parents=True, exist_ok=True)
    stack = {}
    for domain, val in [("frontend", frontend), ("backend", backend), ("database", database)]:
        if val:
            stack[domain] = {"applies": True, "value": val}
        else:
            stack[domain] = {"applies": False, "value": ""}
    (codex / "project-profile.local.json").write_text(
        json.dumps({"stack": stack}), encoding="utf-8"
    )


def _make_manifest(root: Path, categories: dict | None = None) -> dict:
    """Create a basic manifest.json in .codex/skills/."""
    skills_dir = root / ".codex" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    if categories is None:
        categories = {
            "test": {
                "description": "Test skills",
                "skills": ["playwright/SKILL.md"],
            }
        }
    manifest = {"schemaVersion": "1.0", "categories": categories}
    (skills_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


# ── _normalize_stack_value ────────────────────────────────────────────────


class TestNormalizeStackValue:
    def test_from_dict(self) -> None:
        assert _normalize_stack_value({"value": "React + TS", "applies": True}) == "react + ts"

    def test_from_string(self) -> None:
        assert _normalize_stack_value("FastAPI") == "fastapi"

    def test_empty(self) -> None:
        assert _normalize_stack_value("") == ""
        assert _normalize_stack_value(None) == ""


# ── _parse_installs_value ─────────────────────────────────────────────────


class TestParseInstallsValue:
    def test_k_format(self) -> None:
        assert _parse_installs_value("585.8K") == 585800
        assert _parse_installs_value("1.4K") == 1400
        assert _parse_installs_value("100K") == 100000

    def test_m_format(self) -> None:
        assert _parse_installs_value("1.5M") == 1500000

    def test_plain_number(self) -> None:
        assert _parse_installs_value("50") == 50
        assert _parse_installs_value("0") == 0

    def test_invalid(self) -> None:
        assert _parse_installs_value("N/A") == 0
        assert _parse_installs_value("") == 0


# ── _search_skills_internet ───────────────────────────────────────────────


class TestSearchSkillsInternet:
    def test_dry_run_returns_empty(self, tmp_path: Path) -> None:
        assert _search_skills_internet(tmp_path, "react", dry_run=True) == []

    def test_parses_output_and_sorts_by_popularity(self, tmp_path: Path) -> None:
        """Verify parsing of npx skills find output."""
        with patch("tools.sdd_cli.guidance.run_native") as mock_run:
            mock_run.return_value = {
                "returncode": 0,
                "stdout": _INTERNET_SEARCH_OUTPUT_REACT,
            }
            result = _search_skills_internet(tmp_path, "react", dry_run=False)

        assert len(result) == 3  # _MAX_SKILLS_PER_QUERY caps at 3
        assert result[0]["installs"] >= result[1]["installs"]  # sorted descending
        assert result[0]["skill"] == "vercel-react-best-practices"
        assert result[0]["package"] == "vercel-labs/agent-skills"
        assert result[2]["skill"] == "react"
        assert result[2]["package"] == "github/awesome-copilot"

    def test_handles_empty_results(self, tmp_path: Path) -> None:
        with patch("tools.sdd_cli.guidance.run_native") as mock_run:
            mock_run.return_value = {
                "returncode": 0,
                "stdout": _INTERNET_SEARCH_OUTPUT_EMPTY,
            }
            result = _search_skills_internet(tmp_path, "obscure-framework", dry_run=False)
        assert result == []

    def test_handles_command_failure(self, tmp_path: Path) -> None:
        with patch("tools.sdd_cli.guidance.run_native") as mock_run:
            mock_run.return_value = {"returncode": 1, "stdout": ""}
            result = _search_skills_internet(tmp_path, "react", dry_run=False)
        assert result == []


# ── setup_project_guidance ────────────────────────────────────────────────


class TestSetupProjectGuidance:
    def test_skips_when_no_stack_values(self, tmp_path: Path) -> None:
        result = setup_project_guidance(tmp_path, {}, dry_run=False)
        assert result["valid"] is True
        assert "No stack values provided" in str(result)

    def test_searches_internet_for_each_stack_value(self, tmp_path: Path) -> None:
        """Verify internet search is invoked for each stack value token."""
        with patch("tools.sdd_cli.guidance._search_skills_internet") as mock_search:
            mock_search.return_value = [
                {"package": "github/awesome-copilot", "skill": "react", "installs": 100000, "package_skill": "github/awesome-copilot@react"}
            ]
            with patch("tools.sdd_cli.guidance._install_skill_via_npx") as mock_install:
                mock_install.return_value = {"valid": True, "skillName": "react", "actions": []}
                with patch("tools.sdd_cli.guidance._update_manifest_with_skills") as mock_manifest:
                    mock_manifest.return_value = {"valid": True, "newSkills": ["react"], "actions": []}
                    result = setup_project_guidance(
                        tmp_path, {"frontend": "React"}, dry_run=False
                    )

        assert result["valid"] is True
        assert "github/awesome-copilot@react" in result["foundSkills"]
        mock_search.assert_called_once()

    def test_searches_all_tokens_from_compound(self, tmp_path: Path) -> None:
        """Compound values like 'React + TypeScript' should search both tokens."""
        with patch("tools.sdd_cli.guidance._search_skills_internet") as mock_search:
            mock_search.return_value = []
            setup_project_guidance(
                tmp_path, {"frontend": "React + TypeScript"}, dry_run=True
            )
        # Should be called once for "react" and once for "typescript"
        assert mock_search.call_count == 2
        calls = [call.args[1] for call in mock_search.call_args_list]  # query arg
        assert "react" in calls
        assert "typescript" in calls

    def test_reads_profile_when_no_values(self, tmp_path: Path) -> None:
        _make_profile(tmp_path, frontend="Vue.js")
        with patch("tools.sdd_cli.guidance._search_skills_internet") as mock_search:
            mock_search.return_value = []
            result = setup_project_guidance(tmp_path, {}, dry_run=True)
        assert result["valid"] is True
        assert result["stackInput"].get("frontend") == "vue.js"

    def test_manifest_update_on_dry_run(self, tmp_path: Path) -> None:
        """In dry-run mode, manifest should NOT be written to disk."""
        with patch("tools.sdd_cli.guidance._search_skills_internet") as mock_search:
            mock_search.return_value = [
                {"package": "github/awesome-copilot", "skill": "react", "installs": 100000, "package_skill": "github/awesome-copilot@react"}
            ]
            with patch("tools.sdd_cli.guidance._install_skill_via_npx") as mock_install:
                mock_install.return_value = {"valid": True, "skillName": "react", "actions": []}
                result = setup_project_guidance(
                    tmp_path, {"frontend": "React"}, dry_run=True
                )

        assert result["valid"] is True
        manifest_path = tmp_path / ".codex" / "skills" / "manifest.json"
        assert not manifest_path.exists(), "Manifest should not be written in dry-run mode"

    def test_never_auto_installs_without_interactive_confirmation(
        self, tmp_path: Path
    ) -> None:
        """Non-interactive (CI/non-TTY): skills are reported but NEVER installed."""
        with patch("tools.sdd_cli.guidance._search_stack_tokens") as mock_search:
            # Full skill dict so that without the gate the install loop WOULD
            # attempt the install — proving the short-circuit is what blocks it.
            mock_search.return_value = (
                [
                    {
                        "package": "github/awesome-copilot",
                        "skill": "react",
                        "installs": 100000,
                        "package_skill": "github/awesome-copilot@react",
                    }
                ],
                [],
            )
            with patch("tools.sdd_cli.guidance._install_skill_via_npx") as mock_install:
                with patch("tools.sdd_cli.guidance._update_manifest_with_skills") as mock_manifest:
                    result = setup_project_guidance(
                        tmp_path, {"frontend": "React"}, dry_run=False
                    )

        assert result["valid"] is True
        assert result["foundSkills"] == ["github/awesome-copilot@react"]
        assert result["installResults"] == []
        keys = {item["key"] for item in result["actions"]}
        assert "interactive.required" in keys
        mock_install.assert_not_called()
        mock_manifest.assert_not_called()

    def test_installs_only_user_selected_skills_when_interactive(
        self, tmp_path: Path
    ) -> None:
        """In an interactive TTY, only the user-selected skills are installed."""
        with patch("tools.sdd_cli.guidance._search_stack_tokens") as mock_search:
            mock_search.return_value = (
                [
                    {"package": "github/awesome-copilot", "skill": "react", "installs": 100000, "package_skill": "github/awesome-copilot@react"},
                    {"package": "vercel-labs/agent-skills", "skill": "typescript", "installs": 50000, "package_skill": "vercel-labs/agent-skills@typescript"},
                ],
                [],
            )
            # Simulate a TTY where the user selects only skill #2 (typescript)
            with patch("tools.sdd_cli.guidance.sys.stdin.isatty", return_value=True):
                with patch("builtins.input", return_value="2"):
                    with patch("tools.sdd_cli.guidance._install_skill_via_npx") as mock_install:
                        mock_install.return_value = {"valid": True, "skillName": "typescript", "actions": []}
                        with patch("tools.sdd_cli.guidance._update_manifest_with_skills") as mock_manifest:
                            mock_manifest.return_value = {"valid": True, "newSkills": ["typescript"], "actions": []}
                            result = setup_project_guidance(
                                tmp_path, {"frontend": "React"}, dry_run=False,
                                interactive=True,
                            )

        assert result["valid"] is True
        # Only typescript (index 2) was installed — react was NOT auto-installed
        mock_install.assert_called_once()
        installed_names = [r.get("skillName") for r in result["installResults"]]
        assert installed_names == ["typescript"]


# ── discover_project_guidance ─────────────────────────────────────────────


class TestDiscoverProjectGuidance:
    def test_returns_stack_tags_from_profile(self, tmp_path: Path) -> None:
        """Discover reads stack tags from profile (never from manifest)."""
        _make_profile(tmp_path, frontend="react")

        result = discover_project_guidance(tmp_path, dry_run=True)
        assert result["valid"] is True
        assert "react" in (result.get("stackTags") or [])

    def test_never_consults_local_manifest(self, tmp_path: Path) -> None:
        """A rich local manifest must NOT influence discover results."""
        _make_manifest(
            tmp_path,
            categories={
                "frontend": {
                    "description": "Frontend skills",
                    "skills": ["react/SKILL.md", "vue/SKILL.md"],
                    "stackTags": ["react", "vue"],
                },
                "core": {
                    "description": "Core skills",
                    "alwaysActive": True,
                    "skills": [],
                },
            },
        )
        _make_profile(tmp_path, frontend="React")

        with patch("tools.sdd_cli.guidance._search_stack_tokens") as mock_search:
            mock_search.return_value = (
                [{"package_skill": "github/awesome-copilot@react"}],
                [],
            )
            result = discover_project_guidance(tmp_path, dry_run=True)

        assert result["valid"] is True
        # Answer comes from internet search, not from the local manifest.
        assert result["foundSkills"] == ["github/awesome-copilot@react"]
        assert result["skillCount"] == 1
        mock_search.assert_called_once()

    def test_searches_internet_for_each_stack_token(self, tmp_path: Path) -> None:
        """Discover searches the internet per stack value token."""
        _make_profile(tmp_path, frontend="React + TypeScript")
        with patch("tools.sdd_cli.guidance._search_stack_tokens") as mock_search:
            mock_search.return_value = ([], [])
            result = discover_project_guidance(tmp_path, dry_run=True)

        assert result["valid"] is True
        # search actions emitted for each token
        assert mock_search.call_count == 1
        stack_values = mock_search.call_args[0][1]
        assert "react + typescript" in stack_values["frontend"]

    def test_skips_when_no_stack_values(self, tmp_path: Path) -> None:
        """Without a stack, discover skips gracefully — no manifest required."""
        result = discover_project_guidance(tmp_path, dry_run=True)
        assert result["valid"] is True
        keys = {item["key"] for item in result["actions"]}
        assert "guidance.skip" in keys
        assert result["foundSkills"] == []
