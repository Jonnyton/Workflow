"""workflow.attribution — Attribution chain and remix provenance primitives.

Schema layer (schema.py): attribution_edge / attribution_credit DDL and dataclasses.
Persistence, MCP surface, and share-calculation logic come in follow-ups once
the spec is promoted from deferred status.
"""

from __future__ import annotations

from workflow.attribution.schema import (
    ATTRIBUTION_SCHEMA,
    AttributionCredit,
    AttributionEdge,
    ContributionKind,
    RemixProvenance,
    migrate_attribution_schema,
)

__all__ = [
    "ATTRIBUTION_SCHEMA",
    "AttributionCredit",
    "AttributionEdge",
    "ContributionKind",
    "RemixProvenance",
    "migrate_attribution_schema",
]
