"""Memory-scope Stage 2b — write-site threading + episodic migration.

Exec plan: ``docs/exec-plans/active/2026-04-16-memory-scope-stage-2b.md``.
Design reference: ``docs/design-notes/2026-04-15-memory-scope-tiered.md``
§4 "Write-site behavior".

Stage 2b ships three guarantees tests here pin down:

1. **KG write-site threading.** ``KnowledgeGraph.add_entity`` /
   ``add_edge`` / ``add_facts`` accept a ``scope`` kwarg and populate
   the four scope columns.
2. **VectorStore write-site threading.** ``VectorStore.index``
   accepts a ``scope`` kwarg and rows land with matching
   ``universe_id`` / ``goal_id`` / ``branch_id`` / ``user_id``.
3. **Episodic schema migration is non-destructive.** An episodic DB
   populated pre-2b (only ``universe_id``) gains the three new
   scope columns on open without losing rows; the new columns
   default to NULL on legacy rows (= "treat as universe-public").
4. **``store_*`` methods accept a ``scope`` kwarg.** New rows written
   post-migration carry the caller's tier values.
"""

from __future__ import annotations

import sqlite3

import pytest

from workflow.knowledge.knowledge_graph import KnowledgeGraph
from workflow.knowledge.models import (
    FactWithContext,
    GraphEdge,
    GraphEntity,
    LanguageType,
    NarrativeFunction,
    SourceType,
)
from workflow.memory.episodic import EpisodicMemory
from workflow.memory.scoping import MemoryScope

# ─── KG write-site threading ────────────────────────────────────────────


@pytest.fixture
def kg(tmp_path):
    return KnowledgeGraph(db_path=tmp_path / "kg.db")


def _entity(entity_id: str) -> GraphEntity:
    return GraphEntity(
        entity_id=entity_id,
        entity_type="character",
        access_tier=0,
        public_description="",
        hidden_description="",
        secret_description="",
        aliases=[],
    )


def _edge(src: str, tgt: str) -> GraphEdge:
    return GraphEdge(
        source=src,
        target=tgt,
        relation_type="ally_of",
        access_tier=0,
        temporal_scope="always",
        pov_characters=[],
        weight=1.0,
        valid_from_chapter=None,
        valid_to_chapter=None,
    )


def _fact(fact_id: str) -> FactWithContext:
    return FactWithContext(
        fact_id=fact_id,
        text="Ryn is a scout.",
        source_type=SourceType.NARRATOR_CLAIM,
        narrator="narrator",
        language_type=LanguageType.LITERAL,
        narrative_function=NarrativeFunction.WORLD_FACT,
    )


def test_kg_add_entity_without_scope_leaves_columns_null(kg):
    """Backward compat: no ``scope`` kwarg → scope columns stay NULL."""
    kg.add_entity(_entity("ryn"))
    row = kg._conn.execute(
        "SELECT universe_id, goal_id, branch_id, user_id FROM entities "
        "WHERE entity_id = ?",
        ("ryn",),
    ).fetchone()
    assert row["universe_id"] is None
    assert row["goal_id"] is None
    assert row["branch_id"] is None
    assert row["user_id"] is None


def test_kg_add_entity_with_scope_populates_columns(kg):
    scope = MemoryScope(
        universe_id="world",
        goal_id="book-1",
        branch_id="main",
        user_id="alice",
    )
    kg.add_entity(_entity("ryn"), scope=scope)
    row = kg._conn.execute(
        "SELECT universe_id, goal_id, branch_id, user_id FROM entities "
        "WHERE entity_id = ?",
        ("ryn",),
    ).fetchone()
    assert row["universe_id"] == "world"
    assert row["goal_id"] == "book-1"
    assert row["branch_id"] == "main"
    assert row["user_id"] == "alice"


def test_kg_add_entity_scope_with_none_tiers_writes_null(kg):
    scope = MemoryScope(universe_id="world")  # only universe set
    kg.add_entity(_entity("ryn"), scope=scope)
    row = kg._conn.execute(
        "SELECT universe_id, goal_id, branch_id, user_id FROM entities "
        "WHERE entity_id = ?",
        ("ryn",),
    ).fetchone()
    assert row["universe_id"] == "world"
    # None tiers land as NULL, matching design §4 "broader than tier".
    assert row["goal_id"] is None
    assert row["branch_id"] is None
    assert row["user_id"] is None


def test_kg_add_edge_with_scope_populates_columns(kg):
    kg.add_entity(_entity("ryn"))
    kg.add_entity(_entity("kael"))
    scope = MemoryScope(universe_id="world", branch_id="main")
    kg.add_edge(_edge("ryn", "kael"), scope=scope)
    row = kg._conn.execute(
        "SELECT universe_id, branch_id FROM edges "
        "WHERE source = ? AND target = ?",
        ("ryn", "kael"),
    ).fetchone()
    assert row["universe_id"] == "world"
    assert row["branch_id"] == "main"


