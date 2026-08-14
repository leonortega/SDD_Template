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
    codex = tmp_path / ".template"
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


# ── prune_docker_leftovers ───────────────────────────────────────────────


def test_prune_docker_leftovers_runs_scoped_prunes(tmp_path) -> None:
    """Issues the 3 scoped prunes + the tagged-image retention pass."""
    from tools.sdd_cli.environment_lab import prune_docker_leftovers

    calls: list[list[str]] = []

    def fake_run_native(command, root, timeout=30):
        calls.append(command)
        return {"returncode": 0, "stdout": "Deleted leftovers\n", "stderr": ""}

    with patch(
        "tools.sdd_cli.environment_lab.run_native", side_effect=fake_run_native
    ):
        result = prune_docker_leftovers(tmp_path, dry_run=False)

    assert result["valid"] is True
    assert len(calls) == 4  # container + image + volume + docker images list
    assert [c[1] for c in calls[:3]] == ["container", "image", "volume"]
    # Container + volume prunes exclude compose-owned lab resources.
    for c in (calls[0], calls[2]):
        assert "--filter" in c
        assert "label!=com.docker.compose.project" in c
    # Image prune is dangling-only (no -a) so tagged lab images survive.
    assert "-a" not in calls[1]
    # Tagged pass lists images (empty output → nothing pruned, no rmi call).
    assert calls[3][0] == "docker" and "images" in calls[3]
    assert any("Pruned leftover containers" in a["message"] for a in result["actions"])
    assert any("No old registry tags to prune" in a["message"] for a in result["actions"])


def test_prune_docker_leftovers_dry_run_does_not_execute(tmp_path) -> None:
    """Dry-run reports would-do actions and never calls docker."""
    from tools.sdd_cli.environment_lab import prune_docker_leftovers

    with patch("tools.sdd_cli.environment_lab.run_native") as mock_run:
        result = prune_docker_leftovers(tmp_path, dry_run=True)

    mock_run.assert_not_called()
    assert result["valid"] is True
    assert len(result["actions"]) == 4  # 3 scoped prunes + registry-tags (no apps.json → no scratch)
    assert all("Would prune leftover" in a["message"] for a in result["actions"])


def test_prune_docker_leftovers_failure_is_nonblocking(tmp_path) -> None:
    """A failing prune is a warning finding, never an error."""
    from tools.sdd_cli.environment_lab import prune_docker_leftovers

    with patch(
        "tools.sdd_cli.environment_lab.run_native",
        return_value={"returncode": 1, "stdout": "", "stderr": "boom"},
    ):
        result = prune_docker_leftovers(tmp_path, dry_run=False)

    assert result["valid"] is True
    assert len(result["findings"]) == 4  # 3 scoped prunes + docker images list failure


def test_prune_docker_leftovers_prunes_old_registry_shas(tmp_path) -> None:
    """Old registry commit SHAs are pruned; :latest and newest LOCAL_IMAGE_KEEP kept."""
    from tools.sdd_cli.environment_lab import prune_docker_leftovers

    registry = "host.docker.internal:5001"
    sha = lambda n: f"{n:040x}"
    new_ref = f"{registry}/dellop-api:{sha(2)}"
    old_ref = f"{registry}/dellop-api:{sha(1)}"
    image_rows = "\n".join(
        [
            f"2026-08-14 12:00:00 +0000 UTC\t{new_ref}",
            f"2026-08-13 12:00:00 +0000 UTC\t{old_ref}",
            f"2026-08-12 12:00:00 +0000 UTC\t{registry}/dellop-api:latest",
        ]
    )
    calls: list[list[str]] = []

    def fake_run_native(command, root, timeout=30):
        calls.append(command)
        if command[:2] == ["docker", "images"]:
            return {"returncode": 0, "stdout": image_rows + "\n", "stderr": ""}
        if "rmi" in command:
            return {"returncode": 0, "stdout": "deleted\n", "stderr": ""}
        return {"returncode": 0, "stdout": "", "stderr": ""}

    with patch(
        "tools.sdd_cli.environment_lab.run_native", side_effect=fake_run_native
    ):
        result = prune_docker_leftovers(tmp_path, dry_run=False)

    assert result["valid"] is True
    rmi = [c for c in calls if "rmi" in c]
    assert len(rmi) == 1
    removed = set(rmi[0][rmi[0].index("rmi") + 1:])
    assert removed == {old_ref}  # newest SHA + :latest kept, old SHA removed
    assert any(
        "Pruned leftover registry-tags" in a["message"] for a in result["actions"]
    )


