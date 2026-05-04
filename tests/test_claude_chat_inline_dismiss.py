"""Task #35 part B — inline permission-card dismiss.

Tests ``_dismiss_inline_permission_card`` gating + click behavior.
The detector runs ``page.evaluate`` on live Playwright state; we
fake the page with a tiny stub so the gate logic and notepad-log
wiring are unit-testable without a browser.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


@pytest.fixture
def chat_module(tmp_path, monkeypatch):
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    monkeypatch.syspath_prepend(str(scripts_dir))
    sys.modules.pop("claude_chat", None)
    module = importlib.import_module("claude_chat")
    module.NOTEPAD = tmp_path / "user_sim_session.md"
    return module


class _FakePage:
    """Minimal page stub — ``evaluate`` returns a scripted payload."""

    def __init__(self, payload):
        self._payload = payload
        self.calls = 0

    def evaluate(self, _script):
        self.calls += 1
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def _notepad_text(module) -> str:
    path = Path(module.NOTEPAD)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def test_inline_dismiss_click_success_returns_1(chat_module):
    """Detector reports clicked=True → return 1 and log ok."""
    page = _FakePage({
        "found": True, "clicked": True, "label": "Always allow",
    })
    result = chat_module._dismiss_inline_permission_card(page)
    assert result == 1
    body = _notepad_text(chat_module)
    assert "SYSTEM DIALOG _dismiss_inline_permission_card" in body
    assert "auto-dismiss: ok" in body
    assert "Always allow" in body


def test_inline_dismiss_not_found_returns_0_no_log(chat_module):
    """No permission card on page → return 0, nothing logged."""
    page = _FakePage({"found": False, "reason": "no permission card text"})
    result = chat_module._dismiss_inline_permission_card(page)
    assert result == 0
    # Notepad untouched.
    assert _notepad_text(chat_module) == ""


def test_inline_dismiss_detected_but_click_failed_logs_failed(chat_module):
    """Found but click failed → return 0, log 'failed' so host sees it."""
    page = _FakePage({
        "found": True, "clicked": False, "label": "Always allow",
        "error": "node detached",
    })
    result = chat_module._dismiss_inline_permission_card(page)
    assert result == 0
    body = _notepad_text(chat_module)
    assert "auto-dismiss: failed" in body
    assert "Always allow" in body


def test_inline_dismiss_evaluate_raises_returns_0(chat_module):
    """page.evaluate raising is treated as a miss, never propagates."""
    page = _FakePage(RuntimeError("CDP dropped"))
    result = chat_module._dismiss_inline_permission_card(page)
    assert result == 0
    assert _notepad_text(chat_module) == ""


def test_inline_dismiss_empty_payload_returns_0(chat_module):
    """evaluate returning None/empty dict → treated as no-op."""
    page = _FakePage(None)
    assert chat_module._dismiss_inline_permission_card(page) == 0


def test_inline_dismiss_missing_label_falls_back_to_default(chat_module):
    """Missing label still logs a usable line (default 'Always allow')."""
    page = _FakePage({"found": True, "clicked": True})
    result = chat_module._dismiss_inline_permission_card(page)
    assert result == 1
    assert "Always allow" in _notepad_text(chat_module)


def test_inline_probe_script_gating_strings(chat_module):
    """The JS probe uses the exact gate strings team-lead specified —
    "Claude wants to use" AND a brand match (Workflow / Workflow Server /
    legacy Universe Server) AND a button whose text starts with "Always
    allow". Pin the contract."""
    probe = chat_module._INLINE_ALWAYS_ALLOW_PROBE
    assert "Claude wants to use" in probe
    # Brand gate covers the new "Workflow" connector name AND retains
    # the legacy "Universe Server" name so the probe still works for
    # connectors that haven't been reconnected yet.
    assert "Workflow" in probe
    assert "Universe Server" in probe
    # Case-insensitive exact-prefix match on Always allow.
    assert "^always allow" in probe.lower()