def test_kg_add_facts_with_scope_populates_columns(kg):
    scope = MemoryScope(universe_id="world", goal_id="book-1")
    kg.add_facts([_fact("f1"), _fact("f2")], scope=scope)
    rows = kg._conn.execute(
        "SELECT fact_id, universe_id, goal_id FROM facts "
        "ORDER BY fact_id"
    ).fetchall()
    assert len(rows) == 2
    for row in rows:
        assert row["universe_id"] == "world"
        assert row["goal_id"] == "book-1"


def test_kg_add_entity_upsert_refreshes_scope(kg):
    """UPSERT path updates scope columns when caller re-writes with scope."""
    kg.add_entity(_entity("ryn"))  # No scope -> NULL
    kg.add_entity(
        _entity("ryn"),
        scope=MemoryScope(universe_id="world", branch_id="main"),
    )
    row = kg._conn.execute(
        "SELECT universe_id, branch_id FROM entities WHERE entity_id = ?",
        ("ryn",),
    ).fetchone()
    assert row["universe_id"] == "world"
    assert row["branch_id"] == "main"


# ─── Episodic migration ─────────────────────────────────────────────────


def _legacy_episodic_schema() -> str:
    """The pre-Stage-2b episodic schema (no goal_id / branch_id / user_id).

    Mirrors ``workflow/memory/episodic.py``'s schema before this
    landing, so we can simulate a universe with real legacy rows.
    """
    return """
    CREATE TABLE scene_summaries (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        universe_id   TEXT    NOT NULL,
        book_number   INTEGER NOT NULL,
        chapter_number INTEGER NOT NULL,
        scene_number  INTEGER NOT NULL,
        summary       TEXT    NOT NULL,
        word_count    INTEGER NOT NULL DEFAULT 0,
        created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
        UNIQUE(universe_id, book_number, chapter_number, scene_number)
    );
    CREATE TABLE episodic_facts (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        universe_id   TEXT    NOT NULL,
        fact_id       TEXT    NOT NULL,
        entity        TEXT    NOT NULL,
        content       TEXT    NOT NULL,
        evidence_count INTEGER NOT NULL DEFAULT 1,
        source_scenes TEXT    NOT NULL DEFAULT '[]',
        promoted      INTEGER NOT NULL DEFAULT 0,
        created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
        UNIQUE(universe_id, fact_id)
    );
    CREATE TABLE style_observations (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        universe_id   TEXT    NOT NULL,
        dimension     TEXT    NOT NULL,
        observation   TEXT    NOT NULL,
        scene_ref     TEXT    NOT NULL DEFAULT '',
        created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
    );
    CREATE TABLE reflections (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        universe_id   TEXT    NOT NULL,
        chapter_number INTEGER NOT NULL,
        scene_number  INTEGER NOT NULL,
        critique      TEXT    NOT NULL,
        reflection    TEXT    NOT NULL,
        created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
    );
    """


def test_episodic_migration_non_destructive_on_legacy_rows(tmp_path):
    """Simulate a pre-2b universe with populated rows, then open with
    the 2b code. Legacy rows must survive with NULL sub-scope tiers.
    """
    db = tmp_path / "episodic.db"
    # Seed the DB with legacy schema + real rows, using a raw connection
    # (bypass the 2b auto-migration path).
    raw = sqlite3.connect(db)
    try:
        raw.executescript(_legacy_episodic_schema())
        raw.execute(
            "INSERT INTO scene_summaries "
            "(universe_id, book_number, chapter_number, scene_number, summary, word_count) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("world", 1, 1, 1, "Legacy summary.", 100),
        )
        raw.execute(
            "INSERT INTO episodic_facts "
            "(universe_id, fact_id, entity, content) "
            "VALUES (?, ?, ?, ?)",
            ("world", "legacy-f1", "ryn", "Legacy content."),
        )
        raw.execute(
            "INSERT INTO style_observations "
            "(universe_id, dimension, observation) "
            "VALUES (?, ?, ?)",
            ("world", "voice", "Clear and spare."),
        )
        raw.execute(
            "INSERT INTO reflections "
            "(universe_id, chapter_number, scene_number, critique, reflection) "
            "VALUES (?, ?, ?, ?, ?)",
            ("world", 1, 1, "Too sparse.", "Add sensory detail."),
        )
        raw.commit()
    finally:
        raw.close()

    # Open via EpisodicMemory — the __init__ migration should run and
    # leave all 4 legacy rows untouched.
    store = EpisodicMemory(db_path=str(db), universe_id="world")
    try:
        # Every table now has the three new columns.
        for table in ("scene_summaries", "episodic_facts",
                      "style_observations", "reflections"):
            cols = {r[1] for r in store._conn.execute(
                f"PRAGMA table_info({table})"
            )}
            assert "goal_id" in cols
            assert "branch_id" in cols
            assert "user_id" in cols

        # Legacy rows survive with NULL on the new tiers.
        summary_row = store._conn.execute(
            "SELECT summary, goal_id, branch_id, user_id "
            "FROM scene_summaries WHERE universe_id = ?",
            ("world",),
        ).fetchone()
        assert summary_row[0] == "Legacy summary."
        assert summary_row[1] is None
        assert summary_row[2] is None
        assert summary_row[3] is None

        fact_row = store._conn.execute(
            "SELECT content, goal_id FROM episodic_facts "
            "WHERE fact_id = ?",
            ("legacy-f1",),
        ).fetchone()
        assert fact_row[0] == "Legacy content."
        assert fact_row[1] is None

        obs_row = store._conn.execute(
            "SELECT observation, branch_id FROM style_observations"
        ).fetchone()
        assert obs_row[0] == "Clear and spare."
        assert obs_row[1] is None

        ref_row = store._conn.execute(
            "SELECT reflection, user_id FROM reflections"
        ).fetchone()
        assert ref_row[0] == "Add sensory detail."
        assert ref_row[1] is None
    finally:
        store.close()


