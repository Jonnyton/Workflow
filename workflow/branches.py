"""Community Branches — data models for community-designed LangGraph topologies.

Defines the core models that let users design, share, and fork
complete graph topologies through MCP tools:

- **BranchDefinition**: A complete graph topology (nodes + edges + state).
- **NodeDefinition**: A single node within a branch graph, extending
  the existing NodeRegistration contract.
- **StateFieldDecl**: A single field declaration within a branch's
  state schema, supporting the TypedDict + Annotated reducer pattern.
  Deferred to Phase 3 — state_schema is stored as an unvalidated JSON
  blob for now. StateFieldDecl is available for future formal validation.

All models serialize to/from JSON for SQLite storage. BranchDefinition
stores its graph topology (nodes and edges) and state schema as embedded
JSON rather than separate normalized tables — this keeps fork/clone
operations atomic and avoids cross-table consistency issues.

Graph topology JSON follows LangGraph's native API shape:
- nodes: list of {id, node_def_id, position}
- edges: list of {from, to} for simple directed edges
- conditional_edges: list of {from, conditions: {outcome: target}} for branching
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

# ═══════════════════════════════════════════════════════════════════════════
# State Schema (Phase 3 — formal validation deferred)
# ═══════════════════════════════════════════════════════════════════════════

# Valid type strings for state field declarations.
VALID_FIELD_TYPES = {"string", "number", "boolean", "list", "dict", "any"}

# Valid reducer strategies — maps to how LangGraph merges parallel updates.
VALID_REDUCERS = {"overwrite", "append", "merge"}


@dataclass
class StateFieldDecl:
    """A single field declaration in a branch's state schema.

    Maps to one key in the LangGraph TypedDict. The reducer determines
    how parallel node outputs merge into the state:

    - ``overwrite``: last-write-wins (default for scalar fields).
    - ``append``: ``Annotated[list, operator.add]`` — accumulates.
    - ``merge``: ``dict.update`` semantics for dict fields.

    NOTE: This model is available for future Phase 3 formal validation.
    Currently, state_schema in BranchDefinition is stored as an
    unvalidated JSON blob (list of dicts).
    """

    name: str
    type: str = "any"
    default_value: Any = None
    reducer: str = "overwrite"
    description: str = ""

    def __post_init__(self) -> None:
        if self.type not in VALID_FIELD_TYPES:
            raise ValueError(
                f"Invalid field type '{self.type}'. "
                f"Must be one of: {', '.join(sorted(VALID_FIELD_TYPES))}"
            )
        if self.reducer not in VALID_REDUCERS:
            raise ValueError(
                f"Invalid reducer '{self.reducer}'. "
                f"Must be one of: {', '.join(sorted(VALID_REDUCERS))}"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StateFieldDecl:
        return cls(**{
            k: v for k, v in data.items()
            if k in cls.__dataclass_fields__
        })


# ═══════════════════════════════════════════════════════════════════════════
# Node Definition
# ═══════════════════════════════════════════════════════════════════════════

# Valid phases — same set as the existing node registration system.
VALID_PHASES = {
    "orient", "plan", "draft", "commit", "learn",
    "reflect", "worldbuild", "custom",
}


@dataclass
class NodeDefinition:
    """A single node within a branch graph topology.

    Extends the existing NodeRegistration contract with fields needed
    for graph topology (dependencies, evaluation criteria, model hints)
    and execution policy (timeout, retry).

    Nodes come in two flavors:
    - **Code nodes**: have ``source_code`` — executed in the sandbox.
    - **Prompt-template nodes**: have ``prompt_template`` — LLM calls
      with the template filled from state. ``model_hint`` selects the
      provider role.

    ``input_keys`` and ``output_keys`` declare which state fields the node
    reads and writes — enforced by the sandbox at runtime for code nodes.
    """

    node_id: str
    display_name: str
    description: str = ""
    phase: str = "custom"

    # State contract
    input_keys: list[str] = field(default_factory=list)
    output_keys: list[str] = field(default_factory=list)

    # Source and execution — one of source_code or prompt_template
    source_code: str = ""
    prompt_template: str = ""
    model_hint: str = ""
    tools_allowed: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    timeout_seconds: float = 30.0
    retry_policy: dict[str, Any] = field(default_factory=lambda: {
        "max_retries": 0,
        "backoff_seconds": 1.0,
    })

    # Quality
    evaluation_criteria: list[dict[str, str]] = field(default_factory=list)

    # Legacy compat fields from NodeRegistration
    author: str = "anonymous"
    registered_at: str = ""
    enabled: bool = True
    approved: bool = False

    def __post_init__(self) -> None:
        if self.phase not in VALID_PHASES:
            raise ValueError(
                f"Invalid phase '{self.phase}'. "
                f"Must be one of: {', '.join(sorted(VALID_PHASES))}"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NodeDefinition:
        return cls(**{
            k: v for k, v in data.items()
            if k in cls.__dataclass_fields__
        })

    def to_node_registration(self) -> dict[str, Any]:
        """Convert to the legacy NodeRegistration dict shape.

        Used for backward compatibility with the existing sandbox
        ``execute_registered()`` method and the extensions MCP tool.
        """
        return {
            "node_id": self.node_id,
            "display_name": self.display_name,
            "description": self.description,
            "phase": self.phase,
            "input_keys": self.input_keys,
            "output_keys": self.output_keys,
            "source_code": self.source_code,
            "dependencies": self.dependencies,
            "author": self.author,
            "registered_at": self.registered_at,
            "enabled": self.enabled,
            "approved": self.approved,
        }

    @classmethod
    def from_node_registration(cls, reg: dict[str, Any]) -> NodeDefinition:
        """Create a NodeDefinition from a legacy NodeRegistration dict.

        Used during migration from .node_registry.json.
        """
        return cls.from_dict(reg)


# ═══════════════════════════════════════════════════════════════════════════
# Graph Topology Types
# ═══════════════════════════════════════════════════════════════════════════

# Graph topology JSON follows LangGraph's native API shape:
#
# {
#   "nodes": [{"id": "orient", "node_def_id": "...", "position": 0}],
#   "edges": [{"from": "START", "to": "orient"}, ...],
#   "conditional_edges": [{"from": "commit", "conditions": {"accept": "END", "revise": "draft"}}]
# }
#
# Special node IDs: "START" and "END" are reserved for graph entry/exit.

RESERVED_NODE_IDS = {"START", "END"}


@dataclass
class GraphNodeRef:
    """A reference to a node definition within a graph topology.

    This is the graph-level placement of a node — linking a position
    in the topology to a NodeDefinition via ``node_def_id``.
    """

    id: str
    node_def_id: str = ""
    position: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "node_def_id": self.node_def_id, "position": self.position}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GraphNodeRef:
        return cls(**{
            k: v for k, v in data.items()
            if k in cls.__dataclass_fields__
        })


@dataclass
class EdgeDefinition:
    """A simple directed edge in the branch graph topology.

    Uses ``from_node`` and ``to_node`` internally to avoid shadowing
    Python's ``from`` keyword. Serializes as ``{"from": ..., "to": ...}``
    to match LangGraph's native format.
    """

    from_node: str
    to_node: str

    def to_dict(self) -> dict[str, Any]:
        return {"from": self.from_node, "to": self.to_node}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EdgeDefinition:
        return cls(
            from_node=data.get("from", data.get("from_node", "")),
            to_node=data.get("to", data.get("to_node", "")),
        )


@dataclass
class ConditionalEdge:
    """A conditional branching edge in the graph topology.

    Maps outcomes to target nodes. The routing function is determined
    by the source node's evaluation at runtime.
    """

    from_node: str
    conditions: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"from": self.from_node, "conditions": self.conditions}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConditionalEdge:
        return cls(
            from_node=data.get("from", data.get("from_node", "")),
            conditions=data.get("conditions", {}),
        )


# ═══════════════════════════════════════════════════════════════════════════
# Branch Definition
# ═══════════════════════════════════════════════════════════════════════════


def _reachable_from(
    start: str,
    adjacency: dict[str, set[str]],
) -> set[str]:
    """Return all nodes reachable from ``start`` via BFS."""
    visited: set[str] = set()
    queue = [start]
    while queue:
        node = queue.pop(0)
        if node in visited:
            continue
        visited.add(node)
        for neighbor in adjacency.get(node, ()):
            if neighbor not in visited:
                queue.append(neighbor)
    return visited


def _nodes_that_cannot_reach(
    target: str,
    graph_nodes: set[str],
    adjacency: dict[str, set[str]],
) -> set[str]:
    """Return graph nodes that have no path to ``target``.

    Used to detect cycles without an exit condition: if a node
    cannot reach END, it is stuck in a cycle forever.
    """
    # Build reverse adjacency
    reverse: dict[str, set[str]] = {}
    for src, dsts in adjacency.items():
        for dst in dsts:
            reverse.setdefault(dst, set()).add(src)

    # BFS backward from target
    can_reach = _reachable_from(target, reverse)

    # Nodes that cannot reach target
    return graph_nodes - can_reach


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class BranchDefinition:
    """A complete community-designed graph topology.

    A branch definition is the unit of sharing and forking. It contains:

    - Identity and metadata (name, author, domain_id, tags, version).
    - A full graph topology as embedded JSON (nodes + edges).
    - A state schema as an unvalidated JSON blob (formal validation
      deferred to Phase 3).
    - Fork lineage (parent_def_id) for tracking provenance.
    - Publication state and aggregate stats.

    The graph JSON is stored as a single blob in SQLite rather than
    normalized across tables. This makes fork/clone/export atomic —
    one row = one complete topology.
    """

    branch_def_id: str = field(default_factory=_new_id)
    name: str = ""
    description: str = ""
    author: str = "anonymous"
    domain_id: str = "workflow"
    # Phase 5: optional Goal binding. Empty string means no Goal. A
    # Goal captures the intent a Branch serves; many Branches can bind
    # to one Goal for discovery and leaderboards.
    goal_id: str = ""
    tags: list[str] = field(default_factory=list)
    version: int = 1

    # Fork lineage
    parent_def_id: str | None = None

    # Graph topology — stored as embedded JSON in LangGraph-native shape
    graph_nodes: list[GraphNodeRef] = field(default_factory=list)
    edges: list[EdgeDefinition] = field(default_factory=list)
    conditional_edges: list[ConditionalEdge] = field(default_factory=list)
    entry_point: str = ""

    # Node definitions — the actual node implementations
    node_defs: list[NodeDefinition] = field(default_factory=list)

    # State schema — unvalidated JSON blob for now (Phase 3 will use StateFieldDecl)
    state_schema: list[dict[str, Any]] = field(default_factory=list)

    # Publication
    published: bool = False
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    # Aggregate stats (updated by the system, not by users)
    stats: dict[str, Any] = field(default_factory=lambda: {
        "fork_count": 0,
        "run_count": 0,
        "avg_quality_score": 0.0,
    })

    # ── Serialization ──────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict suitable for JSON storage."""
        return {
            "branch_def_id": self.branch_def_id,
            "name": self.name,
            "description": self.description,
            "author": self.author,
            "domain_id": self.domain_id,
            "goal_id": self.goal_id,
            "tags": self.tags,
            "version": self.version,
            "parent_def_id": self.parent_def_id,
            "entry_point": self.entry_point,
            "published": self.published,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "stats": self.stats,
            "graph_nodes": [n.to_dict() for n in self.graph_nodes],
            "edges": [e.to_dict() for e in self.edges],
            "conditional_edges": [c.to_dict() for c in self.conditional_edges],
            "node_defs": [n.to_dict() for n in self.node_defs],
            "state_schema": self.state_schema,
        }

    def to_json(self) -> str:
        """Serialize to a JSON string."""
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BranchDefinition:
        """Deserialize from a plain dict.

        Accepts three formats:
        1. **Canonical**: graph_nodes, edges, conditional_edges, node_defs
           (from ``to_dict()``).
        2. **DB row**: ``graph`` nested dict (from ``_branch_def_from_row``),
           with ``node_defs`` alongside.
        3. **Legacy**: ``nodes`` as a flat node list stored in graph_json.

        Does not mutate the input dict.
        """
        data = dict(data)  # shallow copy to avoid mutating caller's dict

        # DB row format: extract from nested "graph" dict
        graph_blob = data.pop("graph", None)
        if isinstance(graph_blob, dict):
            # Only use graph_blob values if the flat keys aren't present
            if "graph_nodes" not in data:
                data.setdefault("graph_nodes", graph_blob.get("nodes", []))
            if "edges" not in data:
                data.setdefault("edges", graph_blob.get("edges", []))
            if "conditional_edges" not in data:
                data.setdefault(
                    "conditional_edges",
                    graph_blob.get("conditional_edges", []),
                )
            if "entry_point" not in data and graph_blob.get("entry_point"):
                data["entry_point"] = graph_blob["entry_point"]

        # Extract nested structures before filtering
        graph_nodes_raw = data.pop("graph_nodes", [])
        edges_raw = data.pop("edges", [])
        cond_edges_raw = data.pop("conditional_edges", [])
        node_defs_raw = data.pop("node_defs", [])
        state_schema_raw = data.pop("state_schema", [])

        # Legacy compat: "nodes" key from old format becomes node_defs
        legacy_nodes = data.pop("nodes", [])
        if legacy_nodes and not node_defs_raw:
            node_defs_raw = legacy_nodes

        # Filter to known fields only
        known = cls.__dataclass_fields__
        filtered = {k: v for k, v in data.items() if k in known}

        branch = cls(**filtered)
        branch.graph_nodes = [GraphNodeRef.from_dict(n) for n in graph_nodes_raw]
        branch.edges = [EdgeDefinition.from_dict(e) for e in edges_raw]
        branch.conditional_edges = [ConditionalEdge.from_dict(c) for c in cond_edges_raw]
        branch.node_defs = [NodeDefinition.from_dict(n) for n in node_defs_raw]
        branch.state_schema = state_schema_raw
        return branch

    @classmethod
    def from_json(cls, raw: str) -> BranchDefinition:
        """Deserialize from a JSON string."""
        return cls.from_dict(json.loads(raw))

    # ── Graph topology helpers ─────────────────────────────────────────

    def graph_json(self) -> dict[str, Any]:
        """Return the graph topology in LangGraph-native JSON shape."""
        return {
            "nodes": [n.to_dict() for n in self.graph_nodes],
            "edges": [e.to_dict() for e in self.edges],
            "conditional_edges": [c.to_dict() for c in self.conditional_edges],
            "entry_point": self.entry_point,
        }

    def state_schema_json(self) -> list[dict[str, Any]]:
        """Return the state schema as a JSON-serializable list."""
        return list(self.state_schema)

    def node_def_ids(self) -> list[str]:
        """Return all node definition IDs in this branch."""
        return [n.node_id for n in self.node_defs]

    def get_node_def(self, node_id: str) -> NodeDefinition | None:
        """Look up a node definition by ID."""
        for n in self.node_defs:
            if n.node_id == node_id:
                return n
        return None

    def validate(self) -> list[str]:
        """Validate the branch definition for consistency.

        Checks:
        - Name is required.
        - At least one node exists.
        - Entry point is required and references a defined node.
        - No duplicate node IDs (graph nodes or node defs).
        - All edge/conditional_edge references point to defined nodes.
        - Graph node refs point to valid node definitions.
        - No orphaned nodes (nodes not reachable from entry point).
        - No cycles without an exit condition (cycles that never reach END).
        - State schema field names are unique.

        Returns a list of error messages (empty if valid).
        """
        errors: list[str] = []

        if not self.name:
            errors.append("Branch name is required.")

        has_nodes = bool(self.node_defs or self.graph_nodes)
        if not has_nodes:
            errors.append("Branch must have at least one node.")

        # Check for duplicate node definition IDs
        seen_defs: set[str] = set()
        for n in self.node_defs:
            if n.node_id in seen_defs:
                errors.append(f"Duplicate node definition ID: '{n.node_id}'.")
            seen_defs.add(n.node_id)

        # Check for duplicate graph node IDs
        seen_graph: set[str] = set()
        for n in self.graph_nodes:
            if n.id in seen_graph:
                errors.append(f"Duplicate graph node ID: '{n.id}'.")
            seen_graph.add(n.id)

        # Collect all valid node IDs (graph nodes + reserved)
        all_node_ids = seen_graph | RESERVED_NODE_IDS

        # Entry point is required when the branch has nodes
        if has_nodes and not self.entry_point:
            errors.append("Entry point is required when branch has nodes.")
        elif self.entry_point and self.entry_point not in all_node_ids:
            errors.append(
                f"Entry point '{self.entry_point}' is not a defined node."
            )

        # Check graph node refs point to valid node_defs
        for gn in self.graph_nodes:
            if gn.node_def_id and gn.node_def_id not in seen_defs:
                errors.append(
                    f"Graph node '{gn.id}' references unknown "
                    f"node_def_id '{gn.node_def_id}'."
                )

        # Check edge references and build adjacency for reachability
        adjacency: dict[str, set[str]] = {}
        for e in self.edges:
            if e.from_node not in all_node_ids:
                errors.append(
                    f"Edge 'from' node '{e.from_node}' is not defined."
                )
            if e.to_node not in all_node_ids:
                errors.append(
                    f"Edge 'to' node '{e.to_node}' is not defined."
                )
            adjacency.setdefault(e.from_node, set()).add(e.to_node)

        # Check conditional edge references
        for ce in self.conditional_edges:
            if ce.from_node not in all_node_ids:
                errors.append(
                    f"Conditional edge 'from' node '{ce.from_node}' is not defined."
                )
            for target in ce.conditions.values():
                if target not in all_node_ids:
                    errors.append(
                        f"Conditional edge target '{target}' from "
                        f"'{ce.from_node}' is not defined."
                    )
                adjacency.setdefault(ce.from_node, set()).add(target)

        # Orphan detection: check all graph nodes are reachable from entry point
        if self.entry_point and seen_graph:
            reachable = _reachable_from(self.entry_point, adjacency)
            # Also count nodes reachable from START
            reachable |= _reachable_from("START", adjacency)
            for gn in self.graph_nodes:
                if gn.id not in reachable:
                    errors.append(
                        f"Graph node '{gn.id}' is not reachable from "
                        f"entry point '{self.entry_point}'."
                    )

        # Cycle detection: check that every cycle has a path to END
        if seen_graph and not errors:
            # Only run if no structural errors so adjacency is valid
            cycle_nodes = _nodes_that_cannot_reach(
                "END", seen_graph, adjacency
            )
            if cycle_nodes:
                errors.append(
                    f"Nodes in cycle without exit condition: "
                    f"{', '.join(sorted(cycle_nodes))}."
                )

        # Check state schema field names are unique (basic check on raw dicts)
        field_names: set[str] = set()
        for f in self.state_schema:
            name = f.get("name", "")
            if name:
                if name in field_names:
                    errors.append(f"Duplicate state field name: '{name}'.")
                field_names.add(name)

        return errors

    def fork(
        self,
        new_name: str = "",
        author: str = "anonymous",
    ) -> BranchDefinition:
        """Create a forked copy of this branch definition.

        The fork gets a new ID, resets version to 1, and records
        this branch as its parent for lineage tracking.
        """
        forked = BranchDefinition.from_dict(self.to_dict())
        forked.branch_def_id = _new_id()
        forked.name = new_name or f"{self.name} (fork)"
        forked.author = author
        forked.version = 1
        forked.parent_def_id = self.branch_def_id
        forked.published = False
        forked.created_at = _now_iso()
        forked.updated_at = _now_iso()
        forked.stats = {"fork_count": 0, "run_count": 0, "avg_quality_score": 0.0}
        return forked
