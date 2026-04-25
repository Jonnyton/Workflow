"""Settlement schema — DDL and dataclasses for the paid-market settlement layer.

Spec: project_monetization_crypto_1pct + project_node_escrow_and_abandonment.

Four tables:
  escrow_balance     — per-node locked funds (node is the escrow holder)
  pending_settlement — individual settlement events awaiting batch or direct settle
  settlement_batch   — grouped settlements flushed together (sub-$1 batching)
  transaction_log    — immutable append-only audit trail for every state change

Treasury fee (1%) is computed at settlement time from MicroToken.treasury_fee().
Batch threshold: pending_settlements with amount < 1 Token defer to a batch.

All amounts are stored as INTEGER (MicroTokens) — never REAL/FLOAT.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from workflow.payments.identifiers import ActorId, MicroToken, NodeId, RunId

# ── Status enums ──────────────────────────────────────────────────────────────

EscrowBalanceStatus = Literal["locked", "released", "refunded", "partial"]
SettlementStatus = Literal["pending", "batched", "settled", "cancelled"]
BatchStatus = Literal["open", "flushed", "failed"]
TransactionKind = Literal[
    "lock", "release", "refund", "fee", "checkpoint_partial", "batch_flush"
]

# ── DDL ───────────────────────────────────────────────────────────────────────

SETTLEMENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS escrow_balance (
    escrow_id       TEXT PRIMARY KEY,
    node_id         TEXT NOT NULL,
    run_id          TEXT NOT NULL,
    staker_id       TEXT NOT NULL,
    total_amount    INTEGER NOT NULL CHECK (total_amount >= 0),
    released_amount INTEGER NOT NULL DEFAULT 0 CHECK (released_amount >= 0),
    status          TEXT NOT NULL DEFAULT 'locked'
                        CHECK (status IN ('locked','released','refunded','partial')),
    locked_at       TEXT NOT NULL,
    resolved_at     TEXT,
    UNIQUE (node_id, run_id, staker_id)
);

CREATE INDEX IF NOT EXISTS idx_escrow_node
    ON escrow_balance(node_id);

CREATE INDEX IF NOT EXISTS idx_escrow_run
    ON escrow_balance(run_id);

CREATE TABLE IF NOT EXISTS pending_settlement (
    settlement_id   TEXT PRIMARY KEY,
    escrow_id       TEXT NOT NULL REFERENCES escrow_balance(escrow_id),
    recipient_id    TEXT NOT NULL,
    amount          INTEGER NOT NULL CHECK (amount >= 0),
    treasury_fee    INTEGER NOT NULL DEFAULT 0 CHECK (treasury_fee >= 0),
    net_amount      INTEGER NOT NULL DEFAULT 0 CHECK (net_amount >= 0),
    status          TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','batched','settled','cancelled')),
    event_type      TEXT NOT NULL DEFAULT 'completion',
    settlement_key  TEXT NOT NULL UNIQUE,
    created_at      TEXT NOT NULL,
    settled_at      TEXT,
    batch_id        TEXT
);

CREATE INDEX IF NOT EXISTS idx_settlement_escrow
    ON pending_settlement(escrow_id);

CREATE INDEX IF NOT EXISTS idx_settlement_status
    ON pending_settlement(status);

CREATE TABLE IF NOT EXISTS settlement_batch (
    batch_id        TEXT PRIMARY KEY,
    recipient_id    TEXT NOT NULL,
    total_amount    INTEGER NOT NULL DEFAULT 0 CHECK (total_amount >= 0),
    total_fee       INTEGER NOT NULL DEFAULT 0 CHECK (total_fee >= 0),
    item_count      INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open','flushed','failed')),
    opened_at       TEXT NOT NULL,
    flushed_at      TEXT
);

CREATE INDEX IF NOT EXISTS idx_batch_recipient
    ON settlement_batch(recipient_id);

CREATE INDEX IF NOT EXISTS idx_batch_status
    ON settlement_batch(status);

CREATE TABLE IF NOT EXISTS transaction_log (
    tx_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    kind            TEXT NOT NULL
                        CHECK (kind IN (
                            'lock','release','refund','fee',
                            'checkpoint_partial','batch_flush'
                        )),
    escrow_id       TEXT,
    settlement_id   TEXT,
    batch_id        TEXT,
    actor_id        TEXT NOT NULL,
    amount          INTEGER NOT NULL DEFAULT 0,
    recorded_at     TEXT NOT NULL,
    note            TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_txlog_escrow
    ON transaction_log(escrow_id);

CREATE INDEX IF NOT EXISTS idx_txlog_recorded
    ON transaction_log(recorded_at);
"""

# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class EscrowEntry:
    """One node's locked escrow balance."""

    escrow_id: str
    node_id: NodeId
    run_id: RunId
    staker_id: ActorId
    total_amount: MicroToken
    released_amount: MicroToken
    status: EscrowBalanceStatus
    locked_at: str
    resolved_at: str | None = None

    def __post_init__(self) -> None:
        if int(self.released_amount) > int(self.total_amount):
            raise ValueError(
                f"released_amount ({self.released_amount}) cannot exceed "
                f"total_amount ({self.total_amount})"
            )

    @property
    def remaining(self) -> MicroToken:
        return MicroToken(int(self.total_amount) - int(self.released_amount))

    @property
    def is_fully_released(self) -> bool:
        return int(self.released_amount) >= int(self.total_amount)

    @classmethod
    def from_row(cls, row: dict) -> EscrowEntry:
        return cls(
            escrow_id=row["escrow_id"],
            node_id=NodeId(row["node_id"]),
            run_id=RunId(row["run_id"]),
            staker_id=ActorId(row["staker_id"]),
            total_amount=MicroToken(int(row["total_amount"])),
            released_amount=MicroToken(int(row.get("released_amount") or 0)),
            status=row.get("status") or "locked",  # type: ignore[arg-type]
            locked_at=row["locked_at"],
            resolved_at=row.get("resolved_at"),
        )


@dataclass
class Settlement:
    """One pending or completed settlement event."""

    settlement_id: str
    escrow_id: str
    recipient_id: ActorId
    amount: MicroToken
    treasury_fee: MicroToken
    net_amount: MicroToken
    status: SettlementStatus
    event_type: str
    settlement_key: str
    created_at: str
    settled_at: str | None = None
    batch_id: str | None = None

    def __post_init__(self) -> None:
        expected_net = MicroToken(int(self.amount) - int(self.treasury_fee))
        if int(self.net_amount) != int(expected_net):
            raise ValueError(
                f"net_amount ({self.net_amount}) must equal "
                f"amount - treasury_fee ({self.amount} - {self.treasury_fee} "
                f"= {expected_net})"
            )

    @property
    def is_batchable(self) -> bool:
        return self.amount.is_batchable()

    @classmethod
    def build(
        cls,
        *,
        settlement_id: str,
        escrow_id: str,
        recipient_id: str,
        amount: int,
        event_type: str,
        settlement_key: str,
        created_at: str,
    ) -> Settlement:
        """Construct Settlement with auto-computed fee and net_amount."""
        amt = MicroToken(amount)
        fee = amt.treasury_fee()
        net = amt.net_after_fee()
        return cls(
            settlement_id=settlement_id,
            escrow_id=escrow_id,
            recipient_id=ActorId(recipient_id),
            amount=amt,
            treasury_fee=fee,
            net_amount=net,
            status="pending",
            event_type=event_type,
            settlement_key=settlement_key,
            created_at=created_at,
        )

    @classmethod
    def from_row(cls, row: dict) -> Settlement:
        return cls(
            settlement_id=row["settlement_id"],
            escrow_id=row["escrow_id"],
            recipient_id=ActorId(row["recipient_id"]),
            amount=MicroToken(int(row["amount"])),
            treasury_fee=MicroToken(int(row.get("treasury_fee") or 0)),
            net_amount=MicroToken(int(row.get("net_amount") or 0)),
            status=row.get("status") or "pending",  # type: ignore[arg-type]
            event_type=row.get("event_type") or "completion",
            settlement_key=row["settlement_key"],
            created_at=row["created_at"],
            settled_at=row.get("settled_at"),
            batch_id=row.get("batch_id"),
        )


@dataclass
class BatchedTransaction:
    """Grouped settlement batch for sub-threshold amounts."""

    batch_id: str
    recipient_id: ActorId
    total_amount: MicroToken
    total_fee: MicroToken
    item_count: int
    status: BatchStatus
    opened_at: str
    flushed_at: str | None = None
    items: list[str] = field(default_factory=list)

    @property
    def net_amount(self) -> MicroToken:
        return MicroToken(int(self.total_amount) - int(self.total_fee))

    @property
    def is_flushable(self) -> bool:
        return not self.total_amount.is_batchable()

    @classmethod
    def from_row(cls, row: dict) -> BatchedTransaction:
        return cls(
            batch_id=row["batch_id"],
            recipient_id=ActorId(row["recipient_id"]),
            total_amount=MicroToken(int(row.get("total_amount") or 0)),
            total_fee=MicroToken(int(row.get("total_fee") or 0)),
            item_count=int(row.get("item_count") or 0),
            status=row.get("status") or "open",  # type: ignore[arg-type]
            opened_at=row["opened_at"],
            flushed_at=row.get("flushed_at"),
        )


# ── Migration ─────────────────────────────────────────────────────────────────

def migrate_settlement_schema(conn) -> None:  # type: ignore[no-untyped-def]
    """Create settlement tables if absent. Idempotent."""
    conn.executescript(SETTLEMENT_SCHEMA)
