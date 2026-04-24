"""Revert-loop canary tests (BUG-023 Lane 4a).

Pure-logic tests on `classify_loop` + network-path tests via injected
`post_fn`. No live daemon touched; fixtures drawn from actual activity
log shapes captured on 2026-04-23 and adjacent dates.
"""
from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import revert_loop_canary as rlc  # noqa: E402


def _now() -> _dt.datetime:
    return _dt.datetime(2026, 4, 23, 21, 0, 0, tzinfo=_dt.timezone.utc)


def _stamp(minutes_ago: float) -> str:
    ts = _now() - _dt.timedelta(minutes=minutes_ago)
    # Drop microseconds for cleaner fixtures.
    ts = ts.replace(microsecond=0)
    return ts.isoformat().replace("+00:00", "Z")


# ════════════════════════════════════════════════════════════════════
# classify_loop — pure logic
# ════════════════════════════════════════════════════════════════════


class TestClassifyLoopHappyPaths:
    def test_green_on_empty_failure_markers(self):
        tail = [
            f"{_stamp(1)} [worker] universe=x action=commit verdict=accept",
            f"{_stamp(5)} [worker] Draft: accepted",
        ]
        code, msg = rlc.classify_loop(
            tail, now=_now(), window_min=10, threshold=3,
        )
        assert code == 0
        assert "0 failure markers" in msg

    def test_red_on_three_consecutive_draft_failed(self):
        tail = [
            f"{_stamp(9)} [worker] Draft: FAILED (provider exhausted)",
            f"{_stamp(6)} [worker] Draft: FAILED (provider exhausted)",
            f"{_stamp(3)} [worker] Draft: FAILED (provider exhausted)",
        ]
        code, msg = rlc.classify_loop(
            tail, now=_now(), window_min=10, threshold=3,
        )
        assert code == 2
        assert "REVERT-LOOP detected" in msg
        assert "3 failure markers" in msg

    def test_red_on_revert_verdict_signature(self):
        tail = [
            f"{_stamp(8)} [commit] score 0.00 -- REVERT",
            f"{_stamp(5)} [commit] score 0.00 -- REVERT",
            f"{_stamp(2)} [commit] score 0.00 -- REVERT",
        ]
        code, msg = rlc.classify_loop(
            tail, now=_now(), window_min=10, threshold=3,
        )
        assert code == 2
        assert "REVERT-LOOP" in msg

    def test_red_on_all_providers_exhausted_pattern(self):
        tail = [
            f"{_stamp(7)} [provider] All providers exhausted for role=writer",
            f"{_stamp(5)} [provider] All providers exhausted for role=writer",
            f"{_stamp(3)} [provider] All providers exhausted for role=writer",
        ]
        code, _ = rlc.classify_loop(
            tail, now=_now(), window_min=10, threshold=3,
        )
        assert code == 2

    def test_mixed_patterns_count_toward_same_threshold(self):
        tail = [
            f"{_stamp(8)} [worker] Draft: FAILED",
            f"{_stamp(5)} [commit] score 0.00 -- REVERT",
            f"{_stamp(2)} [provider] All providers exhausted",
        ]
        code, _ = rlc.classify_loop(
            tail, now=_now(), window_min=10, threshold=3,
        )
        assert code == 2


class TestClassifyLoopWindowBehavior:
    def test_failures_outside_window_do_not_count(self):
        # 5 old failures, all outside the 10-min window → green.
        tail = [
            f"{_stamp(15)} [worker] Draft: FAILED",
            f"{_stamp(20)} [worker] Draft: FAILED",
            f"{_stamp(25)} [worker] Draft: FAILED",
            f"{_stamp(30)} [worker] Draft: FAILED",
            f"{_stamp(35)} [worker] Draft: FAILED",
        ]
        code, msg = rlc.classify_loop(
            tail, now=_now(), window_min=10, threshold=3,
        )
        assert code == 0
        assert "0 failure markers" in msg

    def test_mixed_inside_and_outside_window_counts_only_in_window(self):
        tail = [
            f"{_stamp(3)} [worker] Draft: FAILED",  # in
            f"{_stamp(20)} [worker] Draft: FAILED",  # out
            f"{_stamp(30)} [worker] Draft: FAILED",  # out
        ]
        code, _ = rlc.classify_loop(
            tail, now=_now(), window_min=10, threshold=3,
        )
        # Only 1 in-window failure; threshold=3 → green.
        assert code == 0

    def test_exactly_threshold_fires(self):
        tail = [
            f"{_stamp(3)} [worker] Draft: FAILED",
            f"{_stamp(2)} [worker] Draft: FAILED",
            f"{_stamp(1)} [worker] Draft: FAILED",
        ]
        code, _ = rlc.classify_loop(
            tail, now=_now(), window_min=10, threshold=3,
        )
        assert code == 2

    def test_one_under_threshold_does_not_fire(self):
        tail = [
            f"{_stamp(3)} [worker] Draft: FAILED",
            f"{_stamp(2)} [worker] Draft: FAILED",
        ]
        code, _ = rlc.classify_loop(
            tail, now=_now(), window_min=10, threshold=3,
        )
        assert code == 0


