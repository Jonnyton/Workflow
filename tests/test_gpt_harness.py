"""Tests for GPTHarness -- mocks Playwright to verify orchestration logic."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from fantasy_author.testing.gpt_harness import GPTHarness, GPTResponse


@pytest.fixture()
def mock_playwright():
    """Patch playwright and return the mock objects."""
    with patch("fantasy_author.testing.gpt_harness.sync_playwright") as sp:
        pw = MagicMock()
        ctx_mgr = MagicMock()
        ctx_mgr.start.return_value = pw
        ctx_mgr.__exit__ = MagicMock(return_value=False)
        sp.return_value = ctx_mgr

        browser_ctx = MagicMock()
        page = MagicMock()
        browser_ctx.new_page.return_value = page
        pw.chromium.launch_persistent_context.return_value = browser_ctx

        yield {
            "sync_playwright": sp,
            "pw": pw,
            "ctx_mgr": ctx_mgr,
            "browser_ctx": browser_ctx,
            "page": page,
        }


def _setup_response_page(page, *, response_text="Here is the story status.",
                          body_text=None, clipboard_text=None,
                          has_copy_button=True):
    """Wire up mock page to simulate a ChatGPT response cycle.

    Configures the page.locator() mock to return appropriate locator mocks
    for assistant messages, copy buttons, stop buttons, and input elements.
    """
    page.wait_for_selector.return_value = MagicMock()

    # Body text for metadata extraction (thinking, actions).
    if body_text is None:
        body_text = response_text

    # Assistant message locator: starts at 0, then shows 1 message.
    assistant_locator = MagicMock()
    call_count = {"n": 0}

    def count_side_effect():
        call_count["n"] += 1
        if call_count["n"] <= 1:
            return 0  # before_count
        return 1  # new message appeared

    assistant_locator.count.side_effect = count_side_effect

    last_msg = MagicMock()
    last_msg.inner_text.return_value = response_text

    # Copy button inside the last assistant message.
    copy_btn = MagicMock()
    copy_btn.count.return_value = 1 if has_copy_button else 0
    copy_btn.first = MagicMock()
    last_msg.locator.return_value = copy_btn

    assistant_locator.nth.return_value = last_msg

    # Clipboard behavior.
    if clipboard_text is not None:
        page.evaluate.side_effect = lambda js, *a: clipboard_text if "clipboard" in js else None
    else:
        page.evaluate.side_effect = lambda js, *a: None

    # Stop button: not visible.
    stop_locator = MagicMock()
    stop_locator.count.return_value = 0

    # Body locator for metadata extraction.
    body_locator = MagicMock()
    body_locator.inner_text.return_value = body_text

    # Input and send button locators.
    input_locator = MagicMock()
    send_locator = MagicMock()
    send_locator.wait_for.return_value = None

    def locator_dispatch(selector):
        if "assistant" in selector:
            return assistant_locator
        if "Stop" in selector:
            return stop_locator
        if "body" == selector:
            return body_locator
        if "prompt-textarea" in selector:
            mock = MagicMock()
            mock.first = input_locator
            return mock
        if "send-button" in selector:
            mock = MagicMock()
            mock.first = send_locator
            return mock
        return MagicMock()

    page.locator.side_effect = locator_dispatch

    return {
        "assistant_locator": assistant_locator,
        "last_msg": last_msg,
        "copy_btn": copy_btn,
        "body_locator": body_locator,
    }


class TestGPTHarnessLifecycle:
    def test_start_navigates_to_url(self, mock_playwright):
        page = mock_playwright["page"]
        page.wait_for_selector.return_value = MagicMock()

        harness = GPTHarness("https://chatgpt.com/g/test-gpt")
        harness.start()

        page.goto.assert_called_once()
        assert "test-gpt" in page.goto.call_args[0][0]
        harness.close()

    def test_context_manager(self, mock_playwright):
        page = mock_playwright["page"]
        page.wait_for_selector.return_value = MagicMock()

        with GPTHarness("https://chatgpt.com/g/test-gpt") as harness:
            assert harness._page is not None
        mock_playwright["browser_ctx"].close.assert_called_once()

    def test_close_without_start(self):
        harness = GPTHarness("https://chatgpt.com/g/test-gpt")
        harness.close()

    def test_send_without_start_raises(self):
        harness = GPTHarness("https://chatgpt.com/g/test-gpt")
        with pytest.raises(RuntimeError, match="not started"):
            harness.send_message("hello")


class TestGPTHarnessSendMessage:
    def test_send_returns_gpt_response(self, mock_playwright):
        page = mock_playwright["page"]
        _setup_response_page(page, response_text="Here is the story status.")

        harness = GPTHarness("https://chatgpt.com/g/test-gpt")
        harness.start()

        response = harness.send_message("What's happening?")
        assert isinstance(response, GPTResponse)
        assert "story status" in response.text
        assert harness._message_count == 1
        harness.close()

    def test_copy_button_used_as_done_signal(self, mock_playwright):
        page = mock_playwright["page"]
        mocks = _setup_response_page(page, response_text="Done response.")

        harness = GPTHarness("https://chatgpt.com/g/test-gpt")
        harness.start()

        response = harness.send_message("test")
        # The copy button locator should have been checked.
        mocks["last_msg"].locator.assert_called()
        assert response.text == "Done response."
        harness.close()

    def test_clipboard_extraction(self, mock_playwright):
        page = mock_playwright["page"]
        _setup_response_page(
            page,
            response_text="DOM text",
            clipboard_text="Clipboard text with **formatting**",
        )

        harness = GPTHarness("https://chatgpt.com/g/test-gpt")
        harness.start()

        response = harness.send_message("test")
        assert "Clipboard text" in response.text
        harness.close()

    def test_dom_fallback_when_clipboard_fails(self, mock_playwright):
        page = mock_playwright["page"]
        _setup_response_page(
            page,
            response_text="Fallback DOM text",
            clipboard_text=None,  # Clipboard returns None
        )

        harness = GPTHarness("https://chatgpt.com/g/test-gpt")
        harness.start()

        response = harness.send_message("test")
        assert response.text == "Fallback DOM text"
        harness.close()

    def test_persistent_profile_path(self, mock_playwright):
        page = mock_playwright["page"]
        page.wait_for_selector.return_value = MagicMock()

        harness = GPTHarness(
            "https://chatgpt.com/g/test-gpt",
            profile_dir="/tmp/test-profile",
        )
        harness.start()

        call_args = mock_playwright["pw"].chromium.launch_persistent_context.call_args
        assert "test-profile" in call_args[0][0]
        harness.close()

    def test_headless_flag_passed(self, mock_playwright):
        page = mock_playwright["page"]
        page.wait_for_selector.return_value = MagicMock()

        harness = GPTHarness(
            "https://chatgpt.com/g/test-gpt", headless=True
        )
        harness.start()

        call_kwargs = mock_playwright["pw"].chromium.launch_persistent_context.call_args[1]
        assert call_kwargs["headless"] is True
        harness.close()


class TestGPTResponseMetadata:
    def test_thinking_seconds_captured(self, mock_playwright):
        page = mock_playwright["page"]
        _setup_response_page(
            page,
            response_text="Analysis complete.",
            body_text="Thought for 12 seconds\nAnalysis complete.",
        )

        harness = GPTHarness("https://chatgpt.com/g/test-gpt")
        harness.start()

        response = harness.send_message("analyze this")
        assert response.thinking_seconds == 12.0
        harness.close()

    def test_action_calls_captured(self, mock_playwright):
        page = mock_playwright["page"]
        _setup_response_page(
            page,
            response_text="Your story is progressing.",
            body_text=(
                "Talked to api.example.com\n"
                "Talked to api.example.com\n"
                "Your story is progressing."
            ),
        )

        harness = GPTHarness("https://chatgpt.com/g/test-gpt")
        harness.start()

        response = harness.send_message("status?")
        assert len(response.actions) == 2
        assert all("api.example.com" in a for a in response.actions)
        harness.close()

    def test_action_failures_captured(self, mock_playwright):
        page = mock_playwright["page"]
        _setup_response_page(
            page,
            response_text="Something went wrong.",
            body_text=(
                "Talked to api.example.com\n"
                "Stopped talking to api.example.com\n"
                "Something went wrong."
            ),
        )

        harness = GPTHarness("https://chatgpt.com/g/test-gpt")
        harness.start()

        response = harness.send_message("do something")
        assert len(response.actions) == 1
        assert len(response.action_failures) == 1
        assert "api.example.com" in response.action_failures[0]
        harness.close()

    def test_str_includes_metadata(self):
        resp = GPTResponse(
            text="The daemon is writing.",
            thinking_seconds=8,
            actions=["api.example.com"],
            action_failures=[],
        )
        rendered = str(resp)
        assert "[thinking: 8s]" in rendered
        assert "[action: api.example.com]" in rendered
        assert "The daemon is writing." in rendered

    def test_str_plain_when_no_metadata(self):
        resp = GPTResponse(text="Just text.")
        assert str(resp) == "Just text."
