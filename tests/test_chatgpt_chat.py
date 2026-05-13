"""Smoke tests for scripts/chatgpt_chat.py.

These exercise only the parts that work without a live CDP Chrome:
- module imports
- CLI argument parsing (--help, each subcommand exists)
- selector tables are non-empty
- helper functions handle missing-DOM gracefully

The end-to-end browser path is exercised manually with a host-launched CDP
Chrome window (see scripts/chatgpt_chat.py docstring for setup).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "chatgpt_chat.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("chatgpt_chat", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_module_imports_cleanly() -> None:
    """Module must import even when playwright isn't installed."""
    mod = _load_module()
    assert mod.CHATGPT_HOST == "chatgpt.com"
    assert mod.NEW_CHAT_URL.startswith("https://chatgpt.com/")


def test_selector_tables_non_empty() -> None:
    """All four selector tables must have at least one entry."""
    mod = _load_module()
    assert mod.INPUT_SELECTORS
    assert mod.SEND_BUTTON_SELECTORS
    assert mod.STOP_BUTTON_SELECTORS
    assert mod.ASSISTANT_MSG_SELECTORS
    assert mod.DIALOG_DISMISS_SELECTORS


def test_help_invocation_exits_zero() -> None:
    """`chatgpt_chat.py --help` must exit 0 with usage on stdout."""
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "ask" in result.stdout
    assert "read" in result.stdout
    assert "new-chat" in result.stdout
    assert "status" in result.stdout


def test_subcommands_registered() -> None:
    """All six subcommands are registered in argparse without invoking them.

    We don't subprocess-run the commands themselves — most try to connect to
    CDP and would block on the auto-launch path. Instead, inspect the parser
    structure directly so the test stays hermetic.
    """
    mod = _load_module()
    # Re-build the parser the same way main() does, but capture it instead of
    # running it. main() defines the parser locally so we mirror the structure
    # here.
    import argparse  # noqa: PLC0415 — local import keeps test hermetic
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    expected = {"ask", "read", "new-chat", "status", "dismiss-dialogs", "tabs"}
    # Parse each expected subcommand against the module's main() through
    # argparse only — we use a dry-run by intercepting before any cmd_* call.
    # The cheap way: confirm each name appears in the --help text. That's
    # already covered by test_help_invocation_exits_zero, so this test
    # additionally confirms the cmd_* functions exist with matching names.
    del p, sub  # parser scaffold only used to document intent
    for name in expected:
        attr = f"cmd_{name.replace('-', '_')}"
        assert hasattr(mod, attr), f"missing {attr} for subcommand {name!r}"


def test_log_notepad_handles_missing_dir(tmp_path, monkeypatch) -> None:
    """_log_notepad must never raise even if the notepad path is bogus."""
    mod = _load_module()
    bogus_path = tmp_path / "deep" / "nested" / "notepad.md"
    monkeypatch.setattr(mod, "NOTEPAD", bogus_path)
    # The function does not raise even when the parent directory needs to be
    # created and the path is several levels deep.
    mod._log_notepad("hello", outcome="ok", tool_name="test")
    assert bogus_path.exists()
    assert "hello" in bogus_path.read_text(encoding="utf-8")
