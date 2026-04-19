"""Tests for the tab-hygiene invariant in claude_chat.py + tab_watchdog.py.

Host-set forever rule: exactly one Chrome tab at every moment. The rule
is enforced at two layers: the `claude_chat.py` command-entry hook
(`_enforce_single_tab`) and the standalone `tab_watchdog.py` background
poller (`_enforce_once`). These tests pin the ranking, idempotency, and
exception-path contracts without touching a live CDP endpoint — mocks
stand in for Playwright's Page/Browser/Context types.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def claude_chat():
    return _load_module("claude_chat_under_test", SCRIPTS / "claude_chat.py")


@pytest.fixture(scope="module")
def tab_watchdog():
    return _load_module("tab_watchdog_under_test", SCRIPTS / "tab_watchdog.py")


class _FakePage:
    def __init__(self, url: str) -> None:
        self.url = url
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1


class _FakeContext:
    def __init__(self, pages: list[_FakePage]) -> None:
        self.pages = pages


class _FakeBrowser:
    def __init__(self, contexts: list[_FakeContext]) -> None:
        self.contexts = contexts


# -------------------------------------------------------------------
# claude_chat._enforce_single_tab
# -------------------------------------------------------------------


def test_enforce_single_tab_keeps_chat_url_closes_others(claude_chat):
    """Keeper ranking: claude.ai /chat/ URL beats any other."""
    chat = _FakePage("https://claude.ai/chat/abc123")
    new = _FakePage("https://claude.ai/new")
    ntp = _FakePage("chrome://new-tab-page/")
    blank = _FakePage("about:blank")
    browser = _FakeBrowser([_FakeContext([chat, new, ntp, blank])])

    closed = claude_chat._enforce_single_tab(browser)

    assert closed == 3
    assert chat.close_calls == 0
    assert new.close_calls == 1
    assert ntp.close_calls == 1
    assert blank.close_calls == 1


def test_enforce_single_tab_keeps_generic_claude_over_non_claude(claude_chat):
    """When no /chat/ URL exists, a bare claude.ai URL beats non-claude."""
    new = _FakePage("https://claude.ai/new")
    ntp = _FakePage("chrome://new-tab-page/")
    browser = _FakeBrowser([_FakeContext([ntp, new])])

    closed = claude_chat._enforce_single_tab(browser)

    assert closed == 1
    assert new.close_calls == 0
    assert ntp.close_calls == 1


def test_enforce_single_tab_idempotent_when_one_tab(claude_chat):
    """Returns 0 and no side effects when only one tab is open."""
    only = _FakePage("https://claude.ai/chat/abc123")
    browser = _FakeBrowser([_FakeContext([only])])

    closed = claude_chat._enforce_single_tab(browser)

    assert closed == 0
    assert only.close_calls == 0


def test_enforce_single_tab_idempotent_when_zero_tabs(claude_chat):
    """Returns 0 and no side effects when no pages are open."""
    browser = _FakeBrowser([_FakeContext([])])

    closed = claude_chat._enforce_single_tab(browser)

    assert closed == 0


def test_enumerate_pages_collects_across_contexts(claude_chat):
    """Pages collected across multiple browser contexts."""
    ctx_a = _FakeContext(
        [_FakePage("https://claude.ai/chat/a"), _FakePage("https://claude.ai/new")]
    )
    ctx_b = _FakeContext([_FakePage("chrome://new-tab-page/")])
    browser = _FakeBrowser([ctx_a, ctx_b])

    pages = claude_chat._enumerate_pages(browser)

    assert len(pages) == 3
    urls = [p.url for p in pages]
    assert "https://claude.ai/chat/a" in urls
    assert "https://claude.ai/new" in urls
    assert "chrome://new-tab-page/" in urls


def test_enforce_single_tab_survives_close_exception(claude_chat):
    """A failing .close() logs but doesn't raise; other closes proceed."""

    class _UncloseablePage(_FakePage):
        def close(self) -> None:
            super().close()
            raise RuntimeError("simulated close failure")

    chat = _FakePage("https://claude.ai/chat/abc")
    bad = _UncloseablePage("chrome://new-tab-page/")
    good = _FakePage("about:blank")
    browser = _FakeBrowser([_FakeContext([chat, bad, good])])

    # Should NOT raise.
    closed = claude_chat._enforce_single_tab(browser)

    # The failing close attempt does not count as "closed"; only successful.
    assert closed == 1
    assert chat.close_calls == 0
    assert bad.close_calls == 1  # attempted
    assert good.close_calls == 1


