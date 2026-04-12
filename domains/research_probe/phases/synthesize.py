"""Synthesize phase: combine facts into a coherent summary."""

from __future__ import annotations

from typing import Any


def synthesize_phase(state: dict[str, Any]) -> dict[str, Any]:
    """Synthesize facts into a research summary.

    This phase combines extracted facts into a coherent narrative.
    Deterministic logic for the probe; a real system would use an LLM.

    Args:
        state: Current workflow state with extracted_facts field.

    Returns:
        Partial state update with synthesis and themes fields updated.
    """
    facts: list[dict[str, Any]] = state.get("extracted_facts", [])
    query: str = state.get("research_query", "")

    # Deterministic synthesis: group facts by topic
    topics = {}
    for fact in facts:
        topic = fact.get("topic", "Unknown")
        if topic not in topics:
            topics[topic] = []
        topics[topic].append(fact.get("fact", ""))

    # Build synthesis text
    synthesis_parts = [f"Research Summary: {query}\n"]
    all_themes = []

    for topic, topic_facts in topics.items():
        synthesis_parts.append(f"\n{topic}:")
        for fact in topic_facts:
            synthesis_parts.append(f"  - {fact}")
        # Extract theme from topic name
        all_themes.append(topic.lower().replace(" ", "_"))

    synthesis = "\n".join(synthesis_parts)

    # Track progress
    iteration = state.get("iteration_count", 0)
    trace_entry = {
        "phase": "synthesize",
        "iteration": iteration,
        "synthesis_length": len(synthesis),
        "themes_identified": len(all_themes),
        "status": "completed",
    }

    return {
        "synthesis": synthesis,
        "themes": all_themes,
        "quality_trace": [trace_entry],
    }
