"""Analyze phase: extract facts and key information from sources."""

from __future__ import annotations

from typing import Any


def analyze_phase(state: dict[str, Any]) -> dict[str, Any]:
    """Extract facts from gathered sources.

    This phase uses deterministic logic to extract structured facts
    from source summaries. In a full system, this would use an LLM
    or semantic extraction pipeline.

    Args:
        state: Current workflow state with sources field.

    Returns:
        Partial state update with extracted_facts added.
    """
    sources: list[dict[str, Any]] = state.get("sources", [])

    # Deterministic fact extraction from source summaries
    facts = []
    for source in sources:
        summary = source.get("summary", "")
        title = source.get("title", "")
        source_id = source.get("source_id", "")

        # Simple heuristic: split sentences in summary as individual facts
        if summary:
            sentences = [s.strip() for s in summary.split(".") if s.strip()]
            for sentence in sentences:
                facts.append(
                    {
                        "topic": title,
                        "fact": sentence,
                        "source_id": source_id,
                        "confidence": 0.8,
                    }
                )

    # Track progress
    iteration = state.get("iteration_count", 0)
    trace_entry = {
        "phase": "analyze",
        "iteration": iteration,
        "facts_extracted": len(facts),
        "status": "completed",
    }

    return {
        "extracted_facts": facts,  # operator.add will accumulate these
        "quality_trace": [trace_entry],
    }
