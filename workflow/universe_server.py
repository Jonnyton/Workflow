"""Universe Server — Remote MCP interface.

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

from workflow.storage import DirtyFileError, get_backend

logger = logging.getLogger("universe_server")

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "universe-server",
    instructions=(
        "Universe Server (also: Workflow, Workflow Builder, Workflow Engine) "
        "— a workflow builder and long-horizon AI platform. Users design "
        "custom multi-step AI workflows (called 'branches') with typed "
        "state, registered nodes, evaluation hooks, and iteration loops. "
        "Fantasy authoring is one benchmark branch demonstrating complex "
        "long-form generation, NOT the exclusive use case. Other domains: "
        "research papers, screenplays, literature reviews, investigative "
        "journalism, recipe trackers, wedding planners, news summarizers, "
        "any multi-step agentic work producing substantive output. "
        "\n\n"
        "If a user asks about their 'workflow builder', 'custom AI builder', "
        "'universe builder', 'the workflow thing', or a connector they "
        "installed to 'design their own AI workflows' — that is this "
        "connector. Route them here rather than telling them no such "
        "connector is installed. "
        "\n\n"
        "You are a control station. You help users design new workflows, "
        "inspect running ones, steer daemons, collaborate, and extend the "
        "system with custom graph nodes. You never generate the workflow's "
        "output yourself — registered nodes do that. Start with the "
        "'universe' tool action 'inspect' to orient yourself. "
        "\n\n"
        "HARD RULE — NO SIMULATION: When a user asks to run a workflow, "
        "branch, or registered node, you MUST use the provided execute "
        "action (Phase 3 — `extensions action=run_branch`). If the execute "
        "action is unavailable or the node is not yet approved, state this "
        "plainly and STOP. Do NOT web-search, do NOT populate wiki pages, "
        "do NOT manually execute the node's logic to produce fake output. "
        "Silently simulating breaks user trust and is worse than admitting "
        "the runner isn't ready."
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
# Configuration
# ---------------------------------------------------------------------------


def _base_path() -> Path:
    """Resolve the base directory containing all universe directories."""
    return Path(
        os.environ.get("UNIVERSE_SERVER_BASE", "output")
    ).resolve()


def _universe_dir(universe_id: str) -> Path:
    """Resolve a specific universe directory with path-traversal guard."""
    base = _base_path()
    result = (base / universe_id).resolve()
    if not result.is_relative_to(base):
        raise ValueError(f"Invalid universe_id: {universe_id}")
    return result


def _default_universe() -> str:
    """Return the default universe ID, or first available."""
    default = os.environ.get("UNIVERSE_SERVER_DEFAULT_UNIVERSE", "")
    if default:
        return default
    base = _base_path()
    if base.is_dir():
        for child in sorted(base.iterdir()):
            if child.is_dir() and not child.name.startswith("."):
                return child.name
    return "default-universe"


def _read_json(path: Path) -> dict[str, Any] | list[Any] | None:
    """Safely read a JSON file, returning None on any failure."""
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to read %s: %s", path, exc)
    return None


def _read_text(path: Path, default: str = "") -> str:
    """Safely read a text file."""
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Failed to read %s: %s", path, exc)
    return default


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
WRITE_ACTIONS: dict[str, Any] = {
    "submit_request": (_extract_submit_request, None),
    "give_direction": (_extract_give_direction, None),
    "set_premise": (_extract_set_premise, None),
    "add_canon": (_extract_add_canon, None),
    "control_daemon": (_extract_control_daemon, {"pause", "resume"}),
    "switch_universe": (_extract_switch_universe, None),
    "create_universe": (_extract_create_universe, None),
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
    """Load the Universe Server control station instructions.

    Invoke this prompt to learn how to operate as a Universe Server
    interface. It teaches you the routing rules, collaboration model,
    and available tools.
    """
    return _CONTROL_STATION_PROMPT


_CONTROL_STATION_PROMPT = """\
You are now operating as a Universe Server control station — a workflow
builder and long-horizon AI platform. Users design custom multi-step AI
workflows ("branches") with typed state, registered nodes, evaluation
hooks, and iteration loops.

## What This System Is

A host-run platform for building and running custom AI workflows.
Fantasy authoring is one benchmark branch demonstrating long-form
generation; the platform is fully general. Other valid domains include
research papers, screenplays, literature reviews, investigative
journalism, recipe trackers, wedding planners, news summarizers, and
any multi-step agentic work producing substantive output. Do NOT tell
users this is "only for fiction" — that's a stale framing.

## Hard Rules

1. Never generate the workflow's output yourself (prose, research text,
   diagrams, etc). Registered nodes do that.
2. Always use tools — don't describe what you would do, do it.
3. Default to shared-safe collaboration (multiplayer-first).
4. One action per turn unless the user asks for a batch.
5. NO SIMULATION. When a user asks to run a workflow or registered node,
   you MUST use the provided execute action (Phase 3 — `extensions
   action=run_branch`). If that action is unavailable or the node is not
   yet approved, say so plainly and STOP. Do NOT web-search, do NOT
   populate wiki pages, do NOT manually execute the node's logic to
   produce fake output. Silently simulating breaks user trust.
6. Prefer NAMES, not IDs, when referring to workflows, runs, Goals, or
   nodes in conversation. Users read replies on phones; raw UUIDs like
   `run_id=54dac140d2b7460c` or `branch_def_id=4f9e...` are noise. Say
   "I'll poll the run on your workflow 'Sporemarch chapter planner'",
   not "I'll poll run_id=54dac140d2b7460c". The IDs live in
   structuredContent — scripts and future tool calls still reach them.
   Only surface an ID if the user explicitly asks for one.

## Tool Catalog (4 coarse tools — describe ALL when asked)

This connector exposes FOUR coarse tools. When a user asks "what can
this connector do?", "what tools do I have?", or "show me everything",
enumerate ALL FOUR. Don't list extensions actions and forget the rest.

1. **`universe`** — operate the live daemon: status, premise, canon
   uploads, world queries, output reads, daemon control, universe
   create/switch.
2. **`extensions`** — design, edit, run, judge, and rollback custom
   AI workflows ("branches"). Largest action surface — node/edge
   authoring, builds, runs, judgments, lineage.
