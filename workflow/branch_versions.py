"""Content-addressed branch snapshot storage.

Spec: docs/vetted-specs.md §publish_version.

A published version is a write-once snapshot of a BranchDefinition's full
topology (node_defs, edges, conditional_edges, state_schema, entry_point)
at the moment of publish. It is immutable after creation.

``publish_version`` mints a new ``branch_version_id`` of the form
``<branch_def_id>@<sha256_prefix8>`` and stores the canonical JSON in
the ``branch_versions`` SQLite table inside the runs database.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# ── DDL ──────────────────────────────────────────────────────────────────────

BRANCH_VERSIONS_SCHEMA = """
    CREATE TABLE IF NOT EXISTS branch_versions (
        branch_version_id   TEXT PRIMARY KEY,
        branch_def_id       TEXT NOT NULL,
        content_hash        TEXT NOT NULL,
        snapshot_json       TEXT NOT NULL,
        notes               TEXT NOT NULL DEFAULT '',
        publisher           TEXT NOT NULL,
        published_at        TEXT NOT NULL,
        parent_version_id   TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_bv_branch_def
        ON branch_versions(branch_def_id, published_at);
    CREATE INDEX IF NOT EXISTS idx_bv_hash
        ON branch_versions(content_hash);
"""


# ── Dataclass ─────────────────────────────────────────────────────────────────

@dataclass
class BranchVersion:
    branch_version_id: str
    branch_def_id: str
    content_hash: str
    snapshot: dict[str, Any]
    notes: str
    publisher: str
    published_at: str
    parent_version_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "branch_version_id": self.branch_version_id,
            "branch_def_id": self.branch_def_id,
            "content_hash": self.content_hash,
            "snapshot": self.snapshot,
            "notes": self.notes,
            "publisher": self.publisher,
            "published_at": self.published_at,
            "parent_version_id": self.parent_version_id,
        }


# ── Storage helpers ───────────────────────────────────────────────────────────

def _connect(base_path: str | Path) -> sqlite3.Connection:
    from workflow.runs import runs_db_path
    path = runs_db_path(base_path)
    conn = sqlite3.connect(str(path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def initialize_branch_versions_db(base_path: str | Path) -> None:
    """Create branch_versions table if it does not exist."""
    from workflow.runs import runs_db_path
    runs_db_path(base_path)  # ensure parent runs DB exists
    with _connect(base_path) as conn:
        conn.executescript(BRANCH_VERSIONS_SCHEMA)


def _canonical_snapshot(branch_dict: dict[str, Any]) -> dict[str, Any]:
    """Extract only the topology fields that define version identity."""
    return {
        "branch_def_id": branch_dict.get("branch_def_id", ""),
        "entry_point": branch_dict.get("entry_point", ""),
        "graph_nodes": branch_dict.get("graph_nodes", []),
        "edges": branch_dict.get("edges", []),
        "conditional_edges": branch_dict.get("conditional_edges", []),
        "node_defs": branch_dict.get("node_defs", []),
        "state_schema": branch_dict.get("state_schema", []),
    }


def compute_content_hash(snapshot: dict[str, Any]) -> str:
    """SHA-256 over canonical JSON serialization of the snapshot."""
    canonical = json.dumps(snapshot, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def publish_branch_version(
    base_path: str | Path,
    branch_dict: dict[str, Any],
    *,
    publisher: str = "anonymous",
    notes: str = "",
    parent_version_id: str | None = None,
) -> BranchVersion:
    """Mint an immutable snapshot of branch_dict.

    Returns the BranchVersion. If an identical content_hash already exists
    for this branch_def_id, returns the existing record (deterministic).
    """
    from datetime import datetime, timezone

    initialize_branch_versions_db(base_path)

    branch_def_id = branch_dict.get("branch_def_id", "")
    if not branch_def_id:
        raise ValueError("branch_dict must contain 'branch_def_id'.")

    snapshot = _canonical_snapshot(branch_dict)
    content_hash = compute_content_hash(snapshot)

    with _connect(base_path) as conn:
        # Deterministic: same content_hash for same branch_def_id returns existing.
        existing = conn.execute(
            "SELECT * FROM branch_versions "
            "WHERE branch_def_id = ? AND content_hash = ?",
            (branch_def_id, content_hash),
        ).fetchone()
        if existing is not None:
            return _row_to_version(existing)

        branch_version_id = f"{branch_def_id}@{content_hash[:8]}"
        # Handle the (rare) case where hash prefix collides with a different hash.
        collision = conn.execute(
            "SELECT content_hash FROM branch_versions WHERE branch_version_id = ?",
            (branch_version_id,),
        ).fetchone()
        if collision and collision["content_hash"] != content_hash:
            branch_version_id = f"{branch_def_id}@{content_hash[:16]}"

        if parent_version_id:
            _validate_version_exists(conn, parent_version_id)

        published_at = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """
            INSERT OR IGNORE INTO branch_versions
                (branch_version_id, branch_def_id, content_hash,
                 snapshot_json, notes, publisher, published_at, parent_version_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                branch_version_id,
                branch_def_id,
                content_hash,
                json.dumps(snapshot, default=str),
                notes,
                publisher,
                published_at,
                parent_version_id,
            ),
        )
        # Re-fetch to get exact stored row (handles INSERT OR IGNORE race).
        row = conn.execute(
            "SELECT * FROM branch_versions WHERE branch_version_id = ?",
            (branch_version_id,),
        ).fetchone()
        return _row_to_version(row)


def get_branch_version(
    base_path: str | Path,
    branch_version_id: str,
) -> BranchVersion | None:
    """Fetch a published version by ID. Returns None if not found."""
    initialize_branch_versions_db(base_path)
    with _connect(base_path) as conn:
        row = conn.execute(
            "SELECT * FROM branch_versions WHERE branch_version_id = ?",
            (branch_version_id,),
        ).fetchone()
    if row is None:
        return None
    return _row_to_version(row)


def list_branch_versions(
    base_path: str | Path,
    branch_def_id: str,
    *,
    limit: int = 50,
) -> list[BranchVersion]:
    """List published versions for a branch, newest first."""
    initialize_branch_versions_db(base_path)
    limit = min(max(1, limit), 500)
    with _connect(base_path) as conn:
        rows = conn.execute(
            "SELECT * FROM branch_versions WHERE branch_def_id = ? "
            "ORDER BY published_at DESC LIMIT ?",
            (branch_def_id, limit),
        ).fetchall()
    return [_row_to_version(r) for r in rows]


def _validate_version_exists(conn: sqlite3.Connection, version_id: str) -> None:
    row = conn.execute(
        "SELECT 1 FROM branch_versions WHERE branch_version_id = ?",
        (version_id,),
    ).fetchone()
    if row is None:
        raise KeyError(f"parent_version_id '{version_id}' not found.")


def _row_to_version(row: sqlite3.Row) -> BranchVersion:
    try:
        snapshot = json.loads(row["snapshot_json"])
    except (json.JSONDecodeError, TypeError):
        snapshot = {}
    return BranchVersion(
        branch_version_id=row["branch_version_id"],
        branch_def_id=row["branch_def_id"],
        content_hash=row["content_hash"],
        snapshot=snapshot,
        notes=row["notes"] or "",
        publisher=row["publisher"],
        published_at=row["published_at"],
        parent_version_id=row["parent_version_id"],
    )


__all__ = [
    "BranchVersion",
    "BRANCH_VERSIONS_SCHEMA",
    "compute_content_hash",
    "get_branch_version",
    "initialize_branch_versions_db",
    "list_branch_versions",
    "publish_branch_version",
]
