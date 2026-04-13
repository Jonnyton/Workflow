"""Tests for `scripts/claude_chat.py::_try_recover_input` — the auto-
recovery ladder for the "input-not-found" state user-sim kept hitting
in Mission 4.

Evidence behind the fix lives at
`output/claude_chat_failures/20260412T184237_input_not_found.html`:
Claude.ai replaced the free-text input with an `aria-activedescendant=
"ask-user-option-question-0-0"` selection widget, so `INPUT_SELECTORS`
returned nothing. The recovery ladder tries several DOM-level nudges
(click main, Escape, scroll, Tab, reload) before giving up — each step
is scoped so the primary-flow failure dump still fires only when all
strategies lose.

Tests use a fake Playwright-like Page that mutates its own state in
response to keyboard/click calls. No real browser.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


@pytest.fixture
def claude_chat(monkeypatch: pytest.MonkeyPatch):
    root = Path(__file__).resolve().parent.parent
    src = root / "scripts" / "claude_chat.py"
    spec = importlib.util.spec_from_file_location(
        "_claude_chat_recovery_under_test", src,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["_claude_chat_recovery_under_test"] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Fake Page scaffolding
# ---------------------------------------------------------------------------


class FakeLocator:
    def __init__(self, visible: bool = True) -> None:
        self._visible = visible
        self.click_count = 0

    def count(self) -> int:
        return 1 if self._visible else 0

    @property
    def first(self) -> "FakeLocator":
        return self

    def nth(self, _i: int) -> "FakeLocator":
        return self

    def is_visible(self) -> bool:
        return self._visible

    def click(self, **_kwargs) -> None:
        self.click_count += 1


class FakeKeyboard:
    def __init__(self, on_press=None) -> None:
        self._on_press = on_press
        self.presses: list[str] = []

    def press(self, key: str) -> None:
        self.presses.append(key)
        if self._on_press is not None:
            self._on_press(key)


class FakePage:
    """Minimal Page that tracks its own "input present" state.

    `selectors` is a mapping from selector string → visible boolean.
    Each recovery step can mutate this mapping to model claude.ai's
    actual DOM flip (Esc dismisses widget, input re-mounts, etc).
    """

    def __init__(
        self,
        *,
        selectors: dict[str, bool] | None = None,
        recover_on: str | None = None,
        url: str = "https://claude.ai/chat/test",
    ) -> None:
        # Start with no contenteditable input visible.
        self.selectors = selectors or {
            'div[contenteditable="true"][enterkeyhint]': False,
            'div.ProseMirror[contenteditable="true"]': False,
            'div[contenteditable="true"]': False,
            "textarea": False,
            "main, [role='main']": True,
            '[aria-activedescendant*="ask-user-option" i]': False,
            '[aria-label*="What do you want to work on" i]': False,
        }
        self._recover_on = recover_on
        self.url = url
        self.goto_calls: list[str] = []
        self.evaluate_calls: list[str] = []

        def _on_press(key: str) -> None:
            if self._recover_on == f"key:{key}":
                self.selectors['div[contenteditable="true"]'] = True
                self.selectors[
                    '[aria-activedescendant*="ask-user-option" i]'
                ] = False
                self.selectors[
                    '[aria-label*="What do you want to work on" i]'
                ] = False

        self.keyboard = FakeKeyboard(on_press=_on_press)

    def locator(self, selector: str) -> FakeLocator:
        visible = self.selectors.get(selector, False)
        return FakeLocator(visible=visible)

    def evaluate(self, script: str) -> None:
        self.evaluate_calls.append(script)
        if self._recover_on == "scroll":
            self.selectors['div[contenteditable="true"]'] = True

    def goto(self, url: str, timeout: int = 20000) -> None:
        self.goto_calls.append(url)
        if self._recover_on == "reload":
            self.selectors['div[contenteditable="true"]'] = True


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def test_selection_widget_visible_detects_ask_user_option(claude_chat) -> None:
    page = FakePage(
        selectors={'[aria-activedescendant*="ask-user-option" i]': True},
    )
    assert claude_chat._selection_widget_visible(page) is True


def test_selection_widget_visible_false_when_input_present(claude_chat) -> None:
    page = FakePage(selectors={'div[contenteditable="true"]': True})
    assert claude_chat._selection_widget_visible(page) is False


# ---------------------------------------------------------------------------
# Recovery ladder — each step mutates the fake page to simulate claude.ai
# actually responding to the attempted action.
# ---------------------------------------------------------------------------


def test_recovery_returns_immediately_when_input_already_present(
    claude_chat,
) -> None:
    """The fast-path rescan should find an input that mounted between
    the caller's first check and recovery invocation, without firing
    any DOM-mutating steps.
    """
    page = FakePage(selectors={
        'div[contenteditable="true"]': True,
        "main, [role='main']": True,
    })
    steps: list[str] = []
    inp = claude_chat._try_recover_input(page, on_step=steps.append)
    assert inp is not None
    assert steps == ["initial_rescan"]
    # No DOM mutations should have fired.
    assert page.keyboard.presses == []
    assert page.goto_calls == []


def test_recovery_via_escape_when_selection_widget_active(claude_chat) -> None:
    """The exact failure captured in the 2026-04-12 dumps: selection
    widget active, no input. Escape should dismiss the widget and
    restore the input. This is the primary recovery path — if this
    test regresses, user-sim loses chat continuity again.
    """
    page = FakePage(
        selectors={
            '[aria-activedescendant*="ask-user-option" i]': True,
            "main, [role='main']": True,
        },
        recover_on="key:Escape",
    )
    steps: list[str] = []
    inp = claude_chat._try_recover_input(page, on_step=steps.append)
    assert inp is not None
    # Must have pressed Escape at least once.
    assert "Escape" in page.keyboard.presses
    # Must have landed on one of the Escape-based recovery names.
    assert any(s.startswith("escape") for s in steps)


def test_recovery_via_main_click(claude_chat) -> None:
    """If the input only needed focus, clicking main should bring it
    back before any keyboard presses fire."""

    class MainClickPage(FakePage):
        def locator(self, selector: str):
            # Once main has been clicked, the input becomes visible.
            if selector == "main, [role='main']":
                loc = FakeLocator(visible=True)
                original_click = loc.click

                def _click(**kw):
                    original_click(**kw)
                    self.selectors['div[contenteditable="true"]'] = True
                loc.click = _click
                return loc
            visible = self.selectors.get(selector, False)
            return FakeLocator(visible=visible)

    page = MainClickPage(selectors={"main, [role='main']": True})
    steps: list[str] = []
    inp = claude_chat._try_recover_input(page, on_step=steps.append)
    assert inp is not None
    assert "main_click" in steps
    # Should NOT have escalated past the click step.
    assert "Escape" not in page.keyboard.presses
    assert page.goto_calls == []


def test_recovery_via_scroll_when_input_virtualized(claude_chat) -> None:
    page = FakePage(recover_on="scroll")
    steps: list[str] = []
    inp = claude_chat._try_recover_input(page, on_step=steps.append)
    assert inp is not None
    assert "scroll_bottom" in steps
    # One scroll evaluate must have fired.
    assert any("scrollTo" in call for call in page.evaluate_calls)


def test_recovery_via_chat_reload_last_resort(claude_chat) -> None:
    """When nothing else works, reload the current chat URL — preserves
    conversation context (same /chat/<id>).
    """
    page = FakePage(
        url="https://claude.ai/chat/abc-123",
        recover_on="reload",
    )
    steps: list[str] = []
    inp = claude_chat._try_recover_input(page, on_step=steps.append)
    assert inp is not None
    assert "chat_reload" in steps
    # Must have reloaded THE SAME chat URL (preserving context),
    # not /new.
    assert page.goto_calls == ["https://claude.ai/chat/abc-123"]
    assert all("/new" not in u for u in page.goto_calls)


def test_recovery_skips_reload_when_not_in_chat_url(claude_chat) -> None:
    """Reload only fires when we're on a /chat/ URL. On /new or elsewhere
    we don't have a chat id to preserve, so this step is a no-op."""
    page = FakePage(
        url="https://claude.ai/new",
        recover_on="reload",
    )
    steps: list[str] = []
    inp = claude_chat._try_recover_input(page, on_step=steps.append)
    # Recovery failed because /new doesn't qualify for reload and
    # nothing else works.
    assert inp is None
    assert page.goto_calls == []


