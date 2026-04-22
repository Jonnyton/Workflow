#!/usr/bin/env python3
"""Navigator-only: record a vet pass for a wiki BUG-* page.

TWO-PASS VET (host rule 2026-04-22):

  Pass 1 — safety:   bug real? fix shape safe? requester plausible?
                     attack surface introduced?
  Pass 2 — strategy: aligns with project goals? expands PLAN.md
                     cleanly? better than what we have — or should we
                     research an alternative to propose instead?

Both passes must be APPROVED before dev implements. Safety-only
approvals do NOT unlock the hook.

Usage:
  python scripts/navigator_approve_bug.py BUG-018 --pass=safety "proof summary"
  python scripts/navigator_approve_bug.py BUG-018 --pass=strategy "alignment rationale"
  python scripts/navigator_approve_bug.py BUG-018 --pass=safety --concerns "specifics"
  python scripts/navigator_approve_bug.py BUG-018 --reject "reason"

Output file: .claude/wiki-bug-approvals.json
  approved[BUG-NNN] = {
    safety_pass:   {verdict, proof, vetted_at, vetted_by},
    strategy_pass: {verdict, proof, vetted_at, vetted_by}
  }
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
from pathlib import Path

BUG_RE = re.compile(r"^BUG-\d{3}$", re.IGNORECASE)
ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or ".").resolve()
APPROVALS = ROOT / ".claude" / "wiki-bug-approvals.json"


def _now() -> str:
    return _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("bug_id")
    ap.add_argument("proof", help="1-2 sentence rationale for this pass")
    ap.add_argument("--pass", dest="pass_name", choices=["safety", "strategy"])
    ap.add_argument("--verdict", choices=["APPROVED", "CONCERNS", "REJECT"], default="APPROVED")
    ap.add_argument("--reject", action="store_true", help="shortcut for --verdict REJECT")
    ap.add_argument("--concerns", action="store_true", help="shortcut for --verdict CONCERNS")
    args = ap.parse_args(argv[1:])

    if args.reject:
        args.verdict = "REJECT"
    elif args.concerns:
        args.verdict = "CONCERNS"

    if args.verdict != "REJECT" and not args.pass_name:
        print("error: --pass=safety|strategy required unless --reject", file=sys.stderr)
        return 2

    bug_id = args.bug_id.upper()
    if not BUG_RE.match(bug_id):
        print(f"bug_id must match BUG-NNN, got {args.bug_id!r}", file=sys.stderr)
        return 2

    APPROVALS.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {"approved": {}, "rejected": {}}
    if APPROVALS.is_file():
        try:
            data = json.loads(APPROVALS.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {"approved": {}, "rejected": {}}
    data.setdefault("approved", {})
    data.setdefault("rejected", {})

    if args.verdict == "REJECT":
        data["rejected"][bug_id] = {
            "vetted_by": "navigator",
            "vetted_at": _now(),
            "reason": args.proof,
        }
        # Remove any in-flight approval. Rejection is terminal.
        data["approved"].pop(bug_id, None)
        APPROVALS.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        print(f"{bug_id} rejected — hook continues to block reads.")
        return 0

    # APPROVED or CONCERNS on a specific pass.
    entry = data["approved"].setdefault(bug_id, {})
    entry[f"{args.pass_name}_pass"] = {
        "verdict": args.verdict,
        "proof": args.proof,
        "vetted_by": "navigator",
        "vetted_at": _now(),
    }
    APPROVALS.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    both_passed = (
        entry.get("safety_pass", {}).get("verdict") == "APPROVED"
        and entry.get("strategy_pass", {}).get("verdict") == "APPROVED"
    )
    if both_passed:
        print(f"{bug_id}: BOTH passes APPROVED — dev unblocked for implementation.")
    else:
        missing = []
        if entry.get("safety_pass", {}).get("verdict") != "APPROVED":
            missing.append("safety")
        if entry.get("strategy_pass", {}).get("verdict") != "APPROVED":
            missing.append("strategy")
        print(
            f"{bug_id}: {args.pass_name}_pass recorded as {args.verdict}. "
            f"Still blocked — missing pass: {', '.join(missing)}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