def test_prune_docker_leftovers_prunes_scratch_tags_for_registered_apps(tmp_path) -> None:
    """Unqualified tags of apps registered in apps.json are removed (except :latest)."""
    from tools.sdd_cli.environment_lab import prune_docker_leftovers

    apps = tmp_path / "infra" / "deployment"
    apps.mkdir(parents=True)
    (apps / "apps.json").write_text(
        json.dumps({"version": 1, "apps": [{"appId": "dellop-api"}]}),
        encoding="utf-8",
    )
    sha = f"{2:040x}"
    image_rows = "\n".join(
        [
            f"2026-08-14 12:00:00 +0000 UTC\tdellop-api:fix",
            f"2026-08-14 11:00:00 +0000 UTC\tdellop-api:jwt",
            f"2026-08-14 10:00:00 +0000 UTC\tdellop-api:latest",
            f"2026-08-14 09:00:00 +0000 UTC\tlocalhost:5001/dellop-api:{sha}",
            f"2026-08-13 09:00:00 +0000 UTC\tnode:22-alpine",
        ]
    )
    calls: list[list[str]] = []

    def fake_run_native(command, root, timeout=30):
        calls.append(command)
        if command[:2] == ["docker", "images"]:
            return {"returncode": 0, "stdout": image_rows + "\n", "stderr": ""}
        if "rmi" in command:
            return {"returncode": 0, "stdout": "deleted\n", "stderr": ""}
        return {"returncode": 0, "stdout": "", "stderr": ""}

    with patch(
        "tools.sdd_cli.environment_lab.run_native", side_effect=fake_run_native
    ):
        result = prune_docker_leftovers(tmp_path, dry_run=False)

    assert result["valid"] is True
    rmi = [c for c in calls if "rmi" in c]
    assert len(rmi) == 1  # only the scratch pass (registry SHA is newest/only → kept)
    removed = set(rmi[0][rmi[0].index("rmi") + 1:])
    assert removed == {"dellop-api:fix", "dellop-api:jwt"}
    assert "dellop-api:latest" not in removed
    assert "node:22-alpine" not in removed
    assert any(
        "Pruned leftover scratch-tags" in a["message"] for a in result["actions"]
    )


def test_prune_docker_leftovers_dry_run_reports_tagged_actions(tmp_path) -> None:
    """Dry-run with registered apps reports both tagged-image passes without docker."""
    from tools.sdd_cli.environment_lab import prune_docker_leftovers

    apps = tmp_path / "infra" / "deployment"
    apps.mkdir(parents=True)
    (apps / "apps.json").write_text(
        json.dumps({"version": 1, "apps": [{"appId": "dellop-api"}]}),
        encoding="utf-8",
    )

    with patch("tools.sdd_cli.environment_lab.run_native") as mock_run:
        result = prune_docker_leftovers(tmp_path, dry_run=True)

    mock_run.assert_not_called()
    assert result["valid"] is True
    messages = [a["message"] for a in result["actions"]]
    assert any("registry-tags" in m for m in messages)
    assert any("scratch-tags" in m for m in messages)


# ── prune_kind_images ────────────────────────────────────────────────────


def test_prune_kind_images_dry_run_reports_without_executing(tmp_path) -> None:
    """Dry-run reports the would-do action and never calls docker."""
    from tools.sdd_cli.environment_lab import prune_kind_images

    with patch("tools.sdd_cli.environment_lab.run_native") as mock_run:
        result = prune_kind_images(tmp_path, dry_run=True)

    mock_run.assert_not_called()
    assert result["valid"] is True
    assert any(
        "Would prune leftover kind-images" in a["message"]
        for a in result["actions"]
    )


