"""Post-synthesis drift-KG cleanup (Task #17 Fix E).

When a pre-synthesis draft cycle has contaminated the KG with facts seeded
against placeholder-premise scenes (pattern: ``{universe}-B*-C*-S*_chunk_*``),
the first successful canon synthesis should wipe those rows universe-wide
so future retrievals don't return hallucinated canon.

**Scope:** facts-only. Only ``facts`` carries ``seeded_scene`` in the
current schema (`workflow/knowledge/knowledge_graph.py:141-163`);
entities and edges have no scene attribution. We intentionally do NOT
sweep orphan entities: facts reference entities by string name (no FK),
so a canon entity with facts but zero relationship edges would look
"orphan" and get wiped — risking loss of real canon. Retrieval already
down-weights orphan entities, so leaving them is low-signal, not
contaminating.

**Follow-up:** full scene-scoped entity/edge cleanup needs a schema
expansion (add ``seeded_scene`` columns to ``entities`` and ``edges``).
Out of scope for this commit; tracked as its own task.
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
