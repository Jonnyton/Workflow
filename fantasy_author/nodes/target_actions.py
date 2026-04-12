"""Execution-side helpers for target mutations.

Execution nodes may create provisional targets directly and may mark targets
for discard, but stronger lifecycle changes still belong to review.
"""

from __future__ import annotations

from typing import Any

from fantasy_author.work_targets import (
    create_provisional_target,
    mark_target_for_discard,
)


def create_provisional_target_from_execution(
    state: dict[str, Any],
    *,
    title: str,
    current_intent: str = "",
    home_target_id: str | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a provisional publishable target from an execution step."""
    universe_path = state.get("_universe_path", state.get("universe_path", ""))
    if not universe_path:
        return {"created_target_ids": [], "quality_trace": []}

    target = create_provisional_target(
        universe_path,
        title=title,
        home_target_id=home_target_id,
        current_intent=current_intent,
        tags=tags,
        metadata=metadata,
    )
    return {
        "created_target_ids": [target.target_id],
        "quality_trace": [{
            "node": "target_actions",
            "action": "create_provisional_target",
            "target_id": target.target_id,
            "title": title,
        }],
    }


def mark_target_for_discard_from_execution(
    state: dict[str, Any],
    *,
    target_id: str,
    reason: str = "",
) -> dict[str, Any]:
    """Mark a target for discard from an execution step.

    Execution never performs true discard directly; it only records the mark.
    """
    universe_path = state.get("_universe_path", state.get("universe_path", ""))
    review_cycle = int(state.get("health", {}).get("review_cycles_completed", 0))
    if not universe_path:
        return {"marked_for_discard": [], "quality_trace": []}

    target = mark_target_for_discard(
        universe_path,
        target_id,
        review_cycle=review_cycle,
        reason=reason,
    )
    if target is None:
        return {"marked_for_discard": [], "quality_trace": []}
    return {
        "marked_for_discard": [target.target_id],
        "quality_trace": [{
            "node": "target_actions",
            "action": "mark_for_discard",
            "target_id": target.target_id,
            "reason": reason,
        }],
    }