def test_prune_kind_images_skips_when_node_missing(tmp_path) -> None:
    """A missing kind node skips the prune (reported, not a failure)."""
    from tools.sdd_cli.environment_lab import prune_kind_images

    with patch(
        "tools.sdd_cli.environment_lab.run_native",
        return_value={"returncode": 1, "stdout": "", "stderr": "No such object"},
    ):
        result = prune_kind_images(tmp_path, dry_run=False)

    assert result["valid"] is True
    assert any(
        "not found - skipping kind image prune" in a["message"]
        for a in result["actions"]
    )


def test_prune_kind_images_keeps_newest_per_app(tmp_path, monkeypatch) -> None:
    """Old SHA tags are pruned; the newest KIND_IMAGE_KEEP per app are kept."""
    from tools.sdd_cli.environment_lab import prune_kind_images

    monkeypatch.setenv("KIND_IMAGE_KEEP", "2")
    registry = "host.docker.internal:5001"
    sha = lambda n: f"{n:040x}"
    refs = [f"{registry}/dellop-web:{sha(n)}" for n in (1, 2, 3, 4)]
    created = [
        f"2026-08-14 12:00:00 +0000 UTC\t{refs[3]}",
        f"2026-08-13 12:00:00 +0000 UTC\t{refs[2]}",
        f"2026-08-12 12:00:00 +0000 UTC\t{refs[1]}",
        f"2026-08-11 12:00:00 +0000 UTC\t{refs[0]}",
    ]
    calls: list[list[str]] = []

    def fake_run_native(command, root, timeout=30):
        calls.append(command)
        if command[:2] == ["docker", "inspect"]:
            return {"returncode": 0, "stdout": "", "stderr": ""}
        if "ctr" in command and "list" in command:
            return {"returncode": 0, "stdout": "\n".join(refs) + "\n", "stderr": ""}
        if command[1] == "images" and "--format" in command:
            return {"returncode": 0, "stdout": "\n".join(created) + "\n", "stderr": ""}
        if "rm" in command:
            return {"returncode": 0, "stdout": "deleted\n", "stderr": ""}
        return {"returncode": 0, "stdout": "", "stderr": ""}

    with patch(
        "tools.sdd_cli.environment_lab.run_native", side_effect=fake_run_native
    ):
        result = prune_kind_images(tmp_path, dry_run=False)

    assert result["valid"] is True
    rm_calls = [c for c in calls if "rm" in c]
    assert len(rm_calls) == 1
    pruned = set(rm_calls[0][rm_calls[0].index("rm") + 1:])
    assert pruned == {refs[0], refs[1]}  # oldest two pruned, newest two kept
    assert any("Pruned leftover kind-images" in a["message"] for a in result["actions"])


def test_prune_kind_images_removal_failure_is_warning(tmp_path) -> None:
    """A failed ctr rm is a warning finding, never an error."""
    from tools.sdd_cli.environment_lab import prune_kind_images

    registry = "host.docker.internal:5001"
    sha = lambda n: f"{n:040x}"
    refs = [f"{registry}/dellop-web:{sha(n)}" for n in (1, 2, 3, 4)]

    def fake_run_native(command, root, timeout=30):
        if command[:2] == ["docker", "inspect"]:
            return {"returncode": 0, "stdout": "", "stderr": ""}
        if "ctr" in command and "list" in command:
            return {"returncode": 0, "stdout": "\n".join(refs) + "\n", "stderr": ""}
        if command[1] == "images" and "--format" in command:
            # No host timestamps → all refs sort as oldest; still prunes safely.
            return {"returncode": 0, "stdout": "", "stderr": ""}
        if "rm" in command:
            return {"returncode": 1, "stdout": "", "stderr": "boom"}
        return {"returncode": 0, "stdout": "", "stderr": ""}

    with patch(
        "tools.sdd_cli.environment_lab.run_native", side_effect=fake_run_native
    ):
        result = prune_kind_images(tmp_path, dry_run=False)

    assert result["valid"] is True
    assert any("kind image prune failed" in f["message"] for f in result["findings"])
    assert all(f.get("severity") == "warning" for f in result["findings"])


# ── set_semgrep_config (single-source-of-truth header) ─────────────────


