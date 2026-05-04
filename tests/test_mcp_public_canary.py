"""Tests for scripts/mcp_public_canary.py."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import mcp_public_canary  # noqa: E402


def test_verbose_success_reports_latency(monkeypatch, capsys):
    """The public TINY probe should expose its measured round-trip time."""
    ticks = iter([10.0, 10.123])

    monkeypatch.setattr(mcp_public_canary.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(mcp_public_canary, "probe_result", lambda url, timeout: None)

    code = mcp_public_canary.main([
        "--url",
        "https://tinyassets.io/mcp",
        "--timeout",
        "5",
        "--verbose",
    ])

    assert code == 0
    assert capsys.readouterr().out == (
        "[canary] OK https://tinyassets.io/mcp rtt_ms=122\n"
    )


def test_non_verbose_success_stays_quiet(monkeypatch, capsys):
    monkeypatch.setattr(mcp_public_canary, "probe_result", lambda url, timeout: None)

    code = mcp_public_canary.main(["--url", "https://tinyassets.io/mcp"])

    assert code == 0
    assert capsys.readouterr().out == ""
