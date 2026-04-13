"""Phase 7.2 G2 — SqliteCachedBackend wired to git_bridge.

Covers the real behavior added by G2:

1. When ``git_bridge.is_enabled()`` is True and no hook is passed, the
   backend auto-wires ``git_bridge.stage`` so YAML writes land staged.
2. ``has_uncommitted_changes`` pre-check refuses to overwrite a file
   the user has uncommitted local edits to, unless ``force=True``.
3. When git is disabled, the backend behaves exactly as before — no
   errors, no false dirty-check refusals.

These tests run a real ``git init`` in ``tmp_path`` so they exercise
the actual contract instead of re-verifying the mock wiring.
"""

from __future__ import annotations

import importlib
import shutil
import subprocess
from pathlib import Path

import pytest

from workflow import git_bridge
from workflow.branches import BranchDefinition, NodeDefinition
from workflow.storage import (
    DirtyFileError,
    SqliteCachedBackend,
    YamlRepoLayout,
)

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git binary not available",
)


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True, check=True,
    )


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "--initial-branch=main"], path)
    _run(["git", "config", "user.email", "ci@example.invalid"], path)
    _run(["git", "config", "user.name", "CI Bot"], path)
    _run(["git", "config", "commit.gpgsign", "false"], path)
    # Seed commit so HEAD exists (has_uncommitted_changes diffs HEAD)
    (path / "README.md").write_text("seed\n", encoding="utf-8")
    _run(["git", "add", "README.md"], path)
    _run(["git", "commit", "-m", "seed", "--no-gpg-sign"], path)


@pytest.fixture(autouse=True)
def _reset_git_bridge_cache():
    git_bridge.invalidate_cache()
    yield
    git_bridge.invalidate_cache()


@pytest.fixture
def base_path(tmp_path, monkeypatch):
    base = tmp_path / "output"
    base.mkdir()
    monkeypatch.setenv("UNIVERSE_SERVER_BASE", str(base))
    monkeypatch.setenv("UNIVERSE_SERVER_USER", "tester")
    from workflow.author_server import initialize_author_server
    initialize_author_server(base)
    from workflow import universe_server as us
    importlib.reload(us)
    yield base


def _make_branch() -> BranchDefinition:
    b = BranchDefinition(
        name="Git-probe branch",
        description="Exercises the G2 stage hook + dirty check.",
        author="tester",
        entry_point="n1",
    )
    b.node_defs = [
        NodeDefinition(
            node_id="n1",
            display_name="Node one",
            prompt_template="echo: {x}",
            input_keys=["x"],
            output_keys=["y"],
        ),
    ]
    return b


# ─── git-enabled: auto-wire + stage ──────────────────────────────────────


def test_git_enabled_auto_wires_stage_hook(base_path, tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)

    backend = SqliteCachedBackend(base_path, repo_root=repo)
    assert backend._git_enabled is True, (
        "backend should detect the initialized repo"
    )
    saved = backend.save_branch(_make_branch())

    layout = YamlRepoLayout(repo)
    branch_path = layout.branch_path("git-probe-branch")
    assert branch_path.exists()

    # Real git: the file should be staged (in the index) after save
    staged = _run(
        ["git", "diff", "--name-only", "--cached"], repo,
    ).stdout.splitlines()
    assert any("git-probe-branch.yaml" in line for line in staged), (
        f"branch YAML should be staged; staged={staged}"
    )
    assert saved["branch_def_id"]


