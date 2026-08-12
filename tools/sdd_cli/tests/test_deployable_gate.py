"""Regression tests for the package-deploy.yml "Check for deployable changes" gate.

The gate computes DEPLOYABLE for the deploy pipeline:

- workflow_dispatch with an explicit `artifact_commit_sha` (pinned QA approval /
  PROD promotion) is an **operator override** -> unconditionally deployable, even
  when the pinned commit's own delta is infra-only (e.g. a kustomize overlay fix).
- ref-head workflow_dispatch (no pin) keeps the first-parent src/test diff gate.
- PR-merge auto-deploys keep the same strict src/test diff gate.

These tests extract the REAL gate step (`run` script + step-level `env` mapping)
from `.gitea/workflows/package-deploy.yml`, render it with concrete event values the
way Gitea does, and execute it with bash in a scratch git repository — so any change
to the workflow's gate logic is caught here.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = REPO_ROOT / ".gitea" / "workflows" / "package-deploy.yml"

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None
    or shutil.which("bash") is None
    or shutil.which("python3") is None,
    reason="requires git, bash, and python3 on PATH to execute the workflow gate script",
)

# Repo-local identity + no signing/hooks so a developer's global git config
# (gpg signing, commit hooks, ...) can never break the scratch commits.
GIT_BASE = [
    "git",
    "-c",
    "user.name=sdd-gate-test",
    "-c",
    "user.email=sdd-gate-test@example.com",
    "-c",
    "commit.gpgsign=false",
    "-c",
    "core.hooksPath=/dev/null",
]


def _gate_step() -> dict:
    """Extract the deployable-changes gate step (run + env) from the workflow."""
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = data["jobs"]["build-and-deploy"]["steps"]
    return next(
        s for s in steps if s["name"].startswith("Check for deployable changes")
    )


def _git(repo: Path, env: dict, *args: str) -> str:
    result = subprocess.run(
        [*GIT_BASE, *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=True,
    )
    return result.stdout.strip()


def _commit(repo: Path, env: dict, message: str, files: dict[str, str]) -> str:
    for rel, content in files.items():
        dst = repo / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(content, encoding="utf-8")
    _git(repo, env, "add", "-A")
    _git(repo, env, "commit", "-qm", message)
    return _git(repo, env, "rev-parse", "HEAD")


@pytest.fixture(scope="module")
def gate_fixture(tmp_path_factory):
    """Scratch git repo + the real gate script.

    History:  A (root README) -> B (infra-only overlay fix) -> C (src change)
    so that B's first-parent diff is infra-only and C's first-parent diff (B..C)
    touches src/.
    """
    step = _gate_step()
    script = step["run"]
    env_template = step.get("env", {})
    repo = tmp_path_factory.mktemp("gate-repo")
    env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"}

    _git(repo, env, "init", "-q")
    _git(repo, env, "checkout", "-qb", "dev")

    _commit(repo, env, "chore: readme (root)", {"README.md": "hello\n"})
    infra_sha = _commit(
        repo,
        env,
        "fix: overlay nodePort (infra only)",
        {"infra/k8s/overlays/dev/service-patch.yaml": "nodePort: 30080\n"},
    )
    src_sha = _commit(
        repo,
        env,
        "feat: src change",
        {"src/app/main.txt": "x\n"},
    )

    return {
        "repo": repo,
        "env": env,
        "script": script,
        "env_template": env_template,
        "infra_sha": infra_sha,
        "src_sha": src_sha,
    }


def _run_gate(fixture: dict, event_name: str, pin: str, deploy_sha: str) -> str:
    """Render the gate step (run script + env mapping) and execute it in the repo."""
    script = (
        fixture["script"]
        .replace("${{ steps.sha.outputs.SHA }}", deploy_sha)
        .replace("${{ github.event_name }}", event_name)
    )
    # The workflow renders the dispatch input into the step-level PINNED_SHA env
    # var; render that mapping the same way Gitea would, then bash reads the
    # plain env var (no inline ${{ }} expression inside the script body).
    step_env = {
        name: value.replace("${{ github.event.inputs.artifact_commit_sha }}", pin)
        for name, value in fixture["env_template"].items()
    }
    # Drift guard: if the workflow ever renames the env var or the source
    # expression, the replace above would no-op and PINNED_SHA would hold a
    # literal non-empty "${{ ... }}" string — silently flipping tests. Fail
    # loudly instead.
    unresolved = [name for name, value in step_env.items() if "${{" in value]
    assert not unresolved, (
        f"gate step env vars still contain unresolved expressions: {unresolved} — "
        "the workflow no longer passes artifact_commit_sha via PINNED_SHA?"
    )
    with tempfile.TemporaryDirectory() as tmp:
        tdir = Path(tmp)
        out_file = tdir / "output.txt"
        script_path = tdir / "gate.sh"
        script_path.write_text(script, encoding="utf-8")
        env = {**fixture["env"], **step_env, "GITHUB_OUTPUT": str(out_file)}
        result = subprocess.run(
            ["bash", str(script_path)],
            cwd=fixture["repo"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
        )
        assert result.returncode == 0, f"gate script failed: {result.stderr}"
        output = out_file.read_text(encoding="utf-8") if out_file.exists() else ""
        deployable = next(
            (
                line.split("=", 1)[1]
                for line in output.splitlines()
                if line.startswith("DEPLOYABLE=")
            ),
            None,
        )
        assert deployable is not None, (
            f"DEPLOYABLE not written by gate; output={output!r}"
        )
        affected = next(
            (
                line.split("=", 1)[1]
                for line in output.splitlines()
                if line.startswith("AFFECTED_APPS=")
            ),
            None,
        )
        assert affected is not None, (
            f"AFFECTED_APPS not written by gate; output={output!r} — "
            "the gate no longer emits the app-aware mapping?"
        )
        return {"deployable": deployable, "affected": affected}


def test_pinned_dispatch_is_unconditionally_deployable(gate_fixture) -> None:
    """Explicit artifact_commit_sha (QA/PROD promotion) overrides the diff gate:
    an infra-only pinned commit must still deploy (regression: Run #18 skip), and
    every app is affected (AFFECTED_APPS=ALL — unconditional promotion)."""
    res = _run_gate(
        gate_fixture,
        event_name="workflow_dispatch",
        pin=gate_fixture["infra_sha"],
        deploy_sha=gate_fixture["infra_sha"],
    )
    assert res["deployable"] == "true"
    assert res["affected"] == "ALL"


def test_ref_head_dispatch_infra_only_is_skipped(gate_fixture) -> None:
    """Dispatch without a pin keeps the first-parent src/test diff gate:
    an infra-only head commit must NOT deploy."""
    res = _run_gate(
        gate_fixture,
        event_name="workflow_dispatch",
        pin="",
        deploy_sha=gate_fixture["infra_sha"],
    )
    assert res["deployable"] == "false"
    assert res["affected"] == ""


def test_pr_merge_src_change_is_deployable(gate_fixture) -> None:
    """PR-merge auto-deploy of a src-touching merge commit must deploy. The
    scratch repo has no apps.json and uses the legacy root src/ layout, so no
    app resolves — AFFECTED_APPS stays empty but the gate still fires on the
    generic (^|/)(src|test)/ match."""
    res = _run_gate(
        gate_fixture,
        event_name="pull_request",
        pin="",
        deploy_sha=gate_fixture["src_sha"],
    )
    assert res["deployable"] == "true"
    assert res["affected"] == ""


def test_pr_merge_infra_only_is_skipped(gate_fixture) -> None:
    """PR-merge auto-deploy keeps the strict gate: an infra-only merge commit
    (no src/test delta) must NOT deploy."""
    res = _run_gate(
        gate_fixture,
        event_name="pull_request",
        pin="",
        deploy_sha=gate_fixture["infra_sha"],
    )
    assert res["deployable"] == "false"
    assert res["affected"] == ""


# ── App-aware mapping (ADR-0002) ─────────────────────────────────────────


@pytest.fixture(scope="module")
def apps_gate_fixture(tmp_path_factory):
    """Scratch repo WITH apps.json: frontend (no deps) + backend (depends on
    shared-auth). History: A (base + apps.json) -> B (frontend src) ->
    C (packages/shared-auth) -> D (packages/shared-ui, no dependents)."""
    step = _gate_step()
    script = step["run"]
    env_template = step.get("env", {})
    repo = tmp_path_factory.mktemp("apps-gate-repo")
    env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"}

    _git(repo, env, "init", "-q")
    _git(repo, env, "checkout", "-qb", "dev")

    apps_json = json.dumps(
        {
            "version": 1,
            "apps": [
                {
                    "appId": "frontend",
                    "projectPath": "apps/frontend",
                    "role": "web",
                    "healthPath": "/health",
                    "deployOrder": 0,
                },
                {
                    "appId": "backend",
                    "projectPath": "apps/backend",
                    "role": "api",
                    "healthPath": "/health",
                    "deployOrder": 1,
                    "dependsOn": ["shared-auth"],
                },
            ],
        }
    )
    _commit(
        repo,
        env,
        "chore: base + apps.json",
        {"README.md": "hello\n", "infra/deployment/apps.json": apps_json},
    )
    frontend_sha = _commit(
        repo, env, "feat: frontend src", {"apps/frontend/src/app.txt": "x\n"}
    )
    packages_sha = _commit(
        repo,
        env,
        "feat: shared-auth change",
        {"packages/shared-auth/src/token.py": "x\n"},
    )
    orphan_pkg_sha = _commit(
        repo,
        env,
        "feat: shared-ui change (no dependents)",
        {"packages/shared-ui/src/button.py": "x\n"},
    )

    return {
        "repo": repo,
        "env": env,
        "script": script,
        "env_template": env_template,
        "frontend_sha": frontend_sha,
        "packages_sha": packages_sha,
        "orphan_pkg_sha": orphan_pkg_sha,
    }


def test_pr_merge_app_src_maps_to_that_app(apps_gate_fixture) -> None:
    """A change under apps/frontend/src maps to frontend only."""
    res = _run_gate(
        apps_gate_fixture,
        event_name="pull_request",
        pin="",
        deploy_sha=apps_gate_fixture["frontend_sha"],
    )
    assert res["deployable"] == "true"
    assert res["affected"] == "frontend"


def test_pr_merge_packages_change_maps_to_dependent_apps(apps_gate_fixture) -> None:
    """A packages/shared-auth change is deployable and affects only the app
    that declares the package in dependsOn (backend)."""
    res = _run_gate(
        apps_gate_fixture,
        event_name="pull_request",
        pin="",
        deploy_sha=apps_gate_fixture["packages_sha"],
    )
    assert res["deployable"] == "true"
    assert res["affected"] == "backend"


def test_pr_merge_packages_change_without_dependents_is_skipped(
    apps_gate_fixture,
) -> None:
    """A packages/shared-ui change (no app declares it) is NOT deployable and
    affects no app."""
    res = _run_gate(
        apps_gate_fixture,
        event_name="pull_request",
        pin="",
        deploy_sha=apps_gate_fixture["orphan_pkg_sha"],
    )
    assert res["deployable"] == "false"
    assert res["affected"] == ""


# ── Deploy-step manifest filter (ADR-0002) ───────────────────────────────


def _deploy_filter_script() -> str:
    """Extract the app-aware manifest filter python from the Deploy step.

    The filter is the first QUOTED heredoc (`<< 'PYEOF'`) in that step; the
    delete/health-gate heredocs use the unquoted marker.
    """
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = data["jobs"]["build-and-deploy"]["steps"]
    deploy = next(s for s in steps if s["name"] == "Deploy to K8s (all targets)")
    m = re.search(r"python3 << 'PYEOF'\n(.*?)\nPYEOF", deploy["run"], re.DOTALL)
    assert m, "manifest filter python not found in the Deploy step"
    return m.group(1)


SAMPLE_MANIFEST = (
    "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: frontend\n---\n"
    "apiVersion: v1\nkind: Service\nmetadata:\n  name: frontend\n---\n"
    "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: backend\n---\n"
    "apiVersion: v1\nkind: Service\nmetadata:\n  name: backend\n"
)


def _run_deploy_filter(script: str, tmp_path: Path, affected: str, manifest: str) -> str:
    """Run the extracted filter against a scratch manifest; returns the result."""
    path = tmp_path / "k8s-manifest.yaml"
    path.write_text(manifest, encoding="utf-8")
    patched = script.replace('"/tmp/k8s-manifest.yaml"', 'os.environ["K8S_MANIFEST"]')
    env = {**os.environ, "AFFECTED_APPS": affected, "K8S_MANIFEST": str(path)}
    subprocess.run(
        ["python3"],
        cwd=tmp_path,
        env=env,
        input=patched,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return path.read_text(encoding="utf-8")


def test_deploy_filter_keeps_only_affected_apps(tmp_path) -> None:
    """A filtered run keeps only the affected app's Deployment + Service."""
    out = _run_deploy_filter(
        _deploy_filter_script(), tmp_path, "frontend", SAMPLE_MANIFEST
    )
    assert "name: frontend" in out
    assert "name: backend" not in out


def test_deploy_filter_truncates_manifest_when_nothing_kept(tmp_path) -> None:
    """Regression guard: when no affected resource matches (empty AFFECTED_APPS),
    the filter must TRUNCATE the manifest so kubectl apply is skipped — never
    apply the stale full manifest with :latest tags."""
    out = _run_deploy_filter(_deploy_filter_script(), tmp_path, "", SAMPLE_MANIFEST)
    assert out.strip() == ""
