"""Tests for exposing `conditional_edges` on build_branch + patch_branch.

STATUS.md Approved-bugs 2026-04-22 — the MCP surface now reads and
patches `conditional_edges`, closing the half-built feature. Schema
and validator already existed; this wires the ingress + patch ops.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def branch_env(tmp_path, monkeypatch):
    monkeypatch.setenv("UNIVERSE_SERVER_BASE", str(tmp_path))
    monkeypatch.setenv("UNIVERSE_SERVER_USER", "tester")

    from workflow import universe_server as us

    importlib.reload(us)
    yield us, Path(tmp_path)
    importlib.reload(us)


def _call(us, action, **kwargs):
    return json.loads(us.extensions(action=action, **kwargs))


def _conditional_edges(got: dict) -> list:
    """Pull conditional_edges out of a get_branch response.

    Storage nests them under ``graph.conditional_edges`` (graph_json in
    sqlite) — the reader does not surface them at top level.
    """
    return got.get("graph", {}).get("conditional_edges", [])


def _three_node_spec() -> dict:
    """Baseline valid 2-node branch (router→leaf→END). Tests that
    exercise patch ops mutate this baseline — they add ``right``
    first via add_node before the conditional edge patch."""
    return {
        "name": "Router",
        "node_defs": [
            {"node_id": "router", "display_name": "Router",
             "prompt_template": "decide"},
            {"node_id": "left", "display_name": "Left",
             "prompt_template": "L"},
        ],
        "edges": [
            {"from": "router", "to": "left"},
            {"from": "left", "to": "END"},
        ],
        "entry_point": "router",
    }


def _router_spec_no_regular_edges() -> dict:
    """Spec for tests that supply conditional_edges in the build itself."""
    return {
        "name": "Router",
        "node_defs": [
            {"node_id": "router", "display_name": "Router",
             "prompt_template": "decide"},
            {"node_id": "left", "display_name": "Left",
             "prompt_template": "L"},
            {"node_id": "right", "display_name": "Right",
             "prompt_template": "R"},
        ],
        "edges": [
            {"from": "left", "to": "END"},
            {"from": "right", "to": "END"},
        ],
        "entry_point": "router",
    }


def test_build_branch_accepts_conditional_edges(branch_env):
    us, _ = branch_env
    spec = _router_spec_no_regular_edges()
    spec["conditional_edges"] = [
        {"from": "router", "conditions": {"a": "left", "b": "right"}},
    ]
    result = _call(us, "build_branch", spec_json=json.dumps(spec))
    assert result["status"] == "built", result
    bid = result["branch_def_id"]

    got = _call(us, "get_branch", branch_def_id=bid)
    assert _conditional_edges(got) == [
        {"from": "router", "conditions": {"a": "left", "b": "right"}}
    ]


def test_patch_branch_add_conditional_edge_appends(branch_env):
    us, _ = branch_env
    result = _call(
        us, "build_branch", spec_json=json.dumps(_three_node_spec()),
    )
    assert result["status"] == "built", result
    bid = result["branch_def_id"]

    # Add a second leaf + conditional branching in one transaction.
    patch_result = _call(
        us, "patch_branch",
        branch_def_id=bid,
        changes_json=json.dumps([
            {"op": "add_node", "node_id": "right", "display_name": "Right",
             "prompt_template": "R"},
            {"op": "add_edge", "from": "right", "to": "END"},
            {"op": "add_conditional_edge",
             "from": "router",
             "conditions": {"a": "left", "b": "right"}},
        ]),
    )
    assert patch_result.get("status") == "patched", patch_result

    got = _call(us, "get_branch", branch_def_id=bid)
    assert _conditional_edges(got) == [
        {"from": "router", "conditions": {"a": "left", "b": "right"}}
    ]


def test_patch_remove_conditional_edge_with_outcome_removes_mapping(branch_env):
    us, _ = branch_env
    spec = _router_spec_no_regular_edges()
    spec["conditional_edges"] = [
        {"from": "router", "conditions": {"a": "left", "b": "right"}},
    ]
    bid = _call(us, "build_branch",
                spec_json=json.dumps(spec))["branch_def_id"]

    _call(
        us, "patch_branch",
        branch_def_id=bid,
        changes_json=json.dumps([{
            "op": "remove_conditional_edge",
            "from": "router",
            "outcome": "a",
        }]),
    )

    got = _call(us, "get_branch", branch_def_id=bid)
    assert _conditional_edges(got) == [
        {"from": "router", "conditions": {"b": "right"}}
    ]


def test_patch_remove_conditional_edge_without_outcome_removes_entire_edge(
    branch_env,
):
    us, _ = branch_env
    spec = _router_spec_no_regular_edges()
    spec["conditional_edges"] = [
        {"from": "router", "conditions": {"a": "left", "b": "right"}},
    ]
    bid = _call(us, "build_branch",
                spec_json=json.dumps(spec))["branch_def_id"]

    _call(
        us, "patch_branch",
        branch_def_id=bid,
        changes_json=json.dumps([{
            "op": "remove_conditional_edge",
            "from": "router",
        }]),
    )

    got = _call(us, "get_branch", branch_def_id=bid)
    assert _conditional_edges(got) == []


def test_validation_rejects_conditional_edge_referencing_nonexistent_node(
    branch_env,
):
    us, _ = branch_env
    spec = _router_spec_no_regular_edges()
    spec["conditional_edges"] = [
        {"from": "router", "conditions": {"a": "ghost_target"}},
    ]
    result = _call(us, "build_branch", spec_json=json.dumps(spec))
    # build_branch runs validation post-apply and rejects.
    assert result["status"] == "rejected"
    errors = result.get("errors") or []
    assert any("ghost_target" in e for e in errors), errors


def test_patch_rejects_empty_conditions_dict(branch_env):
    us, _ = branch_env
    built = _call(us, "build_branch",
                  spec_json=json.dumps(_three_node_spec()))
    bid = built["branch_def_id"]

    result = _call(
        us, "patch_branch",
        branch_def_id=bid,
        changes_json=json.dumps([{
            "op": "add_conditional_edge",
            "from": "router",
            "conditions": {},
        }]),
    )
    assert result.get("status") != "patched"
    assert "conditions" in json.dumps(result).lower()


def test_add_conditional_edge_twice_merges_outcomes(branch_env):
    """Adding outcomes one at a time merges onto the existing edge.

    Callers often add outcomes incrementally. We keep one
    ConditionalEdge per `from` node and merge new outcomes in, so the
    stored shape mirrors LangGraph's routing semantics (one router → one
    edge bundle).
    """
    us, _ = branch_env
    bid = _call(us, "build_branch",
                spec_json=json.dumps(_three_node_spec()))["branch_def_id"]

    # Add a second leaf so both outcomes resolve.
    _call(
        us, "patch_branch", branch_def_id=bid,
        changes_json=json.dumps([
            {"op": "add_node", "node_id": "right", "display_name": "Right",
             "prompt_template": "R"},
            {"op": "add_edge", "from": "right", "to": "END"},
            {"op": "add_conditional_edge",
             "from": "router",
             "conditions": {"a": "left"}},
        ]),
    )
    _call(
        us, "patch_branch", branch_def_id=bid,
        changes_json=json.dumps([{
            "op": "add_conditional_edge",
            "from": "router",
            "conditions": {"b": "right"},
        }]),
    )

    got = _call(us, "get_branch", branch_def_id=bid)
    assert _conditional_edges(got) == [
        {"from": "router", "conditions": {"a": "left", "b": "right"}}
    ]


def test_remove_conditional_edge_missing_outcome_errors(branch_env):
    us, _ = branch_env
    spec = _router_spec_no_regular_edges()
    spec["conditional_edges"] = [
        {"from": "router", "conditions": {"a": "left"}},
    ]
    bid = _call(us, "build_branch",
                spec_json=json.dumps(spec))["branch_def_id"]

    result = _call(
        us, "patch_branch",
        branch_def_id=bid,
        changes_json=json.dumps([{
            "op": "remove_conditional_edge",
            "from": "router",
            "outcome": "does_not_exist",
        }]),
    )
    assert result.get("status") != "patched"
    assert "does_not_exist" in json.dumps(result)


def test_remove_conditional_edge_missing_from_errors(branch_env):
    us, _ = branch_env
    bid = _call(us, "build_branch",
                spec_json=json.dumps(_three_node_spec()))["branch_def_id"]

    result = _call(
        us, "patch_branch",
        branch_def_id=bid,
        changes_json=json.dumps([{
            "op": "remove_conditional_edge",
            "from": "router",
        }]),
    )
    assert result.get("status") != "patched"
