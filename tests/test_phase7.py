"""Tests for Phase 7 polish modules: ingestion, versioning, promises."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

from workflow.memory.ingestion import (
    IngestionPriority,
    ProgressiveIngestor,
)
from workflow.memory.promises import SeriesPromiseTracker
from workflow.memory.versioning import OutputVersionStore

# =====================================================================
# ProgressiveIngestor
# =====================================================================


class TestProgressiveIngestor:
    def _make_canon_dir(self, tmp_path: Path) -> Path:
        canon = tmp_path / "canon"
        canon.mkdir()
        (canon / "world.md").write_text(
            "# Characters\n\nRyn is a scout.\n\n"
            "# Magic System\n\nThe Web connects all things.\n\n"
            "# Locations\n\nThe Northern Gate guards the pass.\n",
            encoding="utf-8",
        )
        (canon / "notes.txt").write_text(
            "Some plain text notes about the story.\n",
            encoding="utf-8",
        )
        return canon

    def test_survey_finds_files(self, tmp_path: Path):
        canon = self._make_canon_dir(tmp_path)
        ingestor = ProgressiveIngestor(canon, "test")
        state = ingestor.survey()
        assert state.total_files == 2
        assert state.total_sections > 0
        assert state.survey_complete

    def test_survey_splits_sections(self, tmp_path: Path):
        canon = self._make_canon_dir(tmp_path)
        ingestor = ProgressiveIngestor(canon, "test")
        ingestor.survey()
        # world.md has 3 headings (Characters, Magic System, Locations)
        # plus potentially a pre-heading section
        headings = [s.heading for s in ingestor.state.sections]
        assert "Characters" in headings
        assert "Magic System" in headings

    def test_triage_assigns_priorities(self, tmp_path: Path):
        canon = self._make_canon_dir(tmp_path)
        ingestor = ProgressiveIngestor(canon, "test")
        ingestor.survey()
        ingestor.triage(
            immediate_keywords=["characters"],
            background_keywords=["magic"],
        )
        for s in ingestor.state.sections:
            if "characters" in s.heading.lower():
                assert s.priority == IngestionPriority.IMMEDIATE
            elif "magic" in s.heading.lower():
                assert s.priority == IngestionPriority.BACKGROUND

    def test_get_next_batch(self, tmp_path: Path):
        canon = self._make_canon_dir(tmp_path)
        ingestor = ProgressiveIngestor(canon, "test")
        ingestor.survey()
        ingestor.triage(immediate_keywords=["characters"])
        batch = ingestor.get_next_batch(IngestionPriority.IMMEDIATE)
        assert len(batch) >= 1
        assert all(
            s.priority == IngestionPriority.IMMEDIATE for s in batch
        )

    def test_mark_ingested(self, tmp_path: Path):
        canon = self._make_canon_dir(tmp_path)
        ingestor = ProgressiveIngestor(canon, "test")
        ingestor.survey()
        section = ingestor.state.sections[0]
        ingestor.mark_ingested(section)
        assert section.ingested
        assert ingestor.state.ingested_sections == 1

    def test_check_for_new_files(self, tmp_path: Path):
        canon = self._make_canon_dir(tmp_path)
        ingestor = ProgressiveIngestor(canon, "test")
        ingestor.survey()
        initial_count = ingestor.state.total_sections

        # Add a new file.
        (canon / "extra.md").write_text(
            "# New Content\n\nSome new material.\n",
            encoding="utf-8",
        )
        new_files = ingestor.check_for_new_files()
        assert len(new_files) == 1
        assert ingestor.state.total_sections > initial_count

    def test_survey_nonexistent_dir(self):
        ingestor = ProgressiveIngestor("/nonexistent/path", "test")
        state = ingestor.survey()
        assert state.total_files == 0

    def test_progress_tracking(self, tmp_path: Path):
        canon = self._make_canon_dir(tmp_path)
        ingestor = ProgressiveIngestor(canon, "test")
        ingestor.survey()
        assert ingestor.state.progress == 0.0
        for s in ingestor.state.sections:
            ingestor.mark_ingested(s)
        assert ingestor.state.progress == 1.0


# =====================================================================
# OutputVersionStore
# =====================================================================


class TestOutputVersionStore:
    def test_save_and_get_current(self):
        store = OutputVersionStore(":memory:", "test")
        v = store.save_draft(1, 1, 1, "Draft one", verdict="accept")
        assert v == 1
        current = store.get_current(1, 1, 1)
        assert current is not None
        assert current.prose == "Draft one"
        assert current.is_current

    def test_multiple_versions(self):
        store = OutputVersionStore(":memory:", "test")
        store.save_draft(1, 1, 1, "Draft one")
        store.save_draft(1, 1, 1, "Draft two")
        store.save_draft(1, 1, 1, "Draft three")

        current = store.get_current(1, 1, 1)
        assert current.version == 3
        assert current.prose == "Draft three"

        all_v = store.get_all_versions(1, 1, 1)
        assert len(all_v) == 3

    def test_rollback(self):
        store = OutputVersionStore(":memory:", "test")
        store.save_draft(1, 1, 1, "Draft one")
        store.save_draft(1, 1, 1, "Draft two")

        rolled = store.rollback(1, 1, 1, to_version=1)
        assert rolled is not None
        assert rolled.prose == "Draft one"
        assert rolled.is_current

        current = store.get_current(1, 1, 1)
        assert current.version == 1

    def test_rollback_nonexistent(self):
        store = OutputVersionStore(":memory:", "test")
        result = store.rollback(1, 1, 1, to_version=99)
        assert result is None

    def test_version_count(self):
        store = OutputVersionStore(":memory:", "test")
        assert store.version_count(1, 1, 1) == 0
        store.save_draft(1, 1, 1, "draft")
        assert store.version_count(1, 1, 1) == 1

    def test_get_specific_version(self):
        store = OutputVersionStore(":memory:", "test")
        store.save_draft(1, 1, 1, "version one")
        store.save_draft(1, 1, 1, "version two")
        v1 = store.get_version(1, 1, 1, 1)
        assert v1 is not None
        assert v1.prose == "version one"

    def test_quality_score_stored(self):
        store = OutputVersionStore(":memory:", "test")
        store.save_draft(1, 1, 1, "draft", quality_score=0.85)
        current = store.get_current(1, 1, 1)
        assert current.quality_score == 0.85

    def test_metadata_stored(self):
        store = OutputVersionStore(":memory:", "test")
        store.save_draft(1, 1, 1, "draft", metadata={"key": "value"})
        current = store.get_current(1, 1, 1)
        assert current.metadata == {"key": "value"}


# =====================================================================
# SeriesPromiseTracker
# =====================================================================


class TestSeriesPromiseTracker:
    def test_create_and_query(self):
        tracker = SeriesPromiseTracker(":memory:", "test")
        tracker.create_promise("p1", "Hero finds the sword", 1, 3)
        open_promises = tracker.get_open_promises()
        assert len(open_promises) == 1
        assert open_promises[0].promise_id == "p1"

    def test_resolve_promise(self):
        tracker = SeriesPromiseTracker(":memory:", "test")
        tracker.create_promise("p1", "Hero finds the sword", 1, 3)
        tracker.resolve_promise("p1", book=2, chapter=10)
        open_promises = tracker.get_open_promises()
        assert len(open_promises) == 0

        all_promises = tracker.get_all_promises()
        assert len(all_promises) == 1
        assert all_promises[0].status == "resolved"

    def test_add_evidence(self):
        tracker = SeriesPromiseTracker(":memory:", "test")
        tracker.create_promise("p1", "Sword quest", 1, 1)
        tracker.add_evidence("p1", {"scene": "b1c3s1", "note": "mentioned"})
        all_p = tracker.get_all_promises()
        assert len(all_p[0].evidence) == 1

    def test_overdue_promises(self):
        tracker = SeriesPromiseTracker(":memory:", "test")
        tracker.create_promise("old", "Ancient promise", 1, 1)
        tracker.create_promise("new", "Recent promise", 3, 25)
        overdue = tracker.get_overdue_promises(
            current_book=3, current_chapter=30, max_age_chapters=20
        )
        assert len(overdue) == 1
        assert overdue[0].promise_id == "old"

    def test_filter_by_book(self):
        tracker = SeriesPromiseTracker(":memory:", "test")
        tracker.create_promise("p1", "Book 1 promise", 1, 1)
        tracker.create_promise("p2", "Book 3 promise", 3, 1)
        book1 = tracker.get_open_promises(book=1)
        assert len(book1) == 1
        assert book1[0].promise_id == "p1"

    def test_promote_from_book(self):
        tracker = SeriesPromiseTracker(":memory:", "test")
        promises = [
            {"id": "p1", "description": "Promise one", "chapter": 5},
            {"id": "p2", "description": "Promise two", "chapter": 10},
        ]
        created = tracker.promote_from_book(promises, book=1)
        assert created == 2
        assert len(tracker.get_open_promises()) == 2

        # Promoting again should not duplicate.
        created = tracker.promote_from_book(promises, book=1)
        assert created == 0

    def test_duplicate_create_ignored(self):
        tracker = SeriesPromiseTracker(":memory:", "test")
        tracker.create_promise("p1", "Promise", 1, 1)
        tracker.create_promise("p1", "Duplicate", 1, 1)
        all_p = tracker.get_all_promises()
        assert len(all_p) == 1
        assert all_p[0].description == "Promise"  # Original kept


# =====================================================================
# Integration: Wiring tests
# =====================================================================


class TestCommitVersionStoreWiring:
    """Test that commit node saves drafts to version store."""

    def test_save_to_version_store_called(self):
        from workflow import runtime
        from domains.fantasy_author.phases.commit import _save_to_version_store

        store = OutputVersionStore(":memory:", "test")
        state = {
            "book_number": 1,
            "chapter_number": 2,
            "scene_number": 3,
        }
        runtime.version_store = store
        try:
            _save_to_version_store(state, "Some prose here.", "accept", 0.9)
        finally:
            runtime.version_store = None

        current = store.get_current(1, 2, 3)
        assert current is not None
        assert current.prose == "Some prose here."
        assert current.verdict == "accept"
        assert current.quality_score == 0.9

    def test_save_to_version_store_absent(self):
        """No crash when version_store is not set."""
        from workflow import runtime
        from domains.fantasy_author.phases.commit import _save_to_version_store

        runtime.version_store = None
        _save_to_version_store({}, "prose", "accept", 0.8)  # should not raise

    def test_save_to_version_store_error_handled(self):
        """Errors in version store are caught gracefully."""
        from workflow import runtime
        from domains.fantasy_author.phases.commit import _save_to_version_store

        broken_store = MagicMock()
        broken_store.save_draft.side_effect = RuntimeError("DB error")
        runtime.version_store = broken_store
        try:
            _save_to_version_store({}, "prose", "accept", 0.5)  # should not raise
        finally:
            runtime.version_store = None


class TestBookClosePromiseWiring:
    """Test that book_close promotes promises to series level."""

    def test_promote_promises_on_close(self):
        from workflow import runtime
        from domains.fantasy_author.phases.book_close import book_close

        tracker = SeriesPromiseTracker(":memory:", "test")
        state = {
            "book_number": 1,
            "chapters_completed": 10,
            "extracted_promises": [
                {"id": "p1", "description": "Hero finds sword", "chapter": 5},
                {"id": "p2", "description": "Villain returns", "chapter": 8},
            ],
        }
        runtime.promise_tracker = tracker
        try:
            result = book_close(state)
        finally:
            runtime.promise_tracker = None
        assert "book_summary" in result

        open_promises = tracker.get_open_promises()
        assert len(open_promises) == 2

    def test_book_close_no_tracker(self):
        """No crash when promise_tracker is not set."""
        from workflow import runtime
        from domains.fantasy_author.phases.book_close import book_close

        runtime.promise_tracker = None
        result = book_close({
            "book_number": 1,
            "chapters_completed": 5,
        })
        assert "book_summary" in result

    def test_book_close_empty_promises(self):
        """Graceful handling when no promises to promote."""
        from workflow import runtime
        from domains.fantasy_author.phases.book_close import book_close

        tracker = SeriesPromiseTracker(":memory:", "test")
        runtime.promise_tracker = tracker
        try:
            result = book_close({
                "book_number": 1,
                "chapters_completed": 5,
                "extracted_promises": [],
            })
        finally:
            runtime.promise_tracker = None
        assert "book_summary" in result
        assert len(tracker.get_all_promises()) == 0


class TestDaemonControllerIngestion:
    """Test progressive ingestion wiring in DaemonController."""

    def test_ingestion_with_canon_dir(self, tmp_path: Path):
        from workflow.__main__ import DaemonController

        # Create canon directory with a file
        universe_dir = tmp_path / "universe"
        canon_dir = universe_dir / "canon"
        canon_dir.mkdir(parents=True)
        (canon_dir / "lore.md").write_text(
            "# Characters\n\nRyn is brave.\n\n"
            "# Magic\n\nThe Web connects all.\n",
            encoding="utf-8",
        )

        controller = DaemonController(
            universe_path=str(universe_dir),
            db_path=":memory:",
            no_tray=True,
        )
        # Call _run_progressive_ingestion directly (start() would
        # try to build the full graph which needs too many deps).
        controller._run_progressive_ingestion("test-universe")
        # Should complete without error -- ingestion is fire-and-forget.

    def test_ingestion_no_canon_dir(self, tmp_path: Path):
        """No crash when canon directory doesn't exist."""
        from workflow.__main__ import DaemonController

        controller = DaemonController(
            universe_path=str(tmp_path / "nonexistent"),
            db_path=":memory:",
            no_tray=True,
        )
        controller._run_progressive_ingestion("test-universe")

    def test_bootstrap_runtime_files_creates_registry_artifacts(
        self, tmp_path: Path,
    ):
        from workflow.__main__ import DaemonController

        universe_dir = tmp_path / "universe"
        universe_dir.mkdir()

        controller = DaemonController(
            universe_path=str(universe_dir),
            db_path=str(universe_dir / "story.db"),
            no_tray=True,
        )
        controller._bootstrap_universe_runtime_files("Ashwater rises.")

        work_targets_path = universe_dir / "work_targets.json"
        hard_priorities_path = universe_dir / "hard_priorities.json"

        assert work_targets_path.exists()
        assert hard_priorities_path.exists()

        targets = json.loads(work_targets_path.read_text(encoding="utf-8"))
        assert {target["target_id"] for target in targets} >= {
            "universe-notes",
            "book-1",
        }
        assert json.loads(hard_priorities_path.read_text(encoding="utf-8")) == []

    def test_bootstrap_retrieval_indices_indexes_bootstrap_documents(
        self, tmp_path: Path,
    ):
        from workflow import runtime
        from workflow.__main__ import DaemonController

        universe_dir = tmp_path / "universe"
        canon_dir = universe_dir / "canon"
        chapter_dir = universe_dir / "output" / "book-1" / "chapter-07"
        chapter_dir.mkdir(parents=True)
        canon_dir.mkdir(parents=True)
        (canon_dir / "world.md").write_text(
            "# Lore\n\nThe river remembers names.\n",
            encoding="utf-8",
        )
        (chapter_dir / "scene-02.md").write_text(
            "Kael crossed the bridge at dusk.\n",
            encoding="utf-8",
        )

        controller = DaemonController(
            universe_path=str(universe_dir),
            db_path=str(universe_dir / "story.db"),
            no_tray=True,
        )
        runtime.knowledge_graph = MagicMock()
        runtime.vector_store = None
        runtime.embed_fn = None

        with patch(
            "workflow.ingestion.indexer.index_text",
            return_value={
                "entities": 1,
                "edges": 2,
                "facts": 3,
                "chunks_indexed": 0,
            },
        ) as mock_index:
            controller._bootstrap_retrieval_indices()

        assert mock_index.call_count == 2
        first_call = mock_index.call_args_list[0]
        second_call = mock_index.call_args_list[1]

        assert first_call.args[1] == "canon/world.md"
        assert first_call.kwargs["chapter_number"] == 0
        assert second_call.args[1] == "output/book-1/chapter-07/scene-02.md"
        assert second_call.kwargs["chapter_number"] == 7

    def test_bootstrap_retrieval_indices_skips_when_kg_has_content(
        self, tmp_path: Path,
    ):
        from workflow import runtime
        from workflow.__main__ import DaemonController

        universe_dir = tmp_path / "universe"
        universe_dir.mkdir()
        kg_path = universe_dir / "knowledge.db"
        with sqlite3.connect(kg_path) as conn:
            conn.execute("CREATE TABLE entities (entity_id TEXT)")
            conn.execute("INSERT INTO entities VALUES ('ryn')")
            conn.commit()

        controller = DaemonController(
            universe_path=str(universe_dir),
            db_path=str(universe_dir / "story.db"),
            no_tray=True,
        )
        runtime.knowledge_graph = MagicMock()

        with patch("workflow.ingestion.indexer.index_text") as mock_index:
            controller._bootstrap_retrieval_indices()

        mock_index.assert_not_called()
