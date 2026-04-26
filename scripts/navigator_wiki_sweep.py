"""Navigator wiki sweep helper — single-process MCP session for wiki enumeration.

Closes the navigator's wiki-sweep cadence gap: the standing 30-min cadence
requires enumerating the wiki via ``wiki action=list``, but the MCP HTTP
transport requires a stateful session (initialize → notifications/initialized
→ tools/call) that doesn't survive across separate curl invocations.

This script does the full session in one process: initialize → initialized
notif → tools/call wiki action=list → diff against the navigator's cursor file
→ emit JSON to stdout. Optional ``--update-cursor`` flag commits the new
cursor; default is dry-run.

Usage
-----
    python scripts/navigator_wiki_sweep.py
        Reads cursor; emits diff JSON to stdout; cursor unchanged.

    python scripts/navigator_wiki_sweep.py --update-cursor
        Same, but writes the new cursor on success.

    python scripts/navigator_wiki_sweep.py --url http://127.0.0.1:8001/mcp
        Probe a non-default endpoint (default is the public canonical).

Cursor file
-----------
``.claude/agent-memory/navigator/wiki_sweep_cursor.md`` is markdown with
embedded YAML frontmatter. This script reads only the page-list section
(``## Promoted pages — pages/<category>/`` tables) and the
``last_sweep:`` field, treating them as the canonical state. The diff
walks the live wiki list against the cursor's recorded set and emits
new / modified / deleted page rows.

Stdlib only.

Exit codes
----------
0  — sweep completed; diff emitted (may be empty if no delta).
2  — MCP handshake failed (initialize / session).
3  — wiki tool call failed (no result / isError).
4  — cursor file unreadable or malformed.
5  — unexpected error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_URL = "https://tinyassets.io/mcp"
DEFAULT_TIMEOUT = 30.0

_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CURSOR_PATH = (
    _REPO_ROOT / ".claude" / "agent-memory" / "navigator" / "wiki_sweep_cursor.md"
)

_INIT_PAYLOAD = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "navigator-wiki-sweep", "version": "1.0"},
    },
}
_INITIALIZED_NOTIF = {"jsonrpc": "2.0", "method": "notifications/initialized"}


class SweepError(Exception):
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
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": "workflow-navigator-wiki-sweep/1.0",
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
        raise SweepError(
            step_code,
            f"HTTP {exc.code} on {payload.get('method','?')}: {exc.reason}",
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SweepError(
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


def fetch_wiki_list(url: str, timeout: float) -> list[dict[str, Any]]:
    """Run handshake + tools/call wiki action=list. Returns list of page dicts."""
    resp, sid = _post(url, None, _INIT_PAYLOAD, timeout, step_code=2)
    if resp is None or "result" not in resp:
        raise SweepError(2, f"initialize returned no result: {resp!r}")
    if "error" in resp:
        raise SweepError(2, f"initialize returned MCP error: {resp['error']!r}")
    if not sid:
        raise SweepError(2, "initialize response did not include mcp-session-id header")

    # notifications/initialized — POST with no expected response body.
    _post(url, sid, _INITIALIZED_NOTIF, timeout, step_code=2)

    # tools/call wiki action=list.
    call_payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "wiki", "arguments": {"action": "list"}},
    }
    resp, _ = _post(url, sid, call_payload, timeout, step_code=3)
    if resp is None or "result" not in resp:
        raise SweepError(3, f"tools/call wiki action=list returned no result: {resp!r}")
    result = resp["result"]
    if result.get("isError"):
        raise SweepError(
            3,
            f"tools/call wiki action=list returned isError: {_extract_tool_text(result)}",
        )

    text = _extract_tool_text(result)
    structured = result.get("structuredContent") or {}
    # Wiki action=list returns structuredContent.result with .promoted + .drafts arrays
    # AND a JSON-string text channel with the same shape. Parse whichever is available.
    payload = structured.get("result") or structured
    if isinstance(payload, dict) and ("promoted" in payload or "drafts" in payload):
        return list(payload.get("promoted") or []) + list(payload.get("drafts") or [])
    if "pages" in structured:
        return list(structured["pages"])
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return (
                list(parsed.get("promoted") or [])
                + list(parsed.get("drafts") or [])
                + list(parsed.get("pages") or [])
            )
    except (json.JSONDecodeError, AttributeError):
        pass
    raise SweepError(
        3,
        f"could not parse pages list from wiki response: "
        f"structured_keys={list(structured.keys())} text_first_200={text[:200]!r}",
    )


_PAGE_ROW_RE = re.compile(r"^\|\s*(?P<path>(?:pages|drafts)/[^|]+\.md)\s*\|", re.MULTILINE)


def parse_cursor_pages(cursor_text: str) -> set[str]:
    """Extract the set of page paths the cursor records as known."""
    return {m.group("path").strip() for m in _PAGE_ROW_RE.finditer(cursor_text)}


def parse_cursor_last_sweep(cursor_text: str) -> str | None:
    m = re.search(r"^last_sweep:\s*(?P<ts>\S+)", cursor_text, re.MULTILINE)
    return m.group("ts") if m else None


def diff(live_pages: list[dict[str, Any]], cursor_paths: set[str]) -> dict[str, Any]:
    """Compute the page-set delta. Returns dict with added/missing/all."""
    live_paths = {p.get("path", "") for p in live_pages if p.get("path")}
    added = sorted(live_paths - cursor_paths)
    missing = sorted(cursor_paths - live_paths)
    return {
        "live_count": len(live_paths),
        "cursor_count": len(cursor_paths),
        "added": added,
        "missing": missing,
    }


_TABLE_RE = re.compile(
    r"(?P<header>^## (?P<title>Promoted pages — pages/[^\n]+|Draft pages)\s*\n\n"
    r"(?P<colhdr>\| Page path \|[^\n]*)\n"
    r"(?P<divider>\|[-|\s]+\|)\n)"
    r"(?P<rows>(?:\|[^\n]*\n)*)",
    re.MULTILINE,
)


def _parse_existing_rows(rows_block: str) -> dict[str, list[str]]:
    """path → list of trailing column cells (preserves historical metadata)."""
    out: dict[str, list[str]] = {}
    for line in rows_block.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells or not cells[0].endswith(".md"):
            continue
        out[cells[0]] = cells[1:]
    return out


def _regen_table(
    title: str,
    header_block: str,
    existing_rows: dict[str, list[str]],
    live_paths: list[str],
    col_count: int,
) -> str:
    """Rebuild a single section's table preserving historical cells."""
    body_lines = [header_block.rstrip()]
    for path in sorted(live_paths):
        prior = existing_rows.get(path)
        if prior is not None and len(prior) >= col_count:
            cells = prior[:col_count]
        else:
            cells = ["unknown"] * col_count
        body_lines.append("| " + path + " | " + " | ".join(cells) + " |")
    return "\n".join(body_lines) + "\n"


