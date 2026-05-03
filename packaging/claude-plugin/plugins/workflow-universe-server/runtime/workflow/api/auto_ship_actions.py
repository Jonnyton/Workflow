"""MCP action wrapper for ``workflow.auto_ship.validate_ship_request`` (PR #198 Phase 2A).

Exposes the auto-ship dry-run validator as a callable MCP action so the
loop's release_safety_gate prompt (and chatbots / canaries) can reach it
via tool. Pure-Python wrapper; no IO beyond JSON parse.

Sequencing:
- PR #223 added ``workflow/auto_ship.py`` with ``validate_ship_request`` —
  importable from Python only.
- This module exposes that function as ``extensions action=validate_ship_packet``
  with ``body_json="<coding_packet JSON>"``. Chatbots, canaries, and the
  loop's release_safety_gate prompt can now call it.
- A future loop-content PR (Mark's lane) updates change_loop_v1's
  release_safety_gate to call this action when child_keep_reject_decision=KEEP
  and emit APPROVE_AUTO_SHIP only when ``would_open_pr`` is True.

Phase 2A is wrapper only — no behavior change to any current path. The
action exists; nothing in the loop or substrate calls it yet.
"""

from __future__ import annotations

import json
from typing import Any


def _action_validate_ship_packet(kwargs: dict[str, Any]) -> str:
    """Validate a coding_packet against the auto-ship safety envelope.

    Args (passed via kwargs from the extensions dispatch):
        body_json: JSON-serialized coding_packet to validate. Required.

    Returns:
        JSON-serialized ship_decision dict. Shape per
        ``workflow.auto_ship.validate_ship_request`` docstring:
        ``{ship_status, would_open_pr, validation_result, violations,
        rollback_handle, dry_run}``.

    Errors:
        ``{"error": "..."}`` JSON when body_json missing or unparseable. Any
        validator-internal exception propagates as ``{"error": ..., "trace": ...}``
        rather than crashing the MCP request.
    """
    body_json = (kwargs.get("body_json") or "").strip()
    if not body_json:
        return json.dumps({
            "error": "body_json (the packet to validate) is required",
            "hint": (
                "Pass body_json='<coding_packet JSON>' — an object with "
                "release_gate_result, ship_class, child_keep_reject_decision, "
                "etc per docs/milestones/auto-ship-canary-v0.md §6"
            ),
        })

    try:
        packet = json.loads(body_json)
    except json.JSONDecodeError as exc:
        return json.dumps({
            "error": f"body_json is not valid JSON: {exc}",
            "hint": "Re-encode the coding_packet via json.dumps before passing.",
        })

    try:
        from workflow.auto_ship import validate_ship_request
        decision = validate_ship_request(packet)
    except Exception as exc:  # noqa: BLE001 — wrapper must not crash MCP request
        return json.dumps({
            "error": f"validate_ship_request raised: {exc}",
            "exception_class": type(exc).__name__,
        })

    return json.dumps(decision)


_AUTO_SHIP_ACTIONS: dict[str, Any] = {
    "validate_ship_packet": _action_validate_ship_packet,
}
