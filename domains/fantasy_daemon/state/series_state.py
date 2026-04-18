"""Series-level state -- multi-book arcs, cross-book promises, recurring characters.

Series logic is folded into the Book graph as conditional edges rather than a
separate nesting level, keeping the proven 4-level graph depth.  This state
definition is used by book-level nodes that need series context.
"""

from __future__ import annotations

from typing_extensions import TypedDict


class SeriesState(TypedDict):
    """Tracks multi-book series state (consumed by Book graph nodes)."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    universe_id: str
    series_id: str
    series_title: str

    # ------------------------------------------------------------------
    # Progress
    # ------------------------------------------------------------------
    books_completed: int
    """Number of books finished in this series."""

    books_planned: int
    """Adaptive -- grows if the story demands more books."""

    # ------------------------------------------------------------------
    # Series-level tracking
    # ------------------------------------------------------------------
    series_arc: dict
    """Multi-book arc tracking (overarching plot threads, themes)."""

    cross_book_promises: list
    """Unresolved promises that span across books."""

    recurring_characters: list
    """Character states that persist across the full series."""

    # ------------------------------------------------------------------
    # Outputs
    # ------------------------------------------------------------------
    series_summary: str | None
    """Summary of the series so far."""

    health: dict
    """Series-level health metrics."""
