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
# ───────────────────────────────────────────────────────────────────────────
# Phase-1 evaluation extraction (Task #12 — decomp Step 5) — back-compat
# re-exports. Phase-4 judgment loop (7 handlers) + branch-versioning metadata
# (3 handlers) + dispatch tables live in ``workflow.api.evaluation`` (~880
# LOC moved out). Re-exported here so ``extensions()`` body's
# ``_JUDGMENT_ACTIONS.get(action)`` and ``_BRANCH_VERSION_ACTIONS.get(action)``
# dispatch reads continue to work, and any direct test imports keep resolving.
# ───────────────────────────────────────────────────────────────────────────
from workflow.api.evaluation import (  # noqa: E402, F401  — back-compat re-exports
    _BRANCH_VERSION_ACTIONS,
    _JUDGMENT_ACTIONS,
    _JUDGMENT_WRITE_ACTIONS,
    _action_compare_runs,
    _action_get_branch_version,
    _action_get_node_output,
    _action_judge_run,
    _action_list_branch_versions,
    _action_list_judgments,
    _action_list_node_versions,
    _action_publish_version,
    _action_rollback_node,
    _action_suggest_node_edit,
    _dispatch_judgment_action,
    _split_tag_csv,
)
from workflow.api.helpers import (  # noqa: E402
    _base_path,
    _default_universe,
    _find_all_pages,  # noqa: F401  (back-compat re-export; live use moved with branches Step 8)
    _read_json,
    _read_text,
    _universe_dir,
    _wiki_drafts_dir,  # noqa: F401  (back-compat re-export; live use moved with branches Step 8)
    _wiki_pages_dir,  # noqa: F401  (back-compat re-export; live use moved with branches Step 8)
    _wiki_root,  # noqa: F401  (back-compat re-export for tests/test_wiki_path_resolver.py)
)

# ───────────────────────────────────────────────────────────────────────────
# Phase-1 market extraction (Task #14 — decomp Step 7) — back-compat
# re-exports. Paid-market economy primitives — escrow, outcomes, attribution,
# goals, gates — live in ``workflow.api.market`` (~2,287 LOC moved out).
# Re-exported here so ``extensions()`` body's 3 dispatch reads (escrow,
# outcomes, attribution) continue to work + tests/scripts importing handlers
# directly via ``workflow.universe_server`` keep resolving.
# The two MCP tool wrappers (``goals()`` + ``gates()``) preserved below for
# FastMCP introspection — Pattern A2 (delegates to market.py callables).
# ───────────────────────────────────────────────────────────────────────────
from workflow.api.market import (  # noqa: E402, F401  — back-compat re-exports
    _ATTRIBUTION_ACTIONS,
    _ESCROW_ACTIONS,
    _GATE_EVENT_ACTIONS,
    _GATES_ACTIONS,
    _GOAL_ACTIONS,
    _GOAL_WRITE_ACTIONS,
    _OUTCOME_ACTIONS,
    _action_attest_gate_event,
    _action_dispute_gate_event,
    _action_escrow_inspect,
    _action_escrow_lock,
    _action_escrow_refund,
    _action_escrow_release,
    _action_gates_claim,
    _action_gates_define_ladder,
    _action_gates_get_ladder,
    _action_gates_leaderboard,
    _action_gates_list_claims,
    _action_gates_release_bonus,
    _action_gates_retract,
    _action_gates_stake_bonus,
    _action_gates_unstake_bonus,
    _action_get_gate_event,
    _action_get_outcome,
    _action_get_provenance,
    _action_goal_bind,
    _action_goal_common_nodes,
    _action_goal_get,
    _action_goal_leaderboard,
    _action_goal_list,
    _action_goal_propose,
    _action_goal_search,
    _action_goal_set_canonical,
    _action_goal_update,
    _action_list_gate_events,
    _action_list_outcomes,
    _action_record_outcome,
    _action_record_remix,
    _action_retract_gate_event,
    _action_verify_gate_event,
    _current_actor_or_anon,
    _dispatch_goal_action,
    _gates_enabled,
)
from workflow.api.market import gates as _gates_impl  # noqa: E402
from workflow.api.market import goals as _goals_impl  # noqa: E402