# -------------------------------------------------------------------
# tab_watchdog._enforce_once + _rank_page
# -------------------------------------------------------------------


class _FakePw:
    """Fake sync_playwright context: exposes .chromium.connect_over_cdp."""

    def __init__(self, browser: Any = None, connect_exc: Exception | None = None):
        self._browser = browser
        self._connect_exc = connect_exc
        self.chromium = self
        self.connect_calls = 0

    def connect_over_cdp(self, _cdp: str):
        self.connect_calls += 1
        if self._connect_exc is not None:
            raise self._connect_exc
        return self._browser


class _WatchdogBrowser(_FakeBrowser):
    """Fake browser with .close() tracked for watchdog's finally block."""

    def __init__(self, contexts: list[_FakeContext]) -> None:
        super().__init__(contexts)
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_watchdog_enforce_once_returns_minus_one_when_cdp_unreachable(tab_watchdog):
    """CDP unreachable → -1 return code, never raises."""
    pw = _FakePw(connect_exc=RuntimeError("ECONNREFUSED"))

    result = tab_watchdog._enforce_once(pw)

    assert result == -1
    assert pw.connect_calls == 1


def test_watchdog_enforce_once_closes_browser_handle(tab_watchdog):
    """Watchdog releases its CDP browser handle after each pass."""
    chat = _FakePage("https://claude.ai/chat/xyz")
    browser = _WatchdogBrowser([_FakeContext([chat])])
    pw = _FakePw(browser=browser)

    result = tab_watchdog._enforce_once(pw)

    assert result == 0
    assert browser.closed is True


def test_watchdog_closes_extras_and_keeps_chat(tab_watchdog):
    """Watchdog replicates the hook's keeper logic."""
    chat = _FakePage("https://claude.ai/chat/main")
    extra = _FakePage("chrome://new-tab-page/")
    browser = _WatchdogBrowser([_FakeContext([chat, extra])])
    pw = _FakePw(browser=browser)

    result = tab_watchdog._enforce_once(pw)

    assert result == 1
    assert chat.close_calls == 0
    assert extra.close_calls == 1


def test_watchdog_rank_matches_hook_rank(claude_chat, tab_watchdog):
    """Shared invariant: hook and watchdog agree on page ordering.

    If these diverge, a page that the hook kept would get closed by the
    watchdog (or vice versa), breaking the single-tab forever rule's
    coherence across the two enforcement layers.
    """
    urls = [
        "https://claude.ai/chat/main",
        "https://claude.ai/new",
        "chrome://new-tab-page/",
        "about:blank",
        "https://google.com/",
    ]
    pages = [_FakePage(u) for u in urls]

    # Hook's ranking (inlined from _enforce_single_tab — mirrors the
    # module-local _rank closure).
    def hook_rank(page):
        url = getattr(page, "url", "") or ""
        host = claude_chat.CLAUDE_HOST
        if host in url and "/chat/" in url:
            return 0
        if host in url:
            return 1
        return 2

    hook_order = [p.url for p in sorted(pages, key=hook_rank)]
    watchdog_order = [p.url for p in sorted(pages, key=tab_watchdog._rank_page)]

    assert hook_order == watchdog_order, (
        "Hook + watchdog ranking diverged — one enforcement layer would "
        "close a tab the other keeps, violating the single-tab invariant."
    )
