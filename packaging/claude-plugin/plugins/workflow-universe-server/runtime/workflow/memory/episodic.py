"""Episodic memory -- recent scene summaries and facts (SQLite-backed).

Stores scene-by-scene summaries, recently-extracted facts, and style
observations from the last N chapters.  Supports sliding-window
eviction to keep only hot data here; older entries are assumed to be
accessible via archival memory (KG / vectors).
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS scene_summaries (
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

CREATE TABLE IF NOT EXISTS episodic_facts (
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

CREATE TABLE IF NOT EXISTS style_observations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    universe_id   TEXT    NOT NULL,
    dimension     TEXT    NOT NULL,
    observation   TEXT    NOT NULL,
    scene_ref     TEXT    NOT NULL DEFAULT '',
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS reflections (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    universe_id   TEXT    NOT NULL,
    chapter_number INTEGER NOT NULL,
    scene_number  INTEGER NOT NULL,
    critique      TEXT    NOT NULL,
    reflection    TEXT    NOT NULL,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""


@dataclass(frozen=True, slots=True)
class SceneSummary:
    """A scene summary retrieved from episodic memory."""

    book_number: int
    chapter_number: int
    scene_number: int
    summary: str
    word_count: int


class EpisodicMemory:
    """SQLite-backed store for recent scene summaries and facts.

    Parameters
    ----------
    db_path : str | Path
        Path to the SQLite database.  Use ``":memory:"`` for tests.
    universe_id : str
        Scopes all reads/writes to this universe.
    window_chapters : int
        How many chapters of history to keep in the hot window.
    """

    def __init__(
        self,
        db_path: str | Path = ":memory:",
        universe_id: str = "default",
        window_chapters: int = 5,
    ) -> None:
        self._db_path = str(db_path)
        self._universe_id = universe_id
        self._window_chapters = window_chapters
        self._conn = sqlite3.connect(self._db_path, timeout=30)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=30000")
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    # ------------------------------------------------------------------
    # Scene summaries
    # ------------------------------------------------------------------

    def store_summary(
        self,
        book_number: int,
        chapter_number: int,
        scene_number: int,
        summary: str,
        word_count: int = 0,
    ) -> None:
        """Persist a scene summary (upsert)."""
        self._conn.execute(
            """
            INSERT INTO scene_summaries
                (universe_id, book_number, chapter_number, scene_number,
                 summary, word_count)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(universe_id, book_number, chapter_number, scene_number)
            DO UPDATE SET summary=excluded.summary,
                          word_count=excluded.word_count
            """,
            (self._universe_id, book_number, chapter_number,
             scene_number, summary, word_count),
        )
        self._conn.commit()

    def get_recent(
        self,
        chapter: int,
        k: int = 5,
        book: int = 1,
    ) -> list[SceneSummary]:
        """Return the *k* most recent scene summaries up to *chapter*."""
        rows = self._conn.execute(
            """
            SELECT book_number, chapter_number, scene_number,
                   summary, word_count
            FROM scene_summaries
            WHERE universe_id = ?
              AND book_number = ?
              AND chapter_number <= ?
            ORDER BY chapter_number DESC, scene_number DESC
            LIMIT ?
            """,
            (self._universe_id, book, chapter, k),
        ).fetchall()
        return [
            SceneSummary(
                book_number=r[0],
                chapter_number=r[1],
                scene_number=r[2],
                summary=r[3],
                word_count=r[4],
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Episodic facts
    # ------------------------------------------------------------------

    def store_fact(
        self,
        fact_id: str,
        entity: str,
        content: str,
        source_scene: str = "",
    ) -> None:
        """Insert or increment evidence for a fact."""
        existing = self._conn.execute(
            "SELECT evidence_count, source_scenes FROM episodic_facts "
            "WHERE universe_id = ? AND fact_id = ?",
            (self._universe_id, fact_id),
        ).fetchone()

        if existing is not None:
            count = existing[0] + 1
            scenes = json.loads(existing[1])
            if source_scene and source_scene not in scenes:
                scenes.append(source_scene)
            self._conn.execute(
                "UPDATE episodic_facts "
                "SET evidence_count = ?, source_scenes = ? "
                "WHERE universe_id = ? AND fact_id = ?",
                (count, json.dumps(scenes), self._universe_id, fact_id),
            )
        else:
            scenes = [source_scene] if source_scene else []
            self._conn.execute(
                """
                INSERT INTO episodic_facts
                    (universe_id, fact_id, entity, content,
                     evidence_count, source_scenes)
                VALUES (?, ?, ?, ?, 1, ?)
                """,
                (self._universe_id, fact_id, entity, content,
                 json.dumps(scenes)),
            )
        self._conn.commit()

    def get_facts_for_entity(self, entity: str) -> list[dict[str, Any]]:
        """Return all episodic facts mentioning *entity*."""
        rows = self._conn.execute(
            "SELECT fact_id, entity, content, evidence_count, "
            "source_scenes, promoted "
            "FROM episodic_facts "
            "WHERE universe_id = ? AND entity = ?",
            (self._universe_id, entity),
        ).fetchall()
        return [
            {
                "fact_id": r[0],
                "entity": r[1],
                "content": r[2],
                "evidence_count": r[3],
                "source_scenes": json.loads(r[4]),
                "promoted": bool(r[5]),
            }
            for r in rows
        ]

    def get_promotable_facts(self, threshold: int = 3) -> list[dict[str, Any]]:
        """Return facts with evidence_count >= *threshold* not yet promoted."""
        rows = self._conn.execute(
            "SELECT fact_id, entity, content, evidence_count, source_scenes "
            "FROM episodic_facts "
            "WHERE universe_id = ? AND promoted = 0 "
            "AND evidence_count >= ?",
            (self._universe_id, threshold),
        ).fetchall()
        return [
            {
                "fact_id": r[0],
                "entity": r[1],
                "content": r[2],
                "evidence_count": r[3],
                "source_scenes": json.loads(r[4]),
            }
            for r in rows
        ]

    def mark_promoted(self, fact_id: str) -> None:
        """Mark a fact as promoted to archival/canonical."""
        self._conn.execute(
            "UPDATE episodic_facts SET promoted = 1 "
            "WHERE universe_id = ? AND fact_id = ?",
            (self._universe_id, fact_id),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Style observations
    # ------------------------------------------------------------------

    def store_observation(
        self,
        dimension: str,
        observation: str,
        scene_ref: str = "",
    ) -> None:
        """Record a style observation from judge feedback."""
        self._conn.execute(
            "INSERT INTO style_observations "
            "(universe_id, dimension, observation, scene_ref) "
            "VALUES (?, ?, ?, ?)",
            (self._universe_id, dimension, observation, scene_ref),
        )
        self._conn.commit()

    def get_observations_by_dimension(
        self, dimension: str
    ) -> list[dict[str, str]]:
        """Return all observations for a style dimension."""
        rows = self._conn.execute(
            "SELECT observation, scene_ref, created_at "
            "FROM style_observations "
            "WHERE universe_id = ? AND dimension = ? "
            "ORDER BY created_at DESC",
            (self._universe_id, dimension),
        ).fetchall()
        return [
            {"observation": r[0], "scene_ref": r[1], "created_at": r[2]}
            for r in rows
        ]

    def count_observations(self, dimension: str) -> int:
        """Count observations for a dimension (used by promotion gates)."""
        row = self._conn.execute(
            "SELECT COUNT(*) FROM style_observations "
            "WHERE universe_id = ? AND dimension = ?",
            (self._universe_id, dimension),
        ).fetchone()
        return row[0] if row else 0

    # ------------------------------------------------------------------
    # Reflections
    # ------------------------------------------------------------------

    def store_reflection(
        self,
        chapter_number: int,
        scene_number: int,
        critique: str,
        reflection: str,
    ) -> None:
        """Store a Reflexion entry from a revert cycle."""
        self._conn.execute(
            "INSERT INTO reflections "
            "(universe_id, chapter_number, scene_number, "
            "critique, reflection) "
            "VALUES (?, ?, ?, ?, ?)",
            (self._universe_id, chapter_number, scene_number,
             critique, reflection),
        )
        self._conn.commit()

    def get_recent_reflections(self, k: int = 3) -> list[dict[str, Any]]:
        """Return the *k* most recent reflections."""
        rows = self._conn.execute(
            "SELECT chapter_number, scene_number, critique, reflection, "
            "created_at "
            "FROM reflections WHERE universe_id = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (self._universe_id, k),
        ).fetchall()
        return [
            {
                "chapter_number": r[0],
                "scene_number": r[1],
                "critique": r[2],
                "reflection": r[3],
                "created_at": r[4],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Sliding window eviction
    # ------------------------------------------------------------------

    def evict_old_summaries(
        self,
        current_chapter: int,
        book: int = 1,
    ) -> int:
        """Remove summaries older than *window_chapters* from current.

        Returns the number of rows deleted.
        """
        cutoff = current_chapter - self._window_chapters
        if cutoff < 1:
            return 0
        cur = self._conn.execute(
            "DELETE FROM scene_summaries "
            "WHERE universe_id = ? AND book_number = ? "
            "AND chapter_number < ?",
            (self._universe_id, book, cutoff),
        )
        self._conn.commit()
        return cur.rowcount
