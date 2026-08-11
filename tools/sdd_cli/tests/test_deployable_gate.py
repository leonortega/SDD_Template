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

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = REPO_ROOT / ".gitea" / "workflows" / "package-deploy.yml"

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="requires git and bash on PATH to execute the workflow gate script",
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
        return deployable


def test_pinned_dispatch_is_unconditionally_deployable(gate_fixture) -> None:
    """Explicit artifact_commit_sha (QA/PROD promotion) overrides the diff gate:
    an infra-only pinned commit must still deploy (regression: Run #18 skip)."""
    dep = _run_gate(
        gate_fixture,
        event_name="workflow_dispatch",
        pin=gate_fixture["infra_sha"],
        deploy_sha=gate_fixture["infra_sha"],
    )
    assert dep == "true"


def test_ref_head_dispatch_infra_only_is_skipped(gate_fixture) -> None:
    """Dispatch without a pin keeps the first-parent src/test diff gate:
    an infra-only head commit must NOT deploy."""
    dep = _run_gate(
        gate_fixture,
        event_name="workflow_dispatch",
        pin="",
        deploy_sha=gate_fixture["infra_sha"],
    )
    assert dep == "false"


def test_pr_merge_src_change_is_deployable(gate_fixture) -> None:
    """PR-merge auto-deploy of a src-touching merge commit must deploy."""
    dep = _run_gate(
        gate_fixture,
        event_name="pull_request",
        pin="",
        deploy_sha=gate_fixture["src_sha"],
    )
    assert dep == "true"


def test_pr_merge_infra_only_is_skipped(gate_fixture) -> None:
    """PR-merge auto-deploy keeps the strict gate: an infra-only merge commit
    (no src/test delta) must NOT deploy."""
    dep = _run_gate(
        gate_fixture,
        event_name="pull_request",
        pin="",
        deploy_sha=gate_fixture["infra_sha"],
    )
    assert dep == "false"
