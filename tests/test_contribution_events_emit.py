"""Tests for execute_step emit-site wiring — Task #72.

Coverage:
- Each terminal status (completed/failed/cancelled/interrupted) emits one
  execute_step event with correct fields.
- Non-terminal status (running) does NOT emit.
- Idempotency via deterministic event_id collision (INSERT OR IGNORE).
- Emit failure (record_contribution_event raises) does NOT break run-status
  update — try/except decoupling preserves load-bearing semantic.
- Bounty-calc smoke on real-data path (events emitted via update_run_status,
  not synthetic INSERT) — confirms §4 recursive-CTE finds production events.

Spec: docs/design-notes/2026-04-25-contribution-ledger-proposal.md §3.
"""
from __future__ import annotations

import json

import pytest

from workflow.contribution_events import _EMIT_FAILURES, _connect
from workflow.runs import (
    RUN_STATUS_CANCELLED,
    RUN_STATUS_COMPLETED,
    RUN_STATUS_FAILED,
    RUN_STATUS_INTERRUPTED,
    RUN_STATUS_QUEUED,
    RUN_STATUS_RUNNING,
    create_run,
    initialize_runs_db,
    update_run_status,
)


def _fresh_run(tmp_path, *, branch_def_id: str = "b1", actor: str = "alice",
               branch_version_id: str | None = None) -> str:
    """Create a fresh queued run, return its run_id."""
    initialize_runs_db(tmp_path)
    return create_run(
        tmp_path,
        branch_def_id=branch_def_id,
        thread_id="t1",
        inputs={},
        run_name="emit-test",
        actor=actor,
        branch_version_id=branch_version_id,
    )


def _events(tmp_path, run_id: str) -> list[dict]:
    with _connect(tmp_path) as conn:
        rows = conn.execute(
            "SELECT * FROM contribution_events WHERE source_run_id = ? "
            "ORDER BY occurred_at ASC",
            (run_id,),
        ).fetchall()
    return [dict(r) for r in rows]


@pytest.fixture(autouse=True)
def _reset_emit_failures():
    """Snapshot + restore _EMIT_FAILURES counter per test."""
    saved = _EMIT_FAILURES["count"]
    _EMIT_FAILURES["count"] = 0
    yield
    _EMIT_FAILURES["count"] = saved


# ── Terminal status emits ────────────────────────────────────────────────────


class TestTerminalStatusEmits:
    def test_completed_run_emits_event(self, tmp_path):
        run_id = _fresh_run(tmp_path)
        update_run_status(tmp_path, run_id, status=RUN_STATUS_COMPLETED)
        events = _events(tmp_path, run_id)
        assert len(events) == 1
        ev = events[0]
        assert ev["event_type"] == "execute_step"
        assert ev["event_id"] == f"execute_step:{run_id}:completed"
        assert ev["actor_id"] == "alice"
        assert ev["source_run_id"] == run_id
        assert ev["source_artifact_id"] == "b1"
        assert ev["source_artifact_kind"] == "branch_def"
        assert ev["weight"] == 1.0
        meta = json.loads(ev["metadata_json"])
        assert meta["branch_def_id"] == "b1"
        assert meta["branch_version_id"] is None
        assert meta["terminal_status"] == "completed"

    def test_failed_run_emits_event(self, tmp_path):
        """Per design §3 — failed runs still represent work attempts;
        caused_regression is a SEPARATE event type, not implied by failure."""
        run_id = _fresh_run(tmp_path)
        update_run_status(
            tmp_path, run_id, status=RUN_STATUS_FAILED, error="boom",
        )
        events = _events(tmp_path, run_id)
        assert len(events) == 1
        assert events[0]["event_type"] == "execute_step"
        assert json.loads(events[0]["metadata_json"])["terminal_status"] == "failed"

    def test_cancelled_run_emits_event(self, tmp_path):
        run_id = _fresh_run(tmp_path)
        update_run_status(tmp_path, run_id, status=RUN_STATUS_CANCELLED)
        events = _events(tmp_path, run_id)
        assert len(events) == 1
        assert events[0]["event_type"] == "execute_step"
        assert json.loads(events[0]["metadata_json"])["terminal_status"] == "cancelled"

    def test_interrupted_run_emits_event(self, tmp_path):
        run_id = _fresh_run(tmp_path)
        update_run_status(tmp_path, run_id, status=RUN_STATUS_INTERRUPTED)
        events = _events(tmp_path, run_id)
        assert len(events) == 1
        assert json.loads(events[0]["metadata_json"])["terminal_status"] == "interrupted"

    def test_version_based_run_carries_branch_version_kind(self, tmp_path):
        """When branch_version_id is set, source_artifact_kind=branch_version."""
        run_id = _fresh_run(
            tmp_path,
            branch_version_id="b1@abc12345",
        )
        update_run_status(tmp_path, run_id, status=RUN_STATUS_COMPLETED)
        events = _events(tmp_path, run_id)
        assert len(events) == 1
        ev = events[0]
        assert ev["source_artifact_id"] == "b1@abc12345"
        assert ev["source_artifact_kind"] == "branch_version"


