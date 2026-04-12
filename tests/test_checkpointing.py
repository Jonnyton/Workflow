"""Tests for checkpointing -- persistence, resume, WAL mode, retention.

Verifies:
- State persists to checkpoint database (in-memory and on-disk).
- Pause/resume from checkpoint restores state correctly.
- WAL mode is set on file-backed databases.
- Checkpoint retention policy works (keep last N + named).
- create_checkpointer factory works.
- compile_all_graphs helper works.
- get_checkpoint_history returns correct data.
- make_resume_config builds valid config dicts.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile

import pytest

from fantasy_author.checkpointing import (
    CheckpointRetentionPolicy,
    compile_all_graphs,
    create_checkpointer,
    get_checkpoint_history,
)
from fantasy_author.checkpointing.sqlite_saver import (
    make_resume_config,
    verify_wal_mode,
)
from fantasy_author.graphs.scene import build_scene_graph

# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------


@pytest.fixture
def scene_input():
    """Minimal valid scene input state."""
    return {
        "universe_id": "test-universe",
        "book_number": 1,
        "chapter_number": 1,
        "scene_number": 1,
        "orient_result": {},
        "retrieved_context": {},
        "recent_prose": "",
        "_db_path": ":memory:",
        "workflow_instructions": {},
        "plan_output": None,
        "draft_output": None,
        "commit_result": None,
        "second_draft_used": False,
        "verdict": "",
        "extracted_facts": [],
        "extracted_promises": [],
        "style_observations": [],
        "quality_trace": [],
        "quality_debt": [],
    }


@pytest.fixture
def tmp_db_path():
    """Create a temporary database file path and clean up after test."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    # Remove the file so SqliteSaver creates it fresh
    os.unlink(path)
    yield path
    # Clean up all SQLite artifacts
    for suffix in ("", "-wal", "-shm"):
        try:
            os.unlink(path + suffix)
        except FileNotFoundError:
            pass


# -----------------------------------------------------------------------
# WAL mode tests
# -----------------------------------------------------------------------


class TestWALMode:
    """Verify WAL journal mode is properly set."""

    def test_wal_mode_on_file_db(self, tmp_db_path):
        with create_checkpointer(tmp_db_path) as cp:
            # Force setup to create tables
            graph = build_scene_graph().compile(checkpointer=cp)
            config = {"configurable": {"thread_id": "wal-test"}}
            graph.invoke(
                {
                    "universe_id": "t",
                    "book_number": 1,
                    "chapter_number": 1,
                    "scene_number": 1,
                    "orient_result": {},
                    "retrieved_context": {},
                    "recent_prose": "",
                    "workflow_instructions": {},
                    "plan_output": None,
                    "draft_output": None,
                    "commit_result": None,
                    "second_draft_used": False,
                    "verdict": "",
                    "extracted_facts": [],
                    "extracted_promises": [],
                    "style_observations": [],
                    "quality_trace": [],
                    "quality_debt": [],
                },
                config,
            )
            assert verify_wal_mode(cp) is True

    def test_wal_mode_verified_independently(self, tmp_db_path):
        """Verify WAL mode persists by checking with a fresh connection."""
        with create_checkpointer(tmp_db_path) as cp:
            # Trigger setup
            build_scene_graph().compile(checkpointer=cp)

        # Open the file independently and check
        conn = sqlite3.connect(tmp_db_path)
        try:
            result = conn.execute("PRAGMA journal_mode;").fetchone()
            assert result[0].lower() == "wal"
        finally:
            conn.close()

    def test_memory_db_wal_returns_false(self):
        """In-memory databases don't support WAL (returns 'memory')."""
        with create_checkpointer(":memory:") as cp:
            result = verify_wal_mode(cp)
            # In-memory SQLite uses 'memory' journal mode, not 'wal'
            assert result is False


# -----------------------------------------------------------------------
# State persistence tests
# -----------------------------------------------------------------------


