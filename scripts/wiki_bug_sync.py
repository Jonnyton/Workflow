"""Wiki bug sync — polls wiki for BUG-NNN entries and creates GitHub Issues.

Fetches the wiki page list via the canonical MCP endpoint, finds all bug
entries newer than the last-seen cursor, and opens a GitHub Issue for each
new bug using the built-in GITHUB_TOKEN.

Cursor state lives in `.agents/.wiki_bug_sync_cursor` (a single line: last
synced BUG number as an integer, e.g. ``3``).  The file is committed to the
repo so GHA runners start from a known state and the pipeline stays
idempotent across re-runs.

Exit codes
----------
0   All new bugs synced (or no new bugs found).
1   MCP protocol / response-shape error.
2   MCP network error.
3   GitHub API error.

Usage
-----
    python scripts/wiki_bug_sync.py
    python scripts/wiki_bug_sync.py --url https://tinyassets.io/mcp
    python scripts/wiki_bug_sync.py --dry-run

Stdlib only — no third-party deps.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_URL = "https://tinyassets.io/mcp"
DEFAULT_TIMEOUT = 20.0
GITHUB_API = "https://api.github.com"
GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", "Jonnyton/Workflow")

_REPO_ROOT = Path(__file__).resolve().parent.parent
CURSOR_PATH = _REPO_ROOT / ".agents" / ".wiki_bug_sync_cursor"

_SEVERITY_LABELS: dict[str, str] = {
    "low": "severity:low",
    "medium": "severity:medium",
    "high": "severity:high",
    "blocker": "severity:blocker",
}
_AUTO_LABEL = "auto-bug"

_BUG_ID_RE = re.compile(r"BUG-(\d+)", re.IGNORECASE)

_INIT_PAYLOAD = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "wiki-bug-sync", "version": "1.0"},
    },
}
_INITIALIZED_NOTIF = {"jsonrpc": "2.0", "method": "notifications/initialized"}


class SyncError(Exception):
    def __init__(self, code: int, msg: str) -> None:
        super().__init__(msg)
        self.code = code
        self.msg = msg


# ---------------------------------------------------------------------------
# MCP transport helpers
# ---------------------------------------------------------------------------


def _mcp_post(
    url: str,
    sid: str | None,
    payload: dict[str, Any],
    timeout: float,
) -> tuple[dict | None, str | None]:
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": "workflow-wiki-bug-sync/1.0",
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
        raise SyncError(2, f"network error on {url}: {exc}") from exc

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


def _mcp_initialize(
    url: str,
    timeout: float,
    post_fn=None,
) -> str | None:
    _post = post_fn or _mcp_post
    resp, sid = _post(url, None, _INIT_PAYLOAD, timeout)
    if not resp or "result" not in resp:
        raise SyncError(1, f"MCP initialize failed: {resp!r}")
    _post(url, sid, _INITIALIZED_NOTIF, timeout)
    return sid


def _mcp_call_tool(
    url: str,
    sid: str | None,
    tool: str,
    args: dict[str, Any],
    timeout: float,
    post_fn=None,
) -> dict[str, Any]:
    _post = post_fn or _mcp_post
    payload = {
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tools/call",
        "params": {"name": tool, "arguments": args},
    }
    resp, _ = _post(url, sid, payload, timeout)
    if resp is None or "result" not in resp:
        raise SyncError(1, f"tools/call {tool!r} got no result: {resp!r}")
    if resp["result"].get("isError"):
        content = resp["result"].get("content", [])
        text = next((c["text"] for c in content if c.get("type") == "text"), "")
        raise SyncError(1, f"tools/call {tool!r} returned isError: {text[:300]}")
    return resp["result"]


def _parse_text_result(result: dict[str, Any]) -> str:
    for item in result.get("content", []):
        if item.get("type") == "text":
            return item["text"]
    raise SyncError(1, "tool returned no text content")


# ---------------------------------------------------------------------------
# Cursor
# ---------------------------------------------------------------------------


def read_cursor(cursor_path: Path = CURSOR_PATH) -> int:
    """Return last-synced BUG number (0 = never synced)."""
    try:
        return int(cursor_path.read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError):
        return 0


def write_cursor(num: int, cursor_path: Path = CURSOR_PATH) -> None:
    cursor_path.parent.mkdir(parents=True, exist_ok=True)
    cursor_path.write_text(str(num), encoding="utf-8")


# ---------------------------------------------------------------------------
# Bug-page discovery
# ---------------------------------------------------------------------------


def _bug_number(path: str) -> int | None:
    """Extract integer bug number from a wiki path like 'bugs/BUG-003-...'."""
    m = _BUG_ID_RE.search(path)
    return int(m.group(1)) if m else None


def list_new_bugs(
    wiki_list: dict[str, Any],
    cursor: int,
) -> list[dict[str, Any]]:
    """Return promoted bug entries with bug_number > cursor, sorted ascending."""
    bugs = []
    for entry in wiki_list.get("promoted", []):
        if entry.get("type") != "bug":
            continue
        num = _bug_number(entry.get("path", ""))
        if num is None or num <= cursor:
            continue
        bugs.append({**entry, "bug_number": num})
    bugs.sort(key=lambda e: e["bug_number"])
    return bugs


# ---------------------------------------------------------------------------
# Wiki read for bug detail
# ---------------------------------------------------------------------------


def fetch_bug_detail(
    url: str,
    sid: str | None,
    path: str,
    timeout: float,
    post_fn=None,
) -> dict[str, Any]:
    """Call wiki action=read and parse the frontmatter fields we need."""
    result = _mcp_call_tool(
        url, sid, "wiki", {"action": "read", "path": path}, timeout, post_fn
    )
    text = _parse_text_result(result)
    try:
        data = json.loads(text)
        content = data.get("content", "")
    except (json.JSONDecodeError, AttributeError):
        content = text

    # Parse frontmatter from the markdown content
    meta: dict[str, str] = {}
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    meta[k.strip()] = v.strip()
    return meta


# ---------------------------------------------------------------------------
# GitHub Issue creation
# ---------------------------------------------------------------------------


def _gh_ensure_label(
    token: str,
    repo: str,
    label: str,
    color: str = "e4e669",
    gh_api: str = GITHUB_API,
    timeout: float = 20.0,
) -> None:
    """Create the label if it doesn't exist yet. Best-effort."""
    url = f"{gh_api}/repos/{repo}/labels"
    body = json.dumps({"name": label, "color": color}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "workflow-wiki-bug-sync/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout):
            pass
    except urllib.error.HTTPError as exc:
        if exc.code == 422:
            pass  # label already exists
    except (urllib.error.URLError, OSError):
        pass  # best-effort


def create_gh_issue(
    token: str,
    repo: str,
    bug_id: str,
    title: str,
    severity: str,
    component: str,
    body_md: str,
    dry_run: bool = False,
    gh_api: str = GITHUB_API,
    timeout: float = 20.0,
) -> str:
    """Create a GitHub Issue; returns the issue URL or '[dry-run]'."""
    labels = [_AUTO_LABEL]
    sev_label = _SEVERITY_LABELS.get(severity.lower())
    if sev_label:
        labels.append(sev_label)

    title_str = f"[{bug_id}] {title}"
    issue_body = (
        f"**Component:** {component}\n"
        f"**Severity:** {severity}\n\n"
        f"{body_md}\n\n"
        f"_Auto-filed by wiki-bug-sync from wiki entry `{bug_id}`._"
    )

    if dry_run:
        print(f"[wiki-bug-sync] DRY-RUN: would create issue {title_str!r} labels={labels}")
        return "[dry-run]"

    if not token:
        raise SyncError(3, "GITHUB_TOKEN is not set — cannot create GH Issues")

    # Ensure labels exist
    for label in labels:
        color = "d93f0b" if "severity" in label else "0075ca"
        _gh_ensure_label(token, repo, label, color=color, gh_api=gh_api, timeout=timeout)

    url = f"{gh_api}/repos/{repo}/issues"
    payload = json.dumps({"title": title_str, "body": issue_body, "labels": labels}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "workflow-wiki-bug-sync/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            return data.get("html_url", "(no url)")
    except urllib.error.HTTPError as exc:
        body_err = exc.read().decode("utf-8", errors="replace")[:300]
        raise SyncError(3, f"GitHub API error {exc.code}: {body_err}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise SyncError(3, f"GitHub network error: {exc}") from exc


# ---------------------------------------------------------------------------
# Main sync logic
# ---------------------------------------------------------------------------


def sync(
    url: str,
    timeout: float,
    dry_run: bool = False,
    token: str | None = None,
    repo: str = GITHUB_REPO,
    cursor_path: Path = CURSOR_PATH,
    post_fn=None,
) -> int:
    """Run one sync pass. Returns exit code."""
    _token = token or os.environ.get("GITHUB_TOKEN", "")

    try:
        sid = _mcp_initialize(url, timeout, post_fn)

        # Fetch wiki list
        list_result = _mcp_call_tool(url, sid, "wiki", {"action": "list"}, timeout, post_fn)
        wiki_list = json.loads(_parse_text_result(list_result))

        cursor = read_cursor(cursor_path)
        new_bugs = list_new_bugs(wiki_list, cursor)

        if not new_bugs:
            print(f"[wiki-bug-sync] No new bugs (cursor={cursor})")
            return 0

        print(f"[wiki-bug-sync] {len(new_bugs)} new bug(s) since BUG-{cursor:03d}")

        max_synced = cursor
        for entry in new_bugs:
            bug_num = entry["bug_number"]
            path = entry["path"]
            bug_id = f"BUG-{bug_num:03d}"

            # Fetch detail for richer issue body
            try:
                meta = fetch_bug_detail(url, sid, path, timeout, post_fn)
            except SyncError:
                meta = {}

            title = meta.get("title") or entry.get("title") or bug_id
            severity = meta.get("severity", "medium")
            component = meta.get("component", "unknown")
            body_md = f"**Wiki path:** `{path}`"

            issue_url = create_gh_issue(
                _token, repo, bug_id, title, severity, component, body_md,
                dry_run=dry_run, timeout=timeout,
            )
            print(f"[wiki-bug-sync] {bug_id} → {issue_url}")
            max_synced = max(max_synced, bug_num)

        if not dry_run:
            write_cursor(max_synced, cursor_path)
            print(f"[wiki-bug-sync] cursor updated to {max_synced}")

        return 0

    except SyncError as exc:
        print(f"[wiki-bug-sync] FAIL (exit {exc.code}): {exc.msg}", file=sys.stderr)
        return exc.code


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Sync wiki BUG-NNN entries to GitHub Issues."
    )
    ap.add_argument("--url", default=DEFAULT_URL, help=f"MCP endpoint (default: {DEFAULT_URL})")
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                    help=f"Per-request timeout (default {DEFAULT_TIMEOUT}s)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print what would be created without touching GH or cursor")
    ap.add_argument("--repo", default=GITHUB_REPO, help=f"owner/repo (default: {GITHUB_REPO})")
    args = ap.parse_args(argv)
    return sync(args.url, args.timeout, dry_run=args.dry_run, repo=args.repo)


if __name__ == "__main__":
    sys.exit(main())
