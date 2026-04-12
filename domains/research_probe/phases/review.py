"""Review phase: check synthesis quality and decide on revision."""

from __future__ import annotations

from typing import Any


def review_phase(state: dict[str, Any]) -> dict[str, Any]:
    """Review synthesis quality and decide whether revision is needed.

    This phase performs deterministic checks. A real system would use
    editorial feedback or automated quality scoring.

    Args:
        state: Current workflow state with synthesis field.

    Returns:
        Partial state update with review_notes and needs_revision flags.
    """
    synthesis: str = state.get("synthesis", "")
    facts: list[dict[str, Any]] = state.get("extracted_facts", [])
    iteration: int = state.get("iteration_count", 0)
    max_iterations: int = state.get("max_iterations", 3)

    notes = []
    needs_revision = False

    # Check 1: Synthesis has content
    if len(synthesis) < 50:
        notes.append("Synthesis is too brief. Consider gathering more sources.")
        needs_revision = True

    # Check 2: Sufficient facts extracted
    if len(facts) < 3:
        notes.append("Too few facts extracted. Revision may help gather better sources.")
        needs_revision = True

    # Check 3: Iteration limit
    if iteration >= max_iterations - 1:
        notes.append(f"Reached iteration limit ({max_iterations}). Finalizing.")
        needs_revision = False  # Force completion

    # Positive feedback
    if not needs_revision and len(synthesis) >= 50:
        notes.append("Synthesis is complete and ready for export.")

    # Track progress
    trace_entry = {
        "phase": "review",
        "iteration": iteration,
        "synthesis_quality": "acceptable" if not needs_revision else "needs_work",
        "notes_count": len(notes),
        "status": "completed",
    }

    return {
        "review_notes": notes,
        "needs_revision": needs_revision,
        "iteration_count": iteration + 1,
        "quality_trace": [trace_entry],
    }
