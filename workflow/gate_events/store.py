"""Storage layer for gate_event — real-world outcome attestation.

Spec: docs/vetted-specs.md §gate_event.

Functions:
  attest_gate_event   — create a new gate event with N citation links
  verify_gate_event   — transition status to 'verified' (different user required)
  dispute_gate_event  — transition status to 'disputed'
  retract_gate_event  — transition status to 'retracted' (audit trail preserved)
  get_gate_event      — fetch by event_id
  list_gate_events    — filter by goal_id and/or branch_version_id

All writes use the runs.db path (gate_events are universe-scoped, not global).
Schema migration is idempotent via migrate_gate_event_schema().
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from workflow.gate_events.schema import (
    GateEvent,
    GateEventCite,
    migrate_gate_event_schema,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runs_db(base_path: str | Path) -> Path:
    from workflow.runs import runs_db_path
    return runs_db_path(base_path)


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _ensure_schema(base_path: str | Path) -> Path:
    db = _runs_db(base_path)
    with _connect(db) as conn:
        migrate_gate_event_schema(conn)
    return db


def _row_to_event(row: sqlite3.Row, cites: list[GateEventCite]) -> GateEvent:
    d = dict(row)
    evt = GateEvent.from_row(d)
    evt.cites.extend(cites)
    return evt


def _load_cites(conn: sqlite3.Connection, event_id: str) -> list[GateEventCite]:
    rows = conn.execute(
        "SELECT * FROM gate_event_cite WHERE event_id = ? ORDER BY cited_at",
        (event_id,),
    ).fetchall()
    return [GateEventCite.from_row(dict(r)) for r in rows]


def attest_gate_event(
    base_path: str | Path,
    *,
    goal_id: str,
    event_type: str,
    event_date: str,
    attested_by: str,
    cites: list[dict[str, Any]],
    notes: str = "",
    evidence_urls: list[str] | None = None,
) -> GateEvent:
    """Create a new gate_event attestation record.

    Args:
        cites: list of dicts with keys:
            branch_version_id (required), run_id (optional), contribution_summary (optional)
    """
    if not goal_id:
        raise ValueError("goal_id is required")
    if not event_type:
        raise ValueError("event_type is required")
    if not event_date:
        raise ValueError("event_date is required")
    if not attested_by:
        raise ValueError("attested_by is required")

    db = _ensure_schema(base_path)
    event_id = str(uuid.uuid4())
    attested_at = _now()

    with _connect(db) as conn:
        # Validate all branch_version_ids exist if branch_versions table present.
        for cite in cites:
            bvid = cite.get("branch_version_id", "")
            if bvid:
                row = conn.execute(
                    "SELECT 1 FROM branch_versions WHERE branch_version_id = ?",
                    (bvid,),
                ).fetchone()
                if row is None:
                    raise KeyError(
                        f"branch_version_id {bvid!r} not found in branch_versions"
                    )

        conn.execute(
            """
            INSERT INTO gate_event
                (event_id, goal_id, event_type, event_date,
                 attested_by, attested_at, verification_status, notes)
            VALUES (?, ?, ?, ?, ?, ?, 'attested', ?)
            """,
            (event_id, goal_id, event_type, event_date, attested_by, attested_at, notes),
        )

        cite_records: list[GateEventCite] = []
        for cite in cites:
            cite_id = str(uuid.uuid4())
            bvid = cite.get("branch_version_id", "")
            run_id = cite.get("run_id")
            summary = cite.get("contribution_summary", "")
            cited_at = _now()
            conn.execute(
                """
                INSERT INTO gate_event_cite
                    (cite_id, event_id, branch_version_id, run_id,
                     contribution_summary, cited_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (cite_id, event_id, bvid, run_id, summary, cited_at),
            )
            cite_records.append(
                GateEventCite(
                    cite_id=cite_id,
                    event_id=event_id,
                    branch_version_id=bvid,
                    cited_at=cited_at,
                    run_id=run_id,
                    contribution_summary=summary,
                )
            )

        row = conn.execute(
            "SELECT * FROM gate_event WHERE event_id = ?", (event_id,)
        ).fetchone()

    evt = GateEvent.from_row(dict(row))
    evt.cites.extend(cite_records)
    return evt


