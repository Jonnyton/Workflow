"""Task #11 — direct tests for `workflow.api.runs` after decomp Step 4.

The legacy test files (test_run_branch_failure_taxonomy.py,
test_query_runs.py, test_run_branch_version.py, test_canonical_branch_mcp.py)
import via `workflow.universe_server` and continue to pass through the
back-compat re-export shim. This file exercises `workflow.api.runs`
directly to lock in the new public surface.
"""

from __future__ import annotations

import json

import pytest

from workflow.api import runs as runs_mod
from workflow.api.runs import (
    _FAILURE_TAXONOMY,
    _RUN_ACTIONS,
    _RUN_WRITE_ACTIONS,
    _action_run_branch,
    _actionable_by,
    _build_failure_taxonomy,
    _classify_run_error,
    _classify_run_outcome_error,
    _ensure_runs_recovery,
    _failure_payload,
)

# ── module surface ──────────────────────────────────────────────────────────


def test_module_exposes_expected_public_names():
    """The new submodule's contract surface — guards against silent removal."""
    expected = {
        "_RUN_ACTIONS", "_RUN_WRITE_ACTIONS", "_dispatch_run_action",
        "_action_run_branch", "_action_get_run", "_action_list_runs",
        "_action_stream_run", "_action_wait_for_run", "_action_cancel_run",
        "_action_get_run_output", "_action_resume_run",
        "_action_estimate_run_cost", "_action_query_runs",
        "_action_run_routing_evidence", "_action_get_memory_scope_status",
        "_action_run_branch_version", "_action_rollback_merge",
        "_action_get_rollback_history",
        "_classify_run_error", "_classify_run_outcome_error",
        "_actionable_by", "_failure_payload",
        "_ensure_runs_recovery", "_build_failure_taxonomy",
        "_FAILURE_TAXONOMY",
        "_run_mermaid_from_events", "_branch_name_for_run",
        "_compose_run_snapshot",
    }
    missing = expected - set(dir(runs_mod))
    assert not missing, f"runs.py is missing public names: {missing}"


# ── _RUN_ACTIONS dispatch table ─────────────────────────────────────────────


def test_run_actions_table_has_15_handlers():
    assert len(_RUN_ACTIONS) == 15


def test_run_actions_table_keys_are_expected_set():
    expected = {
        "run_branch", "run_branch_version", "get_run", "list_runs",
        "stream_run", "wait_for_run", "cancel_run", "get_run_output",
        "resume_run", "estimate_run_cost", "query_runs",
        "get_routing_evidence", "get_memory_scope_status",
        "rollback_merge", "get_rollback_history",
    }
    assert set(_RUN_ACTIONS.keys()) == expected


def test_all_run_actions_are_callable():
    for action, handler in _RUN_ACTIONS.items():
        assert callable(handler), f"{action} handler is not callable"


def test_run_write_actions_is_subset_of_run_actions():
    assert _RUN_WRITE_ACTIONS <= set(_RUN_ACTIONS.keys())


def test_run_write_actions_includes_state_mutators():
    """State-mutating actions must be in the write-set so the ledger captures them."""
    assert "run_branch" in _RUN_WRITE_ACTIONS
    assert "cancel_run" in _RUN_WRITE_ACTIONS
    assert "resume_run" in _RUN_WRITE_ACTIONS
    assert "rollback_merge" in _RUN_WRITE_ACTIONS
    assert "run_branch_version" in _RUN_WRITE_ACTIONS


def test_run_write_actions_excludes_read_actions():
    """Read actions stay out of the ledger to avoid log spam."""
    for read_action in (
        "get_run", "list_runs", "stream_run", "wait_for_run",
        "get_run_output", "estimate_run_cost", "query_runs",
        "get_routing_evidence", "get_memory_scope_status",
        "get_rollback_history",
    ):
        assert read_action not in _RUN_WRITE_ACTIONS


# ── failure taxonomy ────────────────────────────────────────────────────────


def test_build_failure_taxonomy_returns_list_of_triples():
    """Each entry is (exc_type, failure_class_str, suggested_action_str)."""
    table = _build_failure_taxonomy()
    assert table, "taxonomy is empty"
    for entry in table:
        assert len(entry) == 3
        exc_type, failure_class, suggested_action = entry
        assert isinstance(exc_type, type)
        assert isinstance(failure_class, str)
        assert isinstance(suggested_action, str)


