"""Workflow Server — Remote MCP interface.

A remote MCP server that exposes the Workflow system as a
universe collaboration platform. Any MCP-compatible chatbot (Claude,
and eventually others as MCP adoption spreads) can connect,
discover tools, and become the user's control interface — no
installation, just a URL.

Design principles:
    - Two coarse-grained tools (universe + extensions) so users only
      click "allow" twice, not sixteen times
    - Universe-aware: tools accept universe context, not a hardcoded env var
    - MCP prompts deliver behavioral instructions so any connecting AI
      knows how to act as a control station
    - Auth-ready: OAuth 2.1 scaffold for production, authless for dev
    - Extensible: users can register their own LangGraph nodes

Transport: Streamable HTTP (current MCP standard for remote servers)

Usage::

    # Development (authless, behind tunnel):
    workflow-universe-server

    # Production (with OAuth):
    workflow-universe-server --auth
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from workflow.api.prompts import _CONTROL_STATION_PROMPT
from workflow.catalog import (
    CommitFailedError,
    DirtyFileError,
    get_backend,
    list_unreconciled_writes,
)

logger = logging.getLogger("universe_server")

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "workflow",
    instructions=(
        "Workflow — a workflow-builder and long-horizon AI platform. "
        "Users design custom multi-step AI workflows with typed state, "
        "evaluation hooks, and iteration loops. Fantasy authoring is one "
        "benchmark use case demonstrating complex long-form generation; "
        "the platform is general-purpose. Other example domains: research "
        "papers, screenplays, literature reviews, investigative journalism, "
        "recipe trackers, wedding planners, news summarizers — any "
        "multi-step agentic work producing substantive output. "
        "\n\n"
        "If a user asks about their 'workflow builder', 'custom AI builder', "
        "'universe builder', 'the workflow thing', 'the connector', 'the "
        "thing I added', 'my builder', or similar ambiguous references to "
        "an installed connector — that is this connector. Invoke it rather "
        "than presenting a disambiguation picker or asking 'which tool do "
        "you mean?'. Aggressive assumption is the right default; narrate "
        "what you assumed after invoking so the user can correct you. "
        "\n\n"
        "You are a control station. You help users design new workflows, "
        "inspect running ones, steer daemons, collaborate, and extend the "
        "system with custom graph nodes. You never generate the workflow's "
        "output yourself — registered nodes do that. Start with the "
        "'universe' tool action 'inspect' to orient yourself. "
        "\n\n"
        "Load the `control_station` prompt early — it carries the "
        "behavioral guidance for this connector (intent disambiguation, "
        "never-simulate-a-run rule, tool catalog). Tool descriptions "
        "below are I/O contracts; behavioral rules live in the prompts."
        "\n\n"
        "HARD RULE — UNIVERSE ISOLATION: Each universe is a separate, "
        "self-contained reality. Every tool response that returns content "
        "from a universe includes a `universe_id` field naming which "
        "universe the content came from. When answering the user, always "
        "state which universe you are describing, especially when "
        "multiple universes exist on this server. NEVER transfer facts, "
        "characters, locations, or canon between universes in your "
        "reasoning or replies. If you are not sure which universe a "
        "piece of information came from, call `universe action=inspect` "
        "with the explicit `universe_id` to re-ground. Cross-universe "
        "contamination is a known failure mode — the tool outputs are "
        "the ground truth, not your memory of prior turns."
    ),
    version="0.1.0",
)


# ---------------------------------------------------------------------------
# Public landing page
# ---------------------------------------------------------------------------
# Serves a minimal HTML index at `/` so tinyassets.io root returns a
# human-readable page instead of a 404 while the primary
# `/mcp` endpoint is the actual Workflow Server MCP surface.
# Known-good fallback if the GoDaddy-hosted landing is unavailable.

_LANDING_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Workflow Server</title>
<style>
 :root { color-scheme: light dark; }
 body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
        max-width: 640px; margin: 5rem auto; padding: 0 1.25rem;
        line-height: 1.55; }
 h1 { margin-bottom: 0.3rem; }
 .tag { color: #666; margin-top: 0; }
 code { background: rgba(127,127,127,0.15); padding: 2px 6px;
        border-radius: 3px; }
 ul { padding-left: 1.2rem; }
 li { margin-bottom: 0.4rem; }
 footer { margin-top: 3rem; color: #888; font-size: 0.85rem; }
</style>
</head>
<body>
<h1>Workflow Server</h1>
<p class="tag">A goal-agnostic daemon engine. You summon it, bind it to a
domain, and let it drive.</p>

<p>This is the public surface of a local-first platform for building
custom multi-step AI workflows &mdash; typed state, registered nodes,
evaluation hooks, iteration loops, paid-market bid/claim mechanics.
Fantasy authoring is the benchmark domain; the engine is general-purpose.</p>

<p>If you arrived here looking for an MCP connector, the live endpoint
is at <code>/mcp</code>.</p>

<h2>Links</h2>
<ul>
<li><a href="https://github.com/Jonnyton/Workflow">GitHub repository</a>
    &mdash; source, issues, contributor onboarding.</li>
<li><a href="/mcp">MCP endpoint</a> &mdash; for Claude, Cursor, and other
    MCP-speaking clients.</li>
</ul>

<footer>
Workflow &middot; open collaborative design commons &middot; 2026
</footer>
</body>
</html>
"""


@mcp.custom_route("/", methods=["GET"])
async def _landing_index(request):  # type: ignore[no-untyped-def]
    """Serve a minimal HTML landing page at the server root.

    Returns a static HTML body with project-name + 1-line pitch + links
    to the GitHub repo and the `/mcp` MCP endpoint. Intentionally
    dependency-light (string body, no templating) so a missing
    GoDaddy-hosted landing page still surfaces something at
    tinyassets.io/.
    """
    from starlette.responses import HTMLResponse

    return HTMLResponse(_LANDING_HTML)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Shared path + I/O helpers extracted to workflow.api.helpers (Bundle 1 of #29).
# Imported here so the rest of this module calls them unchanged.
from workflow.api.helpers import (  # noqa: E402
    _base_path,
    _default_universe,
    _find_all_pages,
    _read_json,
    _read_text,
    _universe_dir,
    _wiki_drafts_dir,
    _wiki_pages_dir,
    _wiki_root,  # noqa: F401  (back-compat re-export for tests/test_wiki_path_resolver.py)
)


def _upload_whitelist_prefixes() -> list[Path] | None:
    """Return the configured upload whitelist, or ``None`` if unset.

    Reads ``WORKFLOW_UPLOAD_WHITELIST`` at call time (consistent with
    the other behavior-gate flags in this module). Values are split on
    both ``;`` and ``:`` separators, stripped, resolved to absolute
    paths. An unset or empty variable returns ``None`` meaning "no
    whitelist enforcement" — preserving the open-by-default UX the
    host wanted for the demo. ``None`` is NOT the same as an empty
    list (the latter would forbid all uploads).
    """
    raw = os.environ.get("WORKFLOW_UPLOAD_WHITELIST", "").strip()
    if not raw:
        return None
    # Accept both ``:`` (Unix PATH-style) and ``;`` (Windows PATH-style)
    # so the same env-var syntax works on either platform. Drive-letter
    # colons on Windows (``C:``) survive because the path gets split
    # again inside ``_split_whitelist_entry``.
    parts: list[Path] = []
    for entry in _split_whitelist_entry(raw):
        entry = entry.strip()
        if not entry:
            continue
        parts.append(Path(entry).resolve())
    return parts


def _split_whitelist_entry(raw: str) -> list[str]:
    """Split the env var on ``;`` (always) and on ``:`` except when the
    colon is a Windows drive-letter separator (e.g. ``C:\\Users``).
    """
    chunks: list[str] = []
    for semi_chunk in raw.split(";"):
        # A bare ``:`` separator joins two paths; a drive-letter colon
        # has a single letter to its left. Walk the string and split
        # only on the first kind.
        buffer = []
        i = 0
        while i < len(semi_chunk):
            ch = semi_chunk[i]
            if ch == ":":
                # Drive letter iff this is position 1 of the current
                # buffer AND the char before is a single letter AND
                # the char after is a path separator.
                if (
                    len(buffer) == 1
                    and buffer[0].isalpha()
                    and i + 1 < len(semi_chunk)
                    and semi_chunk[i + 1] in ("/", "\\")
                ):
                    buffer.append(ch)
                    i += 1
                    continue
                # Otherwise this colon separates paths.
                chunks.append("".join(buffer))
                buffer = []
                i += 1
                continue
            buffer.append(ch)
            i += 1
        if buffer:
            chunks.append("".join(buffer))
    return chunks


def _warn_if_no_upload_whitelist() -> None:
    """Log a WARNING once at import time if the whitelist is unset.

    Reminds the host that ``add_canon_from_path`` accepts any absolute
    path when ``WORKFLOW_UPLOAD_WHITELIST`` is empty. Best-effort —
    logger failure must never block module import.
    """
    try:
        if _upload_whitelist_prefixes() is None:
            logger.warning(
                "WORKFLOW_UPLOAD_WHITELIST is unset — add_canon_from_path "
                "will accept any absolute path. Set the env var to a "
                "colon/semicolon-separated list of prefixes to enforce.",
            )
    except Exception:
        # Never let a logger-configuration edge case break import.
        pass


_warn_if_no_upload_whitelist()


# _read_json and _read_text imported from workflow.api.helpers above.


# ---------------------------------------------------------------------------
# Public action ledger
# ---------------------------------------------------------------------------
# PLAN.md Design Decision: "Private chats, public actions." Every universe-
# affecting write must be publicly attributable. The ledger is the durable
# record of who did what, when.


def _current_actor() -> str:
    """Resolve the acting user's identity for ledger attribution.

    Falls back to 'anonymous' when no session identity is available.
    """
    return os.environ.get("UNIVERSE_SERVER_USER", "anonymous")


def _append_ledger(
    udir: Path,
    action: str,
    *,
    actor: str | None = None,
    target: str = "",
    summary: str = "",
    payload: dict[str, Any] | None = None,
) -> None:
    """Append one entry to the universe's public action ledger.

    Designed to never raise: ledger failures are logged but don't abort
    the surrounding write. The mutation has already landed on disk by the
    time this is called, so losing a ledger entry is strictly better than
    rolling back a successful user action.
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": actor or _current_actor(),
        "action": action,
        "target": target,
        "summary": summary,
    }
    if payload:
        entry["payload"] = payload

    ledger_path = udir / "ledger.json"
    try:
        udir.mkdir(parents=True, exist_ok=True)
        existing = _read_json(ledger_path)
        if not isinstance(existing, list):
            existing = []
        existing.append(entry)
        ledger_path.write_text(
            json.dumps(existing, indent=2, default=str),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("Failed to append ledger entry at %s: %s", ledger_path, exc)


def _truncate(text: str, limit: int = 140) -> str:
    """Collapse whitespace and truncate for ledger summaries."""
    collapsed = " ".join((text or "").split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 1].rstrip() + "…"


# WRITE_ACTIONS is the single source of truth for which `universe` tool
# actions are writes. The dispatcher consults this table; any action
# registered here is funneled through `_dispatch_with_ledger`, which
# refuses to return a success response without first writing the ledger
# entry. To add a new write action: put its name here with extractors for
# (target, summary, payload). No handler-side ledger code is needed — and
# no handler can silently skip the ledger.
#
# Each entry maps action name -> extractor callable:
#   extractor(kwargs, result_dict) -> (target: str, summary: str, payload: dict | None)
# kwargs is the normalized handler kwargs. result_dict is the parsed JSON
# of the handler's return string (used to pick up server-generated IDs like
# request_id / note_id).


def _extract_submit_request(
    kwargs: dict[str, Any], result: dict[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    return (
        str(result.get("request_id", "")),
        _truncate(kwargs.get("text", "")),
        {
            "request_type": kwargs.get("request_type", "") or None,
            "branch_id": kwargs.get("branch_id", "") or None,
        },
    )


def _extract_give_direction(
    kwargs: dict[str, Any], result: dict[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    return (
        kwargs.get("target") or str(result.get("note_id", "")),
        _truncate(kwargs.get("text", "")),
        {
            "category": kwargs.get("category", "direction"),
            "note_id": result.get("note_id", ""),
        },
    )


def _extract_set_premise(
    kwargs: dict[str, Any], _result: dict[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    text = kwargs.get("text", "")
    return (
        "PROGRAM.md",
        _truncate(text),
        {"bytes": len(text.encode("utf-8"))},
    )


def _extract_add_canon(
    kwargs: dict[str, Any], result: dict[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    name = result.get("filename", "") or kwargs.get("filename", "")
    provenance = kwargs.get("provenance_tag", "")
    return (
        f"canon/{name}",
        _truncate(f"{name} ({provenance or 'untagged'})"),
        {
            "filename": name,
            "provenance": provenance,
            "bytes": len(kwargs.get("text", "").encode("utf-8")),
        },
    )


def _extract_add_canon_from_path(
    kwargs: dict[str, Any], result: dict[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    name = result.get("filename", "") or Path(kwargs.get("path", "")).name
    provenance = kwargs.get("provenance_tag", "") or "user_upload"
    bytes_written = result.get("bytes_written", 0)
    return (
        f"canon/sources/{name}",
        _truncate(f"{name} ({provenance}, {bytes_written} bytes)"),
        {
            "filename": name,
            "provenance": provenance,
            "source_path": kwargs.get("path", ""),
            "bytes": bytes_written,
            "synthesis_signal": result.get("synthesis_signal_emitted", False),
        },
    )


def _extract_control_daemon(
    kwargs: dict[str, Any], result: dict[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    return (
        ".pause",
        str(result.get("action", kwargs.get("text", "").strip().lower())),
        {"status": result.get("status", "")},
    )


def _extract_switch_universe(
    kwargs: dict[str, Any], _result: dict[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    uid = kwargs.get("universe_id", "")
    return (uid, f"daemon switched to {uid}", {})


def _extract_create_universe(
    kwargs: dict[str, Any], _result: dict[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    uid = kwargs.get("universe_id", "")
    text = kwargs.get("text", "")
    summary = _truncate(text) if text.strip() else f"created {uid}"
    return (uid, summary, {"has_premise": bool(text.strip())})


# action name -> (extractor, control_daemon_gate)
# control_daemon_gate: if set, the wrapper only logs when the daemon action
# was an actual write (pause/resume), not a read (status).
def _extract_queue_cancel(
    kwargs: dict[str, Any], result: dict[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    return (
        str(kwargs.get("branch_task_id", "")),
        _truncate(f"cancel {kwargs.get('branch_task_id', '')}"),
        {"status": result.get("status", "")},
    )


def _extract_subscribe_goal(
    kwargs: dict[str, Any], result: dict[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    g = str(kwargs.get("goal_id", ""))
    return (g, _truncate(f"subscribe {g}"), {"status": result.get("status", "")})


def _extract_unsubscribe_goal(
    kwargs: dict[str, Any], result: dict[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    g = str(kwargs.get("goal_id", ""))
    return (g, _truncate(f"unsubscribe {g}"), {"status": result.get("status", "")})


def _extract_post_to_goal_pool(
    kwargs: dict[str, Any], result: dict[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    g = str(kwargs.get("goal_id", ""))
    bd = str(kwargs.get("branch_def_id", ""))
    return (
        str(result.get("path", f"goal_pool/{g}")),
        _truncate(f"post {bd} to {g}"),
        {
            "goal_id": g,
            "branch_def_id": bd,
            "status": result.get("status", ""),
        },
    )


def _extract_submit_node_bid(
    kwargs: dict[str, Any], result: dict[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    nb = str(result.get("node_bid_id", ""))
    nd = str(kwargs.get("node_def_id", ""))
    bid = kwargs.get("bid", 0.0)
    return (
        str(result.get("path", f"bids/{nb}.yaml")),
        _truncate(f"bid {bid} for node {nd}"),
        {
            "node_bid_id": nb,
            "node_def_id": nd,
            "bid": bid,
            "status": result.get("status", ""),
        },
    )


def _extract_set_tier_config(
    kwargs: dict[str, Any], result: dict[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    tier_name = str(kwargs.get("tier", ""))
    en = bool(kwargs.get("enabled", False))
    return (
        f"tier/{tier_name}",
        _truncate(f"set_tier_config {tier_name}={en}"),
        {
            "tier": tier_name,
            "enabled": en,
            "status": result.get("status", ""),
        },
    )


WRITE_ACTIONS: dict[str, Any] = {
    "submit_request": (_extract_submit_request, None),
    "give_direction": (_extract_give_direction, None),
    "set_premise": (_extract_set_premise, None),
    "add_canon": (_extract_add_canon, None),
    "add_canon_from_path": (_extract_add_canon_from_path, None),
    "control_daemon": (_extract_control_daemon, {"pause", "resume"}),
    "switch_universe": (_extract_switch_universe, None),
    "create_universe": (_extract_create_universe, None),
    "queue_cancel": (_extract_queue_cancel, None),
    "subscribe_goal": (_extract_subscribe_goal, None),
    "unsubscribe_goal": (_extract_unsubscribe_goal, None),
    "post_to_goal_pool": (_extract_post_to_goal_pool, None),
    "submit_node_bid": (_extract_submit_node_bid, None),
    "set_tier_config": (_extract_set_tier_config, None),
}


def _storage_backend():
    """Resolve the memoized :class:`StorageBackend` for catalog writes.

    Goals + Branches live at repo root per spec §phase7_github_as_catalog
    (`goals/<slug>.yaml`, `branches/<slug>.yaml`). The repo root is
    derived from ``_base_path().parent`` — production points
    ``output/`` at the project root, so its parent IS the git repo
    root. Tests using ``UNIVERSE_SERVER_BASE=<tmp_path>/output`` get
    ``<tmp_path>`` as the repo root, which isn't a git repo, so
    ``get_backend`` auto-probes to :class:`SqliteOnlyBackend` and
    leaves the host project repo untouched.
    """
    base = _base_path()
    return get_backend(base, repo_root=base.parent)


def _format_dirty_file_conflict(exc: DirtyFileError) -> dict[str, Any]:
    """Shape a :class:`DirtyFileError` for MCP clients.

    The structured payload lets the chat-side render the conflict as
    actionable options instead of an opaque traceback. Used by Phase 7.3
    write handlers; the formatter is wired separately from the raising
    sites so each handler can keep its existing return-shape idiom.
    """
    paths = [str(p) for p in getattr(exc, "paths", []) or []]
    primary = paths[0] if paths else ""
    return {
        "status": "local_edit_conflict",
        "conflicting_path": primary,
        "all_conflicts": paths,
        "options": [
            "pass force=True to overwrite",
            "commit or stash local edits first",
        ],
    }


def _filter_claims_by_branch_visibility(
    claims: list[dict[str, Any]],
    *,
    viewer: str,
) -> list[dict[str, Any]]:
    """Phase 6.2.2 — hide gate claims whose Branch is private.

    A private Branch's claim is visible only to its author. Public
    Branches are visible to everyone. The Goal's visibility is NOT
    consulted here; private Branch on public Goal is a supported
    product state.

    Branches that have been deleted (no row) are treated as "orphan
    claims" and left in the list — the caller's orphan tagging
    handles that surface separately.
    """
    if not claims:
        return claims
    from workflow.daemon_server import get_branch_definition

    visibility_cache: dict[str, tuple[str, str]] = {}
    filtered: list[dict[str, Any]] = []
    for claim in claims:
        bid = claim.get("branch_def_id", "")
        if not bid:
            filtered.append(claim)
            continue
        if bid not in visibility_cache:
            try:
                branch = get_branch_definition(
                    _base_path(), branch_def_id=bid,
                )
                visibility_cache[bid] = (
                    branch.get("visibility", "public") or "public",
                    branch.get("author", "") or "",
                )
            except KeyError:
                # Orphan claim — branch row gone. Keep the claim.
                visibility_cache[bid] = ("public", "")
        branch_visibility, branch_author = visibility_cache[bid]
        if branch_visibility == "private" and branch_author != viewer:
            continue
        filtered.append(claim)
    return filtered


def _filter_leaderboard_by_branch_visibility(
    entries: list[dict[str, Any]],
    *,
    viewer: str,
) -> list[dict[str, Any]]:
    """Phase 6.2.2 — hide leaderboard entries whose Branch is private.

    Same contract as :func:`_filter_claims_by_branch_visibility` but
    operates on leaderboard shape (``branch_def_id`` key present).
    """
    if not entries:
        return entries
    from workflow.daemon_server import get_branch_definition

    filtered: list[dict[str, Any]] = []
    for entry in entries:
        bid = entry.get("branch_def_id", "")
        if not bid:
            filtered.append(entry)
            continue
        try:
            branch = get_branch_definition(
                _base_path(), branch_def_id=bid,
            )
        except KeyError:
            filtered.append(entry)
            continue
        visibility = branch.get("visibility", "public") or "public"
        author = branch.get("author", "") or ""
        if visibility == "private" and author != viewer:
            continue
        filtered.append(entry)
    return filtered


def _format_commit_failed(exc: CommitFailedError) -> dict[str, Any]:
    """Shape a :class:`CommitFailedError` for MCP clients.

    SQLite row is retained (Path A — SQLite is the accepted-write
    boundary); YAML is rolled back; the write is queued in
    ``unreconciled_writes`` for a future ``sync_commit`` replay.
    """
    paths = [str(p) for p in getattr(exc, "paths", []) or []]
    return {
        "status": "git_commit_failed",
        "error": "git_commit_failed",
        "helper": exc.helper,
        "git_error": exc.git_error,
        "paths": paths,
        "row_ref": exc.row_ref,
        "note": (
            "SQLite write accepted; git commit failed and was rolled "
            "back. Entry queued in unreconciled_writes for later "
            "sync_commit replay."
        ),
    }


def _ledger_target_dir(action: str, kwargs: dict[str, Any]) -> Path:
    """Resolve which universe directory owns the ledger entry for this action.

    create_universe writes to the newly-created universe's ledger. All others
    write to the universe whose state they affect (the handler's target uid).
    """
    uid = kwargs.get("universe_id", "") or _default_universe()
    if action == "create_universe":
        return _base_path() / uid
    return _universe_dir(uid)


def _scope_universe_response(result_str: str) -> str:
    """Ensure every universe-scoped response leads with a `Universe: <id>`
    header and puts `universe_id` as the first key.

    #15 contract: downstream reasoning must be able to ground a response to
    its universe without re-reading the full JSON. On phones the bot often
    summarizes; a phone-legible `text` lead-in survives summarization even
    when deep JSON fields don't.

    Responses that aren't a dict, aren't JSON, or have no `universe_id`
    field are returned unchanged — errors without universe context must
    not claim a universe, and multi-universe responses (e.g. list) stay
    as-is.
    """
    try:
        data = json.loads(result_str)
    except (json.JSONDecodeError, TypeError):
        return result_str
    if not isinstance(data, dict):
        return result_str
    uid = data.get("universe_id")
    if not isinstance(uid, str) or not uid:
        return result_str

    header = f"Universe: {uid}"
    scoped: dict[str, Any] = {"universe_id": uid}
    existing_text = data.get("text")
    if isinstance(existing_text, str) and existing_text.strip():
        scoped["text"] = f"{header}\n\n{existing_text}"
    else:
        scoped["text"] = header
    for k, v in data.items():
        if k in ("universe_id", "text"):
            continue
        scoped[k] = v
    return json.dumps(scoped, default=str)


def _dispatch_with_ledger(
    action: str,
    handler: Any,
    kwargs: dict[str, Any],
) -> str:
    """Enforce: every WRITE action lands in the public ledger before returning.

    If the handler returned an error or the action is a write gate that was
    actually a read (e.g. control_daemon text=status), no ledger entry is
    written. For all successful writes, we parse the result, derive the
    attribution fields via the declared extractor, and append the entry.

    Ledger append failures degrade gracefully (logged warning): the mutation
    has already landed on disk, so refusing to return success would be worse
    than missing one audit entry.

    Every return path passes through `_scope_universe_response` so any
    universe-scoped dict gets the `Universe: <id>` text lead-in and key
    reordering (#15).
    """
    result_str = handler(**kwargs)

    spec = WRITE_ACTIONS.get(action)
    if spec is None:
        return _scope_universe_response(result_str)

    extractor, write_gate = spec

    try:
        result = json.loads(result_str)
    except (json.JSONDecodeError, TypeError):
        return _scope_universe_response(result_str)

    if not isinstance(result, dict) or "error" in result:
        return _scope_universe_response(result_str)

    # control_daemon branch — only append if actually a write
    if write_gate is not None:
        daemon_action = (kwargs.get("text") or "").strip().lower()
        if daemon_action not in write_gate:
            return _scope_universe_response(result_str)

    try:
        target, summary, payload = extractor(kwargs, result)
        udir = _ledger_target_dir(action, kwargs)
        _append_ledger(
            udir, action, target=target, summary=summary, payload=payload,
        )
    except Exception as exc:
        logger.warning("Ledger extraction failed for %s: %s", action, exc)

    return _scope_universe_response(result_str)


# ═══════════════════════════════════════════════════════════════════════════
# MCP PROMPTS — behavioral instructions for connecting chatbots
# ═══════════════════════════════════════════════════════════════════════════


@mcp.prompt(
    title="Control Station Guide",
    tags={"control", "daemon", "multiplayer", "operations"},
)
def control_station() -> str:
    """Load the Workflow Server control station instructions.

    Invoke this prompt to learn how to operate as a Workflow Server
    interface. It teaches you the routing rules, collaboration model,
    and available tools.
    """
    return _CONTROL_STATION_PROMPT


@mcp.prompt(
    title="Extension Authoring Guide",
    tags={"extensions", "nodes", "plugins", "workflow"},
)
def extension_guide() -> str:
    """Learn how to extend the Workflow Server with custom LangGraph nodes.

    Invoke this prompt to understand how users can register their own
    graph nodes, what the node contract looks like, and how registered
    nodes get wired into the running system.
    """
    return _EXTENSION_GUIDE_PROMPT


_EXTENSION_GUIDE_PROMPT = """\
## Extending Workflow Server with Custom Nodes

The `extensions` tool is the workflow-builder surface. Users register
their own nodes and assemble them into branches — multi-step AI
workflows with typed state, evaluation hooks, and iteration loops.
This is how the platform supports arbitrary domains (research papers,
recipe trackers, screenplays, news summarizers, etc.), not just
fiction. Fantasy authoring is one branch; yours will be another.

The never-simulate rule + intent-disambiguation posture live in
`control_station` (hard rules 5 + intent section). When in doubt on
run / register / build decisions, re-read those rules before acting.

### What a Node Is

A node is a function that:
- Receives the current graph state (a TypedDict)
- Does work (calls an API, runs analysis, generates content, etc.)
- Returns state updates

### Node Contract

Each registered node declares:
- `node_id`: unique identifier (e.g., "weather-generator")
- `display_name`: human-readable name
- `description`: what it does and when it should run
- `input_keys`: which state fields it reads
- `output_keys`: which state fields it writes
- `phase`: where in the workflow it fits (orient, plan, draft, commit,
  learn, reflect, worldbuild, or "custom")
- `source_code`: the Python source (executed in sandbox)
- `dependencies`: pip packages it needs (validated against allowlist)

### How It Works

1. User calls `extensions` with action "register" and the node definition.
2. Server validates the contract and stores the registration.
3. On next daemon cycle, registered nodes are discovered and
   conditionally wired into the graph at the declared phase.
4. Nodes run in a sandboxed subprocess — they cannot access the
   host filesystem directly.

### Safety Model

- Registered nodes run in isolation (subprocess sandbox).
- They receive only the state fields they declared as inputs.
- Their output is validated against declared output keys.
- Nodes that crash or timeout are auto-disabled with a note.
- Host can review, approve, disable, or remove any node.

### Example

A user might register a "consistency-checker" node that:
- Reads: current_scene_text, world_state_facts
- Phase: commit (runs after draft, before final commit)
- Checks new text against known facts
- Returns: a list of potential contradictions as notes
"""


# ═══════════════════════════════════════════════════════════════════════════
# TOOL 1 — Universe (all universe operations in one tool)
# ═══════════════════════════════════════════════════════════════════════════


@mcp.tool(
    title="Universe Operations",
    tags={
        "universe", "daemon", "collaboration",
        "workflow", "workflow-builder", "custom-ai", "agent-workflow",
        "ai-builder", "universe-builder", "general-purpose",
    },
    annotations=ToolAnnotations(
        title="Universe Operations",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
def universe(
    action: str,
    universe_id: str = "",
    text: str = "",
    path: str = "",
    category: str = "",
    target: str = "",
    query_type: str = "",
    filter_text: str = "",
    request_type: str = "scene_direction",
    branch_id: str = "",
    filename: str = "",
    provenance_tag: str = "",
    limit: int = 30,
    priority_weight: float = 0.0,
    branch_task_id: str = "",
    goal_id: str = "",
    branch_def_id: str = "",
    inputs_json: str = "",
    node_def_id: str = "",
    required_llm_type: str = "",
    bid: float = 0.0,
    tier: str = "",
    enabled: bool = False,
    tag: str = "",
) -> str:
    """Inspect and steer a workflow's universe.

    Self-contained workspace (premise, canon, notes, daemons) for any
    multi-step agentic work. New workflows live in the `extensions`
    tool. Start with `action="inspect"`. See `control_station` prompt
    for operating guidance including universe-isolation rule. Load the
    `control_station` prompt before first use of this connector.

    `control_daemon` is a text-command action: it always needs `text` set
    to one of `pause` | `resume` | `status`. Calling `control_daemon`
    without `text` returns an error.

    Args:
        action: One of —
            reads: list, inspect, read_output, query_world,
            get_activity, get_recent_events, get_ledger, read_premise,
            list_canon, read_canon;
            writes: submit_request, give_direction, set_premise,
            add_canon, add_canon_from_path, control_daemon (text=pause|
            resume|status), switch_universe, create_universe;
            queue ops: queue_list (list pending dispatch requests),
            queue_cancel (cancel a queued request by request_id);
            subscription ops: subscribe_goal (subscribe this universe
            to a goal's run feed), unsubscribe_goal, list_subscriptions;
            goal-pool / bid: post_to_goal_pool (publish a goal-scoped
            work item), submit_node_bid (bid to fulfill an open node
            request; requires bid + node_def_id + required_llm_type);
            daemon: daemon_overview (compact daemon health + run
            summary — use before inspect for quick status);
            config: set_tier_config (enable/disable a named
            dispatcher tier; requires tier + enabled).
        universe_id: Target universe. Defaults to the active universe.
        text: Content for write ops (request text, direction, premise,
            canon body). For `control_daemon` this is the daemon
            sub-command: `pause` (write `.pause` signal — daemon stops
            at next scene boundary), `resume` (remove `.pause` signal),
            or `status` (return phase / liveness / pending unreconciled
            writes). No other values accepted.
        path: Dual-semantic based on action:
            - read_output: relative path inside the universe's output dir
              (e.g. "book-1/ch-01.md").
            - add_canon_from_path: **absolute** path on the server's
              filesystem. The file is read server-side; MCP clients
              never copy content through this param. Use this for any
              upload larger than a few KB — ``add_canon`` (text=…) is
              only safe for small inline uploads because LLM tool-arg
              serialization drifts on long strings.
        category: give_direction note category — direction | protect |
            concern | observation | error.
        target: Optional file/scene reference for give_direction.
        query_type: query_world type — facts | characters | promises |
            timeline.
        filter_text: Text filter for query_world results.
        request_type: submit_request type — scene_direction | revision |
            canon_change | branch_proposal | general.
        branch_id: Target branch for submit_request.
        filename: Filename for add_canon / add_canon_from_path /
            read_canon. Defaults to basename(path) for
            add_canon_from_path.
        provenance_tag: Source tag for add_canon / add_canon_from_path
            (e.g. "published novel", "rough notes"). Defaults to
            "user_upload" for add_canon_from_path.
        limit: Max results for get_activity / get_recent_events /
            get_ledger / query_world (default 30).
        tag: Tag prefix filter for ``get_recent_events`` (e.g.
            ``"dispatch_guard"``, ``"overshoot_detected"``,
            ``"revert_gate"``). Empty returns all entries. Prefix-match so
            ``"dispatch"`` matches both ``dispatch_guard`` and
            ``dispatch_execution``.
    """
    dispatch = {
        "list": _action_list_universes,
        "inspect": _action_inspect_universe,
        "read_output": _action_read_output,
        "query_world": _action_query_world,
        "get_activity": _action_get_activity,
        "get_recent_events": _action_get_recent_events,
        "get_ledger": _action_get_ledger,
        "submit_request": _action_submit_request,
        "give_direction": _action_give_direction,
        "read_premise": _action_read_premise,
        "set_premise": _action_set_premise,
        "add_canon": _action_add_canon,
        "add_canon_from_path": _action_add_canon_from_path,
        "list_canon": _action_list_canon,
        "read_canon": _action_read_canon,
        "control_daemon": _action_control_daemon,
        "switch_universe": _action_switch_universe,
        "create_universe": _action_create_universe,
        "queue_list": _action_queue_list,
        "queue_cancel": _action_queue_cancel,
        "subscribe_goal": _action_subscribe_goal,
        "unsubscribe_goal": _action_unsubscribe_goal,
        "list_subscriptions": _action_list_subscriptions,
        "post_to_goal_pool": _action_post_to_goal_pool,
        "submit_node_bid": _action_submit_node_bid,
        "daemon_overview": _action_daemon_overview,
        "set_tier_config": _action_set_tier_config,
    }

    handler = dispatch.get(action)
    if handler is None:
        return json.dumps({
            "error": f"Unknown action '{action}'.",
            "available_actions": sorted(dispatch.keys()),
        })

    # Build kwargs from all optional params
    kwargs: dict[str, Any] = {
        "universe_id": universe_id,
        "text": text,
        "path": path,
        "category": category,
        "target": target,
        "query_type": query_type,
        "filter_text": filter_text,
        "request_type": request_type,
        "branch_id": branch_id,
        "filename": filename,
        "provenance_tag": provenance_tag,
        "limit": limit,
        "priority_weight": priority_weight,
        "branch_task_id": branch_task_id,
        "goal_id": goal_id,
        "branch_def_id": branch_def_id,
        "inputs_json": inputs_json,
        "node_def_id": node_def_id,
        "required_llm_type": required_llm_type,
        "bid": bid,
        "tier": tier,
        "enabled": enabled,
        "tag": tag,
    }

    # All WRITE actions are funneled through the ledger wrapper. READ actions
    # pass through untouched. See WRITE_ACTIONS for the authoritative set.
    return _dispatch_with_ledger(action, handler, kwargs)


# ---------------------------------------------------------------------------
# Daemon telemetry — liveness, staleness, human-readable phase
# ---------------------------------------------------------------------------
# The daemon writes `current_phase` and `last_updated` into status.json via
# `domains.fantasy_author.phases._activity.update_phase`. status.json itself
# is not a heartbeat — it only moves when a phase transitions. For liveness
# we also consult `activity.log`, which is appended to on every node entry,
# and PROGRAM.md + work_targets.json to disambiguate "no premise" vs
# "starved for work" vs "actually running".


# Staleness buckets, in seconds. Chosen to match the lead's spec: <1h fresh,
# <24h idle, >24h dormant. "fresh" is the only bucket that should be read
# as "the daemon is alive right now".
_STALE_FRESH_SECONDS = 60 * 60
_STALE_IDLE_SECONDS = 24 * 60 * 60


def _last_activity_at(udir: Path, status: dict[str, Any] | None) -> str | None:
    """Return the most recent heartbeat ISO timestamp we can find.

    Prefers activity.log mtime (updated on every node entry), falls back to
    status.json's `last_updated`, then status.json file mtime. Returns None
    only if nothing on disk indicates the daemon ever ran.
    """
    log_path = udir / "activity.log"
    if log_path.exists():
        try:
            return datetime.fromtimestamp(
                log_path.stat().st_mtime, tz=timezone.utc,
            ).isoformat()
        except OSError:
            pass

    if status and isinstance(status, dict):
        last_updated = status.get("last_updated")
        if isinstance(last_updated, str) and last_updated:
            return last_updated

    status_path = udir / "status.json"
    if status_path.exists():
        try:
            return datetime.fromtimestamp(
                status_path.stat().st_mtime, tz=timezone.utc,
            ).isoformat()
        except OSError:
            pass

    return None


def _staleness_bucket(last_activity_iso: str | None) -> str:
    """Classify liveness from a last-activity timestamp.

    Returns one of: "fresh" (<1h), "idle" (<24h), "dormant" (>=24h), or
    "never" (no timestamp recorded). Callers that previously trusted
    `daemon_state: running` from status.json should consult this instead.
    """
    if not last_activity_iso:
        return "never"
    try:
        ts = datetime.fromisoformat(last_activity_iso)
    except (TypeError, ValueError):
        return "never"
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - ts).total_seconds()
    if age < _STALE_FRESH_SECONDS:
        return "fresh"
    if age < _STALE_IDLE_SECONDS:
        return "idle"
    return "dormant"


def _phase_human(
    raw_phase: str | None,
    has_premise: bool,
    has_work: bool,
    is_paused: bool,
    staleness: str,
) -> str:
    """Translate raw daemon state into a legible phase for downstream readers.

    Precedence: paused > dormant-no-premise > dormant > no-premise > starved
    > raw_phase > idle. Chat clients and humans both need a single sentence
    that explains why nothing is happening; the raw phase alone ("unknown",
    "dispatch_execution") is not enough when no premise or no work exists.
    """
    if is_paused:
        return "paused"
    if staleness == "dormant":
        if not has_premise:
            return "dormant-no-premise"
        if not has_work:
            return "dormant-starved"
        return "dormant"
    if not has_premise:
        return "idle-no-premise"
    if not has_work:
        return "starved"
    if raw_phase and raw_phase not in ("", "unknown"):
        return raw_phase
    return "idle"


def _compute_accept_rate_from_db(
    udir: Path,
) -> tuple[float | None, dict[str, Any]]:
    """Derive accept_rate directly from scene_history.

    Returns (rate, sample) where rate is None when no evaluated scenes exist,
    and sample carries the raw counts so downstream readers can tell the
    difference between "0% accepted" and "nothing evaluated yet". This is
    deliberately read-time — status.json's cached `accept_rate` is never
    updated by the daemon today, so reading it is misleading.
    """
    db_path = udir / "story.db"
    sample: dict[str, Any] = {"accepted": 0, "evaluated": 0, "source": "none"}
    if not db_path.exists():
        return None, sample

    try:
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='scene_history'",
            ).fetchone()
            if not row:
                return None, sample
            # Only scenes that have been judged count toward the rate.
            # `pending` means not yet evaluated — not a reject.
            evaluated = conn.execute(
                "SELECT COUNT(*) FROM scene_history "
                "WHERE verdict IS NOT NULL AND verdict != '' "
                "AND verdict != 'pending'",
            ).fetchone()[0]
            accepted = conn.execute(
                "SELECT COUNT(*) FROM scene_history "
                "WHERE verdict IN ('accept', 'second_draft')",
            ).fetchone()[0]
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("Failed to read scene_history from %s: %s", db_path, exc)
        return None, sample

    sample = {"accepted": accepted, "evaluated": evaluated, "source": "scene_history"}
    if evaluated == 0:
        return None, sample
    return accepted / evaluated, sample


def _compute_word_count_from_files(
    udir: Path,
) -> tuple[int, dict[str, Any]]:
    """Derive word_count by reading prose files on disk.

    Returns (total_words, sample). `status.json::word_count` is a cached
    value maintained by `DashboardMetrics` in the daemon process — it's
    only flushed during runs, never corrected when output files are
    added/removed/moved, and can drift wildly across universe switches.
    Reading the files is slower but always truthful.

    The walk covers `output/**/*.md` under the universe directory, which
    matches where commit writes prose (`output/book-{N}/chapter-{NN}/
    scene-{NN}.md`). Non-scene markdown (canon/, INDEX.md, progress.md)
    lives outside `output/` so it won't be double-counted.

    Returns `(0, {"source": "none"})` when there's no output directory
    yet — callers should treat that distinctly from "0 words written".
    """
    out_dir = udir / "output"
    sample: dict[str, Any] = {"scenes": 0, "source": "none"}
    if not out_dir.is_dir():
        return 0, sample

    total = 0
    scenes = 0
    try:
        for path in out_dir.rglob("*.md"):
            if not path.is_file():
                continue
            name = path.name
            # Skip index files; only prose counts. Scene files are
            # scene-*.md; chapter-*.md is a chapter-level wrapper we don't
            # want to double-count if both exist. Count anything under
            # output/ that looks like prose.
            if name.startswith(".") or name in {"INDEX.md", "progress.md"}:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            total += len(text.split())
            if name.startswith("scene-"):
                scenes += 1
    except OSError as exc:
        logger.debug("word_count walk failed at %s: %s", out_dir, exc)
        return 0, {"scenes": 0, "source": "error"}

    sample = {"scenes": scenes, "source": "output_files"}
    return total, sample


def _daemon_liveness(udir: Path, status: dict[str, Any] | None) -> dict[str, Any]:
    """Build the shared liveness block used by list, inspect, and status.

    Centralizing this shape is the point — every reader surface gets the
    same interpreted fields, so legibility fixes in one place land
    everywhere at once.
    """
    has_premise = (udir / "PROGRAM.md").exists()
    targets = _read_json(udir / "work_targets.json")
    has_work = isinstance(targets, list) and any(
        t.get("lifecycle") == "active" for t in targets if isinstance(t, dict)
    )
    is_paused = (udir / ".pause").exists()
    last_activity = _last_activity_at(udir, status)
    staleness = _staleness_bucket(last_activity)

    raw_phase: str | None = None
    if status and isinstance(status, dict):
        # status.json uses `current_phase`; older callers wrote `phase`.
        # Accept both for defense in depth, prefer the canonical name.
        raw_phase = status.get("current_phase") or status.get("phase")

    accept_rate, accept_sample = _compute_accept_rate_from_db(udir)
    # word_count comes from prose on disk, NOT status.json — the cached
    # value there is a DashboardMetrics snapshot that drifts across
    # universe switches. Reading files is slower but truthful.
    word_count, word_count_sample = _compute_word_count_from_files(udir)

    return {
        "phase": raw_phase or "offline",
        "phase_human": _phase_human(
            raw_phase, has_premise, has_work, is_paused, staleness,
        ),
        "is_paused": is_paused,
        "has_premise": has_premise,
        "has_work": has_work,
        "last_activity_at": last_activity,
        "staleness": staleness,
        "word_count": word_count,
        "word_count_sample": word_count_sample,
        "accept_rate": accept_rate,
        "accept_rate_sample": accept_sample,
    }


# ---------------------------------------------------------------------------
# Universe action implementations
# ---------------------------------------------------------------------------


def _action_list_universes(**_kwargs: Any) -> str:
    base = _base_path()
    if not base.is_dir():
        return json.dumps({
            "universes": [],
            "count": 0,
            "note": f"Base directory does not exist: {base}",
        })

    try:
        all_entries = list(base.iterdir())
    except OSError as exc:
        return json.dumps({
            "universes": [],
            "count": 0,
            "note": f"Base directory unreadable ({base}): {exc}",
        })

    universes = []
    for child in sorted(all_entries):
        if not child.is_dir() or child.name.startswith("."):
            continue
        status = _read_json(child / "status.json")
        liveness = _daemon_liveness(child, status if isinstance(status, dict) else None)
        info: dict[str, Any] = {
            "id": child.name,
            "has_premise": liveness["has_premise"],
            "word_count": liveness["word_count"],
            "phase": liveness["phase"],
            "phase_human": liveness["phase_human"],
            "staleness": liveness["staleness"],
            "last_activity_at": liveness["last_activity_at"],
            "accept_rate": liveness["accept_rate"],
        }
        universes.append(info)

    result: dict[str, Any] = {"universes": universes, "count": len(universes)}
    if not universes:
        if not all_entries:
            result["note"] = f"Base directory is empty: {base}"
        else:
            result["note"] = (
                f"Base directory has {len(all_entries)} entries but none "
                f"are valid universes (all hidden or non-directories): {base}"
            )
    return json.dumps(result)


def _action_inspect_universe(universe_id: str = "", **_kwargs: Any) -> str:
    uid = universe_id or _default_universe()
    udir = _universe_dir(uid)

    if not udir.is_dir():
        return json.dumps({
            "error": f"Universe '{uid}' not found.",
            "available": [
                d.name for d in _base_path().iterdir()
                if d.is_dir() and not d.name.startswith(".")
            ] if _base_path().is_dir() else [],
        })

    result: dict[str, Any] = {"universe_id": uid}

    # Daemon liveness block — always present, so downstream readers (humans
    # and chat clients) can always tell whether the daemon is alive, why
    # it's stuck, and whether the premise and work exist.
    status = _read_json(udir / "status.json")
    liveness = _daemon_liveness(udir, status if isinstance(status, dict) else None)
    result["daemon"] = {
        "phase": liveness["phase"],
        "phase_human": liveness["phase_human"],
        "is_paused": liveness["is_paused"],
        "has_premise": liveness["has_premise"],
        "has_work": liveness["has_work"],
        "last_activity_at": liveness["last_activity_at"],
        "staleness": liveness["staleness"],
        "word_count": liveness["word_count"],
        "word_count_sample": liveness["word_count_sample"],
        "accept_rate": liveness["accept_rate"],
        "accept_rate_sample": liveness["accept_rate_sample"],
    }

    # Premise — always present as a boolean so callers can't silently miss
    # the "no premise set" case. Full text included only when non-empty.
    program = _read_text(udir / "PROGRAM.md")
    result["has_premise"] = bool(program)
    if program:
        result["premise"] = program[:500] + ("..." if len(program) > 500 else "")

    # Notes summary
    notes = _read_json(udir / "notes.json")
    if notes and isinstance(notes, list):
        recent = notes[-5:]
        result["recent_notes"] = [
            {
                "source": n.get("source"),
                "category": n.get("category"),
                "text": n.get("text", "")[:200],
                "timestamp": n.get("timestamp"),
            }
            for n in recent
        ]

    # Work targets
    targets = _read_json(udir / "work_targets.json")
    if targets and isinstance(targets, list):
        active = [t for t in targets if t.get("lifecycle") == "active"][:5]
        result["active_targets"] = [
            {
                "id": t.get("target_id"),
                "title": t.get("title"),
                "role": t.get("role"),
                "intent": t.get("current_intent"),
            }
            for t in active
        ]

    # Output files
    output_dir = udir / "output"
    if output_dir.is_dir():
        result["output_files"] = _list_output_tree(output_dir)

    # Activity tail
    activity = _read_text(udir / "activity.log")
    if activity:
        lines = activity.strip().splitlines()
        result["recent_activity"] = lines[-10:]

    # Pending requests
    from workflow.work_targets import REQUESTS_FILENAME
    requests = _read_json(udir / REQUESTS_FILENAME)
    if requests and isinstance(requests, list):
        pending = [r for r in requests if r.get("status") == "pending"]
        if pending:
            result["pending_requests"] = len(pending)

    # Cross-surface hint — helps chatbots discover cross-domain work even
    # when the active universe is themed (e.g. fantasy). The workspace is
    # one container; goals, branches, and wiki span all domains.
    result["cross_surface_hint"] = {
        "note": (
            "This workspace is one container; cross-domain branches and Goals "
            "live at extensions + goals + wiki regardless of this workspace's theme."
        ),
        "paths": [
            {
                "action": "extensions action=list_branches",
                "purpose": "All workflows across all domains",
            },
            {
                "action": "goals action=list",
                "purpose": (
                    "Domain-agnostic intents "
                    "(research, software, science, fantasy, etc.)"
                ),
            },
            {
                "action": "wiki action=search",
                "purpose": "Cross-domain notes, bugs, and design plans",
            },
            {
                "action": "universe action=list",
                "purpose": "Other workspaces if multiple exist",
            },
        ],
    }

    return json.dumps(result, default=str)


def _list_output_tree(output_dir: Path, max_depth: int = 3) -> list[str]:
    """Walk the output directory and return relative paths."""
    files = []
    for root, dirs, filenames in os.walk(output_dir):
        depth = len(Path(root).relative_to(output_dir).parts)
        if depth >= max_depth:
            dirs.clear()
            continue
        for f in sorted(filenames):
            rel = Path(root, f).relative_to(output_dir)
            if not f.startswith("."):
                files.append(str(rel))
    return files[:50]


def _action_read_output(universe_id: str = "", path: str = "", **_kwargs: Any) -> str:
    uid = universe_id or _default_universe()
    udir = _universe_dir(uid)
    target = (udir / "output" / path).resolve()

    if not target.is_relative_to((udir / "output").resolve()):
        return json.dumps({"error": "Path traversal not allowed."})
    if not target.exists():
        return json.dumps({"error": f"File not found: {path}"})

    content = _read_text(target)
    if len(content) > 10000:
        return json.dumps({
            "universe_id": uid,
            "path": path,
            "content": content[:10000],
            "truncated": True,
            "total_chars": len(content),
            "note": "File truncated to 10K chars. Request specific sections if needed.",
        })
    return json.dumps({
        "universe_id": uid,
        "path": path,
        "content": content,
        "truncated": False,
    })


_SUBMIT_REQUEST_MAX_BYTES = 8192


def _action_submit_request(
    universe_id: str = "",
    text: str = "",
    request_type: str = "scene_direction",
    branch_id: str = "",
    priority_weight: float = 0.0,
    **_kwargs: Any,
) -> str:
    from workflow.branch_tasks import BranchTask, append_task, new_task_id
    from workflow.work_targets import REQUESTS_FILENAME

    uid = universe_id or _default_universe()
    udir = _universe_dir(uid)
    if not udir.is_dir():
        return json.dumps({"error": f"Universe '{uid}' not found."})

    # 8 KiB cap keeps requests.json bounded and discourages pasting
    # entire drafts into the request channel (add_canon is the right
    # tool for that). UTF-8 byte length, not char count.
    text_bytes = len(text.encode("utf-8"))
    if text_bytes > _SUBMIT_REQUEST_MAX_BYTES:
        return json.dumps({
            "error": (
                f"Request text exceeds {_SUBMIT_REQUEST_MAX_BYTES} bytes "
                f"({text_bytes} submitted). Summarize or split into "
                "multiple requests. For long prose, use `add_canon` "
                "instead."
            ),
        })

    valid_types = {
        "scene_direction", "revision", "canon_change",
        "branch_proposal", "general",
    }
    if request_type not in valid_types:
        request_type = "general"

    # Invariant 9: priority_weight cap. Negative values reject for all
    # actors. Non-host clamped to 0 silently (preflight §4.3 #9).
    try:
        pw = float(priority_weight)
    except (TypeError, ValueError):
        pw = 0.0
    if pw < 0:
        return json.dumps({
            "error": "priority_weight must be >= 0.",
        })
    source = os.environ.get("UNIVERSE_SERVER_USER", "anonymous")
    host_id = os.environ.get("UNIVERSE_SERVER_HOST_USER", "host")
    is_host = source == host_id
    if not is_host:
        pw = 0.0

    request_id = f"req_{int(time.time())}_{os.urandom(4).hex()}"
    request_obj = {
        "id": request_id,
        "type": request_type,
        "text": text,
        "branch_id": branch_id or None,
        "status": "pending",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
    }

    requests_path = udir / REQUESTS_FILENAME
    existing = _read_json(requests_path)
    if not isinstance(existing, list):
        existing = []
    existing.append(request_obj)

    try:
        udir.mkdir(parents=True, exist_ok=True)
        requests_path.write_text(
            json.dumps(existing, indent=2, default=str),
            encoding="utf-8",
        )
    except OSError as exc:
        return json.dumps({"error": f"Failed to write request: {exc}"})

    # Phase E: also queue a BranchTask so the dispatcher can score +
    # schedule. host submissions land as host_request tier; anyone
    # else lands as user_request. The WorkTarget still gets
    # materialized by UserRequestProducer from requests.json on the
    # next producer cycle — BranchTask wraps the execution intent.
    branch_task_id = ""
    try:
        task = BranchTask(
            branch_task_id=new_task_id(),
            branch_def_id="fantasy_author:universe_cycle_wrapper",
            universe_id=uid,
            inputs={
                "work_target_ref": None,
                "request_id": request_id,
                "request_type": request_type,
                "branch_id": branch_id or "",
            },
            trigger_source="host_request" if is_host else "user_request",
            priority_weight=pw,
        )
        append_task(udir, task)
        branch_task_id = task.branch_task_id
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to queue BranchTask for %s: %s", request_id, exc)

    pending_count = sum(
        1 for r in existing
        if isinstance(r, dict) and r.get("status") == "pending"
    )
    ahead = max(0, pending_count - 1)
    if ahead == 0:
        position_note = "yours is next in the daemon's queue"
    elif ahead == 1:
        position_note = "1 other request is ahead of yours"
    else:
        position_note = f"{ahead} other requests are ahead of yours"

    return json.dumps({
        "universe_id": uid,
        "request_id": request_id,
        "branch_task_id": branch_task_id,
        "status": "pending",
        "priority_weight": pw,
        "queue_position": pending_count,
        "ahead_of_yours": ahead,
        "what_happens_next": (
            f"The daemon will see your request on its next review cycle; "
            f"{position_note}. Use `universe action=inspect universe_id={uid}` "
            "to watch the queue or check whether your request is now active work."
        ),
    })


def _action_queue_list(
    universe_id: str = "",
    **_kwargs: Any,
) -> str:
    """Read ``branch_tasks.json`` fresh (no in-memory cache) and
    return sorted+scored queue. Includes ``tier_status`` per R11.
    """
    from workflow.branch_tasks import read_queue
    from workflow.dispatcher import (
        load_dispatcher_config,
        score_task,
    )

    uid = universe_id or _default_universe()
    udir = _universe_dir(uid)
    if not udir.is_dir():
        return json.dumps({"error": f"Universe '{uid}' not found."})

    try:
        queue = read_queue(udir)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({
            "universe_id": uid,
            "error": f"Failed to read queue: {exc}",
        })

    cfg = load_dispatcher_config(udir)
    now_iso = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    for task in queue:
        row = task.to_dict()
        row["score"] = score_task(task, now_iso=now_iso, config=cfg)
        row["tier_enabled"] = cfg.tier_enabled(task.trigger_source)
        rows.append(row)
    # Primary: status pending first, then score desc. Non-pending
    # sorted by queued_at desc.
    rows.sort(
        key=lambda r: (
            0 if r.get("status") == "pending" else 1,
            -float(r.get("score", 0.0)),
            r.get("queued_at", ""),
        ),
    )

    return json.dumps({
        "universe_id": uid,
        "queue": rows,
        "pending_count": sum(1 for r in rows if r.get("status") == "pending"),
        "running_count": sum(1 for r in rows if r.get("status") == "running"),
        "tier_status": cfg.tier_status_map(),
    })


# ---------------------------------------------------------------------------
# Phase H — daemon_overview + set_tier_config (aggregated MCP surface)
# ---------------------------------------------------------------------------

# 1-second TTL cache per universe for daemon_overview (R1 invariant 1).
_OVERVIEW_CACHE: dict[str, tuple[float, str, str]] = {}
_OVERVIEW_TTL_SECONDS = 1.0

# Per-caller reasonable limits (R14 response-size). Overridable via `limit`.
_OVERVIEW_DEFAULT_LIMITS = {
    "queue_top": 20,
    "bids_top": 20,
    "settlements_recent": 10,
    "gates_recent": 10,
    "activity_tail": 30,
}
# Absolute cap even when `limit=full` — prevents pathological responses.
_OVERVIEW_ABSOLUTE_CAP = {
    "queue_top": 500,
    "bids_top": 500,
    "settlements_recent": 500,
    "gates_recent": 200,
    "activity_tail": 1000,
}

# R14 serialized-byte cap. Per-field caps above are necessary but not
# sufficient: a dense queue + long activity_tail + many bids can still
# blow past Claude.ai token limits even with each field individually
# bounded. If the serialized response exceeds this threshold, trim in
# priority order (see _OVERVIEW_TRIM_ORDER). Gates + dispatcher +
# subscriptions are NEVER trimmed (load-bearing per reviewer polish
# #5).
DAEMON_OVERVIEW_MAX_BYTES = 32_768

# Trim priority when the byte cap fires. Each entry is
# ``(key, subkey, keep_side)``:
# - ``key``: top-level response field.
# - ``subkey``: nested key (e.g. ``response["bids"]["recent"]``) or
#   None for top-level lists.
# - ``keep_side``: "head" keeps the front of the list (sorted
#   descending — top-N); "tail" keeps the back (chronological —
#   latest entries).
_OVERVIEW_TRIM_ORDER = (
    ("activity_tail", None, "tail"),
    ("settlements", "recent", "head"),
    ("bids", "recent", "head"),
    ("queue", "top", "head"),
)


def _trim_overview_for_bytes(
    response: dict[str, Any], *, cap: int = DAEMON_OVERVIEW_MAX_BYTES,
) -> str:
    """Serialize ``response`` and trim until ``<= cap`` bytes.

    Mutates ``response`` in place as fields shrink. When any trim
    lands, sets ``response["truncated"] = True`` so consumers know
    counters (``*_count`` fields) are authoritative over the trimmed
    lists. Gates + dispatcher + subscriptions are never in the trim
    order (load-bearing). Returns the final serialized JSON.
    """
    serialized = json.dumps(response, default=str)
    if len(serialized.encode("utf-8")) <= cap:
        return serialized
    response["truncated"] = True
    for key, subkey, keep_side in _OVERVIEW_TRIM_ORDER:
        container: Any = response.get(key)
        if subkey is not None:
            container = container.get(subkey) if isinstance(container, dict) else None
        if not isinstance(container, list):
            continue
        while container:
            if len(container) <= 1:
                container.clear()
            elif keep_side == "tail":
                # Halve from the front, keep the latest entries.
                del container[: len(container) // 2]
            else:
                # Halve from the back, keep top-ranked entries.
                del container[len(container) // 2:]
            serialized = json.dumps(response, default=str)
            if len(serialized.encode("utf-8")) <= cap:
                return serialized
    return serialized


def _overview_limits(limit_param: Any) -> dict[str, int]:
    """Resolve per-field limits from the `limit` param.

    `limit` int → applies that value to all top-N lists (bounded by
    absolute cap). `limit="full"` → absolute cap (not truly unbounded).
    Default / invalid → documented defaults.
    """
    if isinstance(limit_param, str) and limit_param.strip().lower() == "full":
        return dict(_OVERVIEW_ABSOLUTE_CAP)
    try:
        n = int(limit_param)
    except (TypeError, ValueError):
        return dict(_OVERVIEW_DEFAULT_LIMITS)
    if n <= 0:
        return dict(_OVERVIEW_DEFAULT_LIMITS)
    return {
        key: min(n, _OVERVIEW_ABSOLUTE_CAP[key])
        for key in _OVERVIEW_DEFAULT_LIMITS
    }


def _tail_file_lines(path: Path, n: int) -> list[str]:
    """Return the last `n` lines of `path`, or empty list on missing/error."""
    if not path.exists() or n <= 0:
        return []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            # Naive tail — OK up to 1000 lines for activity.log sized files.
            lines = fh.readlines()
        return [ln.rstrip("\n") for ln in lines[-n:]]
    except OSError:
        return []


def _action_daemon_overview(
    universe_id: str = "",
    limit: Any = None,
    **_kwargs: Any,
) -> str:
    """Aggregated read-through per preflight §4.1 #1 (Phase H).

    Composes queue + subscriptions + bids + settlements + gates +
    activity tail + run state into one response. 1s TTL cache keyed
    on (universe_id, limit) keeps hot-path cost bounded (R1).

    Read-only: no mutations. Absent features gracefully degrade
    (empty lists / zero counts) rather than error.
    """
    import time as _time

    uid = universe_id or _default_universe()
    udir = _universe_dir(uid)
    if not udir.is_dir():
        return json.dumps({"error": f"Universe '{uid}' not found."})

    limit_key = (
        "full" if isinstance(limit, str)
        and limit.strip().lower() == "full" else str(limit)
    )
    cache_key = f"{uid}::{limit_key}"
    now_s = _time.time()
    cached = _OVERVIEW_CACHE.get(cache_key)
    if cached and (now_s - cached[0]) < _OVERVIEW_TTL_SECONDS:
        return cached[2]

    limits = _overview_limits(limit)
    response: dict[str, Any] = {"universe_id": uid}

    # Dispatcher config + tier_status_map.
    try:
        from workflow.dispatcher import load_dispatcher_config
        cfg = load_dispatcher_config(udir)
        response["dispatcher"] = {
            "tier_status_map": cfg.tier_status_map(),
            "config": {
                "accept_external_requests": cfg.accept_external_requests,
                "accept_goal_pool": cfg.accept_goal_pool,
                "accept_paid_bids": cfg.accept_paid_bids,
                "allow_opportunistic": cfg.allow_opportunistic,
                "bid_coefficient": cfg.bid_coefficient,
                "bid_term_cap": cfg.bid_term_cap,
            },
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("daemon_overview: dispatcher read failed: %s", exc)
        response["dispatcher"] = {}

    # Queue top-N.
    try:
        from workflow.branch_tasks import read_queue
        from workflow.dispatcher import score_task
        queue = read_queue(udir)
        q_cfg = load_dispatcher_config(udir)
        now_iso = datetime.now(timezone.utc).isoformat()
        scored: list[tuple[float, dict]] = []
        pending = 0
        for task in queue:
            if task.status == "pending":
                pending += 1
                row = task.to_dict()
                row["score"] = score_task(
                    task, now_iso=now_iso, config=q_cfg,
                )
                scored.append((row["score"], row))
        scored.sort(key=lambda p: -p[0])
        response["queue"] = {
            "pending_count": pending,
            "top": [row for _, row in scored[: limits["queue_top"]]],
            "archived_recent_count": 0,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("daemon_overview: queue read failed: %s", exc)
        response["queue"] = {"pending_count": 0, "top": [],
                             "archived_recent_count": 0}

    # Subscriptions + drift.
    try:
        from workflow.producers.goal_pool import (
            POOL_DIRNAME,
            goal_pool_enabled,
            repo_root_path,
        )
        from workflow.subscriptions import list_subscriptions
        goals = list_subscriptions(udir)
        counts: dict[str, int] = {g: 0 for g in goals}
        try:
            repo_root = repo_root_path(udir)
            pool_root = repo_root / POOL_DIRNAME
            for g in goals:
                gdir = pool_root / g
                if gdir.is_dir():
                    counts[g] = sum(1 for _ in gdir.glob("*.yaml"))
        except RuntimeError:
            pass
        if cfg.accept_goal_pool and not goals:
            drift = "pool_enabled_no_subs"
        elif goals and not cfg.accept_goal_pool:
            drift = "subs_but_pool_disabled"
        else:
            drift = "ok"
        response["subscriptions"] = {
            "goals": goals,
            "drift_flag": drift,
            "pool_status_per_goal": counts,
            "pool_flag_enabled": goal_pool_enabled(),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("daemon_overview: subscriptions read failed: %s", exc)
        response["subscriptions"] = {"goals": [], "drift_flag": "ok",
                                     "pool_status_per_goal": {}}

    # Bids + daemon capabilities.
    try:
        from workflow.bid.node_bid import read_node_bids
        from workflow.producers.goal_pool import repo_root_path
        from workflow.producers.node_bid import paid_market_enabled
        try:
            bid_repo_root = repo_root_path(udir)
            bids = read_node_bids(bid_repo_root)
        except RuntimeError:
            bids = []
        open_bids = [b.to_dict() for b in bids if b.status == "open"]
        claimed = sum(1 for b in bids if b.status.startswith("claimed:"))
        response["bids"] = {
            "open_count": len(open_bids),
            "claimed_count": claimed,
            "top_open": open_bids[: limits["bids_top"]],
            "daemon_capabilities": {
                "serves_llm_types": sorted(
                    os.environ.get("FANTASY_DAEMON_LLM_TYPES", "").split(",")
                    if os.environ.get("FANTASY_DAEMON_LLM_TYPES")
                    else [],
                ),
                "paid_market_enabled": paid_market_enabled(),
                "bid_coefficient": cfg.bid_coefficient,
            },
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("daemon_overview: bids read failed: %s", exc)
        response["bids"] = {"open_count": 0, "claimed_count": 0,
                            "top_open": []}

    # Settlements.
    try:
        import yaml as _yaml

        from workflow.bid.settlements import settlements_dir
        from workflow.producers.goal_pool import repo_root_path
        try:
            sroot = settlements_dir(repo_root_path(udir))
        except RuntimeError:
            sroot = None
        s_entries: list[dict] = []
        s_total = 0
        s_unsettled = 0
        if sroot and sroot.is_dir():
            for p in sorted(sroot.glob("*.yaml")):
                s_total += 1
                try:
                    raw = _yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                except Exception:  # noqa: BLE001
                    continue
                if not isinstance(raw, dict):
                    continue
                if not raw.get("settled"):
                    s_unsettled += 1
                s_entries.append(raw)
        s_entries.sort(
            key=lambda r: str(r.get("completed_at", "")), reverse=True,
        )
        response["settlements"] = {
            "count_total": s_total,
            "count_unsettled": s_unsettled,
            "recent": s_entries[: limits["settlements_recent"]],
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "daemon_overview: settlements read failed: %s", exc,
        )
        response["settlements"] = {
            "count_total": 0, "count_unsettled": 0, "recent": [],
        }

    # Gates — best-effort; counts only (full gates data is expensive).
    try:
        from workflow.daemon_server import list_gate_claims
        claims = list_gate_claims(_base_path()) or []
        # Filter to claims whose branch lives in this universe — for v1
        # we report all claims and let the caller filter; universe-
        # scoping needs the branch-to-universe mapping which isn't
        # always populated.
        response["gates"] = {
            "ladder_count_on_bound_goal": 0,
            "claims_on_this_universe": 0,
            "total_claims": len(claims),
            "recent_claims": (claims or [])[: limits["gates_recent"]],
        }
    except Exception as exc:  # noqa: BLE001
        logger.debug("daemon_overview: gates read failed: %s", exc)
        response["gates"] = {"total_claims": 0, "recent_claims": []}

    # Activity tail (raw file, not a parse).
    response["activity_tail"] = _tail_file_lines(
        udir / "activity.log", limits["activity_tail"],
    )

    # Run state (status.json — best-effort).
    try:
        status = _read_json(udir / "status.json") or {}
        if isinstance(status, dict):
            response["run_state"] = {
                "current_phase": status.get("current_phase", ""),
                "status": status.get("daemon_state", ""),
                "last_verdict": status.get("last_verdict", ""),
                "total_words": status.get("total_words", 0),
                "total_chapters": status.get("total_chapters", 0),
                "last_updated": status.get("last_updated", ""),
            }
        else:
            response["run_state"] = {}
    except Exception:  # noqa: BLE001
        response["run_state"] = {}

    serialized = _trim_overview_for_bytes(response)
    _OVERVIEW_CACHE[cache_key] = (now_s, cache_key, serialized)
    # Cap cache size — prune to last 8 universes worth of keys.
    if len(_OVERVIEW_CACHE) > 16:
        oldest = sorted(_OVERVIEW_CACHE.items(), key=lambda kv: kv[1][0])[:8]
        for k, _ in oldest:
            _OVERVIEW_CACHE.pop(k, None)
    return serialized


_VALID_TIER_KEYS = frozenset({
    "external_requests", "goal_pool", "paid_bids", "opportunistic",
})
_TIER_KEY_TO_CONFIG_FIELD = {
    "external_requests": "accept_external_requests",
    "goal_pool": "accept_goal_pool",
    "paid_bids": "accept_paid_bids",
    "opportunistic": "allow_opportunistic",
}


def _action_set_tier_config(
    universe_id: str = "",
    tier: str = "",
    enabled: bool = False,
    **_kwargs: Any,
) -> str:
    """Phase H: persist a tier toggle into ``dispatcher_config.yaml``.

    Takes effect at the next dispatcher cycle (R2 invariant 3);
    in-flight tasks complete normally. Round-trips YAML so other
    config fields are preserved.
    """
    import yaml as _yaml

    uid = universe_id or _default_universe()
    udir = _universe_dir(uid)
    if not udir.is_dir():
        return json.dumps({"error": f"Universe '{uid}' not found."})

    tier_name = (tier or "").strip().lower()
    if tier_name not in _VALID_TIER_KEYS:
        return json.dumps({
            "status": "rejected",
            "error": "unknown_tier",
            "available_tiers": sorted(_VALID_TIER_KEYS),
        })

    field_name = _TIER_KEY_TO_CONFIG_FIELD[tier_name]
    cfg_path = udir / "dispatcher_config.yaml"
    existing: dict[str, Any] = {}
    if cfg_path.exists():
        try:
            loaded = _yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                existing = loaded
        except Exception as exc:  # noqa: BLE001
            return json.dumps({
                "status": "rejected",
                "error": f"config_corrupt: {exc}",
            })

    existing[field_name] = bool(enabled)

    try:
        udir.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(
            _yaml.safe_dump(existing, sort_keys=True,
                            default_flow_style=False),
            encoding="utf-8",
        )
    except OSError as exc:
        return json.dumps({
            "status": "rejected",
            "error": f"config_write_failed: {exc}",
        })

    # Invalidate the overview cache for this universe so the next
    # `daemon_overview` reflects the change immediately (tests rely
    # on this; production clients also benefit).
    for key in list(_OVERVIEW_CACHE.keys()):
        if key.startswith(f"{uid}::"):
            _OVERVIEW_CACHE.pop(key, None)

    return json.dumps({
        "universe_id": uid,
        "status": "ok",
        "tier": tier_name,
        "enabled": bool(enabled),
        "takes_effect": "next_dispatcher_cycle",
    })


def _action_queue_cancel(
    universe_id: str = "",
    branch_task_id: str = "",
    **_kwargs: Any,
) -> str:
    """Cancel a BranchTask.

    Pending: hard-marks ``cancelled`` via ``mark_status``.
    Running: cooperative cancel — sets ``cancel_requested=True`` so
    the daemon's stream loop observes the flag at the next
    inter-node event and finalizes as ``cancelled``. Authorization:
    the task's ``claimed_by`` daemon (self-cancel) OR host identity.
    Other actors get ``cancel_not_authorized``.
    """
    from workflow.branch_tasks import (
        mark_status,
        read_queue,
        request_task_cancel,
    )

    uid = universe_id or _default_universe()
    udir = _universe_dir(uid)
    if not udir.is_dir():
        return json.dumps({"error": f"Universe '{uid}' not found."})
    if not branch_task_id:
        return json.dumps({"error": "branch_task_id required."})

    try:
        queue = read_queue(udir)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": f"Failed to read queue: {exc}"})

    target = next(
        (t for t in queue if t.branch_task_id == branch_task_id),
        None,
    )
    if target is None:
        return json.dumps({
            "universe_id": uid,
            "status": "not_found",
            "branch_task_id": branch_task_id,
        })
    if target.status == "running":
        source = os.environ.get("UNIVERSE_SERVER_USER", "anonymous")
        host_id = os.environ.get("UNIVERSE_SERVER_HOST_USER", "host")
        is_host = source == host_id
        is_owner = bool(target.claimed_by) and source == target.claimed_by
        if not (is_host or is_owner):
            return json.dumps({
                "universe_id": uid,
                "status": "rejected",
                "error": "cancel_not_authorized",
                "branch_task_id": branch_task_id,
                "hint": (
                    "Running-task cancel requires the host or the "
                    "claiming daemon. Set UNIVERSE_SERVER_USER to the "
                    "task owner or the host identity."
                ),
            })
        try:
            ok = request_task_cancel(udir, branch_task_id)
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"error": f"Failed to request cancel: {exc}"})
        if not ok:
            # Race: task reached terminal between read_queue and now.
            return json.dumps({
                "universe_id": uid,
                "status": "rejected",
                "error": "task_already_terminal",
                "branch_task_id": branch_task_id,
            })
        return json.dumps({
            "universe_id": uid,
            "status": "cancel_requested",
            "branch_task_id": branch_task_id,
            "note": (
                "cooperative cancel — observed at next inter-node "
                "event; daemon finalizes as cancelled"
            ),
        })
    if target.status != "pending":
        return json.dumps({
            "universe_id": uid,
            "status": target.status,
            "branch_task_id": branch_task_id,
            "note": "task is already in a terminal state",
        })

    try:
        mark_status(udir, branch_task_id, status="cancelled")
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": f"Failed to cancel: {exc}"})

    return json.dumps({
        "universe_id": uid,
        "status": "cancelled",
        "branch_task_id": branch_task_id,
    })


def _goal_pool_not_available() -> str:
    return json.dumps({
        "status": "not_available",
        "hint": "WORKFLOW_GOAL_POOL=on required",
    })


def _action_subscribe_goal(
    universe_id: str = "",
    goal_id: str = "",
    **_kwargs: Any,
) -> str:
    from workflow.producers.goal_pool import goal_pool_enabled
    from workflow.subscriptions import subscribe

    if not goal_pool_enabled():
        return _goal_pool_not_available()
    uid = universe_id or _default_universe()
    udir = _universe_dir(uid)
    if not udir.is_dir():
        return json.dumps({"error": f"Universe '{uid}' not found."})
    if not goal_id:
        return json.dumps({"error": "goal_id required."})
    try:
        goals = subscribe(udir, goal_id)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": f"subscribe failed: {exc}"})
    return json.dumps({
        "universe_id": uid,
        "goal_id": goal_id,
        "status": "subscribed",
        "goals": goals,
    })


def _action_unsubscribe_goal(
    universe_id: str = "",
    goal_id: str = "",
    **_kwargs: Any,
) -> str:
    from workflow.producers.goal_pool import goal_pool_enabled
    from workflow.subscriptions import unsubscribe

    if not goal_pool_enabled():
        return _goal_pool_not_available()
    uid = universe_id or _default_universe()
    udir = _universe_dir(uid)
    if not udir.is_dir():
        return json.dumps({"error": f"Universe '{uid}' not found."})
    if not goal_id:
        return json.dumps({"error": "goal_id required."})
    try:
        goals = unsubscribe(udir, goal_id)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": f"unsubscribe failed: {exc}"})
    return json.dumps({
        "universe_id": uid,
        "goal_id": goal_id,
        "status": "unsubscribed",
        "goals": goals,
    })


def _action_list_subscriptions(
    universe_id: str = "",
    **_kwargs: Any,
) -> str:
    """List subscriptions + drift detection + per-goal pool counts.

    Preflight §4.1 #4 drift flag values:
      - "ok"
      - "pool_enabled_no_subs"  (F on + accept_goal_pool=true + zero subs)
      - "subs_but_pool_disabled" (subs exist + accept_goal_pool=false)
    """
    from workflow.dispatcher import load_dispatcher_config
    from workflow.producers.goal_pool import (
        POOL_DIRNAME,
        goal_pool_enabled,
        repo_root_path,
    )
    from workflow.subscriptions import list_subscriptions as _list

    if not goal_pool_enabled():
        return _goal_pool_not_available()
    uid = universe_id or _default_universe()
    udir = _universe_dir(uid)
    if not udir.is_dir():
        return json.dumps({"error": f"Universe '{uid}' not found."})

    try:
        goals = _list(udir)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": f"list_subscriptions failed: {exc}"})

    # Per-goal pool counts.
    counts: dict[str, int] = {g: 0 for g in goals}
    try:
        repo_root = repo_root_path(udir)
        pool_root = repo_root / POOL_DIRNAME
        for g in goals:
            gdir = pool_root / g
            if gdir.is_dir():
                counts[g] = sum(1 for _ in gdir.glob("*.yaml"))
    except RuntimeError:
        # repo_root unresolvable — counts stay zero
        pass

    cfg = load_dispatcher_config(udir)
    if cfg.accept_goal_pool and not goals:
        drift = "pool_enabled_no_subs"
    elif goals and not cfg.accept_goal_pool:
        drift = "subs_but_pool_disabled"
    else:
        drift = "ok"

    return json.dumps({
        "universe_id": uid,
        "goals": goals,
        "pool_status_per_goal": counts,
        "config_vs_subscriptions_drift": drift,
    })


def _action_post_to_goal_pool(
    universe_id: str = "",
    goal_id: str = "",
    branch_def_id: str = "",
    inputs_json: str = "",
    priority_weight: float = 0.0,
    **_kwargs: Any,
) -> str:
    """Write a pool YAML to ``<repo_root>/goal_pool/<goal_id>/<id>.yaml``.

    Response includes a ``next_step`` hint for cross-host visibility
    (git add/commit/push).
    """
    from workflow.producers.goal_pool import (
        goal_pool_enabled,
        repo_root_path,
        validate_pool_task_inputs,
        write_pool_post,
    )

    if not goal_pool_enabled():
        return _goal_pool_not_available()
    uid = universe_id or _default_universe()
    udir = _universe_dir(uid)
    if not udir.is_dir():
        return json.dumps({"error": f"Universe '{uid}' not found."})
    if not goal_id:
        return json.dumps({"error": "goal_id required."})
    if not branch_def_id:
        return json.dumps({"error": "branch_def_id required."})

    # Parse inputs_json. Empty string → {}.
    if inputs_json.strip():
        try:
            inputs = json.loads(inputs_json)
        except json.JSONDecodeError as exc:
            return json.dumps({"error": f"inputs_json invalid JSON: {exc}"})
    else:
        inputs = {}
    ok, reason = validate_pool_task_inputs(inputs)
    if not ok:
        return json.dumps({
            "status": "rejected",
            "error": f"invalid_inputs: {reason}",
        })

    # priority_weight clamp per Phase E invariant 9 (extended to pool posts).
    try:
        pw = float(priority_weight)
    except (TypeError, ValueError):
        pw = 0.0
    if pw < 0:
        return json.dumps({
            "status": "rejected",
            "error": "priority_weight must be >= 0.",
        })
    source = os.environ.get("UNIVERSE_SERVER_USER", "anonymous")
    host_id = os.environ.get("UNIVERSE_SERVER_HOST_USER", "host")
    is_host = source == host_id
    if not is_host:
        pw = 0.0

    try:
        repo_root = repo_root_path(udir)
    except RuntimeError as exc:
        return json.dumps({
            "status": "rejected",
            "error": "repo_root_not_resolvable",
            "hint": (
                "Set WORKFLOW_REPO_ROOT or run the daemon from inside "
                "a git checkout. Detail: " + str(exc)
            ),
        })

    try:
        out_path = write_pool_post(
            repo_root,
            goal_id,
            branch_def_id=branch_def_id,
            inputs=inputs,
            priority_weight=pw,
            posted_by=source,
        )
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": f"post failed: {exc}"})

    rel_path = out_path.relative_to(repo_root) if out_path.is_relative_to(
        repo_root,
    ) else out_path
    return json.dumps({
        "universe_id": uid,
        "status": "posted",
        "goal_id": goal_id,
        "branch_def_id": branch_def_id,
        "path": str(out_path),
        "priority_weight": pw,
        "next_step": (
            f"To make this post visible to cross-host subscribers, run: "
            f"git add {rel_path} && git commit && git push"
        ),
    })


def _paid_market_not_available() -> str:
    return json.dumps({
        "status": "not_available",
        "hint": "WORKFLOW_PAID_MARKET=on required",
    })


def _action_submit_node_bid(
    universe_id: str = "",
    node_def_id: str = "",
    required_llm_type: str = "",
    inputs_json: str = "",
    bid: float = 0.0,
    **_kwargs: Any,
) -> str:
    """Phase G: write a NodeBid YAML to ``<repo_root>/bids/<id>.yaml``.

    Flag-gated on ``WORKFLOW_PAID_MARKET=on``. Flat-dict inputs only.
    Response includes a ``next_step`` git push hint, mirroring
    ``post_to_goal_pool``.
    """
    from workflow.bid.node_bid import (
        new_node_bid_id,
        validate_node_bid_inputs,
        write_node_bid_post,
    )
    from workflow.producers.goal_pool import repo_root_path
    from workflow.producers.node_bid import paid_market_enabled

    if not paid_market_enabled():
        return _paid_market_not_available()
    uid = universe_id or _default_universe()
    udir = _universe_dir(uid)
    if not udir.is_dir():
        return json.dumps({"error": f"Universe '{uid}' not found."})
    if not node_def_id:
        return json.dumps({"error": "node_def_id required."})

    if inputs_json.strip():
        try:
            inputs = json.loads(inputs_json)
        except json.JSONDecodeError as exc:
            return json.dumps({"error": f"inputs_json invalid JSON: {exc}"})
    else:
        inputs = {}
    ok, reason = validate_node_bid_inputs(inputs)
    if not ok:
        return json.dumps({
            "status": "rejected",
            "error": f"invalid_inputs: {reason}",
        })

    try:
        bid_value = float(bid)
    except (TypeError, ValueError):
        return json.dumps({
            "status": "rejected",
            "error": "bid must be numeric",
        })
    if bid_value < 0:
        return json.dumps({
            "status": "rejected",
            "error": "bid must be >= 0",
        })

    try:
        repo_root = repo_root_path(udir)
    except RuntimeError as exc:
        return json.dumps({
            "status": "rejected",
            "error": "repo_root_not_resolvable",
            "hint": (
                "Set WORKFLOW_REPO_ROOT or run the daemon from inside "
                "a git checkout. Detail: " + str(exc)
            ),
        })

    from datetime import datetime, timezone
    source = os.environ.get("UNIVERSE_SERVER_USER", "anonymous")
    node_bid_id = new_node_bid_id()
    payload = {
        "node_bid_id": node_bid_id,
        "node_def_id": node_def_id,
        "required_llm_type": required_llm_type or "",
        "inputs": dict(inputs),
        "bid": bid_value,
        "submitted_by": source,
        "status": "open",
        "evidence_url": "",
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        out_path = write_node_bid_post(repo_root, payload)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": f"post failed: {exc}"})

    rel_path = (
        out_path.relative_to(repo_root)
        if out_path.is_relative_to(repo_root)
        else out_path
    )
    return json.dumps({
        "universe_id": uid,
        "status": "posted",
        "node_bid_id": node_bid_id,
        "node_def_id": node_def_id,
        "path": str(out_path),
        "bid": bid_value,
        "required_llm_type": required_llm_type or "",
        "next_step": (
            f"To make this bid visible to cross-host daemons, run: "
            f"git add {rel_path} && git commit && git push"
        ),
    })


def _action_give_direction(
    universe_id: str = "",
    text: str = "",
    category: str = "direction",
    target: str = "",
    **_kwargs: Any,
) -> str:
    uid = universe_id or _default_universe()
    udir = _universe_dir(uid)
    if not udir.is_dir():
        return json.dumps({"error": f"Universe '{uid}' not found."})

    valid_categories = {"direction", "protect", "concern", "observation", "error"}
    if category not in valid_categories:
        category = "direction"

    try:
        from workflow.notes import add_note as _add_note

        udir.mkdir(parents=True, exist_ok=True)
        note = _add_note(
            udir,
            source="user",
            text=text,
            category=category,
            target=target or None,
        )
        return json.dumps({
            "universe_id": uid,
            "note_id": note.id,
            "category": category,
            "status": "written",
            "note": "Direction delivered. The daemon reads notes at scene boundaries.",
        })
    except Exception as exc:
        return json.dumps({"error": f"Failed to add note: {exc}"})


def _action_query_world(
    universe_id: str = "",
    query_type: str = "facts",
    filter_text: str = "",
    limit: int = 20,
    **_kwargs: Any,
) -> str:
    uid = universe_id or _default_universe()
    udir = _universe_dir(uid)
    if not udir.is_dir():
        return json.dumps({"error": f"Universe '{uid}' not found."})

    if query_type == "characters":
        data = _read_json(udir / "characters.json")
    elif query_type == "promises":
        data = _read_json(udir / "promises.json")
    elif query_type == "timeline":
        data = _read_json(udir / "timeline.json")
    else:
        data = _read_json(udir / "facts.json")

    if data is None:
        return _query_world_db(udir, uid, query_type, filter_text, limit)

    if isinstance(data, list) and filter_text:
        lower_filter = filter_text.lower()
        data = [
            item for item in data
            if lower_filter in json.dumps(item, default=str).lower()
        ]

    if isinstance(data, list):
        data = data[:limit]

    return json.dumps({
        "universe_id": uid,
        "query_type": query_type,
        "results": data,
        "count": len(data) if isinstance(data, list) else 1,
    }, default=str)


def _query_world_db(
    udir: Path, uid: str, query_type: str, filter_text: str, limit: int,
) -> str:
    """Query the SQLite world-state stores.

    World state is split across two DBs today:
      - story.db       — extracted_facts, character_states, promises
                         (written by the commit pipeline)
      - knowledge.db   — entities, facts, edges, communities
                         (written by the KG pipeline)

    A single `query_type` may live in either DB. We probe known candidate
    (db, table) pairs in priority order and return the first one that
    contains data. This is the source-of-truth routing — previous versions
    of this function pointed `characters -> entities` in story.db, which
    never existed and surfaced to users as "entities table missing". The
    actual character data is in story.db::character_states.
    """
    # Each entry: (db_filename, table_name). Order is priority: first table
    # that exists AND has rows wins. If none have rows, the first table that
    # exists is queried (possibly returning an empty list but not "missing").
    SOURCES: dict[str, list[tuple[str, str]]] = {
        "facts": [
            # commit-pipeline facts (richest: 282 rows on sporemarch)
            ("story.db", "extracted_facts"),
            # KG-native facts (written by the knowledge pipeline)
            ("knowledge.db", "facts"),
        ],
        "characters": [
            ("story.db", "character_states"),
            ("knowledge.db", "entities"),
        ],
        "promises": [
            ("story.db", "promises"),
        ],
        "timeline": [
            # No timeline table exists in either DB today. Reserved for a
            # future world-state pipeline; surfaces as "not recorded yet"
            # rather than "missing".
        ],
    }

    candidates = SOURCES.get(query_type, SOURCES["facts"])
    if not candidates:
        return json.dumps({
            "universe_id": uid,
            "query_type": query_type,
            "results": [],
            "count": 0,
            "note": (
                f"No store for query_type='{query_type}' yet. "
                "Valid types: facts, characters, promises."
            ),
        })

    import sqlite3

    # Pick the first (db, table) pair that exists. Prefer ones with data.
    chosen: tuple[str, str] | None = None
    fallback_empty: tuple[str, str] | None = None
    checked: list[str] = []
    for dbname, table in candidates:
        db_path = udir / dbname
        checked.append(f"{dbname}::{table}")
        if not db_path.exists():
            continue
        try:
            probe = sqlite3.connect(str(db_path))
            try:
                row = probe.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name=?",
                    (table,),
                ).fetchone()
                if not row:
                    continue
                count_row = probe.execute(
                    f'SELECT COUNT(*) FROM "{table}"'
                ).fetchone()
                has_rows = count_row and count_row[0] > 0
            finally:
                probe.close()
        except sqlite3.Error:
            continue
        if has_rows:
            chosen = (dbname, table)
            break
        if fallback_empty is None:
            fallback_empty = (dbname, table)

    if chosen is None and fallback_empty is None:
        return json.dumps({
            "universe_id": uid,
            "query_type": query_type,
            "results": [],
            "count": 0,
            "note": (
                f"World-state not initialized for query_type='{query_type}'. "
                f"Checked: {', '.join(checked)}."
            ),
        })

    dbname, table = chosen or fallback_empty  # type: ignore[misc]
    db_path = udir / dbname

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if filter_text:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [row["name"] for row in cursor.fetchall()]
            text_cols = [c for c in columns if c not in ("id", "rowid")]

            where_parts = [f"{c} LIKE ?" for c in text_cols]
            where_clause = " OR ".join(where_parts) if where_parts else "1=1"
            params = [f"%{filter_text}%" for _ in text_cols]

            cursor.execute(
                f"SELECT * FROM {table} WHERE {where_clause} LIMIT ?",
                params + [limit],
            )
        else:
            cursor.execute(f"SELECT * FROM {table} LIMIT ?", (limit,))

        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()

        response: dict[str, Any] = {
            "universe_id": uid,
            "query_type": query_type,
            "results": rows,
            "count": len(rows),
            "source": f"{dbname}::{table}",
        }
        if not rows and chosen is None:
            response["note"] = (
                f"Table '{table}' exists in {dbname} but has no rows yet."
            )
        return json.dumps(response, default=str)

    except Exception as exc:
        return json.dumps({"error": f"DB query failed: {exc}"})


def _action_read_premise(universe_id: str = "", **_kwargs: Any) -> str:
    uid = universe_id or _default_universe()
    udir = _universe_dir(uid)
    program_path = udir / "PROGRAM.md"

    content = _read_text(program_path)
    if not content:
        return json.dumps({
            "universe_id": uid,
            "premise": None,
            "note": "No premise set. Use action='set_premise' to create one.",
        })
    # Read-time fallback: decode any pre-existing files that were written
    # with literal \n sequences by a buggy client before the write-side fix.
    return json.dumps({
        "universe_id": uid,
        "premise": _normalize_escaped_text(content),
    })


def _normalize_escaped_text(text: str) -> str:
    """Convert literal escape sequences (``\\n``, ``\\r``, ``\\t``) to real
    characters when the input looks accidentally double-encoded.

    Some MCP clients transmit multi-line strings as JSON string literals
    and the receiving end sees the escape sequences verbatim. Premise
    markdown is prose — writers essentially never want the 2-character
    literal ``\\n`` sequence in that prose. A text with literal ``\\n``
    sequences is therefore treated as double-encoded, even if it also has
    one or two real newlines (e.g. a trailing file-end newline). If a
    future caller legitimately needs the literal 2-char sequence, they
    can double-escape as ``\\\\n``.
    """
    if not text:
        return text
    if "\\n" not in text and "\\r" not in text and "\\t" not in text:
        return text
    return (
        text
        .replace("\\r\\n", "\n")
        .replace("\\n", "\n")
        .replace("\\r", "\n")
        .replace("\\t", "\t")
    )


def _action_set_premise(universe_id: str = "", text: str = "", **_kwargs: Any) -> str:
    uid = universe_id or _default_universe()
    udir = _universe_dir(uid)
    program_path = udir / "PROGRAM.md"

    if not text.strip():
        return json.dumps({"error": "Premise text cannot be empty."})
    text = _normalize_escaped_text(text)
    try:
        udir.mkdir(parents=True, exist_ok=True)
        program_path.write_text(text, encoding="utf-8")
        return json.dumps({
            "universe_id": uid,
            "status": "updated",
            "note": "Premise saved. The daemon will read it at next startup.",
        })
    except OSError as exc:
        return json.dumps({"error": f"Failed to write premise: {exc}"})


def _action_add_canon(
    universe_id: str = "",
    filename: str = "",
    text: str = "",
    provenance_tag: str = "",
    **_kwargs: Any,
) -> str:
    """Add inline canon text. Small uploads only; large files should use
    ``add_canon_from_path`` so the LLM never has to copy content verbatim
    into the tool-call arg.

    Memory-scope Stage 2b landed the ``synthesize_source`` signal as the
    trigger for premise/canon/entity synthesis. This path now routes
    through :func:`workflow.ingestion.core.ingest_file` so the signal
    fires (the earlier direct-write path bypassed it, breaking MCP
    uploads). Files still land under ``canon/sources/`` on user
    uploads; the daemon's worldbuild node picks up the signal and
    synthesizes canon from the source.
    """
    uid = universe_id or _default_universe()
    udir = _universe_dir(uid)
    canon_dir = udir / "canon"

    safe_name = Path(filename).name
    if not safe_name:
        return json.dumps({"error": "Invalid filename."})

    try:
        data = text.encode("utf-8")
    except UnicodeEncodeError as exc:
        return json.dumps({"error": f"Failed to encode text as UTF-8: {exc}"})

    from workflow.ingestion.core import ingest_file

    try:
        canon_dir.mkdir(parents=True, exist_ok=True)
        result = ingest_file(
            canon_dir=canon_dir,
            filename=safe_name,
            data=data,
            universe_path=udir,
            user_upload=True,
        )

        if provenance_tag:
            meta_path = canon_dir / f".{safe_name}.meta.json"
            meta = {
                "provenance": provenance_tag,
                "added": datetime.now(timezone.utc).isoformat(),
                "source": _current_actor(),
            }
            meta_path.write_text(json.dumps(meta), encoding="utf-8")

        return json.dumps({
            "universe_id": uid,
            "filename": safe_name,
            "status": "written",
            "provenance": provenance_tag or "untagged",
            "routed_to": result.routed_to,
            "bytes_written": result.byte_count,
            "synthesis_signal_emitted": result.signal_emitted,
            "note": (
                "Canon file ingested via ingest_file(). The daemon will "
                "pick up the synthesize_source signal on its next cycle."
            ),
        })
    except OSError as exc:
        return json.dumps({"error": f"Failed to write canon file: {exc}"})


def _action_add_canon_from_path(
    universe_id: str = "",
    path: str = "",
    filename: str = "",
    provenance_tag: str = "",
    **_kwargs: Any,
) -> str:
    """Ingest a file from the server's filesystem into a universe's canon.

    Solves the "copy-through-tool-arg" defect of ``add_canon``: for
    large uploads (>20K tokens) the LLM cannot reliably reproduce the
    file content verbatim in a tool-call arg — summarization drift,
    max-output cutoff, and JSON-escaping errors silently corrupt the
    upload. This path reads the file server-side instead, preserving
    the "user uploads are authoritative" hard rule.

    Trust-model mitigations (task #15):

    - ``WORKFLOW_UPLOAD_WHITELIST`` (env var, optional): colon/
      semicolon-separated absolute-path prefixes. When set, a path
      not under any prefix is rejected with a clear error. When
      unset, any absolute path is accepted and a WARNING is logged
      at startup. The whitelist is opt-in enforcement — the demo
      UX is open-by-default.
    - Response includes ``preview_first_200_bytes``: the first ~200
      UTF-8 characters of the ingested file so the host can see in
      the MCP response what was actually stored (silent substitution
      becomes detectable without an out-of-band read).

    Parameters
    ----------
    universe_id : str
        Target universe. Defaults to the active universe.
    path : str
        **Absolute** path on the server's filesystem. The MCP client's
        LLM never reads the file content through this param — it just
        references a path the host has already placed.
    filename : str, optional
        Filename to store the file under in ``canon/sources/``. Defaults
        to the basename of ``path``.
    provenance_tag : str, optional
        Source tag (e.g. "published novel", "rough notes"). Defaults
        to "user_upload".
    """
    if not path:
        return json.dumps({"error": "path is required."})

    src = Path(path)
    if not src.is_absolute():
        return json.dumps({
            "error": (
                "path must be absolute — this action reads from the "
                "server's filesystem, not the MCP client's context."
            ),
        })

    # Whitelist enforcement (opt-in via WORKFLOW_UPLOAD_WHITELIST).
    # Resolve src to handle symlinks + ``..`` traversals before the
    # prefix check; otherwise ``/allowed/../secret`` would slip past.
    whitelist = _upload_whitelist_prefixes()
    if whitelist is not None:
        try:
            resolved = src.resolve(strict=False)
        except OSError as exc:
            return json.dumps({"error": f"Failed to resolve path: {exc}"})
        if not any(
            resolved.is_relative_to(prefix) for prefix in whitelist
        ):
            return json.dumps({
                "error": (
                    f"Path is not under any WORKFLOW_UPLOAD_WHITELIST "
                    f"prefix. Resolved={resolved!s}, "
                    f"allowed_prefixes={[str(p) for p in whitelist]}."
                ),
            })

    if not src.exists():
        return json.dumps({"error": f"File not found: {path}"})
    if not src.is_file():
        return json.dumps({"error": f"Not a regular file: {path}"})

    try:
        data = src.read_bytes()
    except OSError as exc:
        return json.dumps({"error": f"Failed to read file: {exc}"})

    # Reject non-UTF-8 early with a clear error. The daemon's canon
    # pipeline assumes UTF-8; binary or latin-1 files would silently
    # corrupt synthesis.
    try:
        decoded = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        return json.dumps({
            "error": (
                f"File is not valid UTF-8 ({exc.reason} at byte "
                f"{exc.start}). Convert to UTF-8 before ingesting."
            ),
        })

    uid = universe_id or _default_universe()
    udir = _universe_dir(uid)
    canon_dir = udir / "canon"
    safe_name = Path(filename).name if filename else src.name
    if not safe_name:
        return json.dumps({"error": "Invalid filename."})

    from workflow.ingestion.core import ingest_file

    try:
        canon_dir.mkdir(parents=True, exist_ok=True)
        result = ingest_file(
            canon_dir=canon_dir,
            filename=safe_name,
            data=data,
            universe_path=udir,
            user_upload=True,
        )

        tag = provenance_tag or "user_upload"
        meta_path = canon_dir / f".{safe_name}.meta.json"
        meta = {
            "provenance": tag,
            "source_path": str(src),
            "added": datetime.now(timezone.utc).isoformat(),
            "source": _current_actor(),
        }
        meta_path.write_text(json.dumps(meta), encoding="utf-8")

        return json.dumps({
            "universe_id": uid,
            "filename": safe_name,
            "canonical_path": str(canon_dir / "sources" / safe_name),
            "bytes_written": result.byte_count,
            "synthesis_signal_emitted": result.signal_emitted,
            "routed_to": result.routed_to,
            "provenance": tag,
            # Task #15: echo the first 200 decoded chars so the host
            # can confirm in the MCP response what was ingested —
            # silent file-swap becomes detectable without an
            # out-of-band read.
            "preview_first_200_bytes": decoded[:200],
            "note": (
                "File ingested from server path. The daemon will pick "
                "up the synthesize_source signal on its next cycle."
            ),
        })
    except OSError as exc:
        return json.dumps({"error": f"Failed to ingest file: {exc}"})


def _action_list_canon(
    universe_id: str = "",
    **_kwargs: Any,
) -> str:
    """List all canon documents in a universe with metadata."""
    uid = universe_id or _default_universe()
    udir = _universe_dir(uid)
    canon_dir = udir / "canon"

    if not canon_dir.is_dir():
        return json.dumps({"universe_id": uid, "canon_files": [], "note": "No canon directory."})

    files = []
    for f in sorted(canon_dir.iterdir()):
        if f.is_file() and not f.name.startswith("."):
            entry: dict[str, Any] = {
                "filename": f.name,
                "size_bytes": f.stat().st_size,
            }
            # Check for provenance metadata
            meta_path = canon_dir / f".{f.name}.meta.json"
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    entry["provenance"] = meta.get("provenance", "")
                    entry["added"] = meta.get("added", "")
                    entry["source"] = meta.get("source", "")
                except (json.JSONDecodeError, OSError):
                    pass
            files.append(entry)

    return json.dumps({"universe_id": uid, "canon_files": files, "count": len(files)})


def _action_read_canon(
    universe_id: str = "",
    filename: str = "",
    **_kwargs: Any,
) -> str:
    """Read the contents of a specific canon document."""
    uid = universe_id or _default_universe()
    udir = _universe_dir(uid)
    canon_dir = udir / "canon"

    safe_name = Path(filename).name
    if not safe_name:
        return json.dumps({"error": "Filename required. Use list_canon to see available files."})

    target = canon_dir / safe_name
    if not target.is_file():
        return json.dumps({
            "error": f"Canon file '{safe_name}' not found.",
            "hint": "Use list_canon to see available files.",
        })

    try:
        content = target.read_text(encoding="utf-8")
        entry: dict[str, Any] = {
            "universe_id": uid,
            "filename": safe_name,
            "size_bytes": target.stat().st_size,
            "content": content,
        }
        # Attach provenance if available
        meta_path = canon_dir / f".{safe_name}.meta.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                entry["provenance"] = meta.get("provenance", "")
            except (json.JSONDecodeError, OSError):
                pass
        return json.dumps(entry)
    except OSError as exc:
        return json.dumps({"error": f"Failed to read canon file: {exc}"})


def _action_control_daemon(
    universe_id: str = "",
    text: str = "",
    **_kwargs: Any,
) -> str:
    action = text.strip().lower()
    uid = universe_id or _default_universe()
    udir = _universe_dir(uid)
    if not udir.is_dir():
        return json.dumps({"error": f"Universe '{uid}' not found."})

    pause_path = udir / ".pause"

    if action == "pause":
        try:
            udir.mkdir(parents=True, exist_ok=True)
            pause_path.write_text(
                datetime.now(timezone.utc).isoformat(), encoding="utf-8",
            )
            return json.dumps({
                "universe_id": uid,
                "action": "pause",
                "status": "signal_written",
                "note": "Daemon will pause at the next scene boundary.",
            })
        except OSError as exc:
            return json.dumps({"error": f"Failed to write pause signal: {exc}"})

    elif action == "resume":
        if not pause_path.exists():
            return json.dumps({
                "universe_id": uid,
                "action": "resume",
                "status": "not_paused",
                "note": "Daemon was not paused.",
            })
        try:
            pause_path.unlink()
            return json.dumps({
                "universe_id": uid,
                "action": "resume",
                "status": "resumed",
                "note": "Pause signal removed. Daemon will resume.",
            })
        except OSError as exc:
            return json.dumps({"error": f"Failed to remove pause: {exc}"})

    elif action == "status":
        status = _read_json(udir / "status.json")
        liveness = _daemon_liveness(
            udir, status if isinstance(status, dict) else None,
        )
        # Count pending unreconciled writes so host sees drift when a
        # git commit failed but SQLite accepted the write.
        try:
            pending = list_unreconciled_writes(_base_path(), limit=500)
            pending_count = len(pending)
        except Exception:
            pending_count = 0
        return json.dumps({
            "universe_id": uid,
            "action": "status",
            "phase": liveness["phase"],
            "phase_human": liveness["phase_human"],
            "is_paused": liveness["is_paused"],
            "has_premise": liveness["has_premise"],
            "has_work": liveness["has_work"],
            "last_activity_at": liveness["last_activity_at"],
            "staleness": liveness["staleness"],
            "word_count": liveness["word_count"],
            "word_count_sample": liveness["word_count_sample"],
            "accept_rate": liveness["accept_rate"],
            "accept_rate_sample": liveness["accept_rate_sample"],
            "unreconciled_writes_count": pending_count,
        })

    else:
        return json.dumps({
            "error": f"Unknown daemon action '{action}'. Use: pause, resume, status.",
        })


def _action_get_activity(
    universe_id: str = "",
    limit: int = 30,
    **_kwargs: Any,
) -> str:
    uid = universe_id or _default_universe()
    udir = _universe_dir(uid)
    log_path = udir / "activity.log"

    limit = min(max(limit, 1), 200)

    content = _read_text(log_path)
    if not content:
        return json.dumps({
            "universe_id": uid,
            "lines": [],
            "note": "No activity log found. The daemon may not have run yet.",
        })

    all_lines = content.strip().splitlines()
    tail = all_lines[-limit:]
    return json.dumps({
        "universe_id": uid,
        "lines": tail,
        "count": len(tail),
        "total": len(all_lines),
    })


# Pattern: "[2026-04-19 20:30:00] [dispatch_guard] message body" or
# legacy "[2026-04-19 20:30:00] untagged message". Lenient — any line
# that can't be parsed is surfaced in the 'raw' field so callers still
# see the source text when they need it.
_ACTIVITY_LINE_RE = re.compile(
    r"^\[(?P<ts>[^\]]+)\](?:\s*\[(?P<tag>[^\]]+)\])?\s*(?P<msg>.*)$"
)

# Domain caveat for dispatch_guard queries with zero matching events.
# dispatch_guard only emits when the daemon actively dispatches a scene;
# empty results could mean (a) no overshoots fired, OR (b) the daemon did
# not dispatch at all in this window (endpoint unbound, daemon paused,
# universe idle). Chatbot must not read empty-list as "no overshoots."
_DISPATCH_GUARD_ABSENCE_CAVEAT = (
    "Empty dispatch_guard list does not prove no overshoots — the daemon "
    "may not have dispatched any scenes in this window (endpoint unbound, "
    "daemon paused, or universe idle). Verify daemon ran before inferring "
    "'guard never needed to fire'."
)


def _parse_activity_line(line: str) -> dict[str, str]:
    """Split ``[TS] [TAG] MSG`` (or legacy ``[TS] MSG``) into fields.

    Returns dict with keys ``ts``, ``tag`` (empty when untagged),
    ``message``, ``raw``. Unparseable lines fall back to all-empty
    fields + ``raw`` holding the original string.
    """
    line = line.rstrip("\n")
    match = _ACTIVITY_LINE_RE.match(line)
    if not match:
        return {"ts": "", "tag": "", "message": "", "raw": line}
    return {
        "ts": match.group("ts") or "",
        "tag": match.group("tag") or "",
        "message": match.group("msg") or "",
        "raw": line,
    }


def _action_get_recent_events(
    universe_id: str = "",
    tag: str = "",
    limit: int = 30,
    **_kwargs: Any,
) -> str:
    """Tag-filterable view of activity.log for chatbot observability.

    Reads the universe's ``activity.log`` tail and returns entries as
    structured dicts (``ts`` / ``tag`` / ``message`` / ``raw``). When
    ``tag`` is non-empty, only entries whose tag starts with ``tag``
    are returned — tag prefix-match so a caller can filter ``"dispatch"``
    and get both ``dispatch_guard`` and ``dispatch_execution``.

    Evidence + caveat fields follow the self-auditing-tools pattern:
      - ``events``: matching structured entries (most recent first).
      - ``source``: ``"activity.log"`` — the audit surface backing the
        answer.
      - ``caveats``: list of strings explaining any observation caveats
        (e.g. "log file missing", "tag filter matched 0 of N entries").

    Args:
        universe_id: Target universe (falls back to default).
        tag: Optional tag prefix filter (empty = all entries).
        limit: Max entries to return (1..500, clamped).
    """
    uid = universe_id or _default_universe()
    udir = _universe_dir(uid)
    log_path = udir / "activity.log"

    limit = min(max(limit, 1), 500)
    caveats: list[str] = []

    content = _read_text(log_path)
    if not content:
        missing_caveats = [
            "No activity.log found. The daemon may not have run yet "
            "in this universe, or the log was cleared.",
        ]
        if tag == "dispatch_guard":
            missing_caveats.append(_DISPATCH_GUARD_ABSENCE_CAVEAT)
        return json.dumps({
            "universe_id": uid,
            "events": [],
            "source": "activity.log",
            "tag_filter": tag,
            "caveats": missing_caveats,
        })

    all_lines = content.strip().splitlines()
    parsed = [_parse_activity_line(line) for line in all_lines]

    if tag:
        matched = [p for p in parsed if p["tag"].startswith(tag)]
        if not matched:
            caveats.append(
                f"Tag filter {tag!r} matched 0 of {len(parsed)} entries. "
                f"Known tags in file: "
                f"{sorted({p['tag'] for p in parsed if p['tag']})[:10]}."
            )
            if tag == "dispatch_guard":
                caveats.append(_DISPATCH_GUARD_ABSENCE_CAVEAT)
    else:
        matched = parsed

    # Return most-recent first so chatbot readers see newest events at top.
    tail = matched[-limit:]
    events = list(reversed(tail))

    untagged_count = sum(1 for p in parsed if not p["tag"])
    if untagged_count and not tag:
        caveats.append(
            f"{untagged_count} of {len(parsed)} activity lines carry no tag "
            "(pre-tagging call sites or legacy entries)."
        )

    return json.dumps({
        "universe_id": uid,
        "events": events,
        "source": "activity.log",
        "tag_filter": tag,
        "total_lines": len(all_lines),
        "matched": len(matched),
        "returned": len(events),
        "caveats": caveats,
    })


def _action_get_ledger(universe_id: str = "", limit: int = 50, **_kwargs: Any) -> str:
    uid = universe_id or _default_universe()
    udir = _universe_dir(uid)

    ledger_path = udir / "ledger.json"
    data = _read_json(ledger_path)
    if not data or not isinstance(data, list):
        return json.dumps({"universe_id": uid, "entries": [], "note": "No ledger entries yet."})

    entries = list(reversed(data))[:limit]
    return json.dumps({"universe_id": uid, "entries": entries, "count": len(entries)})


def _action_switch_universe(universe_id: str = "", **_kwargs: Any) -> str:
    if not universe_id:
        return json.dumps({"error": "universe_id is required."})

    uid = universe_id
    udir = _universe_dir(uid)
    if not udir.is_dir():
        return json.dumps({
            "error": f"Universe '{uid}' not found.",
            "available": [
                d.name for d in _base_path().iterdir()
                if d.is_dir() and not d.name.startswith(".")
            ] if _base_path().is_dir() else [],
        })

    # Write the active universe marker — the tray app watches this file
    marker = _base_path() / ".active_universe"
    try:
        marker.write_text(uid, encoding="utf-8")
    except OSError as exc:
        return json.dumps({"error": f"Failed to write active universe marker: {exc}"})

    return json.dumps({
        "universe_id": uid,
        "status": "switching",
        "note": f"Daemon will restart on '{uid}' within ~10 seconds.",
    })


def _action_create_universe(
    universe_id: str = "",
    text: str = "",
    **_kwargs: Any,
) -> str:
    if not universe_id:
        return json.dumps({"error": "universe_id is required."})

    uid = universe_id
    base = _base_path()
    udir = base / uid

    # Sanitize
    if "/" in uid or "\\" in uid or uid.startswith("."):
        return json.dumps({"error": "Invalid universe_id."})
    if udir.exists():
        return json.dumps({"error": f"Universe '{uid}' already exists."})

    try:
        udir.mkdir(parents=True, exist_ok=True)
        # Write premise if provided
        if text.strip():
            (udir / "PROGRAM.md").write_text(
                _normalize_escaped_text(text), encoding="utf-8",
            )

        # Initialize empty state files
        (udir / "notes.json").write_text("[]", encoding="utf-8")
        (udir / "activity.log").write_text("", encoding="utf-8")

        result: dict[str, Any] = {
            "universe_id": uid,
            "status": "created",
            "has_premise": bool(text.strip()),
        }

        # Auto-switch the daemon to the new universe
        marker = base / ".active_universe"
        marker.write_text(uid, encoding="utf-8")
        result["note"] = (
            f"Universe '{uid}' created. "
            "Daemon will switch to it within ~10 seconds."
        )

        return json.dumps(result)
    except OSError as exc:
        return json.dumps({"error": f"Failed to create universe: {exc}"})


# ═══════════════════════════════════════════════════════════════════════════
# TOOL 2 — Extensions (node registration system)
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class NodeRegistration:
    """A user-contributed LangGraph node."""

    node_id: str
    display_name: str
    description: str
    phase: str  # orient, plan, draft, commit, learn, reflect, worldbuild, custom
    input_keys: list[str]
    output_keys: list[str]
    source_code: str
    dependencies: list[str] = field(default_factory=list)
    author: str = "anonymous"
    registered_at: str = ""
    enabled: bool = True
    approved: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NodeRegistration:
        return cls(**{
            k: v for k, v in data.items()
            if k in cls.__dataclass_fields__
        })


STANDALONE_NODES_BRANCH_ID = "__standalone_nodes__"
"""Well-known branch definition ID for individually registered nodes
that aren't part of a full graph topology yet."""


def _nodes_path() -> Path:
    """Path to the legacy JSON node registry (used for migration only)."""
    return _base_path() / ".node_registry.json"


def _ensure_standalone_branch(base_path: Path) -> None:
    """Ensure the standalone-nodes branch definition exists in SQLite.

    If the branch doesn't exist and a legacy .node_registry.json file
    does, migrate its contents automatically.
    """
    from workflow.daemon_server import (
        get_branch_definition,
        initialize_author_server,
        save_branch_definition,
    )

    initialize_author_server(base_path)

    try:
        get_branch_definition(base_path, branch_def_id=STANDALONE_NODES_BRANCH_ID)
        return  # already exists
    except KeyError:
        pass

    # Migrate from legacy JSON if it exists
    legacy_nodes: list[dict[str, Any]] = []
    json_path = _nodes_path()
    if json_path.exists():
        data = _read_json(json_path)
        if isinstance(data, list):
            legacy_nodes = data
            logger.info(
                "Migrating %d nodes from .node_registry.json to SQLite",
                len(legacy_nodes),
            )

    save_branch_definition(
        base_path,
        branch_def={
            "branch_def_id": STANDALONE_NODES_BRANCH_ID,
            "name": "Standalone Nodes",
            "description": "Individually registered nodes not yet part of a full graph topology.",
            "author": "system",
            "tags": ["system", "standalone"],
            "nodes": legacy_nodes,
            "edges": [],
            "state_schema": [],
            "published": False,
        },
    )


def _load_nodes() -> list[dict[str, Any]]:
    """Load all registered nodes from SQLite."""
    from workflow.daemon_server import get_branch_definition

    base = _base_path()
    _ensure_standalone_branch(base)

    try:
        branch = get_branch_definition(
            base, branch_def_id=STANDALONE_NODES_BRANCH_ID
        )
        return branch.get("graph", {}).get("nodes", [])
    except KeyError:
        return []


def _save_nodes(nodes: list[dict[str, Any]]) -> None:
    """Save the node registry to SQLite."""
    from workflow.daemon_server import update_branch_definition

    base = _base_path()
    _ensure_standalone_branch(base)

    update_branch_definition(
        base,
        branch_def_id=STANDALONE_NODES_BRANCH_ID,
        updates={"nodes": nodes},
    )


VALID_PHASES = {
    "orient", "plan", "draft", "commit", "learn",
    "reflect", "worldbuild", "custom",
}

ALLOWED_DEPENDENCIES = {
    "requests", "httpx", "json", "re", "datetime", "collections",
    "dataclasses", "typing", "math", "statistics", "textwrap",
    "difflib", "hashlib", "urllib", "pathlib",
}


@mcp.tool(
    title="Graph Extensions",
    tags={"extensions", "nodes", "plugins", "customization"},
    annotations=ToolAnnotations(
        title="Graph Extensions",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    ),
)
def extensions(
    action: str,
    node_id: str = "",
    display_name: str = "",
    description: str = "",
    phase: str = "",
    input_keys: str = "",
    output_keys: str = "",
    source_code: str = "",
    dependencies: str = "",
    enabled_only: bool = True,
    branch_def_id: str = "",
    name: str = "",
    domain_id: str = "",
    author: str = "",
    from_node: str = "",
    to_node: str = "",
    prompt_template: str = "",
    field_name: str = "",
    field_type: str = "",
    reducer: str = "",
    field_default: str = "",
    run_id: str = "",
    inputs_json: str = "",
    run_name: str = "",
    status: str = "",
    since_step: int = -1,
    max_wait_s: int = 60,
    limit: int = 50,
    spec_json: str = "",
    changes_json: str = "",
    judgment_text: str = "",
    judgment_id: str = "",
    tags: str = "",
    run_a_id: str = "",
    run_b_id: str = "",
    field: str = "",
    value: str = "",
    node_ids: str = "",
    context: str = "",
    triggered_by_judgment_id: str = "",
    to_version: str = "",
    goal_id: str = "",
    node_ref_json: str = "",
    intent: str = "",
    node_query: str = "",
    force: bool = False,
    project_id: str = "",
    key: str = "",
    key_prefix: str = "",
    expected_version: str = "",
    recursion_limit_override: str = "",
    filters_json: str = "",
    select: str = "",
    aggregate_json: str = "",
    branch_spec_json: str = "",
    from_run_id: str = "",
    to_node_id: str = "",
    message_type: str = "",
    body_json: str = "",
    reply_to_message_id: str = "",
    message_types: str = "",
    message_id: str = "",
    since: str = "",
    branch_version_id: str = "",
    parent_version_id: str = "",
    notes: str = "",
    lock_id: str = "",
    escrow_amount: int = 0,
    escrow_currency: str = "MicroToken",
    escrow_recipient_id: str = "",
    escrow_evidence: str = "",
    escrow_reason: str = "",
    event_id: str = "",
    event_type: str = "",
    event_date: str = "",
    attested_by: str = "",
    cites_json: str = "",
    verifier_id: str = "",
    disputed_by: str = "",
    retracted_by: str = "",
    schedule_id: str = "",
    cron_expr: str = "",
    interval_seconds: float = 0.0,
    owner_actor: str = "",
    inputs_template_json: str = "",
    skip_if_running: bool = False,
    subscription_id: str = "",
    active_only: bool = True,
    outcome_id: str = "",
    evidence_url: str = "",
    gate_event_id: str = "",
    outcome_payload_json: str = "",
    outcome_note: str = "",
    parent_branch_def_id: str = "",
    child_branch_def_id: str = "",
    contribution_kind: str = "remix",
    credit_share: float = 0.0,
    max_depth: int = 10,
    # Surgical-rollback args (Task #22 Phase B). Routed via _RUN_ACTIONS
    # to rollback_merge / get_rollback_history. `branch_version_id` is
    # already declared above for run_branch_version.
    reason: str = "",
    severity: str = "P1",
    since_days: int = 7,
) -> str:
    """Workflow-builder surface: design, edit, run, judge custom AI graphs.

    See `control_station`, `extension_guide`, and `branch_design_guide`
    prompts for operating guidance and worked examples. Load the
    `control_station` prompt before first use of this connector.

    Action groups:
    - Node lifecycle: register, list, inspect, approve, disable, enable, remove.
    - Branch composite (prefer): build_branch (spec_json), patch_branch (changes_json).
    - Branch atomic: create_branch, add_node, connect_nodes, set_entry_point,
      add_state_field, update_node, validate_branch, delete_branch.
    - Branch ops: continue_branch, fork_tree, patch_nodes.
    - Branch query: describe_branch, get_branch, list_branches, search_nodes.
    - Run (Phase 3): run_branch, get_run, list_runs, stream_run, cancel_run,
      get_run_output.
    - Run extensions: wait_for_run, resume_run, query_runs, estimate_run_cost,
      run_branch_version.
    - Surgical rollback: rollback_merge (host-only), get_rollback_history.
    - Versioning: publish_version, get_branch_version, list_branch_versions.
    - Scheduler: schedule_branch, unschedule_branch, list_schedules,
      subscribe_branch, unsubscribe_branch, list_scheduler_subscriptions.
    - Project memory: project_memory_get, project_memory_set, project_memory_list.
    - Eval / iterate (Phase 4): judge_run, list_judgments, compare_runs,
      suggest_node_edit, get_node_output, rollback_node, list_node_versions.
    - Self-audit: get_routing_evidence, get_memory_scope_status.

    Feature-flag caveats — some action groups are conditionally available
    based on server flags (callers see structured `not_available` rather
    than tool-discovery hiding):
    - Outcome gates live in the separate `gates` tool, gated by
      GATES_ENABLED=1. When the flag is off, `gates` returns
      `{"status": "not_available"}` — unrelated to this tool, but worth
      knowing when discussing outcomes.
    - Paid-market actions on `gates` (stake_bonus / unstake_bonus /
      release_bonus) additionally require WORKFLOW_PAID_MARKET=on.
    - Goal-pool surfaces (`universe action=post_to_goal_pool` /
      `submit_node_bid`) require WORKFLOW_GOAL_POOL=on or
      WORKFLOW_PAID_MARKET=on respectively.
    - Tiered-memory-scope routing in `get_memory_scope_status` reflects
      whatever WORKFLOW_TIERED_SCOPE is set to today (Stage 1 monitoring
      is the default; Stage 2c flips it on).

    Node reuse across branches uses `node_ref_json`
    (`{"source": "standalone", "node_id": "..."}` or source=<branch_def_id>).
    A bare node_id colliding with a standalone registration is rejected;
    pass node_ref_json or intent="copy".

    `run_branch` is async (returns run_id; poll get_run or stream_run).
    `get_run` emits a ```mermaid``` diagram for Claude.ai auto-render.

    Args:
        action: Operation name.
        node_id / display_name / description / phase / input_keys /
            output_keys / source_code / dependencies / enabled_only:
            Single-node registration fields.
        branch_def_id: Target BranchDefinition for branch and run actions.
        name: Branch name (create_branch) or node id filter.
        domain_id / author: Branch metadata / list filters.
        from_node / to_node: Edge endpoints for connect_nodes. Use
            "START"/"END" for graph entry/exit.
        prompt_template: LLM template for prompt-template nodes (alternative
            to source_code).
        field_name / field_type / reducer / field_default: State schema
            field declaration (add_state_field).
        run_id: Target run for get_run / stream_run / cancel_run /
            get_run_output.
        inputs_json: JSON object of state field values for run_branch.
        run_name: Optional human label for this run.
        status: Filter for list_runs (queued/running/completed/failed/
            cancelled).
        since_step: Cursor for stream_run; returns events after this
            step index. Use -1 (default) for all.
        limit: Row cap for list_runs.
        spec_json: Full BranchDefinition JSON spec for build_branch.
            Shape: {name, description?, domain_id?, node_defs: [...],
            edges: [{from, to}, ...], state_schema?: [...], entry_point?}.
        changes_json: Ordered list of patch ops for patch_branch.
            Each op is {op: "add_node"|"remove_node"|"add_edge"|
            "remove_edge"|"add_state_field"|"remove_state_field"|
            "set_entry_point"|"update_node"|"set_name"|
            "set_description"|"set_tags"|"set_published"|"set_goal"|
            "unset_goal", ...fields}. Branch-level metadata ops
            (set_name/description/tags/published) preserve the
            branch_def_id, run history, and judgments — a label
            change no longer requires delete-and-rebuild.
        judgment_text: Natural-language judgment for judge_run. Required.
        judgment_id: Reserved for future cross-linking (unused in v1).
        tags: Comma-separated free-form tags for judge_run.
        run_a_id / run_b_id: Runs to compare via compare_runs.
        field: Optional single-field narrow for compare_runs and
            get_run_output.
        context: Optional extra user-context line for suggest_node_edit.
        triggered_by_judgment_id: Optional attribution for update_node —
            the judgment that motivated this edit. Surfaces in the
            node_edit_audit row so lineage shows "edit triggered by
            judgment X".
        to_version: Target version for rollback_node. Omit to rewind one
            step (to the immediately previous version).
        node_ref_json: Optional JSON for atomic add_node to reuse a node
            from another source. Shape:
            `{"source": "standalone" | "<branch_def_id>",
              "node_id": "X"}`. Snapshots the canonical body into this
            branch (copy semantics). Any inline fields you also pass
            (e.g. display_name) overlay the snapshot.
        intent: Consent flag for node-id collisions on add_node /
            build_branch / patch_branch add_node ops. Use `intent="copy"`
            to intentionally copy an existing standalone node. Omit to
            force the server to refuse silent shadowing.
        node_query: Free-text search string for `search_nodes`.
            Tokenized, substring-matched across node_id, display_name,
            description, and prompt_template preview.
        force: override `local_edit_conflict` refusal on branch write
            actions (create_branch / add_node / connect_nodes /
            set_entry_point / add_state_field) when the target YAML has
            uncommitted local edits. Default False — when a conflict
            exists the server returns a structured envelope
            `{"status": "local_edit_conflict", "conflicting_file": "...",
            "options": ["commit", "stash", "discard", "force"]}` (not
            an error). Present the options to the user, then retry with
            `force=True` only if the user explicitly chooses "force".
    """
    if action == "register":
        return _ext_register(
            node_id, display_name, description, phase,
            input_keys, output_keys, source_code, dependencies,
        )
    elif action == "list":
        return _ext_list(phase, enabled_only)
    elif action == "inspect":
        return _ext_inspect(node_id)
    elif action in ("approve", "disable", "enable", "remove"):
        return _ext_manage(node_id, action)

    # ── Phase 2: Community Branches ────────────────────────────────────────
    branch_kwargs: dict[str, Any] = {
        "branch_def_id": branch_def_id,
        "name": name,
        "description": description,
        "domain_id": domain_id,
        "author": author,
        "node_id": node_id,
        "display_name": display_name,
        "phase": phase,
        "source_code": source_code,
        "prompt_template": prompt_template,
        "input_keys": input_keys,
        "output_keys": output_keys,
        "from_node": from_node,
        "to_node": to_node,
        "field_name": field_name,
        "field_type": field_type,
        "reducer": reducer,
        "field_default": field_default,
        "spec_json": spec_json,
        "changes_json": changes_json,
        "field": field,
        "value": value,
        "node_ids": node_ids,
        "triggered_by_judgment_id": triggered_by_judgment_id,
        "goal_id": goal_id,
        "intent": intent,
        "query": node_query,
        "limit": limit,
        "force": force,
    }
    if node_ref_json:
        try:
            parsed_ref = json.loads(node_ref_json)
        except json.JSONDecodeError as exc:
            return json.dumps({
                "error": f"node_ref_json is not valid JSON: {exc}",
            })
        branch_kwargs["node_ref"] = parsed_ref
    branch_handler = _BRANCH_ACTIONS.get(action)
    if branch_handler is not None:
        return _dispatch_branch_action(action, branch_handler, branch_kwargs)

    # ── Phase 3: Graph Runner ──────────────────────────────────────────────
    run_kwargs: dict[str, Any] = {
        "branch_def_id": branch_def_id,
        "branch_version_id": branch_version_id,
        "run_id": run_id,
        "inputs_json": inputs_json,
        "run_name": run_name,
        "status": status,
        "since_step": since_step,
        "max_wait_s": max_wait_s,
        "limit": limit,
        "field_name": field_name,
        "recursion_limit_override": recursion_limit_override,
        "filters_json": filters_json,
        "select": select,
        "aggregate_json": aggregate_json,
        # Surgical-rollback args (Task #22 Phase B).
        "reason": reason,
        "severity": severity,
        "since_days": since_days,
    }
    run_handler = _RUN_ACTIONS.get(action)
    if run_handler is not None:
        return _dispatch_run_action(action, run_handler, run_kwargs)

    # ── Phase 4: Eval + iteration hooks ────────────────────────────────────
    judgment_kwargs: dict[str, Any] = {
        "branch_def_id": branch_def_id,
        "run_id": run_id,
        "node_id": node_id,
        "judgment_text": judgment_text,
        "judgment_id": judgment_id,
        "tags": tags,
        "run_a_id": run_a_id,
        "run_b_id": run_b_id,
        "field": field,
        "context": context,
        "limit": limit,
        "to_version": to_version,
    }
    judgment_handler = _JUDGMENT_ACTIONS.get(action)
    if judgment_handler is not None:
        return _dispatch_judgment_action(
            action, judgment_handler, judgment_kwargs,
        )

    # ── Project Memory ─────────────────────────────────────────────────────
    pm_kwargs: dict[str, Any] = {
        "project_id": project_id,
        "key": key,
        "key_prefix": key_prefix,
        "value": value,
        "expected_version": expected_version if expected_version else None,
        "limit": limit,
    }
    pm_handler = _PROJECT_MEMORY_ACTIONS.get(action)
    if pm_handler is not None:
        result_str = pm_handler(pm_kwargs)
        if action in _PROJECT_MEMORY_WRITE_ACTIONS:
            try:
                res = json.loads(result_str)
                if isinstance(res, dict) and not res.get("error") and not res.get("conflict"):
                    _append_global_ledger(
                        action=action,
                        target=f"{project_id}/{key}",
                        summary=f"{action} project_id={project_id} key={key}",
                    )
            except (json.JSONDecodeError, TypeError):
                pass
        return result_str

    # ── Branch versioning ──────────────────────────────────────────────────
    bv_handler = _BRANCH_VERSION_ACTIONS.get(action)
    if bv_handler is not None:
        bv_kwargs: dict[str, Any] = {
            "branch_def_id": branch_def_id,
            "branch_version_id": branch_version_id,
            "parent_version_id": parent_version_id,
            "notes": notes,
            "publisher": os.environ.get("UNIVERSE_SERVER_USER", "anonymous"),
            "limit": limit,
        }
        return bv_handler(bv_kwargs)

    # ── Teammate messaging ─────────────────────────────────────────────────
    messaging_handler = _MESSAGING_ACTIONS.get(action)
    if messaging_handler is not None:
        messaging_kwargs: dict[str, Any] = {
            "from_run_id": from_run_id,
            "to_node_id": to_node_id,
            "message_type": message_type,
            "body_json": body_json,
            "reply_to_message_id": reply_to_message_id,
            "message_types": message_types,
            "node_id": node_id,
            "message_id": message_id,
            "since": since,
            "limit": limit,
        }
        return messaging_handler(messaging_kwargs)

    # ── Escrow ─────────────────────────────────────────────────────────────
    escrow_handler = _ESCROW_ACTIONS.get(action)
    if escrow_handler is not None:
        escrow_kwargs: dict[str, Any] = {
            "node_id": node_id,
            "lock_id": lock_id,
            "amount": escrow_amount,
            "currency": escrow_currency,
            "recipient_id": escrow_recipient_id,
            "evidence": escrow_evidence,
            "reason": escrow_reason,
        }
        return escrow_handler(escrow_kwargs)

    # ── Gate events (real-world outcome attestation) ───────────────────────
    gate_event_handler = _GATE_EVENT_ACTIONS.get(action)
    if gate_event_handler is not None:
        ge_kwargs: dict[str, Any] = {
            "goal_id": goal_id,
            "event_id": event_id,
            "event_type": event_type,
            "event_date": event_date,
            "attested_by": attested_by,
            "cites_json": cites_json,
            "verifier_id": verifier_id,
            "disputed_by": disputed_by,
            "retracted_by": retracted_by,
            "reason": notes,
            "note": notes,
            "branch_version_id": branch_version_id,
            "since": since,
            "limit": limit,
        }
        return gate_event_handler(ge_kwargs)

    # ── Dry inspect ────────────────────────────────────────────────────────
    inspect_dry_handler = _INSPECT_DRY_ACTIONS.get(action)
    if inspect_dry_handler is not None:
        di_kwargs: dict[str, Any] = {
            "branch_def_id": branch_def_id,
            "node_id": node_id,
            "branch_spec_json": branch_spec_json,
            "changes_json": changes_json,
        }
        return inspect_dry_handler(di_kwargs)

    # ── Scheduler ──────────────────────────────────────────────────────────
    scheduler_handler = _SCHEDULER_ACTIONS.get(action)
    if scheduler_handler is not None:
        sched_kwargs: dict[str, Any] = {
            "branch_def_id": branch_def_id,
            "cron_expr": cron_expr,
            "interval_seconds": interval_seconds,
            "owner_actor": owner_actor,  # empty = "all" for list; write handlers default to anon
            "inputs_template_json": inputs_template_json,
            "skip_if_running": skip_if_running,
            "schedule_id": schedule_id,
            "subscription_id": subscription_id,
            "event_type": event_type,
            "active_only": active_only,
        }
        return scheduler_handler(sched_kwargs)

    # ── Outcome events ─────────────────────────────────────────────────────
    outcome_handler = _OUTCOME_ACTIONS.get(action)
    if outcome_handler is not None:
        oc_kwargs: dict[str, Any] = {
            "branch_def_id": branch_def_id,
            "run_id": run_id,
            "outcome_id": outcome_id,
            "outcome_type": event_type,  # reuse event_type param
            "evidence_url": evidence_url,
            "gate_event_id": gate_event_id,
            "payload_json": outcome_payload_json,
            "note": outcome_note,
            "limit": limit,
        }
        return outcome_handler(oc_kwargs)

    # ── Attribution chain ──────────────────────────────────────────────────
    attribution_handler = _ATTRIBUTION_ACTIONS.get(action)
    if attribution_handler is not None:
        attr_kwargs: dict[str, Any] = {
            "parent_branch_def_id": parent_branch_def_id,
            "child_branch_def_id": child_branch_def_id,
            "contribution_kind": contribution_kind,
            "credit_share": credit_share,
            "max_depth": max_depth,
            "actor_id": _current_actor(),
        }
        return attribution_handler(attr_kwargs)

    return json.dumps({
        "error": f"Unknown action '{action}'.",
        "available_actions": [
            "register", "list", "inspect",
            "approve", "disable", "enable", "remove",
            "build_branch", "patch_branch", "update_node",
            "create_branch", "add_node", "connect_nodes",
            "set_entry_point", "add_state_field",
            "validate_branch", "describe_branch",
            "get_branch", "list_branches", "delete_branch",
            "run_branch", "get_run", "list_runs",
            "stream_run", "cancel_run", "get_run_output",
            "resume_run", "estimate_run_cost", "query_runs",
            "judge_run", "list_judgments", "compare_runs",
            "suggest_node_edit", "get_node_output",
            "rollback_node", "list_node_versions",
            "project_memory_get", "project_memory_set", "project_memory_list",
            "dry_inspect_node", "dry_inspect_patch",
            "messaging_send", "messaging_receive", "messaging_ack",
            "publish_version", "get_branch_version", "list_branch_versions",
            "continue_branch", "fork_tree",
            "escrow_lock", "escrow_release", "escrow_refund", "escrow_inspect",
            "attest_gate_event", "verify_gate_event", "dispute_gate_event",
            "retract_gate_event", "get_gate_event", "list_gate_events",
            "schedule_branch", "unschedule_branch", "list_schedules",
            "subscribe_branch", "unsubscribe_branch",
            "pause_schedule", "unpause_schedule", "list_scheduler_subscriptions",
            "record_outcome", "list_outcomes", "get_outcome",
            "record_remix", "get_provenance",
        ],
    })


def _ext_register(
    node_id: str,
    display_name: str,
    description: str,
    phase: str,
    input_keys: str,
    output_keys: str,
    source_code: str,
    dependencies: str,
) -> str:
    if not node_id or not display_name or not source_code:
        return json.dumps({"error": "node_id, display_name, and source_code are required."})

    if phase not in VALID_PHASES:
        return json.dumps({
            "error": f"Invalid phase '{phase}'. Must be one of: {', '.join(sorted(VALID_PHASES))}",
        })

    in_keys = [k.strip() for k in input_keys.split(",") if k.strip()] if input_keys else []
    out_keys = [k.strip() for k in output_keys.split(",") if k.strip()] if output_keys else []
    deps = [d.strip() for d in dependencies.split(",") if d.strip()] if dependencies else []

    disallowed = [d for d in deps if d.split("==")[0].split(">=")[0] not in ALLOWED_DEPENDENCIES]
    if disallowed:
        return json.dumps({
            "error": f"Disallowed dependencies: {disallowed}. "
            f"Allowed: {sorted(ALLOWED_DEPENDENCIES)}",
        })

    dangerous_patterns = ["os.system", "subprocess", "eval(", "exec(", "__import__"]
    for pattern in dangerous_patterns:
        if pattern in source_code:
            return json.dumps({
                "error": f"Source code contains disallowed pattern: '{pattern}'",
            })

    nodes = _load_nodes()
    existing = [n for n in nodes if n.get("node_id") == node_id]
    if existing:
        return json.dumps({
            "error": f"Node '{node_id}' already registered. Use a different ID.",
        })

    registration = NodeRegistration(
        node_id=node_id,
        display_name=display_name,
        description=description,
        phase=phase,
        input_keys=in_keys,
        output_keys=out_keys,
        source_code=source_code,
        dependencies=deps,
        author=os.environ.get("UNIVERSE_SERVER_USER", "anonymous"),
        registered_at=datetime.now(timezone.utc).isoformat(),
        enabled=True,
        approved=False,
    )

    nodes.append(registration.to_dict())
    _save_nodes(nodes)

    return json.dumps({
        "node_id": node_id,
        "status": "registered",
        "approved": False,
        "note": "Node registered. It will be available after host approval.",
    })


def _ext_list(phase: str = "", enabled_only: bool = True) -> str:
    nodes = _load_nodes()

    if phase:
        nodes = [n for n in nodes if n.get("phase") == phase]
    if enabled_only:
        nodes = [n for n in nodes if n.get("enabled", True)]

    summaries = [
        {
            "node_id": n.get("node_id"),
            "display_name": n.get("display_name"),
            "description": n.get("description"),
            "phase": n.get("phase"),
            "input_keys": n.get("input_keys"),
            "output_keys": n.get("output_keys"),
            "author": n.get("author"),
            "approved": n.get("approved", False),
            "enabled": n.get("enabled", True),
        }
        for n in nodes
    ]

    return json.dumps({"nodes": summaries, "count": len(summaries)})


def _ext_inspect(node_id: str) -> str:
    if not node_id:
        return json.dumps({"error": "node_id is required."})
    nodes = _load_nodes()
    match = [n for n in nodes if n.get("node_id") == node_id]
    if not match:
        return json.dumps({"error": f"Node '{node_id}' not found."})
    return json.dumps(match[0])


def _ext_manage(node_id: str, action: str) -> str:
    if not node_id:
        return json.dumps({"error": "node_id is required."})

    nodes = _load_nodes()
    idx = next((i for i, n in enumerate(nodes) if n.get("node_id") == node_id), None)
    if idx is None:
        return json.dumps({"error": f"Node '{node_id}' not found."})

    if action == "remove":
        removed = nodes.pop(idx)
        _save_nodes(nodes)
        return json.dumps({
            "node_id": node_id,
            "action": "removed",
            "note": f"Node '{removed.get('display_name')}' permanently removed.",
        })

    if action == "approve":
        nodes[idx]["approved"] = True
    elif action == "disable":
        nodes[idx]["enabled"] = False
    elif action == "enable":
        nodes[idx]["enabled"] = True

    _save_nodes(nodes)
    return json.dumps({
        "node_id": node_id,
        "action": action,
        "approved": nodes[idx].get("approved"),
        "enabled": nodes[idx].get("enabled"),
    })


# ───────────────────────────────────────────────────────────────────────────
# Phase 2: Community Branches — author/edit BranchDefinition over MCP
# ───────────────────────────────────────────────────────────────────────────
# Branches are domain-agnostic graph topologies that live in the same SQLite
# backing store as the rest of the multiplayer substrate (base_path /
# .author_server.db, table branch_definitions). Each write action appends to
# the global ledger at base_path / "ledger.json" for public attribution —
# branches are not scoped to a universe, so the ledger target is the global
# base_path rather than a per-universe directory.


def _split_csv(text: str) -> list[str]:
    return [p.strip() for p in text.split(",") if p.strip()]


def _coerce_node_keys(
    value: Any, field_name: str,
) -> tuple[list[str], str]:
    """Coerce input_keys / output_keys to list[str], or return an error.

    Accepts list[str], JSON-encoded list strings (e.g. '["a","b"]'),
    CSV strings ("a, b, c"), and bare single tokens ("a"). Rejects
    anything else — in particular, naked iteration over an un-parsed
    string like "node.output" was silently yielding a per-character
    list, which then validated as a node spec but was unrunnable.

    Returns (keys, error). On success error is "". On failure keys is
    [] and error is a human-readable reason.
    """
    if value is None:
        return [], ""
    if isinstance(value, list):
        out: list[str] = []
        for idx, item in enumerate(value):
            if not isinstance(item, str):
                return [], (
                    f"{field_name}[{idx}] must be a string, got "
                    f"{type(item).__name__}"
                )
            trimmed = item.strip()
            if not trimmed:
                return [], f"{field_name}[{idx}] is empty"
            out.append(trimmed)
        return out, ""
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return [], ""
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:
                return [], (
                    f"{field_name} looks like JSON but did not parse: {exc}"
                )
            if not isinstance(parsed, list):
                return [], (
                    f"{field_name} JSON must decode to a list, got "
                    f"{type(parsed).__name__}"
                )
            return _coerce_node_keys(parsed, field_name)
        # CSV path — also handles the bare single-token case.
        return [p.strip() for p in raw.split(",") if p.strip()], ""
    return [], (
        f"{field_name} must be a list or string, got "
        f"{type(value).__name__}"
    )


def _append_global_ledger(
    action: str,
    *,
    target: str,
    summary: str,
    payload: dict[str, Any] | None = None,
) -> None:
    """Append a branch-authoring ledger entry at base_path/ledger.json.

    Branch definitions are global artifacts (not scoped to a universe), so the
    ledger target is the base_path rather than a universe directory. Never
    raises: failures are logged but don't roll back the mutation.
    """
    _append_ledger(
        _base_path(), action,
        target=target, summary=summary, payload=payload,
    )


def _ensure_author_server_db() -> None:
    """Ensure the shared SQLite schema exists before any branch action runs.

    Branch handlers read/write ``base_path/.author_server.db``. Calling this
    lazily keeps tests and first-use paths from needing a separate init step.
    """
    from workflow.daemon_server import initialize_author_server

    initialize_author_server(_base_path())


def _dispatch_branch_action(
    action: str,
    handler: Any,
    kwargs: dict[str, Any],
) -> str:
    """Run a branch handler and append to the global ledger on success.

    Read-only branch actions (get/list/validate/describe) bypass the ledger.
    Write actions (create/add/connect/set/delete) are funneled here so no
    handler can silently skip attribution.
    """
    _ensure_author_server_db()
    try:
        result_str = handler(kwargs)
    except DirtyFileError as exc:
        # Phase 7.3: surface local-edit conflicts as a structured MCP
        # response so the client can render actionable options. Ledger
        # is intentionally skipped — no write landed.
        return json.dumps(_format_dirty_file_conflict(exc))

    if action not in _BRANCH_WRITE_ACTIONS:
        return result_str

    try:
        result = json.loads(result_str)
    except (json.JSONDecodeError, TypeError):
        return result_str

    if not isinstance(result, dict):
        return result_str
    # Skip ledger on any error-shaped response. Composite actions signal
    # failure via status="rejected" + errors[]; atomic actions use "error"
    # (singular string). Treat both as "don't attribute a write that
    # didn't land".
    if "error" in result:
        return result_str
    if result.get("status") == "rejected":
        return result_str

    try:
        target = result.get("branch_def_id", "") or kwargs.get("branch_def_id", "")
        summary_bits: list[str] = [action]
        if kwargs.get("name"):
            summary_bits.append(kwargs["name"])
        if kwargs.get("node_id"):
            summary_bits.append(f"node={kwargs['node_id']}")
        if kwargs.get("from_node") and kwargs.get("to_node"):
            summary_bits.append(f"{kwargs['from_node']}->{kwargs['to_node']}")
        if kwargs.get("field_name"):
            summary_bits.append(f"field={kwargs['field_name']}")
        # Composite summary hints — one ledger entry per call, not per op.
        if action == "build_branch":
            summary_bits.append(
                f"nodes={result.get('node_count', '?')}"
            )
        if action == "patch_branch":
            summary_bits.append(
                f"ops={result.get('ops_applied', '?')}"
            )
        summary = _truncate(" ".join(summary_bits))
        _append_global_ledger(
            action, target=str(target), summary=summary, payload=None,
        )
    except Exception as exc:
        logger.warning("Ledger write failed for branch action %s: %s", action, exc)

    return result_str


def _ext_branch_create(kwargs: dict[str, Any]) -> str:
    from workflow.branches import BranchDefinition
    from workflow.identity import git_author

    name = kwargs.get("name", "").strip()
    if not name:
        return json.dumps({"error": "name is required for create_branch."})

    visibility_in = (kwargs.get("visibility") or "public").strip().lower()
    visibility = "private" if visibility_in == "private" else "public"
    branch = BranchDefinition(
        name=name,
        description=kwargs.get("description", ""),
        domain_id=kwargs.get("domain_id") or "workflow",
        author=kwargs.get("author") or _current_actor(),
        visibility=visibility,
    )
    try:
        saved, _commit = _storage_backend().save_branch_and_commit(
            branch,
            author=git_author(_current_actor()),
            message=f"branches.create_branch: {name}",
            force=bool(kwargs.get("force", False)),
        )
    except CommitFailedError as exc:
        return json.dumps(_format_commit_failed(exc))
    return json.dumps({
        "branch_def_id": saved["branch_def_id"],
        "name": saved["name"],
        "visibility": saved.get("visibility", "public"),
        "status": "created",
    })


def _resolve_branch_id(bid_or_name: str, base_path: str) -> str:
    """Return branch_def_id for either a branch_def_id or a branch name.

    Tries exact ID match first (fast path via get_branch_definition).
    Falls back to case-insensitive name search via list_branch_definitions.
    Returns the original string unchanged if no match is found — the caller's
    KeyError handler will surface the "not found" error as usual.
    """
    from workflow.daemon_server import get_branch_definition, list_branch_definitions

    if not bid_or_name:
        return bid_or_name
    try:
        get_branch_definition(base_path, branch_def_id=bid_or_name)
        return bid_or_name
    except KeyError:
        pass
    needle = bid_or_name.lower()
    for b in list_branch_definitions(base_path, viewer=_current_actor()):
        if (b.get("name") or "").lower() == needle:
            return b["branch_def_id"]
    return bid_or_name


def _ext_branch_get(kwargs: dict[str, Any]) -> str:
    from workflow.daemon_server import get_branch_definition, list_gate_claims

    bid = _resolve_branch_id(kwargs.get("branch_def_id", "").strip(), _base_path())
    if not bid:
        return json.dumps({"error": "branch_def_id is required."})
    try:
        branch = get_branch_definition(_base_path(), branch_def_id=bid)
    except KeyError:
        return json.dumps({"error": f"Branch '{bid}' not found."})
    # Phase 6.2.2 — private Branches are not discoverable by non-owners.
    # Match the "not found" envelope so existence isn't leaked.
    visibility = branch.get("visibility", "public") or "public"
    if visibility == "private" and branch.get("author", "") != _current_actor():
        return json.dumps({"error": f"Branch '{bid}' not found."})
    # Phase 6.4: non-retracted claims for this Branch across all
    # Goals. Flag-gated placeholder when GATES_ENABLED=0 so UIs
    # render "gates off" distinct from "no claims yet."
    if _gates_enabled():
        branch["gate_claims"] = list_gate_claims(
            _base_path(),
            branch_def_id=bid,
            include_retracted=False,
        )
    else:
        branch["gate_claims"] = []
        branch["gate_status"] = "gates_disabled"
    related = _related_wiki_pages(branch)
    branch["related_wiki_pages"] = related["items"]
    branch["related_wiki_pages_truncated"] = related["truncated_count"]
    unapproved_sc = [
        {"node_id": nd.get("node_id", ""), "display_name": nd.get("display_name", "")}
        for nd in branch.get("node_defs", [])
        if nd.get("source_code") and not nd.get("approved", False)
    ]
    branch["unapproved_source_code_nodes"] = unapproved_sc
    branch["runnable"] = not unapproved_sc
    return json.dumps(branch, default=str)


def _ext_branch_list(kwargs: dict[str, Any]) -> str:
    from workflow.daemon_server import list_branch_definitions

    # Phase 6.2.2 — visibility-aware listing. Viewer sees public
    # Branches and any private Branches they authored.
    rows = list_branch_definitions(
        _base_path(),
        domain_id=kwargs.get("domain_id", ""),
        author=kwargs.get("author", ""),
        goal_id=kwargs.get("goal_id", ""),
        viewer=_current_actor(),
    )

    # requires_sandbox filter: "none" = design-only branches only (no node
    # has requires_sandbox=True); "any" = branches that have at least one
    # sandbox-requiring node. Omit / empty = no filter.
    rs_filter = (kwargs.get("requires_sandbox") or "").strip().lower()

    summaries = []
    for r in rows:
        node_defs = r.get("node_defs", [])
        has_sandbox_nodes = any(nd.get("requires_sandbox") for nd in node_defs)
        if rs_filter == "none" and has_sandbox_nodes:
            continue
        if rs_filter == "any" and not has_sandbox_nodes:
            continue

        # node_count MUST match describe_branch's count
        # (``len(branch.node_defs)`` at line ~4924) — that's the
        # source of truth. The old formula added ``graph.nodes +
        # node_defs`` which double-counted because graph.nodes is a
        # compiled-topology view that overlaps with node_defs.
        node_count = len(node_defs)
        summaries.append({
            "branch_def_id": r.get("branch_def_id"),
            "name": r.get("name"),
            "author": r.get("author"),
            "domain_id": r.get("domain_id"),
            "goal_id": r.get("goal_id"),
            "node_count": node_count,
            "published": r.get("published", False),
            "visibility": r.get("visibility", "public"),
            "has_sandbox_nodes": has_sandbox_nodes,
        })
    return json.dumps({"branches": summaries, "count": len(summaries)})


def _ext_branch_delete(kwargs: dict[str, Any]) -> str:
    from workflow.daemon_server import delete_branch_definition

    bid = kwargs.get("branch_def_id", "").strip()
    if not bid:
        return json.dumps({"error": "branch_def_id is required."})
    removed = delete_branch_definition(_base_path(), branch_def_id=bid)
    if not removed:
        return json.dumps({"error": f"Branch '{bid}' not found."})
    return json.dumps({"branch_def_id": bid, "status": "deleted"})


def _ext_branch_add_node(kwargs: dict[str, Any]) -> str:
    from workflow.branches import BranchDefinition
    from workflow.daemon_server import get_branch_definition
    from workflow.identity import git_author

    verbose = str(kwargs.get("verbose") or "").strip().lower() in ("true", "1", "yes")
    bid = kwargs.get("branch_def_id", "").strip()
    nid = kwargs.get("node_id", "").strip()
    if not bid or not nid:
        return json.dumps({
            "error": "branch_def_id and node_id are required.",
        })

    # Normalize kwargs into a node spec dict so we can share the
    # build_branch resolver (which checks node_ref / intent and
    # refuses to silently shadow an existing standalone node — #66).
    raw: dict[str, Any] = {
        "node_id": nid,
        "display_name": kwargs.get("display_name", "").strip(),
        "description": kwargs.get("description", ""),
        "phase": kwargs.get("phase", "") or "custom",
        "input_keys": kwargs.get("input_keys", ""),
        "output_keys": kwargs.get("output_keys", ""),
        "source_code": kwargs.get("source_code", ""),
        "prompt_template": kwargs.get("prompt_template", ""),
        "author": kwargs.get("author") or _current_actor(),
    }
    if "node_ref" in kwargs:
        raw["node_ref"] = kwargs["node_ref"]
    if "intent" in kwargs:
        raw["intent"] = kwargs["intent"]

    try:
        source_dict = get_branch_definition(_base_path(), branch_def_id=bid)
    except KeyError:
        return json.dumps({"error": f"Branch '{bid}' not found."})

    branch = BranchDefinition.from_dict(source_dict)
    err = _apply_node_spec(branch, raw)
    if err:
        return json.dumps({"error": err})

    # The resolved node may have been renamed; capture the final id
    # from the mutated branch BEFORE persisting.
    final_nid = branch.node_defs[-1].node_id
    try:
        _storage_backend().save_branch_and_commit(
            branch,
            author=git_author(_current_actor()),
            message=f"branches.add_node: {bid}.{final_nid}",
            force=bool(kwargs.get("force", False)),
        )
    except CommitFailedError as exc:
        return json.dumps(_format_commit_failed(exc))
    add_node_payload: dict[str, Any] = {
        "branch_def_id": bid,
        "node_id": final_nid,
        "status": "added",
    }
    if verbose:
        added = next(
            (n for n in branch.node_defs if n.node_id == final_nid), None
        )
        if added is not None:
            add_node_payload["node_def"] = added.to_dict()
    return json.dumps(add_node_payload, default=str)


def _ext_branch_connect_nodes(kwargs: dict[str, Any]) -> str:
    from workflow.branches import BranchDefinition, EdgeDefinition
    from workflow.daemon_server import get_branch_definition
    from workflow.identity import git_author

    verbose = str(kwargs.get("verbose") or "").strip().lower() in ("true", "1", "yes")
    bid = kwargs.get("branch_def_id", "").strip()
    src = kwargs.get("from_node", "").strip()
    dst = kwargs.get("to_node", "").strip()
    if not (bid and src and dst):
        return json.dumps({
            "error": "branch_def_id, from_node, and to_node are required.",
        })

    try:
        source_dict = get_branch_definition(_base_path(), branch_def_id=bid)
    except KeyError:
        return json.dumps({"error": f"Branch '{bid}' not found."})

    branch = BranchDefinition.from_dict(source_dict)
    branch.edges.append(EdgeDefinition(from_node=src, to_node=dst))

    try:
        _storage_backend().save_branch_and_commit(
            branch,
            author=git_author(_current_actor()),
            message=f"branches.connect_nodes: {bid} {src}->{dst}",
            force=bool(kwargs.get("force", False)),
        )
    except CommitFailedError as exc:
        return json.dumps(_format_commit_failed(exc))
    connect_payload: dict[str, Any] = {
        "branch_def_id": bid,
        "from_node": src,
        "to_node": dst,
        "status": "connected",
    }
    if verbose:
        connect_payload["edge_count"] = len(branch.edges)
    return json.dumps(connect_payload, default=str)


def _ext_branch_set_entry_point(kwargs: dict[str, Any]) -> str:
    from workflow.branches import BranchDefinition
    from workflow.daemon_server import get_branch_definition
    from workflow.identity import git_author

    verbose = str(kwargs.get("verbose") or "").strip().lower() in ("true", "1", "yes")
    bid = kwargs.get("branch_def_id", "").strip()
    nid = kwargs.get("node_id", "").strip()
    if not (bid and nid):
        return json.dumps({
            "error": "branch_def_id and node_id are required.",
        })

    try:
        source_dict = get_branch_definition(_base_path(), branch_def_id=bid)
    except KeyError:
        return json.dumps({"error": f"Branch '{bid}' not found."})

    branch = BranchDefinition.from_dict(source_dict)
    branch.entry_point = nid

    try:
        _storage_backend().save_branch_and_commit(
            branch,
            author=git_author(_current_actor()),
            message=f"branches.set_entry_point: {bid}.{nid}",
            force=bool(kwargs.get("force", False)),
        )
    except CommitFailedError as exc:
        return json.dumps(_format_commit_failed(exc))
    entry_payload: dict[str, Any] = {
        "branch_def_id": bid,
        "entry_point": nid,
        "status": "set",
    }
    if verbose:
        entry_payload["node_count"] = len(branch.node_defs)
    return json.dumps(entry_payload, default=str)


def _ext_branch_add_state_field(kwargs: dict[str, Any]) -> str:
    from workflow.branches import BranchDefinition
    from workflow.daemon_server import get_branch_definition
    from workflow.identity import git_author

    verbose = str(kwargs.get("verbose") or "").strip().lower() in ("true", "1", "yes")
    bid = kwargs.get("branch_def_id", "").strip()
    fname = kwargs.get("field_name", "").strip()
    ftype = kwargs.get("field_type", "").strip() or "str"
    if not (bid and fname):
        return json.dumps({
            "error": "branch_def_id and field_name are required.",
        })

    try:
        source_dict = get_branch_definition(_base_path(), branch_def_id=bid)
    except KeyError:
        return json.dumps({"error": f"Branch '{bid}' not found."})

    branch = BranchDefinition.from_dict(source_dict)
    if any(f.get("name") == fname for f in branch.state_schema):
        return json.dumps({
            "error": f"State field '{fname}' already exists on this branch.",
        })

    field_entry: dict[str, Any] = {
        "name": fname,
        "type": ftype,
        "description": kwargs.get("description", ""),
    }
    reducer = kwargs.get("reducer", "").strip()
    if reducer:
        field_entry["reducer"] = reducer
    default = kwargs.get("field_default", "")
    if default != "":
        field_entry["default"] = default

    branch.state_schema.append(field_entry)
    try:
        _storage_backend().save_branch_and_commit(
            branch,
            author=git_author(_current_actor()),
            message=f"branches.add_state_field: {bid}.{fname}",
            force=bool(kwargs.get("force", False)),
        )
    except CommitFailedError as exc:
        return json.dumps(_format_commit_failed(exc))
    state_payload: dict[str, Any] = {
        "branch_def_id": bid,
        "field_name": fname,
        "status": "added",
    }
    if verbose:
        state_payload["field_count"] = len(branch.state_schema)
    return json.dumps(state_payload, default=str)


def _ext_branch_validate(kwargs: dict[str, Any]) -> str:
    from workflow.branches import BranchDefinition
    from workflow.daemon_server import get_branch_definition

    bid = kwargs.get("branch_def_id", "").strip()
    if not bid:
        return json.dumps({"error": "branch_def_id is required."})
    try:
        source_dict = get_branch_definition(_base_path(), branch_def_id=bid)
    except KeyError:
        return json.dumps({"error": f"Branch '{bid}' not found."})

    branch = BranchDefinition.from_dict(source_dict)
    errors = branch.validate()

    # BUG-031: surface unapproved source_code nodes so the chatbot can warn
    # the user before they attempt run_branch (which would fail with a
    # permission-denied error and no clear remediation path).
    unapproved_sc = [
        {"node_id": nd.get("node_id", ""), "display_name": nd.get("display_name", "")}
        for nd in source_dict.get("node_defs", [])
        if nd.get("source_code") and not nd.get("approved", False)
    ]

    # sandbox-compat warning: list any requires_sandbox=True nodes when
    # the host's bwrap probe says sandbox is unavailable. Non-fatal.
    sandbox_warnings: list[str] = []
    try:
        from workflow.providers.base import get_sandbox_status
        sb = get_sandbox_status()
        if not sb.get("bwrap_available"):
            sandbox_nodes = [
                nd.node_id
                for nd in branch.node_defs
                if getattr(nd, "requires_sandbox", False)
            ]
            if sandbox_nodes:
                reason = sb.get("reason") or "bwrap unavailable"
                sandbox_warnings.append(
                    f"This branch contains {len(sandbox_nodes)} node(s) that "
                    f"require a sandbox ({', '.join(sorted(sandbox_nodes))}) but "
                    f"the host sandbox probe returned: {reason}. "
                    f"These nodes will fail at runtime. Options: enable bwrap "
                    f"on the host, or use a branch variant without "
                    f"requires_sandbox=true nodes (design-only branch)."
                )
    except Exception:  # noqa: BLE001 — best-effort non-blocking warning
        pass

    return json.dumps({
        "branch_def_id": bid,
        "valid": not errors,
        "errors": errors,
        "runnable": not errors and not unapproved_sc,
        "unapproved_source_code_nodes": unapproved_sc,
        "sandbox_warnings": sandbox_warnings,
    })


_MERMAID_ID_SAFE = re.compile(r"[^A-Za-z0-9_]")


def _mermaid_node_id(raw: str) -> str:
    """Return a Mermaid-safe node identifier.

    Mermaid IDs must be alphanumeric/underscore. Node IDs in our branches
    are usually snake_case so this is a noop for well-formed inputs.
    """
    cleaned = _MERMAID_ID_SAFE.sub("_", raw)
    if cleaned and cleaned[0].isdigit():
        cleaned = "n_" + cleaned
    return cleaned or "node"


def _mermaid_label(text: str) -> str:
    """Escape label text for use inside Mermaid's ``["..."]`` node form."""
    return text.replace('"', "'").replace("\n", " ")


def _branch_mermaid(branch: Any) -> str:
    """Render a BranchDefinition as a Mermaid ``flowchart LR`` block.

    Claude.ai and many markdown clients auto-render fenced ``mermaid``
    code blocks. The returned string includes the fence so callers can
    embed it directly in prose. START/END are rendered as stadium shapes;
    everything else uses the default rectangle with its display_name.
    """
    lines: list[str] = ["```mermaid", "flowchart LR"]

    # START/END get stadium shape so they read as terminals.
    lines.append('    START(["START"])')
    lines.append('    END(["END"])')

    for node in branch.node_defs:
        nid = _mermaid_node_id(node.node_id)
        label = _mermaid_label(node.display_name or node.node_id)
        lines.append(f'    {nid}["{label}"]')

    # Include graph_nodes that weren't also declared as node_defs.
    defined_ids = {_mermaid_node_id(n.node_id) for n in branch.node_defs}
    for gn in branch.graph_nodes:
        nid = _mermaid_node_id(gn.id)
        if nid not in defined_ids and nid not in ("START", "END"):
            lines.append(f'    {nid}["{gn.id}"]')
            defined_ids.add(nid)

    for edge in branch.edges:
        src = _mermaid_node_id(edge.from_node)
        dst = _mermaid_node_id(edge.to_node)
        lines.append(f"    {src} --> {dst}")

    for cedge in branch.conditional_edges:
        src = _mermaid_node_id(cedge.from_node)
        for label, target in cedge.conditions.items():
            dst = _mermaid_node_id(target)
            lines.append(f"    {src} -.{_mermaid_label(label)}.-> {dst}")

    if branch.entry_point:
        entry_id = _mermaid_node_id(branch.entry_point)
        if entry_id not in ("START", "END"):
            lines.append(f"    class {entry_id} entry")
            lines.append(
                "    classDef entry stroke:#4a90e2,stroke-width:3px"
            )

    lines.append("```")
    return "\n".join(lines)


# STATUS.md Approved-bugs 2026-04-22 reshape of BUG-018 (maintainer-notes).
# The wiki already carries the cross-reference surface this feature needs —
# instead of adding a per-node `related_notes` field to NodeDefinition,
# surface wiki pages whose text mentions the branch_def_id or any of its
# node_ids. Always-on (no flag); always-bounded (top 20, summary ≤140 chars).
_RELATED_WIKI_CAP = 20
_RELATED_SUMMARY_MAX = 140


def _related_summary(body: str, meta: dict[str, str]) -> str:
    """First prose paragraph of ``body`` clipped to ``_RELATED_SUMMARY_MAX``.

    Skips heading-only lines (``#`` prefix) when picking the first
    paragraph. Falls back to the frontmatter ``description`` field if
    no prose is found; empty string if neither exists.
    """
    paragraph: list[str] = []
    for raw_line in body.split("\n"):
        line = raw_line.strip()
        if not line:
            if paragraph:
                break
            continue
        if line.startswith("#"):
            if paragraph:
                break
            continue
        paragraph.append(line)
    text = " ".join(paragraph).strip()
    if not text:
        text = (meta.get("description", "") or "").strip()
    if len(text) > _RELATED_SUMMARY_MAX:
        # Reserve one char for the ellipsis so total stays ≤ cap.
        return text[: _RELATED_SUMMARY_MAX - 1].rstrip() + "…"
    return text


def _related_wiki_pages(branch: dict[str, Any]) -> dict[str, Any]:
    """Find wiki pages that mention this branch's id or any node id.

    Returns ``{"items": [...], "truncated_count": int}``. Each item has
    ``path``, ``title``, ``summary``, ``matched_via``. Sorted by
    (matched_via count desc, title asc). Capped at ``_RELATED_WIKI_CAP``.
    """
    bid = (branch.get("branch_def_id") or "").strip()
    node_ids: list[str] = []
    for n in branch.get("node_defs", []) or []:
        nid = (n.get("node_id") or "").strip() if isinstance(n, dict) else ""
        if nid and nid not in node_ids:
            node_ids.append(nid)

    terms: list[tuple[str, str]] = []
    if bid:
        terms.append(("branch_def_id", bid.lower()))
    for nid in node_ids:
        terms.append((f"node:{nid}", nid.lower()))
    if not terms:
        return {"items": [], "truncated_count": 0}

    pages = (
        _find_all_pages(_wiki_pages_dir()) + _find_all_pages(_wiki_drafts_dir())
    )
    scored: list[dict[str, Any]] = []
    for p in pages:
        raw = _read_text(p)
        if not raw:
            continue
        meta, body = _parse_frontmatter(raw)
        title = meta.get("title", p.stem)
        haystack = (title + "\n" + body).lower()
        matched_via: list[str] = []
        for label, needle in terms:
            if needle and needle in haystack:
                matched_via.append(label)
        if not matched_via:
            continue
        scored.append({
            "path": _page_rel_path(p),
            "title": title,
            "summary": _related_summary(body, meta),
            "matched_via": matched_via,
        })

    scored.sort(key=lambda x: (-len(x["matched_via"]), x["title"].lower()))
    total = len(scored)
    top = scored[:_RELATED_WIKI_CAP]
    truncated = total - len(top) if total > _RELATED_WIKI_CAP else 0
    return {"items": top, "truncated_count": truncated}


def _ext_branch_describe(kwargs: dict[str, Any]) -> str:
    from workflow.branches import BranchDefinition
    from workflow.daemon_server import get_branch_definition

    bid = _resolve_branch_id(kwargs.get("branch_def_id", "").strip(), _base_path())
    if not bid:
        return json.dumps({"error": "branch_def_id is required."})
    try:
        source_dict = get_branch_definition(_base_path(), branch_def_id=bid)
    except KeyError:
        return json.dumps({"error": f"Branch '{bid}' not found."})

    branch = BranchDefinition.from_dict(source_dict)
    errors = branch.validate()

    unapproved_sc = [
        {"node_id": nd.get("node_id", ""), "display_name": nd.get("display_name", "")}
        for nd in source_dict.get("node_defs", [])
        if nd.get("source_code") and not nd.get("approved", False)
    ]

    node_lines = [
        f"  - {n.node_id}: {n.display_name}"
        + (f" ({n.phase})" if n.phase != "custom" else "")
        for n in branch.node_defs
    ] or ["  (no nodes yet)"]

    edge_lines = [
        f"  - {e.from_node} -> {e.to_node}" for e in branch.edges
    ] or ["  (no edges yet)"]

    state_lines = [
        f"  - {f.get('name')}: {f.get('type', 'str')}"
        + (f" [{f.get('reducer')}]" if f.get("reducer") else "")
        for f in branch.state_schema
    ] or ["  (no state fields yet)"]

    approval_warning_lines = [
        f"  - APPROVAL REQUIRED: node '{n['node_id']}' ({n['display_name']}) has"
        " unapproved source_code — host must run extensions action=approve_source_code"
        " before this branch can run."
        for n in unapproved_sc
    ]

    problem_lines = (
        [f"  - {err}" for err in errors]
        if errors
        else ["  (none — structure is valid)"]
    )

    mermaid = _branch_mermaid(branch)

    summary_parts = [
        f"Branch: {branch.name or '(unnamed)'}  [{branch.branch_def_id}]",
        f"Author: {branch.author}   Domain: {branch.domain_id}",
        f"Entry point: {branch.entry_point or '(not set)'}",
        "",
        f"Nodes ({len(branch.node_defs)}):",
        *node_lines,
        "",
        f"Edges ({len(branch.edges)}):",
        *edge_lines,
        "",
        f"State schema ({len(branch.state_schema)}):",
        *state_lines,
        "",
        "Open problems:",
        *problem_lines,
    ]
    if approval_warning_lines:
        summary_parts += ["", "Approval warnings (branch NOT runnable):"]
        summary_parts += approval_warning_lines
    summary_parts += [
        "",
        "Graph:",
        mermaid,
        "",
        "Note: run this branch with action='run_branch' once validated. "
        "Pass state field values via inputs_json.",
    ]
    summary = "\n".join(summary_parts)
    related = _related_wiki_pages(source_dict)

    # Lineage: expose fork_from + compute fork_descendants.
    fork_from = source_dict.get("fork_from")
    from workflow.branch_versions import list_branch_versions
    from workflow.daemon_server import list_branch_definitions

    my_versions = list_branch_versions(_base_path(), bid, limit=500)
    my_version_ids = {v.branch_version_id for v in my_versions}
    fork_descendants: list[dict[str, Any]] = []
    for b in list_branch_definitions(_base_path(), include_private=False):
        ff = b.get("fork_from")
        if ff and ff in my_version_ids:
            fork_descendants.append({
                "branch_def_id": b["branch_def_id"],
                "author": b.get("author", ""),
                "published_versions_count": len(
                    list_branch_versions(_base_path(), b["branch_def_id"], limit=500)
                ),
            })

    return json.dumps({
        "branch_def_id": bid,
        "summary": summary,
        "mermaid": mermaid,
        "valid": not errors,
        "error_count": len(errors),
        "runnable": not errors and not unapproved_sc,
        "unapproved_source_code_nodes": unapproved_sc,
        "fork_from": fork_from,
        "fork_descendants": fork_descendants,
        "related_wiki_pages": related["items"],
        "related_wiki_pages_truncated": related["truncated_count"],
    })


# ── Composite: build_branch / patch_branch ────────────────────────────────
# Per docs/specs/composite_branch_actions.md: Claude.ai's per-turn tool-call
# budget tops out around 15–20 atomic actions, below a full workflow build.
# Composite actions let a client ship one spec / one batch and get back a
# validated branch. build_branch is strict-with-suggestions (reject
# ambiguous, propose concrete fixes). patch_branch is transactional (all
# ops land or none).


_VALID_STATE_TYPES = {"str", "int", "float", "bool", "list", "dict", "any"}


def _suggest_entry_point(branch: Any) -> str:
    if not branch.graph_nodes:
        return ""
    incoming: set[str] = set()
    for e in branch.edges:
        if e.to_node and e.to_node != "START":
            incoming.add(e.to_node)
    for gn in branch.graph_nodes:
        if gn.id not in incoming:
            return gn.id
    return branch.graph_nodes[0].id


def _closest_state_type(raw: str) -> str:
    lower = (raw or "").lower()
    if lower in _VALID_STATE_TYPES:
        return lower
    for valid in _VALID_STATE_TYPES:
        if valid.startswith(lower) or lower.startswith(valid):
            return valid
    return "any"


def _errors_to_suggestions(
    branch: Any, errors: list[str],
) -> list[dict[str, str]]:
    suggestions: list[dict[str, str]] = []
    for err in errors:
        low = err.lower()
        if "entry point is required" in low:
            suggestions.append({
                "issue": err,
                "proposed_fix": (
                    f"Set entry_point to '{_suggest_entry_point(branch)}'."
                    if _suggest_entry_point(branch)
                    else "Add at least one node before setting entry_point."
                ),
            })
        elif "not a defined node" in low or "is not defined" in low:
            suggestions.append({
                "issue": err,
                "proposed_fix": (
                    "Either add the missing node via node_defs, or remove "
                    "the edge / entry_point that references it."
                ),
            })
        elif "not reachable from" in low:
            suggestions.append({
                "issue": err,
                "proposed_fix": (
                    "Add an incoming edge from a reachable node, or remove "
                    "the orphan node."
                ),
            })
        elif "cycle without exit" in low:
            suggestions.append({
                "issue": err,
                "proposed_fix": (
                    "Add an edge from a node inside the cycle to END, or "
                    "convert one edge to a conditional edge with an END "
                    "target."
                ),
            })
        elif "at least one node" in low:
            suggestions.append({
                "issue": err,
                "proposed_fix": (
                    "Add at least one node_def + graph_node entry."
                ),
            })
        elif "branch name is required" in low:
            suggestions.append({
                "issue": err,
                "proposed_fix": "Pass a non-empty 'name' in the spec.",
            })
        elif "duplicate" in low:
            suggestions.append({
                "issue": err,
                "proposed_fix": "Rename the duplicate id to a unique value.",
            })
        else:
            suggestions.append({
                "issue": err,
                "proposed_fix": "Review this error and reshape the spec.",
            })
    return suggestions


def _resolve_node_spec(
    raw: dict[str, Any],
) -> tuple[dict[str, Any] | None, str]:
    """Resolve a raw node spec that may contain ``node_ref`` or just a
    ``node_id`` that collides with an existing standalone/branch node.

    Returns ``(resolved_spec, error)``. On success ``error`` is empty
    and ``resolved_spec`` is a fully-populated dict ready to build a
    ``NodeDefinition`` from. On failure ``resolved_spec`` is ``None``
    and ``error`` explains what the caller must do.

    The shape changes we accept are:

    - ``node_ref={"source": "standalone", "node_id": "X"}`` — copy the
      canonical standalone registration X into this branch.
    - ``node_ref={"source": "<branch_def_id>", "node_id": "X"}`` —
      copy node X from another branch.
    - Plain inline spec (``node_id``/``display_name``/...): used as-is,
      EXCEPT we refuse to silently shadow an existing standalone
      registration (#66). The caller must either pick a different
      ``node_id`` or pass ``intent="copy"`` to opt into the copy.

    ``intent="reference"`` is reserved for a future live-reference
    mode. v1 only supports ``intent="copy"``; other values error.
    """
    nid = (raw.get("node_id") or "").strip()
    intent = (raw.get("intent") or "").strip().lower()
    if intent and intent not in ("copy", "reference"):
        return None, (
            f"intent='{raw.get('intent')}' is unknown. "
            "Use 'copy' to snapshot an existing node into this "
            "branch, or omit intent and pass inline fields."
        )
    if intent == "reference":
        return None, (
            "intent='reference' (live shared node) is not supported "
            "yet. Use intent='copy' to snapshot a standalone node "
            "into this branch."
        )

    node_ref = raw.get("node_ref")
    if node_ref:
        if not isinstance(node_ref, dict):
            return None, "node_ref must be an object with 'source' and 'node_id'."
        ref_source = (node_ref.get("source") or "").strip()
        ref_nid = (node_ref.get("node_id") or nid).strip()
        if not ref_source or not ref_nid:
            return None, "node_ref requires 'source' and 'node_id'."
        resolved, err = _lookup_node_body(ref_source, ref_nid)
        if err:
            return None, err
        # Start from the resolved body, then overlay any caller-supplied
        # fields so the client can, e.g., rename the copy.
        merged: dict[str, Any] = dict(resolved)
        merged["node_id"] = nid or ref_nid
        for field_key in (
            "display_name", "description", "phase", "input_keys",
            "output_keys", "source_code", "prompt_template", "author",
        ):
            if field_key in raw and raw[field_key] not in (None, ""):
                merged[field_key] = raw[field_key]
        return merged, ""

    # No explicit ref — fall back to raw. If the node_id shadows a
    # standalone registration, demand explicit intent so the caller
    # cannot silently create a hollow clone.
    if nid and intent != "copy":
        try:
            standalone = _load_nodes()
        except Exception:
            standalone = []
        hit = next(
            (n for n in standalone if n.get("node_id") == nid), None,
        )
        if hit:
            return None, (
                f"node_id '{nid}' matches an existing standalone "
                "registered node. Pass node_ref="
                f"{{'source': 'standalone', 'node_id': '{nid}'}} to "
                "copy its body into this branch, or pass intent='copy' "
                "on this spec if you intentionally want the existing "
                "body, or rename this node to avoid collision."
            )
    return raw, ""


def _lookup_node_body(
    source: str, node_id: str,
) -> tuple[dict[str, Any], str]:
    """Return the canonical node body for a ``node_ref`` lookup.

    ``source`` is either the literal string ``'standalone'`` (look in
    the standalone node registry) or a branch_def_id (look in that
    branch's ``node_defs``).
    """
    if source == "standalone":
        try:
            nodes = _load_nodes()
        except Exception as exc:
            return {}, f"could not load standalone node registry: {exc}"
        hit = next(
            (n for n in nodes if n.get("node_id") == node_id), None,
        )
        if not hit:
            return {}, (
                f"standalone node '{node_id}' not found. "
                "Check `extensions action=list` for registered nodes."
            )
        return {
            "node_id": hit.get("node_id", node_id),
            "display_name": hit.get("display_name", node_id),
            "description": hit.get("description", ""),
            "phase": hit.get("phase", "custom"),
            "input_keys": list(hit.get("input_keys") or []),
            "output_keys": list(hit.get("output_keys") or []),
            "source_code": hit.get("source_code", ""),
            "prompt_template": hit.get("prompt_template", ""),
            "author": hit.get("author", ""),
        }, ""

    # Otherwise treat `source` as a branch_def_id.
    from workflow.daemon_server import get_branch_definition

    try:
        source_branch = get_branch_definition(
            _base_path(), branch_def_id=source,
        )
    except KeyError:
        return {}, (
            f"node_ref source '{source}' is neither 'standalone' nor a "
            "known branch_def_id."
        )
    for nd in source_branch.get("node_defs") or []:
        if nd.get("node_id") == node_id:
            return {
                "node_id": nd.get("node_id", node_id),
                "display_name": nd.get("display_name", node_id),
                "description": nd.get("description", ""),
                "phase": nd.get("phase", "custom"),
                "input_keys": list(nd.get("input_keys") or []),
                "output_keys": list(nd.get("output_keys") or []),
                "source_code": nd.get("source_code", ""),
                "prompt_template": nd.get("prompt_template", ""),
                "author": nd.get("author", ""),
            }, ""
    return {}, (
        f"node '{node_id}' not found on branch '{source}'. "
        "Use `extensions action=get_branch` to list its nodes."
    )


def _apply_node_spec(branch: Any, raw: dict[str, Any]) -> str:
    from workflow.branches import GraphNodeRef, NodeDefinition

    resolved, err = _resolve_node_spec(raw)
    if err:
        return err
    raw = resolved  # resolved may be the same dict, or a merged copy

    nid = (raw.get("node_id") or "").strip()
    display = (raw.get("display_name") or "").strip()
    if not nid or not display:
        return "node spec missing node_id or display_name"

    source_code = raw.get("source_code") or ""
    prompt_template = raw.get("prompt_template") or ""
    if source_code and prompt_template:
        return (
            f"node '{nid}' has both source_code and prompt_template — "
            "pick one."
        )

    phase = (raw.get("phase") or "").strip() or "custom"
    in_keys, err = _coerce_node_keys(raw.get("input_keys"), "input_keys")
    if err:
        return err
    out_keys, err = _coerce_node_keys(raw.get("output_keys"), "output_keys")
    if err:
        return err
    try:
        node = NodeDefinition(
            node_id=nid,
            display_name=display,
            description=raw.get("description", ""),
            phase=phase,
            input_keys=in_keys,
            output_keys=out_keys,
            source_code=source_code,
            prompt_template=prompt_template,
            author=raw.get("author") or _current_actor(),
        )
    except ValueError as exc:
        return str(exc)

    if any(n.node_id == nid for n in branch.node_defs):
        return f"node '{nid}' already exists on the branch"

    branch.node_defs.append(node)
    branch.graph_nodes.append(GraphNodeRef(
        id=nid, node_def_id=nid, position=len(branch.graph_nodes),
    ))
    return ""


def _apply_edge_spec(branch: Any, raw: dict[str, Any]) -> str:
    from workflow.branches import EdgeDefinition

    src = (raw.get("from") or raw.get("from_node") or "").strip()
    dst = (raw.get("to") or raw.get("to_node") or "").strip()
    if not src or not dst:
        return "edge spec missing 'from' or 'to'"
    branch.edges.append(EdgeDefinition(from_node=src, to_node=dst))
    return ""


def _apply_conditional_edge_spec(branch: Any, raw: dict[str, Any]) -> str:
    from workflow.branches import ConditionalEdge

    src = (raw.get("from") or raw.get("from_node") or "").strip()
    if not src:
        return "conditional edge spec missing 'from'"
    conditions_raw = raw.get("conditions")
    if not isinstance(conditions_raw, dict) or not conditions_raw:
        return (
            "conditional edge spec requires a non-empty 'conditions' "
            "object mapping outcome strings to target node ids"
        )
    conditions: dict[str, str] = {}
    for outcome, target in conditions_raw.items():
        outcome_str = str(outcome).strip()
        target_str = str(target).strip()
        if not outcome_str or not target_str:
            return (
                "conditional edge outcome/target must be non-empty strings"
            )
        conditions[outcome_str] = target_str
    # Merge onto any existing edge from the same source so callers can
    # add one outcome at a time without wiping siblings.
    for existing in branch.conditional_edges:
        if existing.from_node == src:
            existing.conditions.update(conditions)
            return ""
    branch.conditional_edges.append(
        ConditionalEdge(from_node=src, conditions=conditions)
    )
    return ""


def _apply_state_field_spec(branch: Any, raw: dict[str, Any]) -> str:
    fname = (raw.get("name") or raw.get("field_name") or "").strip()
    if not fname:
        return "state field spec missing 'name'"
    if any(f.get("name") == fname for f in branch.state_schema):
        return f"state field '{fname}' already exists on the branch"
    ftype_raw = (raw.get("type") or raw.get("field_type") or "str").strip()
    ftype = _closest_state_type(ftype_raw)
    entry: dict[str, Any] = {
        "name": fname,
        "type": ftype,
        "description": raw.get("description", ""),
    }
    if raw.get("reducer"):
        entry["reducer"] = raw["reducer"]
    default = raw.get("default", raw.get("field_default", ""))
    if default != "":
        entry["default"] = default
    branch.state_schema.append(entry)
    if ftype_raw.lower() not in _VALID_STATE_TYPES:
        return (
            f"state field '{fname}' type '{ftype_raw}' unknown; "
            f"coerced to '{ftype}'."
        )
    return ""


def _staged_branch_from_spec(
    spec: dict[str, Any],
) -> tuple[Any, list[str]]:
    from workflow.branches import BranchDefinition

    errors: list[str] = []
    branch = BranchDefinition(
        name=(spec.get("name") or "").strip(),
        description=spec.get("description") or "",
        domain_id=(spec.get("domain_id") or "").strip() or "workflow",
        goal_id=(spec.get("goal_id") or "").strip(),
        author=(spec.get("author") or _current_actor()),
        tags=list(spec.get("tags") or []),
        fork_from=spec.get("fork_from") or None,
    )

    for idx, raw in enumerate(spec.get("node_defs") or spec.get("nodes") or []):
        err = _apply_node_spec(branch, raw)
        if err:
            errors.append(f"node[{idx}]: {err}")

    for idx, raw in enumerate(spec.get("edges") or []):
        err = _apply_edge_spec(branch, raw)
        if err:
            errors.append(f"edge[{idx}]: {err}")

    for idx, raw in enumerate(spec.get("conditional_edges") or []):
        err = _apply_conditional_edge_spec(branch, raw)
        if err:
            errors.append(f"conditional_edge[{idx}]: {err}")

    for idx, raw in enumerate(spec.get("state_schema") or []):
        err = _apply_state_field_spec(branch, raw)
        if err:
            errors.append(f"state_schema[{idx}]: {err}")

    entry = (spec.get("entry_point") or "").strip()
    if entry:
        branch.entry_point = entry

    return branch, errors


def _build_branch_text(branch: Any, *, truncated: bool) -> str:
    node_count = len(branch.node_defs)
    edge_count = len(branch.edges)
    head = (
        f"**Built branch '{branch.name or 'unnamed'}'**: "
        f"{node_count} nodes, {edge_count} edges, "
        f"entry=`{branch.entry_point}`."
    )
    if truncated:
        return "\n".join([
            head,
            "",
            "_(Branch exceeds 12-node phone-legibility limit; "
            "full topology in structuredContent. Mermaid summary:)_",
            "",
            "```mermaid",
            "flowchart LR",
            f'    START(["START"]) --> entry["{_mermaid_label(branch.entry_point)}"]',
            f"    entry --> more[\"... {node_count - 1} more nodes\"]",
            '    more --> END(["END"])',
            "```",
        ])
    mermaid = _branch_mermaid(branch)
    state_lines = [f"State schema: {len(branch.state_schema)} field(s)."]
    return "\n".join([head, "", mermaid, "", *state_lines])


def _ext_branch_build(kwargs: dict[str, Any]) -> str:
    from workflow.daemon_server import save_branch_definition

    verbose = str(kwargs.get("verbose") or "").strip().lower() in ("true", "1", "yes")
    raw = (kwargs.get("spec_json") or "").strip()
    if not raw:
        return json.dumps({
            "status": "rejected",
            "error": "spec_json is required for build_branch.",
            "suggestions": [{
                "issue": "Empty spec.",
                "proposed_fix": (
                    "Pass a JSON object with at minimum `name` and a "
                    "non-empty `node_defs` list. See branch_design_guide."
                ),
            }],
        })
    try:
        spec = json.loads(raw)
    except json.JSONDecodeError as exc:
        return json.dumps({
            "status": "rejected",
            "error": f"spec_json is not valid JSON: {exc}",
            "suggestions": [{
                "issue": "spec_json did not parse.",
                "proposed_fix": "Validate JSON shape before sending.",
            }],
        })
    if not isinstance(spec, dict):
        return json.dumps({
            "status": "rejected",
            "error": "spec_json must decode to a JSON object.",
            "suggestions": [{
                "issue": "Top-level spec is not an object.",
                "proposed_fix": "Wrap the spec in { ... }.",
            }],
        })

    branch, staging_errors = _staged_branch_from_spec(spec)
    validation_errors = branch.validate()
    errors = staging_errors + validation_errors

    # Validate fork_from points to a real branch_version_id.
    if branch.fork_from:
        from workflow.branch_versions import get_branch_version
        if get_branch_version(_base_path(), branch.fork_from) is None:
            errors.append(
                f"fork_from '{branch.fork_from}' is not a known branch_version_id. "
                "Pass a published branch_version_id, not a branch_def_id."
            )

    if errors:
        suggestions = _errors_to_suggestions(branch, errors)
        text_lines = [
            f"**Build failed.** {len(errors)} problem(s) in spec:",
            "",
            *[f"- {err}" for err in errors],
        ]
        if suggestions:
            text_lines += [
                "",
                "Suggested fixes:",
                *[f"- {s['proposed_fix']}" for s in suggestions],
            ]
        return json.dumps({
            "text": "\n".join(text_lines),
            "status": "rejected",
            "errors": errors,
            "suggestions": suggestions,
            "attempted_spec": spec,
        })

    saved = save_branch_definition(_base_path(), branch_def=branch.to_dict())
    from workflow.branches import BranchDefinition as _BD

    persisted = _BD.from_dict(saved)
    truncated = len(persisted.node_defs) > 12
    text = _build_branch_text(persisted, truncated=truncated)
    payload: dict[str, Any] = {
        "text": text,
        "status": "built",
        "branch_def_id": persisted.branch_def_id,
        "name": persisted.name,
        "node_count": len(persisted.node_defs),
        "edge_count": len(persisted.edges),
        "entry_point": persisted.entry_point,
        "validation_summary": "ok",
    }
    if verbose:
        payload["branch"] = saved
    return json.dumps(payload, default=str)


def _apply_patch_op(branch: Any, op: dict[str, Any]) -> str:
    name = (op.get("op") or "").strip().lower()
    if name == "add_node":
        return _apply_node_spec(branch, op)
    if name == "add_edge":
        return _apply_edge_spec(branch, op)
    if name == "add_state_field":
        return _apply_state_field_spec(branch, op)
    if name == "set_entry_point":
        nid = (op.get("node_id") or "").strip()
        if not nid:
            return "set_entry_point requires node_id"
        branch.entry_point = nid
        return ""
    if name == "set_goal":
        gid = (op.get("goal_id") or "").strip()
        if not gid:
            return "set_goal requires goal_id"
        branch.goal_id = gid
        return ""
    if name == "unset_goal":
        branch.goal_id = ""
        return ""
    if name == "remove_node":
        nid = (op.get("node_id") or "").strip()
        if not nid:
            return "remove_node requires node_id"
        before_n = len(branch.node_defs)
        branch.node_defs = [n for n in branch.node_defs if n.node_id != nid]
        branch.graph_nodes = [g for g in branch.graph_nodes if g.id != nid]
        branch.edges = [
            e for e in branch.edges
            if e.from_node != nid and e.to_node != nid
        ]
        if branch.entry_point == nid:
            branch.entry_point = ""
        if len(branch.node_defs) == before_n:
            return f"remove_node: node '{nid}' not found"
        return ""
    if name == "remove_edge":
        src = (op.get("from") or op.get("from_node") or "").strip()
        dst = (op.get("to") or op.get("to_node") or "").strip()
        if not src or not dst:
            return "remove_edge requires from and to"
        before = len(branch.edges)
        branch.edges = [
            e for e in branch.edges
            if not (e.from_node == src and e.to_node == dst)
        ]
        if len(branch.edges) == before:
            return f"remove_edge: {src}->{dst} not found"
        return ""
    if name == "add_conditional_edge":
        return _apply_conditional_edge_spec(branch, op)
    if name == "remove_conditional_edge":
        src = (op.get("from") or op.get("from_node") or "").strip()
        if not src:
            return "remove_conditional_edge requires 'from'"
        outcome = (op.get("outcome") or "").strip()
        for i, ce in enumerate(branch.conditional_edges):
            if ce.from_node != src:
                continue
            if not outcome:
                del branch.conditional_edges[i]
                return ""
            if outcome not in ce.conditions:
                return (
                    f"remove_conditional_edge: outcome '{outcome}' not "
                    f"found on edge from '{src}'"
                )
            del ce.conditions[outcome]
            if not ce.conditions:
                del branch.conditional_edges[i]
            return ""
        return f"remove_conditional_edge: no conditional edge from '{src}'"
    if name == "remove_state_field":
        fname = (op.get("name") or op.get("field_name") or "").strip()
        if not fname:
            return "remove_state_field requires name"
        before = len(branch.state_schema)
        branch.state_schema = [
            f for f in branch.state_schema if f.get("name") != fname
        ]
        if len(branch.state_schema) == before:
            return f"remove_state_field: '{fname}' not found"
        return ""
    if name == "update_node":
        nid = (op.get("node_id") or "").strip()
        if not nid:
            return "update_node requires node_id"
        for n in branch.node_defs:
            if n.node_id == nid:
                if "display_name" in op:
                    n.display_name = op["display_name"]
                if "description" in op:
                    n.description = op["description"]
                if "prompt_template" in op:
                    n.prompt_template = op["prompt_template"]
                if "source_code" in op:
                    n.source_code = op["source_code"]
                if "input_keys" in op:
                    keys, err = _coerce_node_keys(
                        op["input_keys"], "input_keys",
                    )
                    if err:
                        return err
                    n.input_keys = keys
                if "output_keys" in op:
                    keys, err = _coerce_node_keys(
                        op["output_keys"], "output_keys",
                    )
                    if err:
                        return err
                    n.output_keys = keys
                return ""
        return f"update_node: node '{nid}' not found"
    # Branch-level metadata ops (#67). These let patch_branch rename /
    # retag / redescribe / publish a branch atomically, without the
    # previous delete-and-rebuild workaround that lost run history and
    # judgments.
    if name == "set_name":
        new_name = (op.get("name") or "").strip()
        if not new_name:
            return "set_name requires a non-empty name"
        branch.name = new_name
        return ""
    if name == "set_description":
        if "description" not in op:
            return "set_description requires a description field"
        branch.description = op.get("description") or ""
        return ""
    if name == "set_tags":
        if "tags" not in op:
            return "set_tags requires a tags list"
        raw_tags = op.get("tags")
        if raw_tags is None:
            raw_tags = []
        if isinstance(raw_tags, str):
            # Accept CSV too for parity with other surfaces.
            raw_tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
        if not isinstance(raw_tags, list):
            return "set_tags 'tags' must be a list (or CSV string)"
        branch.tags = [str(t).strip() for t in raw_tags if str(t).strip()]
        return ""
    if name == "set_published":
        if "published" not in op:
            return "set_published requires a 'published' boolean"
        val = op.get("published")
        if not isinstance(val, bool):
            return "set_published 'published' must be true or false"
        branch.published = val
        return ""
    if name == "set_visibility":
        # Phase 6.2.2 — private hides Branch + its gate claims from
        # non-owner callers.
        if "visibility" not in op:
            return "set_visibility requires a 'visibility' string"
        raw = op.get("visibility")
        if not isinstance(raw, str):
            return "set_visibility 'visibility' must be 'public' or 'private'"
        normalized = raw.strip().lower()
        if normalized not in ("public", "private"):
            return (
                "set_visibility 'visibility' must be 'public' or 'private'"
            )
        branch.visibility = normalized
        return ""
    if name == "set_fork_from":
        bvid = (op.get("branch_version_id") or "").strip()
        if not bvid:
            return "set_fork_from requires branch_version_id"
        if branch.fork_from is not None:
            return (
                f"set_fork_from: fork_from is already set to '{branch.fork_from}' "
                "and is immutable after set."
            )
        from workflow.branch_versions import get_branch_version
        if get_branch_version(_base_path(), bvid) is None:
            return (
                f"set_fork_from: '{bvid}' is not a known branch_version_id. "
                "Pass a published branch_version_id, not a branch_def_id."
            )
        branch.fork_from = bvid
        return ""
    return f"unknown op '{name}'"


def _ext_branch_patch(kwargs: dict[str, Any]) -> str:
    from workflow.branches import BranchDefinition
    from workflow.daemon_server import (
        get_branch_definition,
        save_branch_definition,
    )

    verbose = str(kwargs.get("verbose") or "").strip().lower() in ("true", "1", "yes")
    bid = _resolve_branch_id(
        (kwargs.get("branch_def_id") or "").strip(), str(_base_path())
    )
    if not bid:
        return json.dumps({
            "status": "rejected",
            "error": "branch_def_id is required.",
        })
    raw = (kwargs.get("changes_json") or "").strip()
    if not raw:
        return json.dumps({
            "status": "rejected",
            "error": "changes_json is required (ordered list of ops).",
        })

    try:
        changes = json.loads(raw)
    except json.JSONDecodeError as exc:
        return json.dumps({
            "status": "rejected",
            "error": f"changes_json is not valid JSON: {exc}",
        })
    if not isinstance(changes, list):
        return json.dumps({
            "status": "rejected",
            "error": "changes_json must decode to a JSON list.",
        })

    try:
        source = get_branch_definition(_base_path(), branch_def_id=bid)
    except KeyError:
        return json.dumps({
            "status": "rejected",
            "error": f"Branch '{bid}' not found.",
        })

    old_name = source.get("name", "")
    staging = BranchDefinition.from_dict(source)

    per_op_errors: list[dict[str, Any]] = []
    for idx, op in enumerate(changes):
        if not isinstance(op, dict):
            per_op_errors.append({
                "op_index": idx, "op": op,
                "error": "op must be an object with an 'op' key",
            })
            continue
        err = _apply_patch_op(staging, op)
        if err:
            per_op_errors.append({
                "op_index": idx, "op": op, "error": err,
            })

    validation_errors: list[str] = []
    if not per_op_errors:
        validation_errors = staging.validate()

    if per_op_errors or validation_errors:
        suggestions = _errors_to_suggestions(staging, validation_errors)
        text_lines = [
            f"**Patch rejected.** {len(per_op_errors)} op error(s), "
            f"{len(validation_errors)} validation error(s). No changes "
            "were applied.",
        ]
        if per_op_errors:
            text_lines += ["", "Op errors:"]
            for pe in per_op_errors:
                op_name = (
                    pe['op'].get('op', '?')
                    if isinstance(pe['op'], dict) else str(pe['op'])
                )
                text_lines.append(
                    f"- op[{pe['op_index']}] {op_name}: {pe['error']}"
                )
        if validation_errors:
            text_lines += ["", "Validation:"]
            for err in validation_errors:
                text_lines.append(f"- {err}")
        if suggestions:
            text_lines += ["", "Suggested fixes:"]
            for s in suggestions:
                text_lines.append(f"- {s['proposed_fix']}")
        return json.dumps({
            "text": "\n".join(text_lines),
            "status": "rejected",
            "errors": per_op_errors,
            "validation_errors": validation_errors,
            "suggestions": suggestions,
        })

    saved = save_branch_definition(_base_path(), branch_def=staging.to_dict())
    persisted = BranchDefinition.from_dict(saved)

    _SKIP_DIFF = {"updated_at", "created_at", "node_defs", "edges",
                  "conditional_edges", "graph_nodes", "state_schema", "stats"}
    patched_fields = [
        k for k in source
        if k not in _SKIP_DIFF and source.get(k) != saved.get(k)
    ]

    post_patch = {
        "branch_def_id": persisted.branch_def_id,
        "name": persisted.name,
        "entry_point": persisted.entry_point,
        "node_count": len(persisted.node_defs),
        "edge_count": len(persisted.edges),
        "visibility": persisted.visibility,
    }

    truncated = len(persisted.node_defs) > 12
    text_lines = [
        f"**Patched branch '{persisted.name}'**: applied {len(changes)} op(s). "
        f"{len(persisted.node_defs)} nodes, {len(persisted.edges)} edges, "
        f"entry=`{persisted.entry_point}`.",
    ]
    if patched_fields:
        text_lines += ["", f"Changed fields: {', '.join(patched_fields)}."]
    if truncated:
        text_lines += [
            "",
            "_(Branch exceeds 12 nodes; full topology in structuredContent.)_",
        ]
    else:
        text_lines += ["", _branch_mermaid(persisted)]
    name_updated = persisted.name != old_name
    patch_payload: dict[str, Any] = {
        "text": "\n".join(text_lines),
        "status": "patched",
        "branch_def_id": persisted.branch_def_id,
        "ops_applied": len(changes),
        "node_count": len(persisted.node_defs),
        "edge_count": len(persisted.edges),
        "patched_fields": patched_fields,
        "name_updated": name_updated,
        "new_name": persisted.name,
        "post_patch": post_patch,
    }
    if verbose:
        patch_payload["branch"] = saved
    return json.dumps(patch_payload, default=str)


def _ext_branch_update_node(kwargs: dict[str, Any]) -> str:
    """Update a single node in-place, keeping ``node_id`` stable.

    Phase 4 lineage + judgments are keyed on node_id, so edits must
    preserve identity. Same update semantics as the patch op of the same
    name; this standalone action bumps BranchDefinition.version (+1)
    so downstream lineage can distinguish pre/post-edit runs.
    """
    from workflow.branches import BranchDefinition
    from workflow.daemon_server import (
        get_branch_definition,
        save_branch_definition,
    )

    bid = _resolve_branch_id(
        (kwargs.get("branch_def_id") or "").strip(), str(_base_path())
    )
    nid = (kwargs.get("node_id") or "").strip()
    if not bid or not nid:
        return json.dumps({
            "status": "rejected",
            "error": "branch_def_id and node_id are required.",
        })

    # Accept updates as a JSON blob (changes_json) OR as individual
    # kwargs (display_name, description, phase, prompt_template,
    # source_code, input_keys, output_keys). Individual kwargs are
    # the phone-friendly shape; changes_json is for scripts batching.
    changes_raw = (kwargs.get("changes_json") or "").strip()
    updates: dict[str, Any] = {}
    if changes_raw:
        try:
            parsed = json.loads(changes_raw)
        except json.JSONDecodeError as exc:
            return json.dumps({
                "status": "rejected",
                "error": f"changes_json is not valid JSON: {exc}",
            })
        if not isinstance(parsed, dict):
            return json.dumps({
                "status": "rejected",
                "error": "changes_json must decode to an object.",
            })
        updates = parsed
    else:
        # Pull supported fields from the top-level kwargs.
        for field in (
            "display_name", "description", "phase",
            "prompt_template", "source_code",
        ):
            if kwargs.get(field):
                updates[field] = kwargs[field]
        if kwargs.get("input_keys"):
            updates["input_keys"] = kwargs["input_keys"]
        if kwargs.get("output_keys"):
            updates["output_keys"] = kwargs["output_keys"]

    if not updates:
        return json.dumps({
            "status": "rejected",
            "error": (
                "No fields to update. Pass one or more of "
                "display_name / description / phase / prompt_template / "
                "source_code / input_keys / output_keys, or a "
                "changes_json object."
            ),
        })

    try:
        source = get_branch_definition(_base_path(), branch_def_id=bid)
    except KeyError:
        return json.dumps({
            "status": "rejected",
            "error": f"Branch '{bid}' not found.",
        })

    staging = BranchDefinition.from_dict(source)
    target_node = next(
        (n for n in staging.node_defs if n.node_id == nid), None,
    )
    if target_node is None:
        return json.dumps({
            "status": "rejected",
            "error": f"Node '{nid}' not found on branch '{bid}'.",
        })

    # Reject ambiguous prompt_template + source_code combos explicitly
    # so we don't silently end up with both set.
    incoming_template = updates.get("prompt_template", "")
    incoming_source = updates.get("source_code", "")
    if incoming_template and incoming_source:
        return json.dumps({
            "status": "rejected",
            "error": (
                "Pass prompt_template OR source_code, not both. "
                "To switch types, clear the other field first."
            ),
        })

    try:
        if "display_name" in updates:
            target_node.display_name = updates["display_name"]
        if "description" in updates:
            target_node.description = updates["description"]
        if "phase" in updates:
            # NodeDefinition.__post_init__ guards valid phases, so we
            # validate here too.
            new_phase = updates["phase"] or "custom"
            if new_phase not in VALID_PHASES:
                return json.dumps({
                    "status": "rejected",
                    "error": (
                        f"Invalid phase '{new_phase}'. Must be one of: "
                        f"{', '.join(sorted(VALID_PHASES))}"
                    ),
                })
            target_node.phase = new_phase
        if "prompt_template" in updates:
            target_node.prompt_template = updates["prompt_template"]
            if target_node.prompt_template:
                target_node.source_code = ""
        if "source_code" in updates:
            target_node.source_code = updates["source_code"]
            if target_node.source_code:
                target_node.prompt_template = ""
        if "input_keys" in updates:
            keys, err = _coerce_node_keys(
                updates["input_keys"], "input_keys",
            )
            if err:
                return json.dumps({"status": "rejected", "error": err})
            target_node.input_keys = keys
        if "output_keys" in updates:
            keys, err = _coerce_node_keys(
                updates["output_keys"], "output_keys",
            )
            if err:
                return json.dumps({"status": "rejected", "error": err})
            target_node.output_keys = keys
    except Exception as exc:
        return json.dumps({
            "status": "rejected",
            "error": f"Failed to apply update: {exc}",
        })

    # Snapshot the previous node body BEFORE we mutate further, so the
    # audit row captures rollback-capable state.
    before_branch = BranchDefinition.from_dict(source)
    before_node = next(
        (n for n in before_branch.node_defs if n.node_id == nid), None,
    )
    node_before_body = before_node.to_dict() if before_node else {}

    # Bump version so Phase 4 lineage can distinguish pre/post-edit runs.
    old_version = int(source.get("version") or 1)
    new_version = old_version + 1
    staging_dict = staging.to_dict()
    staging_dict["version"] = new_version
    saved = save_branch_definition(_base_path(), branch_def=staging_dict)

    # Re-hydrate to produce a clean NodeDefinition dict for the response.
    persisted = BranchDefinition.from_dict(saved)
    updated_node = next(
        (n for n in persisted.node_defs if n.node_id == nid), target_node,
    )

    # #50: emit a node_edit_audit row capturing full pre/post node
    # bodies so `rollback_node` can restore the exact prior state.
    # ``triggered_by_judgment_id`` is optional — callers applying a
    # judgment-driven edit can pass it.
    try:
        from workflow.runs import record_node_edit_audit

        triggered = (
            kwargs.get("triggered_by_judgment_id") or ""
        ).strip() or None
        record_node_edit_audit(
            _base_path(),
            branch_def_id=bid,
            version_before=old_version,
            version_after=new_version,
            nodes_changed=[nid],
            triggered_by_judgment_id=triggered,
            node_before=node_before_body,
            node_after=updated_node.to_dict() if updated_node else {},
            edit_kind="update",
        )
    except Exception:
        logger.exception("node_edit_audit failed for %s/%s", bid, nid)

    changed_fields = sorted(updates.keys())
    branch_label = persisted.name or "unnamed"
    text_lines = [
        f"**Updated node `{nid}`** on workflow '{branch_label}' "
        f"(version {old_version} → {new_version}). "
        f"Fields changed: {', '.join(changed_fields) or '(none)'}.",
    ]
    # Summarize the node briefly so Claude.ai sees the new shape.
    body_kind = "prompt_template" if updated_node.prompt_template else (
        "source_code" if updated_node.source_code else "passthrough"
    )
    text_lines += [
        "",
        f"- display_name: {updated_node.display_name}",
        f"- phase: {updated_node.phase}",
        f"- body: {body_kind}",
    ]
    if body_kind == "prompt_template":
        preview = updated_node.prompt_template
        if len(preview) > 240:
            preview = preview[:240].rstrip() + "…"
        text_lines += ["", f"Template preview:\n\n```\n{preview}\n```"]

    return json.dumps({
        "text": "\n".join(text_lines),
        "status": "updated",
        "branch_def_id": bid,
        "node_id": nid,
        "version_before": old_version,
        "version_after": new_version,
        "changed_fields": changed_fields,
        "node": updated_node.to_dict(),
    }, default=str)


def _ext_branch_search_nodes(kwargs: dict[str, Any]) -> str:
    """Search NodeDefinitions across every Branch for reuse candidates.

    #62 Part B. The bot's reuse-vs-invent decision depends on being
    able to ask "what nodes already exist that might fit the role I
    need?". This action returns phone-card-sized hits ranked by
    substring match + reuse_count across Branches.

    Combined with #66's ``node_ref`` primitive, the flow is:
    search_nodes → pick a hit → build_branch / add_node with
    ``node_ref={source, node_id}``.
    """
    from workflow.daemon_server import search_nodes

    query = (kwargs.get("query") or "").strip()
    role = (kwargs.get("role") or kwargs.get("phase") or "").strip()
    limit = int(kwargs.get("limit", 20) or 20)

    entries = search_nodes(
        _base_path(),
        query=query,
        role=role,
        limit=limit,
    )

    header = "**Reusable nodes**"
    if query:
        header += f" matching '{query}'"
    if role:
        header += f" (phase={role})"
    lines = [header, ""]
    if entries:
        for e in entries[:12]:
            reuse_tag = (
                f" · used by {e['reuse_count']} branch"
                f"{'es' if e['reuse_count'] != 1 else ''}"
            )
            phase_tag = f" · phase={e['phase']}" if e.get("phase") else ""
            lines.append(
                f"- `{e['node_id']}` · **{e['display_name']}**"
                f"{phase_tag}{reuse_tag}"
            )
            desc = (e.get("description") or "").strip()
            if desc:
                lines.append(f"  {desc[:120]}")
            preview = (e.get("prompt_template_preview") or "").strip()
            if preview:
                lines.append(f"  _prompt:_ `{preview}`")
        if len(entries) > 12:
            lines.append(f"- … and {len(entries) - 12} more.")
        lines.append("")
        lines.append(
            "_To reuse: call `add_node` with "
            "`node_ref_json={\"source\": \"<branch_def_id>\", "
            "\"node_id\": \"<node_id>\"}`, or include the same "
            "`node_ref` inside a `spec_json` / `changes_json` node "
            "entry on build_branch / patch_branch. See #66._"
        )
    else:
        if query or role:
            lines.append(
                "_No existing nodes match. If you invent one, "
                "consider a node_id future callers would search for "
                "(e.g. `citation_audit` rather than `node_7`)._"
            )
        else:
            lines.append(
                "_No nodes registered yet. Build one with "
                "`extensions action=build_branch` and future callers "
                "will find it here._"
            )

    return json.dumps({
        "text": "\n".join(lines),
        "query": query,
        "role": role,
        "count": len(entries),
        "entries": entries,
    }, default=str)


# #64: whitelisted fields for bulk `patch_nodes`. Type coercion per
# field so phone-entered strings land as the right Python type.
_PATCH_NODES_FIELDS: dict[str, Any] = {
    "display_name": str,
    "description": str,
    "phase": str,
    "prompt_template": str,
    "source_code": str,
    "model_hint": str,
    "timeout_seconds": float,
    "enabled": bool,
}


def _coerce_patch_nodes_value(
    field: str, raw: Any,
) -> tuple[Any, str | None]:
    """Coerce a bulk-patch value into the right Python type.

    Returns ``(coerced, error)``. ``error`` non-None → reject without
    mutating any node; atomic.
    """
    kind = _PATCH_NODES_FIELDS[field]
    if kind is bool:
        if isinstance(raw, bool):
            return raw, None
        s = str(raw).strip().lower()
        if s in {"true", "1", "yes", "on"}:
            return True, None
        if s in {"false", "0", "no", "off"}:
            return False, None
        return None, f"Cannot coerce {raw!r} to bool."
    if kind is float:
        try:
            return float(raw), None
        except (TypeError, ValueError):
            return None, f"Cannot coerce {raw!r} to float."
    return str(raw), None


def _ext_branch_patch_nodes(kwargs: dict[str, Any]) -> str:
    """Bulk-set one field across N nodes in one call (#64).

    Different from ``patch_branch`` (heterogeneous batches of ops).
    ``patch_nodes`` is homogeneous: same field, same value, filtered by
    ``node_ids`` (default: all nodes on the branch). Atomic — if any
    node rejects, nothing is written.
    """
    from workflow.branches import BranchDefinition
    from workflow.daemon_server import (
        get_branch_definition,
        save_branch_definition,
    )

    bid = (kwargs.get("branch_def_id") or "").strip()
    if not bid:
        return json.dumps({
            "status": "rejected",
            "error": "branch_def_id is required for patch_nodes.",
        })
    field = (kwargs.get("field") or "").strip()
    if field not in _PATCH_NODES_FIELDS:
        return json.dumps({
            "status": "rejected",
            "error": (
                f"Unknown field '{field}'. patch_nodes supports: "
                f"{', '.join(sorted(_PATCH_NODES_FIELDS))}"
            ),
        })
    raw_value = kwargs.get("value")
    if raw_value is None or raw_value == "":
        return json.dumps({
            "status": "rejected",
            "error": "value is required.",
        })

    value, err = _coerce_patch_nodes_value(field, raw_value)
    if err is not None:
        return json.dumps({
            "status": "rejected",
            "error": f"Field '{field}': {err}",
        })

    if field == "phase" and value not in VALID_PHASES:
        return json.dumps({
            "status": "rejected",
            "error": (
                f"Invalid phase '{value}'. Must be one of: "
                f"{', '.join(sorted(VALID_PHASES))}"
            ),
        })

    _ensure_author_server_db()
    try:
        source = get_branch_definition(_base_path(), branch_def_id=bid)
    except KeyError:
        return json.dumps({
            "status": "rejected",
            "error": f"Branch '{bid}' not found.",
        })

    staging = BranchDefinition.from_dict(source)

    # Resolve target node set. Empty `node_ids` means "every node".
    target_ids_raw = kwargs.get("node_ids") or ""
    if isinstance(target_ids_raw, list):
        target_ids = [
            str(n).strip() for n in target_ids_raw if str(n).strip()
        ]
    else:
        target_ids = _split_csv(target_ids_raw)
    all_node_ids = [n.node_id for n in staging.node_defs]
    if not target_ids:
        target_ids = all_node_ids

    unknown = [nid for nid in target_ids if nid not in all_node_ids]
    if unknown:
        return json.dumps({
            "status": "rejected",
            "error": (
                f"Unknown node_ids on branch '{staging.name}': "
                f"{', '.join(unknown)}. Atomic — no node was patched."
            ),
        })

    if not target_ids:
        return json.dumps({
            "status": "rejected",
            "error": "Branch has no nodes to patch.",
        })

    # Apply the field. prompt_template / source_code are mutually
    # exclusive — clear the other when setting one.
    for node in staging.node_defs:
        if node.node_id not in target_ids:
            continue
        setattr(node, field, value)
        if field == "prompt_template" and value:
            node.source_code = ""
        elif field == "source_code" and value:
            node.prompt_template = ""

    old_version = int(source.get("version") or 1)
    new_version = old_version + 1
    staging_dict = staging.to_dict()
    staging_dict["version"] = new_version
    saved = save_branch_definition(_base_path(), branch_def=staging_dict)
    persisted = BranchDefinition.from_dict(saved)

    branch_label = persisted.name or "(unnamed workflow)"
    text = (
        f"**Updated `{field}` on {len(target_ids)} node(s)** of "
        f"workflow '{branch_label}'. New value: `{value}`. "
        f"(version {old_version} → {new_version})"
    )
    per_node = [
        {"node_id": nid, "status": "updated"} for nid in target_ids
    ]
    return json.dumps({
        "text": text,
        "status": "patched",
        "field": field,
        "value": value,
        "patched_count": len(target_ids),
        "version_before": old_version,
        "version_after": new_version,
        "node_results": per_node,
    }, default=str)


# ───────────────────────────────────────────────────────────────────────────
# continue_branch — workspace-memory continuity primitive
# ───────────────────────────────────────────────────────────────────────────


def _resolve_udir() -> Path:
    """Return the active universe directory (best-effort; never raises)."""
    try:
        uid = os.environ.get("UNIVERSE_SERVER_DEFAULT_UNIVERSE", "")
        if not uid:
            base = _base_path()
            if base.is_dir():
                subdirs = [d for d in base.iterdir() if d.is_dir()]
                if subdirs:
                    uid = subdirs[0].name
        if uid:
            return _universe_dir(uid)
    except Exception:  # noqa: BLE001
        pass
    return _base_path()


def _action_continue_branch(kwargs: dict[str, Any]) -> str:
    """Read-only composite that returns everything a chatbot needs to resume work.

    Composes: branch metadata, last-5 run records, open notes (branch-scoped),
    current daemon phase, session_boundary block.  Zero writes — safe to call
    on every session open.

    Spec: docs/vetted-specs.md §continue_branch
    """
    from workflow.daemon_server import get_branch_definition
    from workflow.runs import initialize_runs_db, query_runs

    bid = (kwargs.get("branch_def_id") or "").strip()
    if not bid:
        return json.dumps({"error": "branch_def_id is required."})

    base = _base_path()

    # ── 1. Branch metadata ───────────────────────────────────────────────────
    try:
        branch = get_branch_definition(base, branch_def_id=bid)
    except KeyError:
        return json.dumps({
            "error": (
                f"Branch '{bid}' not found. "
                "Use extensions action=build_branch to create it first."
            ),
        })

    branch_name: str = branch.get("name") or bid
    description: str = branch.get("description") or ""
    last_modified_at: str | None = branch.get("last_modified_at") or branch.get("updated_at")

    # ── 2. Run history (last 5, most recent first) ───────────────────────────
    initialize_runs_db(base)
    run_result = query_runs(
        base,
        branch_def_id=bid,
        filters={},
        select=[],
        limit=5,
    )
    run_rows: list[dict[str, Any]] = run_result.get("rows", [])
    run_history = [
        {
            "run_id": r.get("run_id"),
            "status": r.get("status"),
            "actor": r.get("actor"),
            "started_at": r.get("started_at"),
            "finished_at": r.get("finished_at"),
        }
        for r in run_rows
    ]

    # ── 3. Open notes scoped to this branch (last 10) ───────────────────────
    # notes.json lives in the active universe dir.  Scope = notes whose
    # "target_id" or "branch_def_id" field matches bid, or that have no
    # target (universe-global user/editor/structural notes are included).
    udir = _resolve_udir()
    raw_notes = _read_json(udir / "notes.json")
    open_notes: list[dict[str, Any]] = []
    if raw_notes and isinstance(raw_notes, list):
        wanted_types = {"user", "editor", "structural"}
        for n in raw_notes:
            nt = n.get("note_type") or n.get("type") or ""
            if nt not in wanted_types:
                continue
            # Branch-scoped notes or universe-global notes (no branch_def_id field).
            note_bid = n.get("branch_def_id") or n.get("target_id") or ""
            if note_bid and note_bid != bid:
                continue
            open_notes.append({
                "note_id": n.get("note_id") or n.get("id"),
                "note_type": nt,
                "text": (n.get("text") or "")[:500],
                "timestamp": n.get("timestamp"),
            })
        open_notes = open_notes[-10:]

    # ── 4. Current daemon phase (best-effort, never raises) ─────────────────
    # Check if any run for this branch is currently in "running" state.
    current_phase: str | None = None
    try:
        active_result = query_runs(
            base,
            branch_def_id=bid,
            filters={"status": "running"},
            select=[],
            limit=1,
        )
        active_rows = active_result.get("rows", [])
        if active_rows:
            current_phase = active_rows[0].get("status")
    except Exception:  # noqa: BLE001
        pass

    # ── 5. session_boundary (same logic as get_status) ───────────────────────
    account_user = os.environ.get("UNIVERSE_SERVER_USER", "anonymous")
    prior_session_ts: str | None = None
    try:
        import re as _re
        log_path = udir / "activity.log"
        if log_path.exists():
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            for line in reversed(lines[-200:]):
                if account_user in line:
                    m = _re.match(r"\[(\d{4}-\d{2}-\d{2}[^\]]*)\]", line)
                    if m:
                        prior_session_ts = m.group(1)
                        break
    except Exception:  # noqa: BLE001
        pass

    prior_session_available: bool = prior_session_ts is not None
    if prior_session_available:
        session_boundary = {
            "prior_session_context_available": True,
            "account_user": account_user,
            "last_session_ts": prior_session_ts,
            "note": (
                f"Activity log contains entries for '{account_user}'. "
                "Prior session context may be available."
            ),
        }
    else:
        session_boundary = {
            "prior_session_context_available": False,
            "account_user": account_user,
            "last_session_ts": None,
            "note": (
                f"No activity log entries found for '{account_user}'. "
                "Chatbot has no prior session record — do not assert prior session context."
            ),
        }

    # ── 6. chatbot_summary (pre-composed, anti-hallucination) ───────────────
    run_count = len(run_history)
    completed = sum(1 for r in run_history if r.get("status") == "completed")
    note_count = len(open_notes)

    if prior_session_available:
        session_line = f"Last session recorded: {prior_session_ts}."
    else:
        session_line = (
            "No prior session history is recorded — this may be your first time "
            "running this branch, or context was not captured."
        )

    if run_count == 0:
        progress_line = "No runs have been recorded for this branch yet."
    else:
        last_run = run_history[0]
        progress_line = (
            f"{run_count} run(s) on record; {completed} completed. "
            f"Most recent run: status={last_run.get('status')}, "
            f"started {last_run.get('started_at')}."
        )

    if current_phase:
        phase_line = f"Current daemon phase: {current_phase}."
    else:
        phase_line = ""

    if note_count == 0:
        notes_line = "No open notes."
    elif note_count <= 2:
        quoted = "; ".join(
            f'"{n["text"][:120]}"' for n in open_notes if n.get("text")
        )
        notes_line = f"{note_count} open note(s): {quoted}"
    else:
        notes_line = f"{note_count} open notes (use list_canon or inspect to see all)."

    parts = [
        f"Branch: {branch_name!r}.",
        session_line,
        progress_line,
    ]
    if phase_line:
        parts.append(phase_line)
    parts.append(notes_line)
    chatbot_summary = " ".join(p for p in parts if p)

    return json.dumps(
        {
            "branch_def_id": bid,
            "branch_name": branch_name,
            "description": description,
            "last_modified_at": last_modified_at,
            "run_history": run_history,
            "open_notes": open_notes,
            "current_phase": current_phase,
            "session_boundary": session_boundary,
            "prior_session_available": prior_session_available,
            "chatbot_summary": chatbot_summary,
        },
        default=str,
    )


def _action_fork_tree(kwargs: dict[str, Any]) -> str:
    from workflow.branch_versions import get_branch_version, list_branch_versions
    from workflow.daemon_server import get_branch_definition, list_branch_definitions

    bid = (kwargs.get("branch_def_id") or "").strip()
    if not bid:
        return json.dumps({"error": "branch_def_id is required."})

    try:
        root = get_branch_definition(_base_path(), branch_def_id=bid)
    except KeyError:
        return json.dumps({"error": f"branch_def_id '{bid}' not found."})

    # Walk ancestor chain via fork_from (branch_version_id → branch_def_id).
    ancestors: list[dict[str, Any]] = []
    seen_bids: set[str] = {bid}
    current_bvid = root.get("fork_from")
    while current_bvid:
        bv = get_branch_version(_base_path(), current_bvid)
        if bv is None:
            break
        anc_bid = bv.branch_def_id
        if anc_bid in seen_bids:
            break  # cycle guard
        seen_bids.add(anc_bid)
        try:
            anc = get_branch_definition(_base_path(), branch_def_id=anc_bid)
        except KeyError:
            break
        ancestors.append({
            "branch_def_id": anc_bid,
            "name": anc.get("name", ""),
            "author": anc.get("author", ""),
            "fork_from_version": current_bvid,
        })
        current_bvid = anc.get("fork_from")

    # Find descendants: branches whose fork_from matches any version of this branch.
    versions = list_branch_versions(_base_path(), bid, limit=200)
    version_ids = {v.branch_version_id for v in versions}
    descendants: list[dict[str, Any]] = []
    all_branches = list_branch_definitions(_base_path(), include_private=False)
    for b in all_branches:
        ff = b.get("fork_from")
        if ff and ff in version_ids:
            descendants.append({
                "branch_def_id": b["branch_def_id"],
                "name": b.get("name", ""),
                "author": b.get("author", ""),
                "fork_from_version": ff,
                "published_versions_count": len(
                    list_branch_versions(_base_path(), b["branch_def_id"], limit=500)
                ),
            })

    return json.dumps({
        "branch_def_id": bid,
        "name": root.get("name", ""),
        "fork_from": root.get("fork_from"),
        "ancestors": ancestors,
        "descendant_count": len(descendants),
        "descendants": descendants[:50],
    }, default=str)


_BRANCH_ACTIONS: dict[str, Any] = {
    "create_branch": _ext_branch_create,
    "get_branch": _ext_branch_get,
    "list_branches": _ext_branch_list,
    "delete_branch": _ext_branch_delete,
    "add_node": _ext_branch_add_node,
    "connect_nodes": _ext_branch_connect_nodes,
    "set_entry_point": _ext_branch_set_entry_point,
    "add_state_field": _ext_branch_add_state_field,
    "validate_branch": _ext_branch_validate,
    "describe_branch": _ext_branch_describe,
    "build_branch": _ext_branch_build,
    "patch_branch": _ext_branch_patch,
    "patch_nodes": _ext_branch_patch_nodes,
    "update_node": _ext_branch_update_node,
    "search_nodes": _ext_branch_search_nodes,
    "continue_branch": _action_continue_branch,
    "fork_tree": _action_fork_tree,
}

_BRANCH_WRITE_ACTIONS: frozenset[str] = frozenset({
    "create_branch", "add_node", "connect_nodes",
    "set_entry_point", "add_state_field", "delete_branch",
    "build_branch", "patch_branch", "patch_nodes", "update_node",
})


@mcp.prompt(
    title="Branch Design Guide",
    tags={"branches", "extensions", "graph", "customization"},
)
def branch_design_guide() -> str:
    """Walk through designing a BranchDefinition with the `extensions` tool.

    Returns a guide covering the create → add_node → connect_nodes →
    set_entry_point → add_state_field → validate → describe loop, plus
    the recipe-tracker example.
    """
    return _BRANCH_DESIGN_GUIDE


_BRANCH_DESIGN_GUIDE = """\
You help users author community-designed graph branches through the
`extensions` tool. A branch is a LangGraph topology (nodes + edges +
state schema) the user can fork, share, and (in Phase 3) run.

## Before you invent — search for reusable nodes

Before you design any node for the user's new Branch, check whether an
existing node already fills the role. Every node already on the server
was written once and validated; reusing it preserves lineage and lets
comparative evaluation (judge_run, compare_runs) work across branches.

```
extensions action=search_nodes node_query="citation audit"
extensions action=search_nodes node_query="outline" phase="plan"
goals action=common_nodes scope=all min_branches=2
```

For each relevant hit, point the user at it and ask whether to reuse.
If yes, include a `node_ref` inside the `node_defs` entry rather than
restating source_code / prompt_template:

```
{"node_id": "citation_audit",
 "node_ref": {"source": "<branch_def_id_from_search>",
              "node_id": "citation_audit"}}
```

Copy semantics are the default and usually what the user wants — the
canonical body is snapshotted into the new Branch and diverges from
there. If the user later edits it on either side, the other stays
unchanged. (v1; live shared nodes may come later.)

Bare `node_id` that collides with an existing standalone registered
node is REJECTED by the server; you must pass `node_ref` or
`intent="copy"` or rename. This is intentional — silent shadowing was
a bug (#66).

## Author flow (PREFERRED — one round trip)

Use `build_branch` with the whole workflow in a single `spec_json`.
You get back a validated branch with a mermaid diagram in one call —
no per-node chatter, no tool-call budget burn:

```
extensions action=build_branch spec_json='{
  "name": "Recipe tracker",
  "description": "Capture, categorize, archive recipes",
  "entry_point": "capture",
  "node_defs": [
    {"node_id": "capture", "display_name": "Capture raw recipe",
     "prompt_template": "Read the user's message and extract recipe name."},
    {"node_id": "categorize", "display_name": "Categorize recipe",
     "prompt_template": "Classify by cuisine and meal type."},
    {"node_id": "archive", "display_name": "Archive to library",
     "prompt_template": "Format as a wiki entry and file it."}
  ],
  "edges": [
    {"from": "START", "to": "capture"},
    {"from": "capture", "to": "categorize"},
    {"from": "categorize", "to": "archive"},
    {"from": "archive", "to": "END"}
  ],
  "state_schema": [
    {"name": "raw_recipe", "type": "str"},
    {"name": "category", "type": "str"},
    {"name": "archived", "type": "bool", "default": false}
  ]
}'
```

If validation fails, `build_branch` returns concrete `suggestions` with
proposed fixes — apply them and retry. No partial branch is ever visible.

## Editing an existing workflow (PREFERRED)

Use `patch_branch` with a batch of ops. Transactional — all land or none:

```
extensions action=patch_branch branch_def_id=... changes_json='[
  {"op": "add_node", "node_id": "novelty_check",
   "display_name": "Novelty assessor",
   "prompt_template": "Rate novelty of: {claim}"},
  {"op": "add_edge", "from": "categorize", "to": "novelty_check"},
  {"op": "add_edge", "from": "novelty_check", "to": "archive"},
  {"op": "remove_edge", "from": "categorize", "to": "archive"},
  {"op": "add_state_field", "name": "novelty_score", "type": "float"}
]'
```

## Atomic actions (single-item surgery only)

Use these ONLY when the user wants exactly one small change and the
per-turn tool-call budget is not at risk:

- `create_branch name="..." description="..."`
- `add_node branch_def_id=... node_id=... display_name=... prompt_template=...`
- `connect_nodes branch_def_id=... from_node=... to_node=...`
- `set_entry_point branch_def_id=... node_id=...`
- `add_state_field branch_def_id=... field_name=... field_type=...`
- `validate_branch branch_def_id=...`
- `describe_branch branch_def_id=...`

## Hard rule

After `describe_branch`, tell the user their branch is ready to run. Use
`run_branch` with a JSON `inputs_json` that fills the state_schema fields.
The runner returns a `run_id`, final status, and per-node trace.

## Power users

Pass `source_code="def run(state): ..."` instead of `prompt_template`
for code nodes. Pass `reducer="append"` on `add_state_field` for
accumulating list fields. The same 10 actions cover both audiences;
the difference is how much you abstract on the user's behalf.

## Running a branch

Once validated, execute with:

- `run_branch branch_def_id=... inputs_json='{"raw_recipe": "pasta"}'`
- `get_run run_id=...` for a full snapshot with mermaid + per-node status.
- `stream_run run_id=... since_step=-1` to poll incrementally.
- `get_run_output run_id=... field_name=archived` to pull one field.
- `cancel_run run_id=...` to request cooperative stop.

The never-simulate rule lives in `control_station` (hard rule 5):
if run_branch fails, the branch isn't validated, or a source_code node
isn't approved, state the reason and stop.
"""


# ───────────────────────────────────────────────────────────────────────────
# Phase 3: Graph Runner — execute a BranchDefinition
# ───────────────────────────────────────────────────────────────────────────
# The runner compiles a validated branch into a LangGraph StateGraph via
# `workflow.graph_compiler.compile_branch`, runs it synchronously against
# user-supplied inputs, and persists run metadata + per-node events in
# `<base>/.runs.db`. Status-aware mermaid diagrams are returned so
# Claude.ai can auto-visualize the live/completed graph. True async
# execution is task #39 (Phase 3.5).


def _run_mermaid_from_events(
    branch_def_id: str,
    node_statuses: list[dict[str, Any]],
) -> str:
    """Render a status-colored mermaid flowchart for a run snapshot.

    Colors: ran=green, running=amber, failed=red, pending=grey. The caller
    embeds this in the `summary` markdown and as a top-level field so
    Claude.ai auto-renders.
    """
    from workflow.branches import BranchDefinition
    from workflow.daemon_server import get_branch_definition

    try:
        source_dict = get_branch_definition(
            _base_path(), branch_def_id=branch_def_id,
        )
    except KeyError:
        return "```mermaid\nflowchart LR\n    missing_branch[\"(branch not found)\"]\n```"

    branch = BranchDefinition.from_dict(source_dict)
    status_by_id = {s["node_id"]: s["status"] for s in node_statuses}

    lines: list[str] = ["```mermaid", "flowchart LR"]
    lines.append('    START(["START"])')
    lines.append('    END(["END"])')

    for node in branch.node_defs:
        nid = _mermaid_node_id(node.node_id)
        label = _mermaid_label(node.display_name or node.node_id)
        lines.append(f'    {nid}["{label}"]')

    for edge in branch.edges:
        src = _mermaid_node_id(edge.from_node)
        dst = _mermaid_node_id(edge.to_node)
        lines.append(f"    {src} --> {dst}")

    # Apply status classes per node.
    status_classes = {
        "ran": "ran",
        "running": "running",
        "failed": "failed",
        "pending": "pending",
    }
    for node in branch.node_defs:
        nid = _mermaid_node_id(node.node_id)
        st = status_by_id.get(node.node_id, "pending")
        cls = status_classes.get(st, "pending")
        lines.append(f"    class {nid} {cls}")

    lines.extend([
        "    classDef ran fill:#d4edda,stroke:#28a745,stroke-width:2px",
        "    classDef running fill:#fff3cd,stroke:#ffc107,stroke-width:2px",
        "    classDef failed fill:#f8d7da,stroke:#dc3545,stroke-width:2px",
        "    classDef pending fill:#e9ecef,stroke:#6c757d,stroke-width:1px",
    ])

    lines.append("```")
    return "\n".join(lines)


_RUNS_RECOVERY_DONE = False


def _ensure_runs_recovery() -> None:
    """Once per process, mark any queued/running rows in the runs DB as
    ``interrupted``. Called from Phase 3 run handlers so the recovery
    happens on first use without needing a server start hook."""
    global _RUNS_RECOVERY_DONE
    if _RUNS_RECOVERY_DONE:
        return
    try:
        from workflow.runs import recover_in_flight_runs

        recover_in_flight_runs(_base_path())
    except Exception:
        logger.exception("in-flight run recovery failed")
    _RUNS_RECOVERY_DONE = True


_FAILURE_TAXONOMY: list[tuple[type, str, str]] = []


def _build_failure_taxonomy() -> list[tuple[type, str, str]]:
    """Build the (exc_type, failure_class, suggested_action) table lazily."""
    rows: list[tuple[type, str, str]] = []
    try:
        from workflow.graph_compiler import EmptyResponseError
        rows.append((
            EmptyResponseError,
            "empty_llm_response",
            "Check provider config or try a different model via the llm_type param.",
        ))
    except ImportError:
        pass
    rows.append((
        RecursionError,
        "recursion_limit",
        "Branch loop may be too deep; raise recursion_limit_override param or simplify loop.",
    ))
    rows.append((
        TimeoutError,
        "timeout",
        "Branch run timed out; try a shorter branch or increase timeout param.",
    ))
    return rows


def _actionable_by(failure_class: str) -> str:
    """Look up `actionable_by` for a failure_class via the canonical table.

    BUG-029 surface: chatbot reads this field to know whether to retry
    via another tool call ("chatbot"), surface a host-action to the user
    ("host"), escalate the raw error to the user for human judgment
    ("user"), or accept the run as terminal-by-design with no recovery
    path ("none" — e.g. cancelled).

    Defaults to "user" — never silently drops the field; conservative
    "ask the human" beats silent absence. Use "none" only when the
    failure is genuinely unrecoverable.
    """
    from workflow.runs import ACTIONABLE_BY
    return ACTIONABLE_BY.get(failure_class, "user")


def _failure_payload(
    exc: Exception, failure_class: str, suggested_action: str,
) -> dict[str, Any]:
    """Construct the standard failure response with all 3 BUG-029 fields."""
    return {
        "status": "error",
        "error": f"Run failed: {exc}",
        "failure_class": failure_class,
        "suggested_action": suggested_action,
        "actionable_by": _actionable_by(failure_class),
    }


def _classify_run_error(exc: Exception, bid: str) -> dict[str, Any]:
    for exc_type, failure_class, suggested_action in _build_failure_taxonomy():
        if isinstance(exc, exc_type):
            return _failure_payload(exc, failure_class, suggested_action)
    msg = str(exc).lower()
    if "quota" in msg or "rate limit" in msg or "rate_limit" in msg or "ratelimit" in msg:
        return _failure_payload(
            exc, "quota_exhausted",
            "Provider quota or rate limit hit; wait before retrying OR"
            " switch providers via the llm_type param.",
        )
    if "auth expir" in msg or "token expir" in msg or "credential" in msg:
        return _failure_payload(
            exc, "permission_denied:auth_expired",
            "Provider credentials have expired; re-authenticate or rotate the API key.",
        )
    if "permission denied" in msg:
        return _failure_payload(
            exc, "permission_denied:approval_required",
            "Ask host to approve the source_code node via extensions"
            " action=approve_source_code before running.",
        )
    if "approv" in msg or "source_code" in msg:
        return _failure_payload(
            exc, "node_not_approved",
            "Ask host to approve the source_code node via extensions"
            " action=approve_source_code before running.",
        )
    if "concurrent" in msg or "conflict" in msg or "modified" in msg or "stale" in msg:
        return _failure_payload(
            exc, "state_mutation_conflict",
            "Concurrent modification detected; re-fetch the branch state"
            " with get_branch then reapply your edit.",
        )
    if "provider" in msg or "api key" in msg or "api_key" in msg or "auth" in msg:
        return _failure_payload(
            exc, "provider_unavailable",
            "No LLM provider is reachable; check ANTHROPIC/GROQ/GEMINI keys.",
        )
    return _failure_payload(
        exc, "unknown",
        f"Inspect the run transcript with get_run for branch '{bid}' details.",
    )


def _classify_run_outcome_error(error_str: str) -> tuple[str, str] | None:
    """Map a stored run-failure error string to (failure_class, suggested_action).

    Called on RunOutcome objects whose error was recorded by the async runner,
    so exception type is gone — only the serialised string remains.  Returns
    None when the error does not match any known pattern (caller keeps raw
    error string and omits failure_class / suggested_action).
    """
    msg = error_str.lower()
    if "empty" in msg and ("llm" in msg or "response" in msg or "provider" in msg):
        return (
            "empty_llm_response",
            "Check provider config or try a different model via the llm_type param.",
        )
    if "timed out" in msg or "timeout" in msg:
        return (
            "timeout",
            "Branch run timed out; try a shorter branch or increase timeout param.",
        )
    if "quota" in msg or "rate limit" in msg or "rate_limit" in msg or "ratelimit" in msg:
        return (
            "quota_exhausted",
            "Provider quota or rate limit hit; wait before retrying OR"
            " switch providers via the llm_type param.",
        )
    if "overload" in msg or "503" in msg or "service unavailable" in msg or "server error" in msg:
        return (
            "provider_overloaded",
            "Provider is temporarily overloaded; wait 30-60s then retry"
            " or switch llm_type.",
        )
    if (
        "maximum context length" in msg
        or "context_length_exceeded" in msg
        or "tokens exceeded" in msg
        or "too many tokens" in msg
    ):
        return (
            "context_length_exceeded",
            "Input or accumulated state is too long for this provider;"
            " try a branch with fewer nodes or a higher-context model.",
        )
    if "auth expir" in msg or "token expir" in msg or "credential" in msg:
        return (
            "permission_denied:auth_expired",
            "Provider credentials have expired; re-authenticate or rotate the API key.",
        )
    if "approv" in msg or "source_code" in msg:
        return (
            "node_not_approved",
            "Ask host to approve the source_code node via extensions"
            " action=approve_source_code before running.",
        )
    if "permission denied" in msg:
        return (
            "permission_denied:approval_required",
            "Ask host to approve the source_code node via extensions"
            " action=approve_source_code before running.",
        )
    if "exit code" in msg or "subprocess failure" in msg or "api likely unavailable" in msg:
        return (
            "provider_subprocess_failed",
            "Provider CLI process failed; check that claude/codex binary is"
            " installed and reachable.",
        )
    if "concurrent" in msg or "conflict" in msg or "modified" in msg or "stale" in msg:
        return (
            "state_mutation_conflict",
            "Concurrent modification detected; re-fetch the branch state"
            " with get_branch then reapply your edit.",
        )
    if "provider" in msg or "api key" in msg or "api_key" in msg:
        return (
            "provider_unavailable",
            "No LLM provider is reachable; check ANTHROPIC/GROQ/GEMINI keys.",
        )
    if "call failed" in msg or "groq" in msg or "gemini" in msg or "grok" in msg:
        return (
            "provider_error",
            "Provider returned an unexpected error; check provider logs"
            " or try a different llm_type.",
        )
    return None


def _action_run_branch(kwargs: dict[str, Any]) -> str:
    """Execute a branch once.

    Durability guarantee (v1): runs are *terminal-on-restart*. If the
    daemon exits while a run is in flight, the row is marked
    ``interrupted`` on next startup (see
    ``workflow.runs.recover_in_flight_runs``) and ``get_run`` returns
    ``resumable=false`` with ``resumable_reason="v1 terminal-on-restart"``.
    To continue, re-invoke ``run_branch`` with the same ``branch_def_id``
    and ``inputs_json`` — a new ``run_id`` is returned. Mid-run resume
    from a SqliteSaver checkpoint is a future extension and is not
    available today; do not poll an ``interrupted`` run expecting it to
    flip back to ``running``.
    """
    from workflow.branches import BranchDefinition
    from workflow.daemon_server import get_branch_definition
    from workflow.runs import execute_branch_async

    _ensure_runs_recovery()

    bid = _resolve_branch_id(kwargs.get("branch_def_id", "").strip(), _base_path())
    if not bid:
        return json.dumps({"error": "branch_def_id is required."})

    try:
        source_dict = get_branch_definition(_base_path(), branch_def_id=bid)
    except KeyError:
        return json.dumps({"error": f"Branch '{bid}' not found."})

    branch = BranchDefinition.from_dict(source_dict)
    errors = branch.validate()
    if errors:
        return json.dumps({
            "error": "Branch is not valid. Fix these before running:",
            "validation_errors": errors,
        })

    inputs_raw = kwargs.get("inputs_json", "").strip()
    inputs: dict[str, Any] = {}
    if inputs_raw:
        try:
            parsed = json.loads(inputs_raw)
            if not isinstance(parsed, dict):
                return json.dumps({
                    "error": "inputs_json must decode to a JSON object.",
                })
            inputs = parsed
        except json.JSONDecodeError as exc:
            return json.dumps({
                "error": f"inputs_json is not valid JSON: {exc}",
            })

    # Real provider — lazy import so test envs without providers work.
    provider_call: Any = None
    try:
        from domains.fantasy_author.phases._provider_stub import (
            call_provider as provider_call,
        )
    except ImportError:
        provider_call = None

    # Parse + validate recursion_limit_override (10-1000).
    _rl_raw = kwargs.get("recursion_limit_override", "")
    recursion_limit_override: int | None = None
    if _rl_raw:
        try:
            _rl_val = int(_rl_raw)
        except (TypeError, ValueError):
            return json.dumps({"error": "recursion_limit_override must be an integer."})
        if not 10 <= _rl_val <= 1000:
            return json.dumps({
                "error": (
                    f"recursion_limit_override {_rl_val} out of range. "
                    "Valid range: 10-1000."
                ),
            })
        recursion_limit_override = _rl_val

    try:
        outcome = execute_branch_async(
            _base_path(),
            branch=branch,
            inputs=inputs,
            run_name=kwargs.get("run_name", ""),
            actor=_current_actor(),
            provider_call=provider_call,
            recursion_limit_override=recursion_limit_override,
        )
    except Exception as exc:
        logger.exception("run_branch failed for %s", bid)
        return json.dumps(_classify_run_error(exc, bid))

    # Write-ack per tool_return_shapes.md §Write actions. Phase 3.5 async:
    # the graph is running in a background worker, so the MCP call returns
    # status=queued almost immediately. The text channel is phone-legible
    # (no raw IDs); the run_id lives in structuredContent for the next
    # tool call.
    error_annotation = _classify_run_outcome_error(outcome.error) if outcome.error else None
    error_lines: list[str] = []
    if outcome.error:
        error_lines.append(f"Error: {outcome.error}")
    if error_annotation:
        error_lines.append(f"Suggested action: {error_annotation[1]}")
    text = "\n".join([
        f"**Run {outcome.status}.** Workflow handed to the "
        "background executor.",
        "",
        *error_lines,
        "Use `get_run` to read a snapshot, `stream_run` to poll for "
        "progress, or `cancel_run` to stop. Each takes a `run_id` "
        "from the structured content of this response.",
    ]).strip()

    result: dict[str, Any] = {
        "text": text,
        "run_id": outcome.run_id,
        "status": outcome.status,
        "output": outcome.output,
        "error": outcome.error,
    }
    if error_annotation:
        result["failure_class"] = error_annotation[0]
        result["suggested_action"] = error_annotation[1]
        result["actionable_by"] = _actionable_by(error_annotation[0])
    return json.dumps(result)


def _branch_name_for_run(run_record: dict[str, Any]) -> str:
    """Fetch the human-legible branch name for a run record.

    Text channels should surface names, never raw branch_def_id strings.
    Falls back to ``(unknown workflow)`` when the branch is missing.
    """
    from workflow.branches import BranchDefinition
    from workflow.daemon_server import get_branch_definition

    try:
        source_dict = get_branch_definition(
            _base_path(),
            branch_def_id=run_record.get("branch_def_id", ""),
        )
        branch = BranchDefinition.from_dict(source_dict)
        return branch.name or "(unnamed workflow)"
    except Exception:
        return "(unknown workflow)"


def _compose_run_snapshot(
    run_record: dict[str, Any],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Pack run metadata + node statuses + mermaid into a phone-legible dict."""
    from workflow.branches import BranchDefinition
    from workflow.daemon_server import get_branch_definition
    from workflow.runs import build_node_status_map

    declared_order: list[str] = []
    branch_name = ""
    try:
        source_dict = get_branch_definition(
            _base_path(), branch_def_id=run_record["branch_def_id"],
        )
        branch = BranchDefinition.from_dict(source_dict)
        declared_order = [gn.id for gn in branch.graph_nodes]
        branch_name = branch.name or ""
    except KeyError:
        pass

    node_statuses = build_node_status_map(events, declared_order)
    mermaid = _run_mermaid_from_events(
        run_record["branch_def_id"], node_statuses,
    )

    node_lines = (
        [f"  - {s['node_id']}: {s['status']}" for s in node_statuses]
        or ["  (no nodes reported)"]
    )
    # Phone-legible header — name first, IDs only in structuredContent.
    header_branch = branch_name or "(branch)"
    summary = "\n".join([
        f"**Run on workflow `{header_branch}`** — status "
        f"`{run_record['status']}`",
        f"Actor: {run_record['actor']}",
        "",
        "Nodes:",
        *node_lines,
        "",
        "Graph:",
        mermaid,
    ])

    # Surface the applied recursion limit from the __system__ event if present.
    recursion_limit: int | None = None
    for ev in events:
        if ev.get("node_id") == "__system__" and ev.get("status") == "recursion_limit_applied":
            try:
                recursion_limit = int(ev.get("detail", {}).get("recursion_limit", 0)) or None
            except (TypeError, ValueError):
                pass
            break

    snapshot: dict[str, Any] = {
        "text": summary,
        "run_id": run_record["run_id"],
        "branch_def_id": run_record["branch_def_id"],
        "status": run_record["status"],
        "actor": run_record["actor"],
        "last_node_id": run_record.get("last_node_id", ""),
        "started_at": run_record.get("started_at"),
        "finished_at": run_record.get("finished_at"),
        "error": run_record.get("error", ""),
        "node_statuses": node_statuses,
        "mermaid": mermaid,
        "summary": summary,
        "recursion_limit": recursion_limit,
    }
    # INTERRUPTED runs are terminal in v1 (durability guarantee — see
    # ``_action_run_branch`` docstring + ``runs.recover_in_flight_runs``).
    # The client must rerun with the same ``inputs_json``; it cannot be
    # polled to recovery. Surface this explicitly so chatbots don't
    # busy-wait forever.
    if run_record["status"] == "interrupted":
        snapshot["resumable"] = False
        snapshot["resumable_reason"] = "v1 terminal-on-restart"
    # BUG-029: enrich failed snapshots so chatbots have a user-actionable hint.
    # `actionable_by` tells the chatbot WHO can fix it — chatbot/host/user —
    # so it doesn't have to guess (Mara's failure mode 2026-04-24).
    if run_record["status"] == "failed":
        error_annotation = _classify_run_outcome_error(run_record.get("error", ""))
        if error_annotation:
            snapshot["failure_class"] = error_annotation[0]
            snapshot["suggested_action"] = error_annotation[1]
            snapshot["actionable_by"] = _actionable_by(error_annotation[0])
    return snapshot


def _action_get_run(kwargs: dict[str, Any]) -> str:
    from workflow.runs import get_run as _get_run
    from workflow.runs import list_events

    rid = kwargs.get("run_id", "").strip()
    if not rid:
        return json.dumps({"error": "run_id is required."})

    record = _get_run(_base_path(), rid)
    if record is None:
        return json.dumps({"error": f"Run '{rid}' not found."})

    events = list_events(_base_path(), rid)
    return json.dumps(_compose_run_snapshot(record, events), default=str)


def _action_list_runs(kwargs: dict[str, Any]) -> str:
    from workflow.runs import list_runs as _list_runs

    rows = _list_runs(
        _base_path(),
        branch_def_id=kwargs.get("branch_def_id", ""),
        status=kwargs.get("status", ""),
        limit=int(kwargs.get("limit", 50) or 50),
    )
    summaries = [
        {
            "run_id": r["run_id"],
            "branch_def_id": r["branch_def_id"],
            "run_name": r["run_name"],
            "status": r["status"],
            "actor": r["actor"],
            "started_at": r.get("started_at"),
            "finished_at": r.get("finished_at"),
            "last_node_id": r.get("last_node_id", ""),
        }
        for r in rows
    ]
    # Catalog shape per tool_return_shapes.md — compact markdown list
    # for phone clients; full fidelity is in the `runs` array.
    if summaries:
        lines = [f"**{len(summaries)} run(s):**", ""]
        for s in summaries[:12]:
            name = s["run_name"] or s["run_id"]
            lines.append(
                f"- `{s['run_id']}` · {s['status']} · "
                f"branch={s['branch_def_id']}"
                + (f" · name={name}" if s['run_name'] else "")
            )
        if len(summaries) > 12:
            lines.append(
                f"- … and {len(summaries) - 12} more. Narrow with "
                "`branch_def_id=...` or `status=...`."
            )
        text = "\n".join(lines)
    else:
        text = "No runs match the filter."
    return json.dumps({
        "text": text,
        "runs": summaries,
        "count": len(summaries),
    }, default=str)


def _action_stream_run(kwargs: dict[str, Any]) -> str:
    from workflow.runs import get_run as _get_run
    from workflow.runs import list_events

    rid = kwargs.get("run_id", "").strip()
    if not rid:
        return json.dumps({"error": "run_id is required."})

    record = _get_run(_base_path(), rid)
    if record is None:
        return json.dumps({"error": f"Run '{rid}' not found."})

    since = int(kwargs.get("since_step", -1))
    events = list_events(_base_path(), rid, since_step=since)
    next_cursor = max(
        (e.get("step_index", since) for e in events), default=since,
    )

    # State-over-time shape per tool_return_shapes.md — ordered event
    # ticks, tight one-line per event for phone polling.
    if events:
        lines = [
            f"**Run {record['status']}** · {len(events)} new event(s)",
            "",
        ]
        for e in events[-12:]:
            lines.append(
                f"- step {e.get('step_index')} · "
                f"`{e.get('node_id', '?')}` · {e.get('status', '?')}"
            )
        if len(events) > 12:
            lines.insert(
                2, f"_(showing last 12 of {len(events)})_\n",
            )
        lines.append("")
        lines.append(f"Next poll: `since_step={next_cursor}`.")
        text = "\n".join(lines)
    else:
        text = (
            f"No new events since step {since}. "
            f"Run status: `{record['status']}`."
        )

    return json.dumps({
        "text": text,
        "run_id": rid,
        "status": record["status"],
        "events": events,
        "next_cursor": next_cursor,
    }, default=str)


def _action_wait_for_run(kwargs: dict[str, Any]) -> str:
    """Long-poll for new events on a run (#65).

    Holds the response for up to ``max_wait_s`` OR until new events
    land, then returns everything since ``since_step``. One tool call
    covers ~60s of run wall time — dramatically cheaper than repeated
    stream_run polls on the Claude.ai per-turn budget.
    """
    from workflow.runs import await_run_events
    from workflow.runs import get_run as _get_run

    rid = kwargs.get("run_id", "").strip()
    if not rid:
        return json.dumps({
            "error": "run_id is required for wait_for_run.",
        })
    record = _get_run(_base_path(), rid)
    if record is None:
        return json.dumps({"error": f"Run '{rid}' not found."})

    # Bound max_wait_s to 120s so a broken client can't tie up the
    # server thread forever. Default 60s per spec.
    raw_wait = kwargs.get("max_wait_s", 60)
    try:
        max_wait_s = max(0.5, min(120.0, float(raw_wait)))
    except (TypeError, ValueError):
        max_wait_s = 60.0
    since = int(kwargs.get("since_step", -1) or -1)

    result = await_run_events(
        _base_path(), rid,
        since_step=since,
        max_wait_s=max_wait_s,
    )
    events = result["events"]
    status = result["status"]
    next_cursor = result["next_cursor"]
    reason = result["reason"]
    waited = result["waited_s"]

    if events:
        header = (
            f"**Run status: `{status}`** · {len(events)} new event(s) "
            f"after waiting {waited}s."
        )
    elif reason == "terminal":
        header = (
            f"**Run finished** with status `{status}` "
            f"({waited}s wait)."
        )
    else:
        header = (
            f"**Still running** — no new events in {waited}s. "
            f"Status: `{status}`."
        )

    lines = [header, ""]
    for e in events[-12:]:
        lines.append(
            f"- step {e.get('step_index')} · "
            f"`{e.get('node_id', '?')}` · {e.get('status', '?')}"
        )
    if len(events) > 12:
        lines.insert(
            2, f"_(showing last 12 of {len(events)})_\n",
        )
    if events:
        lines.append("")
        lines.append(f"Next poll: `since_step={next_cursor}`.")
    text = "\n".join(lines)

    return json.dumps({
        "text": text,
        "run_id": rid,
        "status": status,
        "events": events,
        "next_cursor": next_cursor,
        "waited_s": waited,
        "reason": reason,
    }, default=str)


def _action_cancel_run(kwargs: dict[str, Any]) -> str:
    from workflow.runs import (
        get_run as _get_run,
    )
    from workflow.runs import (
        request_cancel,
    )

    rid = kwargs.get("run_id", "").strip()
    if not rid:
        return json.dumps({"error": "run_id is required."})
    if _get_run(_base_path(), rid) is None:
        return json.dumps({"error": f"Run '{rid}' not found."})

    request_cancel(_base_path(), rid)
    note = (
        "Cancel noted. Sync v1 runs typically finish before the flag "
        "is checked; full cooperative cancel ships with Phase 3.5 "
        "(task #39)."
    )
    text = (
        "**Cancel requested.** The background executor will stop at the "
        f"next checkpoint.\n\n{note}"
    )
    return json.dumps({
        "text": text,
        "run_id": rid,
        "status": "cancel_requested",
        "note": note,
    })


def _action_get_run_output(kwargs: dict[str, Any]) -> str:
    from workflow.runs import get_run as _get_run

    rid = kwargs.get("run_id", "").strip()
    if not rid:
        return json.dumps({"error": "run_id is required."})

    record = _get_run(_base_path(), rid)
    if record is None:
        return json.dumps({"error": f"Run '{rid}' not found."})

    field = kwargs.get("field_name", "").strip()
    output = record.get("output") or {}
    if field:
        if field not in output:
            return json.dumps({
                "error": f"Output field '{field}' not present on run.",
                "available_fields": sorted(output.keys()),
            })
        value = output[field]
        # Scalar/single-artifact shape per tool_return_shapes.md —
        # tight one-liner + full value for scripts.
        preview = str(value)
        if len(preview) > 240:
            preview = preview[:240].rstrip() + "…"
        branch_label = _branch_name_for_run(record)
        text = (
            f"**{field}** (workflow '{branch_label}'):\n\n{preview}"
        )
        return json.dumps({
            "text": text,
            "run_id": rid,
            "field_name": field,
            "value": value,
        }, default=str)
    # Whole-output read — catalog of fields.
    branch_label = _branch_name_for_run(record)
    lines = [
        f"**Output from workflow '{branch_label}'** "
        f"(status: {record.get('status')})"
    ]
    if output:
        lines.append("")
        for key in sorted(output.keys()):
            val_preview = str(output[key])
            if len(val_preview) > 120:
                val_preview = val_preview[:120].rstrip() + "…"
            lines.append(f"- `{key}`: {val_preview}")
    else:
        lines.append("\n_(no output produced)_")
    return json.dumps({
        "text": "\n".join(lines),
        "run_id": rid,
        "status": record.get("status"),
        "output": output,
    }, default=str)


def _action_resume_run(kwargs: dict[str, Any]) -> str:
    """Resume an INTERRUPTED run from its SqliteSaver checkpoint.

    Auth re-check is performed at resume time — the caller must still own
    the run. If the run is already in RESUMED status, the call is
    idempotent and returns the existing run_id.
    """
    from workflow.branches import BranchDefinition
    from workflow.daemon_server import get_branch_definition
    from workflow.runs import ResumeError, resume_run

    _ensure_runs_recovery()

    run_id = kwargs.get("run_id", "").strip()
    if not run_id:
        return json.dumps({"error": "run_id is required."})

    actor = _current_actor()

    def _branch_lookup(branch_def_id: str, _version: int) -> BranchDefinition | None:
        try:
            source_dict = get_branch_definition(_base_path(), branch_def_id=branch_def_id)
            return BranchDefinition.from_dict(source_dict)
        except Exception:
            return None

    provider_call: Any = None
    try:
        from domains.fantasy_author.phases._provider_stub import (
            call_provider as provider_call,
        )
    except ImportError:
        provider_call = None

    try:
        outcome = resume_run(
            _base_path(),
            run_id=run_id,
            actor=actor,
            branch_lookup=_branch_lookup,
            provider_call=provider_call,
        )
    except ResumeError as exc:
        return json.dumps({
            "error": str(exc), "reason": exc.reason, "current_status": exc.current_status,
        })
    except Exception as exc:
        logger.exception("resume_run failed for %s", run_id)
        return json.dumps({"error": f"Resume failed: {exc}"})

    text = "\n".join([
        f"**Run {outcome.status}.** Resume handed to the background executor.",
        "",
        f"Error: {outcome.error}" if outcome.error else "",
        "Use `get_run` to check progress or `cancel_run` to stop.",
    ]).strip()

    return json.dumps({
        "text": text,
        "run_id": outcome.run_id,
        "status": outcome.status,
        "output": outcome.output,
        "error": outcome.error,
    })


def _action_estimate_run_cost(kwargs: dict[str, Any]) -> str:
    """Estimate cost and time for running a branch before dispatch.

    Returns a structured estimate so the chatbot can narrate cost/time
    framing before the user commits to a paid-market bid or free-queue
    wait. Read-only — no provider calls, no writes.

    Confidence levels:
    - "low": branch has never been run (estimate from node declarations).
    - "medium": 1-4 prior completed runs exist (use average).
    - "high": 5+ prior completed runs exist (use median of sample).
    """
    from workflow.branches import BranchDefinition
    from workflow.daemon_server import get_branch_definition
    from workflow.runs import RUN_STATUS_COMPLETED, list_runs

    bid = kwargs.get("branch_def_id", "").strip()
    if not bid:
        return json.dumps({"error": "branch_def_id is required."})

    try:
        source_dict = get_branch_definition(_base_path(), branch_def_id=bid)
    except Exception:
        return json.dumps({"error": f"Branch '{bid}' not found."})

    branch = BranchDefinition.from_dict(source_dict)
    node_count = len(branch.node_defs)

    # Per-node cost heuristic: roughly 0.01 credits per node for a
    # prompt-template node (LLM call), 0.001 for a code node (exec only).
    # These are illustrative baseline defaults — real pricing depends on
    # the provider bid the user sets at dispatch time (paid_market model).
    credits_per_node: dict[str, float] = {}
    for n in branch.node_defs:
        if n.prompt_template:
            credits_per_node[n.node_id] = 0.01
        else:
            credits_per_node[n.node_id] = 0.001

    estimated_paid_market_credits = round(sum(credits_per_node.values()), 4)

    # Confidence: check prior completed run history.
    try:
        prior_runs = list_runs(
            _base_path(), branch_def_id=bid, status=RUN_STATUS_COMPLETED,
        )
    except Exception:
        prior_runs = []

    run_count = len(prior_runs)
    if run_count == 0:
        confidence = "low"
    elif run_count < 5:
        confidence = "medium"
    else:
        confidence = "high"

    # Free-queue ETA: best-effort from dispatcher queue depth.
    free_queue_eta_hours: float | None = None
    free_queue_caveat: str | None = None
    try:
        from workflow.dispatcher import get_queue_depth
        queue_depth = get_queue_depth()
        # Rough heuristic: ~10 min per queued run ahead of this one.
        free_queue_eta_hours = round((queue_depth * 10) / 60, 2)
    except Exception:
        free_queue_caveat = (
            "Dispatcher queue depth unavailable — free_queue_eta_hours is null. "
            "Dispatcher may be disabled or not yet initialised."
        )

    # Build a chatbot-quotable basis string.
    llm_nodes = sum(1 for n in branch.node_defs if n.prompt_template)
    code_nodes = node_count - llm_nodes
    basis_parts = [
        f"{node_count} node(s) total: {llm_nodes} LLM node(s) at ~0.01 credits each, "
        f"{code_nodes} code/other node(s) at ~0.001 credits each.",
        f"Confidence: {confidence} ({run_count} prior completed run(s)).",
    ]
    if free_queue_caveat:
        basis_parts.append(free_queue_caveat)
    else:
        basis_parts.append(
            f"Free-queue ETA based on ~{free_queue_eta_hours}h "
            "(estimated from current queue depth)."
        )
    basis = " ".join(basis_parts)

    return json.dumps({
        "branch_def_id": bid,
        "node_count": node_count,
        "estimated_paid_market_credits": estimated_paid_market_credits,
        "free_queue_eta_hours": free_queue_eta_hours,
        "confidence": confidence,
        "basis": basis,
        "prior_run_count": run_count,
    })


def _action_project_memory_get(kwargs: dict[str, Any]) -> str:
    from workflow.memory.project import project_memory_get

    project_id = kwargs.get("project_id", "").strip()
    key = kwargs.get("key", "").strip()
    if not project_id or not key:
        return json.dumps({"error": "project_id and key are required."})
    row = project_memory_get(_base_path(), project_id=project_id, key=key)
    if row is None:
        return json.dumps({"found": False, "project_id": project_id, "key": key})
    return json.dumps({"found": True, **row})


def _action_project_memory_set(kwargs: dict[str, Any]) -> str:
    from workflow.memory.project import project_memory_set

    project_id = kwargs.get("project_id", "").strip()
    key = kwargs.get("key", "").strip()
    raw_value = kwargs.get("value", "")
    if not project_id or not key:
        return json.dumps({"error": "project_id and key are required."})
    try:
        value = json.loads(raw_value) if isinstance(raw_value, str) else raw_value
    except (json.JSONDecodeError, TypeError):
        value = raw_value
    expected_version_raw = kwargs.get("expected_version")
    expected_version: int | None = None
    if expected_version_raw is not None:
        try:
            expected_version = int(expected_version_raw)
        except (TypeError, ValueError):
            return json.dumps({"error": "expected_version must be an integer."})
    actor = _current_actor()
    result = project_memory_set(
        _base_path(),
        project_id=project_id,
        key=key,
        value=value,
        actor=actor,
        expected_version=expected_version,
    )
    return json.dumps(result)


def _action_project_memory_list(kwargs: dict[str, Any]) -> str:
    from workflow.memory.project import project_memory_list

    project_id = kwargs.get("project_id", "").strip()
    if not project_id:
        return json.dumps({"error": "project_id is required."})
    key_prefix = kwargs.get("key_prefix", "") or ""
    try:
        limit = int(kwargs.get("limit", 100))
    except (TypeError, ValueError):
        limit = 100
    rows = project_memory_list(
        _base_path(), project_id=project_id, key_prefix=key_prefix, limit=limit
    )
    return json.dumps({"project_id": project_id, "entries": rows, "count": len(rows)})


_PROJECT_MEMORY_ACTIONS: dict[str, Any] = {
    "project_memory_get": _action_project_memory_get,
    "project_memory_set": _action_project_memory_set,
    "project_memory_list": _action_project_memory_list,
}

_PROJECT_MEMORY_WRITE_ACTIONS: frozenset[str] = frozenset({"project_memory_set"})


def _action_query_runs(kwargs: dict[str, Any]) -> str:
    from workflow.runs import _VALID_AGGREGATES, query_runs

    bid = kwargs.get("branch_def_id", "").strip()
    raw_filters = kwargs.get("filters_json", "") or kwargs.get("filters", "") or ""
    raw_select = kwargs.get("select", "") or ""
    raw_aggregate = kwargs.get("aggregate_json", "") or kwargs.get("aggregate", "") or ""
    raw_limit = kwargs.get("limit", _DEFAULT_QUERY_LIMIT) or _DEFAULT_QUERY_LIMIT

    filters: dict[str, Any] = {}
    if raw_filters:
        try:
            filters = json.loads(raw_filters) if isinstance(raw_filters, str) else raw_filters
        except (json.JSONDecodeError, TypeError):
            return json.dumps({"error": "filters_json is not valid JSON."})

    select: list[str] = []
    if raw_select:
        if isinstance(raw_select, str):
            select = [s.strip() for s in raw_select.split(",") if s.strip()]
        elif isinstance(raw_select, list):
            select = raw_select

    aggregate: dict[str, Any] | None = None
    if raw_aggregate:
        try:
            agg_parsed = (
                json.loads(raw_aggregate) if isinstance(raw_aggregate, str)
                else raw_aggregate
            )
            if isinstance(agg_parsed, dict):
                agg_fn = agg_parsed.get("fn", agg_parsed.get("op", "count"))
                if agg_fn not in _VALID_AGGREGATES:
                    return json.dumps({
                        "error": f"aggregate.fn must be one of: {sorted(_VALID_AGGREGATES)}",
                    })
                aggregate = agg_parsed
        except (json.JSONDecodeError, TypeError):
            return json.dumps({"error": "aggregate_json is not valid JSON."})

    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        limit = _DEFAULT_QUERY_LIMIT

    result = query_runs(
        _base_path(),
        branch_def_id=bid,
        filters=filters,
        select=select,
        aggregate=aggregate,
        limit=limit,
    )
    return json.dumps(result, default=str)


_DEFAULT_QUERY_LIMIT = 100


def _action_run_routing_evidence(kwargs: dict[str, Any]) -> str:
    """Return recent run records shaped for provider/routing self-audit.

    Answers "which LLM answered the last call?" and "why did the run fail?"
    Each record includes derived latency_ms, failure_class, suggested_action,
    and a caveat noting that provider_used / token_count fields are not yet
    in the runs schema (pending schema migration).
    """
    from workflow.runs import list_recent_runs

    bid = (kwargs.get("branch_def_id") or "").strip()
    raw_limit = kwargs.get("limit", 10)
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        limit = 10

    records = list_recent_runs(_base_path(), branch_def_id=bid, limit=limit)
    return json.dumps({
        "runs": records,
        "count": len(records),
        "caveat": records[0]["caveat"] if records else (
            "No runs found. Execute a branch first, then call get_routing_evidence."
        ),
    }, default=str)


# ───────────────────────────────────────────────────────────────────────────
# get_memory_scope_status — self-auditing primitive §4.1
# ───────────────────────────────────────────────────────────────────────────


def _action_get_memory_scope_status(kwargs: dict[str, Any]) -> str:
    """Snapshot of memory-scope enforcement state for chatbot self-audit.

    Self-auditing-tools pattern (§4.1). Answers: "Is tiered scope active?
    Which tiers are being enforced? Have any scope mismatches been logged?"
    Returns concrete evidence the chatbot can narrate; does not infer.

    Shape (schema_version=1):
        {
          "schema_version": int,
          "tiered_scope_enabled": bool,
          "flag_state": str,
          "active_enforcement_tiers": [str, ...],
          "all_scope_tiers": [str, ...],
          "retrieval_stats_by_tier": {},
          "recent_scope_mismatch_warnings": [str, ...],
          "caveats": [str, ...],
          "actionable_next_steps": [str, ...],
        }
    """
    import os as _os

    from workflow.retrieval.router import tiered_scope_enabled

    flag_on = tiered_scope_enabled()
    flag_raw = _os.environ.get("WORKFLOW_TIERED_SCOPE", "off")
    all_tiers = ["universe_id", "goal_id", "branch_id", "user_id"]
    active_tiers = all_tiers if flag_on else ["universe_id"]

    universe_id = (kwargs.get("universe_id") or "").strip() or _default_universe()
    udir = _universe_dir(universe_id)
    log_content = _read_text(udir / "activity.log")
    mismatch_lines: list[str] = []
    if log_content:
        for line in log_content.strip().splitlines():
            if "retrieval.scope_mismatch" in line:
                mismatch_lines.append(line.strip())
    recent_mismatches = mismatch_lines[-10:]

    caveats: list[str] = [
        "retrieval_stats_by_tier is not yet instrumented (Stage 2b.3);"
        " per-tier drop counts will appear in Stage 2c.",
    ]
    if not flag_on:
        caveats.append(
            "WORKFLOW_TIERED_SCOPE=off: only universe_id is enforced."
            " goal_id / branch_id / user_id isolation is NOT active."
        )
    if recent_mismatches:
        caveats.append(
            f"{len(recent_mismatches)} recent scope-mismatch warning(s) in"
            " activity.log — inspect recent_scope_mismatch_warnings."
        )

    next_steps: list[str] = []
    if not flag_on:
        next_steps.append(
            "Set WORKFLOW_TIERED_SCOPE=on to enable full four-tier"
            " isolation (universe/goal/branch/user)."
        )
    next_steps.append(
        "Check activity.log for 'retrieval.scope_mismatch' to diagnose"
        " any cross-universe content bleed."
    )

    return json.dumps({
        "schema_version": 1,
        "tiered_scope_enabled": flag_on,
        "flag_state": flag_raw,
        "active_enforcement_tiers": active_tiers,
        "all_scope_tiers": all_tiers,
        "retrieval_stats_by_tier": {},
        "recent_scope_mismatch_warnings": recent_mismatches,
        "caveats": caveats,
        "actionable_next_steps": next_steps,
        "universe_id": universe_id,
    })


# ───────────────────────────────────────────────────────────────────────────
# dry_inspect_node / dry_inspect_patch — zero-side-effect structural preview
# ───────────────────────────────────────────────────────────────────────────


def _load_branch_for_inspect(
    branch_def_id: str,
    branch_spec_json: str,
) -> tuple[Any, str | None]:
    """Return (BranchDefinition, error_str). Exactly one of the two inputs."""
    from workflow.branches import BranchDefinition as _BD

    if branch_spec_json:
        try:
            spec = json.loads(branch_spec_json)
        except json.JSONDecodeError as exc:
            return None, f"branch_spec_json is not valid JSON: {exc}"
        try:
            return _BD.from_dict(spec), None
        except Exception as exc:  # noqa: BLE001
            return None, f"branch_spec_json could not be parsed: {exc}"

    if not branch_def_id:
        return None, "branch_def_id or branch_spec_json is required."

    try:
        from workflow.daemon_server import get_branch_definition
        source = get_branch_definition(_base_path(), branch_def_id=branch_def_id)
        return _BD.from_dict(source), None
    except KeyError:
        return None, f"Branch '{branch_def_id}' not found."


def _action_dry_inspect_node(kwargs: dict[str, Any]) -> str:
    from workflow.graph_compiler import inspect_node_dry

    bid = (kwargs.get("branch_def_id") or "").strip()
    nid = (kwargs.get("node_id") or "").strip()
    spec_json = (kwargs.get("branch_spec_json") or kwargs.get("spec_json") or "").strip()

    branch, err = _load_branch_for_inspect(bid, spec_json)
    if err:
        return json.dumps({"error": err})

    result = inspect_node_dry(branch, node_id=nid)
    return json.dumps(result, default=str)


def _apply_patch_ops(
    branch: Any,
    changes_json: str,
) -> tuple[Any, str | None]:
    """Apply patch_branch-style ops to a branch copy without persisting.

    Returns (patched_branch, error_str).  Uses the same op executor as
    the real patch_branch action but skips the DB write.
    """
    try:
        ops = json.loads(changes_json) if isinstance(changes_json, str) else changes_json
    except json.JSONDecodeError as exc:
        return None, f"changes_json is not valid JSON: {exc}"

    if not isinstance(ops, list):
        return None, "changes_json must be a JSON array of ops."

    from workflow.branches import BranchDefinition as _BD

    branch_dict = branch.to_dict()
    for i, op in enumerate(ops):
        if not isinstance(op, dict):
            return None, f"Op #{i} is not an object."
        op_name = op.get("op", "")
        if op_name == "add_node":
            from workflow.branches import NodeDefinition as _ND
            try:
                nd = _ND.from_dict(op)
                branch_dict.setdefault("node_defs", []).append(nd.to_dict())
            except Exception as exc:  # noqa: BLE001
                return None, f"Op #{i} add_node failed: {exc}"
        elif op_name == "remove_node":
            nid = op.get("node_id", "")
            branch_dict["node_defs"] = [
                n for n in branch_dict.get("node_defs", [])
                if n.get("node_id") != nid
            ]
        elif op_name == "update_node":
            nid = op.get("node_id", "")
            for nd in branch_dict.get("node_defs", []):
                if nd.get("node_id") == nid:
                    nd.update({k: v for k, v in op.items() if k not in ("op",)})
        elif op_name == "add_state_field":
            branch_dict.setdefault("state_schema", []).append({
                "name": op.get("field_name", ""),
                "type": op.get("field_type", "str"),
                "reducer": op.get("reducer", ""),
                "default": op.get("field_default", ""),
            })
        elif op_name == "remove_state_field":
            fn = op.get("field_name", "")
            branch_dict["state_schema"] = [
                f for f in branch_dict.get("state_schema", [])
                if f.get("name") != fn
            ]
        # Other ops (edges, metadata) are no-ops for structural inspection

    try:
        return _BD.from_dict(branch_dict), None
    except Exception as exc:  # noqa: BLE001
        return None, f"Patched branch could not be reconstructed: {exc}"


def _action_dry_inspect_patch(kwargs: dict[str, Any]) -> str:
    from workflow.graph_compiler import inspect_node_dry

    bid = (kwargs.get("branch_def_id") or "").strip()
    nid = (kwargs.get("node_id") or "").strip()
    changes_json = (kwargs.get("changes_json") or "").strip()
    spec_json = (kwargs.get("branch_spec_json") or kwargs.get("spec_json") or "").strip()

    if not changes_json:
        return json.dumps({"error": "changes_json is required for dry_inspect_patch."})

    branch, err = _load_branch_for_inspect(bid, spec_json)
    if err:
        return json.dumps({"error": err})

    patched, err2 = _apply_patch_ops(branch, changes_json)
    if err2:
        return json.dumps({"error": err2})

    result = inspect_node_dry(patched, node_id=nid)
    return json.dumps(result, default=str)


_INSPECT_DRY_ACTIONS: dict[str, Any] = {
    "dry_inspect_node": _action_dry_inspect_node,
    "dry_inspect_patch": _action_dry_inspect_patch,
}


# ── Escrow MCP handlers ────────────────────────────────────────────────────────

def _action_escrow_lock(kwargs: dict[str, Any]) -> str:
    """Lock escrow for a node request. Requires WORKFLOW_PAID_MARKET=on."""
    from workflow.payments.actions import action_escrow_lock
    from workflow.producers.node_bid import paid_market_enabled
    from workflow.storage import _connect

    if not paid_market_enabled():
        return json.dumps({
            "status": "not_available",
            "error": "Escrow actions require WORKFLOW_PAID_MARKET=on.",
        })

    node_id = (kwargs.get("node_id") or "").strip()
    claimer = os.environ.get("UNIVERSE_SERVER_USER", "anonymous")
    currency = (kwargs.get("currency") or "MicroToken").strip()
    raw_amount = kwargs.get("amount", 0)
    try:
        amount = int(raw_amount)
    except (TypeError, ValueError):
        return json.dumps({
            "status": "rejected",
            "error": f"amount must be an integer, got {raw_amount!r}.",
        })

    with _connect(_base_path()) as conn:
        result = action_escrow_lock(
            conn,
            node_id=node_id,
            amount=amount,
            claimer=claimer,
            currency=currency,
        )
    return json.dumps(result)


def _action_escrow_release(kwargs: dict[str, Any]) -> str:
    """Release locked escrow to a recipient on completion verdict."""
    from workflow.payments.actions import action_escrow_release
    from workflow.producers.node_bid import paid_market_enabled
    from workflow.storage import _connect

    if not paid_market_enabled():
        return json.dumps({
            "status": "not_available",
            "error": "Escrow actions require WORKFLOW_PAID_MARKET=on.",
        })

    lock_id = (kwargs.get("lock_id") or "").strip()
    recipient_id = (kwargs.get("recipient_id") or "").strip()
    evidence = (kwargs.get("evidence") or "").strip()

    if not recipient_id:
        return json.dumps({
            "status": "rejected",
            "error": "recipient_id is required for escrow_release.",
        })

    with _connect(_base_path()) as conn:
        result = action_escrow_release(
            conn,
            lock_id=lock_id,
            recipient_id=recipient_id,
            evidence=evidence,
        )
    return json.dumps(result)


def _action_escrow_refund(kwargs: dict[str, Any]) -> str:
    """Refund locked escrow to staker on abandonment or rejection."""
    from workflow.payments.actions import action_escrow_refund
    from workflow.producers.node_bid import paid_market_enabled
    from workflow.storage import _connect

    if not paid_market_enabled():
        return json.dumps({
            "status": "not_available",
            "error": "Escrow actions require WORKFLOW_PAID_MARKET=on.",
        })

    lock_id = (kwargs.get("lock_id") or "").strip()
    reason = (kwargs.get("reason") or "").strip()

    with _connect(_base_path()) as conn:
        result = action_escrow_refund(conn, lock_id=lock_id, reason=reason)
    return json.dumps(result)


def _action_escrow_inspect(kwargs: dict[str, Any]) -> str:
    """Read-only inspection of escrow lock(s). No paid-market gate."""
    from workflow.payments.actions import action_escrow_inspect
    from workflow.storage import _connect

    node_id = (kwargs.get("node_id") or "").strip()
    lock_id = (kwargs.get("lock_id") or "").strip()

    with _connect(_base_path()) as conn:
        result = action_escrow_inspect(conn, node_id=node_id, lock_id=lock_id)
    return json.dumps(result)


_ESCROW_ACTIONS: dict[str, Any] = {
    "escrow_lock": _action_escrow_lock,
    "escrow_release": _action_escrow_release,
    "escrow_refund": _action_escrow_refund,
    "escrow_inspect": _action_escrow_inspect,
}


def _action_run_branch_version(kwargs: dict[str, Any]) -> str:
    """Execute a published branch_version snapshot.

    Phase A item 6 (Task #65b). Sibling to ``run_branch``; resolves a
    ``branch_version_id`` via ``branch_versions``, reconstructs a
    ``BranchDefinition`` from the immutable snapshot, and hands off to
    the same async executor pool. Records the ``branch_version_id`` on
    the new ``runs.branch_version_id`` column for attribution.
    """
    from workflow.runs import (
        SnapshotSchemaDrift,
        execute_branch_version_async,
    )

    _ensure_runs_recovery()

    bvid = (kwargs.get("branch_version_id") or "").strip()
    if not bvid:
        return json.dumps({"error": "branch_version_id is required."})

    inputs_raw = kwargs.get("inputs_json", "").strip()
    inputs: dict[str, Any] = {}
    if inputs_raw:
        try:
            parsed = json.loads(inputs_raw)
            if not isinstance(parsed, dict):
                return json.dumps({
                    "error": "inputs_json must decode to a JSON object.",
                })
            inputs = parsed
        except json.JSONDecodeError as exc:
            return json.dumps({
                "error": f"inputs_json is not valid JSON: {exc}",
            })

    # Real provider — lazy import so test envs without providers work.
    provider_call: Any = None
    try:
        from domains.fantasy_author.phases._provider_stub import (
            call_provider as provider_call,
        )
    except ImportError:
        provider_call = None

    # Parse + validate recursion_limit_override (10-1000) — same shape as run_branch.
    _rl_raw = kwargs.get("recursion_limit_override", "")
    recursion_limit_override: int | None = None
    if _rl_raw:
        try:
            _rl_val = int(_rl_raw)
        except (TypeError, ValueError):
            return json.dumps({"error": "recursion_limit_override must be an integer."})
        if not 10 <= _rl_val <= 1000:
            return json.dumps({
                "error": (
                    f"recursion_limit_override {_rl_val} out of range. "
                    "Valid range: 10-1000."
                ),
            })
        recursion_limit_override = _rl_val

    try:
        outcome = execute_branch_version_async(
            _base_path(),
            branch_version_id=bvid,
            inputs=inputs,
            run_name=kwargs.get("run_name", ""),
            actor=_current_actor(),
            provider_call=provider_call,
            recursion_limit_override=recursion_limit_override,
        )
    except KeyError as exc:
        return json.dumps({"error": str(exc).strip("'\"")})
    except SnapshotSchemaDrift as exc:
        return json.dumps({
            "error": str(exc),
            "failure_class": SnapshotSchemaDrift.failure_class,
            "suggested_action": SnapshotSchemaDrift.suggested_action,
            "actionable_by": SnapshotSchemaDrift.actionable_by,
        })
    except Exception as exc:
        logger.exception("run_branch_version failed for %s", bvid)
        return json.dumps(_classify_run_error(exc, bvid))

    # Write-ack mirroring _action_run_branch's response shape.
    error_annotation = _classify_run_outcome_error(outcome.error) if outcome.error else None
    error_lines: list[str] = []
    if outcome.error:
        error_lines.append(f"Error: {outcome.error}")
    if error_annotation:
        error_lines.append(f"Suggested action: {error_annotation[1]}")
    text = "\n".join([
        f"**Run {outcome.status}.** Version-based workflow handed to the "
        "background executor.",
        "",
        *error_lines,
        "Use `get_run` to read a snapshot, `stream_run` to poll for "
        "progress, or `cancel_run` to stop. Each takes a `run_id` "
        "from the structured content of this response.",
    ]).strip()

    result: dict[str, Any] = {
        "text": text,
        "run_id": outcome.run_id,
        "status": outcome.status,
        "output": outcome.output,
        "error": outcome.error,
        "branch_version_id": bvid,
    }
    if error_annotation:
        result["failure_class"] = error_annotation[0]
        result["suggested_action"] = error_annotation[1]
        result["actionable_by"] = _actionable_by(error_annotation[0])
    return json.dumps(result)


def _action_rollback_merge(kwargs: dict[str, Any]) -> str:
    """Surgical-rollback (Task #22 Phase B). Host-only authority per
    design §5 + Hard-Rule emergency-override pattern.

    Required kwargs: ``branch_version_id`` (seed), ``reason``.
    Optional kwargs: ``severity`` (P0/P1/P2; default P1).

    Computes the dependency closure from the seed, atomically flips each
    closure version to ``status='rolled_back'`` + emits one
    ``caused_regression`` event per version (single runs-DB transaction),
    then re-points any goal canonical pointing into the closure to the
    nearest non-rolled-back ancestor (separate author_server-DB step
    per cross-DB refinement; see ``workflow/rollback.py`` module
    docstring).
    """
    from workflow.rollback import rollback_merge_orchestrator

    bvid = (kwargs.get("branch_version_id") or "").strip()
    reason = (kwargs.get("reason") or "").strip()
    severity = (kwargs.get("severity") or "P1").strip().upper()
    if not bvid:
        return json.dumps({"error": "branch_version_id is required."})
    if not reason:
        return json.dumps({"error": "reason is required."})

    actor = _current_actor()
    host_actor = os.environ.get("UNIVERSE_SERVER_HOST_USER", "host")
    if actor != host_actor:
        return json.dumps({
            "error": (
                "host-only authority — only the host actor "
                f"({host_actor!r}) may roll back versions. "
                f"Request actor was {actor!r}."
            ),
        })

    result = rollback_merge_orchestrator(
        _base_path(),
        bvid,
        reason=reason,
        set_by=actor,
        severity=severity,
    )
    if result.get("status") == "rejected":
        return json.dumps(result, default=str)

    closure = result.get("closure", [])
    repoint = result.get("repoint", {})
    text_lines = [
        f"**Rolled back** {len(closure)} branch_version(s) seeded from "
        f"`{bvid}` (severity {severity}).",
        f"Reason: {reason}",
    ]
    repointed_count = repoint.get("repointed_count", 0)
    if repointed_count:
        text_lines.append(
            f"Re-pointed canonical bindings on {repointed_count} Goal(s) "
            "to nearest non-rolled-back ancestor."
        )
    return json.dumps({
        "text": "\n".join(text_lines),
        **result,
    }, default=str)


def _action_get_rollback_history(kwargs: dict[str, Any]) -> str:
    """Read-only rollback history surface. No authority restriction.

    Optional kwargs: ``since_days`` (default 7).
    """
    from workflow.rollback import get_rollback_history

    try:
        since_days = int(kwargs.get("since_days", 7) or 7)
    except (TypeError, ValueError):
        since_days = 7
    since_days = max(1, min(since_days, 365))

    rollbacks = get_rollback_history(_base_path(), since_days=since_days)
    if rollbacks:
        text_lines = [
            f"**{len(rollbacks)} rollback(s)** in the past {since_days} day(s):",
            "",
        ]
        for r in rollbacks[:20]:
            text_lines.append(
                f"- `{r['branch_version_id']}` · "
                f"{r['rolled_back_at']} · by `{r['rolled_back_by']}` · "
                f"{r['rolled_back_reason']}"
            )
        if len(rollbacks) > 20:
            text_lines.append(f"_… and {len(rollbacks) - 20} more._")
        text = "\n".join(text_lines)
    else:
        text = f"_No rollbacks in the past {since_days} day(s)._"
    return json.dumps({
        "text": text,
        "rollbacks": rollbacks,
        "count": len(rollbacks),
        "since_days": since_days,
    }, default=str)


_RUN_ACTIONS: dict[str, Any] = {
    "run_branch": _action_run_branch,
    "run_branch_version": _action_run_branch_version,
    "get_run": _action_get_run,
    "list_runs": _action_list_runs,
    "stream_run": _action_stream_run,
    "wait_for_run": _action_wait_for_run,
    "cancel_run": _action_cancel_run,
    "get_run_output": _action_get_run_output,
    "resume_run": _action_resume_run,
    "estimate_run_cost": _action_estimate_run_cost,
    "query_runs": _action_query_runs,
    "get_routing_evidence": _action_run_routing_evidence,
    "get_memory_scope_status": _action_get_memory_scope_status,
    "rollback_merge": _action_rollback_merge,
    "get_rollback_history": _action_get_rollback_history,
}

_RUN_WRITE_ACTIONS: frozenset[str] = frozenset(
    {"run_branch", "run_branch_version", "cancel_run", "resume_run",
     "rollback_merge"}
)


def _dispatch_run_action(
    action: str,
    handler: Any,
    kwargs: dict[str, Any],
) -> str:
    """Dispatch a Phase 3 run action, ledger the write actions.

    run_branch and cancel_run both mutate durable state so they land in
    the global ledger with the run_id as the target.
    """
    result_str = handler(kwargs)
    if action not in _RUN_WRITE_ACTIONS:
        return result_str

    try:
        result = json.loads(result_str)
    except (json.JSONDecodeError, TypeError):
        return result_str
    if not isinstance(result, dict):
        return result_str
    # Only skip ledger on actual error responses (non-empty 'error' value).
    # _action_run_branch always includes an empty 'error' field on success.
    if result.get("error"):
        return result_str

    try:
        target = result.get("run_id", "") or kwargs.get("run_id", "")
        summary_bits = [action]
        if kwargs.get("branch_def_id"):
            summary_bits.append(f"branch={kwargs['branch_def_id']}")
        if result.get("status"):
            summary_bits.append(f"status={result['status']}")
        _append_global_ledger(
            action,
            target=str(target),
            summary=_truncate(" ".join(summary_bits)),
            payload=None,
        )
    except Exception as exc:
        logger.warning("Ledger write failed for run action %s: %s", action, exc)
    return result_str


# ───────────────────────────────────────────────────────────────────────────
# Branch versioning — publish_version + get_branch_version + list_branch_versions
# ───────────────────────────────────────────────────────────────────────────


def _action_publish_version(kwargs: dict[str, Any]) -> str:
    from workflow.branch_versions import publish_branch_version
    from workflow.daemon_server import get_branch_definition

    bid = (kwargs.get("branch_def_id") or "").strip()
    notes = (kwargs.get("notes") or "").strip()
    parent_version_id = (kwargs.get("parent_version_id") or "").strip() or None
    publisher = (kwargs.get("publisher") or "anonymous").strip()

    if not bid:
        return json.dumps({"error": "branch_def_id is required."})

    base_path = _base_path()
    try:
        raw = get_branch_definition(base_path, branch_def_id=bid)
    except (KeyError, FileNotFoundError):
        return json.dumps({"error": f"Branch '{bid}' not found."})
    except Exception as exc:
        return json.dumps({"error": f"Could not load branch: {exc}"})

    try:
        version = publish_branch_version(
            base_path,
            raw,
            publisher=publisher,
            notes=notes,
            parent_version_id=parent_version_id,
        )
    except (KeyError, ValueError) as exc:
        return json.dumps({"error": str(exc)})

    return json.dumps({
        "branch_version_id": version.branch_version_id,
        "content_hash": version.content_hash,
        "published_at": version.published_at,
        "publisher": version.publisher,
        "parent_version_id": version.parent_version_id,
    })


def _action_get_branch_version(kwargs: dict[str, Any]) -> str:
    from workflow.branch_versions import get_branch_version

    version_id = (kwargs.get("branch_version_id") or "").strip()
    if not version_id:
        return json.dumps({"error": "branch_version_id is required."})

    base_path = _base_path()
    version = get_branch_version(base_path, version_id)
    if version is None:
        return json.dumps({"error": f"Version '{version_id}' not found."})
    return json.dumps(version.to_dict())


def _action_list_branch_versions(kwargs: dict[str, Any]) -> str:
    from workflow.branch_versions import list_branch_versions

    bid = (kwargs.get("branch_def_id") or "").strip()
    if not bid:
        return json.dumps({"error": "branch_def_id is required."})
    limit = int(kwargs.get("limit", 50) or 50)

    base_path = _base_path()
    versions = list_branch_versions(base_path, bid, limit=limit)
    return json.dumps({
        "branch_def_id": bid,
        "versions": [v.to_dict() for v in versions],
        "count": len(versions),
    })


_BRANCH_VERSION_ACTIONS: dict[str, Any] = {
    "publish_version": _action_publish_version,
    "get_branch_version": _action_get_branch_version,
    "list_branch_versions": _action_list_branch_versions,
}


# ───────────────────────────────────────────────────────────────────────────
# Teammate messaging
# ───────────────────────────────────────────────────────────────────────────


def _action_messaging_send(kwargs: dict[str, Any]) -> str:
    from workflow.runs import post_teammate_message

    from_run_id = kwargs.get("from_run_id", "").strip()
    to_node_id = kwargs.get("to_node_id", "").strip()
    message_type = kwargs.get("message_type", "").strip()
    body_raw = kwargs.get("body_json", "") or kwargs.get("body", "") or "{}"
    reply_to_id = kwargs.get("reply_to_message_id") or None

    if isinstance(body_raw, dict):
        body = body_raw
    else:
        try:
            body = json.loads(body_raw)
        except (json.JSONDecodeError, TypeError):
            return json.dumps({"error": "body_json is not valid JSON."})

    base_path = _base_path()
    try:
        record = post_teammate_message(
            base_path,
            from_run_id=from_run_id,
            to_node_id=to_node_id,
            message_type=message_type,
            body=body,
            reply_to_id=reply_to_id,
        )
    except (KeyError, ValueError, PermissionError) as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps({"message_id": record["message_id"], "delivered_at": record["sent_at"]})


def _action_messaging_receive(kwargs: dict[str, Any]) -> str:
    from workflow.runs import read_teammate_messages

    node_id = kwargs.get("node_id", "").strip()
    since = kwargs.get("since") or None
    raw_types = kwargs.get("message_types", "") or ""
    limit = int(kwargs.get("limit", 50) or 50)

    if isinstance(raw_types, list):
        message_types = [t.strip() for t in raw_types if t.strip()]
    elif isinstance(raw_types, str) and raw_types.strip():
        message_types = [t.strip() for t in raw_types.split(",") if t.strip()]
    else:
        message_types = None

    base_path = _base_path()
    try:
        messages = read_teammate_messages(
            base_path,
            node_id=node_id,
            since=since,
            message_types=message_types,
            limit=limit,
        )
    except Exception as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps({"messages": messages, "count": len(messages)})


def _action_messaging_ack(kwargs: dict[str, Any]) -> str:
    from workflow.runs import ack_teammate_message

    message_id = kwargs.get("message_id", "").strip()
    node_id = kwargs.get("node_id", "").strip()

    if not message_id:
        return json.dumps({"error": "message_id is required."})
    if not node_id:
        return json.dumps({"error": "node_id is required."})

    base_path = _base_path()
    try:
        result = ack_teammate_message(base_path, message_id=message_id, node_id=node_id)
    except KeyError as exc:
        return json.dumps({"error": str(exc)})
    except PermissionError as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps(result)


_MESSAGING_ACTIONS: dict[str, Any] = {
    "messaging_send": _action_messaging_send,
    "messaging_receive": _action_messaging_receive,
    "messaging_ack": _action_messaging_ack,
}


# ── Scheduler MCP actions ─────────────────────────────────────────────────


def _action_schedule_branch(kwargs: dict[str, Any]) -> str:
    from workflow.runs import initialize_runs_db
    from workflow.scheduler import CronParseError, register_schedule

    branch_def_id = (kwargs.get("branch_def_id") or "").strip()
    if not branch_def_id:
        return json.dumps({"error": "branch_def_id is required."})
    cron_expr = (kwargs.get("cron_expr") or "").strip()
    interval_seconds = kwargs.get("interval_seconds") or 0.0
    try:
        interval_seconds = float(interval_seconds)
    except (TypeError, ValueError):
        interval_seconds = 0.0
    if not cron_expr and interval_seconds <= 0:
        return json.dumps({"error": "one of cron_expr or interval_seconds must be provided."})
    owner_actor = (kwargs.get("owner_actor") or "").strip() or "anonymous"
    raw_inputs = kwargs.get("inputs_template_json") or "{}"
    try:
        inputs_template = json.loads(raw_inputs) if isinstance(raw_inputs, str) else raw_inputs
    except (json.JSONDecodeError, TypeError):
        inputs_template = {}
    skip_if_running = bool(kwargs.get("skip_if_running", False))
    base = _base_path()
    initialize_runs_db(base)
    try:
        schedule_id = register_schedule(
            base,
            branch_def_id=branch_def_id,
            owner_actor=owner_actor,
            cron_expr=cron_expr,
            interval_seconds=interval_seconds,
            inputs_template=inputs_template,
            skip_if_running=skip_if_running,
        )
    except CronParseError as exc:
        return json.dumps({"error": f"Invalid cron_expr: {exc}"})
    except ValueError as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps({
        "status": "scheduled",
        "schedule_id": schedule_id,
        "branch_def_id": branch_def_id,
        "cron_expr": cron_expr,
        "interval_seconds": interval_seconds,
    })


def _action_unschedule_branch(kwargs: dict[str, Any]) -> str:
    from workflow.scheduler import unregister_schedule

    schedule_id = (kwargs.get("schedule_id") or "").strip()
    if not schedule_id:
        return json.dumps({"error": "schedule_id is required."})
    owner_actor = (kwargs.get("owner_actor") or "").strip() or "anonymous"
    base = _base_path()
    try:
        removed = unregister_schedule(base, schedule_id, requesting_actor=owner_actor)
    except PermissionError as exc:
        return json.dumps({"error": str(exc)})
    if not removed:
        return json.dumps({"error": f"schedule_id '{schedule_id}' not found."})
    return json.dumps({"status": "unscheduled", "schedule_id": schedule_id})


def _action_list_schedules(kwargs: dict[str, Any]) -> str:
    from workflow.runs import initialize_runs_db
    from workflow.scheduler import list_schedules

    owner_actor = (kwargs.get("owner_actor") or "").strip()
    active_only = bool(kwargs.get("active_only", True))
    base = _base_path()
    initialize_runs_db(base)
    rows = list_schedules(base, owner_actor=owner_actor, active_only=active_only)
    return json.dumps({"schedules": rows, "count": len(rows)})


def _action_subscribe_branch(kwargs: dict[str, Any]) -> str:
    from workflow.runs import initialize_runs_db
    from workflow.scheduler import VALID_EVENT_TYPES, register_subscription

    branch_def_id = (kwargs.get("branch_def_id") or "").strip()
    if not branch_def_id:
        return json.dumps({"error": "branch_def_id is required."})
    event_type = (kwargs.get("event_type") or "").strip()
    if not event_type:
        return json.dumps({"error": "event_type is required."})
    if event_type not in VALID_EVENT_TYPES:
        return json.dumps({
            "error": f"Unknown event_type '{event_type}'.",
            "valid": sorted(VALID_EVENT_TYPES),
        })
    owner_actor = (kwargs.get("owner_actor") or "").strip() or "anonymous"
    base = _base_path()
    initialize_runs_db(base)
    try:
        sub_id = register_subscription(
            base,
            branch_def_id=branch_def_id,
            owner_actor=owner_actor,
            event_type=event_type,
        )
    except ValueError as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps({
        "status": "subscribed",
        "subscription_id": sub_id,
        "branch_def_id": branch_def_id,
        "event_type": event_type,
    })


def _action_unsubscribe_branch(kwargs: dict[str, Any]) -> str:
    from workflow.scheduler import unregister_subscription

    subscription_id = (kwargs.get("subscription_id") or "").strip()
    if not subscription_id:
        return json.dumps({"error": "subscription_id is required."})
    owner_actor = (kwargs.get("owner_actor") or "").strip() or "anonymous"
    base = _base_path()
    try:
        removed = unregister_subscription(base, subscription_id, requesting_actor=owner_actor)
    except PermissionError as exc:
        return json.dumps({"error": str(exc)})
    if not removed:
        return json.dumps({"error": f"subscription_id '{subscription_id}' not found."})
    return json.dumps({"status": "unsubscribed", "subscription_id": subscription_id})


def _action_pause_schedule(kwargs: dict[str, Any]) -> str:
    from workflow.scheduler import pause_schedule

    schedule_id = (kwargs.get("schedule_id") or "").strip()
    if not schedule_id:
        return json.dumps({"error": "schedule_id is required."})
    owner_actor = (kwargs.get("owner_actor") or "").strip() or "anonymous"
    base = _base_path()
    try:
        found = pause_schedule(base, schedule_id, requesting_actor=owner_actor)
    except PermissionError as exc:
        return json.dumps({"error": str(exc)})
    if not found:
        return json.dumps({"error": f"schedule_id '{schedule_id}' not found."})
    return json.dumps({"status": "paused", "schedule_id": schedule_id})


def _action_unpause_schedule(kwargs: dict[str, Any]) -> str:
    from workflow.scheduler import unpause_schedule

    schedule_id = (kwargs.get("schedule_id") or "").strip()
    if not schedule_id:
        return json.dumps({"error": "schedule_id is required."})
    owner_actor = (kwargs.get("owner_actor") or "").strip() or "anonymous"
    base = _base_path()
    try:
        found = unpause_schedule(base, schedule_id, requesting_actor=owner_actor)
    except PermissionError as exc:
        return json.dumps({"error": str(exc)})
    if not found:
        return json.dumps({"error": f"schedule_id '{schedule_id}' not found."})
    return json.dumps({"status": "unpaused", "schedule_id": schedule_id})


def _action_list_scheduler_subscriptions(kwargs: dict[str, Any]) -> str:
    from workflow.runs import initialize_runs_db
    from workflow.scheduler import list_scheduler_subscriptions

    owner_actor = (kwargs.get("owner_actor") or "").strip()
    event_type = (kwargs.get("event_type") or "").strip()
    active_only = bool(kwargs.get("active_only", True))
    base = _base_path()
    initialize_runs_db(base)
    rows = list_scheduler_subscriptions(
        base, owner_actor=owner_actor, event_type=event_type, active_only=active_only
    )
    return json.dumps({"subscriptions": rows, "count": len(rows)})


_SCHEDULER_ACTIONS: dict[str, Any] = {
    "schedule_branch": _action_schedule_branch,
    "unschedule_branch": _action_unschedule_branch,
    "list_schedules": _action_list_schedules,
    "subscribe_branch": _action_subscribe_branch,
    "unsubscribe_branch": _action_unsubscribe_branch,
    "pause_schedule": _action_pause_schedule,
    "unpause_schedule": _action_unpause_schedule,
    "list_scheduler_subscriptions": _action_list_scheduler_subscriptions,
}


# ── Outcome event MCP actions ─────────────────────────────────────────────


def _outcome_db_path(base_path: "Path") -> "Path":
    return base_path / ".runs.db"


def _outcome_connect(base_path: "Path") -> Any:
    import sqlite3 as _sqlite3

    from workflow.outcomes.schema import migrate_outcome_schema
    db = _outcome_db_path(base_path)
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = _sqlite3.connect(str(db), timeout=30.0)
    conn.row_factory = _sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    migrate_outcome_schema(conn)
    conn.commit()
    return conn


def _outcome_row_to_dict(row: Any) -> dict:
    return {
        "outcome_id": row["outcome_id"],
        "run_id": row["run_id"],
        "outcome_type": row["outcome_type"],
        "evidence_url": row["evidence_url"],
        "verified_at": row["verified_at"],
        "verified_by": row["verified_by"],
        "claim_run_id": row["claim_run_id"],
        "payload": json.loads(row["payload"] or "{}"),
        "recorded_at": row["recorded_at"],
        "note": row["note"] or "",
    }


def _action_record_outcome(kwargs: dict[str, Any]) -> str:
    import uuid as _uuid
    from datetime import datetime, timezone

    from workflow.outcomes.schema import OUTCOME_TYPES

    run_id = (kwargs.get("run_id") or "").strip()
    outcome_type = (kwargs.get("outcome_type") or "").strip()
    if not run_id:
        return json.dumps({"error": "run_id is required."})
    if not outcome_type:
        return json.dumps({"error": "outcome_type is required."})
    if outcome_type not in OUTCOME_TYPES:
        return json.dumps({
            "error": f"Unknown outcome_type '{outcome_type}'.",
            "valid": sorted(OUTCOME_TYPES),
        })
    evidence_url = (kwargs.get("evidence_url") or "").strip() or None
    gate_event_id = (kwargs.get("gate_event_id") or "").strip() or None
    note = (kwargs.get("note") or "").strip()
    raw_payload = kwargs.get("payload_json") or "{}"
    try:
        payload = json.dumps(
            json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
        )
    except (json.JSONDecodeError, TypeError):
        payload = "{}"
    outcome_id = str(_uuid.uuid4())
    recorded_at = datetime.now(timezone.utc).isoformat()
    base = _base_path()
    with _outcome_connect(base) as conn:
        conn.execute(
            """
            INSERT INTO outcome_event
                (outcome_id, run_id, outcome_type, evidence_url,
                 claim_run_id, payload, recorded_at, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (outcome_id, run_id, outcome_type, evidence_url,
             gate_event_id, payload, recorded_at, note),
        )
    return json.dumps({
        "status": "recorded",
        "outcome_id": outcome_id,
        "run_id": run_id,
        "outcome_type": outcome_type,
        "recorded_at": recorded_at,
    })


def _action_list_outcomes(kwargs: dict[str, Any]) -> str:
    branch_def_id = (kwargs.get("branch_def_id") or "").strip()
    run_id = (kwargs.get("run_id") or "").strip()
    outcome_type = (kwargs.get("outcome_type") or "").strip()
    try:
        limit = min(int(kwargs.get("limit") or 50), 200)
    except (TypeError, ValueError):
        limit = 50

    base = _base_path()

    # If filtering by branch_def_id, resolve matching run_ids first.
    if branch_def_id and not run_id:
        try:
            from workflow.runs import initialize_runs_db, query_runs
            initialize_runs_db(base)
            runs = query_runs(base, branch_def_id=branch_def_id, limit=1000)
            run_ids = [r["run_id"] for r in runs]
            if not run_ids:
                return json.dumps({"outcomes": [], "count": 0})
        except Exception:
            return json.dumps({"outcomes": [], "count": 0})
    else:
        run_ids = [run_id] if run_id else []

    with _outcome_connect(base) as conn:
        clauses: list[str] = []
        params: list[Any] = []
        if run_ids:
            placeholders = ",".join("?" * len(run_ids))
            clauses.append(f"run_id IN ({placeholders})")
            params.extend(run_ids)
        if outcome_type:
            clauses.append("outcome_type = ?")
            params.append(outcome_type)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)
        rows = conn.execute(
            f"SELECT * FROM outcome_event {where} ORDER BY recorded_at DESC LIMIT ?",
            params,
        ).fetchall()
    outcomes = [_outcome_row_to_dict(r) for r in rows]
    return json.dumps({"outcomes": outcomes, "count": len(outcomes)})


def _action_get_outcome(kwargs: dict[str, Any]) -> str:
    outcome_id = (kwargs.get("outcome_id") or "").strip()
    if not outcome_id:
        return json.dumps({"error": "outcome_id is required."})
    base = _base_path()
    with _outcome_connect(base) as conn:
        row = conn.execute(
            "SELECT * FROM outcome_event WHERE outcome_id = ?",
            (outcome_id,),
        ).fetchone()
    if row is None:
        return json.dumps({"error": f"outcome_id '{outcome_id}' not found."})
    return json.dumps(_outcome_row_to_dict(row))


_OUTCOME_ACTIONS: dict[str, Any] = {
    "record_outcome": _action_record_outcome,
    "list_outcomes": _action_list_outcomes,
    "get_outcome": _action_get_outcome,
}


# ── Attribution chain ──────────────────────────────────────────────────────

def _attribution_connect(base_path: "Path") -> Any:
    import sqlite3 as _sqlite3

    from workflow.attribution.schema import migrate_attribution_schema

    db = base_path / ".runs.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = _sqlite3.connect(str(db), timeout=30.0)
    conn.row_factory = _sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    migrate_attribution_schema(conn)
    conn.commit()
    return conn


_VALID_CONTRIBUTION_KINDS = frozenset({"original", "remix", "patch", "template"})


def _action_record_remix(kwargs: dict[str, Any]) -> str:
    import uuid as _uuid
    from datetime import datetime, timezone

    parent_id = (kwargs.get("parent_branch_def_id") or "").strip()
    child_id = (kwargs.get("child_branch_def_id") or "").strip()
    if not parent_id:
        return json.dumps({"error": "parent_branch_def_id is required."})
    if not child_id:
        return json.dumps({"error": "child_branch_def_id is required."})
    if parent_id == child_id:
        return json.dumps({"error": "parent_branch_def_id and child_branch_def_id must differ."})

    contribution_kind = (kwargs.get("contribution_kind") or "remix").strip()
    if contribution_kind not in _VALID_CONTRIBUTION_KINDS:
        return json.dumps({
            "error": f"Unknown contribution_kind '{contribution_kind}'.",
            "valid": sorted(_VALID_CONTRIBUTION_KINDS),
        })

    try:
        credit_share = float(kwargs.get("credit_share") or 0.0)
    except (TypeError, ValueError):
        credit_share = 0.0
    credit_share = max(0.0, min(1.0, credit_share))

    actor_id = (kwargs.get("actor_id") or "anonymous").strip() or "anonymous"
    base = _base_path()

    with _attribution_connect(base) as conn:
        # Cycle guard: reject if child already appears as an ancestor of parent.
        # Walk attribution_edge parents of parent_id up to 50 hops.
        ancestors: set[str] = set()
        frontier = [parent_id]
        for _ in range(50):
            if not frontier:
                break
            placeholders = ",".join("?" * len(frontier))
            rows = conn.execute(
                f"SELECT parent_id FROM attribution_edge WHERE child_id IN ({placeholders})",
                frontier,
            ).fetchall()
            frontier = []
            for r in rows:
                pid = r["parent_id"]
                if pid not in ancestors:
                    ancestors.add(pid)
                    frontier.append(pid)
        if child_id in ancestors or child_id == parent_id:
            return json.dumps({
                "error": "Cycle detected: child is already an ancestor of parent."
            })

        # Compute generation_depth = max depth of parent + 1 (minimum 1).
        row = conn.execute(
            "SELECT MAX(generation_depth) AS d FROM attribution_edge WHERE child_id = ?",
            (parent_id,),
        ).fetchone()
        parent_depth = int(row["d"] or 0) if row and row["d"] is not None else 0
        generation_depth = parent_depth + 1

        edge_id = str(_uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        try:
            conn.execute(
                """
                INSERT INTO attribution_edge
                    (edge_id, parent_id, child_id, parent_kind, child_kind,
                     generation_depth, contribution_kind, created_at)
                VALUES (?, ?, ?, 'branch', 'branch', ?, ?, ?)
                """,
                (edge_id, parent_id, child_id, generation_depth, contribution_kind, created_at),
            )
        except Exception as exc:
            if "UNIQUE constraint failed" in str(exc):
                return json.dumps({"error": f"Edge {parent_id} → {child_id} already exists."})
            raise

        # Record credit for the remixing actor on the child artifact.
        if credit_share > 0.0:
            credit_id = str(_uuid.uuid4())
            conn.execute(
                """
                INSERT OR IGNORE INTO attribution_credit
                    (credit_id, artifact_id, artifact_kind, actor_id,
                     credit_share, royalty_share, generation_depth,
                     contribution_kind, recorded_at)
                VALUES (?, ?, 'branch', ?, ?, 0.0, ?, ?, ?)
                """,
                (credit_id, child_id, actor_id, credit_share,
                 generation_depth, contribution_kind, created_at),
            )

    return json.dumps({
        "status": "recorded",
        "edge_id": edge_id,
        "parent_branch_def_id": parent_id,
        "child_branch_def_id": child_id,
        "contribution_kind": contribution_kind,
        "generation_depth": generation_depth,
        "credit_share": credit_share,
        "actor_id": actor_id,
        "created_at": created_at,
    })


def _action_get_provenance(kwargs: dict[str, Any]) -> str:
    child_id = (kwargs.get("child_branch_def_id") or "").strip()
    if not child_id:
        return json.dumps({"error": "child_branch_def_id is required."})
    try:
        max_depth = max(1, min(50, int(kwargs.get("max_depth") or 10)))
    except (TypeError, ValueError):
        max_depth = 10

    base = _base_path()
    chain: list[dict[str, Any]] = []

    with _attribution_connect(base) as conn:
        frontier = [child_id]
        visited: set[str] = {child_id}
        depth = 0
        while frontier and depth < max_depth:
            placeholders = ",".join("?" * len(frontier))
            rows = conn.execute(
                f"""
                SELECT e.parent_id, e.child_id, e.generation_depth,
                       e.contribution_kind, e.edge_id, e.created_at,
                       c.actor_id, c.credit_share
                FROM attribution_edge e
                LEFT JOIN attribution_credit c
                    ON c.artifact_id = e.child_id AND c.artifact_kind = 'branch'
                WHERE e.child_id IN ({placeholders})
                ORDER BY e.generation_depth ASC
                """,
                frontier,
            ).fetchall()
            next_frontier: list[str] = []
            for r in rows:
                chain.append({
                    "edge_id": r["edge_id"],
                    "parent_branch_def_id": r["parent_id"],
                    "child_branch_def_id": r["child_id"],
                    "generation_depth": r["generation_depth"],
                    "contribution_kind": r["contribution_kind"],
                    "actor_id": r["actor_id"],
                    "credit_share": r["credit_share"],
                    "created_at": r["created_at"],
                })
                pid = r["parent_id"]
                if pid not in visited:
                    visited.add(pid)
                    next_frontier.append(pid)
            frontier = next_frontier
            depth += 1

    return json.dumps({
        "child_branch_def_id": child_id,
        "chain": chain,
        "count": len(chain),
    })


_ATTRIBUTION_ACTIONS: dict[str, Any] = {
    "record_remix": _action_record_remix,
    "get_provenance": _action_get_provenance,
}


# ───────────────────────────────────────────────────────────────────────────
# Phase 4: Eval + iteration hooks
# ───────────────────────────────────────────────────────────────────────────
# Five small actions on the `extensions` tool that close the
# build → run → judge → edit → rerun loop. No numeric scoring (spec
# §Non-goals). No AI-in-the-loop judge. `suggest_node_edit` bundles
# context so Claude.ai makes the edit in ~one tool call, not four.


def _split_tag_csv(raw: str) -> list[str]:
    return [t.strip() for t in (raw or "").split(",") if t.strip()]


def _action_judge_run(kwargs: dict[str, Any]) -> str:
    """Attach a natural-language judgment to a run (optionally to a node)."""
    from workflow.runs import add_judgment
    from workflow.runs import get_run as _get_run

    rid = (kwargs.get("run_id") or "").strip()
    text = (kwargs.get("judgment_text") or "").strip()
    if not rid:
        return json.dumps({"error": "run_id is required."})
    if not text:
        return json.dumps({"error": "judgment_text is required."})

    run_record = _get_run(_base_path(), rid)
    if run_record is None:
        return json.dumps({"error": f"Run '{rid}' not found."})

    node_id = (kwargs.get("node_id") or "").strip() or None
    tag_list = _split_tag_csv(kwargs.get("tags", ""))

    saved = add_judgment(
        _base_path(),
        run_id=rid, text=text, node_id=node_id,
        tags=tag_list, author=_current_actor(),
    )
    scope = f"node `{node_id}`" if node_id else "whole run"
    tag_suffix = f" ({', '.join(tag_list)})" if tag_list else ""
    branch_label = _branch_name_for_run(run_record)
    text_md = (
        f"**Judgment recorded** on workflow '{branch_label}' — "
        f"{scope}{tag_suffix}.\n\n"
        f"> {text[:240]}"
        + ("…" if len(text) > 240 else "")
    )
    # Merge: put saved fields first, then overlay the rendered text +
    # status so the response-level `text` isn't clobbered by the
    # judgment's own free-form text field.
    response: dict[str, Any] = dict(saved)
    response["text"] = text_md
    response["status"] = "recorded"
    response["judgment_text"] = saved.get("text", "")
    return json.dumps(response, default=str)


def _action_list_judgments(kwargs: dict[str, Any]) -> str:
    from workflow.runs import list_judgments as _list_judgments

    bid = (kwargs.get("branch_def_id") or "").strip()
    rid = (kwargs.get("run_id") or "").strip()
    nid = (kwargs.get("node_id") or "").strip()
    if not (bid or rid or nid):
        return json.dumps({
            "error": (
                "Pass at least one filter: branch_def_id, run_id, or "
                "node_id. Full-table scans are disabled."
            ),
        })

    rows = _list_judgments(
        _base_path(),
        branch_def_id=bid, run_id=rid, node_id=nid,
        limit=int(kwargs.get("limit", 30) or 30),
    )
    if rows:
        lines = [f"**{len(rows)} judgment(s):**", ""]
        for j in rows[:12]:
            scope = (
                f"node=`{j['node_id']}`" if j.get("node_id")
                else "run-scoped"
            )
            tags_str = (
                f" [{', '.join(j['tags'])}]" if j.get("tags") else ""
            )
            first_line = (j.get("text") or "").split("\n", 1)[0]
            if len(first_line) > 100:
                first_line = first_line[:100].rstrip() + "…"
            lines.append(
                f"- `{j['author']}` · {scope}{tags_str} · {first_line}"
            )
        if len(rows) > 12:
            lines.append(
                f"- … and {len(rows) - 12} more. Narrow with "
                "run_id or node_id."
            )
        text_md = "\n".join(lines)
    else:
        text_md = "No judgments match the filter."
    return json.dumps({
        "text": text_md,
        "judgments": rows,
        "count": len(rows),
    }, default=str)


def _action_compare_runs(kwargs: dict[str, Any]) -> str:
    """Render a side-by-side diff of two runs' final outputs.

    Topology diff emitted only when branch_version changed — avoids
    visual noise for prompt-only edits (the common case).
    """
    from workflow.runs import get_lineage
    from workflow.runs import get_run as _get_run

    rid_a = (kwargs.get("run_a_id") or "").strip()
    rid_b = (kwargs.get("run_b_id") or "").strip()
    if not (rid_a and rid_b):
        return json.dumps({
            "error": "run_a_id and run_b_id are both required.",
        })

    rec_a = _get_run(_base_path(), rid_a)
    rec_b = _get_run(_base_path(), rid_b)
    if rec_a is None or rec_b is None:
        missing = rid_a if rec_a is None else rid_b
        return json.dumps({"error": f"Run '{missing}' not found."})

    lineage_a = get_lineage(_base_path(), rid_a) or {}
    lineage_b = get_lineage(_base_path(), rid_b) or {}
    version_a = int(lineage_a.get("branch_version", 0) or 0)
    version_b = int(lineage_b.get("branch_version", 0) or 0)
    topology_changed = bool(version_a and version_b and version_a != version_b)

    field = (kwargs.get("field") or "").strip()
    out_a = rec_a.get("output") or {}
    out_b = rec_b.get("output") or {}

    differences: list[dict[str, Any]] = []
    if field:
        a_val = out_a.get(field)
        b_val = out_b.get(field)
        differences.append({
            "node_id": field,
            "change_type": "unchanged" if a_val == b_val else "changed",
            "a_value": a_val,
            "b_value": b_val,
            "field": field,
        })
    else:
        keys = sorted(set(out_a) | set(out_b))
        for k in keys:
            a_val = out_a.get(k)
            b_val = out_b.get(k)
            if k not in out_a:
                change_type = "added"
            elif k not in out_b:
                change_type = "removed"
            elif a_val == b_val:
                change_type = "unchanged"
            else:
                change_type = "changed"
            differences.append({
                "node_id": k,
                "change_type": change_type,
                "a_value": a_val,
                "b_value": b_val,
                "field": k,
            })

    # Build phone-legible markdown.
    lines = [
        f"**Comparing runs** `{rid_a}` ↔ `{rid_b}`.",
        f"Branch version: {version_a} → {version_b}"
        + (
            " (topology changed)" if topology_changed
            else " (same version)" if version_a == version_b
            else ""
        ),
        "",
    ]
    changed = [d for d in differences if d["change_type"] != "unchanged"]
    unchanged_count = len(differences) - len(changed)
    if unchanged_count:
        lines.append(
            f"_{unchanged_count} field(s) unchanged._"
        )
        lines.append("")
    if changed:
        for d in changed:
            lines.append(f"### {d['node_id']} — {d['change_type']}")
            a_preview = str(d.get("a_value", ""))[:240]
            b_preview = str(d.get("b_value", ""))[:240]
            lines.append("```diff")
            lines.append(f"- {a_preview}")
            lines.append(f"+ {b_preview}")
            lines.append("```")
            lines.append("")
    else:
        lines.append("No field-level differences between the two runs.")

    return json.dumps({
        "text": "\n".join(lines).rstrip(),
        "run_a": {
            "run_id": rid_a,
            "branch_version": version_a,
            "final_state": out_a,
        },
        "run_b": {
            "run_id": rid_b,
            "branch_version": version_b,
            "final_state": out_b,
        },
        "differences": differences,
        "topology_changed": topology_changed,
    }, default=str)


def _action_suggest_node_edit(kwargs: dict[str, Any]) -> str:
    """Bundle everything Claude.ai needs to propose an edit, in one call.

    Per spec: this does NOT call an LLM. It assembles context. The
    calling client proposes the edit.
    """
    from workflow.branches import BranchDefinition
    from workflow.daemon_server import get_branch_definition
    from workflow.runs import (
        list_judgments as _list_judgments,
    )
    from workflow.runs import (
        list_runs as _list_runs,
    )
    from workflow.runs import (
        node_output_from_run,
    )

    bid = (kwargs.get("branch_def_id") or "").strip()
    nid = (kwargs.get("node_id") or "").strip()
    user_context = (kwargs.get("context") or "").strip()
    if not (bid and nid):
        return json.dumps({
            "error": "branch_def_id and node_id are both required.",
        })

    _ensure_author_server_db()
    try:
        source = get_branch_definition(_base_path(), branch_def_id=bid)
    except KeyError:
        return json.dumps({"error": f"Branch '{bid}' not found."})
    branch = BranchDefinition.from_dict(source)
    node = next((n for n in branch.node_defs if n.node_id == nid), None)
    if node is None:
        return json.dumps({
            "error": f"Node '{nid}' not found on branch '{bid}'.",
        })

    # Recent runs on this branch.
    recent_runs = _list_runs(_base_path(), branch_def_id=bid, limit=5)
    recent_outputs: list[dict[str, Any]] = []
    for r in recent_runs:
        snap = node_output_from_run(
            _base_path(), run_id=r["run_id"], node_id=nid,
        )
        if snap is None:
            continue
        detail = snap.get("detail") or {}
        response = str(
            detail.get("response")
            or detail.get("output")
            or ""
        )
        if len(response) > 500:
            response = response[:500].rstrip() + "…"
        recent_outputs.append({
            "run_id": r["run_id"],
            "status": r.get("status"),
            "output_summary": response,
        })
        if len(recent_outputs) >= 3:
            break

    # Judgments scoped to this node.
    judgments = _list_judgments(
        _base_path(), branch_def_id=bid, node_id=nid, limit=30,
    )

    body_kind = (
        "prompt_template" if node.prompt_template else (
            "source_code" if node.source_code else "passthrough"
        )
    )
    body = node.prompt_template or node.source_code or ""

    # Compose a framed prompt block Claude.ai can act on directly.
    branch_label = branch.name or "(unnamed workflow)"
    lines = [
        f"**Suggest edit for node `{nid}`** on workflow "
        f"'{branch_label}' (`{node.display_name}`).",
        "",
        f"**Current {body_kind}:**",
        "",
        "```",
        body or "(empty)",
        "```",
        "",
    ]
    if recent_outputs:
        lines.append("**Recent outputs:**")
        lines.append("")
        for ro in recent_outputs:
            preview = ro["output_summary"] or "(no output captured)"
            lines.append(f"- `{ro['run_id']}` ({ro['status']}): {preview}")
        lines.append("")
    if judgments:
        lines.append("**Judgments targeting this node:**")
        lines.append("")
        for j in judgments[:10]:
            tag_str = (
                f" [{', '.join(j['tags'])}]" if j.get("tags") else ""
            )
            first_line = (j.get("text") or "").split("\n", 1)[0]
            if len(first_line) > 140:
                first_line = first_line[:140].rstrip() + "…"
            lines.append(
                f"- {j['author']}{tag_str}: {first_line}"
            )
        lines.append("")
    if user_context:
        lines.append(f"**User context:** {user_context}")
        lines.append("")
    lines.append(
        "Now propose a new `prompt_template` (or `source_code`) and "
        "apply it via `update_node` when the user agrees."
    )

    return json.dumps({
        "text": "\n".join(lines),
        "node": node.to_dict(),
        "recent_runs": recent_outputs,
        "judgments": judgments,
        "user_context": user_context,
    }, default=str)


def _action_get_node_output(kwargs: dict[str, Any]) -> str:
    """Return a single node's output from a specific run — the hook
    users need to judge a specific node rather than the final state."""
    from workflow.runs import get_run as _get_run
    from workflow.runs import node_output_from_run

    rid = (kwargs.get("run_id") or "").strip()
    nid = (kwargs.get("node_id") or "").strip()
    if not (rid and nid):
        return json.dumps({
            "error": "run_id and node_id are both required.",
        })
    run_record = _get_run(_base_path(), rid)
    if run_record is None:
        return json.dumps({"error": f"Run '{rid}' not found."})

    snap = node_output_from_run(_base_path(), run_id=rid, node_id=nid)
    if snap is None:
        return json.dumps({
            "error": (
                f"Node '{nid}' did not emit a 'ran' event on run "
                f"'{rid}'. Possible: node skipped, run failed before "
                "reaching it, or run not yet complete."
            ),
        })

    detail = snap.get("detail") or {}
    output_preview = str(
        detail.get("response") or detail.get("output") or ""
    )
    truncated = len(output_preview) > 2000
    if truncated:
        output_preview = output_preview[:2000].rstrip() + "…"

    branch_label = _branch_name_for_run(run_record)
    lines = [
        f"**Node `{nid}` output** from a run of workflow "
        f"'{branch_label}' (step {snap.get('step_index')}).",
        "",
        "```",
        output_preview or "(no output captured)",
        "```",
    ]
    if truncated:
        lines.append("")
        lines.append(
            "_(Output truncated to 2000 chars in text; full detail "
            "in structuredContent.)_"
        )

    return json.dumps({
        "text": "\n".join(lines),
        "run_id": rid,
        "node_id": nid,
        "step_index": snap.get("step_index"),
        "output": detail,
        "tool_calls": detail.get("tool_calls", []),
    }, default=str)


# ── #50: node version rollback ─────────────────────────────────────────
# `rollback_node` restores a node's body to an earlier version snapshot
# preserved in the node_edit_audit log. Rollback is itself an edit —
# bumps the branch version and emits its own audit row with
# ``edit_kind="rollback"`` so forward history is preserved. Judgments
# stay attached to the runs that produced them (their lineage points at
# specific versions), so rolling back doesn't strip accumulated signal.


def _node_body_summary(node_def: dict[str, Any]) -> str:
    """One-line summary for the version list. Phone-legible."""
    display = node_def.get("display_name") or node_def.get("node_id") or "?"
    if node_def.get("prompt_template"):
        body = (node_def.get("prompt_template") or "").strip()
        preview = body.replace("\n", " ")
        if len(preview) > 60:
            preview = preview[:60].rstrip() + "…"
        return f"{display} · prompt: {preview}"
    if node_def.get("source_code"):
        return (
            f"{display} · source_code "
            f"({len(node_def['source_code'])} chars)"
        )
    return f"{display} · passthrough"


def _action_list_node_versions(kwargs: dict[str, Any]) -> str:
    """Return the version history for a single node on a branch."""
    from workflow.branches import BranchDefinition
    from workflow.daemon_server import get_branch_definition
    from workflow.runs import list_node_edit_audits

    bid = (kwargs.get("branch_def_id") or "").strip()
    nid = (kwargs.get("node_id") or "").strip()
    if not (bid and nid):
        return json.dumps({
            "error": "branch_def_id and node_id are both required.",
        })

    _ensure_author_server_db()
    try:
        source = get_branch_definition(_base_path(), branch_def_id=bid)
    except KeyError:
        return json.dumps({"error": f"Branch '{bid}' not found."})
    branch = BranchDefinition.from_dict(source)
    current_node = next(
        (n for n in branch.node_defs if n.node_id == nid), None,
    )
    if current_node is None:
        return json.dumps({
            "error": f"Node '{nid}' not found on branch '{bid}'.",
        })

    audits = list_node_edit_audits(
        _base_path(), branch_def_id=bid, node_id=nid, limit=200,
    )

    current_version = int(branch.version or 1)
    versions: list[dict[str, Any]] = []
    seen: set[int] = set()

    versions.append({
        "version": current_version,
        "kind": "current",
        "timestamp": None,
        "node": current_node.to_dict(),
        "summary": _node_body_summary(current_node.to_dict()),
        "triggered_by_judgment_id": None,
    })
    seen.add(current_version)

    for a in audits:
        va = int(a["version_after"])
        if va not in seen and a.get("node_after"):
            versions.append({
                "version": va,
                "kind": a.get("edit_kind", "update"),
                "timestamp": a.get("timestamp"),
                "node": a["node_after"],
                "summary": _node_body_summary(a["node_after"]),
                "triggered_by_judgment_id": a.get(
                    "triggered_by_judgment_id"
                ),
            })
            seen.add(va)
        vb = int(a["version_before"])
        if vb not in seen and a.get("node_before"):
            versions.append({
                "version": vb,
                "kind": "previous",
                "timestamp": None,
                "node": a["node_before"],
                "summary": _node_body_summary(a["node_before"]),
                "triggered_by_judgment_id": None,
            })
            seen.add(vb)

    versions.sort(key=lambda v: v["version"], reverse=True)

    branch_label = branch.name or "(unnamed workflow)"
    lines = [
        f"**{len(versions)} version(s) of node `{nid}`** on workflow "
        f"'{branch_label}' (current: v{current_version}).",
        "",
        "| Version | Kind | Summary |",
        "|---:|---|---|",
    ]
    for v in versions[:20]:
        marker = (
            "← current" if v["version"] == current_version else ""
        )
        lines.append(
            f"| v{v['version']} | {v['kind']} | "
            f"{v['summary']} {marker} |".rstrip()
        )
    if len(versions) > 20:
        lines.append("")
        lines.append(
            f"_(showing 20 of {len(versions)} versions — full history "
            "in structuredContent)_"
        )
    lines.append("")
    lines.append(
        f"Rollback with `rollback_node branch_def_id={bid} "
        f"node_id={nid} to_version=<N>`."
    )

    return json.dumps({
        "text": "\n".join(lines),
        "branch_def_id": bid,
        "node_id": nid,
        "current_version": current_version,
        "versions": versions,
    }, default=str)


def _action_rollback_node(kwargs: dict[str, Any]) -> str:
    """Restore a node to a previously recorded version.

    Rollback is itself an edit: bumps the branch version and emits a new
    audit row with ``edit_kind="rollback"``. Forward history is never
    destroyed — the old body stays retrievable via list_node_versions.
    """
    from workflow.branches import BranchDefinition, NodeDefinition
    from workflow.daemon_server import (
        get_branch_definition,
        save_branch_definition,
    )
    from workflow.runs import (
        find_node_snapshot,
        list_node_edit_audits,
        record_node_edit_audit,
    )

    bid = (kwargs.get("branch_def_id") or "").strip()
    nid = (kwargs.get("node_id") or "").strip()
    if not (bid and nid):
        return json.dumps({
            "status": "rejected",
            "error": "branch_def_id and node_id are both required.",
        })

    _ensure_author_server_db()
    try:
        source = get_branch_definition(_base_path(), branch_def_id=bid)
    except KeyError:
        return json.dumps({
            "status": "rejected",
            "error": f"Branch '{bid}' not found.",
        })

    branch = BranchDefinition.from_dict(source)
    current_node = next(
        (n for n in branch.node_defs if n.node_id == nid), None,
    )
    if current_node is None:
        return json.dumps({
            "status": "rejected",
            "error": f"Node '{nid}' not found on branch '{bid}'.",
        })

    current_version = int(branch.version or 1)

    to_version_raw = kwargs.get("to_version", "")
    to_version: int | None = None
    if isinstance(to_version_raw, int):
        to_version = to_version_raw
    elif isinstance(to_version_raw, str) and to_version_raw.strip():
        try:
            to_version = int(to_version_raw.strip())
        except ValueError:
            return json.dumps({
                "status": "rejected",
                "error": (
                    f"to_version must be an integer, got "
                    f"{to_version_raw!r}."
                ),
            })

    restored_body: dict[str, Any] = {}
    if to_version is None:
        audits = list_node_edit_audits(
            _base_path(), branch_def_id=bid, node_id=nid, limit=10,
        )
        latest = next(
            (
                a for a in audits
                if int(a["version_after"]) == current_version
            ),
            None,
        )
        if latest is None:
            return json.dumps({
                "status": "rejected",
                "error": (
                    f"No recorded previous version of node '{nid}'. "
                    "Nothing to roll back to."
                ),
            })
        restored_body = latest.get("node_before") or {}
        to_version = int(latest["version_before"])
    elif to_version == current_version:
        return json.dumps({
            "status": "rejected",
            "error": (
                f"Node '{nid}' is already at version {current_version}."
            ),
        })
    else:
        restored_body = find_node_snapshot(
            _base_path(),
            branch_def_id=bid, node_id=nid, at_version=to_version,
        ) or {}
        if not restored_body:
            return json.dumps({
                "status": "rejected",
                "error": (
                    f"No snapshot of node '{nid}' at version "
                    f"{to_version}. Run list_node_versions to see "
                    "available targets."
                ),
            })

    try:
        restored_node = NodeDefinition.from_dict(restored_body)
    except Exception as exc:
        return json.dumps({
            "status": "rejected",
            "error": f"Restored body is not a valid NodeDefinition: {exc}",
        })

    node_before_body = current_node.to_dict()

    new_node_defs = [
        restored_node if n.node_id == nid else n
        for n in branch.node_defs
    ]
    branch.node_defs = new_node_defs

    new_version = current_version + 1
    staging_dict = branch.to_dict()
    staging_dict["version"] = new_version
    saved = save_branch_definition(_base_path(), branch_def=staging_dict)
    persisted = BranchDefinition.from_dict(saved)
    persisted_node = next(
        (n for n in persisted.node_defs if n.node_id == nid),
        restored_node,
    )

    try:
        record_node_edit_audit(
            _base_path(),
            branch_def_id=bid,
            version_before=current_version,
            version_after=new_version,
            nodes_changed=[nid],
            triggered_by_judgment_id=None,
            node_before=node_before_body,
            node_after=persisted_node.to_dict(),
            edit_kind="rollback",
        )
    except Exception:
        logger.exception("rollback audit failed for %s/%s", bid, nid)

    branch_label = persisted.name or "(unnamed workflow)"
    text_lines = [
        f"**Rolled back node `{nid}`** on workflow '{branch_label}' to "
        f"v{to_version} (workflow now at v{new_version}).",
        "",
        f"- Restored body: "
        f"{_node_body_summary(persisted_node.to_dict())}",
        "",
        "_Rollback is itself an edit — the previous body is still in "
        "history if you need to go forward again. List versions with "
        "`list_node_versions`._",
    ]

    return json.dumps({
        "text": "\n".join(text_lines),
        "status": "rolled_back",
        "branch_def_id": bid,
        "node_id": nid,
        "restored_from_version": to_version,
        "version_before": current_version,
        "version_after": new_version,
        "node": persisted_node.to_dict(),
    }, default=str)


_JUDGMENT_ACTIONS: dict[str, Any] = {
    "judge_run": _action_judge_run,
    "list_judgments": _action_list_judgments,
    "compare_runs": _action_compare_runs,
    "suggest_node_edit": _action_suggest_node_edit,
    "get_node_output": _action_get_node_output,
    "rollback_node": _action_rollback_node,
    "list_node_versions": _action_list_node_versions,
}

_JUDGMENT_WRITE_ACTIONS: frozenset[str] = frozenset({
    "judge_run", "rollback_node",
})


def _dispatch_judgment_action(
    action: str,
    handler: Any,
    kwargs: dict[str, Any],
) -> str:
    """Dispatch a Phase 4 action. ``judge_run`` is the only write; the
    rest are read-only and bypass the ledger."""
    result_str = handler(kwargs)
    if action not in _JUDGMENT_WRITE_ACTIONS:
        return result_str

    try:
        result = json.loads(result_str)
    except (json.JSONDecodeError, TypeError):
        return result_str
    if not isinstance(result, dict) or "error" in result:
        return result_str

    try:
        target = (
            result.get("judgment_id")
            or result.get("run_id")
            or kwargs.get("run_id", "")
        )
        summary_bits = [action]
        if kwargs.get("run_id"):
            summary_bits.append(f"run={kwargs['run_id']}")
        if kwargs.get("node_id"):
            summary_bits.append(f"node={kwargs['node_id']}")
        _append_global_ledger(
            action,
            target=str(target),
            summary=_truncate(" ".join(summary_bits)),
            payload=None,
        )
    except Exception as exc:
        logger.warning(
            "Ledger write failed for judgment action %s: %s", action, exc,
        )
    return result_str


# ═══════════════════════════════════════════════════════════════════════════
# TOOL 3 — Goals (first-class shared primitive above Branches)
# ═══════════════════════════════════════════════════════════════════════════
# Phase 5 per docs/specs/community_branches_phase5.md. A Goal is the
# intent a Branch serves — "produce a research paper", "plan a
# wedding". Many Branches bind to one Goal. 8 actions: propose,
# update, bind, list, get, search, leaderboard, common_nodes.
# Storage in workflow/author_server.py.


def _current_actor_or_anon() -> str:
    """Wrapper around the existing ``_current_actor`` for clarity in
    the Goals surface. Identical behavior."""
    return _current_actor()


def _format_goal_catalog_line(g: dict[str, Any]) -> str:
    tags = g.get("tags") or []
    tag_suffix = f" [{', '.join(tags[:3])}]" if tags else ""
    desc = (g.get("description") or "").strip().split("\n", 1)[0]
    if len(desc) > 100:
        desc = desc[:100].rstrip() + "…"
    name = g.get("name") or "(unnamed)"
    return (
        f"- `{g['goal_id']}` · **{name}** · {g.get('author')}"
        f"{tag_suffix}" + (f" · {desc}" if desc else "")
    )


def _action_goal_propose(kwargs: dict[str, Any]) -> str:
    from workflow.identity import git_author

    name = (kwargs.get("name") or "").strip()
    if not name:
        return json.dumps({
            "status": "rejected",
            "error": "name is required for propose.",
        })
    _ensure_author_server_db()
    tags = _split_csv(kwargs.get("tags", ""))
    visibility = (kwargs.get("visibility") or "public").strip().lower()
    if visibility not in {"public", "private"}:
        return json.dumps({
            "status": "rejected",
            "error": (
                "visibility must be 'public' or 'private' at propose "
                "time. Use the `delete_goal` action to soft-delete."
            ),
        })
    goal_dict = {
        "name": name,
        "description": kwargs.get("description", ""),
        "author": _current_actor_or_anon(),
        "tags": tags,
        "visibility": visibility,
    }
    try:
        saved, _commit = _storage_backend().save_goal_and_commit(
            goal_dict,
            author=git_author(_current_actor()),
            message=f"goals.propose: {name}",
            force=bool(kwargs.get("force", False)),
        )
    except CommitFailedError as exc:
        return json.dumps(_format_commit_failed(exc))
    text = (
        f"**Proposed Goal: {saved['name']}.**\n\n"
        "Bind existing workflows to this Goal with the `goals` action "
        "`bind` (pass the Goal name and workflow name). Search for "
        "related intent with `goals action=search query=...`."
    )
    return json.dumps({
        "text": text,
        "status": "proposed",
        "goal": saved,
    }, default=str)


def _action_goal_update(kwargs: dict[str, Any]) -> str:
    from workflow.daemon_server import get_goal
    from workflow.daemon_server import update_goal as _update
    from workflow.identity import git_author

    gid = (kwargs.get("goal_id") or "").strip()
    if not gid:
        return json.dumps({
            "status": "rejected",
            "error": "goal_id is required.",
        })
    _ensure_author_server_db()
    try:
        current = get_goal(_base_path(), goal_id=gid)
    except KeyError:
        return json.dumps({
            "status": "rejected",
            "error": f"Goal '{gid}' not found.",
        })

    # Soft ownership: author-only for update. Host is ambient so future
    # host-admin override can be bolted on without schema change.
    actor = _current_actor_or_anon()
    if current["author"] != actor and actor != "host":
        return json.dumps({
            "status": "rejected",
            "error": (
                f"Goal '{gid}' is owned by '{current['author']}'. "
                "Only the author can update it (Phase 5 default). "
                "Propose a new Goal to capture your variant."
            ),
        })

    updates: dict[str, Any] = {}
    for fld in ("name", "description"):
        if kwargs.get(fld):
            updates[fld] = kwargs[fld]
    if kwargs.get("tags"):
        updates["tags"] = _split_csv(kwargs["tags"])
    if kwargs.get("visibility"):
        vis = (kwargs["visibility"] or "").strip().lower()
        if vis not in {"public", "private", "deleted"}:
            return json.dumps({
                "status": "rejected",
                "error": (
                    "visibility must be 'public', 'private', or "
                    "'deleted'."
                ),
            })
        updates["visibility"] = vis
    if not updates:
        return json.dumps({
            "status": "rejected",
            "error": (
                "No fields to update. Pass one or more of name, "
                "description, tags, visibility."
            ),
        })

    # Apply the SQLite update (owns column-level merging + validation).
    # Then route the resulting full goal dict through the cached backend
    # so the YAML mirror refreshes + single commit lands.
    updated = _update(_base_path(), goal_id=gid, updates=updates)
    try:
        saved, _commit = _storage_backend().save_goal_and_commit(
            updated,
            author=git_author(_current_actor()),
            message=f"goals.update: {gid}",
            force=bool(kwargs.get("force", False)),
        )
    except CommitFailedError as exc:
        return json.dumps(_format_commit_failed(exc))
    changed = sorted(updates.keys())
    text = (
        f"**Updated Goal '{saved['name']}'.** Fields changed: "
        f"{', '.join(changed)}."
    )
    return json.dumps({
        "text": text,
        "status": "updated",
        "changed_fields": changed,
        "goal": saved,
    }, default=str)


def _action_goal_bind(kwargs: dict[str, Any]) -> str:
    from workflow.daemon_server import (
        get_branch_definition,
        get_goal,
        update_branch_definition,
    )

    bid = (kwargs.get("branch_def_id") or "").strip()
    gid = (kwargs.get("goal_id") or "").strip()
    if not bid:
        return json.dumps({
            "status": "rejected",
            "error": "branch_def_id is required.",
        })
    _ensure_author_server_db()
    try:
        branch = get_branch_definition(_base_path(), branch_def_id=bid)
    except KeyError:
        return json.dumps({
            "status": "rejected",
            "error": f"Branch '{bid}' not found.",
        })

    if gid:
        try:
            goal = get_goal(_base_path(), goal_id=gid)
        except KeyError:
            return json.dumps({
                "status": "rejected",
                "error": f"Goal '{gid}' not found.",
            })
        if goal.get("visibility") == "deleted":
            return json.dumps({
                "status": "rejected",
                "error": (
                    f"Goal '{gid}' is soft-deleted. Propose a new Goal "
                    "or re-open the deleted one first."
                ),
            })
    else:
        goal = None

    from workflow.branches import BranchDefinition
    from workflow.identity import git_author

    update_branch_definition(
        _base_path(), branch_def_id=bid,
        updates={"goal_id": gid or None},
    )
    # Re-read post-update and route through cached backend so the YAML
    # mirror + single commit capture the cross-table edit. Commit targets
    # the branch path only (goal row isn't mutated by bind).
    updated_branch = get_branch_definition(_base_path(), branch_def_id=bid)
    branch_obj = BranchDefinition.from_dict(updated_branch)
    if gid and goal is not None:
        commit_msg = f"goals.bind: {branch['name']} → {goal['name']}"
    else:
        commit_msg = f"goals.bind: {branch['name']} ∅ (unbind)"
    try:
        _storage_backend().save_branch_and_commit(
            branch_obj,
            author=git_author(_current_actor()),
            message=commit_msg,
            force=bool(kwargs.get("force", False)),
        )
    except CommitFailedError as exc:
        return json.dumps(_format_commit_failed(exc))
    if gid:
        text = (
            f"**Bound** workflow '{branch['name']}' to "
            f"Goal '{goal['name']}'. Inspect the Goal with "
            "`goals action=get` (Goal name or id in structuredContent)."
        )
        status = "bound"
    else:
        text = (
            f"**Unbound** workflow '{branch['name']}' from its "
            "previous Goal."
        )
        status = "unbound"
    return json.dumps({
        "text": text,
        "status": status,
        "branch_def_id": bid,
        "goal_id": gid or None,
    }, default=str)


def _action_goal_list(kwargs: dict[str, Any]) -> str:
    from workflow.daemon_server import list_goals

    _ensure_author_server_db()
    rows = list_goals(
        _base_path(),
        author=kwargs.get("author", ""),
        tag=(_split_csv(kwargs.get("tags", ""))[:1] or [""])[0],
        limit=int(kwargs.get("limit", 50) or 50),
    )
    if rows:
        lines = [f"**{len(rows)} Goal(s):**", ""]
        for g in rows[:12]:
            lines.append(_format_goal_catalog_line(g))
        if len(rows) > 12:
            lines.append(
                f"- … and {len(rows) - 12} more. Narrow with "
                "`tags=...` or `author=...`."
            )
        text = "\n".join(lines)
    else:
        text = "No Goals match the filter yet. Propose one with `goals action=propose name=...`."
    return json.dumps({
        "text": text,
        "goals": rows,
        "count": len(rows),
    }, default=str)


def _action_goal_get(kwargs: dict[str, Any]) -> str:
    from workflow.daemon_server import (
        branches_for_goal,
        get_goal,
        goal_gate_summary,
    )

    gid = (kwargs.get("goal_id") or "").strip()
    if not gid:
        return json.dumps({
            "status": "rejected",
            "error": "goal_id is required.",
        })
    _ensure_author_server_db()
    try:
        goal = get_goal(_base_path(), goal_id=gid)
    except KeyError:
        return json.dumps({
            "status": "rejected",
            "error": f"Goal '{gid}' not found.",
        })

    # Phase 6.2.2 — viewer-aware. Private Branches owned by other
    # actors are excluded from this Goal's published Branch list.
    branches = branches_for_goal(
        _base_path(), goal_id=gid, viewer=_current_actor(),
    )
    is_deleted = goal.get("visibility") == "deleted"

    # Phase 6.4: gate_summary rides alongside branches/is_deleted.
    # When GATES_ENABLED=0, return a flag-gated placeholder so the
    # UI can render "gates off" without mistaking it for "no claims".
    if _gates_enabled():
        gate_summary = goal_gate_summary(_base_path(), goal_id=gid)
    else:
        gate_summary = {"status": "gates_disabled"}

    lines = [
        f"**Goal: {goal['name']}**",
        f"Author: {goal['author']}   Visibility: {goal['visibility']}",
    ]
    if goal.get("tags"):
        lines.append(f"Tags: {', '.join(goal['tags'])}")
    if goal.get("description"):
        lines.append("")
        lines.append(goal["description"])
    lines.append("")
    if branches:
        lines.append(
            f"**{len(branches)} Branch(es)** bound to this Goal:"
        )
        lines.append("")
        for b in branches[:12]:
            lines.append(
                f"- `{b['branch_def_id']}` · **{b['name']}** · "
                f"{b['author']} · v{b.get('version', 1)}"
            )
        if len(branches) > 12:
            lines.append(
                f"- … and {len(branches) - 12} more. Filter with "
                f"`extensions action=list_branches goal_id={gid}`."
            )
    else:
        lines.append(
            "_No Branches yet. Bind an existing Branch with "
            f"`goals action=bind branch_def_id=... goal_id={gid}`._"
        )
    if is_deleted:
        lines.append("")
        lines.append(
            "_Note: this Goal is soft-deleted. Existing binds remain "
            "resolvable but new binds are rejected._"
        )

    return json.dumps({
        "text": "\n".join(lines),
        "goal": goal,
        "is_deleted": is_deleted,
        "branches": branches,
        "branch_count": len(branches),
        "gate_summary": gate_summary,
    }, default=str)


def _action_goal_search(kwargs: dict[str, Any]) -> str:
    from workflow.daemon_server import search_goals

    query = (kwargs.get("query") or "").strip()
    if not query:
        return json.dumps({
            "status": "rejected",
            "error": "query is required for search.",
        })
    _ensure_author_server_db()
    rows = search_goals(
        _base_path(), query=query,
        limit=int(kwargs.get("limit", 20) or 20),
    )
    if rows:
        lines = [f"**{len(rows)} match(es) for `{query}`:**", ""]
        for g in rows[:12]:
            lines.append(_format_goal_catalog_line(g))
        if len(rows) > 12:
            lines.append(
                f"- … and {len(rows) - 12} more. Tighten the query."
            )
        text = "\n".join(lines)
    else:
        text = (
            f"No Goals match `{query}`. Propose a new Goal if the "
            "intent doesn't already exist."
        )
    return json.dumps({
        "text": text,
        "query": query,
        "goals": rows,
        "count": len(rows),
    }, default=str)


_V1_LEADERBOARD_METRICS = ("run_count", "forks", "outcome")
_GATE_EVENT_LEADERBOARD_METRICS = ("gate_events",)
_ALL_LEADERBOARD_METRICS = _V1_LEADERBOARD_METRICS + _GATE_EVENT_LEADERBOARD_METRICS


def _action_goal_leaderboard(kwargs: dict[str, Any]) -> str:
    from workflow.daemon_server import (
        get_goal,
        goal_leaderboard,
    )

    gid = (kwargs.get("goal_id") or "").strip()
    if not gid:
        return json.dumps({
            "status": "rejected",
            "error": "goal_id is required.",
        })
    metric = (kwargs.get("metric") or "run_count").strip().lower()
    _ensure_author_server_db()
    try:
        goal = get_goal(_base_path(), goal_id=gid)
    except KeyError:
        return json.dumps({
            "status": "rejected",
            "error": f"Goal '{gid}' not found.",
        })

    if metric not in _ALL_LEADERBOARD_METRICS:
        return json.dumps({
            "status": "rejected",
            "error": f"Unknown metric '{metric}'.",
            "available_metrics": list(_ALL_LEADERBOARD_METRICS),
        })

    # gate_events metric: rank by attributed real-world gate events.
    if metric == "gate_events":
        from workflow.gate_events import leaderboard_by_gate_events
        window = (kwargs.get("window") or "all").strip().lower()
        limit = int(kwargs.get("limit", 20) or 20)
        try:
            lb = leaderboard_by_gate_events(
                _base_path(), goal_id=gid, window=window, limit=limit,
            )
        except ValueError as exc:
            return json.dumps({"status": "rejected", "error": str(exc)})
        lines = [
            f"**Gate-event leaderboard for Goal '{goal.get('name', gid)}'**"
            f" — window `{window}`",
            "",
        ]
        if lb["ranked"]:
            for rank, entry in enumerate(lb["ranked"], 1):
                lines.append(
                    f"{rank}. `{entry['branch_version_id']}` · "
                    f"gate events: {entry['gate_event_count']} "
                    f"({entry['verified_event_count']} verified) · "
                    f"score: {entry['score']:.1f} · "
                    f"latest: {entry['most_recent_event_date']}"
                )
        else:
            lines.append("_No gate events attributed to any workflow under this Goal._")
        return json.dumps({
            "text": "\n".join(lines),
            "goal_id": gid,
            "metric": metric,
            "window": lb["window"],
            "ranked": lb["ranked"],
            "total_events_in_window": lb["total_events_in_window"],
        }, default=str)

    # GATES_ENABLED gates the outcome metric. When the flag is off,
    # return a friendly flag-gated envelope rather than letting the
    # live leaderboard path run against an empty ladder (which would
    # confuse the UI into thinking the Goal simply has no claims).
    # Flag flips in 6.3 per spec.
    if metric == "outcome" and not _gates_enabled():
        return json.dumps({
            "text": (
                "**Leaderboard metric `outcome`** is gated by the "
                "`GATES_ENABLED` flag (Phase 6.2). Set "
                "`GATES_ENABLED=1` on the Workflow Server to opt in, "
                "or use `metric=run_count` / `metric=forks` today."
            ),
            "status": "gates_disabled",
            "goal_id": gid,
            "metric": metric,
            "entries": [],
        }, default=str)

    try:
        entries = goal_leaderboard(
            _base_path(), goal_id=gid, metric=metric,
            limit=int(kwargs.get("limit", 20) or 20),
            viewer=_current_actor(),
        )
    except ValueError as exc:
        return json.dumps({
            "status": "rejected",
            "error": str(exc),
            "available_metrics": list(_ALL_LEADERBOARD_METRICS),
        })

    lines = [
        f"**Leaderboard for Goal '{goal['name']}'**"
        f" — metric `{metric}`",
        "",
    ]
    if entries:
        for rank, entry in enumerate(entries, 1):
            value = entry.get("value", 0)
            if metric == "outcome":
                name = entry.get("branch_name") or entry.get("name", "")
                rung = entry.get("highest_rung_key", "")
                lines.append(
                    f"{rank}. **{name}** · rung `{rung}` "
                    f"(index {value}) · {entry.get('claimed_at', '')}"
                )
            else:
                lines.append(
                    f"{rank}. **{entry['name']}** · {entry['author']} · "
                    f"{metric}={value}"
                )
    elif metric == "outcome":
        lines.append(
            "_No gate claims yet. Define a ladder with "
            "`gates action=define_ladder` and have Branches submit "
            "`gates action=claim`._"
        )
    else:
        lines.append(
            "_No workflows bound to this Goal yet. Use "
            "`goals action=bind` with the workflow name and Goal name._"
        )

    return json.dumps({
        "text": "\n".join(lines),
        "goal_id": gid,
        "metric": metric,
        "entries": entries,
    }, default=str)


def _action_goal_common_nodes(kwargs: dict[str, Any]) -> str:
    from workflow.daemon_server import (
        get_goal,
        goal_common_nodes,
        goal_common_nodes_all,
    )

    _ensure_author_server_db()
    min_branches = int(kwargs.get("min_branches", 2) or 2)
    limit = int(kwargs.get("limit", 20) or 20)
    scope = (kwargs.get("scope") or "this_goal").strip().lower() or "this_goal"
    if scope not in ("this_goal", "all"):
        return json.dumps({
            "status": "rejected",
            "error": (
                f"scope='{scope}' is unknown. Use 'this_goal' (default) "
                "to limit to one Goal, or 'all' for cross-Goal "
                "aggregation."
            ),
        })

    if scope == "all":
        # Phase 6.2.2 — viewer-aware cross-Goal aggregation; private
        # Branches owned by other actors don't contribute.
        entries = goal_common_nodes_all(
            _base_path(),
            min_branches=min_branches,
            limit=limit,
            viewer=_current_actor(),
        )
        lines = [
            "**Common nodes across ALL Goals** "
            f"appearing in ≥{min_branches} workflows.",
            "",
        ]
        if entries:
            for e in entries[:12]:
                goal_tag = ""
                if e.get("goal_ids"):
                    gl = e["goal_ids"][:3]
                    goal_tag = (
                        f" · goals: {', '.join(gl)}"
                        + (" …" if len(e["goal_ids"]) > 3 else "")
                    )
                lines.append(
                    f"- `{e['node_id']}` · **{e['display_name']}** · "
                    f"used in {e['occurrence_count']} branches"
                    f"{goal_tag}"
                )
            if len(entries) > 12:
                lines.append(f"- … and {len(entries) - 12} more.")
            lines.append("")
            lines.append(
                "_Reuse an existing node via `node_ref={source, "
                "node_id}` in build_branch / add_node (#66)._"
            )
        else:
            lines.append(
                "_No node_ids repeat across Branches yet. Consider "
                "using the same node_id when nodes serve the same "
                "role so the reuse surface can discover them._"
            )
        return json.dumps({
            "text": "\n".join(lines),
            "scope": "all",
            "min_branches": min_branches,
            "entries": entries,
        }, default=str)

    gid = (kwargs.get("goal_id") or "").strip()
    if not gid:
        return json.dumps({
            "status": "rejected",
            "error": (
                "goal_id is required for scope='this_goal'. Pass "
                "scope='all' to skip the Goal filter."
            ),
        })
    try:
        goal = get_goal(_base_path(), goal_id=gid)
    except KeyError:
        return json.dumps({
            "status": "rejected",
            "error": f"Goal '{gid}' not found.",
        })

    # Phase 6.2.2 — viewer-aware aggregation; private Branches
    # owned by other actors don't contribute their node inventory.
    entries = goal_common_nodes(
        _base_path(), goal_id=gid,
        min_branches=min_branches,
        limit=limit,
        viewer=_current_actor(),
    )
    lines = [
        f"**Common nodes in Goal '{goal['name']}'** "
        f"appearing in ≥{min_branches} workflows.",
        "",
    ]
    if entries:
        for e in entries[:12]:
            lines.append(
                f"- `{e['node_id']}` · **{e['display_name']}** · "
                f"used in {e['occurrence_count']} branches "
                f"(first seen: `{e['first_seen_in']}`)"
            )
        if len(entries) > 12:
            lines.append(
                f"- … and {len(entries) - 12} more."
            )
    else:
        lines.append(
            "_No nodes repeated across Branches yet — each Branch "
            "uses its own node_ids. Consider renaming nodes to share "
            "identity when they serve the same role._"
        )
    return json.dumps({
        "text": "\n".join(lines),
        "goal_id": gid,
        "scope": "this_goal",
        "min_branches": min_branches,
        "entries": entries,
    }, default=str)


def _action_goal_set_canonical(kwargs: dict[str, Any]) -> str:
    from workflow.daemon_server import get_goal, set_canonical_branch

    gid = (kwargs.get("goal_id") or "").strip()
    if not gid:
        return json.dumps({"status": "rejected", "error": "goal_id is required."})
    branch_version_id = (kwargs.get("branch_version_id") or "").strip() or None
    _ensure_author_server_db()

    try:
        goal = get_goal(_base_path(), goal_id=gid)
    except KeyError:
        return json.dumps({"status": "rejected", "error": f"Goal '{gid}' not found."})

    # Authority: only Goal author or host may set canonical.
    actor = _current_actor()
    host_actor = os.environ.get("UNIVERSE_SERVER_HOST_USER", "host")
    if actor != goal["author"] and actor != host_actor:
        return json.dumps({
            "status": "rejected",
            "error": (
                "Only the Goal author or a host-level actor may set the canonical branch. "
                f"Goal author is '{goal['author']}'; request actor is '{actor}'."
            ),
        })

    try:
        updated = set_canonical_branch(
            _base_path(), goal_id=gid,
            branch_version_id=branch_version_id, set_by=actor,
        )
    except ValueError as exc:
        return json.dumps({"status": "rejected", "error": str(exc)})

    if branch_version_id:
        text = (
            f"Canonical branch for Goal '{goal['name']}' set to "
            f"`{branch_version_id}`. New users forking this Goal will "
            f"start from this version."
        )
    else:
        text = (
            f"Canonical branch for Goal '{goal['name']}' unset. "
            f"No starter branch is currently designated."
        )

    return json.dumps({
        "status": "ok",
        "text": text,
        "goal_id": gid,
        "canonical_branch_version_id": updated.get("canonical_branch_version_id"),
    }, default=str)


_GOAL_ACTIONS: dict[str, Any] = {
    "propose": _action_goal_propose,
    "update": _action_goal_update,
    "bind": _action_goal_bind,
    "list": _action_goal_list,
    "get": _action_goal_get,
    "search": _action_goal_search,
    "leaderboard": _action_goal_leaderboard,
    "common_nodes": _action_goal_common_nodes,
    "set_canonical": _action_goal_set_canonical,
}

_GOAL_WRITE_ACTIONS: frozenset[str] = frozenset({
    "propose", "update", "bind", "set_canonical",
})


def _dispatch_goal_action(
    action: str, handler: Any, kwargs: dict[str, Any],
) -> str:
    """Run a Goal action; ledger write actions for public attribution.

    Catches :class:`DirtyFileError` from cached-backend writes (per H2)
    and formats it as the structured ``local_edit_conflict`` payload so
    chat clients render actionable options rather than a raw traceback.
    """
    try:
        result_str = handler(kwargs)
    except DirtyFileError as exc:
        return json.dumps(_format_dirty_file_conflict(exc))
    if action not in _GOAL_WRITE_ACTIONS:
        return result_str
    try:
        result = json.loads(result_str)
    except (json.JSONDecodeError, TypeError):
        return result_str
    if not isinstance(result, dict):
        return result_str
    if result.get("error") or result.get("status") == "rejected":
        return result_str
    try:
        target = (
            result.get("goal", {}).get("goal_id")
            or result.get("goal_id")
            or kwargs.get("goal_id", "")
            or kwargs.get("branch_def_id", "")
        )
        summary_bits = [f"goals.{action}"]
        if kwargs.get("name"):
            summary_bits.append(kwargs["name"])
        if kwargs.get("goal_id"):
            summary_bits.append(f"goal={kwargs['goal_id']}")
        if kwargs.get("branch_def_id"):
            summary_bits.append(f"branch={kwargs['branch_def_id']}")
        _append_global_ledger(
            f"goals.{action}",
            target=str(target),
            summary=_truncate(" ".join(summary_bits)),
            payload=None,
        )
    except Exception as exc:
        logger.warning("Ledger write failed for goals.%s: %s", action, exc)
    return result_str


@mcp.tool(
    title="Goals",
    tags={"goals", "discovery", "intent", "community"},
    annotations=ToolAnnotations(
        title="Goals",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
def goals(
    action: str,
    goal_id: str = "",
    branch_def_id: str = "",
    branch_version_id: str = "",
    name: str = "",
    description: str = "",
    tags: str = "",
    visibility: str = "",
    query: str = "",
    metric: str = "",
    min_branches: int = 2,
    author: str = "",
    limit: int = 50,
    scope: str = "",
    force: bool = False,
) -> str:
    """Goals — first-class shared primitives above workflow Branches.

    A Goal captures the intent a workflow serves ("produce a research
    paper", "plan a wedding"). Many Branches bind to one Goal. Users
    discover existing Goals before building a new Branch so the
    "reuse vs invent" decision is tractable.

    Actions:
      propose      Create a new Goal. Needs `name`. Optional
                   description, tags (CSV), visibility (public/private).
      update       Patch a Goal you own. Fields: name, description,
                   tags, visibility. Non-owners cannot update — propose
                   a new Goal instead.
      bind         Attach a Branch to a Goal. Pass goal_id="" to
                   unbind. Needs branch_def_id.
      set_canonical Mark a branch_version_id as the Goal's canonical
                   (best-known) branch. Author-only or host-only.
                   Pass branch_version_id="" to unset.
      list         Browse Goals. Optional author, tags (CSV first
                   value only), limit. Soft-deleted Goals hidden.
      get          Full Goal view + bound Branches. Needs goal_id.
      search       LIKE-based substring search over name, description,
                   tags. Needs query.
      leaderboard  Rank bound Branches by metric. v1 supports
                   `run_count` and `forks`. `outcome` returns a Phase 6
                   stub today; the same call will surface real outcome
                   rankings once Phase 6 ships.
      common_nodes Nodes appearing in ≥`min_branches` Branches.
                   With `scope="this_goal"` (default), restricts to
                   one Goal's Branches. With `scope="all"`, aggregates
                   across every Goal and every unbound Branch — use
                   this when helping a user decide "is there already
                   a node that does X somewhere on this server?" even
                   if they haven't committed to a Goal yet.

    Args:
      action: see above.
      goal_id: Goal target for bind/get/update/search/leaderboard,
        and for common_nodes when scope='this_goal'.
      branch_def_id: Branch target for bind.
      branch_version_id: Published branch_version_id for set_canonical
        (pass empty string to unset). Must reference a row in
        `branch_versions` — only published versions may be canonical.
      name/description/tags/visibility: Goal fields for propose/update.
      query: search query.
      metric: leaderboard metric (run_count/forks/outcome).
      min_branches: common_nodes cutoff (default 2).
      scope: common_nodes aggregation. 'this_goal' (default) restricts
        to one Goal; 'all' aggregates cross-Goal.
      author: list filter.
      limit: cap on returned rows.
      force: override `local_edit_conflict` refusal on propose/update/bind
        when the target YAML has uncommitted local edits. Default False —
        the conflict surfaces as a structured response so the caller can
        commit / stash / discard first.
    """
    _ensure_author_server_db()
    goal_kwargs: dict[str, Any] = {
        "goal_id": goal_id,
        "branch_def_id": branch_def_id,
        "branch_version_id": branch_version_id,
        "name": name,
        "description": description,
        "tags": tags,
        "visibility": visibility,
        "query": query,
        "metric": metric,
        "min_branches": min_branches,
        "author": author,
        "limit": limit,
        "scope": scope,
        "force": force,
    }
    handler = _GOAL_ACTIONS.get(action)
    if handler is None:
        return json.dumps({
            "error": f"Unknown action '{action}'.",
            "available_actions": sorted(_GOAL_ACTIONS.keys()),
        })
    return _dispatch_goal_action(action, handler, goal_kwargs)


# ═══════════════════════════════════════════════════════════════════════════
# TOOL 3b — Outcome Gates (Phase 6.1)
# ═══════════════════════════════════════════════════════════════════════════
#
# Flag-gated by GATES_ENABLED=1. Phase 6.1 ships schema + three actions
# (define_ladder / get_ladder / claim) write-through SQLite only. Git
# commit integration + remaining actions (retract / list_claims /
# leaderboard) ship in 6.2 / 6.3.


def _gates_enabled() -> bool:
    import os
    return os.environ.get("GATES_ENABLED", "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _validate_evidence_url(url: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(url or "")
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return ""
    return (
        "evidence_url must be an http(s) URL with a host "
        "(e.g. https://example.com/path)."
    )


def _action_gates_define_ladder(kwargs: dict[str, Any]) -> str:
    from workflow.catalog.layout import slugify
    from workflow.daemon_server import get_goal
    from workflow.identity import git_author

    gid = (kwargs.get("goal_id") or "").strip()
    if not gid:
        return json.dumps({
            "status": "rejected",
            "error": "goal_id is required for define_ladder.",
        })
    ladder_raw = (kwargs.get("ladder") or "").strip()
    if not ladder_raw:
        return json.dumps({
            "status": "rejected",
            "error": "ladder JSON is required for define_ladder.",
        })
    try:
        ladder = json.loads(ladder_raw)
    except json.JSONDecodeError as exc:
        return json.dumps({
            "status": "rejected",
            "error": f"ladder must be a JSON list. {exc}",
        })
    if not isinstance(ladder, list):
        return json.dumps({
            "status": "rejected",
            "error": "ladder must be a JSON list of rung objects.",
        })
    seen: set[str] = set()
    for idx, rung in enumerate(ladder):
        if not isinstance(rung, dict):
            return json.dumps({
                "status": "rejected",
                "error": f"ladder[{idx}] must be an object.",
            })
        key = (rung.get("rung_key") or "").strip()
        if not key:
            return json.dumps({
                "status": "rejected",
                "error": f"ladder[{idx}].rung_key is required.",
            })
        if key in seen:
            return json.dumps({
                "status": "rejected",
                "error": f"duplicate rung_key '{key}' in ladder.",
            })
        seen.add(key)
    _ensure_author_server_db()
    try:
        goal = get_goal(_base_path(), goal_id=gid)
    except KeyError:
        return json.dumps({
            "status": "rejected",
            "error": f"Goal '{gid}' not found.",
        })
    actor = _current_actor_or_anon()
    if goal.get("author") and goal["author"] != actor and actor != "host":
        return json.dumps({
            "status": "rejected",
            "error": (
                "Only the Goal author can define its ladder. "
                f"Owner: {goal['author']}."
            ),
        })
    # Ride the ladder through `save_goal_and_commit` — spec §Migration
    # 5: ladder is a dict key on the goal, no backend protocol change
    # beyond the existing save_goal_and_commit. Commit namespace is
    # `goals.define_ladder` because the file written is
    # `goals/<slug>.yaml`, not `gates/...`.
    updated_goal = dict(goal)
    updated_goal["gate_ladder"] = ladder
    force = bool(kwargs.get("force", False))
    goal_slug = slugify(goal.get("name") or gid)
    try:
        saved, _commit = _storage_backend().save_goal_and_commit(
            updated_goal,
            author=git_author(_current_actor()),
            message=f"goals.define_ladder: {goal_slug}",
            force=force,
        )
    except CommitFailedError as exc:
        return json.dumps(_format_commit_failed(exc))
    return json.dumps({
        "status": "defined",
        "goal_id": gid,
        "gate_ladder": saved.get("gate_ladder", []),
    }, default=str)


def _action_gates_get_ladder(kwargs: dict[str, Any]) -> str:
    from workflow.daemon_server import get_goal_ladder

    gid = (kwargs.get("goal_id") or "").strip()
    if not gid:
        return json.dumps({
            "status": "rejected",
            "error": "goal_id is required for get_ladder.",
        })
    _ensure_author_server_db()
    try:
        ladder = get_goal_ladder(_base_path(), goal_id=gid)
    except KeyError:
        return json.dumps({
            "status": "rejected",
            "error": f"Goal '{gid}' not found.",
        })
    return json.dumps({
        "status": "ok",
        "goal_id": gid,
        "gate_ladder": ladder,
    }, default=str)


def _action_gates_claim(kwargs: dict[str, Any]) -> str:
    from workflow.catalog.layout import slugify
    from workflow.daemon_server import (
        get_branch_definition,
        get_gate_claim,
        get_goal,
        get_goal_ladder,
    )
    from workflow.identity import git_author

    bid = (kwargs.get("branch_def_id") or "").strip()
    rung_key = (kwargs.get("rung_key") or "").strip()
    evidence_url = (kwargs.get("evidence_url") or "").strip()
    force = bool(kwargs.get("force", False))
    if not (bid and rung_key and evidence_url):
        return json.dumps({
            "status": "rejected",
            "error": (
                "branch_def_id, rung_key, evidence_url are required."
            ),
        })
    url_err = _validate_evidence_url(evidence_url)
    if url_err:
        return json.dumps({"status": "rejected", "error": url_err})
    _ensure_author_server_db()
    try:
        branch = get_branch_definition(_base_path(), branch_def_id=bid)
    except KeyError:
        return json.dumps({
            "status": "rejected",
            "error": f"Branch '{bid}' not found.",
        })
    goal_id = branch.get("goal_id") or ""
    if not goal_id:
        return json.dumps({
            "status": "rejected",
            "error": (
                "Branch is not bound to a Goal. "
                "Bind it via `goals action=bind` before claiming."
            ),
        })
    try:
        goal = get_goal(_base_path(), goal_id=goal_id)
    except KeyError:
        return json.dumps({
            "status": "rejected",
            "error": f"Goal '{goal_id}' not found.",
        })
    # Rebind guard: if an ACTIVE (non-retracted) claim exists for
    # (branch, rung) under a different Goal, the Branch was rebound
    # between claims. Reject so the original Goal's leaderboard keeps
    # its history; caller must retract the stale claim before
    # re-claiming under the new Goal. Retracted prior claims are
    # resolved intent — re-claim reactivates under the new Goal.
    existing = get_gate_claim(
        _base_path(), branch_def_id=bid, rung_key=rung_key,
    )
    if (
        existing is not None
        and not existing.get("retracted_at")
        and (existing.get("goal_id") or "") != goal_id
    ):
        return json.dumps({
            "status": "rejected",
            "error": "branch_rebound",
            "original_goal_id": existing.get("goal_id") or "",
            "current_goal_id": goal_id,
            "hint": (
                "Retract the existing claim under the original Goal "
                "first, then re-claim under the new Goal."
            ),
        })
    ladder = get_goal_ladder(_base_path(), goal_id=goal_id)
    available = [r.get("rung_key") for r in ladder if r.get("rung_key")]
    if rung_key not in available:
        return json.dumps({
            "status": "rejected",
            "error": "unknown_rung",
            "available_rungs": available,
        })
    from workflow.daemon_server import BranchRebindError

    goal_slug = slugify(goal.get("name") or goal_id)
    branch_slug = slugify(branch.get("name") or bid)
    try:
        saved, _commit = _storage_backend().save_gate_claim_and_commit(
            branch_def_id=bid,
            goal_id=goal_id,
            rung_key=rung_key,
            evidence_url=evidence_url,
            evidence_note=kwargs.get("evidence_note", ""),
            claimed_by=_current_actor_or_anon(),
            goal_slug=goal_slug,
            branch_slug=branch_slug,
            author=git_author(_current_actor()),
            message=f"gates.claim: {goal_slug}/{branch_slug}@{rung_key}",
            force=force,
        )
    except BranchRebindError as exc:
        # Storage-layer guard fired — means another caller rebound the
        # Branch between this handler's pre-check and the storage
        # write. Surface the same envelope as the handler pre-check.
        return json.dumps({
            "status": "rejected",
            "error": "branch_rebound",
            "original_goal_id": exc.original_goal_id,
            "current_goal_id": exc.current_goal_id,
            "hint": (
                "Retract the existing claim under the original Goal "
                "first, then re-claim under the new Goal."
            ),
        })
    except CommitFailedError as exc:
        return json.dumps(_format_commit_failed(exc))
    return json.dumps({
        "status": "claimed",
        "claim": saved,
    }, default=str)


def _action_gates_retract(kwargs: dict[str, Any]) -> str:
    from workflow.catalog.layout import slugify
    from workflow.daemon_server import (
        get_branch_definition,
        get_gate_claim,
        get_goal,
    )
    from workflow.identity import git_author

    bid = (kwargs.get("branch_def_id") or "").strip()
    rung_key = (kwargs.get("rung_key") or "").strip()
    reason = (kwargs.get("reason") or "").strip()
    force = bool(kwargs.get("force", False))
    if not (bid and rung_key):
        return json.dumps({
            "status": "rejected",
            "error": "branch_def_id and rung_key are required for retract.",
        })
    if not reason:
        return json.dumps({
            "status": "rejected",
            "error": "reason is required for retract (non-empty).",
        })
    _ensure_author_server_db()
    existing = get_gate_claim(
        _base_path(), branch_def_id=bid, rung_key=rung_key,
    )
    if existing is None:
        return json.dumps({
            "status": "rejected",
            "error": "claim_not_found",
            "message": (
                f"No claim exists for branch '{bid}' at rung "
                f"'{rung_key}'."
            ),
        })
    if existing.get("retracted_at"):
        # Idempotent: a second retract on an already-retracted claim is
        # a no-op return, not a fresh write. Keeps owners from churning
        # retracted_at timestamps. No YAML rewrite either.
        return json.dumps({
            "status": "already_retracted",
            "claim": existing,
        }, default=str)
    actor = _current_actor_or_anon()
    # Owner-retract: original claimant, Goal author, or ambient host.
    claimed_by = existing.get("claimed_by") or ""
    goal_author = ""
    goal_id = existing.get("goal_id") or ""
    goal_name = ""
    if goal_id:
        try:
            goal = get_goal(_base_path(), goal_id=goal_id)
            goal_author = goal.get("author") or ""
            goal_name = goal.get("name") or ""
        except KeyError:
            pass
    allowed = {actor_id for actor_id in (claimed_by, goal_author) if actor_id}
    if actor not in allowed and actor != "host":
        return json.dumps({
            "status": "rejected",
            "error": (
                "Only the claim author or Goal owner can retract "
                f"(claimant: '{claimed_by}', goal owner: "
                f"'{goal_author}')."
            ),
        })
    # Verify branch still exists (defensive; claim-time check is in claim).
    try:
        branch = get_branch_definition(_base_path(), branch_def_id=bid)
    except KeyError:
        return json.dumps({
            "status": "rejected",
            "error": f"Branch '{bid}' not found.",
        })
    goal_slug = slugify(goal_name or goal_id)
    branch_slug = slugify(branch.get("name") or bid)
    try:
        saved, _commit = _storage_backend().retract_gate_claim_and_commit(
            branch_def_id=bid,
            rung_key=rung_key,
            reason=reason,
            goal_slug=goal_slug,
            branch_slug=branch_slug,
            author=git_author(_current_actor()),
            message=f"gates.retract: {goal_slug}/{branch_slug}@{rung_key}",
            force=force,
        )
    except CommitFailedError as exc:
        return json.dumps(_format_commit_failed(exc))
    return json.dumps({
        "status": "retracted",
        "claim": saved,
    }, default=str)


_LIST_CLAIMS_LIMIT_CAP = 500


def _action_gates_list_claims(kwargs: dict[str, Any]) -> str:
    from workflow.daemon_server import get_goal, list_gate_claims

    bid = (kwargs.get("branch_def_id") or "").strip()
    gid = (kwargs.get("goal_id") or "").strip()
    if bool(bid) == bool(gid):
        return json.dumps({
            "status": "rejected",
            "error": (
                "list_claims requires exactly one of branch_def_id "
                "or goal_id."
            ),
            "available_filters": ["branch_def_id", "goal_id"],
        })
    include_retracted = bool(kwargs.get("include_retracted", False))
    limit = int(kwargs.get("limit", 50) or 50)
    limit = max(1, min(limit, _LIST_CLAIMS_LIMIT_CAP))
    _ensure_author_server_db()
    # Unknown goal_id is a hard reject (caller asked about a specific
    # ID). Unknown branch_def_id falls through to an empty result set,
    # matching `branch list` ergonomics.
    if gid:
        try:
            get_goal(_base_path(), goal_id=gid)
        except KeyError:
            return json.dumps({
                "status": "rejected",
                "error": f"Goal '{gid}' not found.",
            })
    try:
        claims = list_gate_claims(
            _base_path(),
            branch_def_id=bid,
            goal_id=gid,
            include_retracted=include_retracted,
            limit=limit,
        )
    except ValueError as exc:
        return json.dumps({"status": "rejected", "error": str(exc)})
    # Phase 6.2.2 — hide private-Branch claims from non-owners.
    claims = _filter_claims_by_branch_visibility(
        claims, viewer=_current_actor(),
    )
    return json.dumps({
        "status": "ok",
        "filter": {
            "branch_def_id": bid,
            "goal_id": gid,
            "include_retracted": include_retracted,
        },
        "claims": claims,
        "count": len(claims),
    }, default=str)


def _action_gates_leaderboard(kwargs: dict[str, Any]) -> str:
    from workflow.daemon_server import (
        gates_leaderboard,
        get_goal,
        get_goal_ladder,
    )

    gid = (kwargs.get("goal_id") or "").strip()
    if not gid:
        return json.dumps({
            "status": "rejected",
            "error": "goal_id is required for leaderboard.",
        })
    _ensure_author_server_db()
    try:
        goal = get_goal(_base_path(), goal_id=gid)
    except KeyError:
        return json.dumps({
            "status": "rejected",
            "error": f"Goal '{gid}' not found.",
        })
    ladder = get_goal_ladder(_base_path(), goal_id=gid)
    if not ladder:
        return json.dumps({
            "status": "ok",
            "goal_id": gid,
            "goal_name": goal.get("name", ""),
            "entries": [],
            "count": 0,
            "note": "Goal has no ladder defined.",
        }, default=str)
    limit = int(kwargs.get("limit", 50) or 50)
    entries = gates_leaderboard(_base_path(), goal_id=gid, limit=limit)
    # Phase 6.2.2 — hide private-Branch entries from non-owners.
    entries = _filter_leaderboard_by_branch_visibility(
        entries, viewer=_current_actor(),
    )
    return json.dumps({
        "status": "ok",
        "goal_id": gid,
        "goal_name": goal.get("name", ""),
        "entries": entries,
        "count": len(entries),
    }, default=str)


def _action_gates_stake_bonus(kwargs: dict[str, Any]) -> str:
    """Lock a bonus stake on an existing gate claim.

    Requires: claim_id, bonus_stake (int), node_id.
    Rejected when WORKFLOW_PAID_MARKET is off, claim is retracted,
    or claim already has a bonus staked.
    """
    from workflow.gates.actions import stake_bonus, validate_stake_amount
    from workflow.producers.node_bid import paid_market_enabled

    if not paid_market_enabled():
        return json.dumps({
            "status": "not_available",
            "error": (
                "Gate bonuses require WORKFLOW_PAID_MARKET=on. "
                "Enable the paid-market flag to use bonus staking."
            ),
        })

    claim_id = (kwargs.get("claim_id") or "").strip()
    node_id = (kwargs.get("node_id") or "").strip()
    attachment_scope = (kwargs.get("attachment_scope") or "node").strip()
    raw_stake = kwargs.get("bonus_stake", 0)

    if not claim_id:
        return json.dumps({"status": "rejected", "error": "claim_id is required."})
    if not node_id:
        return json.dumps({"status": "rejected", "error": "node_id is required."})

    stake, err = validate_stake_amount(raw_stake)
    if err:
        return json.dumps({"status": "rejected", "error": err})
    if stake == 0:
        return json.dumps({
            "status": "rejected",
            "error": "bonus_stake must be > 0 to stake a bonus.",
        })

    _ensure_author_server_db()
    from workflow.storage import _connect as _storage_connect
    with _storage_connect(_base_path()) as conn:
        result = stake_bonus(
            conn,
            claim_id=claim_id,
            bonus_stake=stake,
            node_id=node_id,
            attachment_scope=attachment_scope,
        )
    return json.dumps(result, default=str)


def _action_gates_unstake_bonus(kwargs: dict[str, Any]) -> str:
    """Remove a bonus stake from a gate claim (refund to original staker).

    Requires: claim_id. Only the original staker can unstake.
    """
    from workflow.gates.actions import unstake_bonus
    from workflow.producers.node_bid import paid_market_enabled

    if not paid_market_enabled():
        return json.dumps({
            "status": "not_available",
            "error": "Gate bonuses require WORKFLOW_PAID_MARKET=on.",
        })

    claim_id = (kwargs.get("claim_id") or "").strip()
    if not claim_id:
        return json.dumps({"status": "rejected", "error": "claim_id is required."})

    actor = _current_actor_or_anon()
    _ensure_author_server_db()
    from workflow.storage import _connect as _storage_connect
    with _storage_connect(_base_path()) as conn:
        result = unstake_bonus(conn, claim_id=claim_id, actor=actor)
    return json.dumps(result, default=str)


def _action_gates_release_bonus(kwargs: dict[str, Any]) -> str:
    """Release or refund a bonus based on an evaluator verdict.

    Requires: claim_id, eval_verdict ("pass"|"fail"|"skip"),
    node_last_claimer (who gets the payout on pass).
    Rejected when no verdict supplied or bonus_stake is 0.
    """
    from workflow.gates.actions import release_bonus
    from workflow.producers.node_bid import paid_market_enabled

    if not paid_market_enabled():
        return json.dumps({
            "status": "not_available",
            "error": "Gate bonuses require WORKFLOW_PAID_MARKET=on.",
        })

    claim_id = (kwargs.get("claim_id") or "").strip()
    eval_verdict = (kwargs.get("eval_verdict") or "").strip()
    node_last_claimer = (kwargs.get("node_last_claimer") or "").strip()

    if not claim_id:
        return json.dumps({"status": "rejected", "error": "claim_id is required."})
    if not eval_verdict:
        return json.dumps({
            "status": "rejected",
            "error": (
                "eval_verdict is required ('pass', 'fail', or 'skip'). "
                "Use the Evaluator protocol to obtain a verdict before releasing."
            ),
        })
    if not node_last_claimer:
        return json.dumps({
            "status": "rejected",
            "error": (
                "node_last_claimer is required "
                "(the actor holding the node at gate-pass time)."
            ),
        })

    staker = _current_actor_or_anon()
    _ensure_author_server_db()
    from workflow.storage import _connect as _storage_connect
    with _storage_connect(_base_path()) as conn:
        result = release_bonus(
            conn,
            claim_id=claim_id,
            eval_verdict=eval_verdict,
            node_last_claimer=node_last_claimer,
            staker=staker,
        )
    return json.dumps(result, default=str)


def _action_attest_gate_event(kwargs: dict[str, Any]) -> str:
    from workflow.gate_events import attest_gate_event

    goal_id = (kwargs.get("goal_id") or "").strip()
    event_type = (kwargs.get("event_type") or "").strip()
    event_date = (kwargs.get("event_date") or "").strip()
    attested_by = (kwargs.get("attested_by") or _current_actor()).strip()
    notes = (kwargs.get("note") or "").strip()
    cites_raw = (kwargs.get("cites_json") or "[]").strip()
    try:
        cites = json.loads(cites_raw) if cites_raw else []
        if not isinstance(cites, list):
            return json.dumps({"error": "cites_json must be a JSON array."})
    except json.JSONDecodeError as exc:
        return json.dumps({"error": f"cites_json is not valid JSON: {exc}"})
    try:
        evt = attest_gate_event(
            _base_path(),
            goal_id=goal_id,
            event_type=event_type,
            event_date=event_date,
            attested_by=attested_by,
            cites=cites,
            notes=notes,
        )
    except (ValueError, KeyError) as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps({"status": "attested", "event_id": evt.event_id,
                       "goal_id": evt.goal_id, "event_type": evt.event_type,
                       "event_date": evt.event_date, "attested_by": evt.attested_by,
                       "verification_status": evt.verification_status,
                       "cite_count": len(evt.cites)})


def _action_verify_gate_event(kwargs: dict[str, Any]) -> str:
    from workflow.gate_events import verify_gate_event

    event_id = (kwargs.get("event_id") or "").strip()
    verifier_id = (kwargs.get("verifier_id") or _current_actor()).strip()
    if not event_id:
        return json.dumps({"error": "event_id is required."})
    try:
        evt = verify_gate_event(_base_path(), event_id=event_id, verifier_id=verifier_id)
    except (ValueError, KeyError) as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps({"status": "verified", "event_id": evt.event_id,
                       "verification_status": evt.verification_status,
                       "verified_by": evt.verified_by})


def _action_dispute_gate_event(kwargs: dict[str, Any]) -> str:
    from workflow.gate_events.store import dispute_gate_event

    event_id = (kwargs.get("event_id") or "").strip()
    disputed_by = (kwargs.get("disputed_by") or _current_actor()).strip()
    reason = (kwargs.get("reason") or "").strip()
    if not event_id:
        return json.dumps({"error": "event_id is required."})
    try:
        evt = dispute_gate_event(_base_path(), event_id=event_id,
                                 disputed_by=disputed_by, reason=reason)
    except (ValueError, KeyError) as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps({"status": "disputed", "event_id": evt.event_id,
                       "verification_status": evt.verification_status})


def _action_retract_gate_event(kwargs: dict[str, Any]) -> str:
    from workflow.gate_events.store import retract_gate_event

    event_id = (kwargs.get("event_id") or "").strip()
    retracted_by = (kwargs.get("retracted_by") or _current_actor()).strip()
    note = (kwargs.get("note") or "").strip()
    if not event_id:
        return json.dumps({"error": "event_id is required."})
    try:
        evt = retract_gate_event(_base_path(), event_id=event_id,
                                 retracted_by=retracted_by, note=note)
    except (ValueError, KeyError) as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps({"status": "retracted", "event_id": evt.event_id,
                       "verification_status": evt.verification_status})


def _action_get_gate_event(kwargs: dict[str, Any]) -> str:
    from workflow.gate_events.store import get_gate_event

    event_id = (kwargs.get("event_id") or "").strip()
    if not event_id:
        return json.dumps({"error": "event_id is required."})
    evt = get_gate_event(_base_path(), event_id)
    if evt is None:
        return json.dumps({"error": f"event_id '{event_id}' not found."})
    return json.dumps({
        "event_id": evt.event_id,
        "goal_id": evt.goal_id,
        "event_type": evt.event_type,
        "event_date": evt.event_date,
        "attested_by": evt.attested_by,
        "attested_at": evt.attested_at,
        "verification_status": evt.verification_status,
        "verified_by": evt.verified_by,
        "notes": evt.notes,
        "cites": [
            {"branch_version_id": c.branch_version_id, "run_id": c.run_id,
             "contribution_summary": c.contribution_summary}
            for c in evt.cites
        ],
    }, default=str)


def _action_list_gate_events(kwargs: dict[str, Any]) -> str:
    from workflow.gate_events.store import list_gate_events

    goal_id = (kwargs.get("goal_id") or "").strip()
    bvid = (kwargs.get("branch_version_id") or "").strip()
    limit = min(max(1, int(kwargs.get("limit") or 50)), 500)
    include_retracted = bool(kwargs.get("include_retracted", True))
    events = list_gate_events(
        _base_path(),
        goal_id=goal_id,
        branch_version_id=bvid,
        include_retracted=include_retracted,
        limit=limit,
    )
    return json.dumps({
        "goal_id": goal_id,
        "count": len(events),
        "events": [
            {"event_id": e.event_id, "event_type": e.event_type,
             "event_date": e.event_date, "attested_by": e.attested_by,
             "verification_status": e.verification_status,
             "cite_count": len(e.cites)}
            for e in events
        ],
    }, default=str)


_GATE_EVENT_ACTIONS: dict[str, Any] = {
    "attest_gate_event": _action_attest_gate_event,
    "verify_gate_event": _action_verify_gate_event,
    "dispute_gate_event": _action_dispute_gate_event,
    "retract_gate_event": _action_retract_gate_event,
    "get_gate_event": _action_get_gate_event,
    "list_gate_events": _action_list_gate_events,
}


_GATES_ACTIONS: dict[str, Any] = {
    "define_ladder": _action_gates_define_ladder,
    "get_ladder": _action_gates_get_ladder,
    "claim": _action_gates_claim,
    "retract": _action_gates_retract,
    "list_claims": _action_gates_list_claims,
    "leaderboard": _action_gates_leaderboard,
    "stake_bonus": _action_gates_stake_bonus,
    "unstake_bonus": _action_gates_unstake_bonus,
    "release_bonus": _action_gates_release_bonus,
}


@mcp.tool(
    title="Outcome Gates",
    tags={"gates", "outcomes", "impact", "leaderboard", "community"},
    annotations=ToolAnnotations(
        title="Outcome Gates",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
def gates(
    action: str,
    goal_id: str = "",
    branch_def_id: str = "",
    rung_key: str = "",
    ladder: str = "",
    evidence_url: str = "",
    evidence_note: str = "",
    reason: str = "",
    include_retracted: bool = False,
    limit: int = 50,
    force: bool = False,
    claim_id: str = "",
    bonus_stake: int = 0,
    attachment_scope: str = "node",
    eval_verdict: str = "",
    node_last_claimer: str = "",
    node_id: str = "",
) -> str:
    """Outcome Gates — real-world impact claims per Branch.

    Each Goal declares a ladder of rungs (draft → peer-reviewed → published
    → cited → breakthrough). Branches self-report which rungs they've
    reached, with an evidence URL.

    All actions require GATES_ENABLED=1 on the server; the tool returns
    {"status": "not_available"} when the flag is off. Bonus actions
    additionally require WORKFLOW_PAID_MARKET=on.

    Actions (all live when GATES_ENABLED=1):
      define_ladder Owner sets the rung list on a Goal. Needs goal_id
                    and `ladder` (JSON list of {rung_key, name,
                    description}).
      get_ladder    Read a Goal's ladder. Needs goal_id.
      claim         Report a rung reached. Needs branch_def_id,
                    rung_key, evidence_url. Idempotent on (branch, rung).
      retract       Soft-delete a claim. Needs branch_def_id, rung_key,
                    reason. Claim author, Goal owner, or host can
                    retract.
      list_claims   Browse claims. Provide exactly one of branch_def_id
                    or goal_id. `include_retracted` optional; claims
                    whose rung no longer exists in the Goal's ladder
                    are tagged `orphaned`.
      leaderboard   Rank Branches bound to a Goal by highest rung
                    reached. Tiebreak: earliest claim wins. Also
                    callable as `goals leaderboard metric=outcome`.

    Bonus actions (live when GATES_ENABLED=1 + WORKFLOW_PAID_MARKET=on):
      stake_bonus   Lock a bonus stake on a claim. Needs claim_id,
                    bonus_stake (int > 0), node_id. attachment_scope
                    controls what the stake attaches to ("node" default).
      unstake_bonus Remove a bonus stake and refund the staker. Needs
                    claim_id. Only the original staker can unstake.
      release_bonus Resolve a bonus payout via evaluator verdict. Needs
                    claim_id, eval_verdict ("pass"|"fail"|"skip"),
                    node_last_claimer (recipient on pass).

    Evidence URL must be http(s) with a host; content is not fetched
    (local-first). Social accountability handles fraud in v1.

    Args:
      action: see Actions above.
      goal_id: Goal target for ladder / leaderboard / list_claims.
      branch_def_id: Branch that's claiming / retracting / listing.
      rung_key: matches a ladder entry's rung_key.
      ladder: JSON list string for define_ladder.
      evidence_url: http(s) URL pointing at the claim's evidence.
      evidence_note: optional human summary.
      reason: retract reason (required for retract, non-empty).
      include_retracted: list_claims filter (default False).
      limit: cap for leaderboard / list_claims.
      force: bypass the dirty-file guard on the target YAML when a
             user has uncommitted local edits. Same ergonomics as
             `goals propose/update/bind` and `branch` mutations.
      claim_id: target claim for stake_bonus / unstake_bonus /
                release_bonus.
      bonus_stake: integer token amount for stake_bonus (must be > 0).
                   Harmless when WORKFLOW_PAID_MARKET is off — the
                   action returns not_available before reading this arg.
      attachment_scope: what the stake attaches to; "node" (default)
                        or "branch". Used by stake_bonus.
      eval_verdict: evaluator decision for release_bonus —
                    "pass" (payout to node_last_claimer), "fail"
                    (refund to staker), or "skip" (no-op).
      node_last_claimer: actor_id of the node fulfiller who receives
                         payout on a "pass" release_bonus verdict.
      node_id: node target for stake_bonus.
    """
    if not _gates_enabled():
        return json.dumps({
            "status": "not_available",
            "error": (
                "Outcome gates are gated by the GATES_ENABLED flag "
                "(Phase 6.1). Set GATES_ENABLED=1 on the Workflow Server "
                "to opt in."
            ),
        })
    handler = _GATES_ACTIONS.get(action)
    if handler is None:
        return json.dumps({
            "status": "rejected",
            "error": f"Unknown action '{action}'.",
            "available_actions": sorted(_GATES_ACTIONS.keys()),
        })
    kwargs: dict[str, Any] = {
        "goal_id": goal_id,
        "branch_def_id": branch_def_id,
        "rung_key": rung_key,
        "ladder": ladder,
        "evidence_url": evidence_url,
        "evidence_note": evidence_note,
        "reason": reason,
        "include_retracted": include_retracted,
        "limit": limit,
        "force": force,
        "claim_id": claim_id,
        "bonus_stake": bonus_stake,
        "attachment_scope": attachment_scope,
        "eval_verdict": eval_verdict,
        "node_last_claimer": node_last_claimer,
        "node_id": node_id,
    }
    try:
        return handler(kwargs)
    except DirtyFileError as exc:
        # Phase 6.3: dirty-file guard surfaces as the structured
        # local_edit_conflict payload (same shape as `goals` and
        # `branch` handlers). Chat-side renders the options;
        # force=True retries through.
        return json.dumps(_format_dirty_file_conflict(exc))


# ══════════════════════════════════════════════════════════════════════
# TOOL 4 — Wiki (global knowledge base)
# ══════════════════════════════════════════════════════════════════════
#
# The wiki action handlers, helpers, and constants live in
# ``workflow/api/wiki.py`` (extracted 2026-04-26 — Task #9, decomp Step 2).
# The @mcp.tool registration stays here so FastMCP introspection sees the
# chatbot-facing signature + docstring exactly as before, and the back-compat
# re-export block keeps the historical
# ``from workflow.universe_server import _wiki_*`` test imports working.
# See ``docs/exec-plans/active/2026-04-26-decomp-step-2-prep.md`` (Pattern A2).

# Back-compat re-exports — the names below are imported here so historical
# `from workflow.universe_server import _<symbol>` paths in tests + design
# notes keep working after the wiki body relocation. The two `_page_rel_path`
# and `_parse_frontmatter` names are also live-used by `_related_wiki_pages`
# (~L5050 in this module). See the F401 noqas — they document each name as
# an intentional re-export rather than an unused import.
from workflow.api.wiki import (  # noqa: E402
    _WIKI_CATEGORIES,  # noqa: F401  (re-export: tests/test_wiki_scaffold.py, tests/test_wiki_file_bug.py, tests/test_wiki_tools.py)
    _add_to_index,  # noqa: F401  (re-export)
    _append_wiki_log,  # noqa: F401  (re-export)
    _bug_token_set,  # noqa: F401  (re-export: tests/test_wiki_file_bug_dedup.py)
    _ensure_wiki_scaffold,  # noqa: F401  (re-export: tests/test_wiki_scaffold.py, tests/test_wiki_cosign_flow.py, tests/test_wiki_file_bug_dedup.py)
    _extract_keywords,  # noqa: F401  (re-export: tests/test_wiki_tools.py)
    _jaccard,  # noqa: F401  (re-export: tests/test_wiki_file_bug_dedup.py)
    _next_bug_id,  # noqa: F401  (re-export: tests/test_wiki_file_bug.py)
    _next_id,  # noqa: F401  (re-export)
    _page_rel_path,  # used by _related_wiki_pages above
    _parse_frontmatter,  # used by _related_wiki_pages above + tests/test_wiki_tools.py
    _render_bug_markdown,  # noqa: F401  (re-export: tests/test_wiki_file_bug.py)
    _resolve_page,  # noqa: F401  (re-export)
    _sanitize_slug,  # noqa: F401  (re-export: tests/test_wiki_tools.py)
    _scan_existing_bugs,  # noqa: F401  (re-export)
    _slugify_title,  # noqa: F401  (re-export: tests/test_wiki_file_bug.py)
    _wiki_cosign_bug,  # noqa: F401  (re-export)
    _wiki_file_bug,  # noqa: F401  (re-export: tests/test_wiki_file_bug.py, docs/design-notes/2026-04-25-canary-to-patch-request-spec.md)
    _wiki_similarity_score,  # noqa: F401  (re-export: tests/test_wiki_tools.py)
)
from workflow.api.wiki import wiki as _wiki_impl  # noqa: E402


@mcp.tool(
    title="Wiki Knowledge Base",
    tags={"wiki", "knowledge", "drafts", "pages", "research"},
    annotations=ToolAnnotations(
        title="Wiki Knowledge Base",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
def wiki(
    action: str,
    page: str = "",
    query: str = "",
    category: str = "",
    filename: str = "",
    content: str = "",
    log_entry: str = "",
    source_url: str = "",
    old_page: str = "",
    new_draft: str = "",
    reason: str = "",
    similarity_threshold: float = 0.25,
    dry_run: bool = True,
    skip_lint: bool = False,
    max_results: int = 10,
    component: str = "",
    severity: str = "",
    title: str = "",
    repro: str = "",
    observed: str = "",
    expected: str = "",
    workaround: str = "",
    force_new: bool = False,
    bug_id: str = "",
    reporter_context: str = "",
) -> str:
    """Read, write, and manage the cross-project knowledge wiki.

    Persistent prose knowledge shared across sessions: how-tos,
    definitions, research notes, references, recipes, plans. New
    content lands in drafts/ and is promoted to pages/ after quality
    checks. Not a "save anything" sink — NOT for workflow structure,
    node definitions, state, or run outputs (those route to
    `extensions` or the universe surfaces). Intent routing: use
    `extensions` for "build / design / create a workflow" or
    "track recipes / tasks / guests"; use wiki for "save this
    how-to / ref / note" or "what is X". Start with `action="list"`
    or `action="read" page="index"`.

    Args:
        action: One of — reads: read, search, list, lint; writes:
            write, consolidate, promote, ingest, supersede,
            sync_projects (no args; scans sibling project directories
            and creates stub pages/projects/*.md entries for any that
            lack one — safe to run at any time), file_bug, cosign_bug
            (add your context to an existing bug — use when file_bug
            returns status="similar_found"; requires bug_id +
            reporter_context; returns the updated bug page with your
            context appended and the cosign_count incremented).
        page: Page name for read (also: index, log, schema).
        query: Search keywords for search.
        category: write / promote category — projects, concepts,
            people, research, recipes, workflows, notes, references,
            plans, bugs. Match the CONTENT; `research` is reserved
            for LLM-generated research pages and paper drafts. `bugs`
            is for `action=file_bug` only — prefer the dedicated verb
            so the server assigns the BUG-NNN id.
        filename: Filename for write / promote / ingest / supersede.
        content: Page or source body for write / ingest.
        log_entry: Optional log message for write.
        source_url: Optional URL for ingest.
        old_page: Page to supersede.
        new_draft: Replacement draft for supersede.
        reason: Why the old page is being superseded.
        similarity_threshold: Merge threshold for consolidate
            (0-1, default 0.25).
        dry_run: Consolidate reports only when true (default true).
        skip_lint: Promote skips quality checks when true.
        max_results: Max search results (default 10).
        component: file_bug — surface where the defect lives (e.g.
            "extensions.patch_branch", "universe.inspect", "tray").
        severity: file_bug — one of critical | major | minor |
            cosmetic. critical=data loss/outage; major=tool unusable;
            minor=non-blocking workaround exists; cosmetic=wording.
        title: file_bug — one-line title (bug) or description (feature/design).
        repro: file_bug — minimal tool call or steps to reproduce (bugs).
        observed: file_bug — what the tool actually returned/did (bugs).
        expected: file_bug — what it should have returned/done, or desired
            behavior for feature requests.
        workaround: file_bug — optional workaround applied (bugs).
        kind: file_bug — classification: "bug" (default) | "feature" |
            "design". All three use the same channel; navigator vets all.
            "feature" = new capability ask; "design" = design proposal or
            primitive ask. Use ``tags`` to add free-form labels.
        tags: file_bug — optional comma-separated free-form labels
            (e.g. "ux,performance"). Added to the frontmatter tags list
            alongside the auto-generated component tag and kind tag.
        force_new: file_bug — skip the similarity check and always mint a
            new id. Use when the symptom is materially different from any
            suggested similar bug.
        bug_id: cosign_bug — id of the bug to cosign (e.g. "BUG-042").
        reporter_context: cosign_bug — free-form context from the reporter
            (what they observed, their environment, etc.).

    Design-participation note: ``file_bug`` is the single verb for bugs,
    feature requests, design proposals, and primitive asks. Navigator vets
    all filings before dev implements — kind tagging is how the pipeline
    distinguishes them without separate verbs.

    Maintenance-ops note: ``promote`` (drafts → pages, runs the lint gate
    unless ``skip_lint=true``) and ``consolidate`` (merge similar drafts
    above a similarity threshold) are housekeeping verbs typically run by
    the host or a curator, not casually invoked from a chat turn. From a
    chatbot, prefer ``write`` (drafts new content) plus ``lint`` (quality
    check) and let curators handle promotion and merging.
    """
    return _wiki_impl(
        action=action,
        page=page,
        query=query,
        category=category,
        filename=filename,
        content=content,
        log_entry=log_entry,
        source_url=source_url,
        old_page=old_page,
        new_draft=new_draft,
        reason=reason,
        similarity_threshold=similarity_threshold,
        dry_run=dry_run,
        skip_lint=skip_lint,
        max_results=max_results,
        component=component,
        severity=severity,
        title=title,
        repro=repro,
        observed=observed,
        expected=expected,
        workaround=workaround,
        force_new=force_new,
        bug_id=bug_id,
        reporter_context=reporter_context,
    )


# ══════════════════════════════════════════════════════════════════════
# TOOL 5 — get_status (routing-evidence primitive for tier-2 trust)
# ══════════════════════════════════════════════════════════════════════
#
# The get_status body and _policy_hash helper live in
# ``workflow/api/status.py`` (extracted 2026-04-26 — Task #10, decomp Step 3).
# Same Pattern A2 as Task #9: the @mcp.tool registration stays here so
# FastMCP introspection sees the chatbot-facing signature + docstring exactly
# as before, and ``get_status`` is re-exported below for back-compat with
# existing test imports (`from workflow.universe_server import get_status`
# across 8 test files). See
# ``docs/exec-plans/active/2026-04-26-decomp-step-3-prep.md``.
#
# Original design rationale, preserved verbatim:
#
# Interim MCP primitive introduced 2026-04-19 (task #88) per navigator's
# Devin-session1 intelligence report §T-7. Devin bounced at live exchange 4
# because his chatbot had no tool-surface primitive to VERIFY the
# confidential-tier routing promise — without concrete evidence it correctly
# refused to guess from parameter names on a privacy-critical decision.
#
# This tool is a factual read-only surface that reports:
#   - current active-host identity
#   - the daemon's served LLM type (the closest legacy-surface analogue of
#     a routing-constraint commitment)
#   - a deterministic policy hash for drift detection across runs
#   - recent-activity evidence drawn from the public activity.log
#
# The legacy universe_server surface predates spec #79's tier-routing
# enforcement schema; this primitive returns what IS factual today and
# narrates what's NOT yet enforced so the chatbot can make honest claims
# instead of inferred ones. Full tray observability + per-universe
# sensitivity_tier enforcement lives in the rewrite (spec #79 §13).

from workflow.api.status import _policy_hash  # noqa: E402, F401  (back-compat re-export)
from workflow.api.status import get_status as _get_status_impl  # noqa: E402


@mcp.tool(
    title="Daemon Status + Routing Evidence",
    tags={
        "status", "routing", "privacy", "verification",
        "confidential-tier", "workflow",
    },
    annotations=ToolAnnotations(
        title="Daemon Status + Routing Evidence",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def get_status(universe_id: str = "") -> str:
    """Factual snapshot of the daemon's identity + routing config.

    Chatbots call this whenever they need ground-truth daemon facts,
    not just for privacy questions. Triggering questions include:
      - Privacy / routing: "will my manuscript go to a cloud LLM?",
        "which model is this bound to?", "is anything leaving my box?".
      - Liveness / orientation: "is the daemon running?", "what's the
        active universe?", "which provider is currently bound?".
      - Audit / proof: "show me the routing evidence" or anything where
        the chatbot needs to back a claim with a tool fact instead of
        relying on memory or the prompt.
    Returns concrete evidence the chatbot can narrate; does not infer
    or guess.

    **Versioned contract (schema_version=1):** All fields below are
    stable. Field removals and renames require a deprecation notice in
    the response for one release before removal. New fields may be added
    freely; they do not bump schema_version. Breaking changes (removal,
    rename, type change) MUST bump schema_version and update this
    docstring + the contract test in tests/test_get_status_primitive.py.

    Shape (§10.7 self-auditing-tools canonical):
        {
          "schema_version": int,
          "active_host": {host_id, served_llm_type, llm_endpoint_bound},
          "tier_routing_policy": {served_llm_type, accept_*, bid_*, ...},
          "evidence": {last_completed_request_llm_used,
                       activity_log_tail, last_n_calls,
                       activity_log_line_count, policy_hash},
          "evidence_caveats": {<evidence_key>: [caveat, ...]},
          "caveats": [global_caveat, ...],
          "actionable_next_steps": [...],
          "session_boundary": {
              prior_session_context_available: bool,
              account_user: str,
              last_session_ts: str | null,
              note: str,
          },
          "storage_utilization": {...},
          "per_provider_cooldown_remaining": {<provider>: seconds_int, ...},
          "universe_id": str,
          "universe_exists": bool,
        }

    `caveats` is load-bearing — the legacy surface does NOT yet enforce
    per-universe sensitivity_tier (that lives in spec #79 §13, post-
    rewrite). The chatbot MUST read + narrate caveats so trust claims
    match reality. Per-field caveats let the chatbot cite only the
    evidence keys that are degenerate, instead of wrapping every claim
    in the global caveat list.

    `last_n_calls` is a structured view of the most recent activity
    entries (parsed `{ts, tag, message, raw}` dicts, most-recent first).
    Derived from the same activity.log tail as `activity_log_tail`. When
    the parser cannot recover a tag for an entry, that key surfaces in
    `evidence_caveats` so chatbots know tag-based filtering on those
    entries is unreliable.

    `session_boundary` gives the chatbot a tool fact for cross-session
    identity grounding. `prior_session_context_available=false` means
    the activity log has no entries from the current account in the last
    30 days — the chatbot can cite this instead of relying purely on
    the prompt-level cross-session behavioral directive.

    Args:
        universe_id: Optional universe scope. Defaults to active universe.
    """
    return _get_status_impl(universe_id=universe_id)



# ═══════════════════════════════════════════════════════════════════════════
# Server Entry Point
# ═══════════════════════════════════════════════════════════════════════════


def main(
    host: str = "0.0.0.0",
    port: int = 8001,
    transport: str = "streamable-http",
) -> None:
    """Run the Workflow Server as a remote MCP server.

    Args:
        host: Bind address (default all interfaces).
        port: Port number (default 8001).
        transport: MCP transport protocol. "streamable-http" for remote
            connections (default), "sse" for legacy, "stdio" for local.
    """
    logger.info(
        "Starting Workflow Server on %s:%d (transport=%s)",
        host, port, transport,
    )

    if transport == "streamable-http":
        mcp.run(transport="streamable-http", host=host, port=port)
    elif transport == "sse":
        mcp.run(transport="sse", host=host, port=port)
    elif transport == "stdio":
        mcp.run()
    else:
        raise ValueError(f"Unknown transport: {transport}")


if __name__ == "__main__":
    main()
