"""Lead's CDP-browser driver — generic navigate / read / click / type.

Drives the same Chrome-for-Testing instance user-sim uses (CDP on
localhost:9222). Holds the shared browser lock (``browser_lock.py``)
so user-sim's auth hook defers to the lead. Obeys the forever
ONE-TAB rule.

Typical flow:
  python scripts/lead_browser.py acquire "godaddy-dns"
  python scripts/lead_browser.py goto "https://dcc.godaddy.com/control/portfolio"
  python scripts/lead_browser.py read
  python scripts/lead_browser.py screenshot
  python scripts/lead_browser.py release

If the lock is already held by user-sim, acquire fails and no
browser ops run. Lead must wait until user-sim releases (or
explicitly --force with a good reason).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import browser_lock  # noqa: E402
from claude_chat import CDP, _enforce_single_tab  # noqa: E402

OWNER = "lead"
SHOT_DIR = ROOT / "output" / "lead_browser_shots"


def _require_lock() -> None:
    if not browser_lock.is_held_by(OWNER):
        print(
            "browser lock not held by lead — acquire first "
            "(python scripts/lead_browser.py acquire <intent>)",
            file=sys.stderr,
        )
        sys.exit(2)


def _first_page(browser):
    _enforce_single_tab(browser)
    for ctx in browser.contexts:
        for p in ctx.pages:
            return p
    raise RuntimeError("no pages available in CDP browser")


def cmd_acquire(intent: str, force: bool) -> int:
    if browser_lock.acquire(OWNER, intent, force=force):
        print(f"acquired by lead for intent={intent!r}")
        return 0
    state = browser_lock.read()
    print(
        f"already held by {state.get('owner')!r} "
        f"intent={state.get('intent')!r}; use --force only if stale",
        file=sys.stderr,
    )
    return 1


def cmd_release() -> int:
    if browser_lock.release(OWNER):
        print("released")
        return 0
    print("lead did not hold the lock", file=sys.stderr)
    return 1


def cmd_status() -> int:
    state = browser_lock.read()
    if state is None:
        print("unheld")
    else:
        print(
            f"owner={state.get('owner')} "
            f"intent={state.get('intent')} "
            f"started_at={state.get('started_at')} "
            f"pid={state.get('pid')}"
        )
    return 0


def cmd_goto(url: str) -> int:
    _require_lock()
    if sync_playwright is None:
        print("playwright not installed", file=sys.stderr)
        return 2
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(CDP)
        try:
            page = _first_page(browser)
            page.goto(url, timeout=30000)
            time.sleep(1.5)
            print(f"loaded {page.url}")
            return 0
        finally:
            browser.close()


def cmd_read(selector: str | None) -> int:
    _require_lock()
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(CDP)
        try:
            page = _first_page(browser)
            if selector:
                loc = page.locator(selector)
                n = loc.count()
                for i in range(min(n, 20)):
                    print(f"[{i}] {loc.nth(i).inner_text().strip()[:500]}")
                return 0
            print(f"URL: {page.url}")
            print(f"TITLE: {page.title()}")
            print("---BODY---")
            print(page.locator("body").inner_text()[:4000])
            return 0
        finally:
            browser.close()


def cmd_click(selector: str) -> int:
    _require_lock()
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(CDP)
        try:
            page = _first_page(browser)
            page.locator(selector).first.click(timeout=10000)
            time.sleep(1.0)
            print(f"clicked {selector}")
            return 0
        finally:
            browser.close()


def cmd_type(selector: str, text: str) -> int:
    _require_lock()
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(CDP)
        try:
            page = _first_page(browser)
            page.locator(selector).first.fill(text, timeout=10000)
            print(f"typed into {selector}")
            return 0
        finally:
            browser.close()


def cmd_screenshot(name: str | None) -> int:
    _require_lock()
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%dT%H%M%S")
    fname = f"{ts}_{name or 'shot'}.png"
    path = SHOT_DIR / fname
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(CDP)
        try:
            page = _first_page(browser)
            page.screenshot(path=str(path), full_page=True)
            print(str(path))
            return 0
        finally:
            browser.close()


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status")

    acq = sub.add_parser("acquire")
    acq.add_argument("intent")
    acq.add_argument("--force", action="store_true")

    sub.add_parser("release")

    g = sub.add_parser("goto")
    g.add_argument("url")

    r = sub.add_parser("read")
    r.add_argument("--sel", default=None)

    c = sub.add_parser("click")
    c.add_argument("selector")

    t = sub.add_parser("type")
    t.add_argument("selector")
    t.add_argument("text")

    sh = sub.add_parser("screenshot")
    sh.add_argument("--name", default=None)

    ns = p.parse_args()

    if ns.cmd == "status":
        return cmd_status()
    if ns.cmd == "acquire":
        return cmd_acquire(ns.intent, ns.force)
    if ns.cmd == "release":
        return cmd_release()
    if ns.cmd == "goto":
        return cmd_goto(ns.url)
    if ns.cmd == "read":
        return cmd_read(ns.sel)
    if ns.cmd == "click":
        return cmd_click(ns.selector)
    if ns.cmd == "type":
        return cmd_type(ns.selector, ns.text)
    if ns.cmd == "screenshot":
        return cmd_screenshot(ns.name)
    return 1


if __name__ == "__main__":
    sys.exit(main())