def update_cursor(cursor_path: Path, cursor_text: str, live_pages: list[dict[str, Any]]) -> str:
    """Refresh cursor: bump last_sweep + regenerate page-path tables.

    Tables that match `## Promoted pages — pages/<category>/` or `## Draft pages`
    are rebuilt from live_pages. Existing rows' trailing cells (created /
    updated / status) are preserved verbatim where the path is unchanged.
    New paths get 'unknown' filler. Missing paths drop out.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if re.search(r"^last_sweep:", cursor_text, re.MULTILINE):
        cursor_text = re.sub(
            r"^last_sweep:\s*\S+", f"last_sweep: {now}",
            cursor_text, count=1, flags=re.MULTILINE,
        )
    else:
        cursor_text = cursor_text.replace("---\n", f"---\nlast_sweep: {now}\n", 1)

    # Group live pages by category.
    by_category: dict[str, list[str]] = {}
    drafts: list[str] = []
    for page in live_pages:
        path = page.get("path", "")
        if not path:
            continue
        if path.startswith("drafts/"):
            drafts.append(path)
        elif path.startswith("pages/"):
            # Category is the second segment: pages/<cat>/...
            parts = path.split("/", 2)
            if len(parts) >= 3:
                cat = parts[1]
                by_category.setdefault(cat, []).append(path)

    def replace_table(match: "re.Match[str]") -> str:
        title = match.group("title")
        header = match.group("header")
        colhdr = match.group("colhdr")
        existing = _parse_existing_rows(match.group("rows"))
        # Column count = number of header cells minus 1 (Page path itself).
        # `colhdr` is `| Page path | id | ... | status |` — split on `|` excluding empties.
        header_cells = [c.strip() for c in colhdr.strip("|").split("|") if c.strip()]
        col_count = max(0, len(header_cells) - 1)

        if title == "Draft pages":
            paths = drafts
        else:
            # Title looks like "Promoted pages — pages/bugs/" — extract category.
            cat_match = re.search(r"pages/([^/\s]+)/", title)
            if not cat_match:
                return match.group(0)
            cat = cat_match.group(1)
            paths = by_category.get(cat, [])

        return _regen_table(title, header, existing, paths, col_count)

    return _TABLE_RE.sub(replace_table, cursor_text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Navigator wiki sweep helper")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"MCP endpoint (default: {DEFAULT_URL})")
    parser.add_argument(
        "--timeout", type=float, default=DEFAULT_TIMEOUT,
        help="HTTP timeout seconds",
    )
    parser.add_argument("--cursor", default=str(DEFAULT_CURSOR_PATH), help="Cursor file path")
    parser.add_argument(
        "--update-cursor", action="store_true",
        help="Write last_sweep timestamp on success",
    )
    args = parser.parse_args(argv)

    cursor_path = Path(args.cursor)
    try:
        cursor_text = cursor_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(json.dumps({"error": f"cursor unreadable: {exc}"}), file=sys.stderr)
        return 4

    cursor_paths = parse_cursor_pages(cursor_text)
    last_sweep = parse_cursor_last_sweep(cursor_text)

    try:
        live_pages = fetch_wiki_list(args.url, args.timeout)
    except SweepError as exc:
        print(json.dumps({"error": exc.msg, "exit_code": exc.code}), file=sys.stderr)
        return exc.code

    delta = diff(live_pages, cursor_paths)
    delta["last_sweep_recorded"] = last_sweep
    delta["sweep_url"] = args.url

    print(json.dumps(delta, indent=2))

    if args.update_cursor:
        new_text = update_cursor(cursor_path, cursor_text, live_pages)
        try:
            cursor_path.write_text(new_text, encoding="utf-8")
        except OSError as exc:
            print(json.dumps({"warning": f"cursor write failed: {exc}"}), file=sys.stderr)
            return 5

    return 0


if __name__ == "__main__":
    sys.exit(main())
