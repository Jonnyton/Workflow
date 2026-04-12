"""Update GPT builder via Playwright CDP. One-liner commands.

    python -m fantasy_author.testing.gpt_builder update-schema
    python -m fantasy_author.testing.gpt_builder update-instructions
    python -m fantasy_author.testing.gpt_builder update-all
    python -m fantasy_author.testing.gpt_builder save
    python -m fantasy_author.testing.gpt_builder click-dialogs
    python -m fantasy_author.testing.gpt_builder read
    python -m fantasy_author.testing.gpt_builder send "message text"
"""

from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import sync_playwright

EDITOR_URL = "https://chatgpt.com/gpts/editor/g-69cd9dc9c52c8191a18dd84829712447"
GPT_URL = "https://chatgpt.com/g/g-69cd9dc9c52c8191a18dd84829712447-fantasy-author"
CDP = "http://localhost:9222"
ROOT = Path(__file__).parent.parent.parent
SCHEMA = ROOT / "custom_gpt" / "actions_schema.yaml"
INSTRUCTIONS = ROOT / "custom_gpt" / "instructions.md"

# -- Helpers ------------------------------------------------------------------

def _connect():
    pw = sync_playwright().start()
    return pw, pw.chromium.connect_over_cdp(CDP)


def _page(browser, *, editor=False):
    GPT_ID = "g-69cd9dc9c52c8191a18dd84829712447"
    for ctx in browser.contexts:
        for p in ctx.pages:
            if editor and "editor" in p.url:
                return p
            is_gpt = GPT_ID in p.url or "fantasy-author" in p.url
            if not editor and is_gpt and "editor" not in p.url:
                return p
    return None


_dismiss_cooldown_until = 0.0


def _dismiss(page):
    """Click any blocking modal/dialog in one pass.

    After a successful dismiss, skips checks for a cooldown period to
    avoid re-clicking stale/animating elements.
    """
    global _dismiss_cooldown_until
    now = time.monotonic()
    if now < _dismiss_cooldown_until:
        return

    # Tight selectors: target dialog/modal buttons specifically.
    # "Allow" alone is too broad — scope to the action confirmation dialog.
    _DIALOG_SELECTORS = [
        'button:has-text("View GPT")',
        '[role="dialog"] button:has-text("Always allow")',
        '[role="dialog"] button:has-text("Confirm")',
        '[role="dialog"] button:has-text("Allow")',
        # Fallback: unscoped but more specific text match
        'button:text-is("Always allow")',
        'button:text-is("Allow")',
    ]

    for sel in _DIALOG_SELECTORS:
        b = page.locator(sel)
        if b.count() > 0 and b.first.is_visible():
            b.first.click(force=True)
            time.sleep(0.5)
            # Verify the button disappeared (dialog actually dismissed)
            try:
                b.first.wait_for(state="hidden", timeout=2000)
                _dismiss_cooldown_until = time.monotonic() + 10.0
            except Exception:
                # Button still visible — don't set cooldown
                pass
            return


def _ensure_editor(pw, browser):
    """Navigate the single browser tab to the editor URL.

    Single-tab rule: only one tab at a time. Navigate the existing
    tab to the editor, then back to chat when done.
    """
    # Try to find an editor tab first
    page = _page(browser, editor=True)
    if page:
        page.bring_to_front()
        _dismiss(page)
        if "editor" not in page.url:
            page.goto(EDITOR_URL, timeout=30000)
            time.sleep(2)
        return page
    # No editor tab — navigate the first available tab
    for ctx in browser.contexts:
        if ctx.pages:
            p = ctx.pages[0]
            p.goto(EDITOR_URL, timeout=30000)
            time.sleep(3)
            return p
    return None


def _fill_textarea(page, *, match: str, content: str) -> bool:
    """Find a textarea whose value starts with `match` and fill it.
    Uses JS to search ALL textareas including hidden/scrolled ones."""
    result = page.evaluate(f"""() => {{
        const tas = document.querySelectorAll('textarea');
        for (const ta of tas) {{
            if (ta.value.substring(0, 20).includes('{match}')) {{
                // React-compatible fill
                const nativeSet = Object.getOwnPropertyDescriptor(
                    HTMLTextAreaElement.prototype, 'value').set;
                nativeSet.call(ta, {repr(content)});
                ta.dispatchEvent(new Event('input', {{bubbles: true}}));
                ta.dispatchEvent(new Event('change', {{bubbles: true}}));
                return ta.value.length;
            }}
        }}
        return -1;
    }}""")
    return result > 0


# -- Commands -----------------------------------------------------------------

def click_dialogs():
    pw, browser = _connect()
    clicked = []
    for ctx in browser.contexts:
        for page in ctx.pages:
            if "chatgpt" not in page.url:
                continue
            for sel in ['button:has-text("Always allow")', 'button:has-text("Confirm")',
                        'button:has-text("Allow")', 'button:has-text("View GPT")']:
                b = page.locator(sel)
                for i in range(b.count()):
                    try:
                        b.nth(i).click(force=True, timeout=2000)
                        clicked.append(sel.split('"')[1])
                    except Exception:
                        pass
    pw.stop()
    return clicked


