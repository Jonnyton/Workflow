"""Self-host migration smoke test — Row F.

Probes both the user-facing canonical URL and the direct tunnel URL, runs
get_status + tools/list on each, and asserts parity on the tool set and
get_status structure.

Exit codes:
  0  Both URLs healthy and in parity.
  1  One or both URLs returned unexpected MCP content (protocol-level fail).
  2  One or both URLs unreachable (network-level fail).
  3  URLs reachable and individually healthy but NOT in parity.
  4  Invalid arguments.

Usage:
  python scripts/selfhost_smoke.py
  python scripts/selfhost_smoke.py \\
      --canonical https://tinyassets.io/mcp \\
      --tunnel    https://mcp.tinyassets.io/mcp \\
      --timeout   20

Designed to run at hour 1, hour 24, and hour 47 of the 48-hour offline
acceptance trial per the Row F spec.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from mcp_public_canary import CanaryError, probe_result  # noqa: E402
from verify_llm_binding import VerifyError, check_llm_binding  # noqa: E402

CANONICAL_URL = "https://tinyassets.io/mcp"
TUNNEL_URL = "https://mcp.tinyassets.io/mcp"
DEFAULT_TIMEOUT = 20.0

_INIT_PAYLOAD = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "selfhost-smoke", "version": "1.0"},
    },
}
_INITIALIZED_NOTIF = {"jsonrpc": "2.0", "method": "notifications/initialized"}
_TOOLS_LIST_PAYLOAD = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
_GET_STATUS_PAYLOAD = {
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {"name": "get_status", "arguments": {}},
}


class SmokeError(Exception):
    def __init__(self, code: int, msg: str) -> None:
        super().__init__(msg)
        self.code = code
        self.msg = msg


def _post(
    url: str, sid: str | None, payload: dict, timeout: float
) -> tuple[dict | None, str | None]:
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": "workflow-selfhost-smoke/1.0",
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
        raise SmokeError(2, f"network error on {url}: {exc}") from exc

    result = None
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


def _initialize(url: str, timeout: float) -> str | None:
    resp, sid = _post(url, None, _INIT_PAYLOAD, timeout)
    if not resp or "result" not in resp:
        raise SmokeError(1, f"initialize failed on {url}: {resp!r}")
    _post(url, sid, _INITIALIZED_NOTIF, timeout)
    return sid


def _tools_list(url: str, sid: str | None, timeout: float) -> set[str]:
    resp, _ = _post(url, sid, _TOOLS_LIST_PAYLOAD, timeout)
    if not resp or "result" not in resp:
        raise SmokeError(1, f"tools/list failed on {url}: {resp!r}")
    tools = resp["result"].get("tools") or []
    return {t["name"] for t in tools}


def _get_status(url: str, sid: str | None, timeout: float) -> dict[str, Any]:
    resp, _ = _post(url, sid, _GET_STATUS_PAYLOAD, timeout)
    if not resp or "result" not in resp:
        raise SmokeError(1, f"get_status failed on {url}: {resp!r}")
    content = resp["result"].get("content") or []
    for item in content:
        if item.get("type") == "text":
            try:
                return json.loads(item["text"])
            except (json.JSONDecodeError, KeyError):
                return {"raw": item["text"]}
    raise SmokeError(1, f"get_status returned no text content on {url}")


def probe_url(url: str, timeout: float, label: str) -> tuple[set[str], dict[str, Any]]:
    print(f"[smoke] probing {label}: {url}")
    try:
        probe_result(url, timeout)
    except CanaryError as exc:
        raise SmokeError(exc.code, f"{label} canary failed: {exc.msg}") from exc
    sid = _initialize(url, timeout)
    tools = _tools_list(url, sid, timeout)
    status = _get_status(url, sid, timeout)
    print(f"[smoke] {label}: {len(tools)} tools, get_status OK")
    return tools, status


def assert_parity(
    canonical_tools: set[str],
    tunnel_tools: set[str],
    canonical_status: dict,
    tunnel_status: dict,
) -> None:
    errors = []

    only_canonical = canonical_tools - tunnel_tools
    only_tunnel = tunnel_tools - canonical_tools
    if only_canonical:
        errors.append(f"tools only in canonical: {sorted(only_canonical)}")
    if only_tunnel:
        errors.append(f"tools only in tunnel: {sorted(only_tunnel)}")

    canonical_keys = set(canonical_status.keys()) if isinstance(canonical_status, dict) else set()
    tunnel_keys = set(tunnel_status.keys()) if isinstance(tunnel_status, dict) else set()
    key_diff = canonical_keys.symmetric_difference(tunnel_keys)
    if key_diff:
        errors.append(f"get_status top-level key mismatch: {sorted(key_diff)}")

    if errors:
        raise SmokeError(3, "parity failure:\n  " + "\n  ".join(errors))


def run(
    canonical: str,
    tunnel: str,
    timeout: float,
    *,
    llm_check_fn=None,  # injection seam: (url, timeout) -> dict; raises VerifyError on fail
) -> int:
    try:
        canonical_tools, canonical_status = probe_url(canonical, timeout, "canonical")
        tunnel_tools, tunnel_status = probe_url(tunnel, timeout, "tunnel")
        assert_parity(canonical_tools, tunnel_tools, canonical_status, tunnel_status)
    except SmokeError as exc:
        print(f"[smoke] FAIL (exit {exc.code}): {exc.msg}", file=sys.stderr)
        return exc.code

    print(
        f"[smoke] PASS — {len(canonical_tools)} tools in parity, "
        f"get_status structure matches"
    )

    # LLM-binding gate (HD-3): smoke fails if canonical daemon has no LLM bound.
    _llm_check = llm_check_fn or check_llm_binding
    try:
        _llm_check(canonical, timeout)
        print("[smoke] LLM binding check PASS")
    except VerifyError as exc:
        print(f"[smoke] LLM binding FAIL (exit {exc.code}): {exc.msg}", file=sys.stderr)
        return exc.code

    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Self-host migration smoke test (Row F).")
    ap.add_argument("--canonical", default=CANONICAL_URL, help="User-facing canonical URL")
    ap.add_argument("--tunnel", default=TUNNEL_URL, help="Direct tunnel URL")
    ap.add_argument(
        "--timeout", type=float, default=DEFAULT_TIMEOUT,
        help=f"Per-request timeout seconds (default {DEFAULT_TIMEOUT})"
    )
    args = ap.parse_args(argv)
    return run(args.canonical, args.tunnel, args.timeout)


if __name__ == "__main__":
    sys.exit(main())
