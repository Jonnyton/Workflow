"""Tests for deterministic loop-outcome rubric packet validation."""

from __future__ import annotations

from workflow.coding_packet_rubric import validate_rubric_packet


def _valid_packet(**overrides) -> dict:
    packet = {
        "child_run": {"status": "completed"},
        "attached_child_evidence_handle": "child-evidence:run-123",
        "child_candidate_patch_packet": {"changed_paths": ["docs/autoship-canaries/x.md"]},
        "release": {
            "score": 9.5,
            "evidence_bundle_complete": True,
            "release_gate_result": "APPROVE_AUTO_SHIP",
        },
        "automation_claim_status": "child_attached_with_handle",
    }
    packet.update(overrides)
    return packet


def test_valid_keep_packet_has_no_rubric_violations():
    assert validate_rubric_packet(_valid_packet()) == []


def test_missing_child_output_evidence_is_a_rubric_violation():
    packet = _valid_packet(attached_child_evidence_handle="")

    violations = validate_rubric_packet(packet)

    assert any(v["rule_id"] == "child_output_evidence_missing" for v in violations)


def test_recursion_limit_applied_cannot_be_keep_ready():
    packet = _valid_packet(
        __system__={"recursion_limit_applied": True},
        coding_packet={"status": "KEEP_READY"},
    )

    violations = validate_rubric_packet(packet)

    assert any(v["rule_id"] == "recursion_limit_keep_overclaim" for v in violations)


def test_bug_051_contradictory_child_invocation_claim_is_detected():
    packet = _valid_packet(
        automation_claim_status="child_invoked_with_handle",
        reason_for_downgrade="BUG-045 cannot invoke child packet in this surface",
    )

    violations = validate_rubric_packet(packet)

    assert any(v["rule_id"] == "contradictory_child_invocation_claim" for v in violations)


def test_dispatcher_request_id_cannot_stand_in_for_run_id():
    packet = _valid_packet(
        dispatcher_request_id="task-123",
        run_id="task-123",
    )

    violations = validate_rubric_packet(packet)

    assert any(v["rule_id"] == "dispatcher_request_id_used_as_run_id" for v in violations)


def test_shipped_label_requires_resolvable_repo_or_observation_handle():
    packet = _valid_packet(label="shipped")

    violations = validate_rubric_packet(packet)

    assert any(v["rule_id"] == "shipped_without_resolvable_handle" for v in violations)
