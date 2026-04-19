"""Run orchestration for community-designed branches.

Stores run metadata and per-step events in ``<base>/.runs.db`` so Phase 4
can judge, diff, and iterate on run output. Runs are synchronous in v1
per PLAN.md discussion (see task #39 for the async follow-up) — a single
``start_run`` call compiles, invokes, and persists the final state before
returning. That makes reasoning about cancel/thread-isolation trivial:
one run per tool call, no background tasks to babysit.

DB layout:

- ``runs``   — one row per run: id, branch_def_id, status, thread_id,
               inputs_json, output_json, started_at, finished_at, error.
- ``events`` — one row per node step: run_id, step_index, node_id,
               status, started_at, finished_at, detail_json.

Concurrency-safe across processes via WAL. No long-held connection —
each operation opens, commits, closes.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import sqlite3
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from workflow.branches import BranchDefinition
from workflow.graph_compiler import (
    CompilerError,
    NodeTimeoutError,
    UnapprovedNodeError,
    compile_branch,
)

logger = logging.getLogger(__name__)


RUN_STATUS_QUEUED = "queued"
RUN_STATUS_RUNNING = "running"
RUN_STATUS_COMPLETED = "completed"
RUN_STATUS_FAILED = "failed"
RUN_STATUS_CANCELLED = "cancelled"
RUN_STATUS_INTERRUPTED = "interrupted"

NODE_STATUS_PENDING = "pending"
NODE_STATUS_RUNNING = "running"
NODE_STATUS_RAN = "ran"
NODE_STATUS_FAILED = "failed"


class RunCancelledError(Exception):
    """Raised from an event_sink when a run has been cancelled so the
    graph invocation unwinds cleanly. Caught by the executor and
    reported as ``status=cancelled``."""


def runs_db_path(base_path: str | Path) -> Path:
    return Path(base_path) / ".runs.db"


@contextlib.contextmanager
def _connect(base_path: str | Path) -> sqlite3.Connection:
    db = runs_db_path(base_path)
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _now() -> float:
    return time.time()


def initialize_runs_db(base_path: str | Path) -> Path:
    """Ensure runs, events, and Phase 4 judgment tables exist. Idempotent."""
    schema = """
    CREATE TABLE IF NOT EXISTS runs (
        run_id         TEXT PRIMARY KEY,
        branch_def_id  TEXT NOT NULL,
        run_name       TEXT NOT NULL DEFAULT '',
        thread_id      TEXT NOT NULL,
        status         TEXT NOT NULL DEFAULT 'queued',
        actor          TEXT NOT NULL DEFAULT 'anonymous',
        inputs_json    TEXT NOT NULL DEFAULT '{}',
        output_json    TEXT NOT NULL DEFAULT '{}',
        error          TEXT NOT NULL DEFAULT '',
        last_node_id   TEXT NOT NULL DEFAULT '',
        started_at     REAL NOT NULL,
        finished_at    REAL
    );

    CREATE INDEX IF NOT EXISTS idx_runs_branch ON runs(branch_def_id);
    CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);

    CREATE TABLE IF NOT EXISTS run_events (
        run_id         TEXT NOT NULL,
        step_index     INTEGER NOT NULL,
        node_id        TEXT NOT NULL,
        status         TEXT NOT NULL,
        started_at     REAL NOT NULL,
        finished_at    REAL,
        detail_json    TEXT NOT NULL DEFAULT '{}',
        PRIMARY KEY (run_id, step_index)
    );

    CREATE INDEX IF NOT EXISTS idx_events_run ON run_events(run_id);

    CREATE TABLE IF NOT EXISTS run_cancels (
        run_id         TEXT PRIMARY KEY,
        requested_at   REAL NOT NULL
    );

    -- Phase 4: eval + iteration hooks.

    CREATE TABLE IF NOT EXISTS run_judgments (
        judgment_id    TEXT PRIMARY KEY,
        run_id         TEXT NOT NULL,
        node_id        TEXT,
        text           TEXT NOT NULL,
        tags_json      TEXT NOT NULL DEFAULT '[]',
        author         TEXT NOT NULL,
        timestamp      TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_judgments_run
        ON run_judgments(run_id);
    CREATE INDEX IF NOT EXISTS idx_judgments_node
        ON run_judgments(node_id);

    CREATE TABLE IF NOT EXISTS run_lineage (
        run_id                    TEXT PRIMARY KEY,
        parent_run_id             TEXT,
        branch_def_id             TEXT NOT NULL,
        branch_version            INTEGER NOT NULL,
        edits_since_parent_json   TEXT NOT NULL DEFAULT '[]',
        timestamp                 TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_lineage_parent
        ON run_lineage(parent_run_id);
    CREATE INDEX IF NOT EXISTS idx_lineage_branch
        ON run_lineage(branch_def_id, branch_version);

    CREATE TABLE IF NOT EXISTS node_edit_audit (
        audit_id                    TEXT PRIMARY KEY,
        branch_def_id               TEXT NOT NULL,
        version_before              INTEGER NOT NULL,
        version_after               INTEGER NOT NULL,
        nodes_changed_json          TEXT NOT NULL,
        triggered_by_judgment_id    TEXT,
        timestamp                   TEXT NOT NULL,
        node_before_json            TEXT NOT NULL DEFAULT '{}',
        node_after_json             TEXT NOT NULL DEFAULT '{}',
        edit_kind                   TEXT NOT NULL DEFAULT 'update'
    );

    CREATE INDEX IF NOT EXISTS idx_audit_branch
        ON node_edit_audit(branch_def_id);
    """
    with _connect(base_path) as conn:
        conn.executescript(schema)
        # Migration: older installs may predate the body-snapshot columns
        # added for rollback support. SQLite doesn't have
        # ``ADD COLUMN IF NOT EXISTS``, so probe pragma and add on-demand.
        existing = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(node_edit_audit)")
        }
        for col, ddl in (
            ("node_before_json", "TEXT NOT NULL DEFAULT '{}'"),
            ("node_after_json",  "TEXT NOT NULL DEFAULT '{}'"),
            ("edit_kind",        "TEXT NOT NULL DEFAULT 'update'"),
        ):
            if col not in existing:
                conn.execute(
                    f"ALTER TABLE node_edit_audit ADD COLUMN {col} {ddl}"
                )
    return runs_db_path(base_path)


# ─────────────────────────────────────────────────────────────────────────────
# Run record shape
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class RunStepEvent:
    run_id: str
    step_index: int
    node_id: str
    status: str
    started_at: float
    finished_at: float | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "step_index": self.step_index,
            "node_id": self.node_id,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "detail": self.detail,
        }


def _row_to_run(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "run_id": row["run_id"],
        "branch_def_id": row["branch_def_id"],
        "run_name": row["run_name"],
        "thread_id": row["thread_id"],
        "status": row["status"],
        "actor": row["actor"],
        "inputs": json.loads(row["inputs_json"] or "{}"),
        "output": json.loads(row["output_json"] or "{}"),
        "error": row["error"],
        "last_node_id": row["last_node_id"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
    }


def _row_to_event(row: sqlite3.Row) -> dict[str, Any]:
    detail_raw = row["detail_json"] or "{}"
    try:
        detail = json.loads(detail_raw)
    except json.JSONDecodeError:
        detail = {}
    return {
        "step_index": row["step_index"],
        "node_id": row["node_id"],
        "status": row["status"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "detail": detail,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Persistence CRUD
# ─────────────────────────────────────────────────────────────────────────────


def create_run(
    base_path: str | Path,
    *,
    branch_def_id: str,
    thread_id: str,
    inputs: dict[str, Any],
    run_name: str = "",
    actor: str = "anonymous",
) -> str:
    initialize_runs_db(base_path)
    run_id = uuid.uuid4().hex[:16]
    with _connect(base_path) as conn:
        conn.execute(
            """
            INSERT INTO runs (
                run_id, branch_def_id, run_name, thread_id,
                status, actor, inputs_json, started_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id, branch_def_id, run_name, thread_id,
                RUN_STATUS_QUEUED, actor,
                json.dumps(inputs, default=str), _now(),
            ),
        )
    return run_id


def update_run_status(
    base_path: str | Path,
    run_id: str,
    *,
    status: str | None = None,
    output: dict[str, Any] | None = None,
    error: str | None = None,
    last_node_id: str | None = None,
    finished_at: float | None = None,
) -> None:
    sets: list[str] = []
    params: list[Any] = []
    if status is not None:
        sets.append("status = ?")
        params.append(status)
    if output is not None:
        sets.append("output_json = ?")
        params.append(json.dumps(output, default=str))
    if error is not None:
        sets.append("error = ?")
        params.append(error)
    if last_node_id is not None:
        sets.append("last_node_id = ?")
        params.append(last_node_id)
    if finished_at is not None:
        sets.append("finished_at = ?")
        params.append(finished_at)
    if not sets:
        return
    params.append(run_id)
    with _connect(base_path) as conn:
        conn.execute(
            f"UPDATE runs SET {', '.join(sets)} WHERE run_id = ?",
            params,
        )


def get_run(base_path: str | Path, run_id: str) -> dict[str, Any] | None:
    initialize_runs_db(base_path)
    with _connect(base_path) as conn:
        row = conn.execute(
            "SELECT * FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
    return _row_to_run(row) if row else None


def list_runs(
    base_path: str | Path,
    *,
    branch_def_id: str = "",
    status: str = "",
    limit: int = 50,
) -> list[dict[str, Any]]:
    initialize_runs_db(base_path)
    clauses: list[str] = []
    params: list[Any] = []
    if branch_def_id:
        clauses.append("branch_def_id = ?")
        params.append(branch_def_id)
    if status:
        clauses.append("status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with _connect(base_path) as conn:
        rows = conn.execute(
            f"SELECT * FROM runs {where} "
            f"ORDER BY started_at DESC LIMIT ?",
            (*params, max(1, int(limit))),
        ).fetchall()
    return [_row_to_run(r) for r in rows]


def record_event(
    base_path: str | Path, event: RunStepEvent,
) -> None:
    with _connect(base_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO run_events (
                run_id, step_index, node_id, status,
                started_at, finished_at, detail_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.run_id, event.step_index, event.node_id,
                event.status, event.started_at, event.finished_at,
                json.dumps(event.detail, default=str),
            ),
        )


def list_events(
    base_path: str | Path,
    run_id: str,
    *,
    since_step: int = -1,
) -> list[dict[str, Any]]:
    """Return events with ``step_index > since_step``, ascending.

    ``step_index`` is an opaque, monotonically-increasing cursor — NOT
    a node-count ordinal. One node can emit multiple events (started,
    ran, timeout, etc.) each with its own step_index, so cursor
    arithmetic ("I have N events, skip to step N") is incorrect.
    Always pass the last-seen step_index back as ``since_step``.
    """
    initialize_runs_db(base_path)
    with _connect(base_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM run_events
            WHERE run_id = ? AND step_index > ?
            ORDER BY step_index ASC
            """,
            (run_id, int(since_step)),
        ).fetchall()
    return [_row_to_event(r) for r in rows]


# Terminal run statuses end a long-poll immediately regardless of
# whether new events have landed. Callers don't need to wait the full
# max_wait_s once the run has resolved.
_TERMINAL_STATUSES = frozenset({
    "completed", "failed", "cancelled",
})


def await_run_events(
    base_path: str | Path,
    run_id: str,
    *,
    since_step: int = -1,
    max_wait_s: float = 60.0,
    poll_interval_s: float = 0.25,
) -> dict[str, Any]:
    """Long-poll for new run events. Block up to ``max_wait_s`` (#65).

    Returns as soon as any of:
    - a new event lands with ``step_index > since_step``
    - the run reaches a terminal status (completed/failed/cancelled)
    - the deadline elapses

    Returns ``{"events": [...], "status": "...", "next_cursor": N,
    "waited_s": float, "reason": "events|terminal|timeout"}``. The
    caller uses ``next_cursor`` as the next ``since_step``.

    ``step_index`` (and therefore ``next_cursor``) is an opaque,
    monotonically-increasing cursor — NOT a node-count ordinal. A
    single node may emit several events, each with its own
    step_index, so do not treat it as "number of nodes completed".
    """
    deadline = time.monotonic() + max(0.0, float(max_wait_s))
    poll_interval = max(0.05, float(poll_interval_s))
    started = time.monotonic()
    while True:
        events = list_events(base_path, run_id, since_step=since_step)
        record = get_run(base_path, run_id)
        status = (record or {}).get("status", "unknown")
        if events:
            reason = "events"
            break
        if status in _TERMINAL_STATUSES:
            reason = "terminal"
            break
        if time.monotonic() >= deadline:
            reason = "timeout"
            break
        time.sleep(poll_interval)

    next_cursor = max(
        (e.get("step_index", since_step) for e in events),
        default=since_step,
    )
    return {
        "events": events,
        "status": status,
        "next_cursor": next_cursor,
        "waited_s": round(time.monotonic() - started, 3),
        "reason": reason,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Phase 4: judgments, lineage, node edit audit
# ─────────────────────────────────────────────────────────────────────────────


def _iso_now() -> str:
    import datetime as _dt

    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def add_judgment(
    base_path: str | Path,
    *,
    run_id: str,
    text: str,
    node_id: str | None = None,
    tags: list[str] | None = None,
    author: str = "anonymous",
) -> dict[str, Any]:
    """Persist a user's natural-language judgment of a run or node.

    Returns the stored dict (useful for response composition).
    """
    initialize_runs_db(base_path)
    judgment_id = uuid.uuid4().hex[:16]
    ts = _iso_now()
    with _connect(base_path) as conn:
        conn.execute(
            """
            INSERT INTO run_judgments (
                judgment_id, run_id, node_id, text,
                tags_json, author, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                judgment_id, run_id, node_id, text,
                json.dumps(list(tags or []), default=str),
                author, ts,
            ),
        )
    return {
        "judgment_id": judgment_id,
        "run_id": run_id,
        "node_id": node_id,
        "text": text,
        "tags": list(tags or []),
        "author": author,
        "timestamp": ts,
    }


def list_judgments(
    base_path: str | Path,
    *,
    branch_def_id: str = "",
    run_id: str = "",
    node_id: str = "",
    limit: int = 30,
) -> list[dict[str, Any]]:
    """Return judgments filtered by branch / run / node. At least one
    filter must be set to avoid accidental full-table scans — callers
    that want everything should pass a branch_def_id."""
    initialize_runs_db(base_path)
    if not (branch_def_id or run_id or node_id):
        return []

    clauses: list[str] = []
    params: list[Any] = []
    if run_id:
        clauses.append("j.run_id = ?")
        params.append(run_id)
    if node_id:
        clauses.append("j.node_id = ?")
        params.append(node_id)
    if branch_def_id:
        # Join through runs to scope by branch.
        clauses.append(
            "j.run_id IN (SELECT run_id FROM runs WHERE branch_def_id = ?)"
        )
        params.append(branch_def_id)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with _connect(base_path) as conn:
        rows = conn.execute(
            f"""
            SELECT j.judgment_id, j.run_id, j.node_id, j.text,
                   j.tags_json, j.author, j.timestamp
            FROM run_judgments j
            {where}
            ORDER BY j.timestamp DESC
            LIMIT ?
            """,
            (*params, max(1, int(limit))),
        ).fetchall()

    result: list[dict[str, Any]] = []
    for r in rows:
        try:
            tags = json.loads(r["tags_json"] or "[]")
        except json.JSONDecodeError:
            tags = []
        result.append({
            "judgment_id": r["judgment_id"],
            "run_id": r["run_id"],
            "node_id": r["node_id"],
            "text": r["text"],
            "tags": tags,
            "author": r["author"],
            "timestamp": r["timestamp"],
        })
    return result


def record_lineage(
    base_path: str | Path,
    *,
    run_id: str,
    parent_run_id: str | None,
    branch_def_id: str,
    branch_version: int,
    edits_since_parent: list[str] | None = None,
) -> None:
    """Store a lineage row at run start. ``parent_run_id`` is resolved by
    the caller (usually: most recent terminal run on the same branch by
    the same actor)."""
    initialize_runs_db(base_path)
    with _connect(base_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO run_lineage (
                run_id, parent_run_id, branch_def_id, branch_version,
                edits_since_parent_json, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run_id, parent_run_id, branch_def_id, int(branch_version),
                json.dumps(list(edits_since_parent or []), default=str),
                _iso_now(),
            ),
        )


def get_lineage(base_path: str | Path, run_id: str) -> dict[str, Any] | None:
    initialize_runs_db(base_path)
    with _connect(base_path) as conn:
        row = conn.execute(
            "SELECT * FROM run_lineage WHERE run_id = ?", (run_id,),
        ).fetchone()
    if row is None:
        return None
    try:
        edits = json.loads(row["edits_since_parent_json"] or "[]")
    except json.JSONDecodeError:
        edits = []
    return {
        "run_id": row["run_id"],
        "parent_run_id": row["parent_run_id"],
        "branch_def_id": row["branch_def_id"],
        "branch_version": row["branch_version"],
        "edits_since_parent": edits,
        "timestamp": row["timestamp"],
    }


def latest_terminal_run(
    base_path: str | Path,
    *,
    branch_def_id: str,
    actor: str = "",
) -> str | None:
    """Find the most recent terminal run on this branch (optionally by
    actor) to use as ``parent_run_id`` for a new run."""
    initialize_runs_db(base_path)
    clauses = [
        "branch_def_id = ?",
        "status IN (?, ?, ?, ?)",
    ]
    params: list[Any] = [
        branch_def_id,
        RUN_STATUS_COMPLETED, RUN_STATUS_FAILED,
        RUN_STATUS_CANCELLED, RUN_STATUS_INTERRUPTED,
    ]
    if actor:
        clauses.append("actor = ?")
        params.append(actor)
    where = " AND ".join(clauses)
    with _connect(base_path) as conn:
        row = conn.execute(
            f"""
            SELECT run_id FROM runs
            WHERE {where}
            ORDER BY started_at DESC LIMIT 1
            """,
            params,
        ).fetchone()
    return row["run_id"] if row else None


def record_node_edit_audit(
    base_path: str | Path,
    *,
    branch_def_id: str,
    version_before: int,
    version_after: int,
    nodes_changed: list[str],
    triggered_by_judgment_id: str | None = None,
    node_before: dict[str, Any] | None = None,
    node_after: dict[str, Any] | None = None,
    edit_kind: str = "update",
) -> str:
    """Persist a NodeEditAudit row when a branch is edited.

    ``node_before`` / ``node_after`` are full serialized NodeDefinition
    dicts. Snapshotting the bodies means rollback can restore the exact
    previous state without re-synthesising it. ``edit_kind`` is either
    ``"update"`` (normal edit via update_node) or ``"rollback"`` (edit
    via rollback_node) so clients can distinguish forward-progress edits
    from rewinds. Returns the audit_id.
    """
    initialize_runs_db(base_path)
    audit_id = uuid.uuid4().hex[:16]
    with _connect(base_path) as conn:
        conn.execute(
            """
            INSERT INTO node_edit_audit (
                audit_id, branch_def_id, version_before, version_after,
                nodes_changed_json, triggered_by_judgment_id, timestamp,
                node_before_json, node_after_json, edit_kind
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                audit_id, branch_def_id,
                int(version_before), int(version_after),
                json.dumps(list(nodes_changed), default=str),
                triggered_by_judgment_id, _iso_now(),
                json.dumps(node_before or {}, default=str),
                json.dumps(node_after or {}, default=str),
                edit_kind,
            ),
        )
    return audit_id


def _audit_row_to_dict(r: sqlite3.Row) -> dict[str, Any]:
    try:
        changed = json.loads(r["nodes_changed_json"] or "[]")
    except json.JSONDecodeError:
        changed = []
    try:
        before = json.loads(r["node_before_json"] or "{}")
    except json.JSONDecodeError:
        before = {}
    try:
        after = json.loads(r["node_after_json"] or "{}")
    except json.JSONDecodeError:
        after = {}
    return {
        "audit_id": r["audit_id"],
        "branch_def_id": r["branch_def_id"],
        "version_before": r["version_before"],
        "version_after": r["version_after"],
        "nodes_changed": changed,
        "triggered_by_judgment_id": r["triggered_by_judgment_id"],
        "timestamp": r["timestamp"],
        "node_before": before,
        "node_after": after,
        "edit_kind": (
            r["edit_kind"] if "edit_kind" in r.keys() else "update"
        ),
    }


def list_node_edit_audits(
    base_path: str | Path,
    *,
    branch_def_id: str,
    node_id: str = "",
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return audit rows for a branch, optionally narrowed to a single
    node. Rows are sorted newest-first. The ``node_id`` filter uses JSON
    containment against ``nodes_changed_json`` (``update_node`` writes
    single-element lists, so equality is the common case)."""
    initialize_runs_db(base_path)
    clauses: list[str] = ["branch_def_id = ?"]
    params: list[Any] = [branch_def_id]
    if node_id:
        # nodes_changed_json stores a JSON list. Exact-match tests for
        # a single-element list as well as containment for multi-node
        # edits (future when patch_branch learns to emit audits).
        clauses.append(
            "(nodes_changed_json = ? OR nodes_changed_json LIKE ?)"
        )
        params.append(json.dumps([node_id]))
        params.append(f'%"{node_id}"%')
    where = " AND ".join(clauses)
    with _connect(base_path) as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM node_edit_audit
            WHERE {where}
            ORDER BY timestamp DESC LIMIT ?
            """,
            (*params, max(1, int(limit))),
        ).fetchall()
    return [_audit_row_to_dict(r) for r in rows]


def find_node_snapshot(
    base_path: str | Path,
    *,
    branch_def_id: str,
    node_id: str,
    at_version: int,
) -> dict[str, Any] | None:
    """Locate the node body as it existed at a specific branch version.

    Strategy: the audit row whose ``version_after`` equals ``at_version``
    captures the node's ``node_after`` — that's the body at that version.
    When no row matches (e.g. the target is version 1, never edited), we
    fall back to the oldest audit row's ``node_before``.
    """
    initialize_runs_db(base_path)
    with _connect(base_path) as conn:
        exact = conn.execute(
            """
            SELECT * FROM node_edit_audit
            WHERE branch_def_id = ?
              AND version_after = ?
              AND (nodes_changed_json = ? OR nodes_changed_json LIKE ?)
            ORDER BY timestamp DESC LIMIT 1
            """,
            (
                branch_def_id, int(at_version),
                json.dumps([node_id]), f'%"{node_id}"%',
            ),
        ).fetchone()
        if exact is not None:
            return _audit_row_to_dict(exact).get("node_after") or None

        oldest = conn.execute(
            """
            SELECT * FROM node_edit_audit
            WHERE branch_def_id = ?
              AND version_before = ?
              AND (nodes_changed_json = ? OR nodes_changed_json LIKE ?)
            ORDER BY timestamp ASC LIMIT 1
            """,
            (
                branch_def_id, int(at_version),
                json.dumps([node_id]), f'%"{node_id}"%',
            ),
        ).fetchone()
        if oldest is not None:
            return _audit_row_to_dict(oldest).get("node_before") or None
    return None


def node_output_from_run(
    base_path: str | Path,
    *,
    run_id: str,
    node_id: str,
) -> dict[str, Any] | None:
    """Return the output snapshot event for a specific (run_id, node_id).

    Phase 4 judgments target specific nodes, so users need the per-node
    output to judge on, not just final state.
    """
    initialize_runs_db(base_path)
    with _connect(base_path) as conn:
        row = conn.execute(
            """
            SELECT * FROM run_events
            WHERE run_id = ? AND node_id = ? AND status = ?
            ORDER BY step_index DESC LIMIT 1
            """,
            (run_id, node_id, NODE_STATUS_RAN),
        ).fetchone()
    if row is None:
        return None
    detail_raw = row["detail_json"] or "{}"
    try:
        detail = json.loads(detail_raw)
    except json.JSONDecodeError:
        detail = {}
    return {
        "run_id": run_id,
        "node_id": node_id,
        "step_index": row["step_index"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "detail": detail,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Cooperative cancel
# ─────────────────────────────────────────────────────────────────────────────


def request_cancel(base_path: str | Path, run_id: str) -> bool:
    initialize_runs_db(base_path)
    with _connect(base_path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO run_cancels (run_id, requested_at) "
            "VALUES (?, ?)",
            (run_id, _now()),
        )
    return True


def is_cancel_requested(base_path: str | Path, run_id: str) -> bool:
    with _connect(base_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM run_cancels WHERE run_id = ?", (run_id,)
        ).fetchone()
    return row is not None


# ─────────────────────────────────────────────────────────────────────────────
# Synchronous runner
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class RunOutcome:
    run_id: str
    status: str
    output: dict[str, Any]
    error: str = ""


def _graph_node_order(branch: BranchDefinition) -> list[str]:
    return [gn.id for gn in branch.graph_nodes]


def _prepare_run(
    base_path: str | Path,
    *,
    branch: BranchDefinition,
    inputs: dict[str, Any],
    run_name: str,
    actor: str,
) -> str:
    """Write the run row + pending-node events + lineage synchronously.

    Returns the ``run_id``. Fast (~a few ms); safe to call from the MCP
    handler before handing off to a background executor.
    """
    initialize_runs_db(base_path)
    run_id = create_run(
        base_path,
        branch_def_id=branch.branch_def_id,
        thread_id="",
        inputs=inputs,
        run_name=run_name,
        actor=actor,
    )
    thread_id = run_id
    with _connect(base_path) as conn:
        conn.execute(
            "UPDATE runs SET thread_id = ? WHERE run_id = ?",
            (thread_id, run_id),
        )
    for step, node_id in enumerate(_graph_node_order(branch)):
        record_event(base_path, RunStepEvent(
            run_id=run_id,
            step_index=step,
            node_id=node_id,
            status=NODE_STATUS_PENDING,
            started_at=_now(),
        ))

    # Phase 4: record lineage so `compare_runs` and "what changed since
    # the last run" work. Parent is the most recent terminal run on this
    # branch by the same actor (best-effort — falls back to branch-wide
    # latest if no same-actor match).
    parent = latest_terminal_run(
        base_path, branch_def_id=branch.branch_def_id, actor=actor,
    )
    if parent is None:
        parent = latest_terminal_run(
            base_path, branch_def_id=branch.branch_def_id,
        )
    branch_version = int(getattr(branch, "version", 1) or 1)
    edits_since_parent: list[str] = []
    if parent is not None:
        parent_lineage = get_lineage(base_path, parent)
        if parent_lineage and parent_lineage["branch_version"] != branch_version:
            # Best-effort: enumerate audit rows between the versions for
            # a summary of what changed between runs.
            try:
                audits = list_node_edit_audits(
                    base_path, branch_def_id=branch.branch_def_id, limit=100,
                )
                for a in audits:
                    if (
                        a["version_before"] >= parent_lineage["branch_version"]
                        and a["version_after"] <= branch_version
                    ):
                        edits_since_parent.extend(a.get("nodes_changed", []))
            except Exception:
                logger.exception("lineage edit summary failed for %s", run_id)
    record_lineage(
        base_path,
        run_id=run_id,
        parent_run_id=parent,
        branch_def_id=branch.branch_def_id,
        branch_version=branch_version,
        edits_since_parent=edits_since_parent,
    )
    return run_id


def _invoke_graph(
    base_path: str | Path,
    *,
    run_id: str,
    branch: BranchDefinition,
    inputs: dict[str, Any],
    provider_call: Callable[..., str] | None,
) -> RunOutcome:
    """Compile + invoke the graph for an already-prepared run_id.

    Blocks until the graph finishes or is cancelled. Updates run status
    to RUNNING on entry, COMPLETED / FAILED / CANCELLED on exit.
    """
    thread_id = run_id
    execution_cursor = {"step": 0}

    def _on_node(node_id: str, **detail: Any) -> None:
        # #60: the compiler emits TWO events per node — phase="starting"
        # before the provider call and phase="ran" after. Each event gets
        # its own step_index so polling clients see node status transition
        # pending -> running -> ran, no more "frozen for 4 minutes" gaps.
        #
        # Cooperative cancel fires only on "ran" (between nodes).
        # Cancelling mid-provider-call would orphan the LLM call; the
        # node boundary is the right checkpoint.
        phase = detail.pop("phase", "ran")
        step = execution_cursor["step"]
        execution_cursor["step"] += 1

        if phase == "starting":
            record_event(base_path, RunStepEvent(
                run_id=run_id,
                step_index=step + _PENDING_OFFSET,
                node_id=node_id,
                status=NODE_STATUS_RUNNING,
                started_at=_now(),
                detail=detail,
            ))
            return

        if is_cancel_requested(base_path, run_id):
            raise RunCancelledError(f"Run {run_id} cancelled between nodes.")
        record_event(base_path, RunStepEvent(
            run_id=run_id,
            step_index=step + _PENDING_OFFSET,
            node_id=node_id,
            status=NODE_STATUS_RAN,
            started_at=_now(),
            finished_at=_now(),
            detail=detail,
        ))

    try:
        compiled = compile_branch(
            branch,
            provider_call=provider_call,
            event_sink=_on_node,
        )
    except (UnapprovedNodeError, CompilerError) as exc:
        update_run_status(
            base_path, run_id,
            status=RUN_STATUS_FAILED,
            error=str(exc),
            finished_at=_now(),
        )
        return RunOutcome(
            run_id=run_id, status=RUN_STATUS_FAILED,
            output={}, error=str(exc),
        )

    update_run_status(base_path, run_id, status=RUN_STATUS_RUNNING)

    if is_cancel_requested(base_path, run_id):
        update_run_status(
            base_path, run_id,
            status=RUN_STATUS_CANCELLED,
            error="Cancelled before execution started.",
            finished_at=_now(),
        )
        return RunOutcome(
            run_id=run_id, status=RUN_STATUS_CANCELLED,
            output={}, error="Cancelled before execution started.",
        )

    try:
        from langgraph.checkpoint.sqlite import SqliteSaver

        saver_path = str(Path(base_path) / ".langgraph_runs.db")
        Path(saver_path).parent.mkdir(parents=True, exist_ok=True)
        with SqliteSaver.from_conn_string(saver_path) as checkpointer:
            app = compiled.graph.compile(checkpointer=checkpointer)
            result = app.invoke(
                dict(inputs),
                config={"configurable": {"thread_id": thread_id}},
            )
    except RunCancelledError as exc:
        update_run_status(
            base_path, run_id,
            status=RUN_STATUS_CANCELLED,
            error=str(exc),
            finished_at=_now(),
        )
        return RunOutcome(
            run_id=run_id, status=RUN_STATUS_CANCELLED,
            output={}, error=str(exc),
        )
    except Exception as exc:
        # LangGraph may wrap RunCancelledError in its own exception.
        # Unwrap and handle uniformly.
        if _is_cancel_exception(exc):
            msg = f"Run {run_id} cancelled between nodes."
            update_run_status(
                base_path, run_id,
                status=RUN_STATUS_CANCELLED,
                error=msg,
                finished_at=_now(),
            )
            return RunOutcome(
                run_id=run_id, status=RUN_STATUS_CANCELLED,
                output={}, error=msg,
            )
        # #61: surface node timeouts with a distinct reason so the user
        # can tell "your evidence-intake node hit the 300s cap" from a
        # generic crash. The NodeTimeoutError message carries the
        # node_id and timeout value.
        timeout_exc = _find_timeout_exception(exc)
        if timeout_exc is not None:
            msg = f"Node timeout: {timeout_exc}"
            step = execution_cursor["step"]
            execution_cursor["step"] += 1
            record_event(base_path, RunStepEvent(
                run_id=run_id,
                step_index=step + _PENDING_OFFSET,
                node_id=_node_id_from_timeout_exc(timeout_exc),
                status=NODE_STATUS_FAILED,
                started_at=_now(),
                finished_at=_now(),
                detail={"reason": "timeout", "message": str(timeout_exc)},
            ))
            update_run_status(
                base_path, run_id,
                status=RUN_STATUS_FAILED,
                error=msg,
                finished_at=_now(),
            )
            return RunOutcome(
                run_id=run_id, status=RUN_STATUS_FAILED,
                output={}, error=msg,
            )
        logger.exception("Run %s failed at invoke", run_id)
        update_run_status(
            base_path, run_id,
            status=RUN_STATUS_FAILED,
            error=f"{type(exc).__name__}: {exc}",
            finished_at=_now(),
        )
        return RunOutcome(
            run_id=run_id, status=RUN_STATUS_FAILED,
            output={}, error=f"{type(exc).__name__}: {exc}",
        )

    output = dict(result) if isinstance(result, dict) else {"result": result}
    update_run_status(
        base_path, run_id,
        status=RUN_STATUS_COMPLETED,
        output=output,
        finished_at=_now(),
    )
    return RunOutcome(
        run_id=run_id, status=RUN_STATUS_COMPLETED,
        output=output, error="",
    )


def _is_cancel_exception(exc: BaseException) -> bool:
    """Detect a wrapped RunCancelledError in a chain."""
    seen: set[int] = set()
    cur: BaseException | None = exc
    while cur is not None and id(cur) not in seen:
        if isinstance(cur, RunCancelledError):
            return True
        seen.add(id(cur))
        cur = cur.__cause__ or cur.__context__
    return False


def _find_timeout_exception(exc: BaseException) -> NodeTimeoutError | None:
    """Walk the exception chain for a NodeTimeoutError (#61).

    LangGraph wraps node errors in its own exception types; the
    underlying timeout sits on ``__cause__`` / ``__context__``.
    """
    seen: set[int] = set()
    cur: BaseException | None = exc
    while cur is not None and id(cur) not in seen:
        if isinstance(cur, NodeTimeoutError):
            return cur
        seen.add(id(cur))
        cur = cur.__cause__ or cur.__context__
    return None


_TIMEOUT_NODE_RE = re.compile(r"Node '([^']+)'")


def _node_id_from_timeout_exc(exc: NodeTimeoutError) -> str:
    """Return the node_id for a NodeTimeoutError.

    Prefers the ``node_id`` attribute set by the raiser (stable contract).
    Falls back to parsing the human-readable message for older callers
    that constructed the exception without the keyword — keeps backward
    compatibility with test fixtures and third-party code.
    """
    node_id = getattr(exc, "node_id", "") or ""
    if node_id:
        return node_id
    return _node_id_from_timeout_message(str(exc))


def _node_id_from_timeout_message(message: str) -> str:
    """Extract the node_id from a NodeTimeoutError message (legacy fallback).

    Fallback to ``"(timeout)"`` when the message doesn't match. The
    node_id drives which row in the run_events timeline surfaces the
    failure. Prefer :func:`_node_id_from_timeout_exc` when the exception
    object is in hand.
    """
    m = _TIMEOUT_NODE_RE.search(message)
    return m.group(1) if m else "(timeout)"


def execute_branch(
    base_path: str | Path,
    *,
    branch: BranchDefinition,
    inputs: dict[str, Any],
    run_name: str = "",
    actor: str = "anonymous",
    provider_call: Callable[..., str] | None = None,
) -> RunOutcome:
    """Synchronous end-to-end execution.

    Kept for callers that want the blocking contract (tests, scripts).
    The MCP handler uses :func:`execute_branch_async` instead.

    Raises nothing: validation/runtime errors are reported via
    ``RunOutcome.status``.
    """
    run_id = _prepare_run(
        base_path,
        branch=branch, inputs=inputs,
        run_name=run_name, actor=actor,
    )
    return _invoke_graph(
        base_path,
        run_id=run_id, branch=branch, inputs=inputs,
        provider_call=provider_call,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Async executor pool — in-process background worker for graph runs
# ─────────────────────────────────────────────────────────────────────────────
# Phase 3.5: the MCP tool returns a `run_id` in <1s. The graph runs in a
# background thread. `cancel_run` flips the flag, the next inter-node
# `event_sink` check unwinds the graph. Restart recovery marks in-flight
# runs as `interrupted` so clients see a clean terminal state and can
# choose to rerun.

_DEFAULT_MAX_WORKERS = 4
_executor_lock = threading.Lock()
_executor: ThreadPoolExecutor | None = None
_futures: dict[str, Future] = {}
_futures_lock = threading.Lock()


def _max_workers() -> int:
    raw = os.environ.get("WORKFLOW_RUN_MAX_CONCURRENT", "")
    try:
        val = int(raw) if raw else _DEFAULT_MAX_WORKERS
    except ValueError:
        val = _DEFAULT_MAX_WORKERS
    return max(1, val)


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(
                max_workers=_max_workers(),
                thread_name_prefix="workflow-run",
            )
    return _executor


def shutdown_executor(wait: bool = True) -> None:
    """Shut down the shared executor. Used by tests and graceful shutdown."""
    global _executor
    with _executor_lock:
        if _executor is not None:
            _executor.shutdown(wait=wait)
            _executor = None
    with _futures_lock:
        _futures.clear()


def _track_future(run_id: str, future: Future) -> None:
    with _futures_lock:
        _futures[run_id] = future

    def _on_done(_fut: Future) -> None:
        with _futures_lock:
            _futures.pop(run_id, None)

    future.add_done_callback(_on_done)


def get_future(run_id: str) -> Future | None:
    """Return the in-flight Future for a run, if any. Mostly used by tests."""
    with _futures_lock:
        return _futures.get(run_id)


def wait_for(run_id: str, timeout: float | None = None) -> None:
    """Block until the background worker for a run finishes. Test helper."""
    fut = get_future(run_id)
    if fut is not None:
        fut.result(timeout=timeout)


def execute_branch_async(
    base_path: str | Path,
    *,
    branch: BranchDefinition,
    inputs: dict[str, Any],
    run_name: str = "",
    actor: str = "anonymous",
    provider_call: Callable[..., str] | None = None,
) -> RunOutcome:
    """Prepare a run synchronously and kick off graph execution in the
    background. Returns within a few ms with ``status=queued``.

    The status will transition to ``running`` once the worker picks up
    the job, then to ``completed`` / ``failed`` / ``cancelled``. Clients
    poll ``get_run`` or ``stream_run`` for updates.
    """
    run_id = _prepare_run(
        base_path,
        branch=branch, inputs=inputs,
        run_name=run_name, actor=actor,
    )

    executor = _get_executor()

    def _worker() -> RunOutcome:
        try:
            return _invoke_graph(
                base_path,
                run_id=run_id, branch=branch, inputs=inputs,
                provider_call=provider_call,
            )
        except Exception:
            # Belt-and-suspenders: _invoke_graph already catches and
            # writes status, but if something escapes we still don't
            # want the executor to swallow it silently.
            logger.exception("Background worker for run %s crashed", run_id)
            update_run_status(
                base_path, run_id,
                status=RUN_STATUS_FAILED,
                error="Background worker crashed; see server logs.",
                finished_at=_now(),
            )
            return RunOutcome(
                run_id=run_id, status=RUN_STATUS_FAILED,
                output={}, error="Background worker crashed.",
            )

    future = executor.submit(_worker)
    _track_future(run_id, future)

    return RunOutcome(
        run_id=run_id, status=RUN_STATUS_QUEUED,
        output={}, error="",
    )


def recover_in_flight_runs(base_path: str | Path) -> int:
    """Mark any ``queued`` or ``running`` rows as ``interrupted``.

    Called at Workflow Server startup to clean up runs that were in
    flight when the server died. Returns the number of rows updated.

    A follow-up could resume these via SqliteSaver checkpoint + thread_id,
    but for v1 a clean terminal state is the product requirement — the
    user can see what happened and choose to rerun.
    """
    initialize_runs_db(base_path)
    now = _now()
    with _connect(base_path) as conn:
        cursor = conn.execute(
            """
            UPDATE runs
            SET status = ?, error = ?, finished_at = ?
            WHERE status IN (?, ?)
            """,
            (
                RUN_STATUS_INTERRUPTED,
                "Server restarted while this run was in flight.",
                now,
                RUN_STATUS_QUEUED, RUN_STATUS_RUNNING,
            ),
        )
        count = cursor.rowcount
    if count:
        logger.info("Recovered %d in-flight runs as 'interrupted'", count)
    return count


# Step indices higher than the count of pending events are reserved for
# the executed events, so the two event streams don't collide on
# (run_id, step_index) primary keys.
_PENDING_OFFSET = 1_000_000


# ─────────────────────────────────────────────────────────────────────────────
# Presentation helpers
# ─────────────────────────────────────────────────────────────────────────────


def build_node_status_map(
    events: list[dict[str, Any]],
    declared_order: list[str],
) -> list[dict[str, Any]]:
    """Fold the raw event stream into a per-node status list.

    Later events dominate earlier ones: a node seen as ``ran`` wins over
    its earlier ``pending`` row. This is the shape Claude.ai visualises
    to auto-build a state diagram.
    """
    statuses: dict[str, str] = {nid: NODE_STATUS_PENDING for nid in declared_order}
    for ev in events:
        node_id = ev.get("node_id", "")
        if not node_id:
            continue
        statuses.setdefault(node_id, NODE_STATUS_PENDING)
        current = statuses[node_id]
        incoming = ev.get("status", NODE_STATUS_PENDING)
        # ran/failed trump running which trumps pending
        priority = {
            NODE_STATUS_PENDING: 0,
            NODE_STATUS_RUNNING: 1,
            NODE_STATUS_RAN: 2,
            NODE_STATUS_FAILED: 2,
        }
        if priority.get(incoming, 0) >= priority.get(current, 0):
            statuses[node_id] = incoming
    # Preserve declared order, then append any out-of-order nodes.
    ordered_ids = list(declared_order)
    for nid in statuses:
        if nid not in ordered_ids:
            ordered_ids.append(nid)
    return [
        {"node_id": nid, "status": statuses[nid]}
        for nid in ordered_ids
    ]


__all__ = [
    "RUN_STATUS_QUEUED",
    "RUN_STATUS_RUNNING",
    "RUN_STATUS_COMPLETED",
    "RUN_STATUS_FAILED",
    "RUN_STATUS_CANCELLED",
    "RUN_STATUS_INTERRUPTED",
    "NODE_STATUS_PENDING",
    "NODE_STATUS_RUNNING",
    "NODE_STATUS_RAN",
    "NODE_STATUS_FAILED",
    "RunCancelledError",
    "RunOutcome",
    "RunStepEvent",
    # Phase 4 storage helpers
    "add_judgment",
    "build_node_status_map",
    "create_run",
    "execute_branch",
    "execute_branch_async",
    "find_node_snapshot",
    "get_future",
    "get_lineage",
    "get_run",
    "initialize_runs_db",
    "is_cancel_requested",
    "latest_terminal_run",
    "list_events",
    "list_judgments",
    "list_node_edit_audits",
    "list_runs",
    "node_output_from_run",
    "record_event",
    "record_lineage",
    "record_node_edit_audit",
    "recover_in_flight_runs",
    "request_cancel",
    "runs_db_path",
    "shutdown_executor",
    "update_run_status",
    "wait_for",
]
