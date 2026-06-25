"""E2E withdrawal-bridge tests through the extensions() MCP surface (Slice 1a).

set_wallet -> fund -> withdraw: spendable balance settles OUT via the configured
backend (internal marker by default; mock base_sepolia USDC under env), debiting
the off-chain balance and recording a settlement_batch + transaction_log entry.
No network — the base_sepolia backend uses the mock on-chain client.
"""

from __future__ import annotations

import json
from pathlib import Path

ADDR = "0x" + "1" * 40


def _init(base_path: Path) -> None:
    from workflow.daemon_server import initialize_author_server
    initialize_author_server(base_path)


def _ext(monkeypatch, tmp_path, *, user="alice", paid_market=True, backend=None, **kwargs):
    monkeypatch.setenv("WORKFLOW_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("WORKFLOW_PAID_MARKET", "on" if paid_market else "off")
    monkeypatch.setenv("UNIVERSE_SERVER_USER", user)
    if backend is not None:
        monkeypatch.setenv("WORKFLOW_SETTLEMENT_BACKEND", backend)
    else:
        monkeypatch.delenv("WORKFLOW_SETTLEMENT_BACKEND", raising=False)
    from workflow.universe_server import extensions
    return json.loads(extensions(**kwargs))


class TestWithdrawE2E:
    def test_set_wallet_fund_withdraw_internal(self, tmp_path, monkeypatch):
        _init(tmp_path)
        wallet = _ext(monkeypatch, tmp_path, action="escrow_set_wallet",
                      escrow_wallet_address=ADDR)
        assert wallet["status"] == "ok"
        assert wallet["address"] == ADDR

        _ext(monkeypatch, tmp_path, action="escrow_fund", escrow_amount=1_000_000)
        wd = _ext(monkeypatch, tmp_path, action="escrow_withdraw", escrow_amount=600_000)
        assert wd["status"] == "ok"
        assert wd["backend"] == "internal"
        assert wd["tx_ref"].startswith("internal-")
        assert wd["amount"] == 600_000
        assert wd["recipient_wallet"] == ADDR
        assert wd["remaining_spendable"] == 400_000

        bal = _ext(monkeypatch, tmp_path, action="escrow_balance")
        assert bal["total"] == 400_000

    def test_withdraw_base_sepolia_mock(self, tmp_path, monkeypatch):
        _init(tmp_path)
        _ext(monkeypatch, tmp_path, action="escrow_set_wallet", escrow_wallet_address=ADDR)
        _ext(monkeypatch, tmp_path, action="escrow_fund", escrow_amount=1_000_000)
        wd = _ext(monkeypatch, tmp_path, backend="base_sepolia",
                  action="escrow_withdraw", escrow_amount=1_000_000)
        assert wd["status"] == "ok"
        assert wd["backend"] == "base_sepolia"
        assert wd["settlement_status"] == "submitted"
        assert wd["tx_ref"].startswith("0xMOCK")
        assert wd["chain_id"] == 84532

    def test_withdraw_without_wallet_rejected(self, tmp_path, monkeypatch):
        _init(tmp_path)
        _ext(monkeypatch, tmp_path, action="escrow_fund", escrow_amount=1_000_000)
        wd = _ext(monkeypatch, tmp_path, action="escrow_withdraw", escrow_amount=100)
        assert wd["status"] == "rejected"
        assert "payout wallet" in wd["error"].lower()

    def test_withdraw_insufficient_balance_rejected(self, tmp_path, monkeypatch):
        _init(tmp_path)
        _ext(monkeypatch, tmp_path, action="escrow_set_wallet", escrow_wallet_address=ADDR)
        _ext(monkeypatch, tmp_path, action="escrow_fund", escrow_amount=100)
        wd = _ext(monkeypatch, tmp_path, action="escrow_withdraw", escrow_amount=1_000)
        assert wd["status"] == "rejected"
        assert "insufficient" in wd["error"].lower()
        # Balance untouched on rejection.
        bal = _ext(monkeypatch, tmp_path, action="escrow_balance")
        assert bal["total"] == 100

    def test_set_wallet_invalid_address_rejected(self, tmp_path, monkeypatch):
        _init(tmp_path)
        out = _ext(monkeypatch, tmp_path, action="escrow_set_wallet",
                   escrow_wallet_address="not-an-address")
        assert out["status"] == "rejected"
        assert "address" in out["error"].lower()

    def test_withdraw_requires_paid_market(self, tmp_path, monkeypatch):
        _init(tmp_path)
        out = _ext(monkeypatch, tmp_path, paid_market=False,
                   action="escrow_withdraw", escrow_amount=100)
        assert out["status"] == "not_available"


class TestWithdrawIdempotency:
    """slice1a review HIGH 4: a retry of a withdrawal (same idempotency key)
    must NOT debit balance or pay out twice."""

    def _count_batches(self, tmp_path, monkeypatch, batch_id):
        import sqlite3

        from workflow.storage import db_path
        conn = sqlite3.connect(str(db_path(tmp_path)))
        try:
            return conn.execute(
                "SELECT COUNT(*) FROM settlement_batch WHERE batch_id = ?",
                (batch_id,),
            ).fetchone()[0]
        finally:
            conn.close()

    def test_retry_with_client_key_does_not_double_pay(self, tmp_path, monkeypatch):
        _init(tmp_path)
        _ext(monkeypatch, tmp_path, action="escrow_set_wallet",
             escrow_wallet_address=ADDR)
        _ext(monkeypatch, tmp_path, action="escrow_fund", escrow_amount=1_000_000)

        first = _ext(monkeypatch, tmp_path, action="escrow_withdraw",
                     escrow_amount=600_000, escrow_idempotency_key="req-42")
        assert first["status"] == "ok"
        assert first.get("idempotent_replay") is False
        assert first["amount"] == 600_000

        bal_after_first = _ext(monkeypatch, tmp_path, action="escrow_balance")
        assert bal_after_first["total"] == 400_000

        # Client retries the SAME request (didn't see the first result).
        retry = _ext(monkeypatch, tmp_path, action="escrow_withdraw",
                     escrow_amount=600_000, escrow_idempotency_key="req-42")
        assert retry["status"] == "ok"
        assert retry["idempotent_replay"] is True
        assert retry["batch_id"] == first["batch_id"]
        assert retry["tx_ref"] == first["tx_ref"]

        # Balance debited exactly ONCE; one batch row only.
        bal_after_retry = _ext(monkeypatch, tmp_path, action="escrow_balance")
        assert bal_after_retry["total"] == 400_000
        assert self._count_batches(tmp_path, monkeypatch, first["batch_id"]) == 1

    def test_retry_without_client_key_dedups_same_shape(self, tmp_path, monkeypatch):
        """Without an explicit key, a same-shape retry (same actor/amount/
        wallet/chain) still maps to the same operation — the safe default."""
        _init(tmp_path)
        _ext(monkeypatch, tmp_path, action="escrow_set_wallet",
             escrow_wallet_address=ADDR)
        _ext(monkeypatch, tmp_path, action="escrow_fund", escrow_amount=1_000_000)

        first = _ext(monkeypatch, tmp_path, action="escrow_withdraw",
                     escrow_amount=250_000)
        assert first["status"] == "ok"
        assert first.get("idempotent_replay") is False

        retry = _ext(monkeypatch, tmp_path, action="escrow_withdraw",
                     escrow_amount=250_000)
        assert retry["idempotent_replay"] is True
        assert retry["batch_id"] == first["batch_id"]

        bal = _ext(monkeypatch, tmp_path, action="escrow_balance")
        # Debited once (1_000_000 - 250_000), not twice.
        assert bal["total"] == 750_000

    def test_distinct_client_keys_allow_separate_withdrawals(self, tmp_path, monkeypatch):
        _init(tmp_path)
        _ext(monkeypatch, tmp_path, action="escrow_set_wallet",
             escrow_wallet_address=ADDR)
        _ext(monkeypatch, tmp_path, action="escrow_fund", escrow_amount=1_000_000)

        a = _ext(monkeypatch, tmp_path, action="escrow_withdraw",
                 escrow_amount=200_000, escrow_idempotency_key="wd-a")
        b = _ext(monkeypatch, tmp_path, action="escrow_withdraw",
                 escrow_amount=200_000, escrow_idempotency_key="wd-b")
        assert a["status"] == "ok" and b["status"] == "ok"
        assert a["batch_id"] != b["batch_id"]
        assert b["idempotent_replay"] is False

        bal = _ext(monkeypatch, tmp_path, action="escrow_balance")
        # Two distinct withdrawals both debited.
        assert bal["total"] == 600_000