def test_recovery_returns_none_when_all_strategies_fail(claude_chat) -> None:
    """All six ladder steps exhausted without finding an input — the
    primary flow's failure dump should still fire cleanly after this.
    """
    page = FakePage(
        selectors={
            '[aria-activedescendant*="ask-user-option" i]': True,
            "main, [role='main']": True,
        },
    )  # no recover_on — nothing mutates the page
    steps: list[str] = []
    inp = claude_chat._try_recover_input(page, on_step=steps.append)
    assert inp is None
    # Must have genuinely tried multiple strategies before giving up.
    assert "Escape" in page.keyboard.presses
    assert "Tab" in page.keyboard.presses


def test_recovery_never_navigates_to_new_chat(claude_chat) -> None:
    """Critical: the ladder must NEVER call /new — that loses the
    conversation. User-sim explicitly flagged this as the behavior to
    avoid when the lead opened this task.
    """
    page = FakePage(url="https://claude.ai/chat/xyz")
    claude_chat._try_recover_input(page, on_step=lambda _s: None)
    for url in page.goto_calls:
        assert "/new" not in url, (
            "recovery ladder must preserve chat context by reloading "
            "the same chat id, never navigating to /new"
        )


def test_recovery_clicks_widget_skip_button_before_escape(claude_chat) -> None:
    """Primary failure mode from 2026-04-12 dumps: selection widget is
    active and the `Skip` button is its own dismiss affordance. Clicking
    Skip is more reliable than Escape because it doesn't depend on
    widget focus. The ladder must try Skip BEFORE falling through to
    Escape / scroll / Tab / reload.
    """

    class WidgetPage(FakePage):
        def locator(self, selector: str):
            if selector.startswith('button[data-widget-action'):
                loc = FakeLocator(visible=True)

                def _click(**kw):
                    # Clicking Skip re-mounts the input and dismisses
                    # the widget — claude.ai's real behavior.
                    self.selectors['div[contenteditable="true"]'] = True
                    self.selectors[
                        '[aria-activedescendant*="ask-user-option" i]'
                    ] = False
                loc.click = _click
                return loc
            visible = self.selectors.get(selector, False)
            return FakeLocator(visible=visible)

    page = WidgetPage(
        selectors={
            '[aria-activedescendant*="ask-user-option" i]': True,
            "main, [role='main']": True,
        },
    )
    steps: list[str] = []
    inp = claude_chat._try_recover_input(page, on_step=steps.append)
    assert inp is not None
    assert "widget_skip_click" in steps
    # Skip click must happen BEFORE any Escape presses.
    assert "Escape" not in page.keyboard.presses


