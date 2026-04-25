#!/usr/bin/env python3
"""Keep teammates from going idle while dispatchable work exists.

Generalizes the prior `dev_idle_guard.py`:
- Fires for every teammate role, not just dev.
- Reads the actual TaskList JSON state (`~/.claude/tasks/<team>/*.json`)
  instead of brittle STATUS.md substring checks.
- Role-appropriate guidance: dev/dev-N/dev-N-N self-claims dispatchable
  tasks; navigator does ambient monitoring + scoping; verifier processes
  SHIP requests; floater roles match their underlying type.

Exit code 2 + stderr injects context back into the teammate's next turn
per the Claude Code hook contract.

Project rule: "session always busy" — host directive 2026-04-25. The
3-core + 1-floater team is sized to the rate-limit budget; idle slots
waste budget. Lead pre-queues; teammates self-claim; this hook is the
backstop when both fail.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

DEV_NAME = re.compile(r"^(dev|dev-\d+(?:-\d+)?|developer)$", re.IGNORECASE)
NAV_NAME = re.compile(r"^(navigator|navigator-\d+)$", re.IGNORECASE)
VERIFIER_NAME = re.compile(r"^(verifier|verifier-\d+|verifier-fresh)$", re.IGNORECASE)


def _project_root(payload: dict) -> Path:
    env_root = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_root:
        return Path(env_root)
    cwd = Path(payload.get("cwd") or os.getcwd()).resolve()
    for candidate in (cwd, *cwd.parents):
        if (candidate / "STATUS.md").exists():
            return candidate
    return cwd


def _team_name(payload: dict) -> str | None:
    """Pull team name from payload; fall back to active workflow-lead."""
    team = payload.get("team_name") or payload.get("team")
    if team:
        return str(team)
    return "workflow-lead"


def _tasks_root(team: str) -> Path:
    home = os.environ.get("USERPROFILE") or os.environ.get("HOME") or ""
    return Path(home) / ".claude" / "tasks" / team


def _load_tasks(team: str) -> list[dict]:
    root = _tasks_root(team)
    if not root.is_dir():
        return []
    out: list[dict] = []
    for path in root.glob("*.json"):
        try:
            out.append(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return out


def _unblocked_pending(tasks: list[dict]) -> list[dict]:
    """Tasks that are pending, have no owner, and have no open blockers."""
    by_id = {t.get("id"): t for t in tasks}
    out: list[dict] = []
    for t in tasks:
        if t.get("status") != "pending":
            continue
        if t.get("owner"):
            continue
        blockers = t.get("blockedBy") or []
        if any(by_id.get(b, {}).get("status") not in ("completed", None) for b in blockers):
            continue
        out.append(t)
    return out


def _in_progress_for(tasks: list[dict], teammate: str) -> list[dict]:
    return [t for t in tasks if t.get("status") == "in_progress" and t.get("owner") == teammate]


def _dev_guidance(unblocked: list[dict], my_active: list[dict]) -> list[str]:
    if my_active:
        return []  # already working
    lines = [
        f"DEV_IDLE_GUARD: TaskList has {len(unblocked)} unclaimed unblocked task(s).",
    ]
    for t in unblocked[:5]:
        lines.append(f"  - #{t.get('id')}: {t.get('subject', '?')[:80]}")
    lines += [
        "",
        "Self-claim now: TaskUpdate set owner to your name + status=in_progress.",
        "Investigation-first: scope-message lead BEFORE edits, then implement → ruff → SHIP.",
        'Do NOT report "QUEUE EMPTY" while pending unblocked tasks exist.',
    ]
    return lines


def _navigator_guidance(unblocked: list[dict], my_active: list[dict]) -> list[str]:
    if my_active:
        return []
    lines = [
        "NAVIGATOR_IDLE_GUARD: ambient duties when no task assigned.",
        "",
        "1. Wiki sweep — check for new BUGs / patch_requests filed since last cursor",
        "   (.claude/agent-memory/navigator/wiki_sweep_cursor.md).",
        "2. Scoping pass — if dev/dev-2 queue is shallow, produce 4-6 dev-ready",
        "   bounded candidates with Files + Depends + deliverable.",
        "3. Read incoming design docs (any docs/design-notes/2026-04-* dated today)",
        "   and prepare v2 input for the self-evolving platform vision.",
        "4. STATUS Concerns scan — flag any concern that a recent ship resolves.",
        "",
        "Send findings to lead via SendMessage; do not idle silently.",
    ]
    if unblocked:
        lines.insert(2, f"   ({len(unblocked)} pending tasks visible in TaskList)")
    return lines


def _verifier_guidance(my_active: list[dict]) -> list[str]:
    if my_active:
        return []
    lines = [
        "VERIFIER_IDLE_GUARD: gate duties when no SHIP request in flight.",
        "",
        "1. Re-run baseline if commits landed since last baseline — confirm green.",
        "2. Scan working tree (git status) for genuinely uncommitted bundles",
        "   that may have shipped without your verdict.",
        "3. Process any pending SHIP requests in your inbox.",
        "4. If truly nothing to gate: read recent ships' diffs proactively for",
        "   semantic-correctness concerns to surface as follow-ups.",
        "",
        "Send findings/verdicts to lead; do not idle silently while bundles",
        "may be awaiting verdict.",
    ]
    return lines


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    teammate = str(payload.get("teammate_name") or payload.get("name") or "")
    if not teammate:
        return 0

    team = _team_name(payload)
    tasks = _load_tasks(team or "workflow-lead")
    unblocked = _unblocked_pending(tasks)
    my_active = _in_progress_for(tasks, teammate)

    if DEV_NAME.match(teammate):
        lines = _dev_guidance(unblocked, my_active)
    elif NAV_NAME.match(teammate):
        lines = _navigator_guidance(unblocked, my_active)
    elif VERIFIER_NAME.match(teammate):
        lines = _verifier_guidance(my_active)
    else:
        return 0

    if not lines:
        return 0

    print("\n".join(lines), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
