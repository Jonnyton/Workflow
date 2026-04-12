"""Run GPT test battery and log results to output/gpt_test_log.md"""
import datetime
import io
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

LOG_FILE = Path(r"C:/Users/Jonathan/Projects/Fantasy Author/output/gpt_test_log.md")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

RESPONSE_TIMEOUT = 180
POLL_INTERVAL = 0.5
STABLE_WAIT = 12

GPT_URL = "https://chatgpt.com/g/g-69cd9dc9c52c8191a18dd84829712447-fantasy-author"

TESTS = [
    "How many words has the writer produced so far?",
    "What characters have appeared in the story?",
    "Read me the opening paragraph of Scene 1.",
    "What canon files are loaded for Ashwater?",
    (
        "Steer the writer to increase tension in the next scene -- the "
        "stranger Daeren should say something that makes the villagers "
        "distrust him more."
    ),
    "Is the writer currently running or paused?",
    "What narrative promises or unresolved threads are active?",
    "Show me the activity log -- what happened in the last hour?",
    (
        "Create a workspace note called continuity-fixes.md with the text: "
        "Fix Corin/Ryn identity split in opening scenes. Consolidate to "
        "single protagonist name."
    ),
    "What universes exist besides Ashwater?",
]


def now_ts():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log_result(
    test_num,
    sent,
    actions,
    failures,
    thinking,
    response_text,
    elapsed,
    dialogs_found,
    assessment,
):
    thinking_str = f", Thought for {thinking}s" if thinking else ""
    actions_str = f' ({", ".join(set(actions))})' if actions else ""
    dialog_str = " -- DIALOGS FOUND" if dialogs_found else ""
    truncated = response_text[:500] + ("..." if len(response_text) > 500 else "")
    entry = (
        f"## Test #{test_num} -- {now_ts()}\n"
        f'**Sent:** "{sent}"\n'
        f"**Timing:** {elapsed:.1f}s total{thinking_str}\n"
        f"**Actions:** {len(actions)} calls{actions_str}, {len(failures)} failures{dialog_str}\n"
        f"**Response:** ({len(response_text)} chars) {truncated}\n"
        f"**Assessment:** {assessment}\n"
        f"---\n\n"
    )
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(entry)
    print(f"[TEST {test_num}] Logged. {assessment}")


def check_dialogs(page):
    found = False
    for sel in [
        'button:has-text("Always allow")',
        'button:has-text("Confirm")',
        'button:has-text("Allow")',
    ]:
        btns = page.locator(sel)
        if btns.count() > 0:
            print(f"  DIALOG: clicking {sel}")
            btns.first.click(force=True)
            time.sleep(0.5)
            found = True
    return found


def send_msg(page, msg):
    input_el = page.locator("#prompt-textarea").first
    input_el.click()
    time.sleep(0.15)
    page.keyboard.press("Control+a")
    page.keyboard.press("Backspace")
    page.evaluate(
        """(text) => {
        const el = document.querySelector('#prompt-textarea');
        if (!el) return;
        if (el.contentEditable === 'true') {
            el.innerHTML = '<p>' + text + '</p>';
            el.dispatchEvent(new Event('input', { bubbles: true }));
        } else {
            el.value = text;
            el.dispatchEvent(new Event('input', { bubbles: true }));
        }
    }""",
        msg,
    )
    time.sleep(0.2)
    send_btn = page.locator('[data-testid="send-button"]').first
    try:
        send_btn.wait_for(state="visible", timeout=3000)
        send_btn.click()
    except Exception:
        input_el.press("Enter")


def count_actions_on_page(page):
    try:
        body = page.locator("body").inner_text()
        return len(re.findall(r"Talked to\s+(\S+)", body))
    except Exception:
        return 0


