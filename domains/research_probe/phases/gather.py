"""Gather phase: collect relevant sources for the research query."""

from __future__ import annotations

from typing import Any

from domains.research_probe.tools import research_search


def gather_phase(state: dict[str, Any]) -> dict[str, Any]:
    """Gather sources relevant to the research query.

    This phase uses the research_search tool to find documents.
    Sources are accumulated in state.sources (uses operator.add reducer).

    Args:
        state: Current workflow state with research_query field.

    Returns:
        Partial state update with new sources added.
    """
    query: str = state.get("research_query", "")

    if not query:
        return {"sources": []}

    # Call the search tool to find sources
    results = research_search(query=query, max_results=5)

    # Convert results to uniform format
    sources = [
        {
            "source_id": result.get("id", ""),
            "title": result.get("title", ""),
            "url": result.get("url", ""),
            "summary": result.get("summary", ""),
            "relevance": result.get("relevance", 0.0),
        }
        for result in results
    ]

    # Track progress
    iteration = state.get("iteration_count", 0)
    trace_entry = {
        "phase": "gather",
        "iteration": iteration,
        "sources_found": len(sources),
        "status": "completed",
    }

    return {
        "sources": sources,  # operator.add will accumulate these
        "quality_trace": [trace_entry],
    }