# ── Non-terminal status does NOT emit ────────────────────────────────────────


class TestNonTerminalStatusDoesNotEmit:
    def test_running_status_does_not_emit(self, tmp_path):
        run_id = _fresh_run(tmp_path)
        update_run_status(tmp_path, run_id, status=RUN_STATUS_RUNNING)
        assert _events(tmp_path, run_id) == []

    def test_queued_status_does_not_emit(self, tmp_path):
        run_id = _fresh_run(tmp_path)
        update_run_status(tmp_path, run_id, status=RUN_STATUS_QUEUED)
        assert _events(tmp_path, run_id) == []

    def test_no_status_change_does_not_emit(self, tmp_path):
        """Updating only a non-status field doesn't trigger emit."""
        run_id = _fresh_run(tmp_path)
        update_run_status(tmp_path, run_id, error="warn-only")
        assert _events(tmp_path, run_id) == []


# ── Idempotency ──────────────────────────────────────────────────────────────


class TestIdempotency:
    def test_repeat_emit_for_same_terminal_status_skipped(self, tmp_path):
        """Two completes on the same run produce exactly 1 event row."""
        run_id = _fresh_run(tmp_path)
        update_run_status(tmp_path, run_id, status=RUN_STATUS_COMPLETED)
        update_run_status(tmp_path, run_id, status=RUN_STATUS_COMPLETED)
        events = _events(tmp_path, run_id)
        assert len(events) == 1


# ── Emit failure does NOT break status update ────────────────────────────────


class TestEmitFailureDecoupled:
    def test_emit_raise_preserves_status_update(self, tmp_path, monkeypatch):
        """If record_contribution_event raises, run.status STILL updates AND
        _EMIT_FAILURES counter increments AND a warning is logged."""
        from workflow import contribution_events as ce

        run_id = _fresh_run(tmp_path)

        def boom(*args, **kwargs):
            raise RuntimeError("simulated emit failure")

        monkeypatch.setattr(ce, "record_contribution_event", boom)

        # Status update must succeed despite emit raising.
        update_run_status(tmp_path, run_id, status=RUN_STATUS_COMPLETED)

        # Run row reflects the new status (the load-bearing semantic).
        with _connect(tmp_path) as conn:
            row = conn.execute(
                "SELECT status FROM runs WHERE run_id = ?", (run_id,),
            ).fetchone()
        assert row["status"] == "completed"

        # Counter incremented; production observers see this.
        assert _EMIT_FAILURES["count"] == 1


# ── Bounty-calc smoke on real-data path ──────────────────────────────────────


class TestBountyCalcOnRealData:
    """The §4 recursive-CTE smoke from #71 was synthetic-INSERT-only.
    This extends it to events emitted via the production path."""

    def test_emitted_events_findable_by_bounty_query(self, tmp_path):
        # Create 2 runs, each completes via update_run_status — both emit.
        run_a = _fresh_run(tmp_path, branch_def_id="ba", actor="alice")
        run_b = _fresh_run(tmp_path, branch_def_id="bb", actor="bob")
        update_run_status(tmp_path, run_a, status=RUN_STATUS_COMPLETED)
        update_run_status(tmp_path, run_b, status=RUN_STATUS_COMPLETED)

        # Bounty-calc-shaped query — sum weight by actor in a window.
        with _connect(tmp_path) as conn:
            rows = list(conn.execute(
                "SELECT actor_id, SUM(weight) AS share "
                "FROM contribution_events "
                "WHERE event_type = 'execute_step' "
                "GROUP BY actor_id "
                "ORDER BY actor_id"
            ))
        shares = {r["actor_id"]: r["share"] for r in rows}
        assert shares["alice"] == 1.0
        assert shares["bob"] == 1.0
