"""Letta-inspired hierarchical memory system.

Re-exports
----------
MemoryManager         -- central interface (assemble_context, store, promote, reflect)
CoreMemory            -- active context window (~8-15K tokens)
EpisodicMemory        -- recent scene summaries and facts (SQLite)
ArchivalMemory        -- bridge to KG + ASP
PromotionGates        -- fact/rule/style lifecycle transitions
ReflexionEngine       -- self-critique on revert
ProgressiveIngestor   -- non-blocking canon file ingestion (Phase 7)
OutputVersionStore    -- draft versioning with rollback (Phase 7)
SeriesPromiseTracker  -- cross-book promise tracking (Phase 7)
"""

from fantasy_author.memory.archival import ArchivalMemory
from fantasy_author.memory.core import CoreMemory
from fantasy_author.memory.episodic import EpisodicMemory
from fantasy_author.memory.ingestion import ProgressiveIngestor
from fantasy_author.memory.manager import ContextBundle, MemoryManager
from fantasy_author.memory.promises import SeriesPromiseTracker
from fantasy_author.memory.promotion import PromotionGates, PromotionResult
from fantasy_author.memory.reflexion import ReflexionEngine, ReflexionResult
from fantasy_author.memory.versioning import OutputVersionStore

__all__ = [
    "ArchivalMemory",
    "ContextBundle",
    "CoreMemory",
    "EpisodicMemory",
    "MemoryManager",
    "OutputVersionStore",
    "ProgressiveIngestor",
    "PromotionGates",
    "PromotionResult",
    "ReflexionEngine",
    "ReflexionResult",
    "SeriesPromiseTracker",
]
