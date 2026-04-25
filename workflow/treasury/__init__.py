"""workflow.treasury — Platform fee, bounty pool, and designer royalty primitives.

Schema (schema.py): treasury_balance / bounty_pool_balance / royalty_payout DDL.
Distribution math (distribution.py): pure functions, no I/O.
Persistence wiring + MCP surface come in follow-ups post-sweep.
"""

from __future__ import annotations

from workflow.treasury.distribution import (
    BOUNTY_POOL_SHARE_BP,
    PLATFORM_TAKE_BP,
    TREASURY_SHARE_BP,
    compute_bounty_allocation,
    compute_royalty_share,
    compute_take,
    compute_treasury_retained,
    net_after_take,
    split_take,
)
from workflow.treasury.schema import (
    TREASURY_SCHEMA,
    BountyAllocation,
    RoyaltyPayment,
    TreasuryEntry,
    migrate_treasury_schema,
)

__all__ = [
    # distribution.py
    "BOUNTY_POOL_SHARE_BP",
    "PLATFORM_TAKE_BP",
    "TREASURY_SHARE_BP",
    "compute_bounty_allocation",
    "compute_royalty_share",
    "compute_take",
    "compute_treasury_retained",
    "net_after_take",
    "split_take",
    # schema.py
    "TREASURY_SCHEMA",
    "BountyAllocation",
    "RoyaltyPayment",
    "TreasuryEntry",
    "migrate_treasury_schema",
]
