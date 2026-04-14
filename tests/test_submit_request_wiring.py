"""Task #18 — MCP submit_request must reach the daemon.

Explorer flagged that `submit_request` wrote `requests.json` but nothing
under `domains/fantasy_author/` read it — every request was silently
discarded. This suite pins the wiring: submit_request → pending entry
→ materialize into a WorkTarget during authorial_priority_review →
daemon sees it.

Covers:
- materialize_pending_requests creates a ROLE_NOTES target.
- status flips pending → seen, stamped with seen_at + work_target_id.
- Idempotent: re-running the helper on a seen request does nothing.
- authorial_priority_review picks up the request within one cycle.
- Non-pending entries (already seen, malformed) are skipped gracefully.
"""

from __future__ import annotations

import json

import pytest

from domains.fantasy_author.phases.authorial_priority_review import (
    authorial_priority_review,
)
from workflow.work_targets import (
    ROLE_NOTES,
    load_work_targets,
    materialize_pending_requests,
    requests_path,
)


@pytest.fixture
def universe_dir(tmp_path):
    d = tmp_path / "test-universe"
    d.mkdir()
    return d


def _write_requests(universe_dir, entries):
    requests_path(universe_dir).write_text(
        json.dumps(entries, indent=2), encoding="utf-8",
    )


def _read_requests(universe_dir):
    return json.loads(
        requests_path(universe_dir).read_text(encoding="utf-8"),
    )


# ─── materialize_pending_requests ──────────────────────────────────────


def test_materialize_creates_notes_target(universe_dir):
    _write_requests(universe_dir, [
        {
            "id": "req_1",
            "type": "scene_direction",
            "text": "Add a chase scene through the bazaar.",
            "branch_id": None,
            "status": "pending",
            "timestamp": "2026-04-14T12:00:00Z",
            "source": "alice",
        },
    ])
    created = materialize_pending_requests(universe_dir)
    assert len(created) == 1
    target = created[0]
    assert target.role == ROLE_NOTES
    assert "chase scene" in target.current_intent
    assert "user-request" in target.tags
    assert "scene_direction" in target.tags
    assert target.metadata["request_id"] == "req_1"
    assert target.metadata["request_source"] == "alice"


def test_materialize_flips_status_and_stamps_seen(universe_dir):
    _write_requests(universe_dir, [
        {"id": "req_2", "type": "revision", "text": "fix ch1",
         "status": "pending", "source": "bob"},
    ])
    materialize_pending_requests(universe_dir)
    reqs = _read_requests(universe_dir)
    assert reqs[0]["status"] == "seen"
    assert reqs[0]["seen_at"]
    assert reqs[0]["work_target_id"]


def test_materialize_is_idempotent_on_seen_requests(universe_dir):
    _write_requests(universe_dir, [
        {"id": "req_3", "type": "general", "text": "hi", "status": "pending"},
    ])
    first = materialize_pending_requests(universe_dir)
    second = materialize_pending_requests(universe_dir)
    assert len(first) == 1
    assert len(second) == 0
    # Only one target in registry.
    targets = [
        t for t in load_work_targets(universe_dir)
        if "user-request" in t.tags
    ]
    assert len(targets) == 1


def test_materialize_skips_malformed_entries(universe_dir):
    _write_requests(universe_dir, [
        "not a dict",
        {"id": "", "type": "x", "text": "no id", "status": "pending"},
        {"id": "req_4", "type": "general", "text": "ok", "status": "pending"},
        {"id": "req_5", "type": "general", "text": "already seen",
         "status": "seen"},
    ])
    created = materialize_pending_requests(universe_dir)
    assert len(created) == 1
    assert created[0].metadata["request_id"] == "req_4"


def test_materialize_missing_file_is_noop(universe_dir):
    # No requests.json on disk; should return [] without crashing.
    assert materialize_pending_requests(universe_dir) == []


# ─── authorial_priority_review integration ─────────────────────────────


def test_authorial_review_surfaces_pending_request_within_one_cycle(
    universe_dir,
):
    """Core contract: submit_request → one review cycle → daemon sees it."""
    _write_requests(universe_dir, [
        {
            "id": "req_wiring",
            "type": "scene_direction",
            "text": "Insert a quiet moment in chapter 3.",
            "status": "pending",
            "source": "reader",
        },
    ])

    result = authorial_priority_review({
        "_universe_path": str(universe_dir),
        "workflow_instructions": {"premise": "Glass kingdom."},
    })

    # Daemon selected some target (the request or a seed — either is fine,
    # but the request must be in the candidate set).
    trace = result["quality_trace"][0]
    assert trace["materialized_request_count"] == 1

    # Request is now marked seen.
    reqs = _read_requests(universe_dir)
    assert reqs[0]["status"] == "seen"

    # A WorkTarget tagged user-request exists in the registry.
    targets = [
        t for t in load_work_targets(universe_dir)
        if "user-request" in t.tags
    ]
    assert len(targets) == 1
    assert targets[0].metadata["request_id"] == "req_wiring"


def test_authorial_review_no_requests_still_works(universe_dir):
    # Baseline: no requests.json should not disturb the existing flow.
    result = authorial_priority_review({
        "_universe_path": str(universe_dir),
        "workflow_instructions": {"premise": "Empty run."},
    })
    trace = result["quality_trace"][0]
    assert trace["materialized_request_count"] == 0
