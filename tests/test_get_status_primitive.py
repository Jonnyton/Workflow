"""Tests for the #88 interim `get_status` MCP primitive.

Navigator's Devin-session1 intelligence report §T-7 introduced this
tool as the highest-ROI interim primitive unblocking tier-2
confidential-tier trust. Devin bounced at live exchange 4 because his
chatbot couldn't verify the routing promise; `get_status` is the
concrete-evidence surface that closes that System → Chatbot chain break.

Tests pin the response contract so future edits don't drop the fields
the chatbot relies on for privacy-critical narration.
"""

from __future__ import annotations

import asyncio
import json

from workflow.universe_server import get_status, mcp


def _list_tools():
    return asyncio.run(mcp.list_tools(run_middleware=False))


def test_get_status_tool_is_registered() -> None:
    """#88 must expose `get_status` as an MCP tool the chatbot can call."""
    names = {t.name for t in _list_tools()}
    assert "get_status" in names


def test_get_status_tool_is_read_only() -> None:
    """#88 must be advertised as read-only so the chatbot + gateway
    treat it as safe to call on any turn without consent gates.
    """
    tool = next(t for t in _list_tools() if t.name == "get_status")
    # FastMCP may surface ToolAnnotations via tool.annotations.
    ann = getattr(tool, "annotations", None)
    if ann is not None:
        # readOnlyHint=True pins the contract.
        assert getattr(ann, "readOnlyHint", None) is True or \
            getattr(ann, "read_only_hint", None) is True


def test_get_status_returns_required_shape() -> None:
    """Response must carry the 4 load-bearing blocks the chatbot narrates
    when answering privacy-critical questions: active_host,
    tier_routing_policy, evidence, caveats.
    """
    payload = json.loads(get_status())
    # Top-level required keys.
    for key in ("active_host", "tier_routing_policy", "evidence",
                "caveats", "universe_id"):
        assert key in payload, f"missing top-level key: {key}"

    # active_host shape.
    ah = payload["active_host"]
    assert "host_id" in ah
    assert "served_llm_type" in ah
    assert "llm_endpoint_bound" in ah

    # tier_routing_policy shape.
    trp = payload["tier_routing_policy"]
    assert "served_llm_type" in trp
    assert "accept_external_requests" in trp
    assert "accept_paid_bids" in trp
    assert "tier_status_map" in trp

    # evidence shape — each field load-bearing for chatbot trust claim.
    ev = payload["evidence"]
    assert "last_completed_request_llm_used" in ev
    assert "activity_log_tail" in ev
    assert "policy_hash" in ev

    # caveats must be a non-empty list (legacy-surface honesty).
    assert isinstance(payload["caveats"], list)
    assert len(payload["caveats"]) >= 1


def test_get_status_policy_hash_is_deterministic() -> None:
    """Chatbot uses `policy_hash` to detect config drift across calls.
    Two consecutive calls with no config change must return the same
    hash; otherwise the drift-detection contract breaks.
    """
    h1 = json.loads(get_status())["evidence"]["policy_hash"]
    h2 = json.loads(get_status())["evidence"]["policy_hash"]
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex digest length


def test_get_status_policy_hash_is_sha256_hex() -> None:
    """Hash must be lowercase-hex sha256 so chatbot can compare as a
    simple string match without parsing variants.
    """
    h = json.loads(get_status())["evidence"]["policy_hash"]
    # sha256 hex is 64 lowercase-alnum chars.
    assert all(c in "0123456789abcdef" for c in h)


def test_get_status_surfaces_honest_caveat_about_legacy_surface() -> None:
    """The legacy universe_server surface does NOT enforce per-universe
    sensitivity_tier. Chatbot must see that caveat so trust claims match
    reality (avoid Devin's 'pitch writing checks product isn't cashing'
    bounce reasoning).
    """
    caveats = json.loads(get_status())["caveats"]
    combined = " ".join(caveats).lower()
    # Explicit "does not enforce" signal.
    assert "does not enforce" in combined or "does not yet" in combined \
        or "not a local-only guarantee" in combined or \
        "not enforce" in combined


