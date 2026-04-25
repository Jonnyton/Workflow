"""World-state-db helper -- shared by orient (read) and commit (write) nodes in the scene graph."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS promises (
    id          TEXT PRIMARY KEY,
    text        TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'active',  -- active | resolved | expired
    importance  REAL NOT NULL DEFAULT 0.5,
    created_scene   TEXT NOT NULL,
    resolved_scene  TEXT,
    created_chapter INTEGER NOT NULL DEFAULT 1,
    resolved_chapter INTEGER
);

CREATE TABLE IF NOT EXISTS character_states (
    character_id    TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    location        TEXT NOT NULL DEFAULT 'unknown',
    emotional_state TEXT NOT NULL DEFAULT 'neutral',
    knowledge_facts TEXT NOT NULL DEFAULT '[]',  -- JSON list of fact_ids
    last_updated_scene TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS scene_history (
    scene_id        TEXT PRIMARY KEY,
    universe_id     TEXT NOT NULL,
    book_number     INTEGER NOT NULL,
    chapter_number  INTEGER NOT NULL,
    scene_number    INTEGER NOT NULL,
    word_count      INTEGER NOT NULL DEFAULT 0,
    verdict         TEXT NOT NULL DEFAULT 'accept',
    summary         TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS extracted_facts (
    fact_id         TEXT PRIMARY KEY,
    text            TEXT NOT NULL,
    source_type     TEXT NOT NULL DEFAULT 'narrator_claim',
    language_type   TEXT NOT NULL DEFAULT 'literal',
    narrator        TEXT,
    confidence      REAL NOT NULL DEFAULT 0.5,
    scene_id        TEXT NOT NULL,
    chapter_number  INTEGER NOT NULL DEFAULT 1,
    importance      REAL NOT NULL DEFAULT 0.5
);
"""


# ---------------------------------------------------------------------------
# Database lifecycle
# ---------------------------------------------------------------------------