class TestStatePersistence:
    """Verify state persists to checkpoint database."""

    def test_state_persists_in_memory(self, scene_input):
        with create_checkpointer(":memory:") as cp:
            compiled = build_scene_graph().compile(checkpointer=cp)
            config = {"configurable": {"thread_id": "persist-test"}}

            compiled.invoke(scene_input, config)

            # Verify state was persisted by reading it back
            saved = compiled.get_state(config)
            assert saved.values["verdict"] == "accept"
            assert saved.values["universe_id"] == "test-universe"

    def test_state_persists_to_disk(self, tmp_db_path, scene_input):
        with create_checkpointer(tmp_db_path) as cp:
            compiled = build_scene_graph().compile(checkpointer=cp)
            config = {"configurable": {"thread_id": "persist-disk"}}

            compiled.invoke(scene_input, config)

            # Verify checkpoint tables exist in the database
            saved = compiled.get_state(config)
            assert saved.values["verdict"] == "accept"

    def test_checkpoint_tables_exist(self, tmp_db_path, scene_input):
        """Verify the expected SQLite tables are created."""
        with create_checkpointer(tmp_db_path) as cp:
            compiled = build_scene_graph().compile(checkpointer=cp)
            config = {"configurable": {"thread_id": "tables-test"}}
            compiled.invoke(scene_input, config)

        # Check tables with a fresh connection
        conn = sqlite3.connect(tmp_db_path)
        try:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = {t[0] for t in tables}
            assert "checkpoints" in table_names
            assert "writes" in table_names
        finally:
            conn.close()

    def test_multiple_threads_isolated(self, scene_input):
        """Two different threads maintain independent state."""
        with create_checkpointer(":memory:") as cp:
            compiled = build_scene_graph().compile(checkpointer=cp)

            config1 = {"configurable": {"thread_id": "thread-1"}}
            config2 = {"configurable": {"thread_id": "thread-2"}}

            input2 = dict(scene_input)
            input2["scene_number"] = 42

            compiled.invoke(scene_input, config1)
            compiled.invoke(input2, config2)

            state1 = compiled.get_state(config1)
            state2 = compiled.get_state(config2)

            assert state1.values["scene_number"] == 1
            assert state2.values["scene_number"] == 42


# -----------------------------------------------------------------------
# Pause / resume tests
# -----------------------------------------------------------------------


class TestPauseResume:
    """Verify pause/resume from checkpoint works correctly."""

    def test_resume_from_latest_checkpoint(self, scene_input):
        """After completing a run, get_state returns the final state."""
        with create_checkpointer(":memory:") as cp:
            compiled = build_scene_graph().compile(checkpointer=cp)
            config = {"configurable": {"thread_id": "resume-test"}}

            # First run
            result = compiled.invoke(scene_input, config)
            assert result["verdict"] == "accept"

            # Get the saved state
            saved_state = compiled.get_state(config)
            assert saved_state.values["verdict"] == "accept"
            assert saved_state.values["draft_output"] is not None
            assert saved_state.values["plan_output"] is not None

    def test_resume_config_builder(self):
        """make_resume_config builds correct config dicts."""
        config = make_resume_config("my-thread")
        assert config == {"configurable": {"thread_id": "my-thread"}}

        config_with_cp = make_resume_config("my-thread", "cp-123")
        assert config_with_cp == {
            "configurable": {"thread_id": "my-thread", "checkpoint_id": "cp-123"}
        }

    def test_disk_persistence_across_checkpointers(self, tmp_db_path, scene_input):
        """State survives closing and re-opening the checkpointer."""
        thread_id = "cross-session"

        # First session: run and save
        with create_checkpointer(tmp_db_path) as cp:
            compiled = build_scene_graph().compile(checkpointer=cp)
            config = {"configurable": {"thread_id": thread_id}}
            compiled.invoke(scene_input, config)

        # Second session: re-open and verify state persists
        with create_checkpointer(tmp_db_path) as cp:
            compiled = build_scene_graph().compile(checkpointer=cp)
            config = {"configurable": {"thread_id": thread_id}}
            saved = compiled.get_state(config)
            assert saved.values["verdict"] == "accept"
            assert saved.values["universe_id"] == "test-universe"


# -----------------------------------------------------------------------
# Checkpoint history tests
# -----------------------------------------------------------------------


