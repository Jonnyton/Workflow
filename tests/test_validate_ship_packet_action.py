"""Tests for ``extensions action=validate_ship_packet`` (PR #198 Phase 2A).

Wraps ``workflow.auto_ship.validate_ship_request`` as an MCP action so the
loop's release_safety_gate prompt and external callers (chatbots /
canaries) can reach it via tool. The validator itself is exercised
exhaustively in ``tests/test_auto_ship.py`` — these tests cover the
wrapper layer only.
"""

from __future__ import annotations

import json

import pytest

from workflow.api.auto_ship_actions import (
    _AUTO_SHIP_ACTIONS,
    _action_validate_ship_packet,
)
from workflow.api.extensions import _extensions_impl


# ── Wrapper layer (handler-level) ──────────────────────────────────────────


class TestHandlerLayer:
    def test_dispatch_dict_exposes_action(self):
        assert "validate_ship_packet" in _AUTO_SHIP_ACTIONS
        assert _AUTO_SHIP_ACTIONS["validate_ship_packet"] is _action_validate_ship_packet

    def test_missing_body_json_returns_error(self):
        result = json.loads(_action_validate_ship_packet({}))
        assert "error" in result
        assert "body_json" in result["error"]

    def test_empty_body_json_returns_error(self):
        result = json.loads(_action_validate_ship_packet({"body_json": ""}))
        assert "error" in result

    def test_whitespace_body_json_returns_error(self):
        result = json.loads(_action_validate_ship_packet({"body_json": "   "}))
        assert "error" in result

    def test_invalid_json_returns_parse_error(self):
        result = json.loads(_action_validate_ship_packet({"body_json": "not json"}))
        assert "error" in result
        assert "body_json is not valid JSON" in result["error"]

    def test_valid_packet_returns_decision_dict(self):
        packet = {
            "release_gate_result": "APPROVE_AUTO_SHIP",
            "ship_class": "docs_canary",
            "child_keep_reject_decision": "KEEP",
            "child_score": 9.5,
            "risk_level": "low",
            "blocked_execution_record": {},
            "stable_evidence_handle": "child_run:b:r",
            "automation_claim_status": "child_attached_with_handle",
            "rollback_plan": "Revert commit <sha>",
            "changed_paths": ["docs/autoship-canaries/x.md"],
            "diff": "+ added\n",
        }
        result = json.loads(_action_validate_ship_packet({
            "body_json": json.dumps(packet),
        }))
        assert result["validation_result"] == "passed"
        assert result["would_open_pr"] is True
        assert result["dry_run"] is True
        assert result["ship_status"] == "skipped"

    def test_blocked_packet_returns_decision_dict_with_violations(self):
        packet = {
            "release_gate_result": "HOLD",  # NOT approved
            "ship_class": "docs_canary",
            "child_keep_reject_decision": "REVIEW_READY",
            "stable_evidence_handle": "x",
            "automation_claim_status": "child_attached_with_handle",
            "rollback_plan": "y",
            "changed_paths": ["docs/autoship-canaries/x.md"],
            "diff": "x",
        }
        result = json.loads(_action_validate_ship_packet({
            "body_json": json.dumps(packet),
        }))
        assert result["validation_result"] == "blocked"
        assert result["would_open_pr"] is False
        assert len(result["violations"]) >= 1


# ── Dispatch via _extensions_impl ──────────────────────────────────────────


class TestDispatchIntegration:
    def test_action_routes_to_handler_via_extensions_dispatch(self):
        packet = {
            "release_gate_result": "APPROVE_AUTO_SHIP",
            "ship_class": "docs_canary",
            "child_keep_reject_decision": "KEEP",
            "child_score": 9.5,
            "risk_level": "low",
            "blocked_execution_record": {},
            "stable_evidence_handle": "child_run:b:r",
            "automation_claim_status": "child_attached_with_handle",
            "rollback_plan": "Revert commit <sha>",
            "changed_paths": ["docs/autoship-canaries/x.md"],
            "diff": "+ x\n",
        }
        result_str = _extensions_impl(
            action="validate_ship_packet",
            body_json=json.dumps(packet),
        )
        result = json.loads(result_str)
        assert result["validation_result"] == "passed"

    def test_action_with_no_body_json_routes_and_errors_at_handler(self):
        result_str = _extensions_impl(action="validate_ship_packet")
        result = json.loads(result_str)
        assert "error" in result
        assert "body_json" in result["error"]


# ── Wrapper resilience ─────────────────────────────────────────────────────


class TestResilience:
    def test_packet_that_makes_validator_raise_returns_error_dict_not_crash(self, monkeypatch):
        """Even if validate_ship_request unexpectedly raises, the wrapper
        returns a JSON error dict rather than letting MCP get a 500.
        """
        from workflow.api import auto_ship_actions as mod

        def boom(packet):
            raise RuntimeError("simulated validator failure")

        # Need to patch the import location used inside the handler.
        monkeypatch.setattr("workflow.auto_ship.validate_ship_request", boom)

        result = json.loads(_action_validate_ship_packet({
            "body_json": json.dumps({"any": "packet"}),
        }))
        assert "error" in result
        assert "validate_ship_request raised" in result["error"]
        assert result.get("exception_class") == "RuntimeError"
