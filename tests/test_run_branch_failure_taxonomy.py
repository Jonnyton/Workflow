"""Tests for BUG-029: run_branch error responses include failure_class + suggested_action."""
import json
from unittest.mock import patch

import pytest

from workflow.graph_compiler import EmptyResponseError
from workflow.runs import RunOutcome
from workflow.universe_server import _classify_run_error, _classify_run_outcome_error


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

    def test_quota_exhausted_rate_limit(self):
        exc = RuntimeError("rate limit exceeded for this model")
        result = _classify_run_error(exc, "b1")
        assert result["failure_class"] == "quota_exhausted"
        assert "llm_type" in result["suggested_action"]

    def test_quota_exhausted_quota_keyword(self):
        exc = RuntimeError("quota exceeded — upgrade plan")
        result = _classify_run_error(exc, "b1")
        assert result["failure_class"] == "quota_exhausted"

    def test_permission_denied_auth_expired(self):
        exc = RuntimeError("auth expired, please renew token")
        result = _classify_run_error(exc, "b1")
        assert result["failure_class"] == "permission_denied:auth_expired"
        assert "rotate" in result["suggested_action"].lower()

    def test_permission_denied_approval_required(self):
        exc = RuntimeError("permission denied for this operation")
        result = _classify_run_error(exc, "b1")
        assert result["failure_class"] == "permission_denied:approval_required"

    def test_state_mutation_conflict_concurrent(self):
        exc = RuntimeError("concurrent modification detected on branch")
        result = _classify_run_error(exc, "b1")
        assert result["failure_class"] == "state_mutation_conflict"
        assert "get_branch" in result["suggested_action"]

    def test_state_mutation_conflict_stale(self):
        exc = RuntimeError("stale state — resource was modified externally")
        result = _classify_run_error(exc, "b1")
        assert result["failure_class"] == "state_mutation_conflict"

    def test_node_not_approved_backward_compat(self):
        exc = RuntimeError("source_code node requires approval first")
        result = _classify_run_error(exc, "b1")
        assert result["failure_class"] == "node_not_approved"

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
            patch("workflow.daemon_server.get_branch_definition", return_value=branch_dict),
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


class TestClassifyRunOutcomeError:
    """Unit tests for _classify_run_outcome_error — the async-path string classifier."""

    @pytest.mark.parametrize("error_str,expected_class,action_fragment", [
        (
            "Empty LLM response: Node 'extract_claims': LLM returned empty response — "
            "check provider availability and credentials",
            "empty_llm_response",
            "llm_type",
        ),
        (
            "Branch run timed out after 120s",
            "timeout",
            "timeout param",
        ),
        (
            "Rate limit exceeded for this API key",
            "quota_exhausted",
            "llm_type",
        ),
        # Gap 1: provider "call failed" strings (Groq/Gemini/Grok generic errors)
        (
            "Groq call failed: connection reset by peer",
            "provider_error",
            "llm_type",
        ),
        (
            "Gemini call failed: unexpected EOF",
            "provider_error",
            "llm_type",
        ),
        (
            # "server error" substring triggers provider_overloaded, not provider_error
            "Grok call failed: internal server error",
            "provider_overloaded",
            "30-60s",
        ),
        # Gap 2: Claude subprocess failure strings
        (
            "claude -p returned exit code 1 quickly -- api likely unavailable",
            "provider_subprocess_failed",
            "binary",
        ),
        (
            "claude -p crashed with windows exit code 0xc0000374"
            " — subprocess failure, applying cooldown",
            "provider_subprocess_failed",
            "binary",
        ),
        # Gap 3: model overloaded / 503
        (
            # "503" hits overload check; "rate-limited" (hyphen) does NOT match "rate limit" (space)
            "Gemini rate-limited: 503 service unavailable — model overloaded",
            "provider_overloaded",
            "30-60s",
        ),
        (
            "server error: overloaded, please retry",
            "provider_overloaded",
            "30-60s",
        ),
        (
            "503 service temporarily unavailable",
            "provider_overloaded",
            "30-60s",
        ),
        # Gap 4: context window exceeded
        (
            "maximum context length exceeded: 8192 tokens, got 12000",
            "context_length_exceeded",
            "fewer nodes",
        ),
        (
            "context_length_exceeded: prompt is too long",
            "context_length_exceeded",
            "fewer nodes",
        ),
        (
            "too many tokens in the input",
            "context_length_exceeded",
            "fewer nodes",
        ),
    ])
    def test_known_patterns(self, error_str, expected_class, action_fragment):
        result = _classify_run_outcome_error(error_str)
        assert result is not None
        fc, action = result
        assert fc == expected_class
        assert action_fragment.lower() in action.lower()

    def test_unknown_pattern_returns_none(self):
        assert _classify_run_outcome_error("some opaque internal error xyz") is None

    def test_empty_string_returns_none(self):
        assert _classify_run_outcome_error("") is None

    def test_empty_response_real_message(self):
        """Exact message from graph_compiler.py EmptyResponseError."""
        msg = (
            "Node 'extract_claims': LLM returned empty response — "
            "check provider availability and credentials"
        )
        result = _classify_run_outcome_error(f"Empty LLM response: {msg}")
        assert result is not None
        assert result[0] == "empty_llm_response"
        assert result[1]


