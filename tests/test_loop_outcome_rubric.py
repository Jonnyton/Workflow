"""Tests for the community loop coding-packet rubric validator."""

from __future__ import annotations

from workflow.evaluation.loop_rubric import validate_loop_packet


def _keep_packet() -> dict:
    return {
        "run_id": "run-123",
        "parent_run_status": "completed",
        "child_run_status": "completed",
        "attached_child_evidence_handle": "outcome:child-123",
        "child_candidate_patch_packet": {"changed_paths": ["docs/example.md"]},
        "release_gate_result": "APPROVE_AUTO_SHIP",
        "release_score": 9.2,
        "evidence_bundle_complete": True,
        "label": "keep",
    }


def test_accepts_conformant_keep_packet() -> None:
    result = validate_loop_packet(_keep_packet())

    assert result.passed is True
    assert result.violations == []
    assert result.activity_log_lines() == []


def test_flags_keep_packet_missing_child_output() -> None:
    packet = _keep_packet()
    packet["attached_child_evidence_handle"] = ""
    packet["child_candidate_patch_packet"] = {}

    result = validate_loop_packet(packet)

    assert result.passed is False
    assert [violation.rule for violation in result.violations] == [
        "keep_missing_child_output"
    ]
    assert result.activity_log_lines() == [
        "[rubric_violation] run_id=run-123 rule=keep_missing_child_output "
        "field=child_candidate_patch_packet"
    ]


def test_flags_contradictory_child_claim_status() -> None:
    packet = _keep_packet()
    packet["automation_claim_status"] = "child_invoked_with_handle"
    packet["reason_for_downgrade"] = "BUG-045 cannot attach/invoke the child packet"

    result = validate_loop_packet(packet)

    assert result.passed is False
    assert [violation.rule for violation in result.violations] == [
        "contradictory_child_invocation"
    ]
    assert result.violations[0].field == "reason_for_downgrade"


def test_flags_recursion_limit_keep_overclaim() -> None:
    packet = _keep_packet()
    packet["__system__"] = {"recursion_limit_applied": True}

    result = validate_loop_packet(packet)

    assert result.passed is False
    assert [violation.rule for violation in result.violations] == [
        "keep_with_recursion_limit"
    ]
    assert result.violations[0].field == "__system__.recursion_limit_applied"


def test_checks_release_packet_when_separate_from_coding_packet() -> None:
    coding_packet = {
        "run_id": "run-456",
        "child_run_status": "completed",
        "attached_child_evidence_handle": "outcome:child-456",
        "child_candidate_patch_packet": {"changed_paths": ["docs/example.md"]},
        "label": "keep",
    }
    release_packet = {
        "release_gate_result": "HOLD",
        "release_score": 9.4,
        "evidence_bundle_complete": True,
    }

    result = validate_loop_packet(coding_packet, release_packet=release_packet)

    assert result.passed is False
    assert [violation.rule for violation in result.violations] == [
        "keep_bad_release_gate_result"
    ]
    assert result.violations[0].field == "release_gate_result"
