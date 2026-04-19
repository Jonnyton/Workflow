"""Concerns-staleness invariant: STATUS.md Concerns evaluated for drift.

Wraps `scripts/concerns_resolve.py` under the Invariant contract.
Propose-only per project norm (STATUS.md Concerns is host-managed;
never auto-edited). So:

    check() — runs the heuristics, reports the count of proposals
              flagged RESOLVED or SUPERSEDED as a VIOLATION. Host
              curates based on the proposals file.

    heal()  — no-op (auto_heal=False). Surfaces the proposals path
              for a human to act on.

On-demand scope: not in the pre-commit hook (host-managed content
should not block commits) and no continuous poll (once per session
or via cron is enough).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from . import CheckResult, Invariant, Status

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONCERNS_RESOLVE = REPO_ROOT / "scripts" / "concerns_resolve.py"
PROPOSALS_PATH = REPO_ROOT / "output" / "concerns_trim_proposals.md"


def _load_concerns_resolve():
    spec = importlib.util.spec_from_file_location(
        "concerns_resolve_for_invariant", CONCERNS_RESOLVE,
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class ConcernsStalenessInvariant(Invariant):
    name = "concerns-staleness"
    description = "STATUS.md Concerns have no machine-detectable stale items."
    pre_commit_scope = False
    poll_interval_s = None  # on-demand (host-managed section)
    auto_heal = False

    def _check(self) -> CheckResult:
        if not CONCERNS_RESOLVE.exists():
            return CheckResult(
                status=Status.SKIPPED,
                message=f"concerns_resolve.py not found at {CONCERNS_RESOLVE}",
            )
        mod = _load_concerns_resolve()
        status_text = mod.STATUS_PATH.read_text(encoding="utf-8")
        concerns = mod._read_concerns_section(status_text)
        if not concerns:
            return CheckResult(
                status=Status.OK,
                message="STATUS.md Concerns section is empty",
                evidence={"concern_count": 0},
            )

        commits = mod._git_log_oneline(limit=200)
        proposals = [mod.evaluate_concern(c, commits) for c in concerns]
        resolved = [p for p in proposals if p.verdict == "RESOLVED"]
        superseded = [p for p in proposals if p.verdict == "SUPERSEDED"]
        current = [p for p in proposals if p.verdict == "CURRENT"]

        stale = len(resolved) + len(superseded)
        if stale == 0:
            return CheckResult(
                status=Status.OK,
                message=(
                    f"{len(current)} concern(s); none machine-flagged as "
                    f"stale"
                ),
                evidence={"concern_count": len(current)},
            )

        # Write proposals as a side effect so the human curator has
        # something to read. This is I/O, not a STATUS.md mutation —
        # still conforms to the "propose-only" contract.
        mod.write_proposals(proposals, PROPOSALS_PATH)

        return CheckResult(
            status=Status.VIOLATED,
            message=(
                f"{stale} concern(s) machine-flagged as stale "
                f"(RESOLVED={len(resolved)}, SUPERSEDED={len(superseded)}). "
                f"See {PROPOSALS_PATH.relative_to(REPO_ROOT)}."
            ),
            evidence={
                "resolved": len(resolved),
                "superseded": len(superseded),
                "current": len(current),
                "proposals_path": str(PROPOSALS_PATH.relative_to(REPO_ROOT)),
            },
        )
