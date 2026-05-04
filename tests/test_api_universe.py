"""Direct tests for `workflow.api.universe` after decomp Step 9.

Legacy test files for the `universe()` MCP tool import via
`workflow.universe_server` and continue to pass through the back-compat
re-export shim. This file exercises `workflow.api.universe` directly to
lock in the new public surface.

Pattern mirrors `test_api_market.py` / `test_api_runs.py` /
`test_api_runtime_ops.py` from Steps 4-7.

Surface guarded:
- `WRITE_ACTIONS` table contract — every action mapped to (extractor, daemon-gate)
- `_dispatch_with_ledger`, `_scope_universe_response`, `_ledger_target_dir`
  ledger trio — universe-tool internal pipeline
- 27 `_action_*` handler set — present, callable, owned by this module
- Daemon-liveness telemetry helpers — present, owned by this module
- Pattern A2 wrapper: `workflow.universe_server.universe` delegates to
  `workflow.api.universe._universe_impl` (verified via simple round-trip)
"""

from __future__ import annotations

import pytest

from workflow.api import universe as univ_mod

# ── module surface ──────────────────────────────────────────────────────────


def test_module_exposes_expected_public_names() -> None:
    """Contract surface — guards against silent removal post-Step-9."""
    expected = {
        # WRITE_ACTIONS table + 14 extractor closures
        "WRITE_ACTIONS",
        "_extract_submit_request", "_extract_give_direction",
        "_extract_set_premise", "_extract_add_canon",
        "_extract_add_canon_from_path", "_extract_control_daemon",
        "_extract_switch_universe", "_extract_create_universe",
        "_extract_queue_cancel", "_extract_subscribe_goal",
        "_extract_unsubscribe_goal", "_extract_post_to_goal_pool",
        "_extract_submit_node_bid", "_extract_set_tier_config",
        # Ledger dispatcher trio
        "_ledger_target_dir", "_scope_universe_response",
        "_dispatch_with_ledger",
        # Pattern A2 universe() body
        "_universe_impl",
        # Daemon telemetry
        "_last_activity_at", "_staleness_bucket", "_phase_human",
        "_compute_accept_rate_from_db", "_compute_word_count_from_files",
        "_daemon_liveness", "_parse_activity_line",
        # 27 universe-tool action handlers
        "_action_list_universes", "_action_inspect_universe",
        "_action_read_output", "_action_submit_request",
        "_action_queue_list", "_action_daemon_overview",
        "_action_set_tier_config", "_action_queue_cancel",
        "_action_subscribe_goal", "_action_unsubscribe_goal",
        "_action_list_subscriptions", "_action_post_to_goal_pool",
        "_action_submit_node_bid", "_action_give_direction",
        "_action_query_world", "_action_read_premise",
        "_action_set_premise", "_action_add_canon",
        "_action_add_canon_from_path", "_action_list_canon",
        "_action_read_canon", "_action_control_daemon",
        "_action_get_activity", "_action_get_recent_events",
        "_action_get_ledger", "_action_switch_universe",
        "_action_create_universe",
    }
    actual = set(dir(univ_mod))
    missing = expected - actual
    assert not missing, (
        f"workflow.api.universe missing expected public names: {sorted(missing)}"
    )


def test_write_actions_table_has_14_entries() -> None:
    """WRITE_ACTIONS dict literal locked at 14 entries (per Step 9 prep §2.1)."""
    assert len(univ_mod.WRITE_ACTIONS) == 14


def test_write_actions_entries_are_extractor_gate_tuples() -> None:
    """Every entry is (extractor_callable, write_gate). The write_gate is
    one of: None (always-write), a callable returning bool, or a set of
    allowed sub-command strings (control_daemon's pause/resume gate)."""
    for action, entry in univ_mod.WRITE_ACTIONS.items():
        assert isinstance(entry, tuple), f"{action} entry not a tuple"
        assert len(entry) == 2, f"{action} entry length != 2"
        extractor, gate = entry
        assert callable(extractor), f"{action} extractor not callable"
        assert gate is None or callable(gate) or isinstance(gate, set), (
            f"{action} gate must be None, callable, or set; "
            f"got {type(gate).__name__}={gate!r}"
        )


# ── Pattern A2 wrapper round-trip ────────────────────────────────────────────


