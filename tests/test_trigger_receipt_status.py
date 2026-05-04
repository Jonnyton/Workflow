"""Status-surface tests for FEAT-004 trigger receipt smoke telemetry."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from workflow.api.status import _compute_trigger_receipt_health, get_status
from workflow.wiki import trigger_receipts as tr


def test_trigger_receipt_health_summarizes_recent_attempts(tmp_path):
    db_path = tmp_path / "wiki_trigger_attempts.db"
    first = tr.create_pending(
        request_id="BUG-271",
        request_kind="bug",
        request_page="pages/bugs/bug-271-trigger-receipt-smoke.md",
        branch_def_id="branch-canonical",
        db_path=db_path,
    )
    tr.mark_queued(
        first,
        dispatcher_request_id="dispatcher-271",
        db_path=db_path,
    )
    second = tr.create_pending(
        request_id="FEAT-007",
        request_kind="feature",
        request_page="pages/feature-requests/feat-007.md",
        db_path=db_path,
    )

    health = _compute_trigger_receipt_health(db_path=db_path)

    assert health["receipt_store_available"] is True
    assert health["summary"]["window_size"] == 2
    assert health["summary"]["by_status"] == {"pending": 1, "queued": 1}
    assert [row["trigger_attempt_id"] for row in health["recent_attempts"]] == [
        second.trigger_attempt_id,
        first.trigger_attempt_id,
    ]
    queued = health["recent_attempts"][1]
    assert queued["request_id"] == "BUG-271"
    assert queued["status"] == "queued"
    assert queued["dispatcher_request_id"] == "dispatcher-271"
    assert queued["branch_def_id"] == "branch-canonical"
    assert "request_page" not in queued
    assert health["orphan_attempts"] == []


def test_trigger_receipt_health_surfaces_stale_pending_orphans(tmp_path):
    db_path = tmp_path / "wiki_trigger_attempts.db"
    old_ts = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    with tr._conn(db_path) as conn:
        conn.execute(
            """INSERT INTO wiki_trigger_attempts (
                trigger_attempt_id, request_id, request_kind, request_page,
                status, attempted_at
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (
                "stale-receipt",
                "BUG-999",
                "bug",
                "pages/bugs/bug-999.md",
                "pending",
                old_ts,
            ),
        )

    health = _compute_trigger_receipt_health(db_path=db_path, stale_minutes=30)

    assert health["orphan_attempts"] == [
        {
            "trigger_attempt_id": "stale-receipt",
            "request_id": "BUG-999",
            "request_kind": "bug",
            "status": "pending",
            "attempted_at": old_ts,
        }
    ]
    assert health["warnings"] == ["1 stale trigger receipt attempt(s) need review."]


def test_get_status_includes_trigger_receipt_health(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKFLOW_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("WORKFLOW_TRIGGER_RECEIPTS_DB", str(tmp_path / "receipts.db"))
    monkeypatch.setenv("UNIVERSE_SERVER_DEFAULT_UNIVERSE", "status-universe")
    (tmp_path / "status-universe").mkdir(parents=True, exist_ok=True)
    receipt = tr.create_pending(
        request_id="BUG-271",
        request_kind="bug",
        request_page="pages/bugs/bug-271-trigger-receipt-smoke.md",
    )

    response = json.loads(get_status())

    assert "trigger_receipt_health" in response
    health = response["trigger_receipt_health"]
    assert health["receipt_store_available"] is True
    assert health["recent_attempts"][0]["trigger_attempt_id"] == (
        receipt.trigger_attempt_id
    )