class TestClassifyLoopMissingTimestamps:
    def test_untimestamped_failure_ignored(self):
        tail = [
            "some log line without a timestamp Draft: FAILED",
            "another untimestamped Draft: FAILED",
            "still no timestamp Draft: FAILED",
        ]
        code, _ = rlc.classify_loop(
            tail, now=_now(), window_min=10, threshold=3,
        )
        # No timestamps → no placement in window → green.
        assert code == 0

    def test_mixed_timestamped_and_bare_lines(self):
        tail = [
            f"{_stamp(3)} [worker] Draft: FAILED",
            "no-timestamp Draft: FAILED",
            f"{_stamp(2)} [worker] Draft: FAILED",
            "another bare line Draft: FAILED",
            f"{_stamp(1)} [worker] Draft: FAILED",
        ]
        code, _ = rlc.classify_loop(
            tail, now=_now(), window_min=10, threshold=3,
        )
        # Only the 3 timestamped ones count → fires.
        assert code == 2


class TestClassifyLoopEmptyEvidence:
    def test_empty_tail_returns_code_3(self):
        code, msg = rlc.classify_loop(
            [], now=_now(), window_min=10, threshold=3,
        )
        assert code == 3
        assert "empty" in msg

    def test_tail_of_non_strings_ignored(self):
        tail = [None, 42, {"not": "a string"}, ""]  # type: ignore[list-item]
        code, msg = rlc.classify_loop(
            tail,  # type: ignore[arg-type]
            now=_now(), window_min=10, threshold=3,
        )
        # Non-string entries skipped; no failures counted.
        assert code == 0
        assert "0 failure markers" in msg


class TestFailurePatternPrecision:
    """Guard against over-matching — common non-failure phrases stay green."""

    @pytest.mark.parametrize(
        "ok_line",
        [
            "2026-04-23T21:00:00Z [worker] Draft accepted; verdict accept",
            "2026-04-23T21:00:00Z [worker] score 0.95 -- accept",
            "2026-04-23T21:00:00Z [worker] reverting to checkpoint",  # different shape
        ],
    )
    def test_false_positive_shapes_stay_green(self, ok_line: str):
        tail = [ok_line] * 5
        code, _ = rlc.classify_loop(
            tail, now=_now(), window_min=10, threshold=3,
        )
        assert code == 0

    def test_case_insensitive_matching(self):
        tail = [
            f"{_stamp(3)} [worker] DRAFT: failed (upper + mixed)",
            f"{_stamp(2)} [commit] Score 0.00 -- REVERT",
            f"{_stamp(1)} [worker] draft: FAILED",
        ]
        code, _ = rlc.classify_loop(
            tail, now=_now(), window_min=10, threshold=3,
        )
        assert code == 2


class TestParseLineTimestamp:
    def test_bare_iso(self):
        ts = rlc._parse_line_timestamp("2026-04-23T21:00:00Z foo bar")
        assert ts is not None
        assert ts.year == 2026 and ts.month == 4 and ts.day == 23

    def test_bracketed_iso(self):
        ts = rlc._parse_line_timestamp("[2026-04-23T21:00:00Z] foo")
        assert ts is not None

    def test_offset_form(self):
        ts = rlc._parse_line_timestamp("2026-04-23T21:00:00+00:00 foo")
        assert ts is not None

    def test_no_timestamp_returns_none(self):
        assert rlc._parse_line_timestamp("foo bar baz") is None

    def test_malformed_timestamp_returns_none(self):
        assert rlc._parse_line_timestamp("2026-99-99T99:99:99Z foo") is None


# ════════════════════════════════════════════════════════════════════
# fetch_status_activity_tail — network path via injected post_fn
# ════════════════════════════════════════════════════════════════════


def _make_init_response() -> dict:
    return {
        "jsonrpc": "2.0", "id": 1,
        "result": {"protocolVersion": "2024-11-05", "capabilities": {}},
    }


def _make_tool_response(tail: list[str]) -> dict:
    import json as _json
    payload = {
        "active_host": {"host_id": "test"},
        "evidence": {"activity_log_tail": tail},
    }
    return {
        "jsonrpc": "2.0", "id": 2,
        "result": {
            "content": [{"type": "text", "text": _json.dumps(payload)}],
        },
    }


