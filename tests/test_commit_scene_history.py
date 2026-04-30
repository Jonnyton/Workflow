"""Tests for `_record_scene_verdict` — the commit pipeline's verdict writer.

Before this fix, `scene_history.verdict` was written as `"pending"` by
`_update_world_state` BEFORE the verdict was computed, and nothing ever
updated the row. On sporemarch this left every committed scene marked
`pending`, which meant `accept_rate` telemetry read as 0/0 despite 30+
scenes on disk.

The fix separates the two concerns:
- `_update_world_state` writes facts/promises/characters (pre-verdict, fine).
- `_record_scene_verdict` writes scene_history AFTER the verdict is computed.

These tests exercise the new contract directly without needing a full
LangGraph run.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from domains.fantasy_daemon.phases.commit import _record_scene_verdict
from domains.fantasy_daemon.phases.world_state_db import init_db


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "story.db")


def test_records_scene_with_real_verdict(db_path: str) -> None:
    _record_scene_verdict(
        db_path=db_path,
        scene_id="u-B1-C2-S3",
        state={
            "universe_id": "u",
            "book_number": 1,
            "chapter_number": 2,
            "scene_number": 3,
        },
        word_count=1500,
        verdict="accept",
    )

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT scene_id, verdict, word_count, chapter_number "
        "FROM scene_history WHERE scene_id=?",
        ("u-B1-C2-S3",),
    ).fetchone()
    conn.close()

    assert row is not None
    assert row[0] == "u-B1-C2-S3"
    assert row[1] == "accept"
    assert row[2] == 1500
    assert row[3] == 2


def test_replaces_pending_row_with_committed_verdict(db_path: str) -> None:
    """If an earlier pipeline left a `pending` row (e.g. legacy data or a
    second_draft re-commit), the new verdict must OVERWRITE it, not leave
    both rows in place.
    """
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO scene_history "
        "(scene_id, universe_id, book_number, chapter_number, scene_number, "
        "word_count, verdict, summary) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("u-B1-C1-S1", "u", 1, 1, 1, 0, "pending", ""),
    )
    conn.commit()
    conn.close()

    _record_scene_verdict(
        db_path=db_path,
        scene_id="u-B1-C1-S1",
        state={
            "universe_id": "u", "book_number": 1,
            "chapter_number": 1, "scene_number": 1,
        },
        word_count=1200,
        verdict="accept",
    )

    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT verdict, word_count FROM scene_history WHERE scene_id=?",
        ("u-B1-C1-S1",),
    ).fetchall()
    conn.close()

    assert len(rows) == 1
    assert rows[0][0] == "accept"
    assert rows[0][1] == 1200


def test_different_verdicts_persist(db_path: str) -> None:
    """accept_rate telemetry depends on the verdict column — so rejects,
    second_drafts, and reverts must all be distinguishable in the row.
    """
    for i, verdict in enumerate(["accept", "second_draft", "revert"]):
        _record_scene_verdict(
            db_path=db_path,
            scene_id=f"u-B1-C1-S{i}",
            state={
                "universe_id": "u", "book_number": 1,
                "chapter_number": 1, "scene_number": i,
            },
            word_count=1000 + i,
            verdict=verdict,
        )

    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT verdict, COUNT(*) FROM scene_history GROUP BY verdict",
    ).fetchall()
    conn.close()

    counts = dict(rows)
    assert counts == {"accept": 1, "second_draft": 1, "revert": 1}


def test_db_failure_is_swallowed(db_path: str, tmp_path: Path) -> None:
    """The commit verdict must never fail because of a DB issue. This
    matches the existing `_update_world_state` contract — commit returns
    the verdict to the graph even when persistence can't keep up.
    """
    # Point at a path inside a regular file so the DB open raises
    (tmp_path / "not_a_dir").write_text("blocker", encoding="utf-8")
    bogus_db = str(tmp_path / "not_a_dir" / "story.db")

    # Does not raise — logs a warning and returns normally.
    _record_scene_verdict(
        db_path=bogus_db,
        scene_id="x",
        state={"universe_id": "u", "book_number": 1, "chapter_number": 1, "scene_number": 1},
        word_count=0,
        verdict="accept",
    )
