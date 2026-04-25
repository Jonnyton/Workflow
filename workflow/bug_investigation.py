"""Helpers for the file_bug → canonical investigation branch pipeline (Task #33).

When a chatbot files a bug via wiki action=file_bug, the canonical
bug-investigation branch is auto-queued with the bug payload. This module
holds the constant Goal id + payload mapping + result-comment-attach helper.
"""

from __future__ import annotations

import os

# Goal id for the bug_investigation Goal. Set via env when Phase 0 completes
# (Mark's branch bound + canonical). Default empty = auto-trigger disabled
# (filing falls back to wiki-write-only).
BUG_INVESTIGATION_GOAL_ID = os.environ.get("WORKFLOW_BUG_INVESTIGATION_GOAL_ID", "")

_PAYLOAD_KEYS = (
    "bug_id",
    "title",
    "component",
    "severity",
    "kind",
    "observed",
    "expected",
    "repro",
    "workaround",
)


def is_auto_trigger_enabled() -> bool:
    """True if a canonical bug-investigation branch is configured to auto-run."""
    return bool(BUG_INVESTIGATION_GOAL_ID)


def build_run_payload(bug_frontmatter: dict) -> dict:
    """Map BUG-NNN frontmatter → canonical investigation branch input shape."""
    return {k: bug_frontmatter.get(k, "") for k in _PAYLOAD_KEYS}


def format_investigation_comment(run_id: str, status: str = "queued") -> str:
    """Format the Investigation section appended to the bug page."""
    return (
        f"\n\n## Investigation\n\n"
        f"Queued: investigation_run_id=`{run_id}` (status={status})\n"
    )


def format_patch_packet_comment(patch_packet: dict) -> str:
    """Format the Patch Packet section appended to the bug page after run completes."""
    sections = []
    for key in ("minimal_repro", "root_cause", "test_plan", "implementation_sketch"):
        if patch_packet.get(key):
            label = key.replace("_", " ").title()
            sections.append(f"### {label}\n\n{patch_packet[key]}")
    if not sections:
        return ""
    return "\n\n## Patch Packet\n\n" + "\n\n".join(sections)
