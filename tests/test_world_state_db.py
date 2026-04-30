"""Tests for the world state database (domains.fantasy_daemon.phases.world_state_db).

Covers: schema init, promise CRUD, character CRUD, scene history,
fact storage, pacing flags, and edge cases.
"""

from __future__ import annotations

from domains.fantasy_daemon.phases.world_state_db import (
    add_promise,
    compute_pacing_flags,
    connect,
    get_active_promises,
    get_all_characters,
    get_all_facts,
    get_chapter_scene_count,
    get_chapter_word_count,
    get_character,
    get_character_gaps,
    get_facts_for_chapter,
    get_overdue_promises,
    get_recent_scenes,
    init_db,
    record_scene,
    resolve_promise,
    store_fact,
    upsert_character,
)

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class TestInitDB:
    def test_creates_tables_in_memory(self):
        init_db(":memory:")

    def test_idempotent(self, tmp_story_db):
        init_db(tmp_story_db)
        init_db(tmp_story_db)  # Should not raise

    def test_tables_exist_after_init(self, tmp_story_db):
        init_db(tmp_story_db)
        with connect(tmp_story_db) as conn:
            tables = [
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            ]
        assert "promises" in tables
        assert "character_states" in tables
        assert "scene_history" in tables
        assert "extracted_facts" in tables


# ---------------------------------------------------------------------------
# Promises
# ---------------------------------------------------------------------------


class TestPromises:
    def test_add_and_get_active(self, tmp_story_db):
        init_db(tmp_story_db)
        with connect(tmp_story_db) as conn:
            add_promise(
                conn,
                promise_id="p1",
                text="The sword will be found.",
                created_scene="s1",
                created_chapter=1,
                importance=0.8,
            )
            active = get_active_promises(conn)
        assert len(active) == 1
        assert active[0]["id"] == "p1"
        assert active[0]["status"] == "active"

    def test_resolve_promise(self, tmp_story_db):
        init_db(tmp_story_db)
        with connect(tmp_story_db) as conn:
            add_promise(
                conn,
                promise_id="p1",
                text="Mystery revealed.",
                created_scene="s1",
                created_chapter=1,
            )
            resolve_promise(
                conn,
                promise_id="p1",
                resolved_scene="s5",
                resolved_chapter=3,
            )
            active = get_active_promises(conn)
        assert len(active) == 0

    def test_overdue_promises(self, tmp_story_db):
        init_db(tmp_story_db)
        with connect(tmp_story_db) as conn:
            add_promise(
                conn,
                promise_id="p1",
                text="Old promise.",
                created_scene="s1",
                created_chapter=1,
                importance=0.6,
            )
            add_promise(
                conn,
                promise_id="p2",
                text="Recent promise.",
                created_scene="s10",
                created_chapter=8,
                importance=0.5,
            )
            overdue = get_overdue_promises(conn, current_chapter=10, overdue_threshold=3)
        # p1 (ch1) is overdue at ch10; p2 (ch8) is only 2 chapters old
        assert len(overdue) == 1
        assert overdue[0]["id"] == "p1"

    def test_no_overdue_when_none_exist(self, tmp_story_db):
        init_db(tmp_story_db)
        with connect(tmp_story_db) as conn:
            overdue = get_overdue_promises(conn, current_chapter=1)
        assert overdue == []

    def test_promises_ordered_by_importance(self, tmp_story_db):
        init_db(tmp_story_db)
        with connect(tmp_story_db) as conn:
            add_promise(
                conn, promise_id="p1", text="Low", created_scene="s1",
                created_chapter=1, importance=0.2,
            )
            add_promise(
                conn, promise_id="p2", text="High", created_scene="s1",
                created_chapter=1, importance=0.9,
            )
            active = get_active_promises(conn)
        assert active[0]["id"] == "p2"
        assert active[1]["id"] == "p1"


# ---------------------------------------------------------------------------
# Characters
# ---------------------------------------------------------------------------


