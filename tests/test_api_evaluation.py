"""Task #12 — direct tests for `workflow.api.evaluation` after decomp Step 5.

The legacy test files (test_publish_version.py, test_rollback.py,
test_community_branches_phase4.py, test_branch_versions_rollback_columns.py)
reach the evaluation handlers via the `extensions` MCP tool — those tests
continue to pass through the back-compat re-export shim. This file
exercises `workflow.api.evaluation` directly to lock in the new public surface.
"""

from __future__ import annotations

import json

import pytest

from workflow.api import evaluation as eval_mod
from workflow.api.evaluation import (
    _BRANCH_VERSION_ACTIONS,
    _JUDGMENT_ACTIONS,
    _JUDGMENT_WRITE_ACTIONS,
    _action_judge_run,
    _action_publish_version,
    _split_tag_csv,
)

# ── module surface ──────────────────────────────────────────────────────────


def test_module_exposes_expected_public_names():
    """The new submodule's contract surface — guards against silent removal."""
    expected = {
        "_JUDGMENT_ACTIONS", "_JUDGMENT_WRITE_ACTIONS",
        "_dispatch_judgment_action", "_BRANCH_VERSION_ACTIONS",
        "_action_judge_run", "_action_list_judgments", "_action_compare_runs",
        "_action_suggest_node_edit", "_action_get_node_output",
        "_action_list_node_versions", "_action_rollback_node",
        "_action_publish_version", "_action_get_branch_version",
        "_action_list_branch_versions", "_split_tag_csv",
    }
    missing = expected - set(dir(eval_mod))
    assert not missing, f"evaluation.py is missing public names: {missing}"


# ── _JUDGMENT_ACTIONS dispatch table ────────────────────────────────────────


def test_judgment_actions_table_has_7_handlers():
    assert len(_JUDGMENT_ACTIONS) == 7


def test_judgment_actions_keys_are_expected_set():
    expected = {
        "judge_run", "list_judgments", "compare_runs",
        "suggest_node_edit", "get_node_output",
        "list_node_versions", "rollback_node",
    }
    assert set(_JUDGMENT_ACTIONS.keys()) == expected


def test_all_judgment_actions_are_callable():
    for action, handler in _JUDGMENT_ACTIONS.items():
        assert callable(handler), f"{action} handler is not callable"


def test_judgment_write_actions_is_subset_of_judgment_actions():
    assert _JUDGMENT_WRITE_ACTIONS <= set(_JUDGMENT_ACTIONS.keys())


def test_judgment_write_actions_has_only_state_mutators():
    """judge_run writes a judgment row; rollback_node bumps a branch version.
    Read-only actions stay out so the ledger doesn't bloat."""
    assert _JUDGMENT_WRITE_ACTIONS == {"judge_run", "rollback_node"}


def test_judgment_read_actions_are_excluded_from_write_set():
    for read_action in (
        "list_judgments", "compare_runs", "suggest_node_edit",
        "get_node_output", "list_node_versions",
    ):
        assert read_action not in _JUDGMENT_WRITE_ACTIONS


# ── _BRANCH_VERSION_ACTIONS dispatch table ──────────────────────────────────


def test_branch_version_actions_table_has_3_handlers():
    assert len(_BRANCH_VERSION_ACTIONS) == 3


def test_branch_version_actions_keys_are_expected_set():
    expected = {"publish_version", "get_branch_version", "list_branch_versions"}
    assert set(_BRANCH_VERSION_ACTIONS.keys()) == expected


def test_all_branch_version_actions_are_callable():
    for action, handler in _BRANCH_VERSION_ACTIONS.items():
        assert callable(handler), f"{action} handler is not callable"


# ── _split_tag_csv unit ─────────────────────────────────────────────────────


def test_split_tag_csv_empty_string_returns_empty_list():
    assert _split_tag_csv("") == []


def test_split_tag_csv_single_tag():
    assert _split_tag_csv("foo") == ["foo"]


def test_split_tag_csv_multiple_tags_strips_whitespace():
    assert _split_tag_csv("foo, bar , baz") == ["foo", "bar", "baz"]


def test_split_tag_csv_drops_empty_segments():
    """Sandwich blanks between separators get dropped — no empty strings."""
    assert _split_tag_csv("foo,, bar") == ["foo", "bar"]
    assert _split_tag_csv(",foo,") == ["foo"]


# ── handler error paths (no monkeypatch) ────────────────────────────────────


def test_action_judge_run_missing_run_id_returns_error():
    out = json.loads(_action_judge_run({}))
    assert "error" in out
    assert "run_id" in out["error"]


def test_action_judge_run_missing_judgment_text_returns_error():
    out = json.loads(_action_judge_run({"run_id": "r1"}))
    assert "error" in out
    assert "judgment_text" in out["error"]


def test_action_judge_run_returns_str():
    out = _action_judge_run({})
    assert isinstance(out, str)


def test_action_publish_version_missing_branch_def_id_returns_error():
    out = json.loads(_action_publish_version({}))
    assert "error" in out


# ── back-compat re-export sanity ────────────────────────────────────────────


def test_universe_server_reexports_judgment_actions():
    """Tests + extensions() rely on the universe_server re-exports."""
    from workflow import universe_server as us
    assert us._JUDGMENT_ACTIONS is _JUDGMENT_ACTIONS
    assert us._BRANCH_VERSION_ACTIONS is _BRANCH_VERSION_ACTIONS
    assert us._JUDGMENT_WRITE_ACTIONS is _JUDGMENT_WRITE_ACTIONS


@pytest.mark.parametrize("name", [
    "_JUDGMENT_ACTIONS", "_JUDGMENT_WRITE_ACTIONS",
    "_dispatch_judgment_action", "_BRANCH_VERSION_ACTIONS",
    "_action_judge_run", "_action_list_judgments", "_action_compare_runs",
    "_action_suggest_node_edit", "_action_get_node_output",
    "_action_list_node_versions", "_action_rollback_node",
    "_action_publish_version", "_action_get_branch_version",
    "_action_list_branch_versions", "_split_tag_csv",
])
def test_universe_server_reexport_identity(name):
    """Every re-exported name in universe_server is the same object as in
    evaluation."""
    from workflow import universe_server as us
    assert getattr(us, name) is getattr(eval_mod, name), (
        f"universe_server.{name} is not the same object as evaluation.{name}"
    )
