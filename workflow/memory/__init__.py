"""Letta-inspired hierarchical memory system.

Re-exports
----------
MemoryManager         -- central interface (assemble_context, store, promote, reflect)
CoreMemory            -- active context window (~8-15K tokens)
EpisodicMemory        -- recent scene summaries and facts (SQLite)
ArchivalMemory        -- bridge to KG + ASP
PromotionGates        -- fact/rule/style lifecycle transitions
ReflexionEngine       -- self-critique on revert
FactConsolidator      -- deduplicates and merges episodic facts (Phase 3.3)
ObservationPromoter   -- promotes observations to archival tier (Phase 3.3)
ConsolidationResult   -- outcome of consolidation batch (Phase 3.3)
TemporalFact          -- fact with validity time windows (Phase 3.4)
TemporalFactStore     -- SQLite-backed temporal fact store (Phase 3.4)
TemporalIndex         -- in-memory index for temporal queries (Phase 3.4)
MemoryScope           -- universe/branch/author/user/session scope (Phase 3.5)
ScopedQuery           -- query with scope constraints (Phase 3.5)
ScopeResolver         -- visibility and write permission logic (Phase 3.5)
ScopedMemoryRouter    -- wraps MemoryManager with scope filtering (Phase 3.5)
get_memory_tools      -- agent-controlled memory tools for LangGraph (Phase 3.6)
ProgressiveIngestor   -- non-blocking canon file ingestion (Phase 7)
OutputVersionStore    -- draft versioning with rollback (Phase 7)
SeriesPromiseTracker  -- cross-book promise tracking (Phase 7)
"""

from workflow.memory.archival import ArchivalMemory
from workflow.memory.consolidation import (
    ConsolidationResult,
    FactConsolidator,
    ObservationPromoter,
)
from workflow.memory.core import CoreMemory
from workflow.memory.episodic import EpisodicMemory
from workflow.memory.ingestion import ProgressiveIngestor
from workflow.memory.manager import ContextBundle, MemoryManager
from workflow.memory.promises import SeriesPromiseTracker
from workflow.memory.promotion import PromotionGates, PromotionResult
from workflow.memory.reflexion import ReflexionEngine, ReflexionResult
from workflow.memory.scoping import (
    MemoryScope,
    ScopedMemoryRouter,
    ScopedQuery,
    ScopeResolver,
)
from workflow.memory.temporal import (
    TemporalFact,
    TemporalFactStore,
    TemporalIndex,
)
from workflow.memory.tools import get_memory_tools
from workflow.memory.versioning import OutputVersionStore

__all__ = [
    "ArchivalMemory",
    "ConsolidationResult",
    "ContextBundle",
    "CoreMemory",
    "EpisodicMemory",
    "FactConsolidator",
    "MemoryManager",
    "MemoryScope",
    "ObservationPromoter",
    "OutputVersionStore",
    "ProgressiveIngestor",
    "PromotionGates",
    "PromotionResult",
    "ReflexionEngine",
    "ReflexionResult",
    "ScopedMemoryRouter",
    "ScopedQuery",
    "ScopeResolver",
    "SeriesPromiseTracker",
    "TemporalFact",
    "TemporalFactStore",
    "TemporalIndex",
    "get_memory_tools",
]
