"""State definitions for all four graph levels plus series tracking.

These TypedDicts are the primary interface contract consumed by every
other module in the system.  Changes after Phase 0 require lead approval.

Re-exports
----------
SceneState      -- atomic creative unit (orient/plan/draft/commit)
ChapterState    -- scene sequencing, consolidation, learning
BookState       -- chapter loop, arc closure, stuck recovery
SeriesState     -- multi-book arcs (consumed by Book graph nodes)
UniverseState   -- daemon entry point, task routing
UniverseLiveState -- thin universe live state alias
ExecutionEnvelope -- thin live execution cursor
"""

from domains.fantasy_daemon.state.book_state import BookState
from domains.fantasy_daemon.state.chapter_state import ChapterState
from domains.fantasy_daemon.state.scene_state import SceneState
from domains.fantasy_daemon.state.series_state import SeriesState
from domains.fantasy_daemon.state.universe_state import (
    ExecutionEnvelope,
    UniverseLiveState,
    UniverseState,
)

__all__ = [
    "BookState",
    "ChapterState",
    "ExecutionEnvelope",
    "SceneState",
    "SeriesState",
    "UniverseLiveState",
    "UniverseState",
]
