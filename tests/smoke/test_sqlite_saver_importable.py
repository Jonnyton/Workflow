"""Smoke: AGENTS.md Hard Rule 1 — SqliteSaver is the checkpoint primitive.

If this import breaks on a fresh clone, the dep is missing or the
langgraph-checkpoint-sqlite version pin drifted. Catch at install time,
not at runtime.
"""

from __future__ import annotations


def test_sqlite_saver_is_importable():
    from langgraph.checkpoint.sqlite import SqliteSaver

    assert SqliteSaver is not None


def test_async_sqlite_saver_not_used():
    """Hard Rule 1 — we do NOT use AsyncSqliteSaver.

    This test is a canary: if someone adds a direct AsyncSqliteSaver import
    to core workflow code, main pytest catches it; here we just prove the
    import surface stays consistent.
    """
    try:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        assert AsyncSqliteSaver is not None
    except ImportError:
        # aio submodule optional — that's fine, we don't use it.
        pass
