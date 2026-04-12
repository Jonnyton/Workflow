"""Workflow Engine — shared infrastructure for long-running agent workflows.

Fantasy Author is the first domain. The engine provides providers, memory,
retrieval, evaluation, checkpointing, notes, work targets, API scaffolding,
and optional orchestration profiles. Each domain owns its own graph topology.

Modules
-------
providers     -- Multi-provider routing with fallback chains
memory        -- Three-tier memory (core, episodic, archival)
retrieval     -- Hybrid search across KG, vector, notes, world state
knowledge     -- Knowledge graph, entity extraction, communities
evaluation    -- Editorial feedback, process traces, structural checks
constraints   -- ASP-based formal verification (optional)
planning      -- HTN planner, dome expansion
checkpointing -- SqliteSaver for LangGraph state persistence
learning      -- Craft cards, style rules, criteria discovery
ingestion     -- Canon upload, image/video extraction, indexing
desktop       -- Host tray, dashboard, launcher, notifications
notes         -- Unified attributed notes system
work_targets  -- Work target registry with role/lifecycle guardrails
author_server -- Multiplayer Author server (sessions, branches, runtime)
mcp_server    -- MCP endpoint for tool/context/notes access
api           -- FastAPI routes (scaffolding - domain-specific routes TBD)
testing       -- GPT harness, builder, gpt_harness module
config        -- Configuration and environment
runtime       -- Runtime state and execution envelope
protocols     -- Engine-facing protocol definitions
registry      -- Domain discovery and registration
discovery     -- Domain auto-discovery and registration
exceptions    -- Shared exception types

Profiles
--------
profiles.multi_timescale  -- Four-level (task/batch/project/workspace)
                             orchestration profile

Key exports
-----------
DomainRegistry, default_registry  -- Domain lookup and registration
discover_domains, auto_register   -- Domain discovery utilities
Domain, DomainConfig              -- Domain protocol and metadata
"""

from __future__ import annotations

__version__ = "0.1.0"

# Re-export key infrastructure symbols for convenience
from workflow.discovery import auto_register, discover_domains
from workflow.protocols import Domain, DomainConfig
from workflow.registry import DomainRegistry, default_registry

__all__ = [
    "DomainRegistry",
    "default_registry",
    "discover_domains",
    "auto_register",
    "Domain",
    "DomainConfig",
]

