"""Surgical rollback engine — closure walk + atomic status flip + post-rollback re-point.

Spec: docs/design-notes/2026-04-25-surgical-rollback-proposal.md.
Audit: 1f04067 (Task #57 design).

Implements the rollback primitive that lets autonomous patch loops
self-validate (patch → canary observes → rollback if regression). Phase B
of Task #22 — closure-walk + host-callable rollback verb. Phase C
(separate task #27) wires bisect + canary auto-trigger.

Cross-DB atomicity refinement (lead-approved 2026-04-26):
The original design §2 calls for a single ``BEGIN IMMEDIATE`` wrapping
status-flip + goal-canonical re-point + event emission. In the live
codebase those tables span TWO SQLite databases:

- ``branch_versions`` + ``contribution_events`` → runs DB.
- ``goals`` + ``canonical_bindings`` → author_server DB.

SQLite cannot atomically span two DBs without ``ATTACH``, which would
introduce a novel pattern across the codebase. We refine the design:
``execute_rollback_set`` runs as a single runs-DB transaction (status +
events). Goal-canonical re-point runs as a downstream observer in a
separate author_server-DB transaction (``repoint_goals_after_rollback``).
The "atomic" guarantee weakens to a bounded ~ms window where a goal's
canonical_branch_version_id may point at a rolled_back version — the
read-side already gracefully degrades via the version's ``status`` field
+ the canonical_bindings cutover. Per
``feedback_submission_boundary_clamp``: the rollback engine clamps to
its own DB; goal re-point is a separate domain at its own boundary.

The orchestrator (``rollback_merge_orchestrator``) chains both phases
and surfaces partial-failure to the caller via the result dict.
"""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from workflow.branch_versions import _connect as _runs_connect
from workflow.contribution_events import (
    initialize_contribution_events_db,
    record_contribution_event,
)

# Severity weights per design §5 + attribution-layer-specs §6.1.
# Phase C uses these to gate auto-trigger; Phase B exposes them for
# callers who want to inspect the weight surface up-front.
ROLLBACK_WEIGHTS: dict[str, int] = {
    "P0": -10,
    "P1": -3,
    "P2": -1,
}

# Auto-rollback fires for weight ≤ this value (per design §5: P1+).
# P2 (weight -1) emits the event but does NOT auto-rollback.
AUTO_ROLLBACK_WEIGHT_THRESHOLD: int = -3


# ─── Closure walk ────────────────────────────────────────────────────────


def compute_rollback_set(
    base_path: str | Path,
    rolled_back_version_id: str,
) -> list[str]:
    """Return all branch_version_ids in the dependency closure of the
    rolled-back version.

    Walks two relations per design §2:
    - Forward chain: any version with ``parent_version_id == bvid``.
    - Fork-children: any branch_def with ``fork_from == bvid``; for each
      such fork, all of its published versions enter the closure.

    Returns the closure as a list (caller decides ordering). Includes
    the seed ``rolled_back_version_id`` itself. Closure is artifact-level
    only; in-flight runs that referenced the artifact are handled
    separately in Phase C (per design §6 Q6).

    Closure walk is read-only against the runs DB (branch_versions) +
    author_server DB (branch_definitions). No state mutation.
    """
    closure: set[str] = {rolled_back_version_id}
    queue: list[str] = [rolled_back_version_id]

    with _runs_connect(base_path) as runs_conn:
        while queue:
            bvid = queue.pop()
            # Forward chain: children with parent_version_id == bvid.
            children = runs_conn.execute(
                "SELECT branch_version_id FROM branch_versions "
                "WHERE parent_version_id = ?",
                (bvid,),
            ).fetchall()
            for row in children:
                child_bvid = row["branch_version_id"]
                if child_bvid not in closure:
                    closure.add(child_bvid)
                    queue.append(child_bvid)

            # Fork-children: any branch_def whose fork_from == bvid;
            # then all of that branch_def's published versions.
            forks = _query_fork_children(base_path, bvid)
            for fork_def_id in forks:
                fork_versions = runs_conn.execute(
                    "SELECT branch_version_id FROM branch_versions "
                    "WHERE branch_def_id = ?",
                    (fork_def_id,),
                ).fetchall()
                for fv_row in fork_versions:
                    fv_bvid = fv_row["branch_version_id"]
                    if fv_bvid not in closure:
                        closure.add(fv_bvid)
                        queue.append(fv_bvid)

    return sorted(closure)  # deterministic order for tests + caller readability


