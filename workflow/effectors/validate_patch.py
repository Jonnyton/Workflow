"""validate_patch: a platform-trusted opaque node that deterministically
verifies a proposed patch packet APPLIES to the fetched current contents —
before a real PR is attempted and before an LLM review burns a guess.

The frontier gap it closes: every SOTA issue→PR system (Agentless, AutoCodeRover,
SWE-agent) validates patches with executable ground truth; our loop had none —
``review_gate`` only *guessed* (via an LLM) whether each search string matched.
The dominant patch-failure mode is a ``search`` string that does not occur
verbatim-and-unique in the live file, so the PR fails to apply. That is checkable
deterministically, in code, with NO LLM and NO network: the loop already fetched
the real file contents into ``current_contents_json`` (read_repo_files), and the
github_pull_request effector's ``_apply_edit_blocks`` is a pure exact-match apply.

Contract (opaque callable — ``fn(state) -> dict`` of state updates; never raises):

  reads from state:
    - ``pr_packet_draft`` (str|dict): the external_write_packet from
      propose_changes. We validate ``payload.edits_json`` ({path: [blocks]}).
    - ``current_contents_json`` (str): {path: contents|null} fetched by
      read_repo_files — the ground truth each edit must anchor on.
  writes to state:
    - ``patch_validity`` (str): exactly ``VALID`` or ``INVALID`` — a branch
      conditional-edges on this (``INVALID`` -> propose_changes for a retry,
      ``VALID`` -> review_gate).
    - ``patch_validity_detail`` (str): concrete, per-file reasons a propose
      retry can act on (which search text was not found / not unique).

Wiring (the user composes it via patch_branch): insert a ``validate_patch`` node
between propose_changes and review_gate, declare output_keys
[patch_validity, patch_validity_detail], and add a conditional edge from it.

Design parallels read_repo_files (opaque domain callable; user references it but
cannot supply its body) — see workflow/effectors/github_read.py.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

DOMAIN_ID = "workflow"
NODE_ID = "validate_patch"


def _coerce_packet(raw: Any) -> tuple[dict | None, str]:
    """Return (packet_dict, error). Accepts a dict or a JSON string."""
    if isinstance(raw, dict):
        return raw, ""
    text = str(raw or "").strip()
    if not text:
        return None, "pr_packet_draft is empty; nothing to validate."
    # Tolerate a stray code fence the model may have added.
    if text.startswith("```"):
        text = text.strip("`")
        nl = text.find("\n")
        if nl != -1:
            text = text[nl + 1:]
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError) as exc:
        return None, f"pr_packet_draft is not valid JSON ({exc}); cannot verify the patch."
    if not isinstance(parsed, dict):
        return None, "pr_packet_draft did not decode to a JSON object."
    return parsed, ""


def validate_patch(state: dict) -> dict:
    """Opaque-node body: deterministically check the packet's edits apply to the
    fetched current contents. No LLM, no network. Never raises."""
    # _apply_edit_blocks is a pure (search must occur exactly once) apply; reuse
    # the SAME logic the effector uses so validation matches real apply behavior.
    from workflow.effectors.github_pr import _apply_edit_blocks

    packet, perr = _coerce_packet(state.get("pr_packet_draft"))
    if packet is None:
        return {"patch_validity": "INVALID", "patch_validity_detail": perr}

    try:
        contents = json.loads(state.get("current_contents_json") or "{}")
        if not isinstance(contents, dict):
            contents = {}
    except (TypeError, ValueError):
        contents = {}

    payload = packet.get("payload")
    if not isinstance(payload, dict):
        payload = packet
    edits = payload.get("edits_json")

    errors: dict[str, str] = {}
    checked = 0
    if isinstance(edits, dict):
        for path, blocks in edits.items():
            current = contents.get(path)
            if not isinstance(current, str):
                errors[path] = (
                    "target file was not fetched present in current_contents "
                    "(an in-place edit needs the real file; use changes_json to "
                    "create a new file, or fix the path)"
                )
                continue
            _new, err = _apply_edit_blocks(current, blocks)
            if err is not None:
                errors[path] = err.get("detail") or err.get("error_kind") or "edit did not apply"
            else:
                checked += 1

    # changes_json (string=new-file create, null=deletion) carries no search
    # anchors, so there is nothing deterministic to verify here — left to review.

    if errors:
        detail = "; ".join(f"{p}: {e}" for p, e in sorted(errors.items()))
        return {
            "patch_validity": "INVALID",
            "patch_validity_detail": (
                "Patch does NOT apply to the current file contents — fix these and "
                f"re-propose: {detail}"
            ),
        }
    return {
        "patch_validity": "VALID",
        "patch_validity_detail": (
            f"All {checked} in-place-edited file(s) apply cleanly to current contents."
            if checked else
            "No in-place edits to verify (new-file/deletion packet); deferred to review."
        ),
    }


def register_validate_patch() -> None:
    """Register the validate_patch opaque callable for the workflow domain.

    Idempotent. Called from workflow/effectors/__init__.py at import and lazily
    from the compiler's opaque-resolution path.
    """
    from workflow.domain_registry import register_domain_callable

    register_domain_callable(DOMAIN_ID, NODE_ID, validate_patch)


__all__ = ["validate_patch", "register_validate_patch", "DOMAIN_ID", "NODE_ID"]