# ───────────────────────────────────────────────────────────────────────────
# Phase-1 runs extraction (Task #11 — decomp Step 4) — back-compat re-exports.
# 15 run-action handlers + dispatcher + failure-classification helpers live
# in ``workflow.api.runs`` (~1,460 LOC moved out). Re-exported here so test
# files + ``extensions()`` body can keep importing
# ``from workflow.universe_server import _RUN_ACTIONS, _action_*, ...``.
# ───────────────────────────────────────────────────────────────────────────
from workflow.api.runs import (  # noqa: E402, F401  — back-compat re-exports
    _FAILURE_TAXONOMY,
    _RUN_ACTIONS,
    _RUN_WRITE_ACTIONS,
    _action_cancel_run,
    _action_estimate_run_cost,
    _action_get_memory_scope_status,
    _action_get_rollback_history,
    _action_get_run,
    _action_get_run_output,
    _action_list_runs,
    _action_query_runs,
    _action_resume_run,
    _action_rollback_merge,
    _action_run_branch,
    _action_run_branch_version,
    _action_run_routing_evidence,
    _action_stream_run,
    _action_wait_for_run,
    _actionable_by,
    _branch_name_for_run,
    _build_failure_taxonomy,
    _classify_run_error,
    _classify_run_outcome_error,
    _compose_run_snapshot,
    _dispatch_run_action,
    _ensure_runs_recovery,
    _failure_payload,
    _run_mermaid_from_events,
)

