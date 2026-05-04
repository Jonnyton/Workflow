"""Public MCP uptime canary — stdlib-only end-to-end probe.

POSTs an ``initialize`` JSON-RPC request against a configurable MCP
endpoint (default ``https://tinyassets.io/mcp``) and validates the
response carries a well-formed MCP ``serverInfo`` + ``protocolVersion``.

Intended for continuous uptime monitoring per the 24/7 forever rule.
Tray wires this on a timer; on nonzero exit, tray surfaces an alert.

Exit codes
----------
0   Endpoint is healthy — full MCP initialize round-trip succeeded.
1   Endpoint is reachable but did not return a valid MCP initialize
    response (wrong content-type, missing fields, protocol mismatch).
2   Endpoint is unreachable (DNS failure, TCP refused, TLS failure,
    HTTP non-2xx).
3   Response parsed but MCP-level error returned (``jsonrpc`` error
    field present).

Usage
-----
    python scripts/mcp_public_canary.py
    python scripts/mcp_public_canary.py --url https://tinyassets.io/mcp
    python scripts/mcp_public_canary.py --timeout 15

All output on failure goes to stderr so tray can stream it. stdout
stays silent unless ``--verbose`` is passed so the canary is cheap to
tail.
"""

from __future__ import annotations

import argparse
import json
import ssl
import sys
import time
import urllib.error
import urllib.request
from typing import Any

DEFAULT_URL = "https://tinyassets.io/mcp"
DEFAULT_TIMEOUT = 10.0

_INIT_PAYLOAD = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "mcp-public-canary", "version": "1.0"},
    },
}


def _die(code: int, msg: str) -> None:
    print(f"[canary] {msg}", file=sys.stderr)
    sys.exit(code)


class CanaryError(Exception):
    """Probe failed. Carries the same (exit_code, message) shape as ``_die``."""

    def __init__(self, code: int, msg: str):
        super().__init__(msg)
        self.code = code
        self.msg = msg


def _parse_sse_or_json(body: bytes) -> dict[str, Any]:
    """MCP streamable-http returns either JSON or SSE ``event: message``
    frames. Accept both."""
    text = body.decode("utf-8", errors="replace").strip()
    if not text:
        raise ValueError("empty body")
    if text.startswith("{"):
        return json.loads(text)
    # SSE: find the first ``data: {...}`` line.
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            payload = line[len("data:"):].strip()
            if payload:
                return json.loads(payload)
    raise ValueError("no JSON or SSE data frame in response body")


def probe_result(url: str, timeout: float) -> None:
    """Run the probe. Return None on success; raise ``CanaryError`` on failure.

    Importable by layered canary wrappers that need to log outcomes without
    exiting the process. ``probe()`` is the CLI-shaped thin adapter.
    """
    req = urllib.request.Request(
        url,
        data=json.dumps(_INIT_PAYLOAD).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": "workflow-mcp-canary/1.0",
        },
    )
    ctx = ssl.create_default_context()

    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            status = resp.status
            body = resp.read()
    except urllib.error.HTTPError as exc:
        raise CanaryError(2, f"HTTP {exc.code} from {url}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise CanaryError(2, f"unreachable {url}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise CanaryError(2, f"timeout after {timeout}s: {url}") from exc
    except ssl.SSLError as exc:
        raise CanaryError(2, f"TLS error {url}: {exc}") from exc
    except OSError as exc:
        raise CanaryError(2, f"socket error {url}: {exc}") from exc

    if status != 200:
        raise CanaryError(2, f"non-200 status {status} from {url}")

    try:
        payload = _parse_sse_or_json(body)
    except (ValueError, json.JSONDecodeError) as exc:
        preview = body[:200].decode("utf-8", errors="replace")
        raise CanaryError(1, f"non-MCP body from {url}: {exc}; preview={preview!r}") from exc

    if "error" in payload:
        raise CanaryError(3, f"MCP error response from {url}: {payload['error']}")

    result = payload.get("result") or {}
    if not isinstance(result, dict):
        raise CanaryError(1, f"malformed result (not a dict) from {url}: {result!r}")
    if not result.get("protocolVersion"):
        raise CanaryError(1, f"missing protocolVersion in result from {url}: {result!r}")
    server_info = result.get("serverInfo") or {}
    if not server_info.get("name"):
        raise CanaryError(1, f"missing serverInfo.name in result from {url}: {result!r}")


def probe(url: str, timeout: float) -> int:
    """CLI-shaped adapter — calls ``probe_result`` and ``_die``s on failure."""
    start = time.monotonic()
    try:
        probe_result(url, timeout)
    except CanaryError as exc:
        _die(exc.code, exc.msg)
    return int((time.monotonic() - start) * 1000)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Probe a public MCP endpoint.")
    ap.add_argument("--url", default=DEFAULT_URL, help=f"MCP endpoint URL (default {DEFAULT_URL})")
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                    help=f"request timeout seconds (default {DEFAULT_TIMEOUT})")
    ap.add_argument("--verbose", action="store_true",
                    help="print success line to stdout")
    args = ap.parse_args(argv)

    rtt_ms = probe(args.url, args.timeout)

    if args.verbose:
        print(f"[canary] OK {args.url} rtt_ms={rtt_ms}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
