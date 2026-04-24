"""revert_loop_canary — detect stuck revert / provider-exhaustion loops.

Complements the MCP + tool + last-activity canaries. Those catch dark
daemon / broken tool handler / stalled executor. This canary catches
the state where the daemon IS making "progress" but every scene is
failing — the 2026-04-23 P0 class: workflow-worker looped through 67
revert attempts on the concordance universe before host noticed.

Signal: N consecutive "Draft: FAILED" or "score 0.00 -- REVERT" entries
in ``get_status.evidence.activity_log_tail`` within time window T.
Default: N=3 in T=10 minutes. The MCP surface is green (handshake + tool
canary return 0) and last-activity is fresh (writes are happening) —
but the work product is uniformly broken.

Distinct signal classes
-----------------------
  Revert-loop (this canary): work happens, work fails, work retries,
    repeat. Symptom of provider exhaustion / malformed prose / score=0.
  Dark daemon (mcp_public_canary): no MCP response.
  Tool-broken (mcp_tool_canary): MCP handshake but tool handler errors.
  Stalled (last_activity_canary): no activity for T minutes.

Exit codes
----------
  0  No loop signature detected (GREEN).
  2  Loop signature detected: N consecutive failure markers in T minutes.
  3  Daemon responded but activity_log_tail absent / unparseable.
  4  Handshake / connectivity failure (mirrors last_activity_canary
     step_code convention so operators can tell dark from stuck at a
     glance from the exit code alone).

Stdlib only.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Any

DEFAULT_URL = "https://tinyassets.io/mcp"
DEFAULT_WINDOW_MIN = 10
DEFAULT_THRESHOLD = 3
DEFAULT_TIMEOUT = 20.0

# Patterns that mark a single "this attempt failed" event in the
# activity log tail. Conservative by design — match verbatim strings
# emitted by the daemon's commit / revert pipeline so false positives
# stay rare. Extending these is low-risk; tightening them later is
# harder once operators have tuned N/T thresholds against them.
_FAILURE_PATTERNS: tuple[re.Pattern, ...] = (
    # Draft pipeline hard failure from domains/fantasy_daemon/phases/draft.py
    re.compile(r"Draft:\s*FAILED", re.IGNORECASE),
    # Commit-node REVERT verdict with score 0.00 — the 2026-04-23 P0
    # signature shape.
    re.compile(r"score\s+0\.0{1,2}\s*--\s*REVERT", re.IGNORECASE),
    # Generic revert-loop log from the commit pipeline.
    re.compile(r"verdict:\s*revert", re.IGNORECASE),
    # All-providers-exhausted: fires when every fallback in the chain
    # is cooling. Usually the upstream cause of draft failures.
    re.compile(r"All providers exhausted", re.IGNORECASE),
)

_INIT_PAYLOAD = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "revert-loop-canary", "version": "1.0"},
    },
}
_INITIALIZED_NOTIF = {"jsonrpc": "2.0", "method": "notifications/initialized"}


class RevertLoopError(Exception):
    """Raised by any step; carries the exit code the caller should exit with."""

    def __init__(self, code: int, msg: str) -> None:
        super().__init__(msg)
        self.code = code
        self.msg = msg


# ─────────────────────────────────────────────────────────────────────────────
# Pure classification (no network) — the core logic under test.
# ─────────────────────────────────────────────────────────────────────────────


def _line_is_failure(line: str) -> bool:
    """Return True when any failure-pattern regex matches ``line``."""
    return any(p.search(line) for p in _FAILURE_PATTERNS)


_TIMESTAMP_RE = re.compile(
    r"^(?:\[)?"
    r"(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)"
)


def _parse_line_timestamp(line: str) -> _dt.datetime | None:
    """Extract the ISO-8601 timestamp prefix from a log line, if present.

    Activity-log entries carry an ISO timestamp at the start of the line
    (see .agents/activity.log format). Lines without a parseable timestamp
    return None — those fall back to positional ordering in classify.
    """
    m = _TIMESTAMP_RE.match(line.strip())
    if not m:
        return None
    raw = m.group("ts")
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = _dt.datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_dt.timezone.utc)
    return parsed.astimezone(_dt.timezone.utc)


def classify_loop(
    activity_tail: list[str],
    *,
    now: _dt.datetime,
    window_min: int,
    threshold: int,
) -> tuple[int, str]:
    """Classify an activity_log_tail for a revert-loop signature.

    Returns (exit_code, human_message).

    Rules (conservative by design):
      - Only failure lines within ``window_min`` of ``now`` count.
      - Lines without a parseable timestamp are ignored for the window
        calculation (they can't be placed on the timeline); they do NOT
        contribute to or break a streak.
      - At least ``threshold`` failure lines in-window → loop detected
        (exit 2). Otherwise OK (exit 0).
      - Empty / None tail → exit 3 (daemon spoke but no evidence).

    Pure function — no network, no time calls beyond ``now``. Tests
    inject both so the decision logic is deterministic.
    """
    if not activity_tail:
        return 3, "activity_log_tail empty — no evidence to classify"

    cutoff = now - _dt.timedelta(minutes=window_min)
    failures_in_window: list[str] = []

    for raw_line in activity_tail:
        if not isinstance(raw_line, str) or not raw_line.strip():
            continue
        if not _line_is_failure(raw_line):
            continue
        ts = _parse_line_timestamp(raw_line)
        if ts is None:
            # Untimestamped failure — skip (can't place in window).
            continue
        if ts >= cutoff:
            failures_in_window.append(raw_line.strip())

    count = len(failures_in_window)
    if count >= threshold:
        preview = failures_in_window[-1][:160]
        return 2, (
            f"REVERT-LOOP detected: {count} failure markers in last "
            f"{window_min}min (threshold {threshold}). "
            f"Latest: {preview!r}"
        )
    return 0, (
        f"OK: {count} failure markers in last {window_min}min "
        f"(threshold {threshold})"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Network path (same shape as last_activity_canary).
# ─────────────────────────────────────────────────────────────────────────────


def _post(
    url: str,
    sid: str | None,
    payload: dict[str, Any],
    timeout: float,
    *,
    step_code: int,
) -> tuple[dict | None, str | None]:
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": "workflow-revert-loop-canary/1.0",
    }
    if sid:
        headers["mcp-session-id"] = sid
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        method="POST", headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            new_sid = resp.headers.get("mcp-session-id") or sid
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise RevertLoopError(
            step_code,
            f"HTTP {exc.code} on {payload.get('method','?')}: {exc.reason}",
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RevertLoopError(
            step_code,
            f"network error on {payload.get('method','?')}: {exc}",
        ) from exc

    parsed: dict | None = None
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            try:
                parsed = json.loads(line[5:].strip())
            except json.JSONDecodeError:
                pass
        elif line.startswith("{"):
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                pass
    return parsed, new_sid


def _extract_tool_text(tool_result: dict[str, Any]) -> str:
    return "".join(
        item.get("text", "")
        for item in tool_result.get("content", [])
        if item.get("type") == "text"
    )


def fetch_status_activity_tail(
    url: str,
    timeout: float,
    *,
    post_fn=None,
) -> list[str]:
    """MCP handshake + tools/call get_status; return activity_log_tail.

    Raises RevertLoopError with step_code=4 on handshake trouble, 3 on
    tool-shape trouble.
    """
    post = post_fn or _post

    resp, sid = post(url, None, _INIT_PAYLOAD, timeout, step_code=4)
    if resp is None or "result" not in resp:
        raise RevertLoopError(4, f"initialize returned no result: {resp!r}")
    if "error" in resp:
        raise RevertLoopError(
            4, f"initialize returned MCP error: {resp['error']!r}",
        )
    if not sid:
        raise RevertLoopError(
            4, "initialize response missing mcp-session-id header",
        )

    post(url, sid, _INITIALIZED_NOTIF, timeout, step_code=4)

    call_payload = {
        "jsonrpc": "2.0", "id": 2,
        "method": "tools/call",
        "params": {"name": "get_status", "arguments": {}},
    }
    resp, _ = post(url, sid, call_payload, timeout, step_code=3)
    if resp is None or "result" not in resp:
        raise RevertLoopError(
            3, f"get_status returned no result: {resp!r}",
        )
    result = resp["result"]
    if result.get("isError"):
        text = _extract_tool_text(result)[:300]
        raise RevertLoopError(3, f"get_status isError=true: {text!r}")
    text = _extract_tool_text(result)
    if not text:
        raise RevertLoopError(
            3, f"get_status returned no text content: {result!r}",
        )
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RevertLoopError(
            3, f"get_status text not JSON: {exc}; preview={text[:200]!r}",
        ) from exc

    evidence = payload.get("evidence")
    if not isinstance(evidence, dict):
        raise RevertLoopError(
            3,
            f"get_status payload has no evidence block; top-level keys: "
            f"{sorted(payload.keys())}",
        )
    tail = evidence.get("activity_log_tail")
    if not isinstance(tail, list):
        raise RevertLoopError(
            3,
            f"get_status evidence.activity_log_tail not a list: {type(tail).__name__}",
        )
    return tail


def run_canary(
    url: str,
    timeout: float,
    *,
    window_min: int,
    threshold: int,
    post_fn=None,
    now: _dt.datetime | None = None,
) -> tuple[int, str]:
    """Full canary flow. Returns (exit_code, human_message)."""
    current_now = now or _dt.datetime.now(tz=_dt.timezone.utc)
    tail = fetch_status_activity_tail(url, timeout, post_fn=post_fn)
    return classify_loop(
        tail, now=current_now,
        window_min=window_min, threshold=threshold,
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Probe activity_log_tail for revert-loop / provider-exhaustion signatures.",
    )
    ap.add_argument("--url", default=DEFAULT_URL,
                    help=f"MCP endpoint URL (default: {DEFAULT_URL})")
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                    help=f"Per-request timeout seconds (default: {DEFAULT_TIMEOUT})")
    default_window = int(os.environ.get(
        "WORKFLOW_REVERT_LOOP_WINDOW_MIN", DEFAULT_WINDOW_MIN,
    ))
    default_threshold = int(os.environ.get(
        "WORKFLOW_REVERT_LOOP_THRESHOLD", DEFAULT_THRESHOLD,
    ))
    ap.add_argument(
        "--window-min", type=int, default=default_window,
        help=f"Rolling window in minutes (default: {default_window}; "
             "env: WORKFLOW_REVERT_LOOP_WINDOW_MIN)",
    )
    ap.add_argument(
        "--threshold", type=int, default=default_threshold,
        help=f"Failure-marker count that triggers RED (default: {default_threshold}; "
             "env: WORKFLOW_REVERT_LOOP_THRESHOLD)",
    )
    ap.add_argument("--verbose", action="store_true",
                    help="Echo the canary classification summary.")
    args = ap.parse_args(argv)

    try:
        code, msg = run_canary(
            args.url, args.timeout,
            window_min=args.window_min, threshold=args.threshold,
        )
    except RevertLoopError as exc:
        print(
            f"[revert-loop] FAIL (exit {exc.code}): {exc.msg}",
            file=sys.stderr,
        )
        return exc.code

    if code == 0:
        print(f"[revert-loop] {msg}")
    else:
        print(f"[revert-loop] FAIL (exit {code}): {msg}", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
