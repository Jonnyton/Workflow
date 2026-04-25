"""Wiki write-roundtrip canary — Layer-1 extension.

Probes the wiki MCP surface with a write-then-read roundtrip against a
dedicated canary draft slug (``drafts/canary/uptime-probe.md``).  A working
``initialize`` handshake is necessary but not sufficient: this canary also
verifies that:

- ``wiki action=write`` persists a known body without error.
- ``wiki action=read`` returns that body verbatim.

Wiki-write failure is P0 (Forever Rule: 24/7 uptime, auto-heal pipeline).
BUG-028 demonstrated that a slug-normalization bug could silently break bug
filing while the Layer-1 MCP handshake stayed green.  This canary closes
that gap.

Exit codes
----------
0  — all probe steps passed.
2  — MCP handshake failed (initialize / session).
6  — wiki write failed (isError or network error).
7  — wiki read failed or roundtrip content mismatch.
99 — unexpected error.

Usage
-----
    python scripts/wiki_canary.py
    python scripts/wiki_canary.py --url http://127.0.0.1:8001/mcp --verbose
    python scripts/wiki_canary.py --once --format=gha   # GHA output mode

Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPTS.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from mcp_tool_canary import ToolCanaryError, _extract_tool_text, _post  # noqa: E402
from uptime_canary import _append_log, _now_local_iso  # noqa: E402

DEFAULT_URL = "https://tinyassets.io/mcp"
DEFAULT_TIMEOUT = 20.0

_CANARY_SLUG = "uptime-probe"
_CANARY_CATEGORY = "canary"
_CANARY_BODY = "Workflow wiki uptime canary — automated write-roundtrip probe."

_INIT_PAYLOAD = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "wiki-canary", "version": "1.0"},
    },
}
_INITIALIZED_NOTIF = {"jsonrpc": "2.0", "method": "notifications/initialized"}


def _wiki_write_payload(call_id: int) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": call_id,
        "method": "tools/call",
        "params": {
            "name": "wiki",
            "arguments": {
                "action": "write",
                "slug": _CANARY_SLUG,
                "category": _CANARY_CATEGORY,
                "body": _CANARY_BODY,
            },
        },
    }


def _wiki_read_payload(call_id: int) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": call_id,
        "method": "tools/call",
        "params": {
            "name": "wiki",
            "arguments": {
                "action": "read",
                "slug": _CANARY_SLUG,
                "category": _CANARY_CATEGORY,
            },
        },
    }


def _format_green(ts: str, url: str, rtt_ms: int) -> str:
    return f"{ts} GREEN layer=wiki url={url} surface=wiki_write rtt_ms={rtt_ms}"


def _format_red(ts: str, url: str, exit_code: int, reason: str, rtt_ms: int) -> str:
    reason_oneline = reason.replace("\n", " ").replace("\r", " ")
    return (
        f"{ts} RED   layer=wiki url={url} exit={exit_code} "
        f"surface=wiki_write rtt_ms={rtt_ms} reason={reason_oneline!r}"
    )


def _emit_gha_kv(key: str, value: str) -> None:
    if "\n" in value or "\r" in value:
        import uuid
        delimiter = f"EOF_{uuid.uuid4().hex}"
        print(f"{key}<<{delimiter}")
        print(value)
        print(delimiter)
    else:
        print(f"{key}={value}")


def run_canary(
    url: str,
    timeout: float,
    *,
    post_fn=None,
    verbose: bool = False,
) -> None:
    """Run the wiki write-roundtrip canary.

    ``post_fn`` is injectable for tests (same signature as ``mcp_tool_canary._post``).
    Raises ``ToolCanaryError`` on any failure with the appropriate exit code.
    """
    post = post_fn or _post

    # ---- Step 1: MCP handshake -------------------------------------------
    resp, sid = post(url, None, _INIT_PAYLOAD, timeout, step_code=2)
    if resp is None or "result" not in resp:
        raise ToolCanaryError(2, f"initialize returned no result: {resp!r}")
    if "error" in resp:
        raise ToolCanaryError(2, f"initialize returned MCP error: {resp['error']!r}")
    if not sid:
        raise ToolCanaryError(2, "initialize response did not include mcp-session-id header")
    post(url, sid, _INITIALIZED_NOTIF, timeout, step_code=2)
    if verbose:
        print(f"[wiki-canary] handshake OK sid={sid!r}")

    # ---- Step 2: wiki write ----------------------------------------------
    write_resp, _ = post(url, sid, _wiki_write_payload(2), timeout, step_code=6)
    if write_resp is None or "result" not in write_resp:
        raise ToolCanaryError(6, f"wiki write returned no result: {write_resp!r}")
    write_result = write_resp["result"]
    if write_result.get("isError"):
        text = _extract_tool_text(write_result)[:300]
        raise ToolCanaryError(6, f"wiki write isError=true: {text!r}")
    write_text = _extract_tool_text(write_result)
    if not write_text:
        raise ToolCanaryError(6, f"wiki write returned no text content: {write_result!r}")
    try:
        write_obj = json.loads(write_text)
    except json.JSONDecodeError as exc:
        raise ToolCanaryError(
            6, f"wiki write text not JSON: {exc}; preview={write_text[:200]!r}"
        ) from exc
    if write_obj.get("status") not in ("ok", "written", "updated", "filed"):
        raise ToolCanaryError(6, f"wiki write unexpected status: {write_obj!r}")
    if verbose:
        print(f"[wiki-canary] wiki write OK: {write_obj.get('status')!r}")

    # ---- Step 3: wiki read roundtrip -------------------------------------
    read_resp, _ = post(url, sid, _wiki_read_payload(3), timeout, step_code=7)
    if read_resp is None or "result" not in read_resp:
        raise ToolCanaryError(7, f"wiki read returned no result: {read_resp!r}")
    read_result = read_resp["result"]
    if read_result.get("isError"):
        text = _extract_tool_text(read_result)[:300]
        raise ToolCanaryError(7, f"wiki read isError=true: {text!r}")
    read_text = _extract_tool_text(read_result)
    if not read_text:
        raise ToolCanaryError(7, f"wiki read returned no text content: {read_result!r}")
    if _CANARY_BODY not in read_text:
        raise ToolCanaryError(
            7,
            f"wiki roundtrip mismatch: expected body not found in read response. "
            f"preview={read_text[:300]!r}",
        )
    if verbose:
        print("[wiki-canary] wiki read roundtrip OK — body confirmed")


def run_probe(
    url: str, timeout: float, fmt: str = "log", *, post_fn=None, verbose: bool = False,
) -> int:
    """Run one wiki roundtrip probe. Returns exit code (0=green, nonzero=red)."""
    ts = _now_local_iso()
    start = time.monotonic()
    try:
        run_canary(url, timeout, post_fn=post_fn, verbose=verbose)
    except ToolCanaryError as exc:
        rtt_ms = int((time.monotonic() - start) * 1000)
        _append_log(_format_red(ts, url, exc.code, exc.msg, rtt_ms))
        if fmt == "gha":
            _emit_gha_kv("status", str(exc.code))
            _emit_gha_kv("msg", exc.msg)
        return exc.code
    except Exception as exc:
        rtt_ms = int((time.monotonic() - start) * 1000)
        msg = f"unexpected: {exc!r}"
        _append_log(_format_red(ts, url, 99, msg, rtt_ms))
        if fmt == "gha":
            _emit_gha_kv("status", "99")
            _emit_gha_kv("msg", msg)
        return 99
    rtt_ms = int((time.monotonic() - start) * 1000)
    _append_log(_format_green(ts, url, rtt_ms))
    if fmt == "gha":
        _emit_gha_kv("status", "0")
        _emit_gha_kv("msg", f"OK wiki roundtrip {url} rtt_ms={rtt_ms}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Wiki write-roundtrip uptime canary (P0 surface).",
    )
    ap.add_argument(
        "--url", default=DEFAULT_URL,
        help=f"MCP endpoint URL (default: {DEFAULT_URL})",
    )
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    ap.add_argument(
        "--once", action="store_true",
        help="Run a single probe and exit (default behavior; flag is a no-op).",
    )
    ap.add_argument(
        "--format", dest="fmt", choices=["log", "gha"], default="log",
        help="Output format: 'log' (default) or 'gha' ($GITHUB_OUTPUT).",
    )
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)
    return run_probe(args.url, args.timeout, fmt=args.fmt, verbose=args.verbose)


if __name__ == "__main__":
    sys.exit(main())
