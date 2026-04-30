"""Tests for claude_chat.py send-state diagnostics.

These guard the ui-test failure class where the driver typed a prompt,
the visible Claude.ai page kept it in the composer, and the harness
misreported that as a response timeout instead of a not-submitted turn.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


@pytest.fixture
def claude_chat():
    root = Path(__file__).resolve().parent.parent
    src = root / "scripts" / "claude_chat.py"
    spec = importlib.util.spec_from_file_location(
        "_claude_chat_send_state_under_test", src,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["_claude_chat_send_state_under_test"] = module
    spec.loader.exec_module(module)
    return module


class FakeLocator:
    def __init__(
        self,
        *,
        visible: bool = True,
        text: str = "",
        attrs: dict[str, str | None] | None = None,
        disabled_eval: bool = False,
    ) -> None:
        self._visible = visible
        self._text = text
        self._attrs = attrs or {}
        self._disabled_eval = disabled_eval

    def count(self) -> int:
        return 1 if self._visible else 0

    def nth(self, _i: int) -> "FakeLocator":
        return self

    def is_visible(self) -> bool:
        return self._visible

    def get_attribute(self, name: str) -> str | None:
        return self._attrs.get(name)

    def evaluate(self, script: str):
        if "tagName.toLowerCase() === 'textarea'" in script:
            return False
        if "Boolean(" in script:
            return self._disabled_eval
        if "innerText" in script or "textContent" in script:
            return self._text
        return None


class FakePage:
    def __init__(
        self,
        *,
        input_locator: FakeLocator | None = None,
        visible_text: str = "",
    ) -> None:
        self._input_locator = input_locator
        self._visible_text = visible_text

    def locator(self, _selector: str) -> FakeLocator:
        return self._input_locator or FakeLocator(visible=False)

    def evaluate(self, _script: str) -> str:
        return self._visible_text


def test_composer_contains_message_when_prompt_was_not_submitted(claude_chat):
    page = FakePage(input_locator=FakeLocator(text="  hello workflow  "))

    contains, text = claude_chat._composer_contains_message(
        page, "hello workflow",
    )

    assert contains is True
    assert text == "  hello workflow  "


def test_composer_contains_message_normalizes_whitespace(claude_chat):
    page = FakePage(input_locator=FakeLocator(text="hello\n\nworkflow"))

    contains, _ = claude_chat._composer_contains_message(
        page, "hello workflow",
    )

    assert contains is True


def test_composer_contains_message_false_when_input_missing(claude_chat):
    page = FakePage(input_locator=None)

    contains, text = claude_chat._composer_contains_message(
        page, "hello workflow",
    )

    assert contains is False
    assert text == ""


def test_locator_is_disabled_from_disabled_attribute(claude_chat):
    locator = FakeLocator(attrs={"disabled": ""})

    assert claude_chat._locator_is_disabled(locator) is True


def test_locator_is_disabled_from_aria_attribute(claude_chat):
    locator = FakeLocator(attrs={"aria-disabled": "true"})

    assert claude_chat._locator_is_disabled(locator) is True


def test_locator_is_disabled_from_dom_evaluation(claude_chat):
    locator = FakeLocator(disabled_eval=True)

    assert claude_chat._locator_is_disabled(locator) is True


def test_visible_submit_block_note_extracts_usage_limit(claude_chat):
    page = FakePage(
        visible_text=(
            "Good evening\n"
            "You're out of extra usage\n"
            "Your limit resets Friday at 7:00 PM\n"
            "Buy more\n"
        ),
    )

    note = claude_chat._visible_submit_block_note(page)

    assert "out of extra usage" in note
    assert "limit resets" in note
    assert "Buy more" in note