def _type_and_send(page, text: str):
    """Type into the chat input and send. Works with both textarea and
    contenteditable div versions of #prompt-textarea."""
    el = page.locator("#prompt-textarea").first
    el.click()
    time.sleep(0.2)
    page.keyboard.type(text, delay=5)
    time.sleep(0.3)
    try:
        page.locator('[data-testid="send-button"]').first.click(timeout=3000)
    except Exception:
        page.keyboard.press("Enter")


def _react_fill(page, selector: str, content: str) -> bool:
    """Fill a textarea using React-compatible value setter."""
    return page.evaluate(f"""() => {{
        const ta = document.querySelector('{selector}');
        if (!ta) return false;
        const set = Object.getOwnPropertyDescriptor(
            HTMLTextAreaElement.prototype, 'value').set;
        set.call(ta, {repr(content)});
        ta.dispatchEvent(new Event('input', {{bubbles: true}}));
        ta.dispatchEvent(new Event('change', {{bubbles: true}}));
        return true;
    }}""")


def _open_action_editor(page) -> bool:
    """Click the gear icon on the existing action entry.

    Structural selector: finds the 'Actions' label, walks up to the
    section container, clicks the last small icon button (the gear).
    Does not depend on tunnel URL text or any content.
    """
    return page.evaluate("""() => {
        for (const l of document.querySelectorAll('label')) {
            if (l.textContent.trim() !== 'Actions') continue;
            let section = l.closest('div');
            for (let i = 0; i < 8 && section.parentElement; i++) {
                section = section.parentElement;
                if (section.querySelectorAll('button svg').length >= 2) break;
            }
            const btns = [];
            for (const b of section.querySelectorAll('button'))
                if (b.querySelector('svg') && !b.textContent.trim()
                    && b.offsetWidth < 50 && b.offsetWidth > 20)
                    btns.push(b);
            if (btns.length > 0) { btns[btns.length - 1].click(); return true; }
        }
        return false;
    }""")


def update_schema():
    """Editor → Configure tab → gear icon → fill schema → back to chat."""
    schema = SCHEMA.read_text(encoding="utf-8")
    pw, browser = _connect()
    page = _ensure_editor(pw, browser)
    if not page:
        pw.stop()
        return "FAIL: no editor page"

    page.locator('button:has-text("Configure")').first.click()
    time.sleep(2)
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(1)
    _open_action_editor(page)
    time.sleep(3)

    ok = _react_fill(
        page, 'textarea[placeholder="Enter your OpenAPI schema here"]',
        schema,
    )
    page.goto(GPT_URL, timeout=30000)
    time.sleep(2)
    pw.stop()
    return f"Schema updated ({len(schema)} chars)" if ok else "FAIL: no schema textarea"


def update_instructions():
    """Editor → Create tab (default) → fill instructions → back to chat."""
    instructions = INSTRUCTIONS.read_text(encoding="utf-8")
    pw, browser = _connect()
    page = _ensure_editor(pw, browser)
    if not page:
        pw.stop()
        return "FAIL: no editor page"

    # Instructions textarea: the visible one with placeholder about behavior
    ok = _react_fill(
        page,
        'textarea[placeholder^="What does this GPT do"]',
        instructions,
    )
    page.goto(GPT_URL, timeout=30000)
    time.sleep(2)
    pw.stop()
    if ok:
        return f"Instructions updated ({len(instructions)} chars)"
    return "FAIL: no instructions textarea"


def save_gpt():
    """Editor → click Update → back to chat."""
    pw, browser = _connect()
    page = _ensure_editor(pw, browser)
    if not page:
        pw.stop()
        return "FAIL: no editor page"

    btn = page.locator('button:has-text("Update")')
    if btn.count() == 0:
        page.goto(GPT_URL, timeout=30000)
        time.sleep(2)
        pw.stop()
        return "FAIL: no Update button"

    btn.first.click()
    time.sleep(3)
    _dismiss(page)
    page.goto(GPT_URL, timeout=30000)
    time.sleep(2)
    pw.stop()
    return "Saved"


def update_all():
    """Fill instructions + schema, save, confirm.

    Always starts from a known state: navigates to editor URL (Create tab),
    fills instructions, switches to schema editor, fills schema, saves.
    """
    instructions = INSTRUCTIONS.read_text(encoding="utf-8")
    schema = SCHEMA.read_text(encoding="utf-8")
    pw, browser = _connect()

    # 1. Enforce single tab, then navigate to editor
    page = None
    for ctx in browser.contexts:
        while len(ctx.pages) > 1:
            ctx.pages[-1].close()
        if ctx.pages:
            page = ctx.pages[0]
    if not page:
        pw.stop()
        return "FAIL: no browser page"
    page.goto(EDITOR_URL, timeout=30000)
    time.sleep(4)
    _dismiss(page)

    results = []

    # 2. Fill instructions (Create tab is showing)
    ok = _react_fill(
        page,
        'textarea[placeholder^="What does this GPT do"]',
        instructions,
    )
    results.append(
        f"Instructions: {len(instructions)} chars" if ok
        else "FAIL: instructions"
    )
    time.sleep(1)

    # 3. Navigate to schema editor (Configure tab → gear icon)
    page.locator('button:has-text("Configure")').first.click()
    time.sleep(2)
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(1)
    _open_action_editor(page)
    time.sleep(3)

    # 4. Fill schema
    ok = _react_fill(
        page, 'textarea[placeholder="Enter your OpenAPI schema here"]',
        schema,
    )
    results.append(
        f"Schema: {len(schema)} chars" if ok
        else "FAIL: schema"
    )

    # 5. Save and confirm (View GPT navigates this tab to new session)
    time.sleep(3)
    btn = page.locator('button:has-text("Update")')
    if btn.count() > 0:
        btn.first.click()
        time.sleep(5)
        _dismiss(page)  # clicks View GPT → navigates to new chat session
        results.append("Saved")
    else:
        results.append("FAIL: no Update button")

    pw.stop()
    return "\n".join(results)