class TestCharacters:
    def test_upsert_and_get(self, tmp_story_db):
        init_db(tmp_story_db)
        with connect(tmp_story_db) as conn:
            upsert_character(
                conn,
                character_id="ryn",
                name="Ryn",
                location="Ashwater",
                emotional_state="determined",
                knowledge_facts=["f1", "f2"],
                last_updated_scene="s1",
            )
            char = get_character(conn, "ryn")
        assert char is not None
        assert char["name"] == "Ryn"
        assert char["location"] == "Ashwater"
        assert char["knowledge_facts"] == ["f1", "f2"]

    def test_upsert_overwrites(self, tmp_story_db):
        init_db(tmp_story_db)
        with connect(tmp_story_db) as conn:
            upsert_character(
                conn, character_id="ryn", name="Ryn",
                location="North Gate", last_updated_scene="s1",
            )
            upsert_character(
                conn, character_id="ryn", name="Ryn",
                location="South Bridge", last_updated_scene="s2",
            )
            char = get_character(conn, "ryn")
        assert char["location"] == "South Bridge"

    def test_get_nonexistent_character(self, tmp_story_db):
        init_db(tmp_story_db)
        with connect(tmp_story_db) as conn:
            assert get_character(conn, "nobody") is None

    def test_get_all_characters(self, tmp_story_db):
        init_db(tmp_story_db)
        with connect(tmp_story_db) as conn:
            upsert_character(conn, character_id="a", name="Alice")
            upsert_character(conn, character_id="b", name="Bob")
            chars = get_all_characters(conn)
        assert len(chars) == 2

    def test_character_gaps_unknown_location(self, tmp_story_db):
        init_db(tmp_story_db)
        with connect(tmp_story_db) as conn:
            upsert_character(
                conn, character_id="ryn", name="Ryn",
                location="unknown", emotional_state="determined",
            )
            upsert_character(
                conn, character_id="kael", name="Kael",
                location="Ashwater", emotional_state="neutral",
            )
            gaps = get_character_gaps(conn)
        assert len(gaps) == 2  # Both have at least one gap

    def test_character_gaps_filtered(self, tmp_story_db):
        init_db(tmp_story_db)
        with connect(tmp_story_db) as conn:
            upsert_character(
                conn, character_id="ryn", name="Ryn",
                location="unknown",
            )
            upsert_character(
                conn, character_id="kael", name="Kael",
                location="Ashwater", emotional_state="happy",
            )
            gaps = get_character_gaps(conn, scene_characters=["ryn"])
        assert len(gaps) == 1
        assert gaps[0]["character_id"] == "ryn"


# ---------------------------------------------------------------------------
# Scene history
# ---------------------------------------------------------------------------


class TestSceneHistory:
    def test_record_and_get_recent(self, tmp_story_db):
        init_db(tmp_story_db)
        with connect(tmp_story_db) as conn:
            record_scene(
                conn,
                scene_id="s1", universe_id="u1", book_number=1,
                chapter_number=1, scene_number=1, word_count=1000,
                verdict="accept",
            )
            record_scene(
                conn,
                scene_id="s2", universe_id="u1", book_number=1,
                chapter_number=1, scene_number=2, word_count=800,
                verdict="accept",
            )
            recent = get_recent_scenes(conn, chapter_number=1, limit=5)
        assert len(recent) == 2
        # Most recent first (scene 2)
        assert recent[0]["scene_id"] == "s2"

    def test_chapter_scene_count(self, tmp_story_db):
        init_db(tmp_story_db)
        with connect(tmp_story_db) as conn:
            record_scene(
                conn, scene_id="s1", universe_id="u1", book_number=1,
                chapter_number=1, scene_number=1, word_count=500,
            )
            record_scene(
                conn, scene_id="s2", universe_id="u1", book_number=1,
                chapter_number=1, scene_number=2, word_count=500,
            )
            count = get_chapter_scene_count(conn, 1)
        assert count == 2

    def test_chapter_word_count(self, tmp_story_db):
        init_db(tmp_story_db)
        with connect(tmp_story_db) as conn:
            record_scene(
                conn, scene_id="s1", universe_id="u1", book_number=1,
                chapter_number=1, scene_number=1, word_count=500,
            )
            record_scene(
                conn, scene_id="s2", universe_id="u1", book_number=1,
                chapter_number=1, scene_number=2, word_count=700,
            )
            wc = get_chapter_word_count(conn, 1)
        assert wc == 1200

    def test_empty_chapter_counts(self, tmp_story_db):
        init_db(tmp_story_db)
        with connect(tmp_story_db) as conn:
            assert get_chapter_scene_count(conn, 99) == 0
            assert get_chapter_word_count(conn, 99) == 0