def test_get_status_never_errors_on_missing_activity_log() -> None:
    """Fresh universes have no activity.log yet. get_status must still
    return a valid response — chatbot should be able to call this on
    day one of a host install, before any requests have run.
    """
    payload = json.loads(get_status())
    # activity_log_tail can be an empty list but must be present.
    assert "activity_log_tail" in payload["evidence"]
    assert isinstance(payload["evidence"]["activity_log_tail"], list)
    # last_completed_request_llm_used defaults to "unknown" when no log.
    # (Also accept any value — chatbot only depends on field existing.)
    assert payload["evidence"]["last_completed_request_llm_used"] is not None


# ─────────────────────────────────────────────────────────────────────
# Track Q — routing-evidence fold-in (§10.7 self-auditing-tools shape).
# Adds `last_n_calls` + `evidence_caveats` + `actionable_next_steps` to
# the existing get_status response. Mirrors the dispatch_evidence
# caveat-augmentation pattern from commit 7d19f34.
# ─────────────────────────────────────────────────────────────────────


def _write_activity_log(tmp_path, lines):
    """Write `lines` to a universe's activity.log. Returns universe_id."""
    import os
    os.environ["UNIVERSE_SERVER_BASE"] = str(tmp_path)
    udir = tmp_path / "track_q_universe"
    udir.mkdir(parents=True, exist_ok=True)
    (udir / "activity.log").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    return "track_q_universe"


def test_get_status_evidence_includes_last_n_calls() -> None:
    """Track Q — evidence dict must surface `last_n_calls` as structured
    parsed entries (not just raw strings), so the chatbot can filter by
    tag without reparsing.
    """
    payload = json.loads(get_status())
    ev = payload["evidence"]
    assert "last_n_calls" in ev
    assert isinstance(ev["last_n_calls"], list)


def test_get_status_has_evidence_caveats_dict() -> None:
    """Track Q — per-field caveats keyed by evidence field name so the
    chatbot can cite only the degenerate keys when narrating."""
    payload = json.loads(get_status())
    assert "evidence_caveats" in payload
    assert isinstance(payload["evidence_caveats"], dict)


def test_get_status_has_actionable_next_steps_list() -> None:
    """Track Q — §10.7 canonical shape surfaces optional concrete next
    steps the chatbot can relay to the user."""
    payload = json.loads(get_status())
    assert "actionable_next_steps" in payload
    assert isinstance(payload["actionable_next_steps"], list)


def test_get_status_last_n_calls_parses_tagged_entries(tmp_path) -> None:
    """Track Q — tagged activity.log entries become {ts, tag, message,
    raw} dicts in last_n_calls, newest-first."""
    uid = _write_activity_log(tmp_path, [
        "[2026-04-20 10:00:00] [dispatch_guard] older entry",
        "[2026-04-20 10:05:00] [scene_write] newer entry",
    ])
    payload = json.loads(get_status(universe_id=uid))
    calls = payload["evidence"]["last_n_calls"]
    assert len(calls) == 2
    # Newest-first ordering.
    assert calls[0]["tag"] == "scene_write"
    assert calls[1]["tag"] == "dispatch_guard"
    # Structured parse, not raw strings.
    assert "ts" in calls[0] and "message" in calls[0]


def test_get_status_evidence_caveats_flag_empty_log(tmp_path) -> None:
    """Track Q — when activity.log is empty, per-field caveats must flag
    BOTH activity_log_tail AND last_n_calls as unreliable."""
    import os
    os.environ["UNIVERSE_SERVER_BASE"] = str(tmp_path)
    udir = tmp_path / "empty_universe"
    udir.mkdir(parents=True, exist_ok=True)
    payload = json.loads(get_status(universe_id="empty_universe"))
    ec = payload["evidence_caveats"]
    # No log → both evidence keys should carry caveats.
    assert "activity_log_tail" in ec
    assert "last_n_calls" in ec
    assert any("empty" in c.lower() or "missing" in c.lower()
               for c in ec["activity_log_tail"])


def test_get_status_activity_log_line_count_reflects_total(tmp_path) -> None:
    """Track Q — regression: previously reported len(activity_tail) which
    caps at 20. Must now report the true total line count so the
    chatbot's narration of 'N entries logged' is correct."""
    uid = _write_activity_log(tmp_path, [
        f"[2026-04-20 10:{i:02d}:00] [scene_write] entry {i}"
        for i in range(30)
    ])
    payload = json.loads(get_status(universe_id=uid))
    ev = payload["evidence"]
    # Total should be 30; activity_log_tail is capped at 20.
    assert ev["activity_log_line_count"] == 30
    assert len(ev["activity_log_tail"]) == 20