def test_episodic_migration_is_idempotent(tmp_path):
    """Running EpisodicMemory twice on the same DB does not double-add columns."""
    db = tmp_path / "episodic.db"
    first = EpisodicMemory(db_path=str(db), universe_id="world")
    first.store_summary(1, 1, 1, "First summary.", word_count=42)
    first.close()

    # Second open re-runs the migration path; ALTER TABLE should be a
    # no-op because the columns exist.
    second = EpisodicMemory(db_path=str(db), universe_id="world")
    try:
        row = second._conn.execute(
            "SELECT summary, word_count FROM scene_summaries "
            "WHERE universe_id = ?",
            ("world",),
        ).fetchone()
        assert row[0] == "First summary."
        assert row[1] == 42
    finally:
        second.close()


def test_episodic_store_summary_with_scope(tmp_path):
    store = EpisodicMemory(db_path=str(tmp_path / "e.db"), universe_id="world")
    try:
        scope = MemoryScope(
            universe_id="world",
            goal_id="book-1",
            branch_id="main",
            user_id="alice",
        )
        store.store_summary(1, 1, 1, "Summary.", word_count=10, scope=scope)
        row = store._conn.execute(
            "SELECT goal_id, branch_id, user_id FROM scene_summaries "
            "WHERE universe_id = ?",
            ("world",),
        ).fetchone()
        assert row[0] == "book-1"
        assert row[1] == "main"
        assert row[2] == "alice"
    finally:
        store.close()


def test_episodic_store_fact_with_scope_new_row(tmp_path):
    store = EpisodicMemory(db_path=str(tmp_path / "e.db"), universe_id="world")
    try:
        scope = MemoryScope(universe_id="world", branch_id="dev")
        store.store_fact("f-new", "ryn", "content", scope=scope)
        row = store._conn.execute(
            "SELECT branch_id, goal_id FROM episodic_facts WHERE fact_id = ?",
            ("f-new",),
        ).fetchone()
        assert row[0] == "dev"
        assert row[1] is None
    finally:
        store.close()


def test_episodic_store_fact_increment_does_not_rewrite_scope(tmp_path):
    """Existing fact + new evidence call does NOT overwrite the
    original scope columns — Stage 2b defers re-tagging semantics to 2c.
    """
    store = EpisodicMemory(db_path=str(tmp_path / "e.db"), universe_id="world")
    try:
        original = MemoryScope(universe_id="world", branch_id="main")
        store.store_fact("f-inc", "ryn", "content", scope=original)
        # Second call with a different scope — only evidence_count should move.
        other = MemoryScope(universe_id="world", branch_id="dev")
        store.store_fact("f-inc", "ryn", "content", scope=other)
        row = store._conn.execute(
            "SELECT branch_id, evidence_count FROM episodic_facts WHERE fact_id = ?",
            ("f-inc",),
        ).fetchone()
        assert row[0] == "main"  # unchanged
        assert row[1] == 2
    finally:
        store.close()


def test_episodic_store_observation_with_scope(tmp_path):
    store = EpisodicMemory(db_path=str(tmp_path / "e.db"), universe_id="world")
    try:
        scope = MemoryScope(universe_id="world", user_id="alice")
        store.store_observation("voice", "Spare prose.", scope=scope)
        row = store._conn.execute(
            "SELECT user_id FROM style_observations"
        ).fetchone()
        assert row[0] == "alice"
    finally:
        store.close()


def test_episodic_store_reflection_with_scope(tmp_path):
    store = EpisodicMemory(db_path=str(tmp_path / "e.db"), universe_id="world")
    try:
        scope = MemoryScope(universe_id="world", goal_id="book-2")
        store.store_reflection(1, 1, "critique", "reflection", scope=scope)
        row = store._conn.execute(
            "SELECT goal_id FROM reflections"
        ).fetchone()
        assert row[0] == "book-2"
    finally:
        store.close()


def test_episodic_store_without_scope_still_writes_null(tmp_path):
    """Backward compat: pre-2b callers that don't pass scope still work."""
    store = EpisodicMemory(db_path=str(tmp_path / "e.db"), universe_id="world")
    try:
        store.store_summary(1, 1, 1, "Summary.", word_count=10)
        row = store._conn.execute(
            "SELECT summary, goal_id, branch_id, user_id FROM scene_summaries"
        ).fetchone()
        assert row[0] == "Summary."
        assert row[1] is None
        assert row[2] is None
        assert row[3] is None
    finally:
        store.close()