def test_build_failure_taxonomy_returns_equal_content_across_calls():
    """Multiple calls produce equal-content taxonomies (deterministic build)."""
    a = _build_failure_taxonomy()
    b = _build_failure_taxonomy()
    assert a == b


def test_failure_taxonomy_module_state_is_list():
    """Module-level _FAILURE_TAXONOMY is a list (legacy state guard slot)."""
    assert isinstance(_FAILURE_TAXONOMY, list)


def test_classify_run_error_unknown_falls_back_to_unknown_class():
    """A bare Exception not in the taxonomy returns the unknown-failure shape."""
    out = _classify_run_error(Exception("totally unique nonsense xyzzy"), "b1")
    assert out["status"] == "error"
    assert out["failure_class"] == "unknown"
    assert "actionable_by" in out
    assert "suggested_action" in out


def test_classify_run_error_returns_dict_shape():
    out = _classify_run_error(RuntimeError("x"), "b1")
    assert isinstance(out, dict)
    assert {"status", "failure_class", "actionable_by",
            "suggested_action"} <= set(out.keys())


def test_classify_run_outcome_error_returns_none_when_no_match():
    """An unrecognized outcome.error string returns None."""
    assert _classify_run_outcome_error("totally unknown error string xyzzy") is None


def test_classify_run_outcome_error_returns_none_for_empty():
    assert _classify_run_outcome_error("") is None


def test_actionable_by_returns_string():
    """Any failure_class — known or unknown — yields a string actor."""
    for cls in ("unknown", "empty_llm_response", "recursion_limit",
                "totally_unknown_class_xyzzy"):
        result = _actionable_by(cls)
        assert isinstance(result, str)
        assert result  # non-empty


def test_failure_payload_shape():
    """Direct unit on _failure_payload — used by _classify_run_error."""
    out = _failure_payload(RuntimeError("oops"), "test_class", "do something")
    assert out["status"] == "error"
    assert out["failure_class"] == "test_class"
    assert out["suggested_action"] == "do something"
    assert "actionable_by" in out
    assert "oops" in out["error"]
    assert out["error"].startswith("Run failed:")


# ── _ensure_runs_recovery idempotency ───────────────────────────────────────


def test_ensure_runs_recovery_is_idempotent():
    """Multiple calls don't re-run the recovery sweep."""
    _ensure_runs_recovery()
    _ensure_runs_recovery()  # second call must not raise


# ── handler error path (no-monkeypatch path) ────────────────────────────────


def test_action_run_branch_missing_branch_def_id_returns_error():
    """The dispatch entry returns a JSON error when branch_def_id is empty."""
    out = json.loads(_action_run_branch({}))
    assert "error" in out
    assert "branch_def_id" in out["error"]


def test_action_run_branch_returns_str():
    out = _action_run_branch({})
    assert isinstance(out, str)


def test_action_run_branch_rejects_node_state_key_collision(tmp_path, monkeypatch):
    from workflow.branches import (
        BranchDefinition,
        EdgeDefinition,
        GraphNodeRef,
        NodeDefinition,
    )
    from workflow.daemon_server import initialize_author_server, save_branch_definition

    monkeypatch.setattr(runs_mod, "_base_path", lambda: tmp_path)
    initialize_author_server(tmp_path)

    branch = BranchDefinition(
        name="change_loop_v1 repro",
        entry_point="investigation_gate",
    )
    branch.node_defs = [
        NodeDefinition(
            node_id="investigation_gate",
            display_name="Investigation Gate",
            prompt_template="decide next step",
        )
    ]
    branch.graph_nodes = [
        GraphNodeRef(
            id="investigation_gate",
            node_def_id="investigation_gate",
            position=0,
        )
    ]
    branch.edges = [
        EdgeDefinition(from_node="START", to_node="investigation_gate"),
        EdgeDefinition(from_node="investigation_gate", to_node="END"),
    ]
    branch.state_schema = [{"name": "investigation_gate", "type": "str"}]
    saved = save_branch_definition(tmp_path, branch_def=branch.to_dict())

    out = json.loads(_action_run_branch({"branch_def_id": saved["branch_def_id"]}))

    assert "run_id" not in out
    assert out["error"] == "Branch is not valid. Fix these before running:"
    assert out["validation_errors"] == [
        "Node ID 'investigation_gate' conflicts with state field name "
        "'investigation_gate'. Rename either the node or the state field "
        "before running."
    ]


# Arc A re-export shims removed in Task #18 retarget sweep — the
# `test_universe_server_reexports_run_actions` + parametrized identity tests
# are gone alongside the shim block.