def read_response():
    pw, browser = _connect()
    page = _page(browser, editor=False)
    if not page:
        pw.stop()
        return "No chat tab"
    msgs = page.locator('[data-message-author-role="assistant"]')
    text = msgs.last.inner_text() if msgs.count() > 0 else "No messages"
    pw.stop()
    return text


def send_message(text: str):
    pw, browser = _connect()
    page = _page(browser, editor=False)
    if not page:
        pw.stop()
        return "No chat tab"

    _dismiss(page)
    _type_and_send(page, text)
    pw.stop()
    return f"Sent: {text}"


LOG_PATH = ROOT / "output" / "gpt_test_log.md"


def ask(text: str, timeout: int = 120) -> str:
    """Send a message, wait for response, log full text, return summary.

    Full response goes to output/gpt_test_log.md automatically.
    Returns a short summary (~100 chars) for the agent's context.
    """
    pw, browser = _connect()
    page = _page(browser, editor=False)
    if not page:
        pw.stop()
        return "[FAIL] No chat tab"

    _dismiss(page)

    # Count messages before
    msgs = page.locator('[data-message-author-role="assistant"]')
    before = msgs.count()

    # Send
    _type_and_send(page, text)

    # Wait for response
    last_text = ""
    stable_at = 0
    for _ in range(timeout // 3):
        time.sleep(3)
        _dismiss(page)  # Click any dialogs every cycle

        # Check if GPT is still streaming (stop button visible)
        streaming = page.locator('[data-testid="stop-button"]').count() > 0

        if msgs.count() > before:
            t = msgs.last.inner_text()
            if t == last_text and len(t) > 20 and not streaming:
                stable_at += 3
                if stable_at >= 15:
                    break
            else:
                last_text = t
                stable_at = 0
        elif streaming:
            # GPT is working but no visible message yet — keep waiting
            stable_at = 0

    # Capture full response + thinking/action metadata
    full = msgs.last.inner_text() if msgs.count() > before else "(no response)"

    # Capture thinking and action indicators from the page
    meta_parts = []
    for sel, label in [
        ('text=/Thought for/', 'thinking'),
        ('text=/Talked to/', 'action'),
        ('text=/Stopped talking/', 'action-failed'),
    ]:
        els = page.locator(sel)
        for i in range(els.count()):
            try:
                t = els.nth(i).inner_text(timeout=500)
                if t.strip():
                    meta_parts.append(f"[{label}] {t.strip()}")
            except Exception:
                pass

    pw.stop()

    # Build log entry
    import datetime
    now = datetime.datetime.now().strftime("%H:%M")
    meta_str = "\n".join(meta_parts)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n## {now} — ask\n")
        f.write(f"**Sent:** {text}\n")
        if meta_str:
            f.write(f"**Steps:** {meta_str}\n")
        f.write(f"**Response:** ({len(full)} chars)\n")
        f.write(f"{full}\n---\n")

    return f"[OK] logged ({len(full)} chars)"


def send_next():
    """Read the last '> NEXT:' line from the log and send it as a message."""
    if not LOG_PATH.exists():
        return "[FAIL] No log file"
    lines = LOG_PATH.read_text(encoding="utf-8").splitlines()
    # Find the last NEXT: line
    for line in reversed(lines):
        if line.startswith("> NEXT:"):
            msg = line[7:].strip()
            return ask(msg)
    return "[FAIL] No '> NEXT:' entry found in log"


def new_chat():
    """Start a new chat session (old sessions cache stale URLs)."""
    pw, browser = _connect()
    page = _page(browser, editor=False)
    if not page:
        pw.stop()
        return "No chat tab"
    page.goto(GPT_URL, timeout=30000)
    time.sleep(3)
    pw.stop()
    return "New chat started"


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    arg = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""

    cmds = {
        "read": read_response,
        "ask": lambda: ask(arg),
        "next": send_next,
        "send": lambda: send_message(arg),
        "new-chat": new_chat,
        "click-dialogs": click_dialogs,
        "update-schema": update_schema,
        "update-instructions": update_instructions,
        "update-all": update_all,
        "save": save_gpt,
    }

    if cmd in cmds:
        print(cmds[cmd]())
    else:
        print("Commands: " + ", ".join(cmds))