def test_dialog_dismiss_selectors_shape(chat_module):
    """Pin DIALOG_DISMISS_SELECTORS shape so legacy-modal fallbacks
    don't silently drift. The list backs ``_dismiss_dialogs`` (the
    legacy role=dialog / aria-modal path) and is unreachable from the
    inline-card tests above. If the table loses its key entries or
    grows unboundedly, ``_dismiss_dialogs`` will quietly stop
    matching real Claude.ai permission UI in production."""
    selectors = chat_module.DIALOG_DISMISS_SELECTORS
    assert isinstance(selectors, list)
    # Sane bounds: enough fallbacks to cover legacy + extensions UX,
    # not so many that the table has become a junk drawer. Today: 18.
    assert 10 <= len(selectors) <= 30, (
        f"DIALOG_DISMISS_SELECTORS length {len(selectors)} outside sane bounds"
    )
    # All entries are CSS selector strings.
    for sel in selectors:
        assert isinstance(sel, str) and sel, f"non-string entry: {sel!r}"
    joined = "\n".join(selectors)
    # Legacy modal-dialog path: Always allow + Allow are the load-bearing
    # affordances. Losing either is a regression.
    assert '[role="dialog"]' in joined, "lost role=dialog scope"
    assert "Always allow" in joined, "lost 'Always allow' button match"
    assert "Allow" in joined, "lost 'Allow' button match"
    # Extensions/Goals permission gates (#73): aria-modal containers
    # carry different button copy. At least one of the newer action
    # words must remain wired.
    assert "Use this connector" in joined or "Approve" in joined, (
        "lost extensions/Goals aria-modal action-word coverage"
    )
    assert '[aria-modal="true"]' in joined, "lost aria-modal container scope"


def test_always_allow_toggle_selectors_shape(chat_module):
    """Pin _ALWAYS_ALLOW_TOGGLE_SELECTORS shape. ``_try_check_always_allow``
    walks the first 6 entries with text-proximity gating and the rest
    as the fallback; both halves must remain non-empty or the
    "persist this approval" affordance silently disappears."""
    selectors = chat_module._ALWAYS_ALLOW_TOGGLE_SELECTORS
    assert isinstance(selectors, list)
    # Sane bounds: text-proximity half (6) + fallback half (3+) = 9 today.
    assert 6 <= len(selectors) <= 20, (
        f"_ALWAYS_ALLOW_TOGGLE_SELECTORS length {len(selectors)} outside sane bounds"
    )
    for sel in selectors:
        assert isinstance(sel, str) and sel, f"non-string entry: {sel!r}"
    # _try_check_always_allow at scripts/claude_chat.py slices [:6]
    # for text-proximity selectors and [6:] for the fallback. Both
    # halves must remain non-empty.
    text_proximity_half = selectors[:6]
    fallback_half = selectors[6:]
    assert text_proximity_half, "text-proximity half [:6] empty"
    assert fallback_half, "fallback half [6:] empty"
    proximity_joined = "\n".join(text_proximity_half)
    # Text-proximity selectors must reference the "Always allow" label
    # — that's what makes them precise vs. the unscoped fallback.
    assert "Always allow" in proximity_joined, (
        "text-proximity half lost 'Always allow' label gate"
    )
    # Both modal scopes must stay covered (role=dialog + aria-modal).
    full_joined = "\n".join(selectors)
    assert '[role="dialog"]' in full_joined, "lost role=dialog scope"
    assert '[aria-modal="true"]' in full_joined, "lost aria-modal scope"


def test_always_allow_label_re_pattern(chat_module):
    """Pin _ALWAYS_ALLOW_LABEL_RE: matches the always-allow phrase
    family. _try_check_always_allow uses this on the fallback selector
    half; if the pattern stops matching the canonical phrases, the
    fallback path silently no-ops."""
    pattern = chat_module._ALWAYS_ALLOW_LABEL_RE
    # Canonical phrases the pattern must keep matching.
    for phrase in (
        "Always allow",
        "Don't ask again",
        "Remember this choice",
        "for this chat",
    ):
        assert pattern.search(phrase), f"pattern lost match for {phrase!r}"
    # Negative: arbitrary unrelated label must NOT match (regression
    # canary against a too-broad rewrite).
    assert not pattern.search("Cancel"), "pattern over-matches 'Cancel'"
