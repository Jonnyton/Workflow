#!/usr/bin/env python3
"""Block underspecified team tasks before they enter the shared queue."""

from __future__ import annotations

import json
import re
import sys

WRITE_BOUNDARY = re.compile(r"\b(Files|Read-only|No writes)\s*:", re.IGNORECASE)
DEPENDS = re.compile(r"\bDepends\s*:", re.IGNORECASE)
DELIVERABLE = re.compile(r"\b(Deliverable|Output)\s*:", re.IGNORECASE)
HANDOFF = re.compile(r"\b(Verifier|Verification|Handoff)\s*:", re.IGNORECASE)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        payload = {}

    # Avoid interfering with any non-team task tools that do not include team metadata.
    if not payload.get("team_name"):
        return 0

    subject = str(payload.get("task_subject") or "")
    description = str(payload.get("task_description") or "")
    text = f"{subject}\n{description}"

    missing: list[str] = []
    if not WRITE_BOUNDARY.search(text):
        missing.append("Files: <write paths> or Read-only:/No writes:")
    if not DEPENDS.search(text):
        missing.append("Depends: <task ids or none>")
    if not DELIVERABLE.search(text):
        missing.append("Deliverable: <concrete output>")
    if not HANDOFF.search(text):
        missing.append("Verifier:/Verification:/Handoff: <who checks what>")

    if not missing:
        return 0

    print(
        "TASK_SHAPE_GUARD: task is underspecified. Recreate it with:\n"
        + "\n".join(f"- {item}" for item in missing)
        + "\n\n"
        + "Use file boundaries to prevent teammate collisions. For investigation tasks, "
        + "use Read-only: <paths> plus the expected report/handoff.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
