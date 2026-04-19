"""Tests for Fix E's story.db derivative cleanup (task #49).

Covers the 2026-04-19 extension of `cleanup_drift_kg` that also drops
drift-keyed rows from the legacy story.db tables (`scene_history`,
`extracted_facts`, `character_states`, `promises`). Regression guard
for Mission 26 Probe B Branch B finding: 80+ orphan extracted_facts
rows + 3 scene_history tombstones + 9 residual character_states rows
after Fix E ran on echoes_of_the_cosmos.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from domains.fantasy_daemon.phases.drift_cleanup import (
    cleanup_drift_all,
    cleanup_drift_kg,
    cleanup_drift_story_db,
)

UNIVERSE = "echoes_of_the_cosmos"
DRIFT_SCENE_ID = f"{UNIVERSE}-B1-C1-S1"
DRIFT_CHUNK_ID = f"{UNIVERSE}-B1-C1-S1_chunk_0"
CANON_SCENE_ID = f"{UNIVERSE}-B1-C1-S1"  # intentionally same shape
NON_DRIFT_SCENE_ID = "first_chapter_final"  # canon-doc seeded_scene value


def _make_story_db(path: Path) -> sqlite3.Connection:
    """Create a story.db with the full schema. Returns the live conn."""
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE promises (
            id TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            importance REAL NOT NULL DEFAULT 0.5,
            created_scene TEXT NOT NULL,
            resolved_scene TEXT,
            created_chapter INTEGER NOT NULL DEFAULT 1,
            resolved_chapter INTEGER
        );
        CREATE TABLE character_states (
            character_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            location TEXT NOT NULL DEFAULT 'unknown',
            emotional_state TEXT NOT NULL DEFAULT 'neutral',
            knowledge_facts TEXT NOT NULL DEFAULT '[]',
            last_updated_scene TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE scene_history (
            scene_id TEXT PRIMARY KEY,
            universe_id TEXT NOT NULL,
            book_number INTEGER NOT NULL,
            chapter_number INTEGER NOT NULL,
            scene_number INTEGER NOT NULL,
            word_count INTEGER NOT NULL DEFAULT 0,
            verdict TEXT NOT NULL DEFAULT 'accept',
            summary TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE extracted_facts (
            fact_id TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            source_type TEXT NOT NULL DEFAULT 'narrator_claim',
            language_type TEXT NOT NULL DEFAULT 'literal',
            narrator TEXT,
            confidence REAL NOT NULL DEFAULT 0.5,
            scene_id TEXT NOT NULL,
            chapter_number INTEGER NOT NULL DEFAULT 1,
            importance REAL NOT NULL DEFAULT 0.5
        );
        """
    )
    conn.commit()
    return conn


