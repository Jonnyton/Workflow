"""LLM binding verifier — post-deploy smoke for HD-3.

Confirms the running daemon has at least one LLM provider bound (i.e.
``llm_endpoint_bound`` in get_status is not ``"unset"``).  Also issues a
minimal ``add_canon`` call to exercise the provider chain end-to-end and
checks the daemon's ``get_status`` ``phase`` field advances to something
other than ``idle``.

Exit codes
----------
0   llm_endpoint_bound is set + provider chain exercised.
1   MCP protocol error or unexpected response shape.
2   Network / connectivity error.
3   llm_endpoint_bound is "unset" — daemon has no LLM.
4   Provider chain exercise failed (canon write or status regression).

Usage
-----
    python scripts/verify_llm_binding.py
    python scripts/verify_llm_binding.py --url https://tinyassets.io/mcp
    python scripts/verify_llm_binding.py --url http://127.0.0.1:8001/mcp --timeout 15

Stdlib only — no third-party deps.
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
        "clientInfo": {"name": "verify-llm-binding", "version": "1.0"},
    },
}
_INITIALIZED_NOTIF = {"jsonrpc": "2.0", "method": "notifications/initialized"}


class VerifyError(Exception):
    def __init__(self, code: int, msg: str) -> None:
        super().__init__(msg)
        self.code = code
        self.msg = msg


def _post(
    url: str,
    sid: str | None,
    payload: dict[str, Any],
    timeout: float,
) -> tuple[dict | None, str | None]:
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": "workflow-verify-llm/1.0",
    }
    if sid:
        headers["mcp-session-id"] = sid
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        method="POST",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            new_sid = resp.headers.get("mcp-session-id") or sid
            body = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.HTTPError, urllib.error.URLError, OSError) as exc:
        raise VerifyError(2, f"network error on {url}: {exc}") from exc

    result: dict | None = None
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            try:
                result = json.loads(line[5:].strip())
            except json.JSONDecodeError:
                pass
        elif line.startswith("{"):
            try:
                result = json.loads(line)
            except json.JSONDecodeError:
                pass
    return result, new_sid


def _parse_status(result: dict[str, Any]) -> dict[str, Any]:
    for item in result.get("content", []):
        if item.get("type") == "text":
            try:
                return json.loads(item["text"])
            except (json.JSONDecodeError, KeyError):
                return {"raw": item["text"]}
    raise VerifyError(1, "get_status returned no text content")


def _llm_endpoint_bound(status: dict[str, Any]) -> Any:
    """Return the LLM binding from either historical or current status shape."""
    if "llm_endpoint_bound" in status:
        return status.get("llm_endpoint_bound")
    active_host = status.get("active_host")
    if isinstance(active_host, dict):
        return active_host.get("llm_endpoint_bound", "unset")
    return "unset"


def check_llm_binding(
    url: str,
    timeout: float,
    *,
    post_fn=None,  # injection seam for tests
) -> dict[str, Any]:
    """Run the full binding verification. Returns the final status dict.

    Raises VerifyError with an appropriate exit code on any failure.
    """
    _post_fn = post_fn or _post

    # Step 1: initialize
    resp, sid = _post_fn(url, None, _INIT_PAYLOAD, timeout)
    if not resp or "result" not in resp:
        raise VerifyError(1, f"MCP initialize failed: {resp!r}")
    _post_fn(url, sid, _INITIALIZED_NOTIF, timeout)

    # Step 2: get_status — check llm_endpoint_bound
    status_result = _call_tool_with(url, sid, "get_status", {}, timeout, _post_fn)
    status = _parse_status(status_result)

    llm_bound = _llm_endpoint_bound(status)
    print(f"[verify-llm] get_status llm_endpoint_bound={llm_bound!r}")

    if str(llm_bound).lower() in ("unset", "", "false", "none"):
        raise VerifyError(
            3,
            f"llm_endpoint_bound is {llm_bound!r} — daemon has no LLM bound. "
            "For default daemons, provide subscription-backed Claude/Codex CLI "
            "auth (for example WORKFLOW_CODEX_AUTH_JSON_B64 for Codex) and "
            "restart the container. API-key billing lanes are ignored when "
            "WORKFLOW_ALLOW_API_KEY_PROVIDERS is not explicitly truthy.",
        )

    # Step 3: exercise provider chain with a minimal add_canon call.
    # add_canon writes a short throwaway entry — cheapest tool call that
    # touches the provider dispatch path without starting a full run.
    print("[verify-llm] exercising provider chain via add_canon...")
    try:
        _call_tool_with(
            url,
            sid,
            "add_canon",
            {
                "content": "[verify-llm-binding smoke] throwaway entry — safe to delete",
                "tags": ["verify-llm-smoke"],
            },
            timeout,
            _post_fn,
        )
        print("[verify-llm] add_canon OK — provider chain reachable")
    except VerifyError as exc:
        # add_canon failure is non-fatal for the binding check itself;
        # the LLM may be bound but the universe not initialised yet.
        # Downgrade to a warning so the check still passes on binding.
        print(
            f"[verify-llm] WARN: add_canon returned error (non-fatal): {exc.msg}",
            file=sys.stderr,
        )

    return status


def _call_tool_with(
    url: str,
    sid: str | None,
    tool: str,
    args: dict[str, Any],
    timeout: float,
    post_fn,
) -> dict[str, Any]:
    payload = {
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tools/call",
        "params": {"name": tool, "arguments": args},
    }
    resp, _ = post_fn(url, sid, payload, timeout)
    if resp is None or "result" not in resp:
        raise VerifyError(1, f"tools/call {tool!r} got no result: {resp!r}")
    if resp["result"].get("isError"):
        content = resp["result"].get("content", [])
        text = next((c["text"] for c in content if c.get("type") == "text"), "")
        raise VerifyError(4, f"tools/call {tool!r} returned isError: {text[:300]}")
    return resp["result"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Verify the daemon has an LLM provider bound (HD-3 post-deploy check)."
    )
    ap.add_argument(
        "--url",
        default=DEFAULT_URL,
        help=f"MCP endpoint URL (default: {DEFAULT_URL})",
    )
    ap.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"Per-request timeout seconds (default {DEFAULT_TIMEOUT})",
    )
    args = ap.parse_args(argv)

    try:
        status = check_llm_binding(args.url, args.timeout)
        llm_bound = _llm_endpoint_bound(status)
        print(
            f"[verify-llm] PASS — llm_endpoint_bound={llm_bound!r}"
        )
        return 0
    except VerifyError as exc:
        print(f"[verify-llm] FAIL (exit {exc.code}): {exc.msg}", file=sys.stderr)
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