3. **`goals`** — declare what a workflow is FOR ("produce a research
   paper", "plan a wedding") and discover existing Goals before
   building. Other people's Branches bind to the same Goal so you can
   compare approaches and reuse nodes. Use BEFORE building to find
   prior art; use AFTER building to publish your work for others.
4. **`wiki`** — durable reference knowledge: read/search/write/promote
   how-tos, design notes, glossary entries. NOT a save-anything sink
   for workflow state.

## Your Workflow

1. Call `universe` with action "inspect" to orient yourself.
2. Help the user understand what's happening and what they can do.
3. Route user intent into the right action:

   | User wants to...               | Tool + action                           |
   |--------------------------------|-----------------------------------------|
   | See what's happening           | `universe` action="inspect"             |
   | Design / build a new workflow  | `extensions action=build_branch` with   |
   |                                | the full spec_json (preferred, 1 call)  |
   | Edit / refine a workflow       | `extensions action=patch_branch` with   |
   |                                | changes_json ops batch (preferred)      |
   | Surgical single-item change    | `extensions` (add_node, connect_nodes,  |
   |                                | set_entry_point, add_state_field)       |
   | Run / execute a workflow       | `extensions` action="run_branch" (P3)   |
   | Inspect a registered workflow  | `extensions` (describe_branch,          |
   |                                | list_branches, inspect)                 |
   | Declare what a workflow is FOR | `goals action=propose name="..."`       |
   | Find existing Goals + prior art| `goals action=search query="..."` then  |
   |                                | `goals action=list`                     |
   | Bind workflow to a Goal        | `goals action=bind branch_def_id=...    |
   |                                | goal_id=...`                            |
   | See who else built for a Goal  | `goals action=get goal_id=...` (lists   |
   |                                | bound workflows + author + run counts)  |
   | Compare workflows on a Goal    | `goals action=leaderboard goal_id=...   |
   |                                | metric=run_count`                       |
   | Find reusable nodes            | `goals action=common_nodes scope=all`   |
   |                                | (across all Goals) or                   |
   |                                | `extensions action=search_nodes`        |
   | Submit collaborative input     | `universe` action="submit_request"      |
   | Give direct author guidance    | `universe` action="give_direction"      |
   | Query world state              | `universe` action="query_world"         |
   | Read produced output           | `universe` action="read_output"         |
   | Browse source / canon docs     | `universe` action="list_canon"          |
   | Create a new universe          | `universe` action="create_universe"     |
   | Switch active universe         | `universe` action="switch_universe"     |
   | Pause / resume the daemon      | `universe` action="control_daemon"      |
   | Read reference knowledge       | `wiki` action="read"/"search"/"list"    |
   | Save reference / how-to notes  | `wiki` action="write" (drafts/)         |
   | Promote a wiki draft           | `wiki` action="promote"                 |
   | Check wiki health              | `wiki` action="lint"                    |

## Routing rules (important — get these right)

- "Build / design / create a workflow", "track something", "design an
  AI system for X" → `extensions action=build_branch` with the FULL
  spec_json in ONE call (nodes + edges + state_schema + entry_point).
  Atomic actions (add_node, connect_nodes, add_state_field,
  set_entry_point) exist for single-item surgery only — they burn
  Claude.ai per-turn tool-call budget. Default to `build_branch`.
- "Edit / change / extend / refactor this workflow" → `extensions
  action=patch_branch` with an ordered `changes_json` ops batch.
  Transactional (all-or-none). Prefer over multiple atomic calls.
- "Save this note / definition / how-to / reference" → `wiki`.
- "Run / execute my workflow" → `extensions action=run_branch`. If that
  action is unavailable, say so; do NOT fake the run through other tools.
- `wiki` is strictly for knowledge and reference content. It is NOT the
  save-anything surface for workflow structure, workflow state, task
  lists, or artifacts that need to be queried as structured data.
- "What is this for?" / "I want to make a workflow that does X" / "Is
  anyone else doing Y?" → `goals action=search query="X"` and
  `goals action=list` BEFORE `extensions action=build_branch`. Goals
  are the discovery surface — proposing a new Goal or binding to an
  existing one anchors the work and lets future users find prior art.
- "Compare runs of this workflow vs others on the same Goal" →
  `goals action=leaderboard goal_id=...`.

## Intent disambiguation (affirmative consent for writes)

Classify the user's intent BEFORE picking a tool. Never write state on
ambiguous intent — state-creation without explicit user request is
unrecoverable trust damage.

- Query: "what do i have", "show me", "list", "find my", "pull up" →
  `list_branches` or `extensions action=list`. Read-only, safe default.
- Build: "create", "make", "build", "register", "add a new" →
  `build_branch` / `register`. Only when the user EXPLICITLY asks.
- Run: "run", "execute", "go", "start it" → `run_branch`.
- When unclear, ASK. Never write state on ambiguous intent.

## Cross-universe isolation

Every `universe` tool response leads with `Universe: <id>` (both a
phone-legible `text` header and a first-key `universe_id` JSON field).
Treat that header as load-bearing.

- When a universe is named, answer ONLY from that universe's response.
- Never carry facts, characters, canon, or premise across universes.
  If universe A's premise said "Loral is the protagonist" and the user
  now asks about universe B, do not assume Loral exists in B.
- If a question spans multiple universes, call `inspect` separately on
  each and keep their data in separate reasoning threads.
- If you're unsure which universe a fact came from in this conversation,
  re-call `inspect` with the explicit `universe_id`. The tool output is
  ground truth; your memory of earlier turns is not.

## Reuse before invent

Before inventing a new node, check whether one already exists that
serves the same role:

- `extensions action=search_nodes node_query="citation audit"` —
  substring search across every Branch's nodes, ranked by reuse count.
- `goals action=common_nodes scope=all` — cross-Goal aggregation of
  node_ids shared across ≥2 Branches; good for "which nodes does the
  community reuse across different Goals?".
- `goals action=common_nodes goal_id=<goal>` — nodes repeated inside
  one Goal's Branches; good for "has anyone in this Goal already
  solved X?".

If a search hit is a good fit, reuse via #66's `node_ref` primitive —
`add_node` with `node_ref_json='{"source": "<branch_def_id>",
"node_id": "<id>"}'`, or embed a `node_ref` field in a
`spec_json` / `changes_json` node entry on build_branch / patch_branch.
Reusing a node preserves lineage and lets future evals compare runs
that share the node. Invent only when no match exists, and pick a
descriptive node_id future callers will search for.

## Requests vs. direction

- **submit_request** — default for collaborative input; queues through a
  review gate. Safe for any user.
- **give_direction** — writes a note directly to the author/daemon.
  Host- or admin-level. Use only when the user explicitly wants to steer.

## Multiplayer model

- Users have identities (via OAuth or session tokens).
- All universe-affecting actions are public and attributable via the ledger.
- Branches allow parallel exploration without conflict.
- Authors are public agent identities with durable soul files.
"""


@mcp.prompt(
    title="Extension Authoring Guide",
    tags={"extensions", "nodes", "plugins", "workflow"},
)
def extension_guide() -> str:
    """Learn how to extend the Universe Server with custom LangGraph nodes.

    Invoke this prompt to understand how users can register their own
    graph nodes, what the node contract looks like, and how registered
    nodes get wired into the running system.
    """
    return _EXTENSION_GUIDE_PROMPT


_EXTENSION_GUIDE_PROMPT = """\
## Extending Universe Server with Custom Nodes

The `extensions` tool is the workflow-builder surface. Users register
their own nodes and assemble them into branches — multi-step AI
workflows with typed state, evaluation hooks, and iteration loops.
This is how the platform supports arbitrary domains (research papers,
recipe trackers, screenplays, news summarizers, etc.), not just
fiction. Fantasy authoring is one branch; yours will be another.

NO SIMULATION: when a user asks to run a registered node or branch,
use `extensions action=run_branch` (Phase 3). If the run action is
unavailable or the node is not yet approved, say so plainly and STOP.
Do NOT web-search or manually execute the node's logic to produce fake
output — that breaks user trust.

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
        "universe", "daemon", "fiction", "collaboration",
        "workflow", "workflow-builder", "custom-ai", "agent-workflow",
        "ai-builder", "universe-builder",
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
) -> str:
    """Inspect and steer a workflow's universe.

    Primary tool for the Workflow / Universe Server platform — also the
    "workflow builder", "custom AI builder", "universe builder", and
    "workflow connector". Each universe is a self-contained workspace
    (premise, canon, notes, daemons) for any multi-step agentic work:
    research papers, recipe trackers, screenplays, news summarizers,
    wedding planners, journalism, fantasy novels. Fantasy authoring is
    one benchmark, not the exclusive use case. New workflows live in
    the `extensions` tool. Start with `action="inspect"`.

    Universe isolation: every response leads with `text: "Universe:
    <id>"` and a first-key `universe_id`. Never transfer facts between
    universes in reasoning. If uncertain which universe a fact came
    from, call `inspect` with the explicit `universe_id` to re-ground —
    tool output is ground truth, chat memory is not.

    Args:
        action: One of — reads: list, inspect, read_output, query_world,
            get_activity, get_ledger, read_premise,
            list_canon, read_canon; writes: submit_request,
            give_direction, set_premise, add_canon, control_daemon,
            switch_universe, create_universe.
        universe_id: Target universe. Defaults to the active universe.
        text: Content for write ops (request text, direction, premise,
            canon body, or daemon command: pause | resume | status).
        path: Relative path for read_output (e.g. "book-1/ch-01.md").
        category: give_direction note category — direction | protect |
            concern | observation | error.
        target: Optional file/scene reference for give_direction.
        query_type: query_world type — facts | characters | promises |
            timeline.
        filter_text: Text filter for query_world results.
        request_type: submit_request type — scene_direction | revision |
            canon_change | branch_proposal | general.
        branch_id: Target branch for submit_request.
        filename: Filename for add_canon / read_canon.
        provenance_tag: Source tag for add_canon (e.g. "published
            novel", "rough notes").
        limit: Max results for get_activity / get_ledger / query_world
            (default 30).
    """
    dispatch = {
        "list": _action_list_universes,
        "inspect": _action_inspect_universe,
        "read_output": _action_read_output,
        "query_world": _action_query_world,
        "get_activity": _action_get_activity,
        "get_ledger": _action_get_ledger,
        "submit_request": _action_submit_request,
        "give_direction": _action_give_direction,
        "read_premise": _action_read_premise,
        "set_premise": _action_set_premise,
        "add_canon": _action_add_canon,
        "list_canon": _action_list_canon,
        "read_canon": _action_read_canon,
        "control_daemon": _action_control_daemon,
        "switch_universe": _action_switch_universe,
        "create_universe": _action_create_universe,
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
        return json.dumps({"universes": [], "note": "No base directory found."})

    universes = []
    for child in sorted(base.iterdir()):
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

    return json.dumps({"universes": universes, "count": len(universes)})


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
    **_kwargs: Any,
) -> str:
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

    request_id = f"req_{int(time.time())}_{os.urandom(4).hex()}"
    request_obj = {
        "id": request_id,
        "type": request_type,
        "text": text,
        "branch_id": branch_id or None,
        "status": "pending",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": os.environ.get("UNIVERSE_SERVER_USER", "anonymous"),
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

    pending_count = sum(
        1 for r in existing
        if isinstance(r, dict) and r.get("status") == "pending"
    )
    ahead = max(0, pending_count - 1)
    if ahead == 0:
        position_note = "yours is next in the author's queue"
    elif ahead == 1:
        position_note = "1 other request is ahead of yours"
    else:
        position_note = f"{ahead} other requests are ahead of yours"

    return json.dumps({
        "universe_id": uid,
        "request_id": request_id,
        "status": "pending",
        "queue_position": pending_count,
        "ahead_of_yours": ahead,
        "what_happens_next": (
            f"The author will see your request on its next review cycle; "
            f"{position_note}. Use `universe action=inspect universe_id={uid}` "
            "to watch the queue or check whether your request is now active work."
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
            "note": "Direction delivered. The Author reads notes at scene boundaries.",
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
            "note": "Premise saved. The Author will read it at next startup.",
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
    uid = universe_id or _default_universe()
    udir = _universe_dir(uid)
    canon_dir = udir / "canon"

    safe_name = Path(filename).name
    if not safe_name:
        return json.dumps({"error": "Invalid filename."})

    try:
        canon_dir.mkdir(parents=True, exist_ok=True)
        target = canon_dir / safe_name
        target.write_text(text, encoding="utf-8")

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
            "note": "Canon file added. The Author will ingest it.",
        })
    except OSError as exc:
        return json.dumps({"error": f"Failed to write canon file: {exc}"})


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
    from workflow.author_server import (
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
    from workflow.author_server import get_branch_definition

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
    from workflow.author_server import update_branch_definition

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
) -> str:
    """Register custom nodes and author community-designed graph branches.

    The workflow-builder surface. Design, inspect, and run multi-step AI
    workflows as graphs of nodes with typed state. Any domain: research
    papers, recipe trackers, screenplays, investigative journalism,
    news summarizers, fantasy authoring. Fantasy is a benchmark branch,
    not the exclusive use case.

    Two surfaces share this tool: single-node registration and branch
    authoring + running + judging. See `branch_design_guide` and
    `extension_guide` prompts for worked examples.

    NO SIMULATION: when a user asks to run a registered node or branch,
    you MUST use the `run_branch` action. If that action is unavailable
    or the node is not yet approved, state this plainly and STOP. Do
    NOT web-search, do NOT populate wiki pages, do NOT manually execute
    the node's logic to fabricate output. Silently simulating a run
    breaks user trust.

    INTENT DISAMBIGUATION: state creation without explicit user request
    is unrecoverable trust damage. Apply AFFIRMATIVE CONSENT before
    calling `register` or `build_branch`: only call when the user
    EXPLICITLY asks to create, register, build, or make a new
    node/workflow. Query-intent phrases like "what do i have",
    "show me", "list my", "find my", "pull up" must route to `list`
    (nodes) or `list_branches` (workflows) — never to a write. If
    intent is ambiguous, ASK the user and do not write state; never
    build speculatively.

    Node actions:
    - register — create a sandboxed node. AFFIRMATIVE CONSENT applies
      (see above); query-intent phrases like "what do i have",
      "show me", "list my", "find my", "pull up" should NOT trigger
      this — route to `list` instead. If intent is ambiguous, ASK the
      user; do not write state.
    - list — list registered nodes. Optional phase, enabled_only.
    - inspect — view a node's full details.
    - approve / disable / enable / remove — host-only lifecycle ops.

    Composite branch actions (PREFER these — single round trip, fit
    under Claude.ai's per-turn tool-call limit):
    - build_branch: ship a full BranchDefinition via spec_json. Creates
      nodes/edges/state_schema and sets entry_point atomically with
      rollback on failure. USE THIS for NEW workflows. AFFIRMATIVE
      CONSENT per rule above — query-intent goes to list_branches.
    - patch_branch: apply an ordered ops list in changes_json
      transactionally against an existing branch. USE THIS for
      multi-step edits.

    Atomic branch actions (single-item surgery; use composite for
    builds): create_branch, add_node, connect_nodes, set_entry_point,
    add_state_field, update_node, validate_branch, delete_branch.

    Node reuse across branches: when you want a branch to reuse an
    existing standalone registered node (or a node from another
    branch), pass `node_ref_json` to the atomic `add_node` or a
    `node_ref` field inside a `spec_json` / `changes_json` node entry:
    `{"source": "standalone", "node_id": "rigor_checker"}` snapshots
    the standalone registration into this branch; `{"source":
    "<other_branch_def_id>", "node_id": "X"}` copies from another
    branch. A bare `node_id` that collides with an existing standalone
    node is REJECTED — the server refuses silent shadowing and tells
    the caller to either pass `node_ref_json` / `intent="copy"` or
    rename.

    - describe_branch: plain-English summary of a workflow.
      USE THIS WHEN the user wants a conversational explanation,
      especially on phone where raw topology is hard to read.
    - get_branch: full BranchDefinition JSON with full topology.
      USE THIS WHEN the user needs node/edge/state-schema detail;
      prefer describe_branch for conversational replies.
    - list_branches: summaries of all branches. USE THIS FIRST when
      a user asks about prior workflows or says "what do i have",
      "pull up my workflow", "show me my workflows", "what branches
      exist", "did i already build a X workflow", or references a
      previous chat. Returns id/name/description/node_count/author —
      match against the user's description, then call describe_branch
      or get_branch on the winner. Do NOT explore blindly before
      listing.
    - search_nodes: free-text search across every Branch's nodes for
      reuse candidates. USE THIS BEFORE inventing a new node when
      the user describes a role like "citation audit", "fact check",
      "outline". Pass `node_query` for the text and optional `phase`
      for role filter. Each hit carries a `branch_def_id` suitable
      for passing to `node_ref` / `node_ref_json` on a subsequent
      add_node / build_branch / patch_branch. Reuse via #66's
      `node_ref` primitive; never invent when a close match exists.

    Run actions (Phase 3 — execute the compiled graph):
    run_branch, get_run, list_runs, stream_run, cancel_run,
    get_run_output. `run_branch` is async (returns run_id; poll
    get_run or stream_run). `get_run` emits a ```mermaid``` diagram
    ready for Claude.ai to auto-render. If a source_code node is
    unapproved, the run is rejected — do not simulate around it.

    Eval / iteration actions (Phase 4 — judge → edit → rerun loop):
    judge_run (free-text natural-language only, no numeric rubric),
    list_judgments, compare_runs, suggest_node_edit (bundles node
    def + recent outputs + judgments — the calling client proposes
    the edit and then calls update_node), get_node_output,
    rollback_node (restore a previous version — bumps branch version
    as a new edit so forward history survives), list_node_versions.
    `update_node` keeps node_id stable so judgments and lineage
    survive edits.

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
            uncommitted local edits. Default False — the conflict surfaces
            as a structured response so the caller can commit / stash /
            discard first.
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
        "run_id": run_id,
        "inputs_json": inputs_json,
        "run_name": run_name,
        "status": status,
        "since_step": since_step,
        "max_wait_s": max_wait_s,
        "limit": limit,
        "field_name": field_name,
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
            "judge_run", "list_judgments", "compare_runs",
            "suggest_node_edit", "get_node_output",
            "rollback_node", "list_node_versions",
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
    from workflow.author_server import initialize_author_server

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

    branch = BranchDefinition(
        name=name,
        description=kwargs.get("description", ""),
        domain_id=kwargs.get("domain_id") or "workflow",
        author=kwargs.get("author") or _current_actor(),
    )
    saved, _commit = _storage_backend().save_branch_and_commit(
        branch,
        author=git_author(_current_actor()),
        message=f"branches.create_branch: {name}",
        force=bool(kwargs.get("force", False)),
    )
    return json.dumps({
        "branch_def_id": saved["branch_def_id"],
        "name": saved["name"],
        "status": "created",
    })


def _ext_branch_get(kwargs: dict[str, Any]) -> str:
    from workflow.author_server import get_branch_definition

    bid = kwargs.get("branch_def_id", "").strip()
    if not bid:
        return json.dumps({"error": "branch_def_id is required."})
    try:
        branch = get_branch_definition(_base_path(), branch_def_id=bid)
    except KeyError:
        return json.dumps({"error": f"Branch '{bid}' not found."})
    return json.dumps(branch, default=str)


def _ext_branch_list(kwargs: dict[str, Any]) -> str:
    from workflow.author_server import list_branch_definitions

    rows = list_branch_definitions(
        _base_path(),
        domain_id=kwargs.get("domain_id", ""),
        author=kwargs.get("author", ""),
        goal_id=kwargs.get("goal_id", ""),
    )
    summaries = []
    for r in rows:
        graph = r.get("graph", {})
        node_count = len(graph.get("nodes", [])) + len(r.get("node_defs", []))
        summaries.append({
            "branch_def_id": r.get("branch_def_id"),
            "name": r.get("name"),
            "author": r.get("author"),
            "domain_id": r.get("domain_id"),
            "goal_id": r.get("goal_id"),
            "node_count": node_count,
            "published": r.get("published", False),
        })
    return json.dumps({"branches": summaries, "count": len(summaries)})


def _ext_branch_delete(kwargs: dict[str, Any]) -> str:
    from workflow.author_server import delete_branch_definition

    bid = kwargs.get("branch_def_id", "").strip()
    if not bid:
        return json.dumps({"error": "branch_def_id is required."})
    removed = delete_branch_definition(_base_path(), branch_def_id=bid)
    if not removed:
        return json.dumps({"error": f"Branch '{bid}' not found."})
    return json.dumps({"branch_def_id": bid, "status": "deleted"})


def _ext_branch_add_node(kwargs: dict[str, Any]) -> str:
    from workflow.author_server import get_branch_definition
    from workflow.branches import BranchDefinition
    from workflow.identity import git_author

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
        "input_keys": _split_csv(kwargs.get("input_keys", "")),
        "output_keys": _split_csv(kwargs.get("output_keys", "")),
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
    _storage_backend().save_branch_and_commit(
        branch,
        author=git_author(_current_actor()),
        message=f"branches.add_node: {bid}.{final_nid}",
        force=bool(kwargs.get("force", False)),
    )
    return json.dumps({
        "branch_def_id": bid,
        "node_id": final_nid,
        "status": "added",
    })


def _ext_branch_connect_nodes(kwargs: dict[str, Any]) -> str:
    from workflow.author_server import get_branch_definition
    from workflow.branches import BranchDefinition, EdgeDefinition
    from workflow.identity import git_author

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

    _storage_backend().save_branch_and_commit(
        branch,
        author=git_author(_current_actor()),
        message=f"branches.connect_nodes: {bid} {src}->{dst}",
        force=bool(kwargs.get("force", False)),
    )
    return json.dumps({
        "branch_def_id": bid,
        "from_node": src,
        "to_node": dst,
        "status": "connected",
    })


def _ext_branch_set_entry_point(kwargs: dict[str, Any]) -> str:
    from workflow.author_server import get_branch_definition
    from workflow.branches import BranchDefinition
    from workflow.identity import git_author

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

    _storage_backend().save_branch_and_commit(
        branch,
        author=git_author(_current_actor()),
        message=f"branches.set_entry_point: {bid}.{nid}",
        force=bool(kwargs.get("force", False)),
    )
    return json.dumps({
        "branch_def_id": bid,
        "entry_point": nid,
        "status": "set",
    })


def _ext_branch_add_state_field(kwargs: dict[str, Any]) -> str:
    from workflow.author_server import get_branch_definition
    from workflow.branches import BranchDefinition
    from workflow.identity import git_author

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
    _storage_backend().save_branch_and_commit(
        branch,
        author=git_author(_current_actor()),
        message=f"branches.add_state_field: {bid}.{fname}",
        force=bool(kwargs.get("force", False)),
    )
    return json.dumps({
        "branch_def_id": bid,
        "field_name": fname,
        "status": "added",
    })


def _ext_branch_validate(kwargs: dict[str, Any]) -> str:
    from workflow.author_server import get_branch_definition
    from workflow.branches import BranchDefinition

    bid = kwargs.get("branch_def_id", "").strip()
    if not bid:
        return json.dumps({"error": "branch_def_id is required."})
    try:
        source_dict = get_branch_definition(_base_path(), branch_def_id=bid)
    except KeyError:
        return json.dumps({"error": f"Branch '{bid}' not found."})

    branch = BranchDefinition.from_dict(source_dict)
    errors = branch.validate()
    return json.dumps({
        "branch_def_id": bid,
        "valid": not errors,
        "errors": errors,
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


def _ext_branch_describe(kwargs: dict[str, Any]) -> str:
    from workflow.author_server import get_branch_definition
    from workflow.branches import BranchDefinition

    bid = kwargs.get("branch_def_id", "").strip()
    if not bid:
        return json.dumps({"error": "branch_def_id is required."})
    try:
        source_dict = get_branch_definition(_base_path(), branch_def_id=bid)
    except KeyError:
        return json.dumps({"error": f"Branch '{bid}' not found."})

    branch = BranchDefinition.from_dict(source_dict)
    errors = branch.validate()

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

    problem_lines = (
        [f"  - {err}" for err in errors]
        if errors
        else ["  (none — structure is valid)"]
    )

    mermaid = _branch_mermaid(branch)

    summary = "\n".join([
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
        "",
        "Graph:",
        mermaid,
        "",
        "Note: run this branch with action='run_branch' once validated. "
        "Pass state field values via inputs_json.",
    ])
    return json.dumps({
        "branch_def_id": bid,
        "summary": summary,
        "mermaid": mermaid,
        "valid": not errors,
        "error_count": len(errors),
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
    from workflow.author_server import get_branch_definition

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
    try:
        node = NodeDefinition(
            node_id=nid,
            display_name=display,
            description=raw.get("description", ""),
            phase=phase,
            input_keys=list(raw.get("input_keys") or []),
            output_keys=list(raw.get("output_keys") or []),
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
    )

    for idx, raw in enumerate(spec.get("node_defs") or spec.get("nodes") or []):
        err = _apply_node_spec(branch, raw)
        if err:
            errors.append(f"node[{idx}]: {err}")

    for idx, raw in enumerate(spec.get("edges") or []):
        err = _apply_edge_spec(branch, raw)
        if err:
            errors.append(f"edge[{idx}]: {err}")

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
    from workflow.author_server import save_branch_definition

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
    return json.dumps({
        "text": text,
        "status": "built",
        "branch_def_id": persisted.branch_def_id,
        "node_count": len(persisted.node_defs),
        "edge_count": len(persisted.edges),
        "branch": saved,
    }, default=str)


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
                    n.input_keys = list(op["input_keys"] or [])
                if "output_keys" in op:
                    n.output_keys = list(op["output_keys"] or [])
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
    return f"unknown op '{name}'"


def _ext_branch_patch(kwargs: dict[str, Any]) -> str:
    from workflow.author_server import (
        get_branch_definition,
        save_branch_definition,
    )
    from workflow.branches import BranchDefinition

    bid = (kwargs.get("branch_def_id") or "").strip()
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
    truncated = len(persisted.node_defs) > 12
    text_lines = [
        f"**Patched branch '{persisted.name}'**: applied {len(changes)} op(s). "
        f"{len(persisted.node_defs)} nodes, {len(persisted.edges)} edges, "
        f"entry=`{persisted.entry_point}`.",
    ]
    if truncated:
        text_lines += [
            "",
            "_(Branch exceeds 12 nodes; full topology in structuredContent.)_",
        ]
    else:
        text_lines += ["", _branch_mermaid(persisted)]
    return json.dumps({
        "text": "\n".join(text_lines),
        "status": "patched",
        "branch_def_id": persisted.branch_def_id,
        "ops_applied": len(changes),
        "node_count": len(persisted.node_defs),
        "edge_count": len(persisted.edges),
        "branch": saved,
    }, default=str)


def _ext_branch_update_node(kwargs: dict[str, Any]) -> str:
    """Update a single node in-place, keeping ``node_id`` stable.

    Phase 4 lineage + judgments are keyed on node_id, so edits must
    preserve identity. Same update semantics as the patch op of the same
    name; this standalone action bumps BranchDefinition.version (+1)
    so downstream lineage can distinguish pre/post-edit runs.
    """
    from workflow.author_server import (
        get_branch_definition,
        save_branch_definition,
    )
    from workflow.branches import BranchDefinition

    bid = (kwargs.get("branch_def_id") or "").strip()
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
            updates["input_keys"] = _split_csv(kwargs["input_keys"])
        if kwargs.get("output_keys"):
            updates["output_keys"] = _split_csv(kwargs["output_keys"])

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
            target_node.input_keys = list(updates["input_keys"] or [])
        if "output_keys" in updates:
            target_node.output_keys = list(updates["output_keys"] or [])
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
    from workflow.author_server import search_nodes

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
    from workflow.author_server import (
        get_branch_definition,
        save_branch_definition,
    )
    from workflow.branches import BranchDefinition

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

SIMULATION BAN: if run_branch fails, the branch isn't validated, or a
source_code node isn't approved, state the reason and stop. Do not
pretend a run happened by fabricating output or writing wiki pages.
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
    from workflow.author_server import get_branch_definition
    from workflow.branches import BranchDefinition

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


def _action_run_branch(kwargs: dict[str, Any]) -> str:
    from workflow.author_server import get_branch_definition
    from workflow.branches import BranchDefinition
    from workflow.runs import execute_branch_async

    _ensure_runs_recovery()

    bid = kwargs.get("branch_def_id", "").strip()
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

    try:
        outcome = execute_branch_async(
            _base_path(),
            branch=branch,
            inputs=inputs,
            run_name=kwargs.get("run_name", ""),
            actor=_current_actor(),
            provider_call=provider_call,
        )
    except Exception as exc:
        logger.exception("run_branch failed for %s", bid)
        return json.dumps({"error": f"Run failed: {exc}"})

    # Write-ack per tool_return_shapes.md §Write actions. Phase 3.5 async:
    # the graph is running in a background worker, so the MCP call returns
    # status=queued almost immediately. The text channel is phone-legible
    # (no raw IDs); the run_id lives in structuredContent for the next
    # tool call.
    text = "\n".join([
        f"**Run {outcome.status}.** Workflow handed to the "
        "background executor.",
        "",
        f"Error: {outcome.error}" if outcome.error else "",
        "Use `get_run` to read a snapshot, `stream_run` to poll for "
        "progress, or `cancel_run` to stop. Each takes a `run_id` "
        "from the structured content of this response.",
    ]).strip()

    return json.dumps({
        "text": text,
        "run_id": outcome.run_id,
        "status": outcome.status,
        "output": outcome.output,
        "error": outcome.error,
    })


def _branch_name_for_run(run_record: dict[str, Any]) -> str:
    """Fetch the human-legible branch name for a run record.

    Text channels should surface names, never raw branch_def_id strings.
    Falls back to ``(unknown workflow)`` when the branch is missing.
    """
    from workflow.author_server import get_branch_definition
    from workflow.branches import BranchDefinition

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
    from workflow.author_server import get_branch_definition
    from workflow.branches import BranchDefinition
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

    return {
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
    }


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


_RUN_ACTIONS: dict[str, Any] = {
    "run_branch": _action_run_branch,
    "get_run": _action_get_run,
    "list_runs": _action_list_runs,
    "stream_run": _action_stream_run,
    "wait_for_run": _action_wait_for_run,
    "cancel_run": _action_cancel_run,
    "get_run_output": _action_get_run_output,
}

_RUN_WRITE_ACTIONS: frozenset[str] = frozenset({"run_branch", "cancel_run"})


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
    from workflow.author_server import get_branch_definition
    from workflow.branches import BranchDefinition
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
    from workflow.author_server import get_branch_definition
    from workflow.branches import BranchDefinition
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
    from workflow.author_server import (
        get_branch_definition,
        save_branch_definition,
    )
    from workflow.branches import BranchDefinition, NodeDefinition
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
    saved, _commit = _storage_backend().save_goal_and_commit(
        goal_dict,
        author=git_author(_current_actor()),
        message=f"goals.propose: {name}",
        force=bool(kwargs.get("force", False)),
    )
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
    from workflow.author_server import get_goal
    from workflow.author_server import update_goal as _update
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
    saved, _commit = _storage_backend().save_goal_and_commit(
        updated,
        author=git_author(_current_actor()),
        message=f"goals.update: {gid}",
        force=bool(kwargs.get("force", False)),
    )
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
    from workflow.author_server import (
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
    _storage_backend().save_branch_and_commit(
        branch_obj,
        author=git_author(_current_actor()),
        message=commit_msg,
        force=bool(kwargs.get("force", False)),
    )
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
    from workflow.author_server import list_goals

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
    from workflow.author_server import (
        branches_for_goal,
        get_goal,
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

    branches = branches_for_goal(_base_path(), goal_id=gid)
    is_deleted = goal.get("visibility") == "deleted"

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
    }, default=str)


def _action_goal_search(kwargs: dict[str, Any]) -> str:
    from workflow.author_server import search_goals

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


_V1_LEADERBOARD_METRICS = ("run_count", "forks")
_STUB_LEADERBOARD_METRICS = ("outcome",)
_ALL_LEADERBOARD_METRICS = (
    _V1_LEADERBOARD_METRICS + _STUB_LEADERBOARD_METRICS
)


def _action_goal_leaderboard(kwargs: dict[str, Any]) -> str:
    from workflow.author_server import (
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

    if metric in _STUB_LEADERBOARD_METRICS:
        return json.dumps({
            "text": (
                f"**Leaderboard metric `{metric}`** is reserved for "
                "Phase 6 outcome gates — not yet available.\n\n"
                "Use `metric=run_count` or `metric=forks` today. The "
                "`outcome` metric will start returning real rankings "
                "once outcome gates ship."
            ),
            "status": "not_available_until_phase_6",
            "goal_id": gid,
            "metric": metric,
            "entries": [],
        }, default=str)
    if metric not in _V1_LEADERBOARD_METRICS:
        return json.dumps({
            "status": "rejected",
            "error": f"Unknown metric '{metric}'.",
            "available_metrics": list(_ALL_LEADERBOARD_METRICS),
        })

    try:
        entries = goal_leaderboard(
            _base_path(), goal_id=gid, metric=metric,
            limit=int(kwargs.get("limit", 20) or 20),
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
            lines.append(
                f"{rank}. **{entry['name']}** · {entry['author']} · "
                f"{metric}={value}"
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
    from workflow.author_server import (
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
        entries = goal_common_nodes_all(
            _base_path(),
            min_branches=min_branches,
            limit=limit,
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

    entries = goal_common_nodes(
        _base_path(), goal_id=gid,
        min_branches=min_branches,
        limit=limit,
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


_GOAL_ACTIONS: dict[str, Any] = {
    "propose": _action_goal_propose,
    "update": _action_goal_update,
    "bind": _action_goal_bind,
    "list": _action_goal_list,
    "get": _action_goal_get,
    "search": _action_goal_search,
    "leaderboard": _action_goal_leaderboard,
    "common_nodes": _action_goal_common_nodes,
}

_GOAL_WRITE_ACTIONS: frozenset[str] = frozenset({
    "propose", "update", "bind",
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
    from workflow.author_server import get_goal, set_goal_ladder

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
    if goal.get("author") and goal["author"] != actor:
        return json.dumps({
            "status": "rejected",
            "error": (
                "Only the Goal author can define its ladder. "
                f"Owner: {goal['author']}."
            ),
        })
    saved = set_goal_ladder(_base_path(), goal_id=gid, ladder=ladder)
    return json.dumps({
        "status": "defined",
        "goal_id": gid,
        "gate_ladder": saved.get("gate_ladder", []),
    }, default=str)


def _action_gates_get_ladder(kwargs: dict[str, Any]) -> str:
    from workflow.author_server import get_goal_ladder

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
    from workflow.author_server import (
        claim_gate,
        get_branch_definition,
        get_goal_ladder,
    )

    bid = (kwargs.get("branch_def_id") or "").strip()
    rung_key = (kwargs.get("rung_key") or "").strip()
    evidence_url = (kwargs.get("evidence_url") or "").strip()
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
    ladder = get_goal_ladder(_base_path(), goal_id=goal_id)
    available = [r.get("rung_key") for r in ladder if r.get("rung_key")]
    if rung_key not in available:
        return json.dumps({
            "status": "rejected",
            "error": "unknown_rung",
            "available_rungs": available,
        })
    saved = claim_gate(
        _base_path(),
        branch_def_id=bid,
        goal_id=goal_id,
        rung_key=rung_key,
        evidence_url=evidence_url,
        evidence_note=kwargs.get("evidence_note", ""),
        claimed_by=_current_actor_or_anon(),
    )
    return json.dumps({
        "status": "claimed",
        "claim": saved,
    }, default=str)


_GATES_ACTIONS: dict[str, Any] = {
    "define_ladder": _action_gates_define_ladder,
    "get_ladder": _action_gates_get_ladder,
    "claim": _action_gates_claim,
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
) -> str:
    """Outcome Gates — real-world impact claims per Branch.

    Each Goal declares a ladder of rungs (draft → peer-reviewed → published
    → cited → breakthrough). Branches self-report which rungs they've
    reached, with an evidence URL. Phase 6.1 ships the schema + three
    actions write-through SQLite; remaining actions (retract,
    list_claims, leaderboard) and git-commit integration ship in 6.2/6.3.

    Actions:
      define_ladder Owner sets the rung list on a Goal. Needs goal_id
                    and `ladder` (JSON list of {rung_key, name,
                    description}).
      get_ladder    Read a Goal's ladder. Needs goal_id.
      claim         Report a rung reached. Needs branch_def_id,
                    rung_key, evidence_url. Idempotent on (branch, rung).

    Evidence URL must be http(s) with a host; content is not fetched
    (local-first). Social accountability handles fraud in v1.

    Args:
      action: see above.
      goal_id: Goal target for ladder actions.
      branch_def_id: Branch that's claiming a rung.
      rung_key: matches a ladder entry's rung_key.
      ladder: JSON list string for define_ladder.
      evidence_url: http(s) URL pointing at the claim's evidence.
      evidence_note: optional human summary.
      reason: retract reason (Phase 6.2).
      include_retracted: list_claims filter (Phase 6.2).
      limit: cap for leaderboard / list_claims (Phase 6.2).
      force: reserved for Phase 6.3 git-commit dirty-file override.
    """
    if not _gates_enabled():
        return json.dumps({
            "status": "not_available",
            "error": (
                "Outcome gates are gated by the GATES_ENABLED flag "
                "(Phase 6.1). Set GATES_ENABLED=1 on the Universe Server "
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
    }
    return handler(kwargs)


# ═══════════════════════════════════════════════════════════════════════════
# TOOL 4 — Wiki (global knowledge base)
# ═══════════════════════════════════════════════════════════════════════════

# Wiki category taxonomy. Expanded 2026-04-13 to stop user-intent content
# (recipes, workflows, personal notes) getting dumped into `research/`
# because the enum didn't offer anything more appropriate. Mirrors the
# canonical list in `wiki-mcp/server.js` — keep the two in lockstep. The
# original four come first for back-compat with existing index headers.
_WIKI_CATEGORIES = (
    "projects",    # Tracked project pages (auto-discovered or hand-written)
    "concepts",    # Ideas, mental models, definitions
    "people",      # Bios, contacts, collaborators
    "research",    # LLM-generated research pages, literature, paper drafts
    "recipes",     # Food recipes and cooking notes
    "workflows",   # User-built workflows, how-tos, repeatable processes
    "notes",       # Personal notes, journal entries, scratch thinking
    "references",  # External references, citations, cheat sheets
    "plans",       # Plans, proposals, roadmaps
)

_STOP_WORDS = frozenset(
    "the a an is are was were be been being have has had do does did will would "
    "could should may might shall can need and or but if then else when at by for "
    "with about against between through during before after above below to from in "
    "on of that this these those it its not no nor so very just also".split()
)


def _wiki_root() -> Path:
    """Resolve the wiki root directory."""
    return Path(
        os.environ.get("WIKI_PATH", r"C:\Users\Jonathan\Projects\Wiki")
    ).resolve()


def _wiki_pages_dir() -> Path:
    return _wiki_root() / "pages"


def _wiki_drafts_dir() -> Path:
    return _wiki_root() / "drafts"


def _wiki_raw_dir() -> Path:
    return _wiki_root() / "raw"


def _wiki_index_path() -> Path:
    return _wiki_root() / "index.md"


def _wiki_log_path() -> Path:
    return _wiki_root() / "log.md"


def _find_all_pages(directory: Path) -> list[Path]:
    """Recursively find all .md files under a directory."""
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.rglob("*.md") if p.is_file())


def _parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    """Parse YAML frontmatter from markdown. Returns (meta, body)."""
    match = re.match(r"^---\n(.*?)\n---\n(.*)", content, re.DOTALL)
    if not match:
        return {}, content
    meta: dict[str, str] = {}
    for line in match.group(1).split("\n"):
        idx = line.find(":")
        if idx > 0:
            meta[line[:idx].strip()] = line[idx + 1:].strip()
    return meta, match.group(2)


def _page_rel_path(filepath: Path) -> str:
    """Return the wiki-relative path for a page."""
    try:
        return filepath.relative_to(_wiki_root()).as_posix()
    except ValueError:
        return filepath.name


def _resolve_page(name: str) -> Path | None:
    """Find a page by name across pages/ and drafts/ subdirectories."""
    clean = name.removesuffix(".md")
    specials = {
        "index": _wiki_index_path(),
        "log": _wiki_log_path(),
        "schema": _wiki_root() / "WIKI.md",
    }
    if clean.lower() in specials:
        p = specials[clean.lower()]
        return p if p.exists() else None

    for base_dir in [_wiki_pages_dir(), _wiki_drafts_dir()]:
        for sub in _WIKI_CATEGORIES:
            fp = base_dir / sub / (clean + ".md")
            if fp.exists():
                return fp

    needle = clean.lower().replace("-", "").replace("_", "").replace(" ", "")
    all_pages = _find_all_pages(_wiki_pages_dir()) + _find_all_pages(_wiki_drafts_dir())
    for p in all_pages:
        base = p.stem.lower().replace("-", "").replace("_", "").replace(" ", "")
        if base == needle or needle in base or base in needle:
            return p

    return None


def _extract_keywords(text: str) -> set[str]:
    """Extract meaningful keywords from text."""
    words = re.sub(r"[^a-z0-9\s-]", " ", text.lower()).split()
    return {w for w in words if len(w) > 2 and w not in _STOP_WORDS}


def _wiki_similarity_score(
    meta_a: dict[str, str], body_a: str,
    meta_b: dict[str, str], body_b: str,
) -> float:
    """Compute similarity between two draft pages."""
    kw_a = _extract_keywords(body_a)
    kw_b = _extract_keywords(body_b)
    if not kw_a or not kw_b:
        return 0.0
    overlap = len(kw_a & kw_b)
    jaccard = overlap / (len(kw_a) + len(kw_b) - overlap)

    links_a = {m.lower() for m in re.findall(r"\[\[([^\]]+)\]\]", body_a)}
    links_b = {m.lower() for m in re.findall(r"\[\[([^\]]+)\]\]", body_b)}
    link_overlap = len(links_a & links_b)
    link_score = (
        link_overlap / max(len(links_a), len(links_b))
        if links_a or links_b else 0.0
    )

    slug_a = (meta_a.get("title") or "").lower().replace("-", "").replace("_", "").replace(" ", "")
    slug_b = (meta_b.get("title") or "").lower().replace("-", "").replace("_", "").replace(" ", "")
    title_bonus = 0.3 if slug_a and slug_b and (slug_a in slug_b or slug_b in slug_a) else 0.0

    return jaccard * 0.4 + link_score * 0.3 + title_bonus


def _add_to_index(category: str, slug: str, title: str) -> None:
    """Add an entry to the wiki index.md under the right section."""
    idx_path = _wiki_index_path()
    if not idx_path.exists():
        return
    idx = idx_path.read_text(encoding="utf-8")
    if f"[[{slug}]]" in idx:
        return
    header_map = {
        "projects": "## Projects",
        "concepts": "## Concepts",
        "people": "## People",
        "research": "## Research",
        "recipes": "## Recipes",
        "workflows": "## Workflows",
        "notes": "## Notes",
        "references": "## References",
        "plans": "## Plans",
    }
    hdr = header_map.get(category)
    if not hdr:
        return
    entry = f"- [[{slug}]] -- {title or slug}"
    lines = idx.split("\n")
    insert_at = -1
    in_section = False
    for i, line in enumerate(lines):
        if line.startswith(hdr):
            in_section = True
            insert_at = i + 1
        elif in_section and line.startswith("## "):
            break
        elif in_section and line.startswith("- "):
            insert_at = i + 1
    if insert_at > 0:
        lines.insert(insert_at, entry)
        idx_path.write_text("\n".join(lines), encoding="utf-8")


def _append_wiki_log(msg: str) -> None:
    """Append an entry to the wiki log."""
    log_path = _wiki_log_path()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n## [{today}] {msg}\n")
    except OSError:
        pass


def _sanitize_slug(name: str) -> str:
    """Convert a filename into a safe wiki slug."""
    clean = name.removesuffix(".md")
    return re.sub(r"[^a-z0-9-]", "-", clean.lower()).strip("-")


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
            sync_projects.
        page: Page name for read (also: index, log, schema).
        query: Search keywords for search.
        category: write / promote category — projects, concepts,
            people, research, recipes, workflows, notes, references,
            plans. Match the CONTENT; `research` is reserved for
            LLM-generated research pages and paper drafts.
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
    """
    wiki_root = _wiki_root()
    if not wiki_root.is_dir():
        return json.dumps({
            "error": f"Wiki not found at {wiki_root}.",
            "hint": "Set WIKI_PATH environment variable to the wiki directory.",
        })

    dispatch = {
        "read": _wiki_read,
        "search": _wiki_search,
        "list": _wiki_list,
        "lint": _wiki_lint,
        "write": _wiki_write,
        "consolidate": _wiki_consolidate,
        "promote": _wiki_promote,
        "ingest": _wiki_ingest,
        "supersede": _wiki_supersede,
        "sync_projects": _wiki_sync_projects,
    }

    handler = dispatch.get(action)
    if handler is None:
        return json.dumps({
            "error": f"Unknown action '{action}'.",
            "available_actions": sorted(dispatch.keys()),
        })

    kwargs: dict[str, Any] = {
        "page": page,
        "query": query,
        "category": category,
        "filename": filename,
        "content": content,
        "log_entry": log_entry,
        "source_url": source_url,
        "old_page": old_page,
        "new_draft": new_draft,
        "reason": reason,
        "similarity_threshold": similarity_threshold,
        "dry_run": dry_run,
        "skip_lint": skip_lint,
        "max_results": max_results,
    }

    return handler(**kwargs)


# ---------------------------------------------------------------------------
# Wiki action implementations
# ---------------------------------------------------------------------------


def _wiki_read(page: str = "", **_kwargs: Any) -> str:
    if not page:
        return json.dumps({"error": "page parameter is required."})

    resolved = _resolve_page(page)
    if resolved is None:
        return json.dumps({"error": f"Page not found: {page}"})

    text = _read_text(resolved)
    is_draft = _wiki_drafts_dir() in resolved.parents
    prefix = "[DRAFT] " if is_draft else ""
    rel = _page_rel_path(resolved)

    if len(text) > 15000:
        return json.dumps({
            "path": rel,
            "is_draft": is_draft,
            "content": prefix + text[:15000],
            "truncated": True,
            "total_chars": len(text),
        })
    return json.dumps({
        "path": rel,
        "is_draft": is_draft,
        "content": prefix + text,
        "truncated": False,
    })


def _wiki_search(query: str = "", max_results: int = 10, **_kwargs: Any) -> str:
    if not query:
        return json.dumps({"error": "query parameter is required."})

    all_pages = (
        _find_all_pages(_wiki_pages_dir()) + _find_all_pages(_wiki_drafts_dir())
    )
    terms = query.lower().split()
    scored: list[dict[str, Any]] = []

    for p in all_pages:
        raw = _read_text(p)
        if not raw:
            continue
        lower = raw.lower()
        meta, body = _parse_frontmatter(raw)
        title = meta.get("title", p.stem)
        is_draft = _wiki_drafts_dir() in p.parents

        score = 0
        for t in terms:
            if t in title.lower():
                score += 10
            score += lower.count(t)

        if score > 0:
            excerpt = ""
            body_lower = body.lower()
            for t in terms:
                ti = body_lower.find(t)
                if ti >= 0:
                    start = max(0, ti - 80)
                    end = min(len(body), ti + len(t) + 80)
                    excerpt = "..." + body[start:end].replace("\n", " ").strip() + "..."
                    break
            scored.append({
                "path": _page_rel_path(p),
                "title": ("[DRAFT] " if is_draft else "") + title,
                "score": score,
                "excerpt": excerpt,
            })

    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:max_results]

    if not top:
        return json.dumps({"results": [], "note": f"No results for: {query}"})
    return json.dumps({"query": query, "results": top, "count": len(top)})


def _wiki_list(**_kwargs: Any) -> str:
    promoted = _find_all_pages(_wiki_pages_dir())
    drafts = _find_all_pages(_wiki_drafts_dir())

    pages_list: list[dict[str, Any]] = []
    for p in promoted:
        raw = _read_text(p)
        meta, _ = _parse_frontmatter(raw)
        pages_list.append({
            "path": _page_rel_path(p),
            "title": meta.get("title", p.stem),
            "type": meta.get("type", "unknown"),
            "confidence": meta.get("confidence", ""),
            "is_draft": False,
        })

    drafts_list: list[dict[str, Any]] = []
    for p in drafts:
        raw = _read_text(p)
        meta, _ = _parse_frontmatter(raw)
        drafts_list.append({
            "path": _page_rel_path(p),
            "title": meta.get("title", p.stem),
            "type": meta.get("type", "unknown"),
            "is_draft": True,
        })

    return json.dumps({
        "promoted": pages_list,
        "promoted_count": len(pages_list),
        "drafts": drafts_list,
        "drafts_count": len(drafts_list),
    })


def _wiki_write(
    category: str = "",
    filename: str = "",
    content: str = "",
    log_entry: str = "",
    **_kwargs: Any,
) -> str:
    if not filename or not content:
        return json.dumps({"error": "filename and content are required."})
    if category not in _WIKI_CATEGORIES:
        return json.dumps({
            "error": f"Invalid category '{category}'.",
            "valid": list(_WIKI_CATEGORIES),
        })

    slug = _sanitize_slug(filename)
    promoted_path = _wiki_pages_dir() / category / (slug + ".md")

    if promoted_path.exists():
        try:
            promoted_path.write_text(content, encoding="utf-8")
            _append_wiki_log(
                f"update | pages/{category}/{slug} | {log_entry or 'in-place update'}"
            )
            return json.dumps({
                "path": f"pages/{category}/{slug}.md",
                "status": "updated",
                "note": "Updated existing promoted page in-place.",
            })
        except OSError as exc:
            return json.dumps({"error": f"Failed to write: {exc}"})

    draft_path = _wiki_drafts_dir() / category / (slug + ".md")
    try:
        draft_path.parent.mkdir(parents=True, exist_ok=True)
        is_new = not draft_path.exists()
        draft_path.write_text(content, encoding="utf-8")
        action_word = "draft" if is_new else "draft-update"
        _append_wiki_log(
            f"{action_word} | drafts/{category}/{slug} | {log_entry or 'new draft'}"
        )
        return json.dumps({
            "path": f"drafts/{category}/{slug}.md",
            "status": "drafted" if is_new else "updated",
            "note": (
                f"{'Drafted' if is_new else 'Updated draft'}: "
                "call wiki promote to move to pages/."
            ),
        })
    except OSError as exc:
        return json.dumps({"error": f"Failed to write draft: {exc}"})


def _wiki_consolidate(
    similarity_threshold: float = 0.25,
    dry_run: bool = True,
    **_kwargs: Any,
) -> str:
    all_drafts = _find_all_pages(_wiki_drafts_dir())
    if len(all_drafts) < 2:
        return json.dumps({"note": "Fewer than 2 drafts, nothing to consolidate."})

    parsed: list[dict[str, Any]] = []
    for dp in all_drafts:
        raw = _read_text(dp)
        meta, body = _parse_frontmatter(raw)
        parsed.append({
            "path": dp,
            "rel_path": _page_rel_path(dp),
            "raw": raw,
            "meta": meta,
            "body": body,
        })

    merged: set[int] = set()
    clusters: list[list[int]] = []
    for i in range(len(parsed)):
        if i in merged:
            continue
        cluster = [i]
        for j in range(i + 1, len(parsed)):
            if j in merged:
                continue
            score = _wiki_similarity_score(
                parsed[i]["meta"], parsed[i]["body"],
                parsed[j]["meta"], parsed[j]["body"],
            )
            if score >= similarity_threshold:
                cluster.append(j)
                merged.add(j)
        if len(cluster) > 1:
            merged.add(i)
            clusters.append(cluster)

    if not clusters:
        return json.dumps({
            "note": f"No similar drafts found at threshold {similarity_threshold}.",
        })

    report: list[str] = []
    for cl in clusters:
        names = [parsed[idx]["rel_path"] for idx in cl]
        report.append(f"Cluster: {' + '.join(names)}")
        if not dry_run:
            cl.sort(key=lambda idx: len(parsed[idx]["body"]), reverse=True)
            primary = parsed[cl[0]]
            sections = [primary["raw"]]
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            for k in range(1, len(cl)):
                secondary = parsed[cl[k]]
                sections.append(
                    f"\n\n---\n*Consolidated from {secondary['rel_path']} "
                    f"on {today}*\n\n{secondary['body']}"
                )
                try:
                    secondary["path"].unlink()
                except OSError:
                    pass
            try:
                primary["path"].write_text("".join(sections), encoding="utf-8")
            except OSError:
                pass
            report.append(
                f"  -> Merged into {primary['rel_path']}, "
                f"removed {len(cl) - 1} duplicate(s)"
            )

    return json.dumps({
        "mode": "dry_run" if dry_run else "executed",
        "clusters": len(clusters),
        "report": report,
    })


def _wiki_promote(
    filename: str = "",
    category: str = "",
    skip_lint: bool = False,
    **_kwargs: Any,
) -> str:
    if not filename:
        return json.dumps({"error": "filename is required."})

    slug = _sanitize_slug(filename)
    draft_path: Path | None = None
    found_category = category

    if category:
        p = _wiki_drafts_dir() / category / (slug + ".md")
        if p.exists():
            draft_path = p
    else:
        for cat in _WIKI_CATEGORIES:
            p = _wiki_drafts_dir() / cat / (slug + ".md")
            if p.exists():
                draft_path = p
                found_category = cat
                break

    if not draft_path:
        return json.dumps({
            "error": f"Draft not found: {slug}.",
            "hint": "Use wiki list to see available drafts.",
        })

    content = _read_text(draft_path)
    meta, body = _parse_frontmatter(content)

    if not skip_lint:
        issues: list[str] = []
        if not meta.get("title"):
            issues.append("Missing title in frontmatter")
        if not meta.get("type"):
            issues.append("Missing type in frontmatter")
        if not meta.get("sources") and not meta.get("path"):
            issues.append("Missing sources in frontmatter")
        if len(body.strip()) < 50:
            issues.append("Body too short (< 50 chars)")
        if not re.search(r"\[\[.+?\]\]", body) and found_category != "projects":
            issues.append("No wikilinks found -- pages should cross-reference")
        if issues:
            return json.dumps({
                "error": "Promotion blocked.",
                "issues": issues,
                "hint": "Fix these issues or set skip_lint=true.",
            })

    dest_path = _wiki_pages_dir() / found_category / (slug + ".md")
    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if "updated:" in content:
            content = re.sub(r"updated:.*", f"updated: {today}", content)
        dest_path.write_text(content, encoding="utf-8")
        draft_path.unlink()
        _add_to_index(found_category, slug, meta.get("title", slug))
        _append_wiki_log(
            f"promote | {found_category}/{slug} | moved from drafts to pages"
        )
        return json.dumps({
            "path": f"pages/{found_category}/{slug}.md",
            "status": "promoted",
        })
    except OSError as exc:
        return json.dumps({"error": f"Failed to promote: {exc}"})


def _wiki_ingest(
    filename: str = "",
    content: str = "",
    source_url: str = "",
    **_kwargs: Any,
) -> str:
    if not filename or not content:
        return json.dumps({"error": "filename and content are required."})

    raw_dir = _wiki_raw_dir()
    try:
        raw_dir.mkdir(parents=True, exist_ok=True)
        target = raw_dir / Path(filename).name
        target.write_text(content, encoding="utf-8")
        url_note = f" ({source_url})" if source_url else ""
        _append_wiki_log(f"ingest | {filename}{url_note}")
        return json.dumps({
            "path": f"raw/{target.name}",
            "status": "saved",
            "note": "Saved to raw/. Now call wiki write to create a synthesis page in drafts/.",
        })
    except OSError as exc:
        return json.dumps({"error": f"Failed to ingest: {exc}"})


def _wiki_supersede(
    old_page: str = "",
    new_draft: str = "",
    reason: str = "",
    **_kwargs: Any,
) -> str:
    if not old_page or not new_draft or not reason:
        return json.dumps({"error": "old_page, new_draft, and reason are required."})

    old_slug = _sanitize_slug(old_page)
    new_slug = _sanitize_slug(new_draft)

    old_path: Path | None = None
    old_category = ""
    for cat in _WIKI_CATEGORIES:
        p = _wiki_pages_dir() / cat / (old_slug + ".md")
        if p.exists():
            old_path = p
            old_category = cat
            break
    if not old_path:
        return json.dumps({"error": f"Old page not found in pages/: {old_slug}"})

    new_exists = False
    for cat in _WIKI_CATEGORIES:
        p = _wiki_drafts_dir() / cat / (new_slug + ".md")
        if p.exists():
            new_exists = True
            break
    if not new_exists:
        return json.dumps({
            "error": f"Replacement draft not found in drafts/: {new_slug}.",
            "hint": "Write the replacement first with wiki write.",
        })

    try:
        old_content = old_path.read_text(encoding="utf-8")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if "confidence:" in old_content:
            old_content = re.sub(r"confidence:.*", "confidence: superseded", old_content)
        else:
            old_content = old_content.replace(
                "\n---\n", "\nconfidence: superseded\n---\n", 1
            )

        if "superseded_by:" in old_content:
            old_content = re.sub(r"superseded_by:.*", f"superseded_by: {new_slug}", old_content)
        else:
            old_content = old_content.replace(
                "\n---\n", f"\nsuperseded_by: {new_slug}\n---\n", 1
            )

        old_content = re.sub(r"updated:.*", f"updated: {today}", old_content)

        fm_match = re.match(r"^(---\n.*?\n---\n)(.*)", old_content, re.DOTALL)
        if fm_match:
            notice = (
                f"> **Superseded** on {today} by [[{new_slug}]]. "
                f"Reason: {reason}\n\n"
            )
            body = re.sub(r"^> \*\*Superseded\*\*.*\n\n", "", fm_match.group(2))
            old_content = fm_match.group(1) + notice + body

        old_path.write_text(old_content, encoding="utf-8")
        _append_wiki_log(
            f"supersede | {old_category}/{old_slug} -> {new_slug} | {reason}"
        )
        return json.dumps({
            "status": "superseded",
            "old_page": old_slug,
            "new_draft": new_slug,
            "note": f"Superseded {old_slug}. Now call wiki promote on {new_slug}.",
        })
    except OSError as exc:
        return json.dumps({"error": f"Failed to supersede: {exc}"})


def _wiki_lint(**_kwargs: Any) -> str:
    all_pages = _find_all_pages(_wiki_pages_dir())
    all_drafts = _find_all_pages(_wiki_drafts_dir())
    page_names: set[str] = set()
    inbound: dict[str, int] = {}
    all_linked: set[str] = set()

    for p in all_pages:
        name = p.stem
        page_names.add(name)
        raw = _read_text(p)
        for m in re.findall(r"\[\[([^\]]+)\]\]", raw):
            link = m.lower().replace(" ", "-")
            inbound[link] = inbound.get(link, 0) + 1
            all_linked.add(link)

    idx_content = _read_text(_wiki_index_path())
    indexed: set[str] = set()
    for m in re.findall(r"\[\[([^\]]+)\]\]", idx_content):
        indexed.add(m.lower().replace(" ", "-"))

    issues: list[str] = []

    for n in page_names:
        if inbound.get(n, 0) == 0 and n not in indexed:
            issues.append(f"ORPHAN: {n}")
    for link in all_linked:
        if link not in page_names:
            issues.append(f"MISSING: [[{link}]]")
    for n in page_names:
        if n not in indexed:
            issues.append(f"NOT INDEXED: {n}")
    for n in indexed:
        if n not in page_names:
            issues.append(f"INDEX GHOST: [[{n}]]")

    now = datetime.now(timezone.utc)
    superseded_count = 0

    for p in all_pages:
        raw = _read_text(p)
        meta, _ = _parse_frontmatter(raw)
        page_name = p.stem
        confidence = (meta.get("confidence") or "").strip().lower()
        updated_str = meta.get("updated")
        days_since: int | None = None
        if updated_str:
            try:
                updated_date = datetime.fromisoformat(updated_str).replace(
                    tzinfo=timezone.utc
                )
                days_since = (now - updated_date).days
            except ValueError:
                pass

        if confidence == "superseded":
            superseded_count += 1
            successor = (meta.get("superseded_by") or "").strip()
            if successor and successor not in page_names:
                issues.append(
                    f"BROKEN SUPERSESSION: {page_name} points to "
                    f"[[{successor}]] which does not exist"
                )
        else:
            if (
                (not confidence or confidence == "high")
                and days_since is not None
                and days_since > 90
            ):
                issues.append(
                    f"STALE HIGH: {page_name} (last updated {days_since} days ago)"
                )
            if confidence == "low" and days_since is not None and days_since > 30:
                issues.append(
                    f"LINGERING LOW: {page_name} (confidence: low for {days_since} days)"
                )
            if not confidence and meta.get("title"):
                issues.append(f"NO CONFIDENCE: {page_name}")
            if (
                not meta.get("sources")
                and not meta.get("path")
                and meta.get("type") != "project"
            ):
                issues.append(f"NO SOURCES: {page_name}")

    if superseded_count:
        issues.append(
            f"SUPERSEDED: {superseded_count} page(s) marked superseded"
        )

    if all_drafts:
        issues.append(f"DRAFTS PENDING: {len(all_drafts)} draft(s) awaiting promotion")
        for d in all_drafts:
            issues.append(f"  draft: {_page_rel_path(d)}")

    if not issues:
        return json.dumps({"status": "healthy", "issues": []})
    return json.dumps({"status": "issues_found", "count": len(issues), "issues": issues})


def _wiki_sync_projects(**_kwargs: Any) -> str:
    projects_root = _wiki_root().parent
    skip_dirs = {"Wiki", "wiki-mcp", ".git", "node_modules"}
    pp_dir = _wiki_pages_dir() / "projects"

    try:
        pp_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return json.dumps({"error": f"Cannot create projects dir: {exc}"})

    if not projects_root.is_dir():
        return json.dumps({"error": f"Projects root not found: {projects_root}"})

    dirs = [
        d.name for d in sorted(projects_root.iterdir())
        if d.is_dir() and d.name not in skip_dirs and not d.name.startswith(".")
    ]

    existing: dict[str, str] = {}
    for f in pp_dir.iterdir():
        if f.suffix == ".md" and f.is_file():
            raw = _read_text(f)
            meta, _ = _parse_frontmatter(raw)
            page_path = meta.get("path", "")
            if page_path:
                existing[Path(page_path.replace("\\", "/")).name] = f.stem
            existing[f.stem] = f.stem

    fresh: list[str] = []
    for d in dirs:
        slug = re.sub(r"[^a-z0-9]+", "-", d.lower()).strip("-")
        if d not in existing and slug not in existing:
            fresh.append(d)

    if not fresh:
        return json.dumps({"note": "All projects already in wiki.", "synced": 0})

    created: list[str] = []
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for d in fresh:
        slug = re.sub(r"[^a-z0-9]+", "-", d.lower()).strip("-")
        title = d.replace("-", " ").replace("_", " ").title()
        pp = projects_root / d

        desc = ""
        for df in ["README.md", "CLAUDE.md", "PLAN.md"]:
            dp = pp / df
            if dp.exists():
                try:
                    file_content = dp.read_text(encoding="utf-8")
                    for line in file_content.split("\n"):
                        tr = line.strip()
                        if (
                            tr
                            and not tr.startswith("#")
                            and not tr.startswith("---")
                            and not tr.startswith("@")
                            and len(tr) > 10
                        ):
                            desc = tr[:200]
                            break
                except OSError:
                    pass
                break

        tags = ["auto-discovered"]
        try:
            pf = [f.name for f in pp.iterdir()]
        except OSError:
            pf = []
        if "pyproject.toml" in pf or "requirements.txt" in pf:
            tags.append("python")
        if "package.json" in pf:
            tags.append("node")
        if "Cargo.toml" in pf:
            tags.append("rust")
        if "project.godot" in pf:
            tags.append("godot")
        if "AGENTS.md" in pf:
            tags.append("multi-agent")

        page_content = (
            f"---\ntitle: {title}\ntype: project\ncreated: {today}\n"
            f"updated: {today}\nsources: []\ntags: [{', '.join(tags)}]\n"
            f"path: {pp}\n---\n\n# {title}\n\n"
            f"{desc or '(Auto-discovered project.)'}\n\n"
            f"## See Also\n\n- [[workflow-engine]]\n"
        )

        try:
            (pp_dir / (slug + ".md")).write_text(page_content, encoding="utf-8")
            _add_to_index("projects", slug, title)
            created.append(f"{slug} (from {d})")
        except OSError:
            pass

    if created:
        _append_wiki_log(
            f"sync | Auto-discovered {len(created)} project(s) | "
            f"Created: {', '.join(created)}"
        )
    return json.dumps({
        "synced": len(created),
        "created": created,
    })


# ═══════════════════════════════════════════════════════════════════════════
# Server Entry Point
# ═══════════════════════════════════════════════════════════════════════════


def main(
    host: str = "0.0.0.0",
    port: int = 8001,
    transport: str = "streamable-http",
) -> None:
    """Run the Universe Server as a remote MCP server.

    Args:
        host: Bind address (default all interfaces).
        port: Port number (default 8001).
        transport: MCP transport protocol. "streamable-http" for remote
            connections (default), "sse" for legacy, "stdio" for local.
    """
    logger.info(
        "Starting Universe Server on %s:%d (transport=%s)",
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