class TestAsyncRunOutcomeEnrichment:
    """Test that _action_run_branch enriches failed RunOutcome with failure_class."""

    _BRANCH_DICT = {
        "branch_def_id": "b1", "name": "Test", "description": "",
        "author": "tester", "domain_id": "fantasy", "goal_id": "",
        "tags": [], "version": 1, "parent_def_id": "", "fork_from": None,
        "graph_nodes": [], "edges": [], "conditional_edges": [],
        "entry_point": "", "node_defs": [], "state_schema": [],
        "published": False, "visibility": "public",
        "created_at": "", "updated_at": "", "stats": {},
        "default_llm_policy": None, "concurrency_budget": None,
    }

    def _call_run_branch_with_outcome(self, outcome: RunOutcome) -> dict:
        from workflow.universe_server import _action_run_branch

        with (
            patch("workflow.daemon_server.get_branch_definition", return_value=self._BRANCH_DICT),
            patch("workflow.universe_server._base_path", return_value="/fake"),
            patch("workflow.universe_server._current_actor", return_value="tester"),
            patch("workflow.universe_server._ensure_runs_recovery"),
            patch("workflow.branches.BranchDefinition.validate", return_value=[]),
            patch("workflow.runs.execute_branch_async", return_value=outcome),
        ):
            return json.loads(_action_run_branch({"branch_def_id": "b1"}))

    def test_failed_outcome_empty_response_gets_enriched(self):
        outcome = RunOutcome(
            run_id="r1",
            status="failed",
            output={},
            error="Empty LLM response: Node 'extract_claims': LLM returned empty response — "
                  "check provider availability and credentials",
        )
        result = self._call_run_branch_with_outcome(outcome)
        assert result["failure_class"] == "empty_llm_response"
        assert result["suggested_action"]
        assert "llm_type" in result["suggested_action"]
        assert "Suggested action:" in result["text"]

    def test_failed_outcome_timeout_gets_enriched(self):
        outcome = RunOutcome(
            run_id="r2", status="failed", output={},
            error="Branch run timed out after 120s",
        )
        result = self._call_run_branch_with_outcome(outcome)
        assert result["failure_class"] == "timeout"
        assert result["suggested_action"]

    def test_successful_outcome_no_failure_class(self):
        outcome = RunOutcome(run_id="r3", status="completed", output={"result": "ok"}, error="")
        result = self._call_run_branch_with_outcome(outcome)
        assert "failure_class" not in result
        assert "suggested_action" not in result

    def test_failed_outcome_unknown_error_no_failure_class(self):
        outcome = RunOutcome(
            run_id="r4", status="failed", output={},
            error="some totally opaque internal error nobody knows about",
        )
        result = self._call_run_branch_with_outcome(outcome)
        assert "failure_class" not in result


class TestComposeRunSnapshotEnrichment:
    """Test that _compose_run_snapshot enriches failed runs with failure_class/suggested_action."""

    def _make_snapshot(self, status: str, error: str) -> dict:
        from workflow.universe_server import _compose_run_snapshot

        run_record = {
            "run_id": "r1",
            "branch_def_id": "b1",
            "status": status,
            "actor": "tester",
            "error": error,
            "started_at": None,
            "finished_at": None,
        }
        with (
            patch("workflow.daemon_server.get_branch_definition", side_effect=KeyError("b1")),
            patch("workflow.runs.build_node_status_map", return_value=[]),
            patch("workflow.universe_server._run_mermaid_from_events", return_value=""),
        ):
            return _compose_run_snapshot(run_record, [])

    def test_failed_run_empty_response_enriched(self):
        snapshot = self._make_snapshot(
            "failed",
            "Empty LLM response: Node 'extract_claims': LLM returned empty response — "
            "check provider availability and credentials",
        )
        assert snapshot["failure_class"] == "empty_llm_response"
        assert snapshot["suggested_action"]

    def test_failed_run_unknown_error_not_enriched(self):
        snapshot = self._make_snapshot("failed", "some opaque crash nobody knows")
        assert "failure_class" not in snapshot
        assert "suggested_action" not in snapshot

    def test_completed_run_not_enriched(self):
        snapshot = self._make_snapshot("completed", "")
        assert "failure_class" not in snapshot
        assert "suggested_action" not in snapshot
