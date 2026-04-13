"""Playwright-based harness for driving a Custom GPT through the ChatGPT web UI.

Usage:
    python -m fantasy_author.testing.gpt_harness URL "Your message here"

First run opens a browser for manual ChatGPT login.  Cookies persist in
~/.gpt-test-profile/ so subsequent runs are authenticated automatically.

No credentials are hardcoded -- auth is handled entirely via the persistent
browser profile.
"""

from __future__ import annotations

import argparse
import dataclasses
import logging
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING

from playwright.sync_api import sync_playwright

if TYPE_CHECKING:
    from playwright.sync_api import BrowserContext, Page

logger = logging.getLogger(__name__)

# --- Defaults ----------------------------------------------------------------

_PROFILE_DIR = Path.home() / ".gpt-test-profile"
_NAVIGATE_TIMEOUT_MS = 60_000
_RESPONSE_TIMEOUT_S = 120
_POLL_INTERVAL_S = 0.5
_LOG_INTERVAL_S = 5.0


# --- Selectors ----------------------------------------------------------------
# ChatGPT's React DOM uses these identifiers (as of 2026-04).  If OpenAI
# changes the markup, update these constants -- the rest of the harness is
# selector-agnostic.

_SEL_CHAT_INPUT = "#prompt-textarea"
_SEL_SEND_BUTTON = '[data-testid="send-button"]'
_SEL_STOP_BUTTON = '[aria-label="Stop generating"]'
_SEL_ASSISTANT_MSG = '[data-message-author-role="assistant"]'
# Copy button appears inside the assistant message container once streaming is
# done.  Multiple possible selectors to handle OpenAI markup changes.
_SEL_COPY_BUTTON = (
    'button[aria-label="Copy"], '
    'button[data-testid="copy-turn-action-button"]'
)


# --- Response dataclass -------------------------------------------------------


@dataclasses.dataclass
class GPTResponse:
    """Structured response from a GPT interaction."""

    text: str
    """The assistant's response text."""

    thinking_seconds: float | None = None
    """Seconds the GPT spent 'thinking' (from 'Thought for Xs' indicator)."""

    actions: list[str] = dataclasses.field(default_factory=list)
    """Action call indicators ('Talked to hostname', etc.)."""

    action_failures: list[str] = dataclasses.field(default_factory=list)
    """Action failure indicators ('Stopped talking to hostname')."""

    def __str__(self) -> str:
        """Human-readable rendering with metadata header."""
        parts: list[str] = []
        if self.thinking_seconds is not None:
            parts.append(f"[thinking: {self.thinking_seconds:.0f}s]")
        for a in self.actions:
            parts.append(f"[action: {a}]")
        for f in self.action_failures:
            parts.append(f"[action-failed: {f}]")
        if parts:
            return "\n".join(parts) + "\n" + self.text
        return self.text


# --- GPTHarness class ---------------------------------------------------------