def wait_for_response(page, before_count):
    start = time.monotonic()
    deadline = start + RESPONSE_TIMEOUT
    last_text = ""
    stable_start = None
    dialogs_found = False
    actions_baseline = count_actions_on_page(page)

    # Phase 1: wait for new message
    while time.monotonic() < deadline:
        if check_dialogs(page):
            dialogs_found = True
        msgs = page.locator('[data-message-author-role="assistant"]')
        if msgs.count() > before_count:
            break
        time.sleep(POLL_INTERVAL)

    # Phase 2: wait for completion
    while time.monotonic() < deadline:
        if check_dialogs(page):
            dialogs_found = True

        msgs = page.locator('[data-message-author-role="assistant"]')
        count = msgs.count()
        if count == 0:
            time.sleep(POLL_INTERVAL)
            continue

        last_msg = msgs.nth(count - 1)
        text = last_msg.inner_text().strip()

        # Copy button = done
        copy_btn = last_msg.locator(
            'button[aria-label="Copy"], button[data-testid="copy-turn-action-button"]'
        )
        if copy_btn.count() > 0 and len(text) > 10:
            break

        # Text stability
        if text and text == last_text:
            if stable_start is None:
                stable_start = time.monotonic()
            elif time.monotonic() - stable_start >= STABLE_WAIT:
                break
        else:
            stable_start = None
            last_text = text

        time.sleep(POLL_INTERVAL)

    elapsed = time.monotonic() - start

    # Gather all new messages
    msgs = page.locator('[data-message-author-role="assistant"]')
    count = msgs.count()
    all_new = []
    for i in range(before_count, count):
        all_new.append(msgs.nth(i).inner_text().strip())
    response_text = "\n\n".join(all_new)

    # Metadata
    body = page.locator("body").inner_text()
    all_actions = re.findall(r"Talked to\s+(\S+)", body)
    new_actions = all_actions[actions_baseline:]
    failures = re.findall(r"Stopped talking to\s+(\S+)", body)
    thinking_match = re.search(
        r"Thought for (\d+(?:\.\d+)?)\s*(?:seconds?|s)", body, re.I
    )
    thinking = float(thinking_match.group(1)) if thinking_match else None

    return response_text, new_actions, failures, thinking, elapsed, dialogs_found


def main():
    # Init log
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(f"# GPT Test Log -- {now_ts()}\n\n")
        f.write("Testing isConsequential flags and general GPT behavior.\n")
        f.write(f"Tests: {len(TESTS)} messages back-to-back.\n\n---\n\n")

    pw = sync_playwright().start()
    browser = pw.chromium.connect_over_cdp("http://localhost:9222")

    page = None
    for ctx in browser.contexts:
        for p in ctx.pages:
            if "fantasy-author" in p.url and "editor" not in p.url:
                page = p
                break
        if page:
            break

    if not page:
        print("ERROR: No GPT tab found")
        pw.stop()
        return

    print(f"Connected to: {page.url}")

    # Fresh chat
    print("Starting new chat...")
    page.goto(GPT_URL)
    time.sleep(3)
    try:
        page.wait_for_selector("#prompt-textarea", state="visible", timeout=30000)
    except Exception:
        page.wait_for_selector(
            '[contenteditable="true"], textarea', state="visible", timeout=15000
        )
    print("New chat ready. Running tests...\n")

    for i, msg in enumerate(TESTS, 1):
        before_count = page.locator('[data-message-author-role="assistant"]').count()
        print(f"[TEST {i}/{len(TESTS)}] Sending: {msg[:60]}...")

        send_msg(page, msg)
        response_text, actions, failures, thinking, elapsed, dialogs = (
            wait_for_response(page, before_count)
        )

        # Assessment
        if dialogs:
            assessment = "FAIL -- confirm/allow dialog appeared"
        elif failures:
            assessment = f"WARN -- {len(failures)} action failures"
        elif not response_text or len(response_text) < 10:
            assessment = "FAIL -- empty or near-empty response"
        elif actions:
            assessment = f"PASS -- {len(actions)} actions, no dialogs"
        else:
            assessment = "PASS -- responded (no actions needed)"

        log_result(
            i, msg, actions, failures, thinking, response_text, elapsed, dialogs, assessment
        )

        time.sleep(1)

    print(f"\nAll {len(TESTS)} tests complete. Log: {LOG_FILE}")
    pw.stop()


if __name__ == "__main__":
    main()
