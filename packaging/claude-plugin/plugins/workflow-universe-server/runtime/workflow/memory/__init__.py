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

from workflow.memory.archival import ArchivalMemory
from workflow.memory.core import CoreMemory
from workflow.memory.episodic import EpisodicMemory
from workflow.memory.ingestion import ProgressiveIngestor
from workflow.memory.manager import ContextBundle, MemoryManager
from workflow.memory.promises import SeriesPromiseTracker
from workflow.memory.promotion import PromotionGates, PromotionResult
from workflow.memory.reflexion import ReflexionEngine, ReflexionResult
from workflow.memory.versioning import OutputVersionStore

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
