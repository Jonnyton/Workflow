"""Tests for the thinking-step capture + trace formatter in claude_chat.py.

Navigator reads `output/claude_chat_trace.md` to diagnose chatbot
behavior. The expanded thinking transcript is the most diagnostically
valuable layer — it reveals where the chatbot hallucinates, dismisses
signals, or defaults to generic patterns. These tests pin the trace
format + thinking-expansion helper contracts without touching a live
browser.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

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
    return _load_module("claude_chat_under_test_thinking", SCRIPTS / "claude_chat.py")


# -------------------------------------------------------------------
# _format_assistant_trace — pure function
# -------------------------------------------------------------------


def test_format_trace_without_thinking_is_backward_compatible(claude_chat):
    """No thinking → plain response body + rich section (old format)."""
    body = claude_chat._format_assistant_trace(
        response="hello user-sim",
        thinking="",
        rich_section="",
    )
    assert body == "hello user-sim"


def test_format_trace_with_rich_section_preserves_suffix(claude_chat):
    """Backward-compat: rich_section appended without thinking wrapper."""
    body = claude_chat._format_assistant_trace(
        response="final reply",
        thinking="",
        rich_section="\n\n[rich content: 1 artifact]",
    )
    assert body == "final reply\n\n[rich content: 1 artifact]"


def test_format_trace_with_thinking_wraps_in_sections(claude_chat):
    """Thinking non-empty → `<thinking>`/`<reply>` section wrap."""
    body = claude_chat._format_assistant_trace(
        response="visible answer",
        thinking="the chatbot considered X then Y",
        rich_section="",
    )
    assert "<thinking>" in body
    assert "</thinking>" in body
    assert "<reply>" in body
    assert "</reply>" in body
    assert "the chatbot considered X then Y" in body
    assert "visible answer" in body
    # Ordering: thinking before reply, so diagnostic context lands first.
    assert body.index("<thinking>") < body.index("<reply>")


def test_format_trace_empty_response_substitutes_placeholder(claude_chat):
    body = claude_chat._format_assistant_trace(
        response="",
        thinking="",
        rich_section="",
    )
    assert body == "(empty response)"


def test_format_trace_rich_section_after_reply_when_thinking_present(claude_chat):
    """Rich section must land after the reply, not inside it."""
    body = claude_chat._format_assistant_trace(
        response="reply text",
        thinking="reasoning text",
        rich_section="\n\n[artifact payload]",
    )
    # Rich section attaches at the end — after `</reply>`.
    assert body.endswith("</reply>\n\n[artifact payload]")


# -------------------------------------------------------------------
# _expand_thinking_blocks + _read_thinking_text — locator mocks
# -------------------------------------------------------------------


class _FakeLocator:
    """Minimal Playwright locator stub."""

    def __init__(self, children: dict[str, list["_FakeButton | _FakeContainer"]] | None = None):
        self._children = children or {}

    def locator(self, selector: str):
        # Return a _FakeMultiLocator wrapping any matches for this selector.
        return _FakeMultiLocator(self._children.get(selector, []))


class _FakeMultiLocator:
    def __init__(self, items: list):
        self._items = items

    def count(self) -> int:
        return len(self._items)

    def nth(self, i: int):
        return self._items[i]


class _FakeButton:
    def __init__(self, visible: bool = True, clickable: bool = True):
        self._visible = visible
        self._clickable = clickable
        self.click_count = 0

    def is_visible(self) -> bool:
        return self._visible

    def click(self, timeout: int = 2000) -> None:
        self.click_count += 1
        if not self._clickable:
            raise RuntimeError("simulated click failure")


class _FakeContainer:
    def __init__(self, text: str):
        self._text = text

    def inner_text(self) -> str:
        return self._text


def test_expand_thinking_blocks_clicks_visible_expander(claude_chat):
    btn = _FakeButton(visible=True)
    last = _FakeLocator({
        '[data-testid*="thinking" i] button[aria-expanded="false"]': [btn],
    })

    clicked = claude_chat._expand_thinking_blocks(last)

    assert clicked == 1
    assert btn.click_count == 1


def test_expand_thinking_blocks_skips_invisible_expander(claude_chat):
    btn = _FakeButton(visible=False)
    last = _FakeLocator({
        '[data-testid*="thinking" i] button[aria-expanded="false"]': [btn],
    })

    clicked = claude_chat._expand_thinking_blocks(last)

    assert clicked == 0
    assert btn.click_count == 0


def test_expand_thinking_blocks_survives_click_failure(claude_chat):
    """One failing click doesn't abort the loop — others still proceed."""
    bad = _FakeButton(visible=True, clickable=False)
    good = _FakeButton(visible=True)
    # Put both under the SAME selector so the for-loop processes them.
    last = _FakeLocator({
        '[data-testid*="thinking" i] button[aria-expanded="false"]': [bad, good],
    })

    # Should NOT raise.
    clicked = claude_chat._expand_thinking_blocks(last)

    # Bad click attempted + failed → does NOT count; good click succeeded.
    assert clicked == 1
    assert bad.click_count == 1  # attempted
    assert good.click_count == 1


