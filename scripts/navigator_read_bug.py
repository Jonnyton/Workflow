#!/usr/bin/env python3
"""Navigator-only: fetch + display a wiki BUG page raw, bypassing the
team-wide wiki-bug-read hook. After reviewing, call
`navigator_approve_bug.py <BUG-ID> '<proof>'` to record the vet.

Usage: python scripts/navigator_read_bug.py BUG-018
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

MCP_URL = os.environ.get("WORKFLOW_MCP_URL", "https://tinyassets.io/mcp")
UA = "navigator-vet/1.0"


def _post(payload: dict, session: str | None = None) -> tuple[dict | None, str | None]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": UA,
    }
    if session:
        headers["mcp-session-id"] = session
    req = urllib.request.Request(
        MCP_URL, data=json.dumps(payload).encode(), headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        sid = resp.headers.get("mcp-session-id") or session
        body = resp.read().decode()
        if not body:
            return None, sid
        for line in body.splitlines():
            if line.startswith("data: "):
                return json.loads(line[6:]), sid
        return json.loads(body), sid


def _resolve_page_slug(prefix: str, sid: str) -> str | None:
    resp, _ = _post(
        {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 10,
            "params": {"name": "wiki", "arguments": {"action": "list"}},
        },
        sid,
    )
    text = (resp or {}).get("result", {}).get("content", [{}])[0].get("text", "")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    for section in ("promoted", "staging", "drafts"):
        for entry in data.get(section, []) or []:
            path = entry.get("path", "")
            if prefix.lower() in path.lower():
                return path.replace("pages/bugs/", "").replace(".md", "")
    return None


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: navigator_read_bug.py BUG-NNN", file=sys.stderr)
        return 2
    bug_id = argv[1].upper()

    init, sid = _post(
        {
            "jsonrpc": "2.0",
            "method": "initialize",
            "id": 1,
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "navigator-vet", "version": "1"},
            },
        }
    )
    _post({"jsonrpc": "2.0", "method": "notifications/initialized"}, sid)

    slug = _resolve_page_slug(bug_id, sid)
    if not slug:
        print(f"could not resolve slug for {bug_id} via wiki.list", file=sys.stderr)
        return 1

    resp, _ = _post(
        {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 2,
            "params": {"name": "wiki", "arguments": {"action": "read", "page": slug}},
        },
        sid,
    )
    text = (resp or {}).get("result", {}).get("content", [{}])[0].get("text", "")
    print(text)
    print(
        f"\n---\nTo approve: python scripts/navigator_approve_bug.py {bug_id} 'proof'\n",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