def test_recovery_reload_then_skip_when_widget_rerenders(claude_chat) -> None:
    """If the widget is sticky enough to survive a reload, the post-
    reload path must click Skip once more instead of giving up.
    """

    class ReloadStickyPage(FakePage):
        def __init__(self) -> None:
            super().__init__(
                selectors={
                    '[aria-activedescendant*="ask-user-option" i]': True,
                    "main, [role='main']": True,
                },
                url="https://claude.ai/chat/sticky",
            )
            self._reloaded = False
            # Prevent earlier Skip steps from firing. We only want to
            # exercise the post-reload Skip path.
            self._suppress_skip_until_reload = True

        def locator(self, selector: str):
            if selector.startswith('button[data-widget-action'):
                if self._suppress_skip_until_reload:
                    return FakeLocator(visible=False)
                loc = FakeLocator(visible=True)

                def _click(**kw):
                    self.selectors['div[contenteditable="true"]'] = True
                    self.selectors[
                        '[aria-activedescendant*="ask-user-option" i]'
                    ] = False
                loc.click = _click
                return loc
            visible = self.selectors.get(selector, False)
            return FakeLocator(visible=visible)

        def goto(self, url: str, timeout: int = 20000) -> None:
            self.goto_calls.append(url)
            self._reloaded = True
            self._suppress_skip_until_reload = False
            # Reload does NOT bring the input back on its own here —
            # only the subsequent Skip click will.

    page = ReloadStickyPage()
    steps: list[str] = []
    inp = claude_chat._try_recover_input(page, on_step=steps.append)
    assert inp is not None
    assert "chat_reload_then_skip" in steps
    assert page.goto_calls == ["https://claude.ai/chat/sticky"]


def test_recovery_is_resilient_to_exceptions(claude_chat) -> None:
    """If individual locator / keyboard calls raise, the ladder should
    swallow them and keep trying. Propagating would leave the dump
    path unreachable, which is worse than a failed recovery.
    """

    class ExplodingPage:
        url = "https://claude.ai/chat/x"
        goto_calls: list[str] = []
        evaluate_calls: list[str] = []

        class _KB:
            def press(self, _k): raise RuntimeError("keyboard boom")
        keyboard = _KB()

        def locator(self, _s): raise RuntimeError("locator boom")
        def evaluate(self, _s): raise RuntimeError("evaluate boom")
        def goto(self, _u, timeout=0): raise RuntimeError("goto boom")

    inp = claude_chat._try_recover_input(ExplodingPage())
    assert inp is None  # No recovery, but no crash either.
