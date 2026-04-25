"""Tests for the file_bug → enqueue_investigation_request forward-trigger seam.

Task #34 (FRESH-A). Covers `_maybe_enqueue_investigation` directly. The
integration with `_wiki_file_bug` is captured as a skipped test that flips
to active once verifier-2 lands the one-line call site in
`universe_server.py`. Spec: `docs/exec-plans/active/2026-04-25-file-bug-wiring.md`.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from workflow.branch_tasks import read_queue
from workflow.bug_investigation import (
    REQUEST_TYPE_BUG_INVESTIGATION,
    _maybe_enqueue_investigation,
)

# ── _maybe_enqueue_investigation: env-gate ────────────────────────────────────


class TestEnvGate:
    def test_returns_none_when_env_unset(self, tmp_path, monkeypatch):
        monkeypatch.delenv("WORKFLOW_BUG_INVESTIGATION_BRANCH_DEF_ID", raising=False)
        result = _maybe_enqueue_investigation(
            bug_id="BUG-100",
            frontmatter={"title": "x"},
            base_path=tmp_path,
        )
        assert result is None
        assert read_queue(tmp_path) == []

    def test_returns_none_when_env_empty_string(self, tmp_path, monkeypatch):
        monkeypatch.setenv("WORKFLOW_BUG_INVESTIGATION_BRANCH_DEF_ID", "")
        result = _maybe_enqueue_investigation(
            bug_id="BUG-101",
            frontmatter={"title": "x"},
            base_path=tmp_path,
        )
        assert result is None
        assert read_queue(tmp_path) == []

    def test_returns_none_when_env_whitespace(self, tmp_path, monkeypatch):
        monkeypatch.setenv("WORKFLOW_BUG_INVESTIGATION_BRANCH_DEF_ID", "   ")
        result = _maybe_enqueue_investigation(
            bug_id="BUG-102",
            frontmatter={"title": "x"},
            base_path=tmp_path,
        )
        assert result is None
        assert read_queue(tmp_path) == []


# ── _maybe_enqueue_investigation: happy path ──────────────────────────────────


class TestEnqueuesWhenBound:
    def test_enqueues_when_canonical_bound(self, tmp_path, monkeypatch):
        monkeypatch.setenv(
            "WORKFLOW_BUG_INVESTIGATION_BRANCH_DEF_ID", "branch-canonical-abc"
        )
        monkeypatch.delenv("WORKFLOW_REQUEST_TYPE_PRIORITIES", raising=False)
        request_id = _maybe_enqueue_investigation(
            bug_id="BUG-200",
            frontmatter={
                "title": "crash on load",
                "severity": "high",
                "component": "engine",
            },
            base_path=tmp_path,
        )
        assert request_id is not None
        assert len(request_id) == 36

        queue = read_queue(tmp_path)
        assert len(queue) == 1
        task = queue[0]
        assert task.branch_task_id == request_id
        assert task.request_type == REQUEST_TYPE_BUG_INVESTIGATION
        assert task.branch_def_id == "branch-canonical-abc"
        assert task.inputs["bug_id"] == "BUG-200"
        assert task.inputs["title"] == "crash on load"
        assert task.inputs["severity"] == "high"

    def test_passes_universe_id_through(self, tmp_path, monkeypatch):
        monkeypatch.setenv(
            "WORKFLOW_BUG_INVESTIGATION_BRANCH_DEF_ID", "branch-canonical-abc"
        )
        monkeypatch.delenv("WORKFLOW_REQUEST_TYPE_PRIORITIES", raising=False)
        _maybe_enqueue_investigation(
            bug_id="BUG-201",
            frontmatter={"title": "x"},
            base_path=tmp_path,
            universe_id="custom-universe",
        )
        queue = read_queue(tmp_path)
        assert queue[0].universe_id == "custom-universe"

    def test_frontmatter_bug_id_overridden_by_arg(self, tmp_path, monkeypatch):
        """Even if frontmatter has a stale bug_id, the explicit arg wins."""
        monkeypatch.setenv(
            "WORKFLOW_BUG_INVESTIGATION_BRANCH_DEF_ID", "branch-canonical-abc"
        )
        monkeypatch.delenv("WORKFLOW_REQUEST_TYPE_PRIORITIES", raising=False)
        _maybe_enqueue_investigation(
            bug_id="BUG-202",
            frontmatter={"bug_id": "BUG-WRONG", "title": "x"},
            base_path=tmp_path,
        )
        queue = read_queue(tmp_path)
        assert queue[0].inputs["bug_id"] == "BUG-202"


# ── _maybe_enqueue_investigation: graceful failure ────────────────────────────


class TestGracefulFailure:
    def test_returns_none_on_dispatcher_rejection(self, tmp_path, monkeypatch):
        """When `WORKFLOW_REQUEST_TYPE_PRIORITIES` excludes bug_investigation,
        enqueue raises RuntimeError. Filing must NOT break — caller gets None."""
        monkeypatch.setenv(
            "WORKFLOW_BUG_INVESTIGATION_BRANCH_DEF_ID", "branch-canonical-abc"
        )
        monkeypatch.setenv(
            "WORKFLOW_REQUEST_TYPE_PRIORITIES", "paid_market,branch_run"
        )
        result = _maybe_enqueue_investigation(
            bug_id="BUG-300",
            frontmatter={"title": "x"},
            base_path=tmp_path,
        )
        assert result is None
        assert read_queue(tmp_path) == []

    def test_returns_none_on_missing_bug_id(self, tmp_path, monkeypatch):
        """Empty bug_id is a malformed input — log and return None, do not crash."""
        monkeypatch.setenv(
            "WORKFLOW_BUG_INVESTIGATION_BRANCH_DEF_ID", "branch-canonical-abc"
        )
        monkeypatch.delenv("WORKFLOW_REQUEST_TYPE_PRIORITIES", raising=False)
        result = _maybe_enqueue_investigation(
            bug_id="",
            frontmatter={"title": "x"},
            base_path=tmp_path,
        )
        assert result is None
        assert read_queue(tmp_path) == []

    def test_returns_none_on_value_error_from_enqueue(self, tmp_path, monkeypatch):
        """If `enqueue_investigation_request` raises ValueError, we recover."""
        monkeypatch.setenv(
            "WORKFLOW_BUG_INVESTIGATION_BRANCH_DEF_ID", "branch-canonical-abc"
        )
        monkeypatch.delenv("WORKFLOW_REQUEST_TYPE_PRIORITIES", raising=False)
        with patch(
            "workflow.bug_investigation.enqueue_investigation_request",
            side_effect=ValueError("boom"),
        ):
            result = _maybe_enqueue_investigation(
                bug_id="BUG-301",
                frontmatter={"title": "x"},
                base_path=tmp_path,
            )
        assert result is None

    def test_none_frontmatter_does_not_crash(self, tmp_path, monkeypatch):
        monkeypatch.setenv(
            "WORKFLOW_BUG_INVESTIGATION_BRANCH_DEF_ID", "branch-canonical-abc"
        )
        monkeypatch.delenv("WORKFLOW_REQUEST_TYPE_PRIORITIES", raising=False)
        request_id = _maybe_enqueue_investigation(
            bug_id="BUG-302",
            frontmatter=None,  # type: ignore[arg-type]
            base_path=tmp_path,
        )
        assert request_id is not None
        queue = read_queue(tmp_path)
        assert queue[0].inputs["bug_id"] == "BUG-302"


# ── Integration: _wiki_file_bug call site (UNWIRED today) ─────────────────────


@pytest.mark.skip(
    reason="call site not wired yet — see docs/exec-plans/active/2026-04-25-file-bug-wiring.md"
)
def test_wiki_file_bug_invokes_maybe_enqueue_investigation(tmp_path, monkeypatch):
    """When verifier-2 lands the one-line call in `_wiki_file_bug` after
    `_append_wiki_log`, this test flips to active. The wiring contract:

    1. _wiki_file_bug succeeds (returns status=filed) regardless of helper outcome.
    2. _maybe_enqueue_investigation is called once with bug_id + frontmatter +
       base_path of the universe.
    3. Helper RuntimeError/ValueError must NOT propagate; filing still returns
       status=filed.

    Removing this skip + landing the call site is the FRESH-A integration step.
    """
    from workflow import universe_server

    monkeypatch.setenv(
        "WORKFLOW_BUG_INVESTIGATION_BRANCH_DEF_ID", "branch-canonical-abc"
    )
    monkeypatch.delenv("WORKFLOW_REQUEST_TYPE_PRIORITIES", raising=False)

    with patch(
        "workflow.bug_investigation._maybe_enqueue_investigation",
        return_value="fake-request-id",
    ) as helper:
        result_json = universe_server._wiki_file_bug(
            component="engine",
            severity="high",
            title="example bug",
            observed="boom",
        )

    import json as _json
    result = _json.loads(result_json)
    assert result["status"] == "filed"
    assert helper.call_count == 1
    bug_id = result["bug_id"]
    call_kwargs = helper.call_args.kwargs or {}
    call_args = helper.call_args.args or ()
    # accept either kwarg or positional first arg
    assert (call_kwargs.get("bug_id") == bug_id) or (
        call_args and call_args[0] == bug_id
    )