def _query_fork_children(base_path: str | Path, bvid: str) -> list[str]:
    """Return branch_def_ids that forked from the given branch_version_id.

    Reads the author_server DB (where ``branch_definitions`` lives) via
    its own connection. Read-only.

    Defensive: if `branch_definitions` doesn't exist yet (e.g. the
    author_server DB hasn't been initialized for this universe), returns
    empty — closure walk for this seed simply has no fork-children. The
    only state needed to roll back the seed itself is the runs DB, so
    silently degrading here is correct: the rollback proceeds with an
    accurate (smaller) closure.
    """
    from workflow.daemon_server import _connect as _author_connect

    with _author_connect(base_path) as conn:
        try:
            rows = conn.execute(
                "SELECT branch_def_id FROM branch_definitions "
                "WHERE fork_from = ?",
                (bvid,),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
    return [r["branch_def_id"] for r in rows]


# ─── Atomic execution (runs DB only, per refinement) ─────────────────────


def execute_rollback_set(
    base_path: str | Path,
    version_ids: Iterable[str],
    *,
    reason: str,
    set_by: str,
    severity: str = "P1",
) -> dict[str, Any]:
    """Atomically flip status to ``'rolled_back'`` for every version in the
    set + emit a ``caused_regression`` event per version.

    Single ``BEGIN IMMEDIATE`` transaction on the runs DB. If any step
    fails, the transaction aborts and no version is marked. Goal-canonical
    re-point is a SEPARATE step (``repoint_goals_after_rollback``) per the
    cross-DB atomicity refinement.

    Args:
        version_ids: closure to mark (typically from ``compute_rollback_set``).
        reason: free-form text written to ``rolled_back_reason``.
        set_by: actor id / username that initiated the rollback. Recorded
            on each version + on each emitted event.
        severity: ``"P0"`` | ``"P1"`` | ``"P2"`` (per design §5). Maps to
            event weight via ``ROLLBACK_WEIGHTS``. Default ``"P1"`` matches
            the most common host-initiated case.

    Returns:
        ``{"status": "ok", "rolled_back_count": N, "version_ids": [...],
           "event_ids": [...], "weight": int}`` on success, or
        ``{"status": "rejected", "error": str}`` on validation failure.

    Raises:
        sqlite3.OperationalError on lock contention; caller's responsibility
        to retry with backoff if needed.
    """
    version_ids_list = list(version_ids)
    if not version_ids_list:
        return {"status": "rejected", "error": "version_ids is empty."}
    if severity not in ROLLBACK_WEIGHTS:
        return {
            "status": "rejected",
            "error": f"severity must be one of {sorted(ROLLBACK_WEIGHTS)}; got {severity!r}.",
        }

    weight = ROLLBACK_WEIGHTS[severity]
    now_iso = datetime.now(timezone.utc).isoformat()
    now_epoch = time.time()
    event_ids: list[str] = []

    # Ensure both schemas exist BEFORE the BEGIN IMMEDIATE — the
    # initialize calls take their own write locks, which would deadlock
    # if nested inside our transaction.
    initialize_contribution_events_db(base_path)

    with _runs_connect(base_path) as conn:
        try:
            conn.execute("BEGIN IMMEDIATE")

            # Validate every version exists + is not already rolled back.
            # Validation INSIDE the transaction so concurrent rollbacks
            # of the same set are serialized correctly.
            for bvid in version_ids_list:
                row = conn.execute(
                    "SELECT branch_version_id, status FROM branch_versions "
                    "WHERE branch_version_id = ?",
                    (bvid,),
                ).fetchone()
                if row is None:
                    raise _RollbackAbort(
                        f"branch_version_id {bvid!r} does not exist."
                    )
                if row["status"] == "rolled_back":
                    raise _RollbackAbort(
                        f"branch_version_id {bvid!r} is already rolled_back."
                    )

            # Status flip — all versions in one pass.
            for bvid in version_ids_list:
                conn.execute(
                    """
                    UPDATE branch_versions
                       SET status = 'rolled_back',
                           rolled_back_at = ?,
                           rolled_back_by = ?,
                           rolled_back_reason = ?
                     WHERE branch_version_id = ?
                    """,
                    (now_iso, set_by, reason, bvid),
                )

            # Emit one caused_regression event per rolled-back version.
            # Pass our open `conn` so the inserts share our BEGIN IMMEDIATE
            # transaction (per record_contribution_event's `conn=` seam).
            for bvid in version_ids_list:
                event_id = f"caused_regression:{bvid}:{now_iso}"
                inserted = record_contribution_event(
                    base_path,
                    event_id=event_id,
                    event_type="caused_regression",
                    actor_id=set_by,
                    source_artifact_id=bvid,
                    source_artifact_kind="branch_version",
                    weight=float(weight),
                    occurred_at=now_epoch,
                    metadata_json=json.dumps({
                        "rolled_back_at": now_iso,
                        "reason": reason,
                        "severity": severity,
                    }),
                    conn=conn,
                )
                if inserted:
                    event_ids.append(event_id)

            conn.execute("COMMIT")
        except _RollbackAbort as exc:
            conn.execute("ROLLBACK")
            return {"status": "rejected", "error": str(exc)}
        except sqlite3.Error:
            conn.execute("ROLLBACK")
            raise

    return {
        "status": "ok",
        "rolled_back_count": len(version_ids_list),
        "version_ids": version_ids_list,
        "event_ids": event_ids,
        "weight": weight,
        "rolled_back_at": now_iso,
    }


class _RollbackAbort(Exception):
    """Internal: signals a validation failure inside the BEGIN IMMEDIATE
    block so the outer ``except`` can ROLLBACK + return a structured
    rejection without exposing this class to callers.
    """


# ─── Goal-canonical re-point (author_server DB, post-rollback observer) ──


def repoint_goals_after_rollback(
    base_path: str | Path,
    version_ids: Iterable[str],
    *,
    set_by: str,
) -> dict[str, Any]:
    """Re-point any Goal whose canonical_branch_version_id is in the
    rolled-back set to its parent_version_id (cascading walk-up to the
    nearest non-rolled-back ancestor; NULL if none).

    Runs in a separate author_server-DB transaction per the cross-DB
    refinement. Does NOT roll back the rollback if this fails — the
    versions remain ``rolled_back`` and the goal continues to point at a
    rolled-back canonical until next intervention.

    Returns:
        ``{"status": "ok", "repointed_count": N, "repoints": [...]}``
        with a per-goal log of (goal_id, old_bvid, new_bvid) tuples.
    """
    from workflow.daemon_server import _connect as _author_connect
    from workflow.daemon_server import set_canonical_branch

    rolled_back_set = set(version_ids)
    if not rolled_back_set:
        return {"status": "ok", "repointed_count": 0, "repoints": []}

    repoints: list[dict[str, Any]] = []

    # Find affected goals first (read), then process each via the
    # existing set_canonical_branch helper so we benefit from its
    # legacy-column + canonical_bindings dual-write per Task #61.
    # Defensive: if goals table doesn't exist (universe never had any
    # goals yet), there's nothing to re-point — return clean no-op.
    with _author_connect(base_path) as conn:
        placeholders = ",".join("?" * len(rolled_back_set))
        try:
            affected = conn.execute(
                f"SELECT goal_id, canonical_branch_version_id FROM goals "
                f"WHERE canonical_branch_version_id IN ({placeholders})",
                tuple(rolled_back_set),
            ).fetchall()
        except sqlite3.OperationalError:
            return {"status": "ok", "repointed_count": 0, "repoints": []}

    for row in affected:
        goal_id = row["goal_id"]
        old_bvid = row["canonical_branch_version_id"]
        new_bvid = _walk_up_to_active_ancestor(base_path, old_bvid, rolled_back_set)
        try:
            set_canonical_branch(
                base_path,
                goal_id=goal_id,
                branch_version_id=new_bvid,
                set_by=set_by,
            )
            repoints.append({
                "goal_id": goal_id,
                "old_branch_version_id": old_bvid,
                "new_branch_version_id": new_bvid,
            })
        except (KeyError, ValueError) as exc:
            # Per design intent: don't fail the whole re-point batch on
            # one bad goal. Log the failure into the per-goal log so
            # operators can see what didn't re-point.
            repoints.append({
                "goal_id": goal_id,
                "old_branch_version_id": old_bvid,
                "new_branch_version_id": None,
                "error": str(exc),
            })

    return {
        "status": "ok",
        "repointed_count": len(repoints),
        "repoints": repoints,
    }


def _walk_up_to_active_ancestor(
    base_path: str | Path,
    start_bvid: str,
    rolled_back_set: set[str],
) -> str | None:
    """Walk parent_version_id upward until finding a version NOT in
    ``rolled_back_set`` whose status is also ``'active'``. Returns None
    if the chain runs out (no eligible ancestor).
    """
    from workflow.branch_versions import get_branch_version

    visited: set[str] = set()
    current = start_bvid
    while current and current not in visited:
        visited.add(current)
        version = get_branch_version(base_path, current)
        if version is None:
            return None
        if (
            current not in rolled_back_set
            and version.status == "active"
        ):
            return current
        current = version.parent_version_id  # may be None → loop exits
    return None


# ─── Top-level orchestrator ──────────────────────────────────────────────


def rollback_merge_orchestrator(
    base_path: str | Path,
    branch_version_id: str,
    *,
    reason: str,
    set_by: str,
    severity: str = "P1",
) -> dict[str, Any]:
    """End-to-end host-callable rollback: closure walk → execute → re-point.

    Composes the three primitives per the cross-DB refinement (lead-
    approved option C). Returns a combined summary with both phases'
    results so the caller can see exactly what happened.

    Args:
        branch_version_id: the seed version to roll back; closure walk
            extends to its dependency set.
        reason / set_by / severity: passed through to ``execute_rollback_set``.

    Returns:
        ``{
            "status": "ok" | "rejected",
            "seed_version_id": str,
            "closure": [...],
            "execute": {...},     # execute_rollback_set result
            "repoint": {...},     # repoint_goals_after_rollback result (omitted on reject)
            "error"?: str,        # only on status="rejected"
        }``
    """
    closure = compute_rollback_set(base_path, branch_version_id)
    execute_result = execute_rollback_set(
        base_path,
        closure,
        reason=reason,
        set_by=set_by,
        severity=severity,
    )
    if execute_result["status"] != "ok":
        return {
            "status": "rejected",
            "seed_version_id": branch_version_id,
            "closure": closure,
            "execute": execute_result,
            "error": execute_result.get("error", "execute_rollback_set rejected"),
        }
    repoint_result = repoint_goals_after_rollback(
        base_path, closure, set_by=set_by,
    )
    return {
        "status": "ok",
        "seed_version_id": branch_version_id,
        "closure": closure,
        "execute": execute_result,
        "repoint": repoint_result,
    }


# ─── History query (read-only) ───────────────────────────────────────────


def get_rollback_history(
    base_path: str | Path,
    *,
    since_days: int = 7,
) -> list[dict[str, Any]]:
    """Return rolled-back versions in the past N days, newest first.

    Each entry includes the version metadata + the list of
    ``caused_regression`` event_ids tied to it (via the
    ``contribution_events.branch_version_id`` column).
    """
    from workflow.branch_versions import initialize_branch_versions_db

    initialize_branch_versions_db(base_path)
    cutoff_iso = (
        datetime.now(timezone.utc)
        - _seconds_as_timedelta(since_days * 86400)
    ).isoformat()

    history: list[dict[str, Any]] = []
    with _runs_connect(base_path) as conn:
        rows = conn.execute(
            """
            SELECT branch_version_id, branch_def_id, rolled_back_at,
                   rolled_back_by, rolled_back_reason
              FROM branch_versions
             WHERE status = 'rolled_back' AND rolled_back_at >= ?
             ORDER BY rolled_back_at DESC
            """,
            (cutoff_iso,),
        ).fetchall()
        for row in rows:
            event_rows = conn.execute(
                "SELECT event_id, weight FROM contribution_events "
                "WHERE event_type = 'caused_regression' "
                "  AND source_artifact_kind = 'branch_version' "
                "  AND source_artifact_id = ?",
                (row["branch_version_id"],),
            ).fetchall()
            history.append({
                "branch_version_id": row["branch_version_id"],
                "branch_def_id": row["branch_def_id"],
                "rolled_back_at": row["rolled_back_at"],
                "rolled_back_by": row["rolled_back_by"],
                "rolled_back_reason": row["rolled_back_reason"],
                "event_ids": [e["event_id"] for e in event_rows],
                "weights": [int(e["weight"]) for e in event_rows],
            })
    return history


def _seconds_as_timedelta(seconds: int):
    """Local import shim — ``timedelta`` is only needed here."""
    from datetime import timedelta
    return timedelta(seconds=seconds)


__all__ = [
    "AUTO_ROLLBACK_WEIGHT_THRESHOLD",
    "ROLLBACK_WEIGHTS",
    "compute_rollback_set",
    "execute_rollback_set",
    "get_rollback_history",
    "repoint_goals_after_rollback",
    "rollback_merge_orchestrator",
]
