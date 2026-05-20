"""GitHub PR substrate effector — PR-122 Phase 1 milestone M1.

Reads ``external_write_packet`` shapes from a completed run's final state
for any node whose ``effects`` declaration includes
``"github_pull_request"``, and invokes ``gh pr create`` to open a draft
PR for each.

Packet shape (convention — documented in
drafts/concepts/external-write-packet-shape.md):

.. code-block:: json

    {
      "sink": "github_pull_request",
      "payload": {
        "title": "...",
        "body":  "...",
        "base_branch": "main",
        "head_branch": "auto/.../...",
        "labels": ["..."],
        "draft": true
      },
      "idempotency_hint": "<optional>",
      "expected_evidence_keys": ["pr_number", "pr_url"]
    }

Authentication: re-uses the host's existing ``gh`` CLI credentials.
No new credential resolver in this slice (see PR-122 follow-ons).

Safety defaults (PR-122 Phase 1, round-2 response to Codex review of
PR #955):

- **Default is dry-run.** The effector only invokes ``gh pr create``
  when ``WORKFLOW_EXTERNAL_WRITE_ENABLED`` is truthy. Without that
  explicit opt-in, the effector returns the parsed intent and never
  shells out. This satisfies the consent-gate requirement: an
  out-of-the-box install can have a branch declare
  ``effects=["github_pull_request"]`` and the operator will see the
  intent in run output without any risk of an accidental PR.
- ``WORKFLOW_EXTERNAL_WRITE_DRY_RUN`` (the legacy env) is still
  honored as a back-compat alias: when truthy it forces dry-run
  regardless of the enable flag. Since dry-run is now the safe default
  the alias is essentially a no-op for new installs, but it preserves
  intent for any operator that set it explicitly.
- The caller can also pass ``dry_run=True``; that wins over both env
  vars.
- Even when ``WORKFLOW_EXTERNAL_WRITE_ENABLED`` is set, the effector
  refuses to call ``gh`` unless the packet includes
  ``idempotency_ack='caller_handled_externally_phase_1_temporary_unsafe'``.
  Phase 1 ships no real idempotency check; the ack phrase makes the
  caller name the risk before duplicate-PR potential is enabled.
  Phase 2 replaces this guard with a real dedupe layer.

Errors are captured and returned in the evidence map; the function
never raises to the run-completion path. Hard-rule #8 (fail loudly)
is satisfied by structured ``error`` fields in the per-node evidence.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


EXTERNAL_WRITE_SINK_GITHUB_PR = "github_pull_request"
_DRY_RUN_ENV = "WORKFLOW_EXTERNAL_WRITE_DRY_RUN"
_ENABLE_ENV = "WORKFLOW_EXTERNAL_WRITE_ENABLED"
_GH_TIMEOUT_SECONDS = 60.0

# Phase 1 explicit-acknowledgement phrase. The caller must opt into
# the duplicate-PR risk by hand until Phase 2 lands real idempotency.
PHASE_1_IDEMPOTENCY_ACK = "caller_handled_externally_phase_1_temporary_unsafe"

_TRUTHY = frozenset({"1", "true", "yes", "on"})

_PR_URL_RE = re.compile(r"https?://[^\s]+/pull/(\d+)")


def _env_truthy(name: str) -> bool:
    val = os.environ.get(name, "")
    return val.strip().lower() in _TRUTHY


def _dry_run_from_env() -> bool:
    """Return True when the environment requests dry-run mode.

    Dry-run is the safe default. The effector only goes live when
    ``WORKFLOW_EXTERNAL_WRITE_ENABLED`` is truthy AND
    ``WORKFLOW_EXTERNAL_WRITE_DRY_RUN`` is NOT truthy (the legacy alias
    still wins so an operator that explicitly set it keeps their
    intent). Returning ``True`` here means "force dry-run".
    """
    # Legacy dry-run alias always forces dry-run when set.
    if _env_truthy(_DRY_RUN_ENV):
        return True
    # New default: dry-run unless explicit enable.
    if not _env_truthy(_ENABLE_ENV):
        return True
    return False


def _parse_packet(value: Any) -> dict[str, Any] | None:
    """Parse an output value into an external_write_packet dict.

    Accepts an already-dict shape OR a JSON-string shape. Returns
    ``None`` when the value isn't packet-shaped (missing ``sink``).
    """
    if isinstance(value, dict):
        packet = value
    elif isinstance(value, str):
        stripped = value.strip()
        if not stripped or not stripped.startswith("{"):
            return None
        try:
            packet = json.loads(stripped)
        except (ValueError, TypeError):
            return None
        if not isinstance(packet, dict):
            return None
    else:
        return None
    if "sink" not in packet:
        return None
    return packet


def _parse_pr_evidence(stdout: str) -> dict[str, Any]:
    """Extract ``pr_url`` + ``pr_number`` from ``gh pr create`` stdout.

    ``gh pr create`` prints the PR URL on the last non-empty line.
    """
    if not stdout:
        return {}
    last = ""
    for line in stdout.splitlines():
        stripped = line.strip()
        if stripped:
            last = stripped
    evidence: dict[str, Any] = {}
    if last:
        evidence["pr_url"] = last
        match = _PR_URL_RE.search(last)
        if match is not None:
            try:
                evidence["pr_number"] = int(match.group(1))
            except (TypeError, ValueError):
                pass
    return evidence


def _invoke_gh_pr_create(packet: dict[str, Any]) -> dict[str, Any]:
    """Invoke ``gh pr create`` against the host's credentials.

    Returns an evidence dict including ``pr_url`` / ``pr_number`` on
    success, or ``error`` on failure. Never raises.
    """
    if shutil.which("gh") is None:
        return {
            "error": "gh CLI not installed",
            "error_kind": "gh_not_installed",
        }
    payload = packet.get("payload") or {}
    if not isinstance(payload, dict):
        return {
            "error": "payload must be a JSON object",
            "error_kind": "invalid_payload",
        }
    title = (payload.get("title") or "").strip()
    body = payload.get("body") or ""
    if not title:
        return {
            "error": "payload.title is required",
            "error_kind": "invalid_payload",
        }
    cmd = ["gh", "pr", "create", "--title", title, "--body", body]
    head = payload.get("head_branch")
    if isinstance(head, str) and head.strip():
        cmd.extend(["--head", head.strip()])
    base = payload.get("base_branch")
    if isinstance(base, str) and base.strip():
        cmd.extend(["--base", base.strip()])
    if payload.get("draft", True):
        cmd.append("--draft")
    labels = payload.get("labels") or []
    if isinstance(labels, list):
        for label in labels:
            if isinstance(label, str) and label.strip():
                cmd.extend(["--label", label.strip()])
    try:
        result = subprocess.run(  # noqa: S603 — gh CLI; args explicit
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=_GH_TIMEOUT_SECONDS,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {
            "error": f"gh pr create invocation failed: {exc}",
            "error_kind": "gh_invocation_failed",
        }
    if result.returncode != 0:
        return {
            "error": (
                f"gh pr create exited rc={result.returncode}: "
                f"{(result.stderr or result.stdout or '').strip()}"
            ),
            "error_kind": "gh_nonzero_exit",
            "stderr": (result.stderr or "").strip(),
        }
    evidence = _parse_pr_evidence(result.stdout or "")
    evidence.setdefault("stdout", (result.stdout or "").strip())
    return evidence


def run_github_pr_effector(
    *,
    node_id: str,
    output_keys: list[str],
    run_state: dict[str, Any],
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run the GitHub-PR effector for a single node.

    Scans ``output_keys`` for a value that parses as an
    ``external_write_packet`` with ``sink == "github_pull_request"``.
    The first matching key wins; non-matching keys are skipped silently
    (they are normal output fields, not packets).

    Returns one of:

    - ``{"dry_run": True, "intent": <packet>}`` when ``dry_run`` is set.
    - ``{"pr_url": "...", "pr_number": N, ...}`` on a successful real
      invocation.
    - ``{"error": "...", "error_kind": "..."}`` when something went
      wrong (no matching packet, gh missing, gh non-zero exit, etc.).

    Per the PR-122 contract, this function never raises — all failure
    modes are returned as structured evidence and surfaced into the run
    record's ``external_write_errors`` metadata so authors can debug
    without crashing the run.
    """
    matched_key: str | None = None
    packet: dict[str, Any] | None = None
    for key in output_keys or []:
        if not isinstance(key, str):
            continue
        if key not in run_state:
            continue
        candidate = _parse_packet(run_state.get(key))
        if candidate is None:
            continue
        if candidate.get("sink") != EXTERNAL_WRITE_SINK_GITHUB_PR:
            continue
        matched_key = key
        packet = candidate
        break
    if packet is None:
        return {
            "error": (
                f"node '{node_id}' declared effects=[github_pull_request] "
                "but no output_key held a parseable external_write_packet "
                "with sink='github_pull_request'"
            ),
            "error_kind": "no_matching_packet",
        }
    if dry_run:
        return {
            "dry_run": True,
            "enabled_explicit": _env_truthy(_ENABLE_ENV),
            "intent": packet,
            "matched_output_key": matched_key,
            "reason": (
                "WORKFLOW_EXTERNAL_WRITE_ENABLED not set"
                if not _env_truthy(_ENABLE_ENV)
                else "dry_run forced by caller or WORKFLOW_EXTERNAL_WRITE_DRY_RUN"
            ),
        }
    # Phase 1 idempotency guard. Even when the operator has explicitly
    # enabled real writes via WORKFLOW_EXTERNAL_WRITE_ENABLED, we
    # refuse to call ``gh pr create`` unless the packet contains a
    # specific acknowledgement phrase that names the duplicate-PR risk.
    # Phase 2 replaces this guard with real dedupe (idempotency_hint
    # derivation + existing-PR lookup + run-evidence consultation).
    ack = packet.get("idempotency_ack")
    if ack != PHASE_1_IDEMPOTENCY_ACK:
        return {
            "node_id": node_id,
            "sink": EXTERNAL_WRITE_SINK_GITHUB_PR,
            "dry_run": True,
            "error": "idempotency_not_implemented",
            "error_kind": "idempotency_phase_1_guard",
            "message": (
                "Phase 1 has no idempotency check. Pass "
                f"idempotency_ack={PHASE_1_IDEMPOTENCY_ACK!r} in the "
                "packet to acknowledge the duplicate-PR risk and "
                "proceed. Real idempotency derivation lands in a "
                "follow-on PR."
            ),
            "intent": packet,
            "matched_output_key": matched_key,
        }
    evidence = _invoke_gh_pr_create(packet)
    evidence["matched_output_key"] = matched_key
    evidence["enabled_explicit"] = True
    return evidence