class _StubPost:
    """Replay a list of (response, sid) tuples in order."""

    def __init__(self, steps: list[tuple[dict | None, str | None]]):
        self._steps = list(steps)
        self.calls: list[tuple[str | None, str]] = []

    def __call__(
        self, url, sid, payload, timeout, *, step_code,
    ):
        self.calls.append((sid, payload.get("method", "?")))
        if not self._steps:
            raise AssertionError("stub ran out of responses")
        return self._steps.pop(0)


class TestFetchStatusActivityTail:
    def test_happy_path_returns_tail(self):
        tail = [
            f"{_stamp(2)} [worker] Draft: accepted",
            f"{_stamp(1)} [worker] Draft: accepted",
        ]
        stub = _StubPost([
            (_make_init_response(), "sid-abc"),
            (None, "sid-abc"),  # notifications/initialized — no response
            (_make_tool_response(tail), "sid-abc"),
        ])
        result = rlc.fetch_status_activity_tail(
            "http://fake/mcp", 10.0, post_fn=stub,
        )
        assert result == tail

    def test_initialize_error_raises_step4(self):
        stub = _StubPost([
            ({"jsonrpc": "2.0", "id": 1, "error": {"message": "nope"}}, "sid"),
        ])
        with pytest.raises(rlc.RevertLoopError) as exc_info:
            rlc.fetch_status_activity_tail(
                "http://fake/mcp", 10.0, post_fn=stub,
            )
        assert exc_info.value.code == 4

    def test_initialize_missing_sid_raises_step4(self):
        stub = _StubPost([
            (_make_init_response(), None),  # no session id
        ])
        with pytest.raises(rlc.RevertLoopError) as exc_info:
            rlc.fetch_status_activity_tail(
                "http://fake/mcp", 10.0, post_fn=stub,
            )
        assert exc_info.value.code == 4

    def test_tool_is_error_raises_step3(self):
        stub = _StubPost([
            (_make_init_response(), "sid"),
            (None, "sid"),
            (
                {
                    "jsonrpc": "2.0", "id": 2,
                    "result": {
                        "isError": True,
                        "content": [{"type": "text", "text": "boom"}],
                    },
                },
                "sid",
            ),
        ])
        with pytest.raises(rlc.RevertLoopError) as exc_info:
            rlc.fetch_status_activity_tail(
                "http://fake/mcp", 10.0, post_fn=stub,
            )
        assert exc_info.value.code == 3

    def test_tool_text_not_json_raises_step3(self):
        stub = _StubPost([
            (_make_init_response(), "sid"),
            (None, "sid"),
            (
                {
                    "jsonrpc": "2.0", "id": 2,
                    "result": {
                        "content": [{"type": "text", "text": "not json"}],
                    },
                },
                "sid",
            ),
        ])
        with pytest.raises(rlc.RevertLoopError) as exc_info:
            rlc.fetch_status_activity_tail(
                "http://fake/mcp", 10.0, post_fn=stub,
            )
        assert exc_info.value.code == 3

    def test_payload_missing_evidence_raises_step3(self):
        stub = _StubPost([
            (_make_init_response(), "sid"),
            (None, "sid"),
            (
                {
                    "jsonrpc": "2.0", "id": 2,
                    "result": {
                        "content": [{
                            "type": "text",
                            "text": '{"active_host": {"host_id": "test"}}',
                        }],
                    },
                },
                "sid",
            ),
        ])
        with pytest.raises(rlc.RevertLoopError) as exc_info:
            rlc.fetch_status_activity_tail(
                "http://fake/mcp", 10.0, post_fn=stub,
            )
        assert exc_info.value.code == 3


# ════════════════════════════════════════════════════════════════════
# run_canary — end-to-end via stubbed post_fn
# ════════════════════════════════════════════════════════════════════


class TestRunCanary:
    def test_green_end_to_end(self):
        tail = [f"{_stamp(2)} [worker] Draft: accepted"]
        stub = _StubPost([
            (_make_init_response(), "sid"),
            (None, "sid"),
            (_make_tool_response(tail), "sid"),
        ])
        code, msg = rlc.run_canary(
            "http://fake/mcp", 10.0,
            window_min=10, threshold=3,
            post_fn=stub, now=_now(),
        )
        assert code == 0

    def test_red_end_to_end_on_three_failures(self):
        tail = [
            f"{_stamp(5)} [worker] Draft: FAILED",
            f"{_stamp(3)} [worker] Draft: FAILED",
            f"{_stamp(1)} [worker] Draft: FAILED",
        ]
        stub = _StubPost([
            (_make_init_response(), "sid"),
            (None, "sid"),
            (_make_tool_response(tail), "sid"),
        ])
        code, _ = rlc.run_canary(
            "http://fake/mcp", 10.0,
            window_min=10, threshold=3,
            post_fn=stub, now=_now(),
        )
        assert code == 2