# ───────────────────────────────────────────────────────────────────────────
# Phase-1 runtime_ops extraction (Task #13 — decomp Step 6) — back-compat
# re-exports. Project memory + dry-inspect + teammate messaging + scheduler
# (16 handlers, 4 dispatch tables) live in ``workflow.api.runtime_ops``
# (~564 LOC moved out). Re-exported here so ``extensions()`` body's
# 4 dispatch reads + ledger-write check on _PROJECT_MEMORY_WRITE_ACTIONS
# continue to work; ~26 direct test imports across test_dry_inspect_node
# and test_project_memory keep resolving.
# ───────────────────────────────────────────────────────────────────────────
from workflow.api.runtime_ops import (  # noqa: E402, F401  — back-compat re-exports
    _INSPECT_DRY_ACTIONS,
    _MESSAGING_ACTIONS,
    _PROJECT_MEMORY_ACTIONS,
    _PROJECT_MEMORY_WRITE_ACTIONS,
    _SCHEDULER_ACTIONS,
    _action_dry_inspect_node,
    _action_dry_inspect_patch,
    _action_list_scheduler_subscriptions,
    _action_list_schedules,
    _action_messaging_ack,
    _action_messaging_receive,
    _action_messaging_send,
    _action_pause_schedule,
    _action_project_memory_get,
    _action_project_memory_list,
    _action_project_memory_set,
    _action_schedule_branch,
    _action_subscribe_branch,
    _action_unpause_schedule,
    _action_unschedule_branch,
    _action_unsubscribe_branch,
    _apply_patch_ops,
    _load_branch_for_inspect,
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
# Phase 2 branch authoring + node CRUD (Task #15 — decomp Step 8) —
# back-compat re-exports. The 17 ``_ext_branch_*`` handlers, build/patch
# composite engine, ``_action_continue_branch`` / ``_action_fork_tree``,
# the node-spec resolver + apply machinery, ``_related_wiki_pages``, the
# mermaid renderer, and the ``_BRANCH_ACTIONS`` / ``_BRANCH_WRITE_ACTIONS``
# dispatch surface live in ``workflow.api.branches``. Re-exported here so
# test files + ``extensions()`` body can keep importing
# ``from workflow.universe_server import _BRANCH_ACTIONS, _ext_branch_*, ...``.
# The ``@mcp.prompt("Branch Design Guide")`` registration is preserved
# below (Pattern A2) so FastMCP introspection sees the chatbot-facing
# signature unchanged; the wrapper delegates to
# ``workflow.api.branches._branch_design_guide_prompt``.
# ───────────────────────────────────────────────────────────────────────────
from workflow.api.branches import (  # noqa: E402, F401  — back-compat re-exports
    _BRANCH_ACTIONS,
    _BRANCH_DESIGN_GUIDE,
    _BRANCH_WRITE_ACTIONS,
    _MERMAID_ID_SAFE,
    _PATCH_NODES_FIELDS,
    _RELATED_SUMMARY_MAX,
    _RELATED_WIKI_CAP,
    _VALID_STATE_TYPES,
    _action_continue_branch,
    _action_fork_tree,
    _append_global_ledger,
    _apply_conditional_edge_spec,
    _apply_edge_spec,
    _apply_node_spec,
    _apply_patch_op,
    _apply_state_field_spec,
    _branch_design_guide_prompt,
    _branch_mermaid,
    _build_branch_text,
    _closest_state_type,
    _coerce_node_keys,
    _coerce_patch_nodes_value,
    _dispatch_branch_action,
    _ensure_author_server_db,
    _errors_to_suggestions,
    _ext_branch_add_node,
    _ext_branch_add_state_field,
    _ext_branch_build,
    _ext_branch_connect_nodes,
    _ext_branch_create,
    _ext_branch_delete,
    _ext_branch_describe,
    _ext_branch_get,
    _ext_branch_list,
    _ext_branch_patch,
    _ext_branch_patch_nodes,
    _ext_branch_search_nodes,
    _ext_branch_set_entry_point,
    _ext_branch_update_node,
    _ext_branch_validate,
    _lookup_node_body,
    _mermaid_label,
    _mermaid_node_id,
    _related_summary,
    _related_wiki_pages,
    _resolve_branch_id,
    _resolve_node_spec,
    _resolve_udir,
    _split_csv,
    _staged_branch_from_spec,
    _suggest_entry_point,
)


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
    return _branch_design_guide_prompt()

























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
    _page_rel_path,  # noqa: F401  (back-compat re-export; live use moved with branches Step 8)
    _parse_frontmatter,  # noqa: F401  (back-compat re-export; live use moved with branches Step 8 + tests/test_wiki_tools.py)
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


# ═══════════════════════════════════════════════════════════════════════════
# TOOL 3 — Goals (back-compat @mcp.tool wrapper, Pattern A2)
# ═══════════════════════════════════════════════════════════════════════════
# Body extracted to ``workflow.api.market.goals``. This wrapper preserves
# FastMCP introspection (the chatbot-facing signature + docstring) and
# delegates to the plain callable.

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
      common_nodes Nodes appearing in >=`min_branches` Branches.
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
    return _goals_impl(
        action=action,
        goal_id=goal_id,
        branch_def_id=branch_def_id,
        branch_version_id=branch_version_id,
        name=name,
        description=description,
        tags=tags,
        visibility=visibility,
        query=query,
        metric=metric,
        min_branches=min_branches,
        author=author,
        limit=limit,
        scope=scope,
        force=force,
    )


# ═══════════════════════════════════════════════════════════════════════════
# TOOL 3b — Outcome Gates (back-compat @mcp.tool wrapper, Pattern A2)
# ═══════════════════════════════════════════════════════════════════════════
# Body extracted to ``workflow.api.market.gates``. Same Pattern A2 as
# ``goals()`` above.

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

    Each Goal declares a ladder of rungs (draft -> peer-reviewed -> published
    -> cited -> breakthrough). Branches self-report which rungs they've
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
    return _gates_impl(
        action=action,
        goal_id=goal_id,
        branch_def_id=branch_def_id,
        rung_key=rung_key,
        ladder=ladder,
        evidence_url=evidence_url,
        evidence_note=evidence_note,
        reason=reason,
        include_retracted=include_retracted,
        limit=limit,
        force=force,
        claim_id=claim_id,
        bonus_stake=bonus_stake,
        attachment_scope=attachment_scope,
        eval_verdict=eval_verdict,
        node_last_claimer=node_last_claimer,
        node_id=node_id,
    )


