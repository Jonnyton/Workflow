"""Contribution events ledger — Phase B item 8 (Task #71 schema; Task #72+ emit-wiring).

Single-table append-only events ledger. All five contribution surfaces emit
into ``contribution_events``; the bounty calculator (Phase 2 dispatch) reads.

Spec: ``docs/design-notes/2026-04-25-contribution-ledger-proposal.md`` §1.

This module owns ONLY the schema constant + initializer. Phase 2 emit-wiring
will land helpers (``record_contribution_event``, ``list_events_by_actor``,
etc.) in this module — single-source layout matches ``branch_versions.py``.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

# ── DDL ──────────────────────────────────────────────────────────────────────

CONTRIBUTION_EVENTS_SCHEMA = """
    -- Phase B item 8 (Task #71). One row per contribution event.
    -- Append-only: weight is REAL signed (positive = credit; negative =
    -- regression). source_run_id NULLable for non-run events (PR webhook,
    -- gate-cite of pre-existing wiki page). FK to runs(run_id) is
    -- enforceable because both tables live in the same SQLite file.
    CREATE TABLE IF NOT EXISTS contribution_events (
        event_id              TEXT PRIMARY KEY,
        event_type            TEXT NOT NULL,
        actor_id              TEXT NOT NULL,
        actor_handle          TEXT NOT NULL DEFAULT '',
        source_run_id         TEXT,
        source_artifact_id    TEXT,
        source_artifact_kind  TEXT NOT NULL DEFAULT '',
        weight                REAL NOT NULL DEFAULT 1.0,
        occurred_at           REAL NOT NULL,
        metadata_json         TEXT NOT NULL DEFAULT '{}',
        FOREIGN KEY (source_run_id) REFERENCES runs(run_id)
    );

    CREATE INDEX IF NOT EXISTS idx_contribution_events_window
        ON contribution_events(occurred_at);
    CREATE INDEX IF NOT EXISTS idx_contribution_events_actor
        ON contribution_events(actor_id, occurred_at);
    CREATE INDEX IF NOT EXISTS idx_contribution_events_artifact
        ON contribution_events(source_artifact_id, source_artifact_kind);
    CREATE INDEX IF NOT EXISTS idx_contribution_events_run
        ON contribution_events(source_run_id);
"""


def _connect(base_path: str | Path) -> sqlite3.Connection:
    from workflow.runs import runs_db_path

    path = runs_db_path(base_path)
    conn = sqlite3.connect(str(path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def initialize_contribution_events_db(base_path: str | Path) -> None:
    """Create contribution_events table + indexes if not present.

    Idempotent — uses ``IF NOT EXISTS`` clauses throughout. Concatenated
    into the runs DB schema by ``workflow.runs.initialize_runs_db`` so
    a single ``initialize_runs_db`` call brings up all run-side tables.
    """
    from workflow.runs import runs_db_path

    runs_db_path(base_path)  # ensure parent runs DB path exists
    with _connect(base_path) as conn:
        conn.executescript(CONTRIBUTION_EVENTS_SCHEMA)
