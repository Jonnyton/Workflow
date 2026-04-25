#!/usr/bin/env python3
"""Block Agent spawns on non-latest models.

Project rule (host directive 2026-04-25): every Agent / teammate spawn must
use the latest available model. Today that is Opus 4.7 (`opus` family alias
or `claude-opus-4-7` model id). Non-latest models doing project work is a
safety hazard and treated as an emergency.

Hook contract: PreToolUse with matcher Agent. Receives the tool call JSON
on stdin. If `tool_input.model` is set and NOT in the latest-allowed set,
emit a PermissionDecision=deny with reason. If unset, allow (the spawned
agent inherits the lead's model, which is also Opus).
"""

from __future__ import annotations

import json
import sys

LATEST_ALLOWED = {"opus"}
LATEST_PREFIXES = ("claude-opus-",)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    if payload.get("tool_name") != "Agent":
        return 0

    tool_input = payload.get("tool_input") or {}
    model = tool_input.get("model")

    if model is None:
        return 0  # inherits lead model (Opus); allow

    model_lc = str(model).strip().lower()
    if model_lc in LATEST_ALLOWED:
        return 0
    if any(model_lc.startswith(p) for p in LATEST_PREFIXES):
        return 0

    deny = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"Latest-model rule violation: Agent spawn requested model='{model}'. "
                "Project rule (host directive 2026-04-25): every spawn MUST use the "
                "latest model (`opus` today). Non-latest models doing project work is "
                "a safety hazard. Re-spawn with model='opus' (or omit the model field "
                "to inherit the lead's Opus). See "
                "feedback_always_latest_model.md."
            ),
        },
        "systemMessage": (
            "BLOCKED Agent spawn on non-latest model "
            f"({model!r}). Use model='opus'."
        ),
    }
    print(json.dumps(deny))
    return 0


if __name__ == "__main__":
    sys.exit(main())