def init_db(db_path: str = "") -> None:
    """Create the world state tables if they don't exist.

    Parameters
    ----------
    db_path : str
        Path to the SQLite database file.  Use ``:memory:`` for tests.
        Empty string raises ValueError to prevent CWD-relative fallback.
    """
    if not db_path:
        raise ValueError(
            "init_db requires an explicit db_path. "
            "CWD-relative defaults cause cross-universe contamination."
        )
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(_SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def connect(db_path: str = "") -> Iterator[sqlite3.Connection]:
    """Context manager for a world state DB connection.

    Parameters
    ----------
    db_path : str
        Path to the SQLite database file.  Empty string raises ValueError
        to prevent CWD-relative fallback.

    Yields
    ------
    sqlite3.Connection
    """
    if not db_path:
        raise ValueError(
            "connect requires an explicit db_path. "
            "CWD-relative defaults cause cross-universe contamination."
        )
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Promise operations
# ---------------------------------------------------------------------------


def add_promise(
    conn: sqlite3.Connection,
    *,
    promise_id: str,
    text: str,
    created_scene: str,
    created_chapter: int = 1,
    importance: float = 0.5,
) -> None:
    """Insert a new narrative promise."""
    conn.execute(
        "INSERT OR REPLACE INTO promises "
        "(id, text, status, importance, created_scene, created_chapter) "
        "VALUES (?, ?, 'active', ?, ?, ?)",
        (promise_id, text, importance, created_scene, created_chapter),
    )
    conn.commit()


def resolve_promise(
    conn: sqlite3.Connection,
    *,
    promise_id: str,
    resolved_scene: str,
    resolved_chapter: int,
) -> None:
    """Mark a promise as resolved."""
    conn.execute(
        "UPDATE promises SET status = 'resolved', resolved_scene = ?, resolved_chapter = ? "
        "WHERE id = ?",
        (resolved_scene, resolved_chapter, promise_id),
    )
    conn.commit()


#: Upper bound on how many promises / characters flow into the context
#: bundle. Defense-in-depth after BUG-024 — even if a universe accrues
#: hundreds of active entities, the bundle stays under the 15k-token
#: CoreMemory budget. Top-N by importance / recency is still the most
#: useful slice for planning + drafting.
_MAX_WORLD_STATE_ENTITIES = 25


def get_active_promises(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return the top-N active (unresolved) promises by importance."""
    rows = conn.execute(
        "SELECT * FROM promises WHERE status = 'active' "
        "ORDER BY importance DESC LIMIT ?",
        (_MAX_WORLD_STATE_ENTITIES,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_overdue_promises(
    conn: sqlite3.Connection,
    current_chapter: int,
    *,
    overdue_threshold: int = 3,
) -> list[dict[str, Any]]:
    """Return promises that have been active for more than ``overdue_threshold`` chapters.

    Parameters
    ----------
    conn : sqlite3.Connection
    current_chapter : int
        The current chapter number.
    overdue_threshold : int
        Number of chapters after which an active promise is considered overdue.
    """
    rows = conn.execute(
        "SELECT * FROM promises WHERE status = 'active' "
        "AND (? - created_chapter) >= ? "
        "ORDER BY importance DESC",
        (current_chapter, overdue_threshold),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Character state operations
# ---------------------------------------------------------------------------


def upsert_character(
    conn: sqlite3.Connection,
    *,
    character_id: str,
    name: str,
    location: str = "unknown",
    emotional_state: str = "neutral",
    knowledge_facts: list[str] | None = None,
    last_updated_scene: str = "",
) -> None:
    """Insert or update a character's state."""
    facts_json = json.dumps(knowledge_facts or [])
    conn.execute(
        "INSERT OR REPLACE INTO character_states "
        "(character_id, name, location, emotional_state, knowledge_facts, last_updated_scene) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (character_id, name, location, emotional_state, facts_json, last_updated_scene),
    )
    conn.commit()


def get_character(conn: sqlite3.Connection, character_id: str) -> dict[str, Any] | None:
    """Retrieve a character's state by ID."""
    row = conn.execute(
        "SELECT * FROM character_states WHERE character_id = ?", (character_id,)
    ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["knowledge_facts"] = json.loads(result["knowledge_facts"])
    return result


def get_all_characters(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return the top-N most recently updated tracked characters.

    Ordered by SQLite's ROWID (which INSERT OR REPLACE bumps on upsert),
    so the character who appeared most recently in a scene sorts first.
    """
    rows = conn.execute(
        "SELECT * FROM character_states ORDER BY ROWID DESC LIMIT ?",
        (_MAX_WORLD_STATE_ENTITIES,),
    ).fetchall()
    results = []
    for row in rows:
        r = dict(row)
        r["knowledge_facts"] = json.loads(r["knowledge_facts"])
        results.append(r)
    return results


def get_character_gaps(
    conn: sqlite3.Connection,
    scene_characters: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Find characters with incomplete or stale state.

    A 'gap' is a character whose location is 'unknown' or whose
    emotional_state is 'neutral' (never been set explicitly).

    Parameters
    ----------
    conn : sqlite3.Connection
    scene_characters : list[str] or None
        If provided, only check these characters.
    """
    if scene_characters:
        placeholders = ",".join("?" for _ in scene_characters)
        rows = conn.execute(
            f"SELECT * FROM character_states WHERE character_id IN ({placeholders}) "
            "AND (location = 'unknown' OR emotional_state = 'neutral')",
            scene_characters,
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM character_states "
            "WHERE location = 'unknown' OR emotional_state = 'neutral'"
        ).fetchall()
    results = []
    for row in rows:
        r = dict(row)
        r["knowledge_facts"] = json.loads(r["knowledge_facts"])
        results.append(r)
    return results


# ---------------------------------------------------------------------------
# Scene history operations
# ---------------------------------------------------------------------------


def record_scene(
    conn: sqlite3.Connection,
    *,
    scene_id: str,
    universe_id: str,
    book_number: int,
    chapter_number: int,
    scene_number: int,
    word_count: int = 0,
    verdict: str = "accept",
    summary: str = "",
) -> None:
    """Record a scene's completion in history."""
    conn.execute(
        "INSERT OR REPLACE INTO scene_history "
        "(scene_id, universe_id, book_number, chapter_number, scene_number, "
        "word_count, verdict, summary) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (scene_id, universe_id, book_number, chapter_number, scene_number,
         word_count, verdict, summary),
    )
    conn.commit()


def get_recent_scenes(
    conn: sqlite3.Connection,
    chapter_number: int,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Return the most recent scenes from the current or prior chapters."""
    rows = conn.execute(
        "SELECT * FROM scene_history WHERE chapter_number <= ? "
        "ORDER BY chapter_number DESC, scene_number DESC LIMIT ?",
        (chapter_number, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def get_chapter_scene_count(conn: sqlite3.Connection, chapter_number: int) -> int:
    """Return the number of scenes completed in a given chapter."""
    row = conn.execute(
        "SELECT COUNT(*) FROM scene_history WHERE chapter_number = ?",
        (chapter_number,),
    ).fetchone()
    return row[0] if row else 0


def get_chapter_word_count(conn: sqlite3.Connection, chapter_number: int) -> int:
    """Return total word count for a given chapter."""
    row = conn.execute(
        "SELECT COALESCE(SUM(word_count), 0) FROM scene_history WHERE chapter_number = ?",
        (chapter_number,),
    ).fetchone()
    return row[0] if row else 0


# ---------------------------------------------------------------------------
# Extracted facts operations
# ---------------------------------------------------------------------------


def store_fact(
    conn: sqlite3.Connection,
    *,
    fact_id: str,
    text: str,
    source_type: str = "narrator_claim",
    language_type: str = "literal",
    narrator: str | None = None,
    confidence: float = 0.5,
    scene_id: str = "",
    chapter_number: int = 1,
    importance: float = 0.5,
) -> None:
    """Store an extracted fact."""
    conn.execute(
        "INSERT OR REPLACE INTO extracted_facts "
        "(fact_id, text, source_type, language_type, narrator, confidence, "
        "scene_id, chapter_number, importance) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (fact_id, text, source_type, language_type, narrator, confidence,
         scene_id, chapter_number, importance),
    )
    conn.commit()


def get_facts_for_chapter(
    conn: sqlite3.Connection,
    chapter_number: int,
) -> list[dict[str, Any]]:
    """Return all facts extracted in a given chapter."""
    rows = conn.execute(
        "SELECT * FROM extracted_facts WHERE chapter_number = ? ORDER BY importance DESC",
        (chapter_number,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_all_facts(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return all extracted facts."""
    rows = conn.execute(
        "SELECT * FROM extracted_facts ORDER BY importance DESC"
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Pacing analysis (deterministic)
# ---------------------------------------------------------------------------


def compute_pacing_flags(
    conn: sqlite3.Connection,
    current_chapter: int,
    current_scene: int,
    *,
    target_scenes_per_chapter: int = 4,
    avg_words_per_scene: int = 1000,
) -> list[dict[str, str]]:
    """Compute pacing flags based on scene history.

    Returns a list of warning dicts, each with ``type`` and ``text`` keys.
    """
    flags: list[dict[str, str]] = []

    chapter_scenes = get_chapter_scene_count(conn, current_chapter)
    chapter_words = get_chapter_word_count(conn, current_chapter)

    # Flag: too many scenes in this chapter
    if chapter_scenes >= target_scenes_per_chapter + 2:
        flags.append({
            "type": "pacing_long_chapter",
            "text": (
                f"Chapter {current_chapter} has {chapter_scenes} scenes "
                f"(target: {target_scenes_per_chapter}). Consider wrapping up."
            ),
        })

    # Flag: word count running short
    if chapter_scenes > 0:
        avg_wc = chapter_words / chapter_scenes
        if avg_wc < avg_words_per_scene * 0.5:
            flags.append({
                "type": "pacing_short_scenes",
                "text": (
                    f"Average scene length ({avg_wc:.0f} words) is below target "
                    f"({avg_words_per_scene}). Scenes may need more depth."
                ),
            })

    # Flag: first scene of a chapter (opportunity for scene-setting)
    if current_scene == 1:
        flags.append({
            "type": "chapter_opening",
            "text": "First scene of chapter -- establish setting, re-ground the reader.",
        })

    return flags