# ---------------------------------------------------------------------------
# Extracted facts
# ---------------------------------------------------------------------------


class TestFacts:
    def test_store_and_retrieve(self, tmp_story_db):
        init_db(tmp_story_db)
        with connect(tmp_story_db) as conn:
            store_fact(
                conn,
                fact_id="f1",
                text="Ryn is a Glass-Singer.",
                source_type="narrator_claim",
                language_type="literal",
                scene_id="s1",
                chapter_number=1,
                importance=0.8,
            )
            facts = get_facts_for_chapter(conn, 1)
        assert len(facts) == 1
        assert facts[0]["text"] == "Ryn is a Glass-Singer."

    def test_get_all_facts(self, tmp_story_db):
        init_db(tmp_story_db)
        with connect(tmp_story_db) as conn:
            store_fact(conn, fact_id="f1", text="Fact one", scene_id="s1")
            store_fact(
                conn, fact_id="f2", text="Fact two", scene_id="s2",
                chapter_number=2,
            )
            all_facts = get_all_facts(conn)
        assert len(all_facts) == 2


# ---------------------------------------------------------------------------
# Pacing flags
# ---------------------------------------------------------------------------


class TestPacingFlags:
    def test_chapter_opening_flag(self, tmp_story_db):
        init_db(tmp_story_db)
        with connect(tmp_story_db) as conn:
            flags = compute_pacing_flags(conn, current_chapter=1, current_scene=1)
        assert any(f["type"] == "chapter_opening" for f in flags)

    def test_long_chapter_flag(self, tmp_story_db):
        init_db(tmp_story_db)
        with connect(tmp_story_db) as conn:
            for i in range(7):
                record_scene(
                    conn, scene_id=f"s{i}", universe_id="u1",
                    book_number=1, chapter_number=1, scene_number=i + 1,
                    word_count=1000,
                )
            flags = compute_pacing_flags(conn, current_chapter=1, current_scene=8)
        assert any(f["type"] == "pacing_long_chapter" for f in flags)

    def test_short_scenes_flag(self, tmp_story_db):
        init_db(tmp_story_db)
        with connect(tmp_story_db) as conn:
            for i in range(3):
                record_scene(
                    conn, scene_id=f"s{i}", universe_id="u1",
                    book_number=1, chapter_number=1, scene_number=i + 1,
                    word_count=200,  # Well below 1000 target
                )
            flags = compute_pacing_flags(conn, current_chapter=1, current_scene=4)
        assert any(f["type"] == "pacing_short_scenes" for f in flags)

    def test_no_flags_when_on_track(self, tmp_story_db):
        init_db(tmp_story_db)
        with connect(tmp_story_db) as conn:
            for i in range(2):
                record_scene(
                    conn, scene_id=f"s{i}", universe_id="u1",
                    book_number=1, chapter_number=1, scene_number=i + 1,
                    word_count=1000,
                )
            flags = compute_pacing_flags(conn, current_chapter=1, current_scene=3)
        # Should not have long_chapter or short_scenes
        types = {f["type"] for f in flags}
        assert "pacing_long_chapter" not in types
        assert "pacing_short_scenes" not in types