def test_expand_thinking_blocks_returns_zero_for_no_last_locator(claude_chat):
    assert claude_chat._expand_thinking_blocks(None) == 0


def test_expand_thinking_blocks_returns_zero_when_no_expanders_match(claude_chat):
    last = _FakeLocator({})  # no selector matches

    clicked = claude_chat._expand_thinking_blocks(last)

    assert clicked == 0


def test_read_thinking_text_returns_first_matched_container(claude_chat):
    container = _FakeContainer("the chatbot's reasoning chain")
    last = _FakeLocator({
        '[data-testid*="thinking" i]': [container],
    })

    text = claude_chat._read_thinking_text(last)

    assert text == "the chatbot's reasoning chain"


def test_read_thinking_text_concatenates_multiple_containers(claude_chat):
    a = _FakeContainer("step one")
    b = _FakeContainer("step two")
    last = _FakeLocator({
        '[data-testid*="thinking" i]': [a, b],
    })

    text = claude_chat._read_thinking_text(last)

    assert text == "step one\n\nstep two"


def test_read_thinking_text_returns_empty_when_no_container(claude_chat):
    last = _FakeLocator({})

    text = claude_chat._read_thinking_text(last)

    assert text == ""


def test_read_thinking_text_returns_empty_for_no_last_locator(claude_chat):
    assert claude_chat._read_thinking_text(None) == ""


# -------------------------------------------------------------------
# Selector constants — regression guard against accidental edits
# -------------------------------------------------------------------


def test_thinking_container_selectors_not_empty(claude_chat):
    assert len(claude_chat.THINKING_CONTAINER_SELECTORS) >= 1


def test_thinking_expand_button_selectors_include_aria_expanded(claude_chat):
    """All button selectors must scope to aria-expanded='false' so an
    already-expanded block isn't re-clicked (which would collapse it)."""
    for sel in claude_chat.THINKING_EXPAND_BUTTON_SELECTORS:
        assert 'aria-expanded="false"' in sel, (
            f"Expander selector must target collapsed-state only; got: {sel}"
        )


# -------------------------------------------------------------------
# _trace_timestamp — ISO-8601 + millisecond precision + tz offset
# -------------------------------------------------------------------


def test_trace_timestamp_is_iso_8601_with_millis_and_tz(claude_chat):
    """Navigator reads trace chronologically across providers; format must
    be ISO-8601 + ms + tz offset so ambiguity on close-in-time events is
    impossible.
    """
    import re

    ts = claude_chat._trace_timestamp()

    # YYYY-MM-DDTHH:MM:SS.mmm followed by +HHMM or -HHMM.
    pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}[+-]\d{4}$"
    assert re.match(pattern, ts), (
        f"Timestamp must be ISO-8601 + ms + tz offset; got: {ts!r}"
    )


def test_trace_timestamps_sort_chronologically_as_strings(claude_chat):
    """Consecutive calls produce strings that sort lexicographically."""
    ts1 = claude_chat._trace_timestamp()
    ts2 = claude_chat._trace_timestamp()

    # Lexicographic comparison works for ISO-8601 so ordering navigators
    # expect (earliest-first in a log) holds via simple string sort.
    assert ts1 <= ts2
