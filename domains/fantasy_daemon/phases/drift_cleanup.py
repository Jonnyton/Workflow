"""Post-synthesis drift-KG + story-db cleanup (Task #17 Fix E).

When a pre-synthesis draft cycle has contaminated the KG + world-state DB
with facts seeded against placeholder-premise scenes (pattern:
``{universe}-B*-C*-S*_chunk_*``), the first successful canon synthesis
should wipe those rows universe-wide so future retrievals don't return
hallucinated canon.

**Knowledge-DB scope:** facts-only. Only ``facts`` carries
``seeded_scene`` in the current schema
(`workflow/knowledge/knowledge_graph.py:141-163`); entities and edges
have no scene attribution. We intentionally do NOT sweep orphan
entities: facts reference entities by string name (no FK), so a canon
entity with facts but zero relationship edges would look "orphan" and
get wiped — risking loss of real canon. Retrieval already down-weights
orphan entities, so leaving them is low-signal, not contaminating.

**Story-DB scope (added 2026-04-19 per task #49 / Mission 26 Probe B):**
`scene_history` + `extracted_facts` + `character_states.last_updated_scene`
+ `promises.created_scene` are all drift-attributed. Cleanup DELETEs
rows matching the drift scene pattern across all four tables. This
closes the Mission 26 finding: Fix E previously orphaned 80+
extracted_facts rows + 3 scene_history tombstones + 9 character_states
residuals keyed to drift scene_ids.

**Follow-up:** full scene-scoped entity/edge cleanup on knowledge.db
needs a schema expansion (add ``seeded_scene`` columns to ``entities``
and ``edges``). Out of scope for this commit; tracked separately.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

# Drift seeded_scene pattern: "<universe_id>-B<n>-C<n>-S<n>_chunk_<n>" (or trailing -<something>).
# Matches the id shape emitted by the scene draft/commit pipeline; canon-doc
# seeded_scene values use the doc filename instead (no -B*-C*-S*_chunk).
_DRIFT_SCENE_RE = re.compile(r"^.+-B\d+-C\d+-S\d+_chunk_\d+")


def _drift_pattern_sql(universe_id: str) -> tuple[str, tuple[str, ...]]:
    """SQL fragment + params matching drift `seeded_scene` values for this universe."""
    # GLOB is case-sensitive and fast; matches "<universe>-B*-C*-S*_chunk_*".
    return (
        "seeded_scene GLOB ?",
        (f"{universe_id}-B*-C*-S*_chunk_*",),
    )


def cleanup_drift_kg(universe_id: str, kg_db_path: str) -> dict[str, int]:
    """Delete drift-seeded facts universe-wide.

    Parameters
    ----------
    universe_id : str
        Universe slug used as the prefix of drift scene ids.
    kg_db_path : str
        Absolute path to the universe's ``knowledge.db`` SQLite file.

    Returns
    -------
    dict
        ``{"facts_deleted": N}``. Zero on missing db / schema mismatch
        (fail-open).
    """
    result = {"facts_deleted": 0}
    if not universe_id or not kg_db_path:
        return result
    db_path = Path(kg_db_path)
    if not db_path.exists():
        logger.info("drift_cleanup: kg db not found at %s; skipping", kg_db_path)
        return result

    where, params = _drift_pattern_sql(universe_id)
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.cursor()
            cur.execute(f"DELETE FROM facts WHERE {where}", params)
            result["facts_deleted"] = cur.rowcount or 0
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.warning("drift_cleanup: sqlite error on %s: %s", kg_db_path, e)
        return result

    if result["facts_deleted"]:
        logger.warning(
            "drift_cleanup: %d drift facts deleted from %s "
            "(universe=%s) — forward defense against pre-synthesis drift",
            result["facts_deleted"], kg_db_path, universe_id,
        )
    return result


def is_drift_seeded_scene(seeded_scene: str) -> bool:
    """Utility: does this seeded_scene value match the drift pattern?"""
    return bool(seeded_scene and _DRIFT_SCENE_RE.match(seeded_scene))


# Scene-id drift pattern used against story.db columns that hold raw
# scene ids (no "_chunk" suffix). scene_history.scene_id is
# "<universe>-B*-C*-S*"; extracted_facts.scene_id, promises.created_scene,
# character_states.last_updated_scene follow the same shape.
def _scene_id_drift_pattern(universe_id: str) -> str:
    return f"{universe_id}-B*-C*-S*"


def cleanup_drift_story_db(
    universe_id: str, story_db_path: str,
) -> dict[str, int]:
    """Delete drift-seeded rows from the legacy story.db.

    Removes rows matching the drift scene pattern from all four tables
    that carry scene attribution:
      - ``scene_history.scene_id``        GLOB match → DELETE
      - ``extracted_facts.scene_id``      GLOB match → DELETE
      - ``character_states.last_updated_scene`` GLOB match → DELETE
      - ``promises.created_scene``        GLOB match → DELETE

    Tables that don't exist yet (fresh or migrating universes) are
    silently skipped. Missing file or sqlite error → returns zeros
    (fail-open).

    Returns
    -------
    dict
        Per-table deletion counts, keyed by
        ``scene_history_deleted`` / ``extracted_facts_deleted`` /
        ``character_states_deleted`` / ``promises_deleted``.
    """
    result = {
        "scene_history_deleted": 0,
        "extracted_facts_deleted": 0,
        "character_states_deleted": 0,
        "promises_deleted": 0,
    }
    if not universe_id or not story_db_path:
        return result
    db_path = Path(story_db_path)
    if not db_path.exists():
        logger.info(
            "drift_cleanup: story db not found at %s; skipping",
            story_db_path,
        )
        return result

    pattern = _scene_id_drift_pattern(universe_id)

    table_and_column = [
        ("scene_history", "scene_id", "scene_history_deleted"),
        ("extracted_facts", "scene_id", "extracted_facts_deleted"),
        ("character_states", "last_updated_scene", "character_states_deleted"),
        ("promises", "created_scene", "promises_deleted"),
    ]

    try:
        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.cursor()
            for table, column, result_key in table_and_column:
                # Table may not exist on fresh / migrating universes.
                exists = cur.execute(
                    "SELECT 1 FROM sqlite_master "
                    "WHERE type='table' AND name=?",
                    (table,),
                ).fetchone()
                if not exists:
                    continue
                cur.execute(
                    f"DELETE FROM {table} WHERE {column} GLOB ?",
                    (pattern,),
                )
                result[result_key] = cur.rowcount or 0
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.warning(
            "drift_cleanup: sqlite error on %s: %s", story_db_path, e,
        )
        return result

    total = sum(result.values())
    if total:
        logger.warning(
            "drift_cleanup: %d drift row(s) deleted from %s (universe=%s): "
            "%s — forward defense against pre-synthesis drift",
            total, story_db_path, universe_id, result,
        )
    return result


def cleanup_drift_all(
    universe_id: str,
    kg_db_path: str,
    story_db_path: str,
) -> dict[str, int]:
    """Run both KG and story-db drift cleanups for a universe.

    Convenience wrapper so the Fix E call site issues one cleanup call
    that scopes across both DBs. Returns the merged counts dict.
    """
    merged: dict[str, int] = {}
    merged.update(cleanup_drift_kg(universe_id, kg_db_path))
    merged.update(cleanup_drift_story_db(universe_id, story_db_path))
    return merged
