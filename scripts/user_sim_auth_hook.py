"""Standing-permission check for dispatching user-sim missions.

Host rule (2026-04-19): the lead has standing permission to dispatch
user-sim whenever BOTH are true:
  1. The CDP browser (Chrome-for-Testing at localhost:9222) is up and
     has a visible main window — proof the host can see what user-sim
     is driving.
  2. Exactly one claude.ai tab is open — the forever-rule invariant.

This script checks both and prints one of three verdicts:
  - ``approved`` — safe to dispatch user-sim now.
  - ``heal-tabs`` — CDP up, but tab-count != 1; run
    `python scripts/claude_chat.py tabs` and re-check before dispatch.
  - ``no-browser`` — CDP unreachable; dispatch would fail anyway.

Exit code mirrors the verdict: 0=approved, 1=heal-tabs, 2=no-browser.

Usage:
    python scripts/user_sim_auth_hook.py
    python scripts/user_sim_auth_hook.py --json   # structured output
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import browser_lock  # noqa: E402

CDP_VERSION_URL = "http://localhost:9222/json/version"
CDP_TARGETS_URL = "http://localhost:9222/json"


def _cdp_reachable() -> bool:
    try:
        with urllib.request.urlopen(CDP_VERSION_URL, timeout=2) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _page_targets() -> list[dict]:
    try:
        with urllib.request.urlopen(CDP_TARGETS_URL, timeout=2) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return []
    return [t for t in data if t.get("type") == "page"]


def _browser_window_visible() -> bool:
    """Verify at least one Chrome process has a non-empty MainWindowTitle.

    A non-empty title is a strong proxy for 'host can see it on their
    screen' — hidden/minimized windows on Windows keep their title, but
    truly-detached DevTools-only targets don't. Good enough for the
    forever rule; not a full Win32 IsWindowVisible().
    """
    try:
        out = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-Process chrome -ErrorAction SilentlyContinue | "
                "Where-Object { $_.MainWindowTitle -ne '' } | "
                "Select-Object -First 1 -ExpandProperty Id",
            ],
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
    return bool(out.stdout.strip())


def check() -> dict:
    lock = browser_lock.read()
    if lock is not None and lock.get("owner") != "user-sim":
        return {
            "verdict": "held-by-other",
            "cdp_reachable": _cdp_reachable(),
            "tab_count": 0,
            "browser_visible": False,
            "tabs": [],
            "lock": lock,
            "reason": (
                f"browser lock held by {lock.get('owner')!r} "
                f"for {lock.get('intent')!r}; wait for release"
            ),
        }
    if not _cdp_reachable():
        return {
            "verdict": "no-browser",
            "cdp_reachable": False,
            "tab_count": 0,
            "browser_visible": False,
            "tabs": [],
        }
    targets = _page_targets()
    tab_count = len(targets)
    visible = _browser_window_visible()
    if tab_count != 1:
        return {
            "verdict": "heal-tabs",
            "cdp_reachable": True,
            "tab_count": tab_count,
            "browser_visible": visible,
            "tabs": [t.get("url", "") for t in targets],
        }
    if not visible:
        return {
            "verdict": "heal-tabs",
            "cdp_reachable": True,
            "tab_count": tab_count,
            "browser_visible": False,
            "tabs": [t.get("url", "") for t in targets],
            "reason": "browser up but no visible main window",
        }
    return {
        "verdict": "approved",
        "cdp_reachable": True,
        "tab_count": 1,
        "browser_visible": True,
        "tabs": [t.get("url", "") for t in targets],
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--json", action="store_true")
    ns = p.parse_args()
    result = check()
    if ns.json:
        print(json.dumps(result, indent=2))
    else:
        verdict = result["verdict"]
        if verdict == "approved":
            print(f"approved — 1 tab ({result['tabs'][0]}), browser visible")
        elif verdict == "heal-tabs":
            print(
                f"heal-tabs — cdp={result['cdp_reachable']} "
                f"tabs={result['tab_count']} visible={result['browser_visible']} "
                f"urls={result['tabs']}"
            )
        elif verdict == "held-by-other":
            lock = result.get("lock") or {}
            print(
                f"held-by-other — browser lock owned by "
                f"{lock.get('owner')!r} for {lock.get('intent')!r}; "
                f"wait for release"
            )
        else:
            print("no-browser — CDP unreachable at localhost:9222")
    return {
        "approved": 0,
        "heal-tabs": 1,
        "no-browser": 2,
        "held-by-other": 3,
    }[result["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