def test_git_enabled_refuses_dirty_overwrite(base_path, tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    backend = SqliteCachedBackend(base_path, repo_root=repo)

    # First save + commit to lock the file in git history
    backend.save_branch(_make_branch())
    _run(["git", "commit", "-m", "add branch", "--no-gpg-sign"], repo)

    # User manually edits the YAML file
    layout = YamlRepoLayout(repo)
    branch_path = layout.branch_path("git-probe-branch")
    branch_path.write_text(
        branch_path.read_text(encoding="utf-8") + "\n# user edit\n",
        encoding="utf-8",
    )
    assert git_bridge.has_uncommitted_changes(branch_path, repo_path=repo)

    # Second save with force=False must refuse
    with pytest.raises(DirtyFileError) as exc:
        backend.save_branch(_make_branch())
    assert branch_path in exc.value.paths


def test_git_enabled_force_overrides_dirty_check(base_path, tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    backend = SqliteCachedBackend(base_path, repo_root=repo)

    backend.save_branch(_make_branch())
    _run(["git", "commit", "-m", "add branch", "--no-gpg-sign"], repo)

    layout = YamlRepoLayout(repo)
    branch_path = layout.branch_path("git-probe-branch")
    branch_path.write_text("# user edit\n", encoding="utf-8")
    assert git_bridge.has_uncommitted_changes(branch_path, repo_path=repo)

    # force=True rewrites even when dirty
    b = _make_branch()
    b.description = "forced update"
    backend.save_branch(b, force=True)

    import yaml
    payload = yaml.safe_load(branch_path.read_text(encoding="utf-8"))
    assert payload["description"] == "forced update"


def test_dirty_check_happens_before_sqlite_write(
    base_path, tmp_path, monkeypatch,
):
    """A dirty refusal must not touch SQLite — otherwise backend state
    drifts from YAML state even though the user asked to bail."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    backend = SqliteCachedBackend(base_path, repo_root=repo)

    backend.save_branch(_make_branch())
    _run(["git", "commit", "-m", "add branch", "--no-gpg-sign"], repo)

    layout = YamlRepoLayout(repo)
    branch_path = layout.branch_path("git-probe-branch")
    branch_path.write_text("dirty\n", encoding="utf-8")

    calls: list[dict] = []

    def _track(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        raise AssertionError(
            "SQLite write should not run after dirty refusal"
        )

    monkeypatch.setattr(
        "workflow.author_server.save_branch_definition", _track,
    )
    with pytest.raises(DirtyFileError):
        backend.save_branch(_make_branch())
    assert calls == []


# ─── git-disabled: behaves like SqliteOnlyBackend ─────────────────────────


def test_git_disabled_skips_stage_and_dirty_check(base_path, tmp_path):
    """When the repo isn't a git repo, backend still works; dirty check
    is a no-op and stage hook is no-op."""
    repo = tmp_path / "not_a_repo"  # no git init
    backend = SqliteCachedBackend(base_path, repo_root=repo)
    assert backend._git_enabled is False

    # First save — fine
    backend.save_branch(_make_branch())
    layout = YamlRepoLayout(repo)
    branch_path = layout.branch_path("git-probe-branch")
    assert branch_path.exists()

    # Dirty the file; backend must NOT refuse (no git = can't tell)
    branch_path.write_text("# edit\n", encoding="utf-8")
    b = _make_branch()
    b.description = "updated"
    backend.save_branch(b)  # should not raise


def test_explicit_git_enabled_false_overrides_autodetect(
    base_path, tmp_path,
):
    """Caller can force git-disabled mode even inside a real repo."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    backend = SqliteCachedBackend(
        base_path, repo_root=repo, git_enabled=False,
    )
    assert backend._git_enabled is False

    backend.save_branch(_make_branch())
    # Nothing should be staged since the hook is no-op
    staged = _run(
        ["git", "diff", "--name-only", "--cached"], repo,
    ).stdout.strip()
    assert staged == ""


def test_explicit_stage_hook_wins_over_git(base_path, tmp_path):
    """If caller passes a stage_hook, backend uses that — git_bridge
    doesn't even get probed for the stage side."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    calls: list[Path] = []
    backend = SqliteCachedBackend(
        base_path, repo_root=repo, stage_hook=calls.append,
    )
    backend.save_branch(_make_branch())
    layout = YamlRepoLayout(repo)
    assert layout.branch_path("git-probe-branch") in calls


# ─── Goal save exercises the same contract ───────────────────────────────


def test_git_enabled_auto_wires_goal_stage(base_path, tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    backend = SqliteCachedBackend(base_path, repo_root=repo)
    saved = backend.save_goal({
        "name": "G2 probe goal",
        "author": "tester",
        "tags": ["test"],
    })
    layout = YamlRepoLayout(repo)
    goal_path = layout.goal_path("g2-probe-goal")
    assert goal_path.exists()
    staged = _run(
        ["git", "diff", "--name-only", "--cached"], repo,
    ).stdout.splitlines()
    assert any("g2-probe-goal.yaml" in line for line in staged)
    assert saved["goal_id"]


def test_goal_new_with_no_prior_slug_skips_dirty_check(base_path, tmp_path):
    """A goal with no id and no prior YAML file can never be 'dirty' —
    don't let an empty-slug probe panic."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    backend = SqliteCachedBackend(base_path, repo_root=repo)
    saved = backend.save_goal({
        "name": "Brand new goal",
        "author": "tester",
    })
    assert saved["goal_id"]
