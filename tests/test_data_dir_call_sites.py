"""Row B cleanup: regression guard for the two call sites that were
bypassing ``workflow.storage.data_dir()``.

Pre-Row-B-cleanup state:
    workflow/auth/provider.py:192 → direct UNIVERSE_SERVER_BASE env read.
    workflow/node_eval.py:160     → direct UNIVERSE_SERVER_BASE env read.

Both defaulted to CWD-relative ``output`` → /app/output in a container
→ ephemeral writes lost on restart. Auth sessions specifically: users
had to re-authenticate after every container restart.

These tests prove both call sites now honor ``$WORKFLOW_DATA_DIR``.
The pre-commit hook (invariant 5) prevents the bypass pattern from
re-emerging structurally; this test catches semantic regressions at
the call site level.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def clean_env(monkeypatch):
    """Strip env vars the resolver reads so each test starts at zero."""
    for name in ("WORKFLOW_DATA_DIR", "UNIVERSE_SERVER_BASE", "WORKFLOW_DEPRECATIONS"):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_auth_provider_honors_workflow_data_dir(clean_env, tmp_path):
    """OAuthProvider's default db_path routes through data_dir()."""
    target = tmp_path / "auth-root"
    clean_env.setenv("WORKFLOW_DATA_DIR", str(target))

    from workflow.auth import provider

    ap = provider.OAuthProvider()
    db_path = ap._db_path
    assert db_path.parent.resolve() == target.resolve(), (
        f"OAuthProvider db not rooted at WORKFLOW_DATA_DIR: "
        f"got {db_path.parent.resolve()!r}, expected {target.resolve()!r}"
    )
    assert db_path.name == ".auth.db"


def test_node_evaluator_honors_workflow_data_dir(clean_env, tmp_path):
    """NodeEvaluator's default db_path routes through data_dir()."""
    target = tmp_path / "eval-root"
    clean_env.setenv("WORKFLOW_DATA_DIR", str(target))

    from workflow.node_eval import NodeEvaluator

    ne = NodeEvaluator()
    db_path = ne._db_path
    assert db_path.parent.resolve() == target.resolve(), (
        f"NodeEvaluator db not rooted at WORKFLOW_DATA_DIR: "
        f"got {db_path.parent.resolve()!r}, expected {target.resolve()!r}"
    )
    assert db_path.name == ".node_eval.db"


def test_auth_provider_absolute_even_without_env(clean_env, tmp_path):
    """No env → resolver default → still absolute (no CWD drift)."""
    from workflow.auth import provider

    ap = provider.OAuthProvider()
    assert ap._db_path.is_absolute(), (
        "OAuthProvider.db_path is not absolute — container CWD-drift risk"
    )


def test_node_evaluator_absolute_even_without_env(clean_env, tmp_path):
    """No env → resolver default → still absolute (no CWD drift)."""
    from workflow.node_eval import NodeEvaluator

    ne = NodeEvaluator()
    assert ne._db_path.is_absolute(), (
        "NodeEvaluator.db_path is not absolute — container CWD-drift risk"
    )


def test_explicit_db_path_still_works(clean_env, tmp_path):
    """Caller-supplied db_path is respected (constructor injection still works)."""
    from workflow.auth import provider

    override = tmp_path / "explicit.db"
    ap = provider.OAuthProvider(db_path=override)
    assert ap._db_path == override


def test_legacy_env_still_honored(clean_env, tmp_path):
    """UNIVERSE_SERVER_BASE legacy alias still resolves via data_dir()."""
    target = tmp_path / "legacy-root"
    clean_env.setenv("UNIVERSE_SERVER_BASE", str(target))

    from workflow.auth import provider

    ap = provider.OAuthProvider()
    assert ap._db_path.parent.resolve() == target.resolve()
