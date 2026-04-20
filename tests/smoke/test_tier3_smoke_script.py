"""Smoke: the tier3 smoke script itself runs cleanly.

Meta-test — invoke ``scripts/tier3_smoke.py`` as a subprocess. If the
smoke script fails, the GHA fails; running it under pytest surfaces the
same failure locally.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT = _REPO_ROOT / "scripts" / "tier3_smoke.py"


def test_tier3_smoke_script_exit_zero():
    assert _SCRIPT.is_file(), f"smoke script missing: {_SCRIPT}"
    result = subprocess.run(
        [sys.executable, str(_SCRIPT)],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"tier3_smoke.py failed with exit={result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    # Sanity: at least one 'ok' line printed so we know it exercised checks.
    assert "ok" in result.stdout, f"no 'ok' lines in output: {result.stdout!r}"
