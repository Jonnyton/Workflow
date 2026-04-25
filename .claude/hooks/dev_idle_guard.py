#!/usr/bin/env python3
"""Keep developer teammates from going idle while dispatchable work exists."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

DEV_NAME = re.compile(r"^(dev|dev-\d+|developer)(\b|$)", re.IGNORECASE)


def _project_root(payload: dict) -> Path:
    env_root = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_root:
        return Path(env_root)

    cwd = Path(payload.get("cwd") or os.getcwd()).resolve()
    for candidate in (cwd, *cwd.parents):
        if (candidate / "STATUS.md").exists():
            return candidate
    return cwd


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _backlog_signals(root: Path) -> list[str]:
    status = _read(root / "STATUS.md")
    vetted = _read(root / "docs" / "vetted-specs.md")
    signals: list[str] = []

    if "dev-dispatchable" in status:
        signals.append("STATUS.md has Approved specs marked dev-dispatchable.")
    if "claimed:dev (queued)" in status or "claimed:dev" in status:
        signals.append("STATUS.md shows dev-owned or queued work.")
    if "Dev priority cascade" in status:
        signals.append("STATUS.md Next names the dev priority cascade.")
    if "dev-dispatchable" in vetted:
        signals.append("docs/vetted-specs.md has dev-dispatchable specs.")
    if "Navigator follow-up" in status or "modularity-audit" in status:
        signals.append("STATUS.md has investigation/audit follow-ups that can feed dev tasks.")

    return signals


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        payload = {}

    teammate = str(payload.get("teammate_name") or "")
    if not DEV_NAME.search(teammate):
        return 0

    root = _project_root(payload)
    signals = _backlog_signals(root)
    if not signals:
        return 0

    print(
        "\n".join(
            [
                "DEV_IDLE_GUARD: do not go idle while known dev-dispatchable work exists.",
                *[f"- {signal}" for signal in signals[:5]],
                "",
                "Continue now:",
                "1. Open TaskList and self-claim the next unblocked task for dev/dev-2.",
                (
                    "2. If TaskList is empty or underspecified, create or request a task "
                    "from STATUS.md or docs/vetted-specs.md with Files, Depends, "
                    "deliverable, and verifier handoff."
                ),
                (
                    "3. If all code work is genuinely blocked, message lead and navigator "
                    "with exactly what is blocked, then do read-only scoping for the next "
                    "3 file-bounded dev tasks."
                ),
                "",
                'Do not report only "Standing by" while these backlog signals exist.',
            ]
        ),
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
