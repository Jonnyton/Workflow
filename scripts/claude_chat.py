"""Drive the real Claude.ai chat UI via Chrome DevTools Protocol.

Setup (run ONCE by the human host, not by user-sim):

    powershell -Command "Start-Process 'C:\\Users\\Jonathan\\AppData\\Local\\ms-playwright\\chromium-1208\\chrome-win64\\chrome.exe' -ArgumentList '--user-data-dir=C:\\Users\\Jonathan\\.claude-ai-profile','--remote-debugging-port=9222','--no-first-run','--disable-blink-features=AutomationControlled','https://claude.ai/new'"

Then log into claude.ai in that window, ensure the Universe Server custom connector is enabled, and keep the window visible. Single-tab rule: user-sim will navigate the existing tab, not open new ones.

Usage (user-sim):

    python scripts/claude_chat.py ask "your prompt here"
    python scripts/claude_chat.py read              # read last assistant message
    python scripts/claude_chat.py new-chat          # navigate to /new
    python scripts/claude_chat.py status            # is the CDP tab reachable?

Every `ask` appends the sent prompt and the assistant response to
`output/claude_chat_trace.md`. The user-sim then writes a short summary entry
into `output/user_sim_session.md` (not the full trace — keeps the shared log lean).

Does NOT bypass the UI. Types into the same chat input a human would use. Reads
the same rendered text a human would see. No MCP calls, no DOM metadata that
isn't visible to a human reader.
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import os
import subprocess
import sys
import time
from pathlib import Path

# Windows cp1252 chokes on arrows/em-dashes in claude responses. Force utf-8.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    print("ERROR: playwright not installed. Run: pip install playwright", file=sys.stderr)
    sys.exit(2)

CDP = "http://localhost:9222"
CLAUDE_HOST = "claude.ai"
NEW_CHAT_URL = "https://claude.ai/new"
ROOT = Path(__file__).resolve().parent.parent
TRACE = ROOT / "output" / "claude_chat_trace.md"
FAILURE_DIR = ROOT / "output" / "claude_chat_failures"

CHROME_BIN = Path(
    os.environ.get(
        "WORKFLOW_CHROME_BIN",
        r"C:\Users\Jonathan\AppData\Local\ms-playwright\chromium-1208\chrome-win64\chrome.exe",
    )
)
CHROME_PROFILE = Path(
    os.environ.get(
        "WORKFLOW_CHROME_PROFILE",
        str(Path.home() / ".claude-ai-profile"),
    )
)

# Selector candidates. Claude.ai's DOM shifts — try multiple; use the first that works.
INPUT_SELECTORS = [
    'div[contenteditable="true"][enterkeyhint]',
    'div.ProseMirror[contenteditable="true"]',
    'div[contenteditable="true"]',
    'textarea',
]
SEND_BUTTON_SELECTORS = [
    'button[aria-label*="Send" i]',
    'button[aria-label*="send message" i]',
    'button[type="submit"]',
]
STOP_BUTTON_SELECTORS = [
    'button[aria-label*="Stop" i]',
    'button[aria-label*="stop response" i]',
]
# Interactive selection widgets that claude.ai renders in place of the
# free-text input (e.g. "What do you want to work on?" with clickable
# options). While one is active, `INPUT_SELECTORS` return nothing because
# there's no contenteditable. The recovery helper detects the widget so
# it can try to dismiss it before falling back further.
#
# Evidence: output/claude_chat_failures/20260412T184237_input_not_found.html
# shows <div aria-label="What do you want to work on?"
# aria-activedescendant="ask-user-option-question-0-0"> wrapping four
# role="option" rows, with NO contenteditable="true" anywhere in the DOM.
SELECTION_WIDGET_SELECTORS = [
    '[aria-activedescendant*="ask-user-option" i]',
    '[aria-label*="What do you want to work on" i]',
]
ASSISTANT_MSG_SELECTORS = [
    'div[data-testid="assistant-message"]',
    'div.font-claude-message',
    '[data-is-streaming]',  # usually an assistant turn
]

# Artifact + rich-content selectors. claude.ai auto-renders things like
# mermaid diagrams, code blocks, and long-form artifacts alongside the
# text reply. inner_text() misses the non-textual parts. We scan for
# common containers inside the last assistant message and record their
# source. Selectors are best-effort and fail soft — a miss just means the
# trace omits that artifact, not an error.
ARTIFACT_CONTAINER_SELECTORS = [
    '[data-testid*="artifact" i]',
    '[aria-label*="artifact" i]',
    'div[class*="artifact" i]',
]
ARTIFACT_TITLE_SELECTORS = [
    '[data-testid*="artifact-title" i]',
    'header',
    '[class*="title" i]',
]
# Code / mermaid source lives in <pre><code class="language-XYZ">. We
# filter by language attribute so we can label mermaid distinctly.
CODE_BLOCK_SELECTOR = 'pre code'


def _launch_chrome() -> None:
    """Launch the dedicated Chrome profile with CDP enabled. Non-blocking."""
    if not CHROME_BIN.exists():
        raise RuntimeError(
            f"Chrome binary not found at {CHROME_BIN}. "
            f"Set WORKFLOW_CHROME_BIN env var to override."
        )
    CHROME_PROFILE.mkdir(parents=True, exist_ok=True)
    args = [
        str(CHROME_BIN),
        f"--user-data-dir={CHROME_PROFILE}",
        "--remote-debugging-port=9222",
        "--no-first-run",
        "--disable-blink-features=AutomationControlled",
        NEW_CHAT_URL,
    ]
    # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP so Chrome survives this script.
    creationflags = 0
    if sys.platform == "win32":
        creationflags = 0x00000008 | 0x00000200
    subprocess.Popen(
        args,
        creationflags=creationflags,
        close_fds=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _connect(auto_launch: bool = True, launch_wait_s: int = 20):
    pw = sync_playwright().start()
    try:
        return pw, pw.chromium.connect_over_cdp(CDP)
    except Exception:
        if not auto_launch:
            pw.stop()
            raise RuntimeError(f"Cannot connect to Chrome CDP at {CDP}.")

    # Launch and retry with a short backoff while Chrome warms up.
    print(f"Chrome CDP not up — launching {CHROME_BIN.name} ...", file=sys.stderr)
    try:
        _launch_chrome()
    except Exception as exc:
        pw.stop()
        raise RuntimeError(f"Auto-launch failed: {exc}") from exc

    deadline = time.monotonic() + launch_wait_s
    last_exc: Exception | None = None
    while time.monotonic() < deadline:
        time.sleep(1.0)
        try:
            return pw, pw.chromium.connect_over_cdp(CDP)
        except Exception as exc:
            last_exc = exc
    pw.stop()
    raise RuntimeError(
        f"Chrome launched but CDP still unreachable after {launch_wait_s}s ({last_exc})"
    )


_AUTO_DISMISS_SCRIPT = r"""
(() => {
  if (window.__workflowAutoDismissInstalled) return;
  window.__workflowAutoDismissInstalled = true;
  const ALLOW_RE = /\b(always\s+allow|allow\s+always|allow\s+for\s+this\s+chat|allow\s+this\s+tool|allow)\b/i;
  const CONFIRM_RE = /\b(confirm|continue)\b/i;
  const tryClick = (btn) => {
    const txt = (btn.innerText || btn.textContent || '').trim();
    if (!txt) return false;
    if (!(ALLOW_RE.test(txt) || CONFIRM_RE.test(txt))) return false;
    // Only click if inside a dialog-like container (role=dialog/alertdialog, or class hints).
    const container = btn.closest('[role="dialog"], [role="alertdialog"], [class*="dialog" i], [class*="modal" i], [class*="popover" i], [data-state="open"]');
    if (!container) return false;
    try { btn.click(); window.__workflowAutoDismissCount = (window.__workflowAutoDismissCount || 0) + 1; return true; } catch (e) { return false; }
  };
  const scan = () => {
    document.querySelectorAll('button').forEach(tryClick);
  };
  const obs = new MutationObserver((mutations) => {
    for (const m of mutations) {
      for (const n of m.addedNodes || []) {
        if (!(n instanceof Element)) continue;
        if (n.matches && n.matches('button')) { tryClick(n); continue; }
        if (n.querySelectorAll) n.querySelectorAll('button').forEach(tryClick);
      }
    }
  });
  obs.observe(document.documentElement, {childList: true, subtree: true});
  // Also sweep once at install time in case a dialog is already open.
  scan();
  // Periodic safety sweep at very low frequency (5s) in case the observer misses deeply-nested mounts.
  setInterval(scan, 5000);
})();
"""


def _install_auto_dismiss(page) -> None:
    """Install a persistent MutationObserver that auto-clicks allow/confirm
    buttons the moment they appear. Idempotent — the script guards its own
    re-install with window.__workflowAutoDismissInstalled.
    """
    try:
        page.evaluate(_AUTO_DISMISS_SCRIPT)
    except Exception:
        # Never let auto-dismiss install break the primary flow.
        pass


def _find_claude_page(browser):
    for ctx in browser.contexts:
        for p in ctx.pages:
            if CLAUDE_HOST in p.url:
                return p
    return None


def _ensure_claude_page(browser):
    """Single-tab rule: navigate the first available tab to claude.ai if no claude tab exists.

    Also installs the persistent auto-dismiss MutationObserver so allow/confirm
    permission dialogs are clicked the moment they appear — not just on the
    1.5s poll cadence.
    """
    p = _find_claude_page(browser)
    if p is None:
        for ctx in browser.contexts:
            if ctx.pages:
                p = ctx.pages[0]
                p.goto(NEW_CHAT_URL, timeout=30000)
                time.sleep(2)
                break
    if p is None:
        raise RuntimeError("No pages in the CDP browser context.")
    _install_auto_dismiss(p)
    return p


DIALOG_DISMISS_SELECTORS = [
    '[role="dialog"] button:has-text("Always allow")',
    '[role="dialog"] button:has-text("Allow always")',
    '[role="dialog"] button:has-text("Allow for this chat")',
    '[role="dialog"] button:has-text("Allow")',
    '[role="dialog"] button:has-text("Confirm")',
    '[role="dialog"] button:has-text("Continue")',
    '[role="alertdialog"] button:has-text("Allow")',
]

_dismiss_cooldown_until = 0.0


def _dismiss_dialogs(page) -> int:
    """Click any permission/allow dialog Claude.ai has put up.

    Scoped to role=dialog / alertdialog only — never clicks arbitrary buttons.
    Returns how many dialogs were dismissed. Cheap no-op when no dialog exists,
    so safe to call before every ask and before every response wait.
    """
    global _dismiss_cooldown_until
    if time.monotonic() < _dismiss_cooldown_until:
        return 0
    clicked = 0
    for sel in DIALOG_DISMISS_SELECTORS:
        try:
            loc = page.locator(sel)
            n = loc.count()
        except Exception:
            continue
        for i in range(n):
            try:
                btn = loc.nth(i)
                if not btn.is_visible():
                    continue
                btn.click(force=True)
                clicked += 1
                _dismiss_cooldown_until = time.monotonic() + 3.0
                time.sleep(0.3)
                break  # one per pass; re-evaluate on next call if more
            except Exception:
                continue
        if clicked:
            break
    return clicked


def _first_visible(page, selectors):
    for sel in selectors:
        loc = page.locator(sel)
        count = loc.count()
        for i in range(count):
            try:
                if loc.nth(i).is_visible():
                    return loc.nth(i)
            except Exception:
                continue
    return None


def _selection_widget_visible(page) -> bool:
    """Is the `ask-user-option` selection widget currently blocking input?

    Claude.ai renders this when the bot ends a turn with a multiple-choice
    question. While it's active, there is NO contenteditable input in the
    DOM — the user is expected to pick an option. Detecting it lets the
    recovery path tell this apart from "input just hasn't mounted yet".
    """
    for sel in SELECTION_WIDGET_SELECTORS:
        try:
            loc = page.locator(sel)
            if loc.count() > 0 and loc.first.is_visible():
                return True
        except Exception:
            continue
    return False


def _try_recover_input(page, *, on_step=None):
    """Escalation ladder to restore a usable chat input.

    Returns the input locator on success, or None if every recovery
    strategy failed. Intended for use from `cmd_ask` when the normal
    input lookup comes up empty. Strategies, in order of blast radius:

      1. Click the chat body area to force focus back to the input.
      2. If a selection widget is visible (`ask-user-option`), click its
         "Skip" button. This is the widget's own dismiss affordance and
         re-mounts the free-text input more reliably than Escape.
      3. Press Escape to dismiss any invisible overlay / modal (and a
         second Escape if the selection widget is still visible).
      4. Scroll the message list to the bottom (puts the input back in
         view; sometimes it's virtualized off-screen).
      5. Tab into the input role by keyboard.
      6. Last resort: reload the current chat URL. This preserves chat
         history (same chat id) but re-mounts the full UI. Do NOT
         navigate to /new — that loses the conversation. If the widget
         re-renders after reload, click its Skip button once more.

    Each step re-scans INPUT_SELECTORS; the first one that yields a
    visible input wins. `on_step` is an optional callback invoked with
    the step name for observability — user-sim can route it to stderr.
    """
    def _log(name: str) -> None:
        if on_step is not None:
            try:
                on_step(name)
            except Exception:
                pass

    def _rescan():
        try:
            return _first_visible(page, INPUT_SELECTORS)
        except Exception:
            return None

    # Fast path: maybe the input came back on its own between the
    # original check and now. One re-scan is cheap.
    inp = _rescan()
    if inp is not None:
        _log("initial_rescan")
        return inp

    # 1. Click the main chat content to force focus.
    try:
        body_loc = page.locator("main, [role='main']")
        body = body_loc.first
        if body and body.count() > 0 and body.is_visible():
            body.click(timeout=1000)
            time.sleep(0.3)
            inp = _rescan()
            if inp is not None:
                _log("main_click")
                return inp
    except Exception:
        pass

    # 2. If a selection widget is visible, click its "Skip" button before
    # trying Escape. Claude.ai's ask-user-option widget renders a
    # <button data-widget-action="true">Skip</button> that dismisses the
    # widget and re-mounts the free-text input. This is more reliable
    # than Escape, which depends on focus being on the widget.
    try:
        widget_visible = _selection_widget_visible(page)
    except Exception:
        widget_visible = False
    if widget_visible:
        try:
            skip_btn = page.locator(
                'button[data-widget-action="true"]:has-text("Skip")'
            )
            if skip_btn.count() > 0 and skip_btn.first.is_visible():
                skip_btn.first.click(timeout=1000)
                time.sleep(0.4)
                inp = _rescan()
                if inp is not None:
                    _log("widget_skip_click")
                    return inp
        except Exception:
            pass

    # 3. Escape to dismiss overlays. Some Claude.ai widgets take two Esc
    # presses (one to close active element, one to dismiss the wrapper),
    # so we try twice with a rescan between.
    try:
        page.keyboard.press("Escape")
        time.sleep(0.3)
        inp = _rescan()
        if inp is not None:
            _log("escape_once")
            return inp
    except Exception:
        pass
    try:
        widget_visible = _selection_widget_visible(page)
    except Exception:
        widget_visible = False
    if widget_visible:
        try:
            page.keyboard.press("Escape")
            time.sleep(0.4)
            inp = _rescan()
            if inp is not None:
                _log("escape_selection_widget")
                return inp
        except Exception:
            pass

    # 4. Scroll message list to bottom.
    try:
        page.evaluate(
            "() => window.scrollTo({top: document.body.scrollHeight, "
            "behavior: 'instant'})"
        )
        time.sleep(0.3)
        inp = _rescan()
        if inp is not None:
            _log("scroll_bottom")
            return inp
    except Exception:
        pass

    # 5. Tab-cycle to find a focusable textbox role.
    try:
        for _ in range(6):
            page.keyboard.press("Tab")
            time.sleep(0.1)
            inp = _rescan()
            if inp is not None:
                _log("tab_cycle")
                return inp
    except Exception:
        pass

    # 6. Last resort: reload the current chat. Preserves the chat id
    # so conversation history stays intact.
    try:
        current_url = page.url
        if "/chat/" in current_url:
            page.goto(current_url, timeout=20000)
            time.sleep(2.5)
            inp = _rescan()
            if inp is not None:
                _log("chat_reload")
                return inp
            # Widget may have re-rendered after reload. Try Skip once more.
            try:
                if _selection_widget_visible(page):
                    skip_btn = page.locator(
                        'button[data-widget-action="true"]:has-text("Skip")'
                    )
                    if skip_btn.count() > 0 and skip_btn.first.is_visible():
                        skip_btn.first.click(timeout=1000)
                        time.sleep(0.5)
                        inp = _rescan()
                        if inp is not None:
                            _log("chat_reload_then_skip")
                            return inp
            except Exception:
                pass
    except Exception:
        pass

    return None


def _read_last_assistant_text(page) -> str:
    """Return the rendered text of the last assistant message (what a human sees)."""
    for sel in ASSISTANT_MSG_SELECTORS:
        loc = page.locator(sel)
        count = loc.count()
        if count > 0:
            try:
                return loc.nth(count - 1).inner_text().strip()
            except Exception:
                continue
    # Fallback: last message-looking div in an article role
    try:
        articles = page.locator("article, [role='article']")
        n = articles.count()
        if n:
            return articles.nth(n - 1).inner_text().strip()
    except Exception:
        pass
    return ""


def _last_assistant_locator(page):
    """Return a Playwright locator for the last assistant message, or None.

    Extracted so artifact/code scans can scope to the same DOM subtree
    that `_read_last_assistant_text` pulled text from — otherwise we
    could accidentally pick up code blocks from earlier turns.
    """
    for sel in ASSISTANT_MSG_SELECTORS:
        loc = page.locator(sel)
        try:
            count = loc.count()
        except Exception:
            continue
        if count > 0:
            return loc.nth(count - 1)
    try:
        articles = page.locator("article, [role='article']")
        n = articles.count()
        if n:
            return articles.nth(n - 1)
    except Exception:
        pass
    return None


def _extract_rich_content(page) -> list[dict[str, str]]:
    """Collect artifacts + code blocks from the last assistant message.

    Returns a list of dicts with keys `kind`, `title`, `language`, `text`.
    `kind` is one of:
      - "artifact": content inside an artifact container (title + body)
      - "mermaid":  a <pre><code class="language-mermaid"> block (source)
      - "code":     any other <pre><code class="language-X"> block

    Everything is best-effort. Each selector path is wrapped in try/except
    so a DOM shift on claude.ai's side degrades the trace (missing
    artifacts) instead of crashing user-sim mid-turn.

    No button clicks, no screenshots, no DOM mutation — pure read.
    """
    last = _last_assistant_locator(page)
    if last is None:
        return []

    found: list[dict[str, str]] = []
    seen_texts: set[str] = set()

    # 1. Artifact containers — title + rendered body text.
    for sel in ARTIFACT_CONTAINER_SELECTORS:
        try:
            containers = last.locator(sel)
            count = containers.count()
        except Exception:
            continue
        for i in range(count):
            try:
                node = containers.nth(i)
                body = node.inner_text().strip()
                if not body or body in seen_texts:
                    continue
                title = ""
                for ts in ARTIFACT_TITLE_SELECTORS:
                    try:
                        title_loc = node.locator(ts).first
                        if title_loc.count() > 0:
                            title = title_loc.inner_text().strip()
                            if title:
                                break
                    except Exception:
                        continue
                found.append({
                    "kind": "artifact",
                    "title": title or "(untitled artifact)",
                    "language": "",
                    "text": body,
                })
                seen_texts.add(body)
            except Exception:
                continue

    # 2. Code blocks — distinguish mermaid so diagram source is labeled.
    try:
        code_nodes = last.locator(CODE_BLOCK_SELECTOR)
        count = code_nodes.count()
    except Exception:
        count = 0
    for i in range(count):
        try:
            node = code_nodes.nth(i)
            text = node.inner_text().strip()
            if not text or text in seen_texts:
                continue
            lang = ""
            try:
                cls = node.get_attribute("class") or ""
                for token in cls.split():
                    if token.startswith("language-"):
                        lang = token[len("language-"):]
                        break
            except Exception:
                lang = ""
            kind = "mermaid" if lang.lower() == "mermaid" else "code"
            found.append({
                "kind": kind,
                "title": "",
                "language": lang,
                "text": text,
            })
            seen_texts.add(text)
        except Exception:
            continue

    return found


def _format_rich_content(items: list[dict[str, str]]) -> str:
    """Render rich-content items as trace-friendly markdown sections.

    Empty list → empty string (caller can concat unconditionally).
    """
    if not items:
        return ""
    out: list[str] = []
    for item in items:
        kind = item.get("kind", "code")
        text = item.get("text", "")
        if kind == "artifact":
            title = item.get("title", "(untitled artifact)")
            out.append(f"\n[ARTIFACT: {title}]\n{text}")
        elif kind == "mermaid":
            out.append(f"\n[MERMAID]\n{text}")
        else:
            lang = item.get("language", "")
            label = f"CODE:{lang}" if lang else "CODE"
            out.append(f"\n[{label}]\n{text}")
    return "".join(out)


def _wait_for_response_complete(
    page, prev_text: str, timeout_s: int = 180,
) -> tuple[str, bool]:
    """Poll until a new assistant message appears and stops streaming.

    Returns (text, timed_out). `timed_out=True` means the deadline hit
    without the text going stable — the caller should dump diagnostics.
    Previously this returned only the text, so callers couldn't tell a
    valid short reply from a stuck/streaming session.
    """
    deadline = time.monotonic() + timeout_s
    last_seen = prev_text
    stable_ticks = 0
    while time.monotonic() < deadline:
        time.sleep(1.5)
        # Clear any mid-response permission dialogs (Allow tool call, etc.)
        _dismiss_dialogs(page)
        text = _read_last_assistant_text(page)
        if text and text != prev_text:
            # A new assistant message exists. Watch for streaming to finish.
            stop_btn = _first_visible(page, STOP_BUTTON_SELECTORS)
            if stop_btn is None:
                # No stop button: check stability of text
                if text == last_seen:
                    stable_ticks += 1
                    if stable_ticks >= 2:
                        return text, False
                else:
                    stable_ticks = 0
                    last_seen = text
            else:
                stable_ticks = 0
                last_seen = text
    return last_seen, True  # timed out; return whatever we have


def _append_trace(kind: str, body: str) -> None:
    TRACE.parent.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with TRACE.open("a", encoding="utf-8") as f:
        f.write(f"\n\n## [{ts}] {kind}\n{body}\n")


def _capture_failure_dump(page, reason: str, *, note: str = "") -> str:
    """Save DOM + screenshot when the driver can't recover.

    Writes three artifacts under `output/claude_chat_failures/`:
      - <ts>_<reason>.html   : full rendered DOM
      - <ts>_<reason>.png    : screenshot
      - <ts>_<reason>.txt    : url + visible text + note

    Returns the shared basename (without extension) so callers can reference
    it in logs. All failures are swallowed — if the dump itself errors, we
    still want the caller to exit cleanly.
    """
    try:
        FAILURE_DIR.mkdir(parents=True, exist_ok=True)
        ts = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
        safe_reason = "".join(c if c.isalnum() or c in "-_" else "_" for c in reason)[:40]
        base = FAILURE_DIR / f"{ts}_{safe_reason}"
    except OSError as exc:
        print(f"WARN: could not create failure dump dir: {exc}", file=sys.stderr)
        return ""

    try:
        html = page.content()
        base.with_suffix(".html").write_text(html, encoding="utf-8")
    except Exception as exc:
        print(f"WARN: failed to dump DOM: {exc}", file=sys.stderr)

    try:
        page.screenshot(path=str(base.with_suffix(".png")), full_page=True)
    except Exception as exc:
        print(f"WARN: failed to screenshot: {exc}", file=sys.stderr)

    try:
        url = ""
        try:
            url = page.url
        except Exception:
            pass
        visible = ""
        try:
            visible = page.evaluate("() => document.body ? document.body.innerText : ''") or ""
        except Exception:
            pass
        base.with_suffix(".txt").write_text(
            f"reason: {reason}\n"
            f"url: {url}\n"
            f"note: {note}\n"
            f"--- visible text ---\n{visible[:8000]}\n",
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"WARN: failed to write failure context: {exc}", file=sys.stderr)

    return base.name


def cmd_ask(message: str) -> int:
    pw, browser = _connect()
    try:
        page = _ensure_claude_page(browser)
        page.bring_to_front()
        # Clear any pending permission dialogs before reading or typing.
        _dismiss_dialogs(page)
        prev = _read_last_assistant_text(page)

        inp = _first_visible(page, INPUT_SELECTORS)
        if inp is None:
            # Recovery: try several automatic strategies before giving up.
            # The most common case (per failure dumps) is that claude.ai
            # replaced the input with an ask-user-option selection widget
            # — Escape usually restores the free-text input without new-chat
            # ing, which would drop conversation context.
            recovery_steps: list[str] = []
            inp = _try_recover_input(
                page, on_step=lambda name: recovery_steps.append(name),
            )
            if inp is None:
                widget_active = _selection_widget_visible(page)
                dump = _capture_failure_dump(
                    page, "input_not_found",
                    note=(
                        f"prev_text_len={len(prev)}; "
                        f"message_preview={message[:80]!r}; "
                        f"recovery_attempted={recovery_steps or 'all_failed'}; "
                        f"selection_widget={'visible' if widget_active else 'none'}"
                    ),
                )
                print(
                    "ERROR: could not find chat input on claude.ai "
                    "(even after recovery attempts). Is the page loaded? "
                    f"Diagnostic dump: "
                    f"output/claude_chat_failures/{dump}.{{html,png,txt}}",
                    file=sys.stderr,
                )
                return 3
            # Recovery worked. Emit one line to stderr so user-sim knows
            # the chat state was auto-repaired.
            print(
                f"INFO: recovered chat input via {recovery_steps}",
                file=sys.stderr,
            )
        inp.click()
        page.keyboard.type(message, delay=15)
        # Prefer the send button if visible; fall back to Enter.
        send = _first_visible(page, SEND_BUTTON_SELECTORS)
        if send is not None:
            send.click()
        else:
            page.keyboard.press("Enter")

        _append_trace("USER_SIM -> CLAUDE", message)
        response, timed_out = _wait_for_response_complete(page, prev)

        # Capture rich content (artifacts, mermaid, code blocks) from the
        # last assistant turn. inner_text alone misses auto-rendered
        # diagrams and artifacts — user-sim would otherwise see none of it
        # in the trace.
        rich_items: list[dict[str, str]] = []
        try:
            rich_items = _extract_rich_content(page)
        except Exception as exc:
            # Never let trace enrichment break the primary flow.
            print(f"WARN: rich-content capture failed: {exc}", file=sys.stderr)

        rich_section = _format_rich_content(rich_items)

        if timed_out:
            note = (
                f"prev_len={len(prev)}; response_len={len(response)}; "
                f"message_preview={message[:80]!r}; rich_items={len(rich_items)}"
            )
            dump = _capture_failure_dump(page, "response_timeout", note=note)
            _append_trace(
                "CLAUDE -> USER_SIM",
                f"(TIMEOUT after 180s; partial response below; dump={dump})\n"
                f"{response or '(nothing captured)'}"
                f"{rich_section}",
            )
            print(response or "(no response captured)")
            print(
                f"WARN: response did not settle within 180s. "
                f"Diagnostic dump: output/claude_chat_failures/{dump}.{{html,png,txt}}",
                file=sys.stderr,
            )
            return 5

        _append_trace(
            "CLAUDE -> USER_SIM",
            f"{response or '(empty response)'}{rich_section}",
        )

        # Optional per-turn screenshot for artifact visual verification.
        # Opt-in via WORKFLOW_CLAUDE_CHAT_SCREENSHOTS=1 so normal runs stay
        # cheap. Saved alongside the trace under output/claude_chat_turns/.
        if os.environ.get("WORKFLOW_CLAUDE_CHAT_SCREENSHOTS") == "1":
            try:
                shot_dir = ROOT / "output" / "claude_chat_turns"
                shot_dir.mkdir(parents=True, exist_ok=True)
                ts = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
                page.screenshot(
                    path=str(shot_dir / f"{ts}.png"), full_page=True,
                )
            except Exception as exc:
                print(f"WARN: turn screenshot failed: {exc}", file=sys.stderr)

        # Print a short confirmation plus the response so user-sim can read it.
        print(response or "(no response captured)")
        if rich_items:
            print(
                f"(+{len(rich_items)} rich-content items captured: "
                f"{', '.join(item['kind'] for item in rich_items)})",
                file=sys.stderr,
            )
        return 0
    finally:
        browser.close()
        pw.stop()


def cmd_read() -> int:
    pw, browser = _connect()
    try:
        page = _ensure_claude_page(browser)
        text = _read_last_assistant_text(page)
        print(text or "(no assistant message visible)")
        return 0
    finally:
        browser.close()
        pw.stop()


def cmd_dismiss_dialogs() -> int:
    pw, browser = _connect()
    try:
        page = _ensure_claude_page(browser)
        n = _dismiss_dialogs(page)
        print(f"dismissed {n} dialog(s)")
        return 0
    finally:
        browser.close()
        pw.stop()


def cmd_new_chat() -> int:
    pw, browser = _connect()
    try:
        page = _ensure_claude_page(browser)
        page.goto(NEW_CHAT_URL, timeout=30000)
        time.sleep(2)
        print("new chat ready")
        return 0
    finally:
        browser.close()
        pw.stop()


def cmd_status() -> int:
    try:
        pw, browser = _connect(auto_launch=False)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 4
    try:
        page = _find_claude_page(browser)
        if page is None:
            print("CDP reachable; no claude.ai tab found.")
            return 1
        print(f"OK: claude.ai tab at {page.url}")
        return 0
    finally:
        browser.close()
        pw.stop()


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    ask = sub.add_parser("ask")
    ask.add_argument("message")
    sub.add_parser("read")
    sub.add_parser("new-chat")
    sub.add_parser("status")
    sub.add_parser("dismiss-dialogs")
    ns = p.parse_args()

    if ns.cmd == "ask":
        return cmd_ask(ns.message)
    if ns.cmd == "read":
        return cmd_read()
    if ns.cmd == "new-chat":
        return cmd_new_chat()
    if ns.cmd == "status":
        return cmd_status()
    if ns.cmd == "dismiss-dialogs":
        return cmd_dismiss_dialogs()
    return 1


if __name__ == "__main__":
    sys.exit(main())