def _write_project_profile(tmp_path, stack: dict) -> None:
    codex = tmp_path / ".template"
    codex.mkdir(parents=True)
    (codex / "project-profile.local.json").write_text(
        json.dumps({"stack": stack}), encoding="utf-8"
    )


def test_set_semgrep_config_writes_single_source_of_truth_yml(tmp_path) -> None:
    """Generated .semgrep.yml is header-only; rule packs live in the JSON."""
    from tools.sdd_cli.environment_lab import set_semgrep_config

    _write_project_profile(
        tmp_path,
        {
            "frontend": {"value": "angular"},
            "backend": {"value": "express"},
            "database": {"value": "postgresql"},
        },
    )
    result = set_semgrep_config(tmp_path, dry_run=False)

    assert result["valid"] is True
    yml = (tmp_path / ".semgrep.yml").read_text(encoding="utf-8")
    assert "Single source of truth for active rule packs: .semgrep-rules.json" in yml
    assert "This file intentionally contains no rule list" in yml
    assert "rules: []" in yml
    assert "# - p/" not in yml  # no inline rule-list comments anymore

    rules = json.loads((tmp_path / ".semgrep-rules.json").read_text())["rules"]
    assert rules == ["p/typescript", "p/javascript", "p/sql-injection"]

    profile = json.loads(
        (tmp_path / ".template" / "project-profile.local.json").read_text()
    )
    assert profile["stack"]["semgrepRules"] == rules


def test_set_semgrep_config_no_stack_uses_fallback_rules(tmp_path) -> None:
    """No stack configured → broad fallback set, same header-only yml."""
    from tools.sdd_cli.environment_lab import set_semgrep_config

    _write_project_profile(
        tmp_path,
        {
            "frontend": {"value": ""},
            "backend": {"value": ""},
            "database": {"value": ""},
        },
    )
    result = set_semgrep_config(tmp_path, dry_run=False)

    assert result["valid"] is True
    yml = (tmp_path / ".semgrep.yml").read_text(encoding="utf-8")
    assert "# - p/" not in yml
    rules = json.loads((tmp_path / ".semgrep-rules.json").read_text())["rules"]
    assert rules == ["p/typescript", "p/javascript", "p/python", "p/csharp"]


def test_set_semgrep_config_dry_run_message_aligned(tmp_path) -> None:
    """Dry-run action no longer claims rule packs are written to .semgrep.yml."""
    from tools.sdd_cli.environment_lab import set_semgrep_config

    _write_project_profile(
        tmp_path,
        {
            "frontend": {"value": "react"},
            "backend": {"value": ""},
            "database": {"value": ""},
        },
    )
    result = set_semgrep_config(tmp_path, dry_run=True)

    assert result["valid"] is True
    yml_msg = next(
        a["message"]
        for a in result["actions"]
        if a["path"] == ".semgrep.yml" and a["key"] == "config.written"
    )
    assert ".semgrep.yml" in yml_msg
    assert "rule pack(s):" not in yml_msg
    assert not (tmp_path / ".semgrep.yml").exists()
    assert not (tmp_path / ".semgrep-rules.json").exists()


# ── prune_scaffold_shapes (ADR-0005 lifecycle) ─────────────────────────


def _write_scaffold_shape(tmp_path, rel: str) -> Path:
    """Materialize a fake scaffold shape dir under tmp_path."""
    shape = tmp_path / rel
    shape.mkdir(parents=True, exist_ok=True)
    (shape / "shape.txt").write_text("starting shape\n", encoding="utf-8")
    return shape


def _write_apps_json(tmp_path, apps: list[dict]) -> Path:
    apps_path = tmp_path / "infra" / "deployment" / "apps.json"
    apps_path.parent.mkdir(parents=True, exist_ok=True)
    apps_path.write_text(
        json.dumps({"version": 1, "apps": apps}), encoding="utf-8"
    )
    return apps_path


