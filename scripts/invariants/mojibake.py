"""Mojibake invariant: tracked text files contain no CP-1252-as-UTF-8 garble.

Wraps `scripts/fix-mojibake.py`'s `scan_file` helper. Pre-commit scope
(scans the staged-only set under the hook); diagnostic scope (scans
every tracked `.md`/`.py`/`.json`/`.toml`/`.txt` under the repo when
invoked manually).

Auto-heal IS available (fix-mojibake.py --autofix) but the framework
default keeps it opt-in via the runner's `--heal` flag; silent auto-fix
on every poll would mask the source of the drift.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from . import CheckResult, HealResult, Invariant, Status

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIX_MOJIBAKE = REPO_ROOT / "scripts" / "fix-mojibake.py"
SCAN_SUFFIXES = (".md", ".py", ".json", ".toml", ".txt")
EXCLUDE_NAMES = {"fix-mojibake.py", "test_fix_mojibake.py"}


def _load_fix_mojibake():
    spec = importlib.util.spec_from_file_location(
        "fix_mojibake_for_invariant", FIX_MOJIBAKE,
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _scannable_paths() -> list[Path]:
    """Return every tracked text file under repo root, minus exclusions."""
    out: list[Path] = []
    for path in REPO_ROOT.rglob("*"):
        # Skip noise.
        parts = set(path.parts)
        if any(p in parts for p in (".git", "__pycache__", "node_modules")):
            continue
        if not path.is_file():
            continue
        if path.suffix not in SCAN_SUFFIXES:
            continue
        if path.name in EXCLUDE_NAMES:
            continue
        out.append(path)
    return out


class MojibakeInvariant(Invariant):
    name = "mojibake"
    description = "Tracked text files have no CP-1252-as-UTF-8 garble."
    pre_commit_scope = True
    poll_interval_s = None  # diagnostic / pre-commit only
    auto_heal = True

    def _check(self) -> CheckResult:
        if not FIX_MOJIBAKE.exists():
            return CheckResult(
                status=Status.SKIPPED,
                message=f"fix-mojibake.py not found at {FIX_MOJIBAKE}",
            )
        fix = _load_fix_mojibake()
        paths = _scannable_paths()
        findings: list = []
        for p in paths:
            findings.extend(fix.scan_file(p))

        if findings:
            affected = sorted({str(f.path.relative_to(REPO_ROOT)) for f in findings})
            return CheckResult(
                status=Status.VIOLATED,
                message=(
                    f"{len(findings)} mojibake occurrence(s) across "
                    f"{len(affected)} file(s)"
                ),
                evidence={
                    "affected_files": affected,
                    "total_occurrences": len(findings),
                },
            )
        return CheckResult(
            status=Status.OK,
            message=f"{len(paths)} text file(s) scanned clean",
            evidence={"scanned": len(paths)},
        )

    def _heal(self) -> HealResult:
        fix = _load_fix_mojibake()
        paths = _scannable_paths()
        total_repairs = 0
        touched: list[str] = []
        for p in paths:
            n = fix.fix_file(p)
            if n > 0:
                total_repairs += n
                touched.append(str(p.relative_to(REPO_ROOT)))
        if total_repairs == 0:
            return HealResult(
                healed=True, message="nothing to heal",
            )
        return HealResult(
            healed=True,
            message=f"repaired {total_repairs} occurrence(s) in {len(touched)} file(s)",
            actions_taken=touched,
        )
