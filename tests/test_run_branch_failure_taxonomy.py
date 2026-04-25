"""Tests for BUG-029: run_branch error responses include failure_class + suggested_action."""
import json
from unittest.mock import patch

from workflow.graph_compiler import EmptyResponseError
from workflow.universe_server import _classify_run_error


class TestClassifyRunError:
    def test_empty_response_error_class(self):
        exc = EmptyResponseError("node x returned empty string")
        result = _classify_run_error(exc, "b1")
        assert result["failure_class"] == "empty_llm_response"
        assert result["suggested_action"]
        assert result["status"] == "error"

    def test_recursion_error_class(self):
        exc = RecursionError("maximum recursion depth exceeded")
        result = _classify_run_error(exc, "b1")
        assert result["failure_class"] == "recursion_limit"
        assert "recursion_limit_override" in result["suggested_action"]

    def test_timeout_error_class(self):
        exc = TimeoutError("operation timed out")
        result = _classify_run_error(exc, "b1")
        assert result["failure_class"] == "timeout"
        assert result["suggested_action"]

    def test_provider_keyword_in_message(self):
        exc = RuntimeError("provider ANTHROPIC_API_KEY not set")
        result = _classify_run_error(exc, "b1")
        assert result["failure_class"] == "provider_unavailable"
        assert "keys" in result["suggested_action"].lower()

    def test_approval_keyword_in_message(self):
        exc = RuntimeError("source_code node requires approval")
        result = _classify_run_error(exc, "b1")
        assert result["failure_class"] == "node_not_approved"
        assert "approve_source_code" in result["suggested_action"]

    def test_unknown_exception_class(self):
        exc = ValueError("some unknown internal error")
        result = _classify_run_error(exc, "b1")
        assert result["failure_class"] == "unknown"
        assert "get_run" in result["suggested_action"]

    def test_error_message_always_present(self):
        """All failure classes include the original error message."""
        for exc in [
            EmptyResponseError("x"),
            RecursionError("y"),
            TimeoutError("z"),
            ValueError("w"),
        ]:
            result = _classify_run_error(exc, "b1")
            assert "Run failed:" in result["error"]


class TestRunBranchTaxonomyIntegration:
    """Integration tests: mock execute_branch_async to raise, verify MCP response shape."""

    def _call_run_branch(self, exc_to_raise):
        from workflow.universe_server import _action_run_branch

        branch_dict = {
            "branch_def_id": "b1", "name": "Test", "description": "",
            "author": "tester", "domain_id": "fantasy", "goal_id": "",
            "tags": [], "version": 1, "parent_def_id": "", "fork_from": None,
            "graph_nodes": [], "edges": [], "conditional_edges": [],
            "entry_point": "", "node_defs": [], "state_schema": [],
            "published": False, "visibility": "public",
            "created_at": "", "updated_at": "", "stats": {},
            "default_llm_policy": None, "concurrency_budget": None,
        }

        def raise_exc(*a, **kw):
            raise exc_to_raise

        with (
            patch("workflow.author_server.get_branch_definition", return_value=branch_dict),
            patch("workflow.universe_server._base_path", return_value="/fake"),
            patch("workflow.universe_server._current_actor", return_value="tester"),
            patch("workflow.universe_server._ensure_runs_recovery"),
            patch("workflow.branches.BranchDefinition.validate", return_value=[]),
            patch("workflow.runs.execute_branch_async", side_effect=raise_exc),
        ):
            return json.loads(_action_run_branch({"branch_def_id": "b1"}))

    def test_empty_response_error_surfaces_in_mcp(self):
        result = self._call_run_branch(EmptyResponseError("empty"))
        assert result["failure_class"] == "empty_llm_response"
        assert result["suggested_action"]
        assert result["status"] == "error"

    def test_recursion_error_surfaces_in_mcp(self):
        result = self._call_run_branch(RecursionError("too deep"))
        assert result["failure_class"] == "recursion_limit"

    def test_unknown_error_surfaces_in_mcp(self):
        result = self._call_run_branch(RuntimeError("some mystery error"))
        assert result["failure_class"] in ("unknown", "provider_unavailable", "node_not_approved")
        assert result["suggested_action"]
