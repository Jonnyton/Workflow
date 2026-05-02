"""Cross-provider drift invariant.

Wraps `scripts/check_cross_provider_drift.py` so the same guard can run through
the unified invariant runner and the pre-commit path.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from . import CheckResult, Invariant, Status

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CHECKER = REPO_ROOT / "scripts" / "check_cross_provider_drift.py"


def _load_checker():
    spec = importlib.util.spec_from_file_location(
        "cross_provider_drift_checker_for_invariant", CHECKER
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class CrossProviderDriftInvariant(Invariant):
    name = "cross-provider-drift"
    description = "Provider-specific rules do not drift from AGENTS.md."
    pre_commit_scope = True
    poll_interval_s = None
    auto_heal = False

    def _check(self) -> CheckResult:
        if not CHECKER.exists():
            return CheckResult(
                status=Status.VIOLATED,
                message=f"checker missing: {CHECKER.relative_to(REPO_ROOT)}",
                evidence={"missing": str(CHECKER.relative_to(REPO_ROOT))},
            )

        checker = _load_checker()
        issues = checker.run_checks(REPO_ROOT)
        if not issues:
            return CheckResult(
                status=Status.OK,
                message="cross-provider drift check clean",
                evidence={"issues": 0},
            )

        return CheckResult(
            status=Status.VIOLATED,
            message=f"{len(issues)} cross-provider drift issue(s)",
            evidence={
                "issues": [
                    {
                        "code": issue.code,
                        "path": issue.path,
                        "message": issue.message,
                        "prescription": issue.prescription,
                    }
                    for issue in issues
                ]
            },
        )
