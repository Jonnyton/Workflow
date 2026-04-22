"""MCP tool-invocation canary — end-to-end liveness beyond handshake.

Closes the gap flagged in task #6: `mcp_public_canary.py` only probes
``initialize``, which proves the daemon answers the MCP handshake but
NOT that any tool handler actually works. The ``handshake green, tool
handler crashed`` failure class would go undetected without this.

Canary flow
-----------
1. POST ``initialize`` → capture ``mcp-session-id`` header.
2. POST ``notifications/initialized`` (MCP protocol requires this
   before tool calls, even if the server is lenient).
3. POST ``tools/list`` → confirm the returned tools array is non-empty.
4. POST ``tools/call`` for ``universe`` with ``action=inspect`` → confirm
   the returned content is valid JSON carrying a ``universe_id`` field.

Exit codes (task #6 spec)
-------------------------
0 — all four steps passed.
2 — handshake failed (initialize error, network, TLS, non-200).
3 — session establishment failed (no ``mcp-session-id`` header, or
    ``notifications/initialized`` POST errored).
4 — ``tools/list`` failed or returned an empty tools array.
5 — ``tools/call universe action=inspect`` failed or returned an
    invalid response (no ``universe_id``, isError set, etc.).

Usage
-----
    python scripts/mcp_tool_canary.py
    python scripts/mcp_tool_canary.py --url http://127.0.0.1:8001/mcp
    python scripts/mcp_tool_canary.py --verbose --timeout 20

Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any

DEFAULT_URL = "https://tinyassets.io/mcp"
DEFAULT_TIMEOUT = 20.0

_INIT_PAYLOAD = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "mcp-tool-canary", "version": "1.0"},
    },
}
_INITIALIZED_NOTIF = {"jsonrpc": "2.0", "method": "notifications/initialized"}


class ToolCanaryError(Exception):
    """Raised by any step; carries the exit code so main() can exit with it."""

    def __init__(self, code: int, msg: str) -> None:
        super().__init__(msg)
        self.code = code
        self.msg = msg


def _post(
    url: str,
    sid: str | None,
    payload: dict[str, Any],
    timeout: float,
    *,
    step_code: int,
) -> tuple[dict | None, str | None]:
    """Send one JSON-RPC POST. Returns (parsed_response_or_None, new_sid).

    Raises ``ToolCanaryError(step_code, ...)`` on network/HTTP/TLS failures
    so the caller doesn't need to wrap. The step_code argument tags the
    failure with the right exit code for the canary's failure ladder.
    """
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": "workflow-mcp-tool-canary/1.0",
    }
    if sid:
        headers["mcp-session-id"] = sid
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            new_sid = resp.headers.get("mcp-session-id") or sid
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise ToolCanaryError(
            step_code, f"HTTP {exc.code} on {payload.get('method','?')}: {exc.reason}",
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ToolCanaryError(
            step_code, f"network error on {payload.get('method','?')}: {exc}",
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
    """Return the concatenated text of content items of type 'text'."""
    return "".join(
        item.get("text", "")
        for item in tool_result.get("content", [])
        if item.get("type") == "text"
    )


def run_canary(
    url: str,
    timeout: float,
    *,
    post_fn=None,
    verbose: bool = False,
) -> dict[str, Any]:
    """Run the four-step canary. Returns the inspect-result dict on success.

    ``post_fn`` is an injection seam for tests so unit tests can feed
    scripted responses without network I/O. Signature matches ``_post``.
    Raises ``ToolCanaryError`` on any failure.
    """
    post = post_fn or _post

    # Step 1 — initialize (handshake).
    resp, sid = post(url, None, _INIT_PAYLOAD, timeout, step_code=2)
    if resp is None or "result" not in resp:
        raise ToolCanaryError(
            2, f"initialize returned no result: {resp!r}",
        )
    if "error" in resp:
        raise ToolCanaryError(
            2, f"initialize returned MCP error: {resp['error']!r}",
        )
    if verbose:
        print(f"[tool-canary] initialize OK sid={sid!r}")

    # Step 2 — session established (mcp-session-id present + notif accepted).
    if not sid:
        raise ToolCanaryError(
            3, "initialize response did not include mcp-session-id header",
        )
    # notifications/initialized has no id and no response body; we still POST
    # it for protocol conformance. HTTP-layer errors map to step_code=3.
    post(url, sid, _INITIALIZED_NOTIF, timeout, step_code=3)
    if verbose:
        print("[tool-canary] session established OK")

    # Step 3 — tools/list and assert non-empty.
    list_payload = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
    resp, _ = post(url, sid, list_payload, timeout, step_code=4)
    if resp is None or "result" not in resp:
        raise ToolCanaryError(
            4, f"tools/list returned no result: {resp!r}",
        )
    tools = resp["result"].get("tools", [])
    if not isinstance(tools, list) or not tools:
        raise ToolCanaryError(
            4, f"tools/list returned empty or non-list tools: {tools!r}",
        )
    if verbose:
        names = [t.get("name") for t in tools]
        print(f"[tool-canary] tools/list OK ({len(tools)} tool(s)): {names}")

    # Step 4 — tools/call universe action=inspect and assert universe_id.
    call_payload = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "universe", "arguments": {"action": "inspect"}},
    }
    resp, _ = post(url, sid, call_payload, timeout, step_code=5)
    if resp is None or "result" not in resp:
        raise ToolCanaryError(
            5, f"universe inspect returned no result: {resp!r}",
        )
    result = resp["result"]
    if result.get("isError"):
        text = _extract_tool_text(result)[:300]
        raise ToolCanaryError(
            5, f"universe inspect isError=true: {text!r}",
        )
    text = _extract_tool_text(result)
    if not text:
        raise ToolCanaryError(
            5, f"universe inspect returned no text content: {result!r}",
        )
    try:
        inspect_obj = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ToolCanaryError(
            5, f"universe inspect text not JSON: {exc}; preview={text[:200]!r}",
        ) from exc
    uid = inspect_obj.get("universe_id")
    if not uid:
        raise ToolCanaryError(
            5, f"universe inspect missing universe_id: {inspect_obj!r}",
        )
    if verbose:
        print(f"[tool-canary] universe inspect OK universe_id={uid!r}")

    return inspect_obj


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="End-to-end MCP tool-invocation canary (handshake + "
                    "session + tools/list + universe inspect).",
    )
    ap.add_argument("--url", default=DEFAULT_URL,
                    help=f"MCP endpoint URL (default: {DEFAULT_URL})")
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                    help=f"Per-request timeout seconds (default: {DEFAULT_TIMEOUT})")
    ap.add_argument("--verbose", action="store_true",
                    help="Print per-step OK lines to stdout.")
    args = ap.parse_args(argv)

    try:
        inspect = run_canary(args.url, args.timeout, verbose=args.verbose)
    except ToolCanaryError as exc:
        print(f"[tool-canary] FAIL (exit {exc.code}): {exc.msg}", file=sys.stderr)
        return exc.code

    if args.verbose:
        print(f"[tool-canary] PASS universe_id={inspect.get('universe_id')!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
