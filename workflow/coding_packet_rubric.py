"""Deterministic validator for loop outcome coding/release packets.

The rules here implement the structural subset of
``docs/specs/loop-outcome-rubric-v0.md`` §5 and §7. This module is pure:
no IO, no network, and no LLM judgment.
"""

from __future__ import annotations

from typing import Any

KEEP_SCORE_MIN = 9.0
APPROVED_RELEASE_RESULTS = frozenset({"APPROVE", "APPROVE_AUTO_SHIP"})
KEEP_LABELS = frozenset({"keep", "shipped", "observed_healthy"})
KEEP_PACKET_STATUSES = frozenset({"KEEP_READY", "AUTO_SHIP_READY"})


def _violation(rule_id: str, field: str | None, message: str) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "field": field,
        "severity": "block",
        "message": message,
    }


def _first_present(packet: dict[str, Any], *paths: tuple[str, ...]) -> Any:
    for path in paths:
        cur: Any = packet
        for key in path:
            if not isinstance(cur, dict) or key not in cur:
                cur = None
                break
            cur = cur[key]
        if cur not in (None, ""):
            return cur
    return None


def _is_nonempty(value: Any) -> bool:
    if value in (None, ""):
        return False
    if isinstance(value, (dict, list, tuple, set)) and not value:
        return False
    return True


def _system_flag(packet: dict[str, Any], flag_name: str) -> bool:
    system = packet.get("__system__")
    return isinstance(system, dict) and bool(system.get(flag_name))


def validate_rubric_packet(packet: dict[str, Any]) -> list[dict[str, Any]]:
    """Return rubric-conformance violations for a coding/release packet.

    All returned records use the same violation shape as ``workflow.auto_ship``
    so callers can aggregate envelope and rubric failures without adapters.
    """
    if not isinstance(packet, dict):
        return [
            _violation(
                "packet_not_dict",
                None,
                f"packet must be a dict; got {type(packet).__name__}",
            )
        ]

    violations: list[dict[str, Any]] = []

    child_run_status = _first_present(
        packet,
        ("child_run", "status"),
        ("child_run_status",),
    )
    if child_run_status != "completed":
        violations.append(_violation(
            "child_run_not_completed",
            "child_run.status",
            f"child-run.status must be 'completed'; got {child_run_status!r}",
        ))

    evidence_handle = _first_present(
        packet,
        ("attached_child_evidence_handle",),
        ("child_output", "attached_child_evidence_handle"),
    )
    candidate_packet = _first_present(
        packet,
        ("child_candidate_patch_packet",),
        ("child_output", "child_candidate_patch_packet"),
    )
    if not _is_nonempty(evidence_handle) or not _is_nonempty(candidate_packet):
        violations.append(_violation(
            "child_output_evidence_missing",
            "child-output",
            (
                "child-output evidence requires non-empty "
                "attached_child_evidence_handle and child_candidate_patch_packet"
            ),
        ))

    release_score = _first_present(
        packet,
        ("release", "score"),
        ("child_score",),
    )
    if not isinstance(release_score, (int, float)):
        violations.append(_violation(
            "release_score_not_numeric",
            "release.score",
            f"release.score must be numeric; got {type(release_score).__name__}",
        ))
    elif release_score < KEEP_SCORE_MIN:
        violations.append(_violation(
            "release_score_below_keep_threshold",
            "release.score",
            f"release.score {release_score} below KEEP threshold {KEEP_SCORE_MIN}",
        ))

    evidence_bundle_complete = _first_present(
        packet,
        ("release", "evidence_bundle_complete"),
        ("evidence_bundle_complete",),
    )
    if evidence_bundle_complete is not True:
        violations.append(_violation(
            "evidence_bundle_incomplete",
            "release.evidence_bundle_complete",
            "release.evidence_bundle_complete must be true for KEEP",
        ))

    release_gate_result = _first_present(
        packet,
        ("release", "release_gate_result"),
        ("release_gate_result",),
    )
    if release_gate_result not in APPROVED_RELEASE_RESULTS:
        violations.append(_violation(
            "release_gate_not_keep_approved",
            "release.release_gate_result",
            (
                "release.release_gate_result must be APPROVE or "
                f"APPROVE_AUTO_SHIP; got {release_gate_result!r}"
            ),
        ))

    automation_claim_status = str(packet.get("automation_claim_status") or "")
    reason_for_downgrade = str(packet.get("reason_for_downgrade") or "")
    lowered_reason = reason_for_downgrade.lower()
    if (
        automation_claim_status == "child_invoked_with_handle"
        and (
            "cannot invoke" in lowered_reason
            or "cannot attach" in lowered_reason
            or "bug-045" in lowered_reason
        )
    ):
        violations.append(_violation(
            "contradictory_child_invocation_claim",
            "automation_claim_status",
            (
                "automation_claim_status claims child invocation while "
                "reason_for_downgrade says child invocation/attachment failed"
            ),
        ))

    dispatcher_request_id = packet.get("dispatcher_request_id")
    run_id = packet.get("run_id")
    if dispatcher_request_id and run_id and dispatcher_request_id == run_id:
        violations.append(_violation(
            "dispatcher_request_id_used_as_run_id",
            "run_id",
            "dispatcher_request_id and run_id must be distinct trace handles",
        ))

    label = str(packet.get("label") or packet.get("outcome_label") or "").lower()
    coding_packet_status = _first_present(
        packet,
        ("coding_packet", "status"),
        ("coding_packet_status",),
    )
    if _system_flag(packet, "recursion_limit_applied") and (
        label in KEEP_LABELS or coding_packet_status in KEEP_PACKET_STATUSES
    ):
        violations.append(_violation(
            "recursion_limit_keep_overclaim",
            "__system__.recursion_limit_applied",
            "recursion-limit termination cannot be asserted as KEEP/ship-ready",
        ))

    if label == "shipped":
        commit_sha = _first_present(packet, ("release", "commit_sha"), ("commit_sha",))
        pr_url = _first_present(packet, ("release", "pr_url"), ("pr_url",))
        observation = _first_present(
            packet,
            ("release", "live_observation_gate_result"),
            ("live_observation_gate_result",),
        )
        if not any(_is_nonempty(value) for value in (commit_sha, pr_url, observation)):
            violations.append(_violation(
                "shipped_without_resolvable_handle",
                "label",
                "label='shipped' requires commit_sha, pr_url, or observation evidence",
            ))

    return violations
