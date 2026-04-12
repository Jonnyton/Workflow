"""Universe-cycle node -- end-of-cycle maintenance.

Updates health metrics, calls MemoryManager cleanup, and clears the
completed execution. The daemon loops indefinitely; stopping is driven
externally (API stop, SIGINT, .pause file), not by this node.

Contract
--------
Input:  UniverseState after a task (write/worldbuild/reflect) completes.
Output: Partial UniverseState with updated health and counters.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def universe_cycle(state: dict[str, Any]) -> dict[str, Any]:
    """Perform end-of-cycle maintenance for the universe daemon.

    1. Update health metrics (total_words, total_chapters).
    2. Call MemoryManager cleanup (evict old data) if available.
    3. Clear the completed execution and compatibility queue.
    4. Log a cycle summary to quality_trace.

    The daemon loops continuously; stopping is driven externally
    (API stop, SIGINT, .pause file), not by queue exhaustion.

    Parameters
    ----------
    state : UniverseState
        Full universe state after completing a task.

    Returns
    -------
    dict
        Partial state with:
        - ``health``: updated health metrics.
        - ``task_queue``: cleared compatibility queue.
        - ``quality_trace``: cycle summary entry.
    """
    health = dict(state.get("health", {}))
    queue = list(state.get("task_queue", []))

    total_words = state.get("total_words", 0)
    total_chapters = state.get("total_chapters", 0)

    # --- 1. Update health metrics ---
    health["total_words"] = total_words
    health["total_chapters"] = total_chapters
    health["cycles_completed"] = health.get("cycles_completed", 0) + 1
    health["review_cycles_completed"] = health.get(
        "review_cycles_completed", 0,
    ) + 1

    # --- 2. MemoryManager cleanup ---
    evicted = _run_memory_cleanup(state, total_chapters)

    # --- 3. Clear completed execution / compatibility queue ---
    completed_task = state.get("current_task") or (queue[0] if queue else "unknown")
    if queue:
        queue.pop(0)

    # --- 4. Continue unless explicitly stopped ---
    # The daemon runs indefinitely.  Stopping happens only via an
    # explicit signal (API stop, SIGINT, .pause file).  An empty
    # Queue is only a compatibility mirror. Review gates will pick the
    # next task on the following cycle.
    # stopped is only set externally (API/SIGINT/.pause) -- no auto-stop logic here
    health.setdefault("stopped", False)

    # --- 5. Check cross-universe synthesis queue ---
    switch_target = _check_cross_universe_synthesis(state)
    if switch_target:
        health["switch_to_universe"] = switch_target
        logger.info(
            "Cross-universe synthesis: %s has pending signals, flagging switch",
            switch_target,
        )

    # --- 4. Ensure world_state_version is forwarded ---
    # Explicitly carry forward world_state_version so it persists across
    # the cycle boundary.  Without this, a state-merging edge case can
    # leave version at 0 and re-trigger the bootstrap worldbuild.
    world_state_version = state.get("world_state_version", 0)

    logger.info(
        "Universe cycle: completed=%s, remaining=%d, stopped=%s, "
        "words=%d, chapters=%d, world_version=%d",
        completed_task,
        len(queue),
        health["stopped"],
        total_words,
        total_chapters,
        world_state_version,
    )

    return {
        "health": health,
        "task_queue": queue,
        "review_stage": "foundation",
        "current_task": None,
        "current_execution_id": None,
        "current_execution_ref": None,
        "world_state_version": world_state_version,
        "quality_trace": [
            {
                "node": "universe_cycle",
                "action": "cycle_maintenance",
                "completed_task": completed_task,
                "remaining_tasks": len(queue),
                "stopped": health["stopped"],
                "total_words": total_words,
                "total_chapters": total_chapters,
                "evicted_records": evicted,
                "cycles_completed": health["cycles_completed"],
                "review_cycles_completed": health["review_cycles_completed"],
                "world_state_version": world_state_version,
            }
        ],
    }


def _run_memory_cleanup(state: dict[str, Any], current_chapter: int) -> int:
    """Evict old episodic data via MemoryManager if available.

    Returns the number of records evicted, or 0 if no manager.
    """
    from fantasy_author import runtime

    mgr = runtime.memory_manager
    if mgr is None:
        return 0
    try:
        evicted = mgr.evict_old_data(current_chapter=max(1, current_chapter))
        logger.debug("Memory cleanup: evicted %d records", evicted)
        return evicted
    except Exception as e:
        logger.warning("MemoryManager.evict_old_data() failed: %s", e)
        return 0


def _check_cross_universe_synthesis(state: dict[str, Any]) -> str:
    """Check if other universes have pending synthesis signals.

    Only triggers if the current universe has NO pending synthesis
    of its own (current universe always takes priority).

    Returns the universe ID to switch to, or empty string if none.
    """
    import json
    from pathlib import Path

    # Only check when current universe has no pending synthesis
    current_path = state.get("_universe_path", "")
    if not current_path:
        return ""

    current_dir = Path(current_path)
    current_signals = current_dir / "worldbuild_signals.json"
    if current_signals.exists():
        try:
            data = json.loads(current_signals.read_text(encoding="utf-8"))
            if isinstance(data, list) and any(
                s.get("type") == "synthesize_source" for s in data if isinstance(s, dict)
            ):
                return ""  # Current universe still has work
        except (json.JSONDecodeError, OSError):
            pass

    # Scan sibling universes for pending synthesis
    base_dir = current_dir.parent
    if not base_dir.is_dir():
        return ""

    try:
        for entry in sorted(base_dir.iterdir()):
            if not entry.is_dir() or entry == current_dir:
                continue
            signals_file = entry / "worldbuild_signals.json"
            if not signals_file.exists():
                continue
            try:
                data = json.loads(signals_file.read_text(encoding="utf-8"))
                if isinstance(data, list) and any(
                    s.get("type") == "synthesize_source"
                    for s in data if isinstance(s, dict)
                ):
                    return entry.name
            except (json.JSONDecodeError, OSError):
                continue
    except OSError:
        pass

    return ""
