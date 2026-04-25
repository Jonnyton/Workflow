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
    EmptyResponseError,
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
RUN_STATUS_RESUMED = "resumed"

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
        finished_at    REAL,
        provider_used  TEXT,
        model          TEXT,
        token_count    INTEGER
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

    CREATE TABLE IF NOT EXISTS teammate_messages (
        message_id     TEXT PRIMARY KEY,
        from_run_id    TEXT NOT NULL,
        to_node_id     TEXT NOT NULL,
        message_type   TEXT NOT NULL,
        body_json      TEXT NOT NULL DEFAULT '{}',
        reply_to_id    TEXT,
        sent_at        TEXT NOT NULL,
        acked          INTEGER NOT NULL DEFAULT 0
    );

    CREATE INDEX IF NOT EXISTS idx_tmsg_to_node
        ON teammate_messages(to_node_id, sent_at);
    CREATE INDEX IF NOT EXISTS idx_tmsg_from_run
        ON teammate_messages(from_run_id);
    """
    from workflow.branch_versions import BRANCH_VERSIONS_SCHEMA
    from workflow.contribution_events import CONTRIBUTION_EVENTS_SCHEMA
    from workflow.gate_events.schema import GATE_EVENT_SCHEMA
    from workflow.scheduler import SCHEDULER_SCHEMA
    schema = (
        schema
        + SCHEDULER_SCHEMA
        + BRANCH_VERSIONS_SCHEMA
        + GATE_EVENT_SCHEMA
        + CONTRIBUTION_EVENTS_SCHEMA
    )
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
        # Migration: add provider telemetry columns to runs (added 2026-04-25).
        existing_runs = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(runs)")
        }
        for col, ddl in (
            ("provider_used", "TEXT"),
            ("model",         "TEXT"),
            ("token_count",   "INTEGER"),
        ):
            if col not in existing_runs:
                conn.execute(f"ALTER TABLE runs ADD COLUMN {col} {ddl}")
        # Phase A item 6 (Task #65a) — branch_version_id on runs. NULL for
        # def-based runs (the existing path); populated only by
        # execute_branch_version_async for version-based runs. Required by
        # Task #48 contribution ledger + Task #53 route-back attribution.
        if "branch_version_id" not in existing_runs:
            conn.execute(
                "ALTER TABLE runs ADD COLUMN branch_version_id TEXT"
            )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_runs_branch_version "
            "ON runs(branch_version_id)"
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
    col_names = set(row.keys())
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
        "provider_used": row["provider_used"] if "provider_used" in col_names else None,
        "model": row["model"] if "model" in col_names else None,
        "token_count": row["token_count"] if "token_count" in col_names else None,
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
    branch_version_id: str | None = None,
) -> str:
    initialize_runs_db(base_path)
    run_id = uuid.uuid4().hex[:16]
    with _connect(base_path) as conn:
        conn.execute(
            """
            INSERT INTO runs (
                run_id, branch_def_id, run_name, thread_id,
                status, actor, inputs_json, started_at,
                branch_version_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id, branch_def_id, run_name, thread_id,
                RUN_STATUS_QUEUED, actor,
                json.dumps(inputs, default=str), _now(),
                branch_version_id,
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
    provider_used: str | None = None,
    model: str | None = None,
    token_count: int | None = None,
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
    if provider_used is not None:
        sets.append("provider_used = ?")
        params.append(provider_used)
    if model is not None:
        sets.append("model = ?")
        params.append(model)
    if token_count is not None:
        sets.append("token_count = ?")
        params.append(token_count)
    if not sets:
        return
    params.append(run_id)
    with _connect(base_path) as conn:
        conn.execute(
            f"UPDATE runs SET {', '.join(sets)} WHERE run_id = ?",
            params,
        )
        # Phase 2 emit-site (Task #72): on terminal status transition, emit
        # one execute_step contribution event for attribution. Wrapped in
        # try/except so emit failure (malformed metadata, table missing,
        # etc.) never blocks a status update — status is the load-bearing
        # semantic; emit is best-effort observability. Production observers
        # grep contribution_events._EMIT_FAILURES for non-zero.
        if status in _TERMINAL_STATUSES:
            try:
                row = conn.execute(
                    "SELECT actor, branch_def_id, branch_version_id "
                    "FROM runs WHERE run_id = ?", (run_id,),
                ).fetchone()
                if row is not None:
                    artifact_id = row["branch_version_id"] or row["branch_def_id"]
                    # Skip emit when no artifact identifier is present —
                    # no attribution path = no event (per design discipline).
                    if artifact_id:
                        from workflow.contribution_events import (
                            record_contribution_event,
                        )
                        artifact_kind = (
                            "branch_version" if row["branch_version_id"]
                            else "branch_def"
                        )
                        record_contribution_event(
                            base_path,
                            event_id=f"execute_step:{run_id}:{status}",
                            event_type="execute_step",
                            actor_id=row["actor"] or "anonymous",
                            source_run_id=run_id,
                            source_artifact_id=artifact_id,
                            source_artifact_kind=artifact_kind,
                            weight=1.0,
                            occurred_at=_now(),
                            metadata_json=json.dumps({
                                "branch_def_id": row["branch_def_id"],
                                "branch_version_id": row["branch_version_id"],
                                "terminal_status": status,
                            }),
                            conn=conn,
                        )
            except Exception as exc:
                from workflow.contribution_events import _EMIT_FAILURES
                from workflow.contribution_events import _logger as _ce_logger
                _EMIT_FAILURES["count"] += 1
                _ce_logger.warning(
                    "execute_step emit failed for run %s (status=%s): %s; "
                    "status update preserved",
                    run_id, status, exc,
                )


def get_run(base_path: str | Path, run_id: str) -> dict[str, Any] | None:
    initialize_runs_db(base_path)
    with _connect(base_path) as conn:
        row = conn.execute(
            "SELECT * FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if row is None:
            return None
        result = _row_to_run(row)
        # Surface concurrency stats from the last concurrency_stats system event.
        stats_row = conn.execute(
            """
            SELECT detail_json FROM run_events
            WHERE run_id = ? AND status = 'concurrency_stats'
            ORDER BY step_index DESC LIMIT 1
            """,
            (run_id,),
        ).fetchone()
    if stats_row:
        try:
            result["concurrency"] = json.loads(stats_row["detail_json"] or "{}")
        except json.JSONDecodeError:
            result["concurrency"] = None
    else:
        result["concurrency"] = None
    return result


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
    branch_version_id: str | None = None,
) -> str:
    """Write the run row + pending-node events + lineage synchronously.

    Returns the ``run_id``. Fast (~a few ms); safe to call from the MCP
    handler before handing off to a background executor.

    ``branch_version_id`` is populated only for version-based runs
    (Phase A item 6, Task #65). Def-based runs leave it as None.
    """
    initialize_runs_db(base_path)
    run_id = create_run(
        base_path,
        branch_def_id=branch.branch_def_id,
        thread_id="",
        inputs=inputs,
        run_name=run_name,
        actor=actor,
        branch_version_id=branch_version_id,
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


#: Default LangGraph recursion-limit ceiling, raised from LangGraph's
#: stock 25 → 100 per the Tier-1 investigation Step 6 (BUG-019/021/022).
#: Stock 25 is too tight for branches with 3+ gate iterations; BUG-020
#: runs tripped the limit. Callers can override via the explicit
#: `recursion_limit_override` arg on execute_branch / execute_branch_async.
DEFAULT_RECURSION_LIMIT = 100


def _invoke_graph(
    base_path: str | Path,
    *,
    run_id: str,
    branch: BranchDefinition,
    inputs: dict[str, Any],
    provider_call: Callable[..., str] | None,
    recursion_limit: int = DEFAULT_RECURSION_LIMIT,
    concurrency_budget_override: int | None = None,
) -> RunOutcome:
    """Compile + invoke the graph for an already-prepared run_id.

    Blocks until the graph finishes or is cancelled. Updates run status
    to RUNNING on entry, COMPLETED / FAILED / CANCELLED on exit.
    """
    thread_id = run_id
    execution_cursor = {"step": 0}
    provider_tracker: dict[str, str | None] = {"last": None}

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
        served = detail.get("provider_served")
        if served:
            provider_tracker["last"] = str(served)
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
            concurrency_budget_override=concurrency_budget_override,
            base_path=base_path,
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

    # Emit recursion_limit_applied event so get_run can surface the cap used.
    record_event(base_path, RunStepEvent(
        run_id=run_id,
        step_index=0,
        node_id="__system__",
        status="recursion_limit_applied",
        started_at=_now(),
        detail={"recursion_limit": recursion_limit},
    ))

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
                config={
                    "configurable": {"thread_id": thread_id},
                    "recursion_limit": recursion_limit,
                },
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
        # GraphRecursionError: structured error naming the applied limit.
        try:
            from langgraph.errors import GraphRecursionError as _GRE
            if isinstance(exc, _GRE):
                msg = (
                    f"GraphRecursionError: recursion limit {recursion_limit} reached. "
                    f"Raise via recursion_limit_override on run_branch. Detail: {exc}"
                )
                update_run_status(
                    base_path, run_id,
                    status=RUN_STATUS_FAILED, error=msg, finished_at=_now(),
                )
                return RunOutcome(
                    run_id=run_id, status=RUN_STATUS_FAILED, output={}, error=msg,
                )
        except ImportError:
            pass
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
        empty_exc = _find_empty_response_exception(exc)
        if empty_exc is not None:
            msg = f"Empty LLM response: {empty_exc}"
            step = execution_cursor["step"]
            execution_cursor["step"] += 1
            record_event(base_path, RunStepEvent(
                run_id=run_id,
                step_index=step + _PENDING_OFFSET,
                node_id=empty_exc.node_id or "(unknown)",
                status=NODE_STATUS_FAILED,
                started_at=_now(),
                finished_at=_now(),
                detail={"reason": "empty_response", "message": str(empty_exc)},
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

    # Emit concurrency_stats event so get_run can surface peak + budget.
    if compiled.concurrency_tracker is not None:
        stats = compiled.concurrency_tracker.stats()
        step = execution_cursor["step"]
        execution_cursor["step"] += 1
        record_event(base_path, RunStepEvent(
            run_id=run_id,
            step_index=step + _PENDING_OFFSET,
            node_id="__system__",
            status="concurrency_stats",
            started_at=_now(),
            detail=stats,
        ))

    update_run_status(
        base_path, run_id,
        status=RUN_STATUS_COMPLETED,
        output=output,
        finished_at=_now(),
        provider_used=provider_tracker["last"],
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


def _find_empty_response_exception(exc: BaseException) -> EmptyResponseError | None:
    """Walk the exception chain for an EmptyResponseError."""
    seen: set[int] = set()
    cur: BaseException | None = exc
    while cur is not None and id(cur) not in seen:
        if isinstance(cur, EmptyResponseError):
            return cur
        seen.add(id(cur))
        cur = cur.__cause__ or cur.__context__
    return None


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
    recursion_limit_override: int | None = None,
    concurrency_budget_override: int | None = None,
) -> RunOutcome:
    """Synchronous end-to-end execution.

    Kept for callers that want the blocking contract (tests, scripts).
    The MCP handler uses :func:`execute_branch_async` instead.

    Raises nothing: validation/runtime errors are reported via
    ``RunOutcome.status``.

    Parameters
    ----------
    recursion_limit_override
        Optional override for LangGraph's recursion limit. When ``None``
        (default), uses :data:`DEFAULT_RECURSION_LIMIT` (100). Branches
        with deep conditional loops (Tier-1 Step 6) bump this.
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
        recursion_limit=recursion_limit_override or DEFAULT_RECURSION_LIMIT,
        concurrency_budget_override=concurrency_budget_override,
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


def _execute_branch_core(
    base_path: str | Path,
    *,
    branch: BranchDefinition,
    inputs: dict[str, Any],
    run_name: str = "",
    actor: str = "anonymous",
    provider_call: Callable[..., str] | None = None,
    recursion_limit_override: int | None = None,
    concurrency_budget_override: int | None = None,
    branch_version_id: str | None = None,
) -> RunOutcome:
    """Shared async-execution core for def-based and version-based runs.

    Prepares the run row + pending-node events synchronously, then submits
    the graph invocation to the background executor. Returns within a few
    ms with ``status=queued``.

    ``branch_version_id`` is None for def-based runs (the public
    :func:`execute_branch_async`) and set for version-based runs (the
    Phase A item 6 :func:`execute_branch_version_async`).
    """
    run_id = _prepare_run(
        base_path,
        branch=branch, inputs=inputs,
        run_name=run_name, actor=actor,
        branch_version_id=branch_version_id,
    )

    executor = _get_executor()
    effective_limit = recursion_limit_override or DEFAULT_RECURSION_LIMIT

    def _worker() -> RunOutcome:
        try:
            return _invoke_graph(
                base_path,
                run_id=run_id, branch=branch, inputs=inputs,
                provider_call=provider_call,
                recursion_limit=effective_limit,
                concurrency_budget_override=concurrency_budget_override,
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


def execute_branch_async(
    base_path: str | Path,
    *,
    branch: BranchDefinition,
    inputs: dict[str, Any],
    run_name: str = "",
    actor: str = "anonymous",
    provider_call: Callable[..., str] | None = None,
    recursion_limit_override: int | None = None,
    concurrency_budget_override: int | None = None,
) -> RunOutcome:
    """Prepare a def-based run synchronously and kick off graph execution
    in the background. Returns within a few ms with ``status=queued``.

    The status will transition to ``running`` once the worker picks up
    the job, then to ``completed`` / ``failed`` / ``cancelled``. Clients
    poll ``get_run`` or ``stream_run`` for updates.

    Backed by :func:`_execute_branch_core` with ``branch_version_id=None``.
    Version-based runs use :func:`execute_branch_version_async` (Phase A
    item 6, Task #65) instead.

    Parameters
    ----------
    recursion_limit_override
        Optional override for LangGraph's recursion limit. See
        :func:`execute_branch` for rationale.
    concurrency_budget_override
        Override the branch-level concurrency_budget for this run.
    """
    return _execute_branch_core(
        base_path,
        branch=branch,
        inputs=inputs,
        run_name=run_name,
        actor=actor,
        provider_call=provider_call,
        recursion_limit_override=recursion_limit_override,
        concurrency_budget_override=concurrency_budget_override,
        branch_version_id=None,
    )


class SnapshotSchemaDrift(Exception):
    """Raised when a published version's snapshot can't be reconstructed.

    Phase A item 6 (Task #65). Wraps the failure of
    ``BranchDefinition.from_dict(snapshot)`` when the snapshot was
    published against an older branch schema and is missing a
    now-required field, has a now-removed field, or has a type-changed
    field. Carries class-level ``failure_class`` + ``suggested_action``
    so the MCP-layer handler can read them off the class without
    instantiating a defensive copy.
    """

    failure_class = "snapshot_schema_drift"
    suggested_action = "republish at current schema version"


def execute_branch_version_async(
    base_path: str | Path,
    *,
    branch_version_id: str,
    inputs: dict[str, Any],
    run_name: str = "",
    actor: str = "anonymous",
    provider_call: Callable[..., str] | None = None,
    recursion_limit_override: int | None = None,
) -> RunOutcome:
    """Execute a published branch_version snapshot (immutable).

    Sibling to :func:`execute_branch_async`; both wrap
    :func:`_execute_branch_core`. The version-based path loads the
    immutable snapshot from ``branch_versions``, reconstructs a
    ``BranchDefinition`` from it, and threads ``branch_version_id``
    through to the new ``runs.branch_version_id`` column for
    attribution (Task #48 / Task #53 dependencies).

    Cancellation propagation
    ------------------------
    Basic cancellation is identical to def-based runs — the run gets a
    ``run_id`` like any other; ``cancel_run(run_id)`` flips the flag in
    ``run_cancels`` and ``_invoke_graph``'s event_sink unwinds. **Parent
    gate-series cancellation does NOT propagate to child version-runs
    today.** Child runs are independent ``run_id``s; the propagation
    primitive lands when Task #53 route-back is implemented (a parent
    run that route-backs to a canonical via this helper will need
    cancellation forwarding then).

    Raises
    ------
    KeyError
        ``branch_version_id`` is not found in ``branch_versions``.
    SnapshotSchemaDrift
        The snapshot exists but cannot be reconstructed into a
        ``BranchDefinition`` because the on-disk shape predates a
        required field. The exception's ``failure_class`` and
        ``suggested_action`` class attributes name the recovery path
        ("republish at current schema version").
    """
    from workflow.branch_versions import get_branch_version

    bv = get_branch_version(base_path, branch_version_id=branch_version_id)
    if bv is None:
        raise KeyError(
            f"branch_version_id {branch_version_id!r} not found "
            "in branch_versions"
        )
    try:
        branch = BranchDefinition.from_dict(bv.snapshot)
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise SnapshotSchemaDrift(
            f"Snapshot for {branch_version_id!r} cannot be reconstructed: "
            f"{exc}. Republish at current schema version."
        ) from exc
    return _execute_branch_core(
        base_path,
        branch=branch,
        inputs=inputs,
        run_name=run_name,
        actor=actor,
        provider_call=provider_call,
        recursion_limit_override=recursion_limit_override,
        branch_version_id=branch_version_id,
    )


class ResumeError(Exception):
    """Raised when a resume_run call cannot proceed.

    Carries a structured ``reason`` code for programmatic handling:
    - ``not_interrupted``: run is not in INTERRUPTED status.
    - ``already_resumed``: run is already in RESUMED status (idempotent return).
    - ``not_found``: run_id does not exist.
    - ``auth_failed``: caller does not own the run.
    - ``no_checkpoint``: SqliteSaver has no checkpoint for this thread_id.
    - ``branch_version_mismatch``: branch was patched since the run was created.
    """

    def __init__(self, message: str, *, reason: str = "", current_status: str = "") -> None:
        super().__init__(message)
        self.reason = reason
        self.current_status = current_status


def _has_checkpoint(base_path: str | Path, thread_id: str) -> bool:
    """Return True if SqliteSaver has a checkpoint for thread_id."""
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
        saver_path = str(Path(base_path) / ".langgraph_runs.db")
        if not Path(saver_path).exists():
            return False
        with SqliteSaver.from_conn_string(saver_path) as cp:
            # LangGraph's list() yields checkpoint tuples; we just need to
            # know at least one exists.
            config = {"configurable": {"thread_id": thread_id}}
            items = list(cp.list(config))
            return bool(items)
    except Exception:
        return False


def resume_run(
    base_path: str | Path,
    *,
    run_id: str,
    actor: str,
    branch_lookup: Callable[[str, int], BranchDefinition | None],
    provider_call: Callable[..., str] | None = None,
) -> RunOutcome:
    """Resume an INTERRUPTED run from its SqliteSaver checkpoint.

    Parameters
    ----------
    run_id
        The run to resume.
    actor
        The caller's identity. Must match the run's ``actor`` field.
    branch_lookup
        Callable ``(branch_def_id, branch_version) -> BranchDefinition | None``.
        Used to re-compile the exact branch version used in the original run.
    provider_call
        Optional provider callable; same semantics as ``execute_branch``.

    Returns a ``RunOutcome`` with the resumed run's ID (same as input ``run_id``).

    Raises ``ResumeError`` on auth failure, wrong status, missing checkpoint,
    or branch version mismatch.
    """
    run = get_run(base_path, run_id)
    if run is None:
        raise ResumeError(
            f"Run '{run_id}' not found.", reason="not_found",
        )

    # Auth gate: caller must own the run.
    if run["actor"] != actor:
        raise ResumeError(
            f"Actor '{actor}' does not own run '{run_id}' "
            f"(owned by '{run['actor']}').",
            reason="auth_failed",
        )

    current_status = run["status"]

    # Idempotency: already resumed → return the same run_id, no second resume.
    if current_status == RUN_STATUS_RESUMED:
        return RunOutcome(
            run_id=run_id, status=RUN_STATUS_RESUMED,
            output=run.get("output", {}), error="",
        )

    # Status gate: only INTERRUPTED can be resumed.
    if current_status != RUN_STATUS_INTERRUPTED:
        raise ResumeError(
            f"Run '{run_id}' is '{current_status}', not 'interrupted'. "
            f"Only interrupted runs can be resumed.",
            reason="not_interrupted",
            current_status=current_status,
        )

    # Checkpoint gate.
    thread_id = run.get("thread_id") or run_id
    if not _has_checkpoint(base_path, thread_id):
        raise ResumeError(
            f"No SqliteSaver checkpoint found for run '{run_id}'. "
            "The run predates resume support or the checkpoint was evicted. "
            "Rerun from scratch with run_branch using the same inputs.",
            reason="no_checkpoint",
        )

    # Branch version gate: re-compile the exact version used in the original run.
    lineage = get_lineage(base_path, run_id)
    branch_version = int(
        (lineage or {}).get("branch_version") or getattr(branch_lookup, "_fallback_version", 1)
    )
    branch_def_id = run["branch_def_id"]
    branch = branch_lookup(branch_def_id, branch_version)
    if branch is None:
        raise ResumeError(
            f"Branch '{branch_def_id}' version {branch_version} no longer exists. "
            "Cannot resume — the branch was patched and that version was removed.",
            reason="branch_version_mismatch",
        )

    # Mark RESUMED immediately (before background work starts).
    update_run_status(base_path, run_id, status=RUN_STATUS_RESUMED)

    # Emit resume_started event.
    record_event(base_path, RunStepEvent(
        run_id=run_id,
        step_index=_PENDING_OFFSET,
        node_id="__resume__",
        status="resume_started",
        started_at=_now(),
        finished_at=_now(),
        detail={
            "resume_actor": actor,
            "resumed_at": _iso_now(),
        },
    ))

    # Background worker: re-invoke graph with None inputs to trigger resume.
    executor = _get_executor()

    def _resume_worker() -> RunOutcome:
        return _invoke_graph_resume(
            base_path,
            run_id=run_id,
            branch=branch,
            thread_id=thread_id,
            provider_call=provider_call,
        )

    future = executor.submit(_resume_worker)
    _track_future(run_id, future)

    return RunOutcome(
        run_id=run_id, status=RUN_STATUS_RESUMED,
        output={}, error="",
    )


def _invoke_graph_resume(
    base_path: str | Path,
    *,
    run_id: str,
    branch: BranchDefinition,
    thread_id: str,
    provider_call: Callable[..., str] | None,
) -> RunOutcome:
    """Compile branch + invoke with None inputs to resume from checkpoint."""
    execution_cursor = {"step": 1000}  # offset so resume events don't collide
    provider_tracker: dict[str, str | None] = {"last": None}

    def _on_node(node_id: str, **detail: Any) -> None:
        phase = detail.pop("phase", "ran")
        step = execution_cursor["step"]
        execution_cursor["step"] += 1
        if phase == "ran":
            served = detail.get("provider_served")
            if served:
                provider_tracker["last"] = served

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
            raise RunCancelledError(f"Run {run_id} cancelled during resume.")
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

    try:
        from langgraph.checkpoint.sqlite import SqliteSaver

        saver_path = str(Path(base_path) / ".langgraph_runs.db")
        with SqliteSaver.from_conn_string(saver_path) as checkpointer:
            app = compiled.graph.compile(checkpointer=checkpointer)
            # None inputs triggers resume from last checkpoint.
            result = app.invoke(
                None,
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
        if _is_cancel_exception(exc):
            msg = f"Run {run_id} cancelled during resume."
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
        msg = f"Resume execution failed: {exc}"
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

    output = dict(result) if isinstance(result, dict) else {}
    update_run_status(
        base_path, run_id,
        status=RUN_STATUS_COMPLETED,
        output=output,
        finished_at=_now(),
        provider_used=provider_tracker["last"],
    )
    return RunOutcome(
        run_id=run_id, status=RUN_STATUS_COMPLETED,
        output=output, error="",
    )


def recover_in_flight_runs(base_path: str | Path) -> int:
    """Mark any ``queued`` or ``running`` rows as ``interrupted``.

    Called at Workflow Server startup to clean up runs that were in
    flight when the server died. Returns the number of rows updated.

    v1 contract: ``interrupted`` is terminal. Callers rerun with the
    same ``inputs_json`` to continue; the MCP surface exposes this via
    ``get_run.resumable=false`` (see ``_compose_run_snapshot``). Mid-run
    resume via SqliteSaver checkpoint + thread_id is a future extension
    — not available today. Hard-rule #8 (fail loudly) is satisfied by
    the descriptive error field + terminal status; do not silently
    drop interrupted runs or loop a poll expecting them to re-run.
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


_VALID_STATUSES = frozenset({
    RUN_STATUS_QUEUED, RUN_STATUS_RUNNING, RUN_STATUS_COMPLETED,
    RUN_STATUS_FAILED, RUN_STATUS_CANCELLED, RUN_STATUS_INTERRUPTED,
})
_VALID_AGGREGATES = frozenset({"count", "mean", "sum", "rate"})
_MAX_QUERY_LIMIT = 1000
_DEFAULT_QUERY_LIMIT = 100


def query_runs(
    base_path: str | Path,
    *,
    branch_def_id: str = "",
    filters: dict[str, Any] | None = None,
    select: list[str] | None = None,
    aggregate: dict[str, Any] | None = None,
    limit: int = _DEFAULT_QUERY_LIMIT,
) -> dict[str, Any]:
    """Query runs table with optional field projection + simple aggregation.

    Spec: docs/vetted-specs.md §Cross-run state query primitive.

    Returns:
        {"rows": [...], "count": N} for plain queries.
        {"aggregated": [...], "count": N, "group_by": field, "agg_op": op}
        for aggregate queries.

    Invariants:
        - INTERRUPTED runs excluded from aggregation unless status filter
          explicitly includes them.
        - limit default 100, max 1000.
        - select fields extracted from output_json via JSON path.
        - aggregate.fn in {"count", "mean", "sum", "rate"}.
    """
    initialize_runs_db(base_path)
    filters = filters or {}
    select = select or []
    limit = min(max(1, limit), _MAX_QUERY_LIMIT)

    clauses: list[str] = []
    params: list[Any] = []

    if branch_def_id:
        clauses.append("branch_def_id = ?")
        params.append(branch_def_id)

    if "status" in filters:
        status_val = filters["status"]
        if isinstance(status_val, list):
            placeholders = ",".join("?" * len(status_val))
            clauses.append(f"status IN ({placeholders})")
            params.extend(status_val)
        else:
            clauses.append("status = ?")
            params.append(status_val)

    if "actor" in filters:
        clauses.append("actor = ?")
        params.append(filters["actor"])

    if "since" in filters:
        clauses.append("started_at >= ?")
        params.append(float(filters["since"]))

    if "until" in filters:
        clauses.append("started_at <= ?")
        params.append(float(filters["until"]))

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with _connect(base_path) as conn:
        rows = conn.execute(
            f"SELECT run_id, branch_def_id, status, actor, "
            f"started_at, finished_at, output_json "
            f"FROM runs {where} "
            f"ORDER BY started_at DESC LIMIT ?",
            [*params, limit],
        ).fetchall()

    def _extract_fields(output_str: str, fields: list[str]) -> dict[str, Any]:
        try:
            state = json.loads(output_str) if output_str else {}
        except (json.JSONDecodeError, TypeError):
            state = {}
        if not fields:
            return {}
        return {f: state.get(f) for f in fields}

    _RUN_COLUMNS = frozenset({
        "run_id", "branch_def_id", "status", "actor", "started_at", "finished_at",
    })

    def _row_value(r: Any, field: str) -> Any:
        if field in _RUN_COLUMNS:
            return r[field]
        try:
            state = json.loads(r["output_json"]) if r["output_json"] else {}
        except (json.JSONDecodeError, TypeError):
            state = {}
        return state.get(field)

    if aggregate:
        group_by = aggregate.get("group_by", "")
        agg_op = aggregate.get("fn", aggregate.get("op", "count"))
        agg_field = aggregate.get("field", "")

        groups: dict[Any, list[Any]] = {}
        for r in rows:
            gv = _row_value(r, group_by) if group_by else "_all"
            av = _row_value(r, agg_field) if agg_field else 1.0
            groups.setdefault(gv, []).append(av)

        def _agg(values: list[Any], op: str) -> Any:
            nums = [v for v in values if isinstance(v, (int, float))]
            if op == "count":
                return len(values)
            if op == "sum":
                return sum(nums) if nums else 0
            if op == "mean":
                return sum(nums) / len(nums) if nums else None
            if op == "rate":
                total = len(rows) if rows else 1
                return len(values) / total if total else None
            return len(values)

        aggregated = [
            {"group": gv, "value": _agg(vals, agg_op), "n": len(vals)}
            for gv, vals in sorted(groups.items(), key=lambda kv: str(kv[0]))
        ]
        return {
            "aggregated": aggregated,
            "count": len(aggregated),
            "group_by": group_by,
            "agg_op": agg_op,
        }

    result_rows = []
    for r in rows:
        row_dict: dict[str, Any] = {
            "run_id": r["run_id"],
            "branch_def_id": r["branch_def_id"],
            "status": r["status"],
            "actor": r["actor"],
            "started_at": r["started_at"],
            "finished_at": r["finished_at"],
        }
        if select:
            row_dict["fields"] = _extract_fields(r["output_json"], select)
        result_rows.append(row_dict)

    return {"rows": result_rows, "count": len(result_rows)}


# ─────────────────────────────────────────────────────────────────────────────
# Sub-branch invocation helpers
# ─────────────────────────────────────────────────────────────────────────────

#: Maximum nesting depth for invoke_branch nodes. A child run increments
#: the depth counter; reaching this cap raises CompilerError at runtime.
MAX_INVOKE_BRANCH_DEPTH = 5

_TERMINAL_STATUSES = frozenset({
    RUN_STATUS_COMPLETED,
    RUN_STATUS_FAILED,
    RUN_STATUS_CANCELLED,
    RUN_STATUS_INTERRUPTED,
})


def poll_child_run_status(
    base_path: str | Path,
    run_id: str,
    *,
    timeout_seconds: float = 300.0,
    poll_interval: float = 1.0,
) -> dict[str, Any]:
    """Block until *run_id* reaches a terminal status or *timeout_seconds* elapses.

    Returns the run record dict (same shape as ``get_run``).
    Raises ``TimeoutError`` if the run does not terminate in time.
    Raises ``KeyError`` if the run does not exist at poll time.
    """
    deadline = time.monotonic() + timeout_seconds
    while True:
        record = get_run(base_path, run_id)
        if record is None:
            raise KeyError(f"Child run '{run_id}' not found in runs DB.")
        if record.get("status") in _TERMINAL_STATUSES:
            return record
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(
                f"await_branch_run: child run '{run_id}' did not complete "
                f"within {timeout_seconds}s."
            )
        time.sleep(min(poll_interval, remaining))


# ─── Teammate messaging ───────────────────────────────────────────────────────

_VALID_MESSAGE_TYPES = frozenset({
    "request", "response", "broadcast",
    "plan_approval_request", "plan_approval_response",
    "shutdown_request", "shutdown_response",
})


def post_teammate_message(
    base_path: str | Path,
    *,
    from_run_id: str,
    to_node_id: str,
    message_type: str,
    body: dict[str, Any],
    reply_to_id: str | None = None,
) -> dict[str, Any]:
    """Insert a teammate message. Returns the stored message record."""
    import uuid
    from datetime import datetime, timezone

    if not from_run_id:
        raise ValueError("from_run_id is required.")
    if not to_node_id:
        raise ValueError("to_node_id is required.")
    if message_type not in _VALID_MESSAGE_TYPES:
        raise ValueError(
            f"Unknown message_type {message_type!r}; "
            f"valid: {sorted(_VALID_MESSAGE_TYPES)}"
        )
    try:
        body_json = json.dumps(body)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"body must be JSON-serializable: {exc}") from exc

    run_record = get_run(base_path, from_run_id)
    if run_record is None:
        raise KeyError(f"from_run_id '{from_run_id}' not found in runs DB.")

    message_id = str(uuid.uuid4())
    sent_at = datetime.now(timezone.utc).isoformat()

    initialize_runs_db(base_path)
    with _connect(base_path) as conn:
        conn.execute(
            """
            INSERT INTO teammate_messages
                (message_id, from_run_id, to_node_id, message_type,
                 body_json, reply_to_id, sent_at, acked)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (message_id, from_run_id, to_node_id, message_type,
             body_json, reply_to_id, sent_at),
        )
    return {
        "message_id": message_id,
        "from_run_id": from_run_id,
        "to_node_id": to_node_id,
        "message_type": message_type,
        "body": body,
        "reply_to_id": reply_to_id,
        "sent_at": sent_at,
        "acked": False,
    }


def read_teammate_messages(
    base_path: str | Path,
    *,
    node_id: str = "",
    since: str | None = None,
    message_types: list[str] | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return messages for node_id (or all if node_id is empty/broadcast)."""
    initialize_runs_db(base_path)
    clauses: list[str] = []
    params: list[Any] = []

    if node_id:
        clauses.append("(to_node_id = ? OR to_node_id = '*')")
        params.append(node_id)
    if since:
        clauses.append("sent_at >= ?")
        params.append(since)
    if message_types:
        placeholders = ",".join("?" * len(message_types))
        clauses.append(f"message_type IN ({placeholders})")
        params.extend(message_types)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    limit = min(max(1, limit), 1000)

    with _connect(base_path) as conn:
        rows = conn.execute(
            f"SELECT * FROM teammate_messages {where} "
            f"ORDER BY sent_at ASC LIMIT ?",
            [*params, limit],
        ).fetchall()

    results = []
    for r in rows:
        try:
            body = json.loads(r["body_json"])
        except (json.JSONDecodeError, TypeError):
            body = {}
        results.append({
            "message_id": r["message_id"],
            "from_run_id": r["from_run_id"],
            "to_node_id": r["to_node_id"],
            "message_type": r["message_type"],
            "body": body,
            "reply_to_id": r["reply_to_id"],
            "sent_at": r["sent_at"],
            "acked": bool(r["acked"]),
        })
    return results


def ack_teammate_message(
    base_path: str | Path,
    *,
    message_id: str,
    node_id: str,
) -> dict[str, Any]:
    """Mark message as acked. Idempotent. Returns acked_at timestamp."""
    from datetime import datetime, timezone

    initialize_runs_db(base_path)
    with _connect(base_path) as conn:
        row = conn.execute(
            "SELECT * FROM teammate_messages WHERE message_id = ?",
            (message_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"message_id '{message_id}' not found.")
        if row["to_node_id"] != node_id and row["to_node_id"] != "*":
            raise PermissionError(
                f"node_id '{node_id}' cannot ack message addressed to "
                f"'{row['to_node_id']}'."
            )
        acked_at = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE teammate_messages SET acked = 1 WHERE message_id = ?",
            (message_id,),
        )
    return {"message_id": message_id, "acked_at": acked_at}


_ROUTING_EVIDENCE_CAVEAT = (
    "provider_used is populated for runs that used the policy router; "
    "token_count and model are not yet collected (no LLM billing hooks). "
    "latency_ms is derived from started_at / finished_at timestamps."
)

_ROUTING_EVIDENCE_LIMIT_CAP = 50
_ROUTING_EVIDENCE_DEFAULT_LIMIT = 10


def _classify_failure(run: dict) -> str:
    """Return a short failure class string from a run record."""
    error = run.get("error") or ""
    status = run.get("status", "")
    if status == RUN_STATUS_CANCELLED:
        return "cancelled"
    if status == RUN_STATUS_INTERRUPTED:
        return "interrupted"
    if not error:
        return ""
    lower = error.lower()
    if "timeout" in lower:
        return "timeout"
    if "exhausted" in lower or "cooldown" in lower:
        return "provider_exhausted"
    if "sandbox" in lower or "bwrap" in lower:
        return "sandbox_unavailable"
    return "error"


def _routing_evidence_text(run: dict, latency_ms: float | None) -> str:
    """Render a 1-line chatbot-legible summary for a run record."""
    rid = run.get("run_id", "?")
    status = run.get("status", "?")
    bid = run.get("branch_def_id", "?")
    if latency_ms is not None:
        lat = f"{latency_ms / 1000:.2f}s"
        return f"{rid} — {status} in {lat} on {bid}"
    return f"{rid} — {status} on {bid}"


def list_recent_runs(
    base_path: str | Path,
    *,
    branch_def_id: str = "",
    limit: int = _ROUTING_EVIDENCE_DEFAULT_LIMIT,
) -> list[dict]:
    """Return last-N run records shaped for the get_routing_evidence MCP action.

    Each record includes derived ``latency_ms`` (from timestamps), a
    ``failure_class`` label, a ``suggested_action`` hint, and a ``caveat``
    noting absent provider/token fields. Limit is capped at
    ``_ROUTING_EVIDENCE_LIMIT_CAP`` to prevent token blowout.
    """
    effective_limit = min(max(1, int(limit)), _ROUTING_EVIDENCE_LIMIT_CAP)
    raw = list_runs(base_path, branch_def_id=branch_def_id, limit=effective_limit)

    results: list[dict] = []
    for run in raw:
        started = run.get("started_at")
        finished = run.get("finished_at")
        latency_ms: float | None = None
        if started is not None and finished is not None:
            try:
                # started_at / finished_at may be Unix float or ISO string.
                def _to_float(v: object) -> float | None:
                    if isinstance(v, (int, float)):
                        return float(v)
                    s = str(v)
                    if "T" in s:
                        from datetime import datetime as _dt
                        try:
                            return _dt.fromisoformat(s).timestamp()
                        except ValueError:
                            return _dt.strptime(s, "%Y-%m-%dT%H:%M:%S.%f%z").timestamp()
                    try:
                        return float(s)
                    except ValueError:
                        return None
                s_ts = _to_float(started)
                f_ts = _to_float(finished)
                if s_ts is not None and f_ts is not None:
                    latency_ms = (f_ts - s_ts) * 1000
            except Exception:  # noqa: BLE001 — best-effort
                pass

        failure_class = _classify_failure(run)
        suggested_action = ""
        if failure_class == "provider_exhausted":
            suggested_action = "Wait for provider cooldown or add an alternative provider."
        elif failure_class == "timeout":
            suggested_action = "Increase node timeout or simplify the prompt."
        elif failure_class == "sandbox_unavailable":
            suggested_action = "Enable unprivileged user namespaces or run on a bwrap-capable host."
        elif failure_class == "cancelled":
            suggested_action = "Run was cancelled by request."
        elif failure_class == "interrupted":
            suggested_action = "Run was interrupted; use resume_run to continue."
        elif failure_class == "error":
            suggested_action = "Check error field for details; re-run after fixing root cause."

        results.append({
            "text": _routing_evidence_text(run, latency_ms),
            "run_id": run.get("run_id"),
            "branch_def_id": run.get("branch_def_id"),
            "run_name": run.get("run_name"),
            "status": run.get("status"),
            "actor": run.get("actor"),
            "started_at": started,
            "finished_at": finished,
            "latency_ms": latency_ms,
            "error": run.get("error"),
            "last_node_id": run.get("last_node_id"),
            "failure_class": failure_class,
            "suggested_action": suggested_action,
            "provider_used": run.get("provider_used"),
            "token_count": run.get("token_count"),
            "caveat": _ROUTING_EVIDENCE_CAVEAT,
        })

    return results


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
    "list_recent_runs",
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
    "query_runs",
    "poll_child_run_status",
    "MAX_INVOKE_BRANCH_DEPTH",
    "post_teammate_message",
    "read_teammate_messages",
    "ack_teammate_message",
]