class TestCheckpointHistory:
    """Verify checkpoint listing and history works."""

    def test_get_checkpoint_history(self, scene_input):
        with create_checkpointer(":memory:") as cp:
            compiled = build_scene_graph().compile(checkpointer=cp)
            config = {"configurable": {"thread_id": "history-test"}}

            compiled.invoke(scene_input, config)

            history = get_checkpoint_history(cp, "history-test")
            assert len(history) > 0
            assert all(h["thread_id"] == "history-test" for h in history)
            assert all("checkpoint_id" in h for h in history)

    def test_history_limit(self, scene_input):
        with create_checkpointer(":memory:") as cp:
            compiled = build_scene_graph().compile(checkpointer=cp)

            # Run multiple scenes on the same thread to create checkpoints
            for i in range(3):
                input_i = dict(scene_input)
                input_i["scene_number"] = i + 1
                config = {"configurable": {"thread_id": f"limit-test-{i}"}}
                compiled.invoke(input_i, config)

            history = get_checkpoint_history(cp, "limit-test-0", limit=2)
            assert len(history) <= 2

    def test_empty_history_for_unknown_thread(self, scene_input):
        with create_checkpointer(":memory:") as cp:
            history = get_checkpoint_history(cp, "nonexistent-thread")
            assert history == []


# -----------------------------------------------------------------------
# Retention policy tests
# -----------------------------------------------------------------------


class TestRetentionPolicy:
    """Verify checkpoint retention policy works."""

    def test_retention_keeps_recent(self, scene_input):
        policy = CheckpointRetentionPolicy(keep_last_n=50)
        with create_checkpointer(":memory:") as cp:
            compiled = build_scene_graph().compile(checkpointer=cp)
            config = {"configurable": {"thread_id": "retention-test"}}

            # Create some checkpoints
            compiled.invoke(scene_input, config)

            get_checkpoint_history(cp, "retention-test", limit=100)
            deleted = policy.apply(cp, "retention-test")

            # With keep_last_n=50 and only a few checkpoints, nothing should be deleted
            assert deleted == 0

    def test_retention_deletes_old(self, scene_input):
        policy = CheckpointRetentionPolicy(keep_last_n=1)
        with create_checkpointer(":memory:") as cp:
            compiled = build_scene_graph().compile(checkpointer=cp)
            config = {"configurable": {"thread_id": "prune-test"}}

            # Create checkpoints by running
            compiled.invoke(scene_input, config)

            history = get_checkpoint_history(cp, "prune-test", limit=100)
            if len(history) > 1:
                deleted = policy.apply(cp, "prune-test")
                assert deleted > 0
                remaining = get_checkpoint_history(cp, "prune-test", limit=100)
                assert len(remaining) < len(history)

    def test_named_checkpoints_protected(self, scene_input):
        with create_checkpointer(":memory:") as cp:
            compiled = build_scene_graph().compile(checkpointer=cp)
            config = {"configurable": {"thread_id": "named-test"}}

            compiled.invoke(scene_input, config)

            history = get_checkpoint_history(cp, "named-test", limit=100)
            if history:
                # Mark the first checkpoint as named
                first_cp_id = history[0]["checkpoint_id"]
                policy = CheckpointRetentionPolicy(keep_last_n=0)
                policy.mark_named(first_cp_id)

                policy.apply(cp, "named-test")
                remaining = get_checkpoint_history(cp, "named-test", limit=100)
                # The named checkpoint should still exist
                remaining_ids = [r["checkpoint_id"] for r in remaining]
                assert first_cp_id in remaining_ids

    def test_mark_and_unmark_named(self):
        policy = CheckpointRetentionPolicy()
        policy.mark_named("cp-1")
        assert "cp-1" in policy.named_checkpoints

        policy.unmark_named("cp-1")
        assert "cp-1" not in policy.named_checkpoints

        # Unmark non-existent is safe
        policy.unmark_named("cp-nonexistent")


# -----------------------------------------------------------------------
# create_checkpointer factory tests
# -----------------------------------------------------------------------


class TestCreateCheckpointer:
    """Verify the checkpointer factory works correctly."""

    def test_create_memory_checkpointer(self):
        with create_checkpointer(":memory:") as cp:
            assert cp is not None
            assert cp.conn is not None

    def test_create_file_checkpointer(self, tmp_db_path):
        with create_checkpointer(tmp_db_path) as cp:
            assert cp is not None
            assert cp.conn is not None
        # File should exist after use
        assert os.path.exists(tmp_db_path)

    def test_compile_all_graphs_with_factory(self):
        with create_checkpointer(":memory:") as cp:
            graphs = compile_all_graphs(cp)
            assert "scene" in graphs
            assert "chapter" in graphs
            assert "book" in graphs
            assert "universe" in graphs
