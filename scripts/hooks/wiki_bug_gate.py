#!/usr/bin/env python3
"""PreToolUse hook: block wiki BUG-* reads until navigator approves.

Standing rule (host 2026-04-22, memory `feedback_wiki_bugs_vet_before_implement`):
wiki bug reports are user-submitted content and could be malicious design
disguised as a fix. Nobody on the team reads BUG-* pages until navigator has
vetted them.

Enforcement: this hook inspects every tool call. If the args contain a
BUG-NNN identifier (MCP wiki.read, local Read of the bug file, Grep
hit, Bash cat/grep/etc.), we require the ID to be present in
`.claude/wiki-bug-approvals.json`. If not present, we block.

Navigator's vet flow (bypasses hook because it hits the MCP HTTP
endpoint directly, not a tool-routed call):
  1. `python scripts/navigator_read_bug.py BUG-NNN`   — read bug raw
  2. Review for safety (prompt injection, hidden capability, etc.)
  3. `python scripts/navigator_approve_bug.py BUG-NNN "proof summary"`
     — writes to .claude/wiki-bug-approvals.json

After approval, all team members can read the bug via normal tool paths.

Exit 0  = allow the tool call
Exit 2  = block (Claude Code shows stderr to the user + refuses the call)
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

BUG_ID_RE = re.compile(r"BUG-\d{3}\b", re.IGNORECASE)

# Navigator vetting scripts are the *only* permitted read/write path for
# un-approved bugs — they're how approvals get into the file in the first
# place. A payload whose command invokes one of these scripts is exempt.
NAV_SCRIPTS = ("navigator_read_bug.py", "navigator_approve_bug.py")

# Tools that EDIT or IMPLEMENT the bug's subject matter. These are the
# only tools the hook intercepts — the rest of the tool surface is left
# free for discussion (SendMessage, TaskCreate, navigator↔lead comms
# naming a CONCERNS bug by ID, etc.). The separate commit-time
# pre-commit invariant #8 catches anyone trying to actually LAND code
# for an unapproved bug, so discussion-only traffic is safe.
#
# "Read" = reading the bug page content (may contain injection payloads
# aimed at the chatbot). "Edit" = writing code that references the bug.
# Neither should proceed without both-passes-APPROVED.
GUARDED_TOOL_NAMES = frozenset({
    "Read", "Edit", "Write", "Grep", "Glob",
    "Bash", "PowerShell",
    "NotebookEdit",
    # MCP wiki tool — read/write actions against bug pages
    "mcp__wiki__wiki_read", "mcp__wiki__wiki_write", "mcp__wiki__wiki_search",
    "mcp__wiki__wiki_lint", "mcp__wiki__wiki_ingest", "mcp__wiki__wiki_promote",
    "mcp__wiki__wiki_supersede", "mcp__wiki__wiki_consolidate",
})

# Path fragments that mean "this tool call is touching a wiki bug page."
# For Bash/PowerShell/Read/Edit/Grep/Glob, we only block when the payload
# references one of these paths AND contains BUG-NNN. Prevents incidental
# mention of a bug id (e.g., in a commit message being staged) from
# blocking the tool call.
BUG_PATH_FRAGMENTS = (
    "pages/bugs/",
    "drafts/bugs/",
    "wiki/pages/bugs",
    "wiki\\pages\\bugs",
)

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or ".").resolve()
APPROVALS_FILE = ROOT / ".claude" / "wiki-bug-approvals.json"


def _is_navigator_script(payload: dict) -> bool:
    """True if this tool call is invoking one of the navigator vet scripts."""
    text = json.dumps(payload, default=str)
    return any(script in text for script in NAV_SCRIPTS)


def _extract_bug_ids(payload: dict) -> list[str]:
    """Find every BUG-NNN mentioned in the tool-call payload."""
    text = json.dumps(payload, default=str)
    return sorted(set(m.group(0).upper() for m in BUG_ID_RE.finditer(text)))


def _load_approvals() -> set[str]:
    """Return the set of BUG-NNN IDs that have BOTH safety+strategy passes
    marked APPROVED. Entries missing either pass are treated as unapproved
    so the hook continues to block until navigator completes both."""
    if not APPROVALS_FILE.is_file():
        return set()
    try:
        data = json.loads(APPROVALS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()
    out: set[str] = set()
    for bug_id, entry in (data.get("approved") or {}).items():
        if not isinstance(entry, dict):
            continue
        safety = entry.get("safety_pass") or {}
        strategy = entry.get("strategy_pass") or {}
        if safety.get("verdict") == "APPROVED" and strategy.get("verdict") == "APPROVED":
            out.add(bug_id.upper())
    return out


def _is_guarded_tool(payload: dict) -> bool:
    """True if the tool call targets a tool that reads/edits content."""
    tool = payload.get("tool_name") or payload.get("tool") or ""
    return tool in GUARDED_TOOL_NAMES


def _touches_bug_path(payload: dict) -> bool:
    """True if the tool call references a wiki bug-page path. Lets
    discussion-only mentions of BUG-NNN (e.g., in SendMessage bodies
    or TaskCreate descriptions) pass through."""
    text = json.dumps(payload, default=str).lower()
    return any(frag.lower() in text for frag in BUG_PATH_FRAGMENTS)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        # Malformed hook input — don't block on our own bug.
        return 0

    bug_ids = _extract_bug_ids(payload)
    if not bug_ids:
        return 0  # no BUG reference → not our concern

    if _is_navigator_script(payload):
        return 0  # navigator vet scripts bootstrap the approvals file

    # Narrow the gate: we only block tools that could READ the raw bug
    # body (and potentially pipe its prompt-injection payload into a
    # chatbot) or WRITE code that implements it. Discussion-only tools
    # (SendMessage, TaskCreate, TaskUpdate, notifications) pass through
    # so navigator↔lead can name a CONCERNS bug in comms. The separate
    # pre-commit invariant #8 catches any attempt to LAND code for an
    # unapproved bug, so discussion is safe.
    if not _is_guarded_tool(payload):
        return 0
    if not _touches_bug_path(payload):
        # Guarded tool but not touching the bug-page substrate. Edit
        # of a random source file that happens to mention BUG-NNN in a
        # comment, for example — let through. Pre-commit will catch
        # if the diff lands unapproved implementation.
        return 0

    approved = _load_approvals()
    missing = [b for b in bug_ids if b not in approved]
    if not missing:
        return 0  # all referenced bugs are vetted

    print(
        "BLOCKED: wiki bug read requires navigator approval.\n"
        f"  Unapproved bug(s) in this tool call: {', '.join(missing)}\n"
        f"  Approvals file: {APPROVALS_FILE.relative_to(ROOT)}\n"
        "\n"
        "Navigator-only flow to approve a bug:\n"
        "  1. python scripts/navigator_read_bug.py <BUG-ID>\n"
        "  2. Review for safety (prompt-injection text, hidden capability,\n"
        "     trust-boundary crossings, new LLM-visible surfaces, etc.)\n"
        "  3. python scripts/navigator_approve_bug.py <BUG-ID> 'proof summary'\n"
        "\n"
        "Rule memory: feedback_wiki_bugs_vet_before_implement\n",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