def test_prune_scaffold_removes_service_shape_for_service_app(tmp_path) -> None:
    """A registered service-kind app removes the apps/service shape."""
    from tools.sdd_cli.environment_lab import prune_scaffold_shapes

    _write_scaffold_shape(tmp_path, ".template/scaffold/apps/service")
    _write_apps_json(
        tmp_path,
        [
            {
                "appId": "api-orders",
                "projectPath": "apps/api-orders",
                "role": "api",
                "kind": "service",
                "healthPath": "/health",
                "deployOrder": 0,
            }
        ],
    )

    result = prune_scaffold_shapes(tmp_path, dry_run=False)

    assert result["valid"] is True
    assert not (tmp_path / ".template/scaffold/apps/service").exists()
    # Unrelated job shape untouched.
    assert (tmp_path / ".template/scaffold/apps/job").exists() is False
    assert any(
        a["key"] == "prune.removed"
        and ".template/scaffold/apps/service" in a["path"]
        for a in result["actions"]
    )


def test_prune_scaffold_removes_job_and_db_bootstrap_shapes(tmp_path) -> None:
    """A registered job-kind app removes apps/job; db-bootstrap removes its shape."""
    from tools.sdd_cli.environment_lab import prune_scaffold_shapes

    _write_scaffold_shape(tmp_path, ".template/scaffold/apps/job")
    _write_scaffold_shape(tmp_path, ".template/scaffold/db-bootstrap")
    _write_apps_json(
        tmp_path,
        [
            {
                "appId": "db-bootstrap",
                "projectPath": "apps/db-bootstrap",
                "role": "job",
                "kind": "job",
                "healthPath": "/",
                "deployOrder": 0,
            }
        ],
    )

    result = prune_scaffold_shapes(tmp_path, dry_run=False)

    assert result["valid"] is True
    assert not (tmp_path / ".template/scaffold/apps/job").exists()
    assert not (tmp_path / ".template/scaffold/db-bootstrap").exists()
    removed = {a["path"] for a in result["actions"] if a["key"] == "prune.removed"}
    assert removed == {
        ".template/scaffold/apps/job",
        ".template/scaffold/db-bootstrap",
    }


def test_prune_scaffold_keeps_shapes_when_no_apps(tmp_path) -> None:
    """Empty apps.json → no shape removed, audit action only."""
    from tools.sdd_cli.environment_lab import prune_scaffold_shapes

    _write_scaffold_shape(tmp_path, ".template/scaffold/apps/service")
    _write_scaffold_shape(tmp_path, ".template/scaffold/db-bootstrap")
    _write_apps_json(tmp_path, [])

    result = prune_scaffold_shapes(tmp_path, dry_run=False)

    assert result["valid"] is True
    assert (tmp_path / ".template/scaffold/apps/service").exists()
    assert (tmp_path / ".template/scaffold/db-bootstrap").exists()
    assert any(a["key"] == "prune.none" for a in result["actions"])


def test_prune_scaffold_dry_run_reports_without_deleting(tmp_path) -> None:
    """Dry-run: would-remove actions, shapes stay on disk."""
    from tools.sdd_cli.environment_lab import prune_scaffold_shapes

    service = _write_scaffold_shape(tmp_path, ".template/scaffold/apps/service")
    _write_apps_json(
        tmp_path,
        [
            {
                "appId": "web",
                "projectPath": "apps/web",
                "role": "web",
                "kind": "service",
                "healthPath": "/health",
                "deployOrder": 0,
            }
        ],
    )

    result = prune_scaffold_shapes(tmp_path, dry_run=True)

    assert result["valid"] is True
    assert service.exists()
    assert any(
        a["key"] == "prune.plan" and "Would remove" in a["message"]
        for a in result["actions"]
    )


def test_prune_scaffold_missing_shape_reports_already_pruned(tmp_path) -> None:
    """Shape already gone → audit action, no error."""
    from tools.sdd_cli.environment_lab import prune_scaffold_shapes

    _write_apps_json(
        tmp_path,
        [
            {
                "appId": "api",
                "projectPath": "apps/api",
                "role": "api",
                "kind": "service",
                "healthPath": "/health",
                "deployOrder": 0,
            }
        ],
    )

    result = prune_scaffold_shapes(tmp_path, dry_run=False)

    assert result["valid"] is True
    assert any(a["key"] == "prune.missing" for a in result["actions"])