class GPTHarness:
    """Drives a Custom GPT conversation through the ChatGPT web UI."""

    def __init__(
        self,
        gpt_url: str,
        *,
        profile_dir: Path | str = _PROFILE_DIR,
        headless: bool = False,
    ) -> None:
        self._gpt_url = gpt_url
        self._profile_dir = Path(profile_dir)
        self._headless = headless

        self._pw_context_manager = None
        self._pw = None
        self._browser: BrowserContext | None = None
        self._page: Page | None = None
        self._message_count = 0

    # -- lifecycle -------------------------------------------------------------

    def start(self) -> None:
        """Launch browser and navigate to the GPT URL."""
        self._pw_context_manager = sync_playwright()
        self._pw = self._pw_context_manager.start()

        self._browser = self._pw.chromium.launch_persistent_context(
            str(self._profile_dir),
            headless=self._headless,
            args=["--disable-blink-features=AutomationControlled"],
            viewport={"width": 1280, "height": 900},
        )
        self._page = self._browser.new_page()
        self._page.goto(self._gpt_url, timeout=_NAVIGATE_TIMEOUT_MS)
        logger.info("Navigated to %s", self._gpt_url)

        # If not logged in, the user needs to do it manually.
        self._wait_for_chat_ready()

    def close(self) -> None:
        """Shut down the browser."""
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._pw_context_manager:
            self._pw_context_manager.__exit__(None, None, None)
            self._pw_context_manager = None

    def __enter__(self) -> GPTHarness:
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- public API ------------------------------------------------------------

    def send_message(self, text: str) -> GPTResponse:
        """Type *text* into the chat, send it, and return a structured response.

        Blocks until the response finishes streaming (up to
        ``_RESPONSE_TIMEOUT_S`` seconds).  Returns a ``GPTResponse`` with the
        text, thinking time, action calls, and action failures.
        """
        page = self._ensure_page()

        # Count existing assistant messages so we know which one is new.
        before_count = page.locator(_SEL_ASSISTANT_MSG).count()

        self._type_and_send(page, text)
        logger.info("Sent: %s", text[:80])

        # Wait for the new assistant message to appear and finish streaming.
        response = self._wait_for_response(page, before_count)
        self._message_count += 1
        logger.info(
            "Response #%d: %d chars, %d actions",
            self._message_count,
            len(response.text),
            len(response.actions),
        )
        return response

    # -- internals -------------------------------------------------------------

    def _ensure_page(self) -> Page:
        if self._page is None:
            raise RuntimeError("Harness not started -- call .start() first")
        return self._page

    def _wait_for_chat_ready(self) -> None:
        """Block until the chat input is visible, giving time for login."""
        page = self._ensure_page()
        logger.info("Waiting for chat input to appear (log in if needed)...")
        # Long timeout: user may need to log in manually on first run.
        try:
            page.wait_for_selector(
                _SEL_CHAT_INPUT, state="visible", timeout=300_000
            )
        except Exception:
            # Fallback: look for any contenteditable or textarea
            page.wait_for_selector(
                '[contenteditable="true"], textarea',
                state="visible",
                timeout=300_000,
            )
        logger.info("Chat input ready.")

    def _type_and_send(self, page: Page, text: str) -> None:
        """Focus the chat input, type the message, and click send."""
        input_el = page.locator(_SEL_CHAT_INPUT).first
        input_el.click()

        # Clear any existing text first.
        page.keyboard.press("Control+a")
        page.keyboard.press("Backspace")

        # Inject text via JS for speed (character-by-character is slow).
        page.evaluate(
            """(text) => {
                const el = document.querySelector('%s');
                if (!el) return;
                if (el.contentEditable === 'true') {
                    el.innerHTML = '<p>' + text + '</p>';
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                } else {
                    el.value = text;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                }
            }"""
            % _SEL_CHAT_INPUT.replace("'", "\\'"),
            text,
        )

        # Small settle time for React to pick up the change.
        time.sleep(0.3)

        # Click the send button.
        send_btn = page.locator(_SEL_SEND_BUTTON).first
        try:
            send_btn.wait_for(state="visible", timeout=5_000)
            send_btn.click()
        except Exception:
            # Fallback: press Enter.
            logger.debug("Send button not found, pressing Enter")
            input_el.press("Enter")

    def _wait_for_response(
        self, page: Page, before_count: int
    ) -> GPTResponse:
        """Wait for the assistant response to finish streaming.

        Strategy:
        1. Wait for a new assistant message container to appear.
        2. Poll for the copy button inside the latest assistant message --
           ChatGPT only shows this after streaming completes.
        3. Grab the response text via the copy button (clipboard) or DOM
           fallback.
        4. Capture metadata: thinking time, action calls, action failures.
        """
        deadline = time.monotonic() + _RESPONSE_TIMEOUT_S
        last_log = time.monotonic()

        # Step 1: Wait for a new assistant message to appear.
        logger.info("Waiting for assistant response...")
        while time.monotonic() < deadline:
            current = page.locator(_SEL_ASSISTANT_MSG).count()
            if current > before_count:
                logger.info("Assistant message container appeared.")
                break
            if time.monotonic() - last_log >= _LOG_INTERVAL_S:
                logger.info(
                    "Still waiting for response... (%.0fs elapsed)",
                    time.monotonic() - (deadline - _RESPONSE_TIMEOUT_S),
                )
                last_log = time.monotonic()
            time.sleep(_POLL_INTERVAL_S)
        else:
            raise TimeoutError(
                f"No assistant response appeared within {_RESPONSE_TIMEOUT_S}s"
            )

        # Step 2: Wait for the copy button (definitive completion signal).
        response_text = self._wait_for_copy_button(page, deadline)

        # Step 3: Capture metadata from the turn.
        metadata = self._capture_turn_metadata(page)

        return GPTResponse(
            text=response_text,
            thinking_seconds=metadata["thinking_seconds"],
            actions=metadata["actions"],
            action_failures=metadata["action_failures"],
        )

    def _wait_for_copy_button(self, page: Page, deadline: float) -> str:
        """Wait for the copy button to appear, then extract response text.

        The copy button only appears after streaming is fully complete --
        this is the most reliable "done" signal for ChatGPT responses.

        Attempts to use the copy button to grab text via clipboard.  Falls
        back to DOM innerText extraction if clipboard is unavailable.
        """
        last_log = time.monotonic()
        action_detected = False

        while time.monotonic() < deadline:
            # Get the latest assistant message container.
            msgs = page.locator(_SEL_ASSISTANT_MSG)
            count = msgs.count()
            if count == 0:
                time.sleep(_POLL_INTERVAL_S)
                continue

            last_msg = msgs.nth(count - 1)

            # Check for copy button inside this message.
            copy_btn = last_msg.locator(_SEL_COPY_BUTTON)
            if copy_btn.count() > 0:
                logger.info("Copy button detected -- response complete.")
                return self._extract_via_copy_button(page, copy_btn, last_msg)

            # Progress logging: report what we see while waiting.
            now = time.monotonic()
            if now - last_log >= _LOG_INTERVAL_S:
                elapsed = now - (deadline - _RESPONSE_TIMEOUT_S)
                # Check for action indicators mid-stream.
                if not action_detected and self._has_action_indicator(page):
                    logger.info(
                        "Action indicator detected -- GPT is calling API "
                        "(%.0fs elapsed)",
                        elapsed,
                    )
                    action_detected = True
                elif page.locator(_SEL_STOP_BUTTON).count() > 0:
                    logger.info(
                        "Still streaming... (%.0fs elapsed)", elapsed
                    )
                else:
                    logger.info(
                        "Waiting for completion... (%.0fs elapsed)", elapsed
                    )
                last_log = now

            time.sleep(_POLL_INTERVAL_S)

        # Timeout: fall back to whatever text is in the DOM.
        logger.warning(
            "Copy button did not appear within timeout -- "
            "extracting partial response from DOM."
        )
        return self._extract_last_response_text(page)

    def _extract_via_copy_button(
        self, page: Page, copy_btn, last_msg
    ) -> str:
        """Click the copy button and read clipboard, with DOM fallback."""
        try:
            copy_btn.first.click()
            time.sleep(0.2)
            text = page.evaluate("() => navigator.clipboard.readText()")
            if text and text.strip():
                logger.debug("Got response via clipboard (%d chars).", len(text))
                return text.strip()
        except Exception:
            logger.debug(
                "Clipboard read failed -- falling back to DOM extraction.",
                exc_info=True,
            )

        # DOM fallback.
        return last_msg.inner_text().strip()

    def _extract_last_response_text(self, page: Page) -> str:
        """Extract text from the last assistant message element (DOM)."""
        msgs = page.locator(_SEL_ASSISTANT_MSG)
        count = msgs.count()
        if count == 0:
            return ""
        return msgs.nth(count - 1).inner_text().strip()

    def _has_action_indicator(self, page: Page) -> bool:
        """Check if any action-call indicators are visible on the page."""
        try:
            text = page.locator("body").inner_text()
            return bool(re.search(r"Talked to |Stopped talking to ", text))
        except Exception:
            return False

    def _capture_turn_metadata(self, page: Page) -> dict:
        """Extract thinking time, action calls, and action failures.

        Scans the visible page text for ChatGPT's metadata indicators:
        - "Thought for Xs" -> thinking_seconds
        - "Talked to hostname" -> actions
        - "Stopped talking to hostname" -> action_failures
        """
        result: dict = {
            "thinking_seconds": None,
            "actions": [],
            "action_failures": [],
        }

        try:
            body_text = page.locator("body").inner_text()
        except Exception:
            logger.debug("Could not read body text for metadata", exc_info=True)
            return result

        # Thinking time: "Thought for 12 seconds", "Thought for 5s"
        m = re.search(
            r"Thought for (\d+(?:\.\d+)?)\s*(?:seconds?|s)\b",
            body_text,
            re.I,
        )
        if m:
            result["thinking_seconds"] = float(m.group(1))
            logger.info("GPT thinking time: %.0fs", result["thinking_seconds"])

        # Action calls: "Talked to api.example.com"
        for m in re.finditer(r"Talked to\s+(\S+)", body_text):
            result["actions"].append(m.group(1))

        # Action failures: "Stopped talking to api.example.com"
        for m in re.finditer(r"Stopped talking to\s+(\S+)", body_text):
            result["action_failures"].append(m.group(1))

        if result["actions"]:
            logger.info("Action calls detected: %s", result["actions"])
        if result["action_failures"]:
            logger.warning(
                "Action failures detected: %s", result["action_failures"]
            )

        return result


# --- CLI entry point ----------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send a message to a Custom GPT and capture the response."
    )
    parser.add_argument("url", help="Custom GPT URL (https://chatgpt.com/g/...)")
    parser.add_argument("message", help="Message to send")
    parser.add_argument(
        "--headless", action="store_true", help="Run browser headless"
    )
    parser.add_argument(
        "--profile",
        default=str(_PROFILE_DIR),
        help="Browser profile directory (default: ~/.gpt-test-profile/)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    with GPTHarness(
        args.url, profile_dir=args.profile, headless=args.headless
    ) as harness:
        response = harness.send_message(args.message)
        import io
        import sys

        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )
        print("\n--- GPT Response ---")
        print(response)
        print("--- End ---\n")


if __name__ == "__main__":
    main()
