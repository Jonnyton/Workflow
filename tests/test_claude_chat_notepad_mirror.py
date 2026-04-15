"""Task #34 — mirror permission-dialog events to user_sim_session.md.

Tests the ``_log_dialog_to_notepad`` helper in isolation — it's the
load-bearing piece for notepad visibility. Browser-side drain and
the three call sites are glue around live Playwright state, not
unit-testable here.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


@pytest.fixture
def chat_module(tmp_path, monkeypatch):
    """Import scripts/claude_chat.py with NOTEPAD redirected to tmp_path."""
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    monkeypatch.syspath_prepend(str(scripts_dir))
    # Ensure a clean import so module-level NOTEPAD binding is reset.
    sys.modules.pop("claude_chat", None)
    module = importlib.import_module("claude_chat")
    module.NOTEPAD = tmp_path / "user_sim_session.md"
    return module


def _read_notepad(module) -> str:
    path = Path(module.NOTEPAD)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def test_log_writes_expected_line_shape(chat_module):
    """Happy path: one call → one line in the expected format."""
    chat_module._log_dialog_to_notepad(
        "Always allow for this chat", "ok", tool_name="auto-dismiss",
    )
    body = _read_notepad(chat_module)
    # One line ending in newline.
    assert body.count("\n") == 1
    assert "SYSTEM DIALOG auto-dismiss" in body
    assert 'detected: "Always allow for this chat"' in body
    assert "auto-dismiss: ok" in body


def test_log_truncates_to_80_chars(chat_module):
    """Long dialog text is truncated to 80 chars inside the quotes."""
    long_text = "x" * 200
    chat_module._log_dialog_to_notepad(long_text, "ok")
    body = _read_notepad(chat_module)
    # The quoted snippet should be exactly 80 x's.
    assert f'"{"x" * 80}"' in body
    assert f'"{"x" * 81}"' not in body


def test_log_collapses_newlines_in_snippet(chat_module):
    """Multi-line dialog text gets flattened so it stays on one line."""
    chat_module._log_dialog_to_notepad("line one\nline two", "ok")
    body = _read_notepad(chat_module)
    # One output line overall.
    assert body.count("\n") == 1
    assert "line one line two" in body
    assert "\n" not in body.split(" SYSTEM DIALOG")[0] + body.split('detected: "')[1].split('"')[0]


def test_log_appends_across_calls(chat_module):
    """Each call appends; does not truncate prior entries."""
    chat_module._log_dialog_to_notepad("first", "ok")
    chat_module._log_dialog_to_notepad("second", "failed")
    body = _read_notepad(chat_module)
    assert "first" in body
    assert "second" in body
    assert body.count("SYSTEM DIALOG") == 2
    assert "auto-dismiss: ok" in body
    assert "auto-dismiss: failed" in body


def test_log_default_tool_name_is_dash(chat_module):
    """Omitting tool_name writes `-` so the column stays populated."""
    chat_module._log_dialog_to_notepad("some gate", "ok")
    body = _read_notepad(chat_module)
    assert "SYSTEM DIALOG - " in body


def test_log_creates_parent_directory(tmp_path, chat_module):
    """NOTEPAD's parent is created on demand — first-run safety."""
    target = tmp_path / "nested" / "deeper" / "notepad.md"
    chat_module.NOTEPAD = target
    assert not target.parent.exists()
    chat_module._log_dialog_to_notepad("hello", "ok")
    assert target.exists()
    assert "hello" in target.read_text(encoding="utf-8")


def test_log_never_raises_on_write_error(monkeypatch, chat_module):
    """Notepad logging is observability — must never block the primary
    auto-dismiss flow even if the write path fails."""

    def _raise(*_a, **_kw):
        raise OSError("simulated failure")

    monkeypatch.setattr(chat_module.os, "open", _raise)
    # Must not raise.
    chat_module._log_dialog_to_notepad("anything", "ok")


def test_log_empty_text_still_writes_line(chat_module):
    """Empty detected text still produces a line — host notices the
    event even if we couldn't extract button copy."""
    chat_module._log_dialog_to_notepad("", "failed", tool_name="probe")
    body = _read_notepad(chat_module)
    assert 'detected: ""' in body
    assert "auto-dismiss: failed" in body