def run_effects_for_branch(
    *,
    branch: Any,
    run_state: dict[str, Any],
    dry_run: bool | None = None,
) -> dict[str, Any]:
    """Walk every node on ``branch`` with a declared effect, dispatch.

    Returns a dict keyed by ``node_id`` for every node that declared at
    least one effect. Each value is the evidence dict from the matching
    effector (one currently — github_pull_request). Nodes without
    ``effects`` are skipped entirely.

    ``dry_run`` precedence: explicit kwarg wins; otherwise read the
    ``WORKFLOW_EXTERNAL_WRITE_DRY_RUN`` env var.

    Never raises. Errors are folded into the per-node evidence so the
    caller can log them as ``external_write_errors`` and otherwise
    complete the run normally.
    """
    effective_dry_run = (
        dry_run if dry_run is not None else _dry_run_from_env()
    )
    evidence_map: dict[str, Any] = {}
    node_defs = getattr(branch, "node_defs", None) or []
    for node in node_defs:
        effects = getattr(node, "effects", None) or []
        if not effects:
            continue
        node_id = getattr(node, "node_id", "")
        output_keys = list(getattr(node, "output_keys", None) or [])
        per_node: dict[str, Any] = {}
        for sink in effects:
            if sink == EXTERNAL_WRITE_SINK_GITHUB_PR:
                try:
                    result = run_github_pr_effector(
                        node_id=node_id,
                        output_keys=output_keys,
                        run_state=run_state,
                        dry_run=effective_dry_run,
                    )
                except Exception as exc:  # defensive — never raise
                    logger.exception(
                        "github_pr effector crashed for node %s",
                        node_id,
                    )
                    result = {
                        "error": f"effector crashed: {exc}",
                        "error_kind": "effector_crashed",
                    }
                per_node[sink] = result
            else:
                per_node[sink] = {
                    "error": f"unknown effect sink '{sink}'",
                    "error_kind": "unknown_sink",
                }
        if per_node:
            evidence_map[node_id] = per_node
    return evidence_map
