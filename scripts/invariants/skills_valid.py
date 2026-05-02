"""Project skill validation invariant.

Wraps `scripts/validate_skills.py` so skill metadata, router coverage, and
`.agents` -> `.claude` mirror hygiene run through the shared invariant gate.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from . import CheckResult, Invariant, Status

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
VALIDATOR = REPO_ROOT / "scripts" / "validate_skills.py"


def _load_validator():
    spec = importlib.util.spec_from_file_location("skills_validator_for_invariant", VALIDATOR)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class SkillsValidInvariant(Invariant):
    name = "skills-valid"
    description = "Project-local skills have valid metadata, routing, and mirrors."
    pre_commit_scope = True
    poll_interval_s = None
    auto_heal = False

    def _check(self) -> CheckResult:
        if not VALIDATOR.exists():
            return CheckResult(
                status=Status.VIOLATED,
                message=f"validator missing: {VALIDATOR.relative_to(REPO_ROOT)}",
                evidence={"missing": str(VALIDATOR.relative_to(REPO_ROOT))},
            )

        validator = _load_validator()
        issues = validator.validate_all(REPO_ROOT)
        if not issues:
            return CheckResult(
                status=Status.OK,
                message="skill validation passed",
                evidence={"issues": 0},
            )

        return CheckResult(
            status=Status.VIOLATED,
            message=f"{len(issues)} skill validation issue(s)",
            evidence={"issues": [issue.format() for issue in issues]},
        )
