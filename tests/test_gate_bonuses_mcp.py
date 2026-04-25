"""Tests for gate bonus MCP actions: stake_bonus, unstake_bonus, release_bonus.

Spec: docs/vetted-specs.md §Gate bonuses — staked payouts attached to gate milestones.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

# ── helpers ───────────────────────────────────────────────────────────────────

def _seed_goal_and_claim(base_path: Path) -> tuple[str, str, str]:
    """Insert a gate claim directly into the DB.

    Returns (goal_id, branch_def_id, claim_id).
    The bonus handlers only need the gate_claims table row.
    """
    from workflow.daemon_server import initialize_author_server
    from workflow.gates.schema import migrate_gate_bonus_columns
    from workflow.storage import _connect

    initialize_author_server(base_path)

    goal_id = f"goal-{uuid.uuid4().hex[:8]}"
    bid = f"branch-{uuid.uuid4().hex[:8]}"
    claim_id = f"claim-{uuid.uuid4().hex[:8]}"
    now_iso = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()

    with _connect(base_path) as conn:
        migrate_gate_bonus_columns(conn)
        conn.execute(
            """
            INSERT INTO gate_claims
                (claim_id, branch_def_id, goal_id, rung_key,
                 evidence_url, evidence_note, claimed_by, claimed_at,
                 retracted_at, retracted_reason)
            VALUES (?, ?, ?, 'rung1', 'https://example.com/ev', '', 'test_user', ?, NULL, '')
            """,
            (claim_id, bid, goal_id, now_iso),
        )
    return goal_id, bid, claim_id


def _gates(monkeypatch, tmp_path, **kwargs):
    """Call gates() with GATES_ENABLED + WORKFLOW_PAID_MARKET set."""
    monkeypatch.setenv("WORKFLOW_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("GATES_ENABLED", "1")
    monkeypatch.setenv("WORKFLOW_PAID_MARKET", "on")
    monkeypatch.setenv("UNIVERSE_SERVER_USER", "test_user")
    from workflow.universe_server import gates
    return json.loads(gates(**kwargs))


# ── stake_bonus ───────────────────────────────────────────────────────────────

class TestStakeBonus:
    def test_stake_bonus_success(self, tmp_path, monkeypatch):
        _, _, claim_id = _seed_goal_and_claim(tmp_path)
        result = _gates(monkeypatch, tmp_path,
                        action="stake_bonus",
                        claim_id=claim_id,
                        bonus_stake=1000,
                        node_id="n1")
        assert result["status"] == "ok"
        assert result["bonus_stake"] == 1000
        assert result["claim_id"] == claim_id

    def test_stake_bonus_requires_paid_market(self, tmp_path, monkeypatch):
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(tmp_path))
        monkeypatch.setenv("GATES_ENABLED", "1")
        monkeypatch.setenv("WORKFLOW_PAID_MARKET", "off")
        from workflow.universe_server import gates
        result = json.loads(gates(action="stake_bonus", claim_id="x", bonus_stake=100))
        assert result["status"] == "not_available"

    def test_stake_bonus_rejects_zero_stake(self, tmp_path, monkeypatch):
        _, _, claim_id = _seed_goal_and_claim(tmp_path)
        result = _gates(monkeypatch, tmp_path,
                        action="stake_bonus",
                        claim_id=claim_id,
                        bonus_stake=0)
        assert result["status"] == "rejected"

    def test_stake_bonus_rejects_negative_stake(self, tmp_path, monkeypatch):
        _, _, claim_id = _seed_goal_and_claim(tmp_path)
        result = _gates(monkeypatch, tmp_path,
                        action="stake_bonus",
                        claim_id=claim_id,
                        bonus_stake=-50,
                        node_id="n1")
        assert result["status"] == "rejected"

    def test_stake_bonus_rejects_missing_claim_id(self, tmp_path, monkeypatch):
        _seed_goal_and_claim(tmp_path)
        result = _gates(monkeypatch, tmp_path,
                        action="stake_bonus",
                        bonus_stake=100)
        assert result["status"] == "rejected"
        assert "claim_id" in result["error"].lower()

    def test_stake_bonus_rejects_missing_node_id(self, tmp_path, monkeypatch):
        _, _, claim_id = _seed_goal_and_claim(tmp_path)
        result = _gates(monkeypatch, tmp_path,
                        action="stake_bonus",
                        claim_id=claim_id,
                        bonus_stake=100)
        assert result["status"] == "rejected"
        assert "node_id" in result["error"].lower()

    def test_stake_bonus_rejects_unknown_claim(self, tmp_path, monkeypatch):
        _seed_goal_and_claim(tmp_path)
        result = _gates(monkeypatch, tmp_path,
                        action="stake_bonus",
                        claim_id="does-not-exist",
                        bonus_stake=100,
                        node_id="n1")
        assert result["status"] == "rejected"
        assert "not found" in result["error"].lower()

    def test_stake_bonus_rejects_branch_scope(self, tmp_path, monkeypatch):
        _, _, claim_id = _seed_goal_and_claim(tmp_path)
        result = _gates(monkeypatch, tmp_path,
                        action="stake_bonus",
                        claim_id=claim_id,
                        bonus_stake=100,
                        node_id="n1",
                        attachment_scope="branch")
        assert result["status"] == "rejected"
        assert "not yet implemented" in result["error"].lower()

    def test_stake_bonus_rejects_double_stake(self, tmp_path, monkeypatch):
        _, _, claim_id = _seed_goal_and_claim(tmp_path)
        _gates(monkeypatch, tmp_path,
               action="stake_bonus",
               claim_id=claim_id,
               bonus_stake=500,
               node_id="n1")
        result = _gates(monkeypatch, tmp_path,
                        action="stake_bonus",
                        claim_id=claim_id,
                        bonus_stake=200,
                        node_id="n1")
        assert result["status"] == "rejected"
        assert "already" in result["error"].lower()


# ── unstake_bonus ─────────────────────────────────────────────────────────────

class TestUnstakeBonus:
    def test_unstake_after_stake(self, tmp_path, monkeypatch):
        _, _, claim_id = _seed_goal_and_claim(tmp_path)
        _gates(monkeypatch, tmp_path,
               action="stake_bonus",
               claim_id=claim_id,
               bonus_stake=1000,
               node_id="n1")
        result = _gates(monkeypatch, tmp_path,
                        action="unstake_bonus",
                        claim_id=claim_id)
        assert result["status"] == "ok"
        assert result["refunded"] == 1000
        assert result["refunded_to"] == "test_user"

    def test_unstake_rejects_wrong_actor(self, tmp_path, monkeypatch):
        _, _, claim_id = _seed_goal_and_claim(tmp_path)
        _gates(monkeypatch, tmp_path,
               action="stake_bonus",
               claim_id=claim_id,
               bonus_stake=500,
               node_id="n1")
        monkeypatch.setenv("UNIVERSE_SERVER_USER", "other_user")
        from workflow.universe_server import gates
        result = json.loads(gates(action="unstake_bonus", claim_id=claim_id))
        assert result["status"] == "rejected"
        assert "not authorized" in result["error"].lower()

    def test_unstake_rejects_no_stake(self, tmp_path, monkeypatch):
        _, _, claim_id = _seed_goal_and_claim(tmp_path)
        result = _gates(monkeypatch, tmp_path,
                        action="unstake_bonus",
                        claim_id=claim_id)
        assert result["status"] == "rejected"

    def test_unstake_rejects_unknown_claim(self, tmp_path, monkeypatch):
        _seed_goal_and_claim(tmp_path)
        result = _gates(monkeypatch, tmp_path,
                        action="unstake_bonus",
                        claim_id="no-such-claim")
        assert result["status"] == "rejected"


# ── release_bonus ─────────────────────────────────────────────────────────────

class TestReleaseBonus:
    def test_release_on_pass_goes_to_node_last_claimer(self, tmp_path, monkeypatch):
        _, _, claim_id = _seed_goal_and_claim(tmp_path)
        _gates(monkeypatch, tmp_path,
               action="stake_bonus",
               claim_id=claim_id,
               bonus_stake=1000,
               node_id="n1")
        result = _gates(monkeypatch, tmp_path,
                        action="release_bonus",
                        claim_id=claim_id,
                        eval_verdict="pass",
                        node_last_claimer="daemon_holder")
        assert result["status"] == "ok"
        assert result["disposition"] == "released"
        assert result["recipient"] == "daemon_holder"
        assert result["net_disbursed"] + result["treasury_take"] == 1000

    def test_release_on_fail_refunds_to_staker(self, tmp_path, monkeypatch):
        _, _, claim_id = _seed_goal_and_claim(tmp_path)
        _gates(monkeypatch, tmp_path,
               action="stake_bonus",
               claim_id=claim_id,
               bonus_stake=800,
               node_id="n1")
        result = _gates(monkeypatch, tmp_path,
                        action="release_bonus",
                        claim_id=claim_id,
                        eval_verdict="fail",
                        node_last_claimer="daemon_holder")
        assert result["status"] == "ok"
        assert result["disposition"] == "refunded"
        assert result["recipient"] == "test_user"

    def test_release_rejects_missing_verdict(self, tmp_path, monkeypatch):
        _, _, claim_id = _seed_goal_and_claim(tmp_path)
        _gates(monkeypatch, tmp_path,
               action="stake_bonus",
               claim_id=claim_id,
               bonus_stake=500,
               node_id="n1")
        result = _gates(monkeypatch, tmp_path,
                        action="release_bonus",
                        claim_id=claim_id,
                        node_last_claimer="daemon_holder")
        assert result["status"] == "rejected"
        assert "eval_verdict" in result["error"].lower()

    def test_release_rejects_invalid_verdict(self, tmp_path, monkeypatch):
        _, _, claim_id = _seed_goal_and_claim(tmp_path)
        _gates(monkeypatch, tmp_path,
               action="stake_bonus",
               claim_id=claim_id,
               bonus_stake=500,
               node_id="n1")
        result = _gates(monkeypatch, tmp_path,
                        action="release_bonus",
                        claim_id=claim_id,
                        eval_verdict="maybe",
                        node_last_claimer="daemon_holder")
        assert result["status"] == "rejected"

    def test_release_rejects_no_stake(self, tmp_path, monkeypatch):
        _, _, claim_id = _seed_goal_and_claim(tmp_path)
        result = _gates(monkeypatch, tmp_path,
                        action="release_bonus",
                        claim_id=claim_id,
                        eval_verdict="pass",
                        node_last_claimer="daemon_holder")
        assert result["status"] == "rejected"
        assert "no bonus" in result["error"].lower()

    def test_release_rejects_missing_node_last_claimer(self, tmp_path, monkeypatch):
        _, _, claim_id = _seed_goal_and_claim(tmp_path)
        _gates(monkeypatch, tmp_path,
               action="stake_bonus",
               claim_id=claim_id,
               bonus_stake=500,
               node_id="n1")
        result = _gates(monkeypatch, tmp_path,
                        action="release_bonus",
                        claim_id=claim_id,
                        eval_verdict="pass")
        assert result["status"] == "rejected"

    def test_payout_invariant_net_plus_treasury_equals_stake(self, tmp_path, monkeypatch):
        """net + treasury == original stake for any verdict."""
        _, _, claim_id = _seed_goal_and_claim(tmp_path)
        stake = 9999
        _gates(monkeypatch, tmp_path,
               action="stake_bonus",
               claim_id=claim_id,
               bonus_stake=stake,
               node_id="n1")
        result = _gates(monkeypatch, tmp_path,
                        action="release_bonus",
                        claim_id=claim_id,
                        eval_verdict="pass",
                        node_last_claimer="daemon_holder")
        assert result["net_disbursed"] + result["treasury_take"] == stake


# ── Pure business logic unit tests ────────────────────────────────────────────

class TestGatesActionsUnit:
    """Unit tests for workflow/gates/actions.py business logic (no MCP layer)."""

    def test_validate_stake_amount_valid(self):
        from workflow.gates.actions import validate_stake_amount
        stake, err = validate_stake_amount(500)
        assert stake == 500
        assert err is None

    def test_validate_stake_amount_zero(self):
        from workflow.gates.actions import validate_stake_amount
        stake, err = validate_stake_amount(0)
        assert stake == 0
        assert err is None

    def test_validate_stake_amount_negative_rejected(self):
        from workflow.gates.actions import validate_stake_amount
        stake, err = validate_stake_amount(-1)
        assert err is not None

    def test_validate_stake_amount_non_numeric_rejected(self):
        from workflow.gates.actions import validate_stake_amount
        _, err = validate_stake_amount("abc")
        assert err is not None

    def test_compute_bonus_payout_invariant(self):
        from workflow.gates.actions import compute_bonus_payout
        for stake in range(0, 10_001, 100):
            net, treasury = compute_bonus_payout(stake)
            assert net + treasury == stake, f"invariant broken at stake={stake}"

    def test_compute_bonus_payout_1pct_take(self):
        from workflow.gates.actions import compute_bonus_payout
        net, treasury = compute_bonus_payout(10_000)
        assert treasury == 100
        assert net == 9_900
