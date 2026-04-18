"""Register fantasy-author domain-trusted opaque nodes (Phase D).

The ``universe_cycle_wrapper`` callable runs one full pass of the
fantasy universe graph. It's invoked by the outer Branch's single
node under ``WORKFLOW_UNIFIED_EXECUTION=1``. Boundary semantics:

- Input: a dict with the six boundary fields (``universe_id``,
  ``universe_path``, ``premise_kernel``, ``health``, ``total_words``,
  ``total_chapters``; plus ``world_state_version``, ``canon_facts_count``,
  ``active_series``, ``series_completed`` if present for resume).
- Inside: builds ``build_universe_graph()`` fresh, compiles without a
  checkpointer, invokes it once (runs until END — either ``idle`` or
  ``health.stopped``).
- Output: boundary fields read out of the final inner state.

Checkpoint semantics: the outer SqliteSaver stores only the boundary
fields. Mid-cycle state (``workflow_instructions``, ``task_queue``,
``selected_target_id``) is NOT persisted across wrapper boundaries
under flag-on. See preflight §4.11. Option-1 regression, accepted
for v1 per lead direction.

Import this module from ``fantasy_author/__main__.py`` so
registration happens before any ``compile_branch`` call.
"""

from __future__ import annotations

import logging
from typing import Any

from workflow.domain_registry import register_domain_callable

logger = logging.getLogger(__name__)


_BOUNDARY_FIELDS = (
    "universe_id",
    "universe_path",
    "premise_kernel",
    "health",
    "total_words",
    "total_chapters",
    "world_state_version",
    "canon_facts_count",
    "active_series",
    "series_completed",
)


def universe_cycle_wrapper(state: dict[str, Any]) -> dict[str, Any]:
    """Run one full pass of the fantasy universe graph.

    See module docstring for boundary semantics.
    """
    # Import lazily so the registry can be imported without pulling
    # the full graph module at import time (helps test isolation and
    # keeps the engine→domain arrow clean).
    from fantasy_author.graphs.universe import build_universe_graph

    inner_graph = build_universe_graph()
    # No inner checkpointer — boundary-only persistence under
    # flag-on. Mid-cycle state is reconstructed on resume via the
    # normal dispatch path (same as a fresh start).
    compiled = inner_graph.compile()

    # Seed the inner state from the boundary. Missing fields use
    # UniverseState TypedDict defaults via LangGraph reducer merge.
    initial: dict[str, Any] = {
        field: state[field] for field in _BOUNDARY_FIELDS if field in state
    }
    # Workflow instructions can be reconstructed from premise_kernel.
    if state.get("premise_kernel"):
        initial.setdefault("premise_kernel", state["premise_kernel"])
        initial.setdefault(
            "workflow_instructions",
            {"premise": state["premise_kernel"]},
        )
    # Pass internal config fields through so phases that read them
    # (e.g. _db_path for knowledge graph) find them.
    for passthrough in ("_universe_path", "_db_path", "_kg_path"):
        if passthrough in state:
            initial[passthrough] = state[passthrough]

    # recursion_limit is generous because the inner graph cycles
    # through review→dispatch→execute→cycle many times before idle.
    config = {"recursion_limit": 10000}

    logger.info(
        "universe_cycle_wrapper: invoking inner graph "
        "(universe_id=%s, premise_set=%s)",
        state.get("universe_id", ""),
        bool(state.get("premise_kernel")),
    )
    final = compiled.invoke(initial, config=config)
    logger.info(
        "universe_cycle_wrapper: inner graph returned "
        "(total_words=%s, total_chapters=%s)",
        final.get("total_words", 0),
        final.get("total_chapters", 0),
    )

    # Return only the boundary fields. LangGraph reducer merges them
    # into the outer state.
    return {
        field: final[field]
        for field in _BOUNDARY_FIELDS
        if field in final
    }


register_domain_callable(
    "fantasy_author", "universe_cycle_wrapper", universe_cycle_wrapper,
)
