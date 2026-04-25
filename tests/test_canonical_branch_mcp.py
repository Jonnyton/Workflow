"""Tests for goals action=set_canonical MCP wiring.

Spec: docs/vetted-specs.md §canonical_branch.
Implementation: workflow/universe_server.py _action_goal_set_canonical().
Depends on canonical_branch storage layer (Task #43 / daemon_server.py).
"""

from __future__ import annotations

import json

import pytest


def _make_extensions():
    from workflow.universe_server import extensions
    return extensions


def _assert_action_recognized(result: dict) -> None:
    error = result.get("error", "")
    assert "Unknown action" not in error, (
        f"set_canonical action is not wired — got unknown-action error: {error}"
    )


class TestSetCanonicalResponseShape:
    """Shape tests that don't require live universe_server state."""

    def test_set_canonical_action_in_goal_available_actions(self):
        from workflow.universe_server import _GOAL_ACTIONS
        assert "set_canonical" in _GOAL_ACTIONS

    def test_set_canonical_in_goal_write_actions(self):
        from workflow.universe_server import _GOAL_WRITE_ACTIONS
        assert "set_canonical" in _GOAL_WRITE_ACTIONS

    def test_set_canonical_in_all_goal_actions(self):
        from workflow.universe_server import _GOAL_ACTIONS, _GOAL_WRITE_ACTIONS
        assert "set_canonical" in _GOAL_ACTIONS
        assert "set_canonical" in _GOAL_WRITE_ACTIONS


class TestRunBranchVersionWiring:
    """Phase A item 6 (Task #65b) — sibling-action runs the canonical bvid."""

    def test_run_branch_version_action_wired(self):
        from workflow.universe_server import _RUN_ACTIONS
        assert "run_branch_version" in _RUN_ACTIONS

    def test_run_branch_version_in_run_write_actions(self):
        from workflow.universe_server import _RUN_WRITE_ACTIONS
        assert "run_branch_version" in _RUN_WRITE_ACTIONS

    def test_set_canonical_and_run_version_actions_compose(self):
        """End-to-end wiring: a set_canonical -> run_branch_version pipeline
        depends on both actions being registered together. Confirms the
        action namespace pair that gate-routing (Task #53) will rely on."""
        from workflow.universe_server import _GOAL_ACTIONS, _RUN_ACTIONS
        assert "set_canonical" in _GOAL_ACTIONS
        assert "run_branch_version" in _RUN_ACTIONS


@pytest.mark.xfail(reason="requires live universe_server db state", strict=True)
class TestSetCanonicalAction:
    """Integration tests for the set_canonical MCP action."""

    def test_set_canonical_by_goal_author_succeeds(self, tmp_path):
        extensions = _make_extensions()
        result = json.loads(
            extensions(goals_action="set_canonical", goal_id="g1",
                       branch_version_id="bv_test")
        )
        _assert_action_recognized(result)
        assert result["status"] == "ok"
        assert result["canonical_branch_version_id"] == "bv_test"

    def test_set_canonical_non_author_rejected(self, tmp_path):
        extensions = _make_extensions()
        result = json.loads(
            extensions(goals_action="set_canonical", goal_id="g1",
                       branch_version_id="bv_test")
        )
        _assert_action_recognized(result)
        assert result["status"] == "rejected"

    def test_set_canonical_nonexistent_version_rejected(self, tmp_path):
        extensions = _make_extensions()
        result = json.loads(
            extensions(goals_action="set_canonical", goal_id="g1",
                       branch_version_id="not-a-real-version")
        )
        _assert_action_recognized(result)
        assert result["status"] == "rejected"

    def test_unset_canonical_returns_null(self, tmp_path):
        extensions = _make_extensions()
        result = json.loads(
            extensions(goals_action="set_canonical", goal_id="g1",
                       branch_version_id="")
        )
        _assert_action_recognized(result)
        assert result["status"] == "ok"
        assert result["canonical_branch_version_id"] is None

    def test_goals_get_includes_canonical_field(self, tmp_path):
        extensions = _make_extensions()
        result = json.loads(extensions(action="get", goal_id="g1"))
        _assert_action_recognized(result)
        assert "canonical_branch_version_id" in result.get("goal", {})
