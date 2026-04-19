"""Tab-single invariant: exactly one Chrome tab at every moment.

Wraps `scripts/tab_watchdog.py`'s `_enforce_once` logic under the
unified Invariant contract. Polls the CDP endpoint; on >1 tab, picks
the mission tab (claude.ai /chat/ preferred) and closes the rest.

Continuous mode. Auto-healing. Silent when CDP unreachable — Chrome
not launched yet is a valid state; no false alarms.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from . import CheckResult, HealResult, Invariant, Status

SCRIPTS = Path(__file__).resolve().parent.parent


def _load_watchdog():
    spec = importlib.util.spec_from_file_location(
        "tab_watchdog_for_invariant", SCRIPTS / "tab_watchdog.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class TabSingleInvariant(Invariant):
    name = "tab-single"
    description = "Exactly one Chrome tab on claude.ai CDP."
    pre_commit_scope = False
    poll_interval_s = 3.0
    auto_heal = True

    def _check(self) -> CheckResult:
        watchdog = _load_watchdog()
        if watchdog.sync_playwright is None:
            return CheckResult(
                status=Status.SKIPPED,
                message="playwright not installed",
            )
        with watchdog.sync_playwright() as pw:
            try:
                browser = pw.chromium.connect_over_cdp(watchdog.CDP)
            except Exception:
                return CheckResult(
                    status=Status.SKIPPED,
                    message="CDP unreachable (Chrome not launched)",
                )
            try:
                pages = [p for ctx in browser.contexts for p in ctx.pages]
                count = len(pages)
            finally:
                try:
                    browser.close()
                except Exception:
                    pass
        if count <= 1:
            return CheckResult(
                status=Status.OK,
                message=f"{count} tab(s) open",
                evidence={"tab_count": count},
            )
        return CheckResult(
            status=Status.VIOLATED,
            message=f"{count} tabs open; expected 1",
            evidence={"tab_count": count},
        )

    def _heal(self) -> HealResult:
        watchdog = _load_watchdog()
        if watchdog.sync_playwright is None:
            return HealResult(
                healed=False, message="playwright not installed",
            )
        with watchdog.sync_playwright() as pw:
            closed = watchdog._enforce_once(pw)
        if closed == -1:
            return HealResult(
                healed=False, message="CDP unreachable; no heal attempted",
            )
        if closed == 0:
            return HealResult(
                healed=True, message="nothing to heal; already 1 tab",
            )
        return HealResult(
            healed=True,
            message=f"closed {closed} extra tab(s)",
            actions_taken=[f"closed {closed} tabs"],
        )
