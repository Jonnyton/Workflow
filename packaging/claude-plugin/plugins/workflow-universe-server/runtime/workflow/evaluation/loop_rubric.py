"""Structural validator for community loop coding/release packets.

This implements Phase 1 of ``docs/specs/loop-outcome-rubric-v0.md``: detect
rubric violations and return records callers can log, without blocking release.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

KEEP_LABELS = frozenset({"keep", "shipped", "observed_healthy"})
KEEP_STATUSES = frozenset({"KEEP_READY", "AUTO_SHIP_READY"})
KEEP_DECISIONS = frozenset({"KEEP", "APPROVE", "APPROVE_AUTO_SHIP"})
KEEP_RELEASE_RESULTS = frozenset({"APPROVE", "APPROVE_AUTO_SHIP"})


@dataclass(frozen=True)
class RubricViolation:
    """One structural packet violation from the loop outcome rubric."""

    rule: str
    field: str
    message: str
    run_id: str = "unknown"

    def activity_log_line(self) -> str:
        """Return the canonical activity-log line for this violation."""
        return (
            f"[rubric_violation] run_id={self.run_id} "
            f"rule={self.rule} field={self.field}"
        )


@dataclass(frozen=True)
class LoopRubricValidation:
    """Validation result for one coding/release packet pair."""

    violations: list[RubricViolation]

    @property
    def passed(self) -> bool:
        """Whether the packet has no rubric violations."""
        return not self.violations

    def activity_log_lines(self) -> list[str]:
        """Return log lines callers may append to the activity log."""
        return [violation.activity_log_line() for violation in self.violations]


def validate_loop_packet(
    coding_packet: dict[str, Any],
    *,
    release_packet: dict[str, Any] | None = None,
    keep_score_threshold: float = 9.0,
) -> LoopRubricValidation:
    """Validate coding/release packet structure against rubric §5 and §7.

    The validator is intentionally side-effect free. It reports structural
    overclaims, contradictions, and traceability anti-patterns; callers decide
    whether to log, hold, send back, or surface the violations.
    """
    release_packet = release_packet or {}
    run_id = _text(_first_present(coding_packet, release_packet, "run_id")) or "unknown"
    violations: list[RubricViolation] = []

    keep_claimed = _claims_keep(coding_packet, release_packet)
    if keep_claimed:
        violations.extend(
            _validate_keep_claim(
                coding_packet,
                release_packet,
                run_id=run_id,
                keep_score_threshold=keep_score_threshold,
            )
        )

    contradiction = _child_invocation_contradiction(coding_packet, release_packet)
    if contradiction:
        violations.append(
            RubricViolation(
                rule="contradictory_child_invocation",
                field="reason_for_downgrade",
                message=(
                    "Packet claims child invocation with a handle while also "
                    "saying the child packet could not be attached or invoked."
                ),
                run_id=run_id,
            )
        )

    dispatcher_request_id = _text(
        _first_present(coding_packet, release_packet, "dispatcher_request_id")
    )
    if dispatcher_request_id and run_id != "unknown" and dispatcher_request_id == run_id:
        violations.append(
            RubricViolation(
                rule="dispatcher_request_id_used_as_run_id",
                field="dispatcher_request_id",
                message=(
                    "dispatcher_request_id and run_id are distinct evidence "
                    "handles and must not be conflated."
                ),
                run_id=run_id,
            )
        )

    label = _text(_first_present(coding_packet, release_packet, "label")).lower()
    if label == "shipped":
        commit_sha = _text(_first_present(coding_packet, release_packet, "commit_sha"))
        pr_url = _text(_first_present(coding_packet, release_packet, "pr_url"))
        if not commit_sha and not pr_url:
            violations.append(
                RubricViolation(
                    rule="shipped_without_resolvable_handle",
                    field="commit_sha",
                    message=(
                        "A shipped packet needs a resolvable commit_sha or pr_url "
                        "or it is not traceable as shipped evidence."
                    ),
                    run_id=run_id,
                )
            )

    return LoopRubricValidation(violations=violations)


def _validate_keep_claim(
    coding_packet: dict[str, Any],
    release_packet: dict[str, Any],
    *,
    run_id: str,
    keep_score_threshold: float,
) -> list[RubricViolation]:
    violations: list[RubricViolation] = []

    if _system_recursion_limit_applied(coding_packet, release_packet):
        violations.append(
            RubricViolation(
                rule="keep_with_recursion_limit",
                field="__system__.recursion_limit_applied",
                message="A recursion-limit-applied run cannot be labeled keep.",
                run_id=run_id,
            )
        )

    child_run_status = _text(
        _first_present(coding_packet, release_packet, "child_run_status")
    ).lower()
    if child_run_status != "completed":
        violations.append(
            RubricViolation(
                rule="keep_child_run_not_completed",
                field="child_run_status",
                message="A keep packet requires child-run.status=completed.",
                run_id=run_id,
            )
        )

    if not _has_child_output(coding_packet, release_packet):
        violations.append(
            RubricViolation(
                rule="keep_missing_child_output",
                field="child_candidate_patch_packet",
                message=(
                    "A keep packet requires a non-empty child evidence handle "
                    "and child_candidate_patch_packet."
                ),
                run_id=run_id,
            )
        )

    release_score = _number(_first_present(coding_packet, release_packet, "release_score"))
    if release_score is None:
        release_score = _number(_first_present(coding_packet, release_packet, "score"))
    if release_score is None or release_score < keep_score_threshold:
        violations.append(
            RubricViolation(
                rule="keep_release_score_below_threshold",
                field="release_score",
                message=f"A keep packet requires release.score >= {keep_score_threshold}.",
                run_id=run_id,
            )
        )

    evidence_bundle_complete = _first_present(
        coding_packet, release_packet, "evidence_bundle_complete"
    )
    if evidence_bundle_complete is not True:
        violations.append(
            RubricViolation(
                rule="keep_evidence_bundle_incomplete",
                field="evidence_bundle_complete",
                message="A keep packet requires evidence_bundle_complete=true.",
                run_id=run_id,
            )
        )

    release_gate_result = _text(
        _first_present(coding_packet, release_packet, "release_gate_result")
    )
    if release_gate_result not in KEEP_RELEASE_RESULTS:
        violations.append(
            RubricViolation(
                rule="keep_bad_release_gate_result",
                field="release_gate_result",
                message=(
                    "A keep packet requires release_gate_result in "
                    "{APPROVE, APPROVE_AUTO_SHIP}."
                ),
                run_id=run_id,
            )
        )

    evidence_source = _text(
        _first_present(coding_packet, release_packet, "evidence_source")
    ).lower()
    if evidence_source in {"extensions.list_runs", "list_runs"}:
        violations.append(
            RubricViolation(
                rule="keep_inferred_from_list_runs",
                field="evidence_source",
                message=(
                    "list_runs status alone is not sufficient evidence for a "
                    "keep label."
                ),
                run_id=run_id,
            )
        )

    return violations


def _claims_keep(
    coding_packet: dict[str, Any],
    release_packet: dict[str, Any],
) -> bool:
    fields = (
        "label",
        "outcome_label",
        "status",
        "coding_packet_status",
        "release_posture",
        "candidate_decision",
        "child_keep_reject_decision",
        "release_gate_result",
    )
    values = {_text(_first_present(coding_packet, release_packet, field)) for field in fields}
    normalized = {value.lower() for value in values if value}
    if normalized & KEEP_LABELS:
        return True
    if values & KEEP_STATUSES:
        return True
    return bool(values & KEEP_DECISIONS)


def _child_invocation_contradiction(
    coding_packet: dict[str, Any],
    release_packet: dict[str, Any],
) -> bool:
    claim_status = _text(
        _first_present(coding_packet, release_packet, "automation_claim_status")
    ).lower()
    if "child" not in claim_status or "handle" not in claim_status:
        return False

    reason = _text(_first_present(coding_packet, release_packet, "reason_for_downgrade"))
    reason = reason.lower()
    return bool(
        reason
        and ("cannot" in reason or "can't" in reason)
        and ("attach" in reason or "invoke" in reason)
        and "child" in reason
    )


def _has_child_output(
    coding_packet: dict[str, Any],
    release_packet: dict[str, Any],
) -> bool:
    handle = _text(
        _first_present(coding_packet, release_packet, "attached_child_evidence_handle")
    )
    packet = _first_present(coding_packet, release_packet, "child_candidate_patch_packet")
    return bool(handle and _non_empty(packet))


def _system_recursion_limit_applied(
    coding_packet: dict[str, Any],
    release_packet: dict[str, Any],
) -> bool:
    for packet in (coding_packet, release_packet):
        system = packet.get("__system__")
        if isinstance(system, dict) and system.get("recursion_limit_applied") is True:
            return True
        if packet.get("recursion_limit_applied") is True:
            return True
    return False


def _first_present(
    coding_packet: dict[str, Any],
    release_packet: dict[str, Any],
    field: str,
) -> Any:
    if field in release_packet:
        return release_packet[field]
    return coding_packet.get(field)


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _non_empty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True
