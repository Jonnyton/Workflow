"""NodeBid executor (Phase G).

Executes a single approved node against user-supplied inputs, with
no universe state piped in. Writes a JSON output artifact under
``<output_dir>/bid_outputs/<node_bid_id>/output.json`` and reports
an ``evidence_url`` pointing at that file.

Safety model:
- Node must be ``approved=True`` (host-reviewed).
- Source is scanned for an expanded ``_DANGEROUS_PATTERNS`` list on
  top of the compile-time check in ``graph_compiler``.
- The ``node_lookup_fn`` is injected by the caller — this module has
  no dependency on the universe_server or branch registry.

v1 scope: prompt_template nodes are NOT executed here (that would
need the provider stack). Only source_code nodes with a ``run(state)``
entry point are supported; prompt_template-only nodes return
``status="failed"`` with a clear error.
"""

from __future__ import annotations

import json
import logging
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from workflow.node_bid import NodeBid

logger = logging.getLogger(__name__)


# Preflight §4.1 #5d single source of truth: the stricter bid-market
# pattern list lives at ``workflow.graph_compiler._BID_DANGEROUS_PATTERNS``.
# Both the producer and the executor re-validate against it (invariant 1
# requires both boundaries).
from workflow.graph_compiler import (  # noqa: E402
    _BID_DANGEROUS_PATTERNS as _DANGEROUS_PATTERNS,
)


@dataclass
class NodeBidResult:
    node_bid_id: str
    status: str  # "succeeded" | "failed"
    output: dict = field(default_factory=dict)
    evidence_url: str = ""
    error: str = ""


def _strip_producer_keys(inputs: dict) -> dict:
    """Remove ``__``-prefixed producer-internal keys before passing
    inputs to the node body."""
    return {k: v for k, v in inputs.items() if not str(k).startswith("__")}


def _scan_dangerous_patterns(source: str) -> str:
    """Return the offending pattern or empty string."""
    for pattern in _DANGEROUS_PATTERNS:
        if pattern in source:
            return pattern
    return ""


def execute_node_bid(
    bid: NodeBid,
    *,
    node_lookup_fn: Callable[[str], object | None],
    output_dir: Path,
) -> NodeBidResult:
    """Execute a single NodeBid. Never raises — all failures return a
    ``NodeBidResult`` with ``status="failed"``.

    Parameters
    ----------
    bid:
        The NodeBid to execute.
    node_lookup_fn:
        Callable ``(node_def_id: str) -> NodeDefinition | None``. The
        caller controls how nodes are resolved (registry, branch,
        discovery) — keeps this module dependency-free.
    output_dir:
        Universe output directory. The result artifact is written
        under ``<output_dir>/bid_outputs/<bid_id>/output.json``.
    """
    node_bid_id = bid.node_bid_id
    artifact_dir = Path(output_dir) / "bid_outputs" / node_bid_id
    try:
        node = node_lookup_fn(bid.node_def_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("node_bid: lookup raised for %s: %s", bid.node_def_id, exc)
        return NodeBidResult(
            node_bid_id=node_bid_id,
            status="failed",
            error=f"node_lookup_error: {exc}",
        )

    if node is None:
        return NodeBidResult(
            node_bid_id=node_bid_id,
            status="failed",
            error=f"node_not_found: {bid.node_def_id}",
        )

    # Approval gate — required.
    approved = bool(getattr(node, "approved", False))
    if not approved:
        return NodeBidResult(
            node_bid_id=node_bid_id,
            status="failed",
            error=f"unapproved_node: {bid.node_def_id}",
        )

    source = getattr(node, "source_code", "") or ""
    prompt_template = getattr(node, "prompt_template", "") or ""

    if not source and prompt_template:
        return NodeBidResult(
            node_bid_id=node_bid_id,
            status="failed",
            error=(
                "prompt_template_nodes_not_supported: NodeBid execution "
                "v1 only supports source_code nodes with a run(state) entry"
            ),
        )
    if not source:
        return NodeBidResult(
            node_bid_id=node_bid_id,
            status="failed",
            error="node_has_no_source_code",
        )

    offending = _scan_dangerous_patterns(source)
    if offending:
        return NodeBidResult(
            node_bid_id=node_bid_id,
            status="failed",
            error=f"dangerous_pattern:{offending}",
        )

    # Strip producer-internal keys before exposing to node body.
    user_inputs = _strip_producer_keys(dict(bid.inputs or {}))

    # Execute source — define runner, call run(state).
    local_scope: dict = {}
    try:
        exec(  # noqa: S102 — approved source with expanded pattern scan
            source,
            {"__builtins__": __builtins__},
            local_scope,
        )
    except Exception as exc:  # noqa: BLE001
        return NodeBidResult(
            node_bid_id=node_bid_id,
            status="failed",
            error=f"source_load_error: {exc}",
        )

    runner = local_scope.get("run")
    if not callable(runner):
        return NodeBidResult(
            node_bid_id=node_bid_id,
            status="failed",
            error="source_missing_run_callable",
        )

    try:
        result = runner(dict(user_inputs))
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "node_bid: run raised for %s: %s\n%s",
            node_bid_id, exc, traceback.format_exc(),
        )
        return NodeBidResult(
            node_bid_id=node_bid_id,
            status="failed",
            error=f"run_error: {exc}",
        )

    if not isinstance(result, dict):
        return NodeBidResult(
            node_bid_id=node_bid_id,
            status="failed",
            error=f"run_returned_non_dict: {type(result).__name__}",
        )

    # Write artifact.
    try:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        out_file = artifact_dir / "output.json"
        out_file.write_text(
            json.dumps(result, indent=2, default=str),
            encoding="utf-8",
        )
        evidence_url = f"file://{out_file.resolve().as_posix()}"
    except Exception as exc:  # noqa: BLE001
        return NodeBidResult(
            node_bid_id=node_bid_id,
            status="failed",
            error=f"artifact_write_error: {exc}",
            output=result,
        )

    return NodeBidResult(
        node_bid_id=node_bid_id,
        status="succeeded",
        output=result,
        evidence_url=evidence_url,
    )