def _make_kg_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE facts (
            fact_id TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            seeded_scene TEXT NOT NULL DEFAULT ''
        );
        """
    )
    conn.commit()
    return conn


@pytest.fixture
def story_db(tmp_path):
    path = tmp_path / "story.db"
    conn = _make_story_db(path)
    # Drift rows — all 4 tables.
    conn.execute(
        "INSERT INTO scene_history VALUES (?, ?, 1, 1, 1, 0, 'tombstone', '')",
        (DRIFT_SCENE_ID, UNIVERSE),
    )
    conn.execute(
        "INSERT INTO extracted_facts (fact_id, text, scene_id) VALUES (?, ?, ?)",
        ("drift-fact-1", "Kael stares at the stasis pod.", DRIFT_SCENE_ID),
    )
    conn.execute(
        "INSERT INTO extracted_facts (fact_id, text, scene_id) VALUES (?, ?, ?)",
        ("drift-fact-2", "Violet spirals churn in the void.", DRIFT_SCENE_ID),
    )
    conn.execute(
        "INSERT INTO character_states "
        "(character_id, name, last_updated_scene) VALUES (?, ?, ?)",
        ("kael", "Kael", DRIFT_SCENE_ID),
    )
    conn.execute(
        "INSERT INTO character_states "
        "(character_id, name, last_updated_scene) VALUES (?, ?, ?)",
        ("if_kael", "If Kael", DRIFT_SCENE_ID),  # NER garbage per Mission 26
    )
    conn.execute(
        "INSERT INTO promises VALUES (?, ?, 'active', 0.5, ?, NULL, 1, NULL)",
        ("drift-promise", "Someone will survive the stasis.", DRIFT_SCENE_ID),
    )
    # Canon rows (non-drift) — must survive cleanup.
    conn.execute(
        "INSERT INTO scene_history VALUES "
        "('canon-s1', ?, 1, 1, 1, 1200, 'accept', 'first canon scene')",
        (UNIVERSE,),
    )
    conn.execute(
        "INSERT INTO extracted_facts (fact_id, text, scene_id) VALUES (?, ?, ?)",
        ("canon-fact", "The ship enters orbit.", "canon-s1"),
    )
    conn.execute(
        "INSERT INTO character_states "
        "(character_id, name, last_updated_scene) VALUES (?, ?, ?)",
        ("real_character", "RealName", "canon-s1"),
    )
    conn.execute(
        "INSERT INTO promises VALUES (?, ?, 'active', 0.5, ?, NULL, 1, NULL)",
        ("canon-promise", "Reach the homeworld.", "canon-s1"),
    )
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def kg_db(tmp_path):
    path = tmp_path / "knowledge.db"
    conn = _make_kg_db(path)
    # Drift facts use the _chunk_ suffix per knowledge_graph.py schema.
    conn.execute(
        "INSERT INTO facts VALUES (?, ?, ?)",
        ("kg-drift-1", "drifted canon", DRIFT_CHUNK_ID),
    )
    conn.execute(
        "INSERT INTO facts VALUES (?, ?, ?)",
        ("kg-canon", "real canon", "first_chapter_final.md"),
    )
    conn.commit()
    conn.close()
    return path


# -------------------------------------------------------------------
# cleanup_drift_story_db
# -------------------------------------------------------------------


def test_drift_rows_removed_across_all_four_tables(story_db):
    result = cleanup_drift_story_db(UNIVERSE, str(story_db))

    assert result == {
        "scene_history_deleted": 1,
        "extracted_facts_deleted": 2,
        "character_states_deleted": 2,
        "promises_deleted": 1,
    }


def test_canon_rows_preserved(story_db):
    """Non-drift rows must remain untouched after cleanup."""
    cleanup_drift_story_db(UNIVERSE, str(story_db))

    conn = sqlite3.connect(str(story_db))
    try:
        assert conn.execute(
            "SELECT COUNT(*) FROM scene_history WHERE scene_id='canon-s1'"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM extracted_facts WHERE fact_id='canon-fact'"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM character_states WHERE character_id='real_character'"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM promises WHERE id='canon-promise'"
        ).fetchone()[0] == 1
    finally:
        conn.close()


def test_missing_story_db_returns_zeros(tmp_path):
    missing = tmp_path / "does_not_exist.db"

    result = cleanup_drift_story_db(UNIVERSE, str(missing))

    assert all(v == 0 for v in result.values())


def test_tables_missing_are_silently_skipped(tmp_path):
    """A story.db that hasn't created some tables yet must not raise."""
    partial = tmp_path / "partial.db"
    conn = sqlite3.connect(str(partial))
    conn.executescript(
        """
        CREATE TABLE scene_history (
            scene_id TEXT PRIMARY KEY,
            universe_id TEXT NOT NULL,
            book_number INTEGER NOT NULL,
            chapter_number INTEGER NOT NULL,
            scene_number INTEGER NOT NULL,
            word_count INTEGER DEFAULT 0,
            verdict TEXT DEFAULT 'accept',
            summary TEXT DEFAULT ''
        );
        """
    )
    conn.execute(
        "INSERT INTO scene_history VALUES (?, ?, 1, 1, 1, 0, 'x', '')",
        (DRIFT_SCENE_ID, UNIVERSE),
    )
    conn.commit()
    conn.close()

    # Only scene_history exists; the other tables are skipped, no crash.
    result = cleanup_drift_story_db(UNIVERSE, str(partial))

    assert result["scene_history_deleted"] == 1
    assert result["extracted_facts_deleted"] == 0
    assert result["character_states_deleted"] == 0
    assert result["promises_deleted"] == 0


def test_empty_universe_id_is_noop(story_db):
    result = cleanup_drift_story_db("", str(story_db))
    assert all(v == 0 for v in result.values())


def test_empty_db_path_is_noop():
    result = cleanup_drift_story_db(UNIVERSE, "")
    assert all(v == 0 for v in result.values())


# -------------------------------------------------------------------
# cleanup_drift_all — wrapper
# -------------------------------------------------------------------


def test_cleanup_drift_all_covers_both_dbs(story_db, kg_db):
    """Wrapper drops drift rows from both story.db AND knowledge.db."""
    result = cleanup_drift_all(UNIVERSE, str(kg_db), str(story_db))

    # Knowledge.db: 1 drift fact removed, 1 canon fact preserved.
    assert result["facts_deleted"] == 1
    # Story.db: counts from the story-db cleanup.
    assert result["scene_history_deleted"] == 1
    assert result["extracted_facts_deleted"] == 2
    assert result["character_states_deleted"] == 2
    assert result["promises_deleted"] == 1

    # Canon kg fact preserved.
    conn = sqlite3.connect(str(kg_db))
    try:
        assert conn.execute(
            "SELECT COUNT(*) FROM facts WHERE fact_id='kg-canon'"
        ).fetchone()[0] == 1
    finally:
        conn.close()


def test_cleanup_drift_kg_backward_compatible(kg_db):
    """Original KG-only cleanup still works the same."""
    result = cleanup_drift_kg(UNIVERSE, str(kg_db))

    assert result["facts_deleted"] == 1


# -------------------------------------------------------------------
# Integration: Fix E call site (worldbuild.py) uses cleanup_drift_all
# -------------------------------------------------------------------


def test_worldbuild_fix_e_uses_cleanup_drift_all():
    """Regression guard: the Fix E call site imports cleanup_drift_all
    rather than the KG-only cleanup_drift_kg. A future refactor that
    drops back to KG-only would re-introduce the Mission 26 finding.
    """
    # Read the module source directly — `phases.worldbuild` is a
    # function in the phases/__init__ re-export, not a submodule,
    # so inspect.getsource would only give the function body.
    repo_root = Path(__file__).resolve().parent.parent
    source_file = (
        repo_root / "domains" / "fantasy_daemon" / "phases" / "worldbuild.py"
    )
    src = source_file.read_text(encoding="utf-8")
    assert "cleanup_drift_all" in src, (
        "Fix E call site must import cleanup_drift_all, not the "
        "KG-only cleanup_drift_kg helper (Mission 26 regression guard)."
    )
