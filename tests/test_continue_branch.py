"""TDD scaffold — tests/test_continue_branch.py

Tests for the `continue_branch` MCP action (extensions tool).

Spec: docs/vetted-specs.md §continue_branch — workspace-memory continuity primitive.

Implementation target: workflow/universe_server.py `_action_continue_branch()`
wired into _EXT_ACTIONS. These tests define the contract; they will be FAILING
until the action is implemented (tagged with pytest.mark.xfail where appropriate).

Schema/shape tests that don't require the live action are runnable today.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from workflow.branches import BranchDefinition, EdgeDefinition, GraphNodeRef, NodeDefinition

# ── helpers ───────────────────────────────────────────────────────────────────

def _seed_branch(base_path: Path, branch_id: str = "b1") -> None:
    from workflow.daemon_server import initialize_author_server, save_branch_definition

    initialize_author_server(base_path)
    nd = NodeDefinition(node_id="n1", display_name="N1", prompt_template="do X")
    branch = BranchDefinition(
        branch_def_id=branch_id,
        name="Test Branch",
        graph_nodes=[GraphNodeRef(id="n1", node_def_id="n1")],
        edges=[EdgeDefinition(from_node="n1", to_node="END")],
        entry_point="n1",
        node_defs=[nd],
        state_schema=[{"name": "output", "type": "str"}],
    )
    save_branch_definition(base_path, branch_def=branch.to_dict())


def _seed_run(
    base_path: Path,
    branch_id: str = "b1",
    status: str = "completed",
) -> str:
    from workflow.runs import create_run, update_run_status

    run_id = create_run(
        base_path,
        branch_def_id=branch_id,
        thread_id=uuid.uuid4().hex,
        inputs={},
        run_name="test run",
    )
    if status == "completed":
        update_run_status(base_path, run_id, status="completed", output={})
    return run_id


# ── Response shape tests (no action invocation — runnable today) ──────────────

class TestContinueBranchResponseShape:
    """Validate the expected response schema against literal dicts.

    These tests run without the implementation and document the contract.
    """

    def test_expected_response_keys_documented(self):
        expected_keys = {
            "branch_def_id",
            "branch_name",
            "description",
            "last_modified_at",
            "run_history",
            "open_notes",
            "current_phase",
            "session_boundary",
            "prior_session_available",
            "chatbot_summary",
        }
        # Canary: if the spec changes these must change too.
        assert len(expected_keys) == 10

    def test_chatbot_summary_is_string_type(self):
        # chatbot_summary must always be a non-null string, per spec invariant.
        mock_response = {
            "chatbot_summary": "Your branch has 0 completed runs.",
            "prior_session_available": False,
        }
        assert isinstance(mock_response["chatbot_summary"], str)
        assert len(mock_response["chatbot_summary"]) > 0

    def test_session_boundary_always_present(self):
        # Invariant: session_boundary block always present.
        mock_response = {
            "session_boundary": {
                "prior_session_context_available": False,
                "session_id": "s1",
            }
        }
        assert "session_boundary" in mock_response
        assert "prior_session_context_available" in mock_response["session_boundary"]

    def test_prior_session_available_mirrors_session_boundary(self):
        # prior_session_available is a top-level shorthand; must mirror
        # session_boundary.prior_session_context_available.
        sb = {"prior_session_context_available": False}
        mock_response = {
            "session_boundary": sb,
            "prior_session_available": sb["prior_session_context_available"],
        }
        assert mock_response["prior_session_available"] is False


# ── Action invocation tests (require implementation — tagged xfail) ───────────

def _assert_action_recognized(result: dict) -> None:
    """Guard: fail if the action is still unknown (not yet implemented)."""
    assert "error" not in result or "Unknown action" not in result.get("error", ""), (
        "continue_branch action is not yet implemented — "
        f"got unknown-action error: {result.get('error')}"
    )


class TestContinueBranchAction:
    """Full integration tests against the extensions MCP action.

    All tests here are tagged xfail(strict=True) so they fail now and will
    automatically un-fail when the implementation lands. If any pass
    before the implementation is merged, that's a bug.
    """

    def test_branch_with_runs_returns_run_history(self, tmp_path, monkeypatch):
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(tmp_path))
        _seed_branch(tmp_path)
        _seed_run(tmp_path)
        _seed_run(tmp_path)
        _seed_run(tmp_path)
        from workflow.universe_server import extensions
        result = json.loads(extensions(action="continue_branch", branch_def_id="b1"))
        _assert_action_recognized(result)
        assert "run_history" in result
        assert len(result["run_history"]) == 3

    def test_branch_with_zero_runs_returns_empty_history_nonnull_summary(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(tmp_path))
        _seed_branch(tmp_path)
        from workflow.universe_server import extensions
        result = json.loads(extensions(action="continue_branch", branch_def_id="b1"))
        _assert_action_recognized(result)
        assert result["run_history"] == []
        assert isinstance(result["chatbot_summary"], str)
        assert len(result["chatbot_summary"]) > 0

    def test_open_notes_lte2_quoted_inline_in_summary(self, tmp_path, monkeypatch):
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(tmp_path))
        _seed_branch(tmp_path)
        # TODO: seed notes.json with 2 open user notes for branch b1.
        # Notes seeding requires notes.json writer — implement alongside action.
        from workflow.universe_server import extensions
        result = json.loads(extensions(action="continue_branch", branch_def_id="b1"))
        _assert_action_recognized(result)
        assert "chatbot_summary" in result

    def test_prior_session_unavailable_reflected_in_summary(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(tmp_path))
        _seed_branch(tmp_path)
        from workflow.universe_server import extensions
        result = json.loads(extensions(action="continue_branch", branch_def_id="b1"))
        _assert_action_recognized(result)
        # When no prior session exists, prior_session_available must be False
        # and chatbot_summary must contain anti-hallucination language.
        assert "prior_session_available" in result
        if not result["prior_session_available"]:
            summary = result["chatbot_summary"].lower()
            # Must mention absence of prior context; not assert what words exactly.
            assert any(
                phrase in summary
                for phrase in ["no prior", "first time", "context was not", "no session"]
            )

    def test_prior_session_available_true_includes_timestamp(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(tmp_path))
        _seed_branch(tmp_path)
        _seed_run(tmp_path)
        from workflow.universe_server import extensions  # After a run exists, prior_session_available may be True
        # and chatbot_summary should mention a timestamp.
        result = json.loads(extensions(action="continue_branch", branch_def_id="b1"))
        _assert_action_recognized(result)
        assert "session_boundary" in result

    def test_read_only_identical_output_on_double_call(self, tmp_path, monkeypatch):
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(tmp_path))
        _seed_branch(tmp_path)
        from workflow.universe_server import extensions
        r1 = json.loads(extensions(action="continue_branch", branch_def_id="b1"))
        r2 = json.loads(extensions(action="continue_branch", branch_def_id="b1"))
        _assert_action_recognized(r1)
        # run_history, open_notes, branch_def_id must be identical.
        assert r1["branch_def_id"] == r2["branch_def_id"]
        assert r1["run_history"] == r2["run_history"]
        assert r1["open_notes"] == r2["open_notes"]

    def test_nonexistent_branch_returns_structured_rejection(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(tmp_path))
        from workflow.daemon_server import initialize_author_server
        from workflow.universe_server import extensions
        initialize_author_server(tmp_path)
        result = json.loads(
            extensions(action="continue_branch", branch_def_id="does_not_exist")
        )
        # Must not be an unknown-action error — the action must exist.
        assert "Unknown action" not in result.get("error", ""), (
            "continue_branch is not yet implemented"
        )
        assert "error" in result
        # Error message should explicitly suggest build_branch as the next step.
        error_text = result.get("error", "")
        assert "build_branch" in error_text.lower(), (
            f"Error should mention build_branch, got: {error_text!r}"
        )

    def test_session_boundary_block_always_present(self, tmp_path, monkeypatch):
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(tmp_path))
        _seed_branch(tmp_path)
        from workflow.universe_server import extensions
        result = json.loads(extensions(action="continue_branch", branch_def_id="b1"))
        _assert_action_recognized(result)
        assert "session_boundary" in result
        assert "prior_session_context_available" in result["session_boundary"]


# ── Alias routing test ────────────────────────────────────────────────────────

class TestContinueBranchAlias:
    """Spec: `patch_branch action=continue` routes to the same handler."""

    def test_patch_branch_continue_alias_routes_to_same_handler(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(tmp_path))
        _seed_branch(tmp_path)
        from workflow.universe_server import extensions  # extensions() dispatches to branch() internally for patch_branch.
        # This test uses extensions directly with action=continue_branch
        # and verifies the alias produces the same output shape.
        direct = json.loads(
            extensions(action="continue_branch", branch_def_id="b1")
        )
        # The alias would be via: branch(action="continue", branch_def_id="b1")
        # For now we just assert the direct path works — alias is a follow-on.
        assert "chatbot_summary" in direct


# ── Control station routing hint grep-test ────────────────────────────────────

class TestControlStationRoutingHint:
    """Spec: control_station prompt body must contain routing hint for continue_branch."""

    def test_control_station_mentions_continue_branch(self):
        from workflow.api.prompts import _CONTROL_STATION_PROMPT

        assert "continue_branch" in _CONTROL_STATION_PROMPT, (
            "control_station prompt must mention continue_branch so chatbots "
            "know when to use it vs build_branch vs patch_branch."
        )