def verify_gate_event(
    base_path: str | Path,
    *,
    event_id: str,
    verifier_id: str,
) -> GateEvent:
    """Transition gate_event to 'verified'. Verifier must differ from attester."""
    db = _ensure_schema(base_path)
    with _connect(db) as conn:
        row = conn.execute(
            "SELECT * FROM gate_event WHERE event_id = ?", (event_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"gate_event {event_id!r} not found")
        cites = _load_cites(conn, event_id)
        evt = _row_to_event(row, cites)
        # Raises ValueError on self-verify or wrong status.
        verified_at = _now()
        updated = evt.verify(verifier_id=verifier_id, verified_at=verified_at)
        conn.execute(
            """
            UPDATE gate_event
               SET verification_status='verified', verified_by=?, verified_at=?
             WHERE event_id=?
            """,
            (verifier_id, verified_at, event_id),
        )
    return updated


def dispute_gate_event(
    base_path: str | Path,
    *,
    event_id: str,
    disputed_by: str,
    reason: str,
) -> GateEvent:
    """Transition gate_event to 'disputed'."""
    db = _ensure_schema(base_path)
    with _connect(db) as conn:
        row = conn.execute(
            "SELECT * FROM gate_event WHERE event_id = ?", (event_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"gate_event {event_id!r} not found")
        cites = _load_cites(conn, event_id)
        evt = _row_to_event(row, cites)
        disputed_at = _now()
        updated = evt.dispute(disputed_by=disputed_by, disputed_at=disputed_at, reason=reason)
        conn.execute(
            """
            UPDATE gate_event
               SET verification_status='disputed', disputed_by=?, disputed_at=?, dispute_reason=?
             WHERE event_id=?
            """,
            (disputed_by, disputed_at, reason, event_id),
        )
    return updated


def retract_gate_event(
    base_path: str | Path,
    *,
    event_id: str,
    retracted_by: str,
    note: str = "",
) -> GateEvent:
    """Transition gate_event to 'retracted'. Audit trail preserved."""
    db = _ensure_schema(base_path)
    with _connect(db) as conn:
        row = conn.execute(
            "SELECT * FROM gate_event WHERE event_id = ?", (event_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"gate_event {event_id!r} not found")
        cites = _load_cites(conn, event_id)
        evt = _row_to_event(row, cites)
        retracted_at = _now()
        updated = evt.retract(retracted_by=retracted_by, retracted_at=retracted_at, note=note)
        conn.execute(
            """
            UPDATE gate_event
               SET verification_status='retracted',
                   retracted_by=?,
                   retracted_at=?,
                   retraction_note=?
             WHERE event_id=?
            """,
            (retracted_by, retracted_at, note, event_id),
        )
    return updated


def get_gate_event(
    base_path: str | Path,
    event_id: str,
) -> GateEvent | None:
    """Fetch a gate_event by ID. Returns None if not found."""
    db = _ensure_schema(base_path)
    with _connect(db) as conn:
        row = conn.execute(
            "SELECT * FROM gate_event WHERE event_id = ?", (event_id,)
        ).fetchone()
        if row is None:
            return None
        cites = _load_cites(conn, event_id)
    return _row_to_event(row, cites)


def list_gate_events(
    base_path: str | Path,
    *,
    goal_id: str = "",
    branch_version_id: str = "",
    include_retracted: bool = True,
    limit: int = 50,
) -> list[GateEvent]:
    """List gate events filtered by goal_id and/or branch_version_id."""
    db = _ensure_schema(base_path)
    limit = min(max(1, limit), 500)

    with _connect(db) as conn:
        if branch_version_id:
            # Join through gate_event_cite to filter by branch_version_id.
            query = """
                SELECT DISTINCT ge.*
                  FROM gate_event ge
                  JOIN gate_event_cite gec ON ge.event_id = gec.event_id
                 WHERE gec.branch_version_id = ?
            """
            params: list[Any] = [branch_version_id]
            if goal_id:
                query += " AND ge.goal_id = ?"
                params.append(goal_id)
            if not include_retracted:
                query += " AND ge.verification_status != 'retracted'"
            query += " ORDER BY ge.attested_at DESC LIMIT ?"
            params.append(limit)
        else:
            query = "SELECT * FROM gate_event"
            params = []
            clauses = []
            if goal_id:
                clauses.append("goal_id = ?")
                params.append(goal_id)
            if not include_retracted:
                clauses.append("verification_status != 'retracted'")
            if clauses:
                query += " WHERE " + " AND ".join(clauses)
            query += " ORDER BY attested_at DESC LIMIT ?"
            params.append(limit)

        rows = conn.execute(query, params).fetchall()
        result = []
        for row in rows:
            eid = row["event_id"]
            cites = _load_cites(conn, eid)
            result.append(_row_to_event(row, cites))

    return result


__all__ = [
    "attest_gate_event",
    "dispute_gate_event",
    "get_gate_event",
    "list_gate_events",
    "retract_gate_event",
    "verify_gate_event",
]
