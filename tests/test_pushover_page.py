"""Tests for scripts/pushover_page.py escalation logic.

Covers the should_page decision table (first alarm / within window / ladder
climb / host ack / post-24h cap) and send_pushover error-path handling.
Network calls are stubbed; we do not hit Pushover in tests.
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import pushover_page  # noqa: E402


def _mk_comment(created_at: str, body: str, login: str = "alice") -> dict:
    return {
        "created_at": created_at,
        "body": body,
        "user": {"login": login},
    }


def _now(ts: str) -> _dt.datetime:
    return _dt.datetime.fromisoformat(ts).replace(tzinfo=_dt.timezone.utc)


# ---- should_page -----------------------------------------------------------


def test_first_alarm_always_pages():
    fire, reason = pushover_page.should_page(
        comments=[], now=_now("2026-04-22T01:00:00"), is_first_alarm=True,
    )
    assert fire is True
    assert reason == "threshold_crossed"


def test_open_issue_no_markers_pages_as_catchup():
    # Open issue but no prior PAGED marker — safety catch-up.
    fire, reason = pushover_page.should_page(
        comments=[_mk_comment("2026-04-22T00:00:00Z", "RED body")],
        now=_now("2026-04-22T01:00:00"), is_first_alarm=False,
    )
    assert fire is True
    assert reason == "catchup_missing_marker"


def test_within_1h_window_does_not_re_page():
    comments = [
        _mk_comment("2026-04-22T01:00:00Z", "[PAGED 2026-04-22T01:00:00 threshold_crossed]"),
    ]
    # 30 min later — well within the 1h rung.
    fire, reason = pushover_page.should_page(
        comments=comments, now=_now("2026-04-22T01:30:00"), is_first_alarm=False,
    )
    assert fire is False
    assert reason.startswith("within_window_")


def test_1h_escalation_fires():
    comments = [
        _mk_comment("2026-04-22T01:00:00Z", "[PAGED 2026-04-22T01:00:00 threshold_crossed]"),
    ]
    fire, reason = pushover_page.should_page(
        comments=comments, now=_now("2026-04-22T02:00:05"), is_first_alarm=False,
    )
    assert fire is True
    assert reason == "escalation_3600s"


def test_4h_escalation_fires_after_1h_marker():
    comments = [
        _mk_comment("2026-04-22T01:00:00Z", "[PAGED 2026-04-22T01:00:00 threshold_crossed]"),
        _mk_comment("2026-04-22T02:00:00Z", "[PAGED 2026-04-22T02:00:00 escalation_3600s]"),
    ]
    # 4h after the most recent marker (02:00 -> 06:00).
    fire, reason = pushover_page.should_page(
        comments=comments, now=_now("2026-04-22T06:00:10"), is_first_alarm=False,
    )
    assert fire is True
    assert reason == "escalation_14400s"


def test_24h_escalation_fires_after_4h_marker():
    comments = [
        _mk_comment("2026-04-22T01:00:00Z", "[PAGED 2026-04-22T01:00:00 threshold_crossed]"),
        _mk_comment("2026-04-22T02:00:00Z", "[PAGED 2026-04-22T02:00:00 escalation_3600s]"),
        _mk_comment("2026-04-22T06:00:00Z", "[PAGED 2026-04-22T06:00:00 escalation_14400s]"),
    ]
    fire, reason = pushover_page.should_page(
        comments=comments, now=_now("2026-04-23T06:00:10"), is_first_alarm=False,
    )
    assert fire is True
    assert reason == "escalation_86400s"


def test_beyond_24h_rung_caps_at_24h_window():
    # 4 prior markers = ladder fully climbed. Re-page cadence locks at 24h.
    comments = [
        _mk_comment("2026-04-22T01:00:00Z", "[PAGED 2026-04-22T01:00:00 threshold_crossed]"),
        _mk_comment("2026-04-22T02:00:00Z", "[PAGED 2026-04-22T02:00:00 escalation_3600s]"),
        _mk_comment("2026-04-22T06:00:00Z", "[PAGED 2026-04-22T06:00:00 escalation_14400s]"),
        _mk_comment("2026-04-23T06:00:00Z", "[PAGED 2026-04-23T06:00:00 escalation_86400s]"),
    ]
    # 2h after last page — no re-page (inside 24h cap).
    fire, _ = pushover_page.should_page(
        comments=comments, now=_now("2026-04-23T08:00:00"), is_first_alarm=False,
    )
    assert fire is False
    # 24h+ after last page — re-page.
    fire2, reason2 = pushover_page.should_page(
        comments=comments, now=_now("2026-04-24T06:00:10"), is_first_alarm=False,
    )
    assert fire2 is True
    assert reason2 == "escalation_86400s"


def test_host_comment_between_pages_suppresses_re_page():
    comments = [
        _mk_comment("2026-04-22T01:00:00Z", "[PAGED 2026-04-22T01:00:00 threshold_crossed]"),
        _mk_comment("2026-04-22T01:30:00Z", "on it, investigating", login="jonathan"),
    ]
    # 2h after the page — would normally trigger 1h rung, but host acked.
    fire, reason = pushover_page.should_page(
        comments=comments, now=_now("2026-04-22T03:00:00"), is_first_alarm=False,
    )
    assert fire is False
    assert reason == "host_acknowledged"


def test_bot_comment_does_not_count_as_host_ack():
    # Bot-authored RED tick comment is not an ack.
    comments = [
        _mk_comment("2026-04-22T01:00:00Z", "[PAGED 2026-04-22T01:00:00 threshold_crossed]"),
        _mk_comment("2026-04-22T01:35:00Z", "RED @ tick", login="github-actions[bot]"),
    ]
    fire, reason = pushover_page.should_page(
        comments=comments, now=_now("2026-04-22T02:00:10"), is_first_alarm=False,
    )
    assert fire is True
    assert reason == "escalation_3600s"


def test_paged_marker_comments_are_not_host_ack_even_if_human_authored():
    # If a PAT posts the marker, the user.login is a real person. The marker
    # body prefix must take precedence so we don't mistake our own markers
    # for host ack.
    comments = [
        _mk_comment("2026-04-22T01:00:00Z", "[PAGED 2026-04-22T01:00:00 threshold_crossed]",
                    login="jonathan"),
    ]
    fire, reason = pushover_page.should_page(
        comments=comments, now=_now("2026-04-22T02:00:10"), is_first_alarm=False,
    )
    # Host did NOT comment separately; the marker is ours. Should still escalate.
    assert fire is True
    assert reason == "escalation_3600s"


# ---- send_pushover ---------------------------------------------------------


def test_send_pushover_missing_creds_returns_error():
    ok, msg = pushover_page.send_pushover(
        title="t", message="m", user_key="", app_token="",
    )
    assert ok is False
    assert "missing" in msg.lower()


def test_send_pushover_success_passes_params(monkeypatch):
    captured: dict = {}

    class _FakeResp:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def read(self):
            return b'{"status":1}'

    def fake_opener(req, timeout=None):
        captured["url"] = req.full_url
        captured["data"] = req.data
        return _FakeResp()

    ok, body = pushover_page.send_pushover(
        title="title", message="msg", url="https://x/run",
        url_title="Run", priority=1,
        user_key="u1", app_token="a1",
        _opener=fake_opener,
    )
    assert ok is True
    assert "status" in body
    assert captured["url"] == pushover_page.PUSHOVER_API
    # Verify form encoding carries our keys.
    decoded = captured["data"].decode("ascii")
    assert "token=a1" in decoded
    assert "user=u1" in decoded
    assert "priority=1" in decoded
    assert "url_title=Run" in decoded


def test_send_pushover_network_error_returns_friendly(monkeypatch):
    def fake_opener(req, timeout=None):
        raise TimeoutError("slow")

    ok, msg = pushover_page.send_pushover(
        title="t", message="m", user_key="u", app_token="a",
        _opener=fake_opener,
    )
    assert ok is False
    assert "network error" in msg


# ---- main() integration smoke ---------------------------------------------


def test_main_dry_run_decides_without_posting(tmp_path, capsys, monkeypatch):
    # Comments JSON = empty list; --first-alarm forces a PAGE decision.
    comments_path = tmp_path / "comments.json"
    comments_path.write_text("[]", encoding="utf-8")
    rc = pushover_page.main([
        "--issue-number", "42",
        "--run-url", "https://gh/run/1",
        "--probe-url", "https://x/mcp",
        "--probe-exit", "2",
        "--first-alarm",
        "--comments-json", str(comments_path),
        "--dry-run",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "decision=PAGE" in out
    assert "reason=threshold_crossed" in out
    assert "DRY-RUN" in out


def test_main_skips_when_within_window(tmp_path, capsys):
    comments_path = tmp_path / "comments.json"
    comments_path.write_text(json.dumps([
        {"created_at": "2999-01-01T01:00:00Z",
         "body": "[PAGED 2999-01-01T01:00:00 threshold_crossed]",
         "user": {"login": "github-actions[bot]"}},
    ]), encoding="utf-8")
    # "now" happens to be before the marker — elapsed negative. Should skip.
    rc = pushover_page.main([
        "--issue-number", "42",
        "--run-url", "https://gh/run/1",
        "--probe-url", "https://x/mcp",
        "--probe-exit", "2",
        "--comments-json", str(comments_path),
        "--dry-run",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "decision=SKIP" in out


def test_main_rejects_non_list_comments_json(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text('{"not": "a list"}', encoding="utf-8")
    rc = pushover_page.main([
        "--issue-number", "1",
        "--run-url", "https://gh/run/1",
        "--probe-url", "https://x/mcp",
        "--probe-exit", "2",
        "--comments-json", str(bad),
    ])
    assert rc == 2


# ---- parser robustness -----------------------------------------------------


def test_parse_iso_handles_z_suffix():
    ts = pushover_page._parse_iso("2026-04-22T01:00:00Z")
    assert ts is not None
    assert ts.tzinfo is not None


def test_parse_iso_returns_none_on_junk():
    assert pushover_page._parse_iso("not-a-date") is None
    assert pushover_page._parse_iso("") is None


# ---- priority=2 (emergency) form params -----------------------------------


def _capture_opener():
    """Return (captured_dict, fake_opener) for inspecting the POST body."""
    captured: dict = {}

    class _FakeResp:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def read(self):
            return b'{"status":1}'

    def fake_opener(req, timeout=None):
        captured["url"] = req.full_url
        captured["data"] = req.data
        return _FakeResp()

    return captured, fake_opener


def test_priority_2_requires_retry_and_expire():
    """Pushover API rejects priority=2 without retry+expire. We pre-empt
    that server-side rejection with a client-side guard returning a clear
    error so the caller never hits a mysterious 400 from the API.
    """
    ok, msg = pushover_page.send_pushover(
        title="t", message="m", priority=2,
        user_key="u", app_token="a",
    )
    assert ok is False
    assert "priority=2" in msg
    assert "retry" in msg
    assert "expire" in msg


def test_priority_2_with_both_params_sends_retry_and_expire():
    captured, opener = _capture_opener()
    ok, _ = pushover_page.send_pushover(
        title="P0", message="outage",
        priority=2,
        retry=pushover_page.P0_RETRY_S,
        expire=pushover_page.P0_EXPIRE_S,
        user_key="u", app_token="a",
        _opener=opener,
    )
    assert ok is True
    decoded = captured["data"].decode("ascii")
    assert "priority=2" in decoded
    assert f"retry={pushover_page.P0_RETRY_S}" in decoded
    assert f"expire={pushover_page.P0_EXPIRE_S}" in decoded


def test_priority_2_missing_only_retry_fails():
    ok, msg = pushover_page.send_pushover(
        title="t", message="m", priority=2,
        expire=3600,  # retry omitted
        user_key="u", app_token="a",
    )
    assert ok is False
    assert "retry" in msg


def test_priority_2_missing_only_expire_fails():
    ok, msg = pushover_page.send_pushover(
        title="t", message="m", priority=2,
        retry=60,  # expire omitted
        user_key="u", app_token="a",
    )
    assert ok is False
    assert "expire" in msg


def test_priority_1_does_not_require_retry_or_expire():
    """Priority=1 path must stay working without retry/expire — the
    pushover-test.yml workflow uses it deliberately."""
    captured, opener = _capture_opener()
    ok, _ = pushover_page.send_pushover(
        title="test", message="m", priority=1,
        user_key="u", app_token="a",
        _opener=opener,
    )
    assert ok is True
    decoded = captured["data"].decode("ascii")
    assert "priority=1" in decoded
    assert "retry=" not in decoded
    assert "expire=" not in decoded


def test_priority_1_ignores_retry_and_expire_if_passed():
    """retry+expire should only land on the wire for priority=2. If a
    caller accidentally passes them for priority=1, don't leak them into
    the form (Pushover ignores them at priority=1 but it's cleaner to
    keep the body minimal)."""
    captured, opener = _capture_opener()
    ok, _ = pushover_page.send_pushover(
        title="test", message="m", priority=1,
        retry=60, expire=3600,
        user_key="u", app_token="a",
        _opener=opener,
    )
    assert ok is True
    decoded = captured["data"].decode("ascii")
    assert "priority=1" in decoded
    assert "retry=" not in decoded
    assert "expire=" not in decoded


def test_p0_constants_satisfy_pushover_api_bounds():
    """Pushover API: retry >= 30s; expire <= 10800s. Guard against future
    constant edits drifting outside the API-enforced range."""
    assert pushover_page.P0_RETRY_S >= 30
    assert pushover_page.P0_EXPIRE_S <= 10800
    assert pushover_page.P0_EXPIRE_S > pushover_page.P0_RETRY_S
