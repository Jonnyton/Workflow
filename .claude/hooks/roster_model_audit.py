#!/usr/bin/env python3
"""Audit team roster for non-latest model members at session start.

If `~/.claude/teams/<active-team>/config.json` lists any member with a model
that is not the latest (Opus today), emit an emergency systemMessage via the
SessionStart hook. The lead is expected to despawn + respawn the offender
on the latest model immediately. Project rule: latest-model-only.

Filters to the active team only — stale entries from prior sessions get
ignored. Active-team detection mirrors `stale_team_pruner.py`'s
`_team_is_active` (kept inline rather than imported to keep this hook
single-file). Reference: `docs/audits/2026-04-25-despawn-chain-protocol.md`
§6 CHANGE-2.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

LATEST_ALLOWED = {"opus"}
LATEST_PREFIXES = ("claude-opus-",)
ACTIVE_THRESHOLD_MIN = 60


def _is_latest(model: str | None) -> bool:
    if not model:
        return True  # unset => inherits lead model
    m = str(model).strip().lower()
    if m in LATEST_ALLOWED:
        return True
    return any(m.startswith(p) for p in LATEST_PREFIXES)


def _teams_root() -> Path:
    home = os.environ.get("USERPROFILE") or os.environ.get("HOME") or ""
    return Path(home) / ".claude" / "teams"


def _path_mtime(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except (OSError, ValueError):
        return None


def _team_is_active(team_dir: Path, threshold_seconds: float, now: float) -> bool:
    """Active if `inboxes/` OR `config.json` mtime is within threshold.

    Mirrors the helper in `stale_team_pruner.py`. Kept inline here so this
    hook stays a single file.
    """
    inboxes = team_dir / "inboxes"
    config = team_dir / "config.json"
    for candidate in (inboxes, config):
        mtime = _path_mtime(candidate)
        if mtime is not None and (now - mtime) <= threshold_seconds:
            return True
    return False


def main() -> int:
    teams_root = _teams_root()
    if not teams_root.is_dir():
        return 0

    now = time.time()
    threshold_seconds = ACTIVE_THRESHOLD_MIN * 60.0

    offenders: list[tuple[str, str, str]] = []
    for team_dir in teams_root.iterdir():
        if not team_dir.is_dir():
            continue
        try:
            if not _team_is_active(team_dir, threshold_seconds, now):
                continue
        except OSError:
            continue
        cfg = team_dir / "config.json"
        if not cfg.is_file():
            continue
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for member in data.get("members") or []:
            name = member.get("name", "?")
            if name == "team-lead":
                continue
            model = member.get("model")
            if not _is_latest(model):
                offenders.append((team_dir.name, name, str(model)))

    if not offenders:
        return 0

    lines = ["EMERGENCY: roster has non-latest-model teammates (rule = always Opus):"]
    for team, name, model in offenders:
        lines.append(f"  - team={team!r} member={name!r} model={model!r}")
    lines.append("Despawn + respawn each on model='opus' immediately.")
    msg = "\n".join(lines)

    print(json.dumps({"systemMessage": msg}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
