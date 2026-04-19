"""Execution-side helpers for target mutations.

Execution nodes may create provisional targets directly and may mark targets
for discard, but stronger lifecycle changes still belong to review.
"""

from __future__ import annotations

import logging
from typing import Any

from domains.fantasy_daemon.work_kinds import (
    EXECUTION_KIND_BOOK,
    EXECUTION_KIND_CHAPTER,
    EXECUTION_KIND_SCENE,
)
from workflow.work_targets import (
    create_provisional_target,
    get_target,
    mark_target_for_discard,
    upsert_work_target,
)

logger = logging.getLogger(__name__)


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


def advance_work_target_on_accept(
    universe_path: str,
    target_id: str | None,
    *,
    verdict: str,
    execution_scope: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Bump a WorkTarget's positional metadata after a scene is accepted.

    Sporemarch oscillation fix (b): the root-cause complement to fix (a).
    After `commit` returns verdict="accept", the WorkTarget that produced
    this execution gets its `metadata.scene_number` (or chapter/book)
    advanced so the next universe cycle picks up a fresh coordinate
    instead of re-requesting the just-accepted one.

    Returns a trace dict on success, ``None`` on no-op or failure. Never
    raises — nodes must not crash.
    """
    if verdict != "accept":
        return None
    if not universe_path or not target_id:
        return None
    scope = dict(execution_scope or {})
    kind = str(scope.get("execution_kind", "")).strip().lower()
    if kind not in (EXECUTION_KIND_SCENE, EXECUTION_KIND_CHAPTER, EXECUTION_KIND_BOOK):
        return None

    try:
        target = get_target(universe_path, target_id)
    except Exception as exc:
        logger.warning("advance_work_target: get_target failed for %s: %s", target_id, exc)
        return None
    if target is None:
        return None

    metadata = dict(target.metadata)
    before: dict[str, Any] = {}
    after: dict[str, Any] = {}

    if kind == EXECUTION_KIND_SCENE:
        current = metadata.get("scene_number")
        if current is None:
            current = scope.get("scene_number")
        try:
            current_int = int(current) if current is not None else None
        except (TypeError, ValueError):
            current_int = None
        if current_int is None:
            return None
        before["scene_number"] = metadata.get("scene_number")
        metadata["scene_number"] = current_int + 1
        after["scene_number"] = metadata["scene_number"]
    elif kind == EXECUTION_KIND_CHAPTER:
        current = metadata.get("chapter_number") or scope.get("chapter_number")
        try:
            current_int = int(current) if current is not None else None
        except (TypeError, ValueError):
            current_int = None
        if current_int is None:
            return None
        before["chapter_number"] = metadata.get("chapter_number")
        before["scene_number"] = metadata.get("scene_number")
        metadata["chapter_number"] = current_int + 1
        metadata.pop("scene_number", None)
        after["chapter_number"] = metadata["chapter_number"]
        after["scene_number"] = None
    else:  # EXECUTION_KIND_BOOK
        current = metadata.get("book_number") or scope.get("book_number")
        try:
            current_int = int(current) if current is not None else None
        except (TypeError, ValueError):
            current_int = None
        if current_int is None:
            return None
        before["book_number"] = metadata.get("book_number")
        before["chapter_number"] = metadata.get("chapter_number")
        before["scene_number"] = metadata.get("scene_number")
        metadata["book_number"] = current_int + 1
        metadata.pop("chapter_number", None)
        metadata.pop("scene_number", None)
        after["book_number"] = metadata["book_number"]
        after["chapter_number"] = None
        after["scene_number"] = None

    target.metadata = metadata
    try:
        upsert_work_target(universe_path, target)
    except Exception as exc:
        logger.warning(
            "advance_work_target: upsert failed for %s: %s", target_id, exc,
        )
        return None

    logger.info(
        "advance_work_target: %s kind=%s before=%s after=%s",
        target_id, kind, before, after,
    )
    return {
        "node": "target_actions",
        "action": "advance_on_accept",
        "target_id": target_id,
        "execution_kind": kind,
        "before": before,
        "after": after,
    }
