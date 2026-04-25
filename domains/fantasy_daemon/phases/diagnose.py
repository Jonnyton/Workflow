"""Diagnose node -- book graph; entry when stuck_level elevated, generates recovery suggestions."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Number of consecutive reverts that constitutes a stuck pattern.
_REVERT_PATTERN_THRESHOLD = 3


def diagnose(state: dict[str, Any]) -> dict[str, Any]:
    """Diagnose and recover from stuck states.

    1. Scan ``quality_trace`` for repeated reverts.
    2. Identify recurring structural failure patterns.
    3. Generate recovery suggestions in ``health``.
    4. Only reset ``stuck_level`` if a recovery action was identified.

    Parameters
    ----------
    state : BookState
        Must contain ``health`` with ``stuck_level``.  Optionally
        contains ``quality_trace`` (from accumulated scene runs).

    Returns
    -------
    dict
        Partial state with:
        - ``health``: updated health dict with recovery info.
    """
    health = dict(state.get("health", {}))
    quality_trace = state.get("quality_trace", [])

    # --- 1. Count recent reverts ---
    recent_reverts = _count_recent_reverts(quality_trace)
    revert_pattern = recent_reverts >= _REVERT_PATTERN_THRESHOLD

    # --- 2. Identify recurring structural failures ---
    recurring_failures = _find_recurring_failures(quality_trace)

    # --- 3. Generate recovery suggestions ---
    suggestions = []
    recovery_taken = False

    if revert_pattern:
        suggestions.append({
            "type": "revert_pattern",
            "message": (
                f"Detected {recent_reverts} consecutive reverts. "
                "Consider re-outlining the chapter or introducing a "
                "character disruption to break the pattern."
            ),
            "action": "re_outline",
        })
        recovery_taken = True

    if recurring_failures:
        for failure_name, count in recurring_failures.items():
            suggestions.append({
                "type": "recurring_failure",
                "failure": failure_name,
                "count": count,
                "message": (
                    f"Structural check '{failure_name}' has failed "
                    f"{count} times recently. Consider adjusting "
                    "the approach for this dimension."
                ),
                "action": "adjust_approach",
            })
        if not recovery_taken:
            recovery_taken = True

    if not suggestions:
        # No specific pattern found, but stuck_level is elevated.
        # Suggest a worldbuild detour to refresh context.
        suggestions.append({
            "type": "general_stuck",
            "message": (
                "No specific failure pattern detected, but progress "
                "is stalled. Consider a worldbuild detour or lowering "
                "quality thresholds temporarily."
            ),
            "action": "worldbuild_detour",
        })
        recovery_taken = True

    # --- 4. Update health ---
    health["recovery_suggestions"] = suggestions
    health["recent_reverts"] = recent_reverts
    health["recurring_failures"] = recurring_failures

    if recovery_taken:
        # Reset stuck_level since we identified a recovery path.
        # Reduce by 2 (don't fully reset to preserve some history).
        old_stuck = health.get("stuck_level", 0)
        health["stuck_level"] = max(0, old_stuck - 2)
        logger.info(
            "Diagnose: stuck_level %d -> %d, %d suggestions",
            old_stuck,
            health["stuck_level"],
            len(suggestions),
        )
    else:
        logger.info("Diagnose: no recovery action found, stuck_level unchanged")

    return {
        "health": health,
    }


def _count_recent_reverts(quality_trace: list[dict[str, Any]]) -> int:
    """Count consecutive reverts at the tail of the quality trace.

    Only looks at commit-node entries with a verdict of 'revert'.
    """
    count = 0
    for entry in reversed(quality_trace):
        if entry.get("node") != "commit":
            continue
        if entry.get("verdict") == "revert":
            count += 1
        else:
            break
    return count


def _find_recurring_failures(
    quality_trace: list[dict[str, Any]],
    window: int = 10,
) -> dict[str, int]:
    """Find structural check names that fail repeatedly.

    Scans the last ``window`` commit entries for structural failures
    and returns those that appear 2 or more times.
    """
    failure_counts: dict[str, int] = {}

    commit_entries = [
        e for e in quality_trace if e.get("node") == "commit"
    ]
    recent = commit_entries[-window:]

    for entry in recent:
        # commit_result may contain structural_checks list
        checks = entry.get("structural_checks", [])
        for check in checks:
            if not check.get("passed", True):
                name = check.get("name", "unknown")
                failure_counts[name] = failure_counts.get(name, 0) + 1

    # Only return failures that recur (2+ times)
    return {k: v for k, v in failure_counts.items() if v >= 2}