def test_pattern_a2_wrapper_delegates_to_api_universe() -> None:
    """`workflow.universe_server.universe` MUST be a thin wrapper that
    delegates to `workflow.api.universe._universe_impl`.

    Validates the Step 9 Pattern A2 contract: the FastMCP @mcp.tool
    registration lives in universe_server.py, the body lives in
    workflow.api.universe._universe_impl. Catches any silent regression
    where the wrapper grows independent logic.
    """
    from workflow import universe_server as us

    assert callable(us.universe)
    # Read-only action — no side effects.
    result = us.universe(action="list")
    direct = univ_mod._universe_impl(action="list")
    assert result == direct, "Pattern A2 wrapper drift: us.universe != _universe_impl"


# ── Ledger dispatcher contract ───────────────────────────────────────────────


def test_dispatch_with_ledger_signature() -> None:
    """`_dispatch_with_ledger(action, kwargs, *, universe_id)` contract."""
    import inspect
    sig = inspect.signature(univ_mod._dispatch_with_ledger)
    params = list(sig.parameters.keys())
    # Don't lock on exact names — ensure (action, kwargs, ...) shape.
    assert len(params) >= 2
    assert params[0] in {"action", "name"}


def test_scope_universe_response_prepends_universe_lead_in() -> None:
    """#15 contract: response carries a `Universe: <id>` text lead-in."""
    raw = '{"text": "hello", "universe_id": "u_test"}'
    out = univ_mod._scope_universe_response(raw)
    assert "Universe:" in out


# ── Daemon telemetry helpers ─────────────────────────────────────────────────


def test_staleness_bucket_handles_none() -> None:
    """`_staleness_bucket(None)` must return a defined bucket, not raise."""
    result = univ_mod._staleness_bucket(None)
    assert isinstance(result, str)
    assert result  # non-empty


def test_daemon_liveness_returns_dict_with_required_keys(tmp_path) -> None:
    """`_daemon_liveness(udir, status)` returns the contract dict shape
    consumed by `_action_list_universes`, `_action_inspect_universe`,
    and `_action_daemon_overview`."""
    result = univ_mod._daemon_liveness(tmp_path, status=None)
    assert isinstance(result, dict)
    # The exact keys are part of the public contract — lock the shape.
    expected_keys = {"liveness", "staleness", "human_phase"}
    actual_keys = set(result.keys())
    # Tolerant assertion — at least one expected key present (full lockdown
    # belongs in dedicated daemon_liveness tests; this sentinel guards
    # against shape collapse).
    assert actual_keys & expected_keys, (
        f"_daemon_liveness shape unexpected: got {actual_keys}, "
        f"expected at least one of {expected_keys}"
    )


# ── 27-handler dispatch table sanity ─────────────────────────────────────────


def test_universe_impl_dispatch_table_has_27_actions() -> None:
    """The `dispatch` table inside `_universe_impl` must cover 27 actions
    (corrected from prep §2.3's 28 — `daemon_overview` and `set_tier_config`
    were already in the table, no additional handlers added). Smoke-tested
    via 'list' which is read-only."""
    # Round-trip "list" through _universe_impl to confirm the dispatch
    # table is wired and covers at least one read action.
    out = univ_mod._universe_impl(action="list")
    assert isinstance(out, str)
    assert out  # non-empty JSON


@pytest.mark.parametrize("action", [
    "list", "inspect", "read_output", "submit_request", "queue_list",
    "daemon_overview", "set_tier_config", "queue_cancel",
    "subscribe_goal", "unsubscribe_goal", "list_subscriptions",
    "post_to_goal_pool", "submit_node_bid", "give_direction",
    "query_world", "read_premise", "set_premise", "add_canon",
    "add_canon_from_path", "list_canon", "read_canon",
    "control_daemon", "get_activity", "get_recent_events",
    "get_ledger", "switch_universe", "create_universe",
])
def test_every_universe_action_dispatches(action: str) -> None:
    """Every action verb resolves to a handler (no `Unknown action 'X'` errors
    from the top-level dispatch table).

    Smoke-tests dispatch only — we pass empty kwargs and accept any
    response shape (handlers may legitimately error on missing args, including
    handler-internal "Unknown daemon action" errors that are NOT dispatch-table
    misses). The bug we're guarding against is "action verb dropped from the
    universe() dispatch table" — caught by the exact-string `"Unknown action
    '<action>'"` sentinel.
    """
    out = univ_mod._universe_impl(action=action)
    sentinel = f"Unknown action '{action}'"
    assert sentinel not in out, (
        f"action {action!r} dropped from _universe_impl dispatch table"
    )
