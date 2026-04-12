"""Runtime singletons for non-serializable objects.

LangGraph's checkpointer serializes the full state dict via msgpack.
Objects like MemoryManager, OutputVersionStore, and SeriesPromiseTracker
are not serializable. Instead of storing them in graph state, they live
here as module-level references that DaemonController sets before
starting the graph and nodes read at execution time.
"""

from __future__ import annotations

from typing import Any, Callable

from fantasy_author.config import UniverseConfig

# Set by DaemonController.start() before graph execution begins.
memory_manager: Any | None = None
version_store: Any | None = None
promise_tracker: Any | None = None

# Retrieval backends (set by DaemonController.start())
knowledge_graph: Any | None = None
vector_store: Any | None = None
raptor_tree: Any | None = None
embed_fn: Callable[[str], list[float]] | None = None

# Per-universe configuration (loaded from config.yaml)
universe_config: UniverseConfig = UniverseConfig()


def reset() -> None:
    """Clear all runtime references (used in tests and shutdown)."""
    global memory_manager, version_store, promise_tracker
    global knowledge_graph, vector_store, raptor_tree, embed_fn
    global universe_config
    memory_manager = None
    version_store = None
    promise_tracker = None
    knowledge_graph = None
    vector_store = None
    raptor_tree = None
    embed_fn = None
    universe_config = UniverseConfig()
