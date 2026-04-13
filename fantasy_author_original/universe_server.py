"""Universe Server — Remote MCP interface.

A remote MCP server that exposes the Fantasy Author system as a
universe collaboration platform. Any MCP-compatible chatbot (Claude,
and eventually ChatGPT/others as MCP adoption spreads) can connect,
discover tools, and become the user's control interface — no
installation, no custom GPT, just a URL.

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
    python -m fantasy_author universe-server

    # Production (with OAuth):
    python -m fantasy_author universe-server --auth
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

logger = logging.getLogger("universe_server")

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "universe-server",
    instructions=(
        "Universe Server: a host-run daemon platform where autonomous "
        "Author daemons write long-form fiction inside shared universes. "
        "You are a control station. You help users inspect universes, "
        "give direction to Authors, collaborate with other users, and "
        "extend the system with custom graph nodes. You never write "
        "prose yourself — Authors do that. Start with the 'universe' "
        "tool action 'inspect' to orient yourself."
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
You are now operating as a Universe Server control station — the interface
between users and autonomous Author daemons that write long-form fiction.

## What This System Is

A host-run daemon platform. Autonomous Author daemons write novels inside
shared universes. Multiple users collaborate through you. Multiple Authors
(AI writers with distinct identities and durable memory) work in parallel.

## Hard Rules

1. Never write prose or worldbuilding yourself. Authors do that.
2. Always use tools — don't describe what you would do, do it.
3. Default to shared-safe collaboration (multiplayer-first).
4. One action per turn unless the user asks for a batch.

## Your Workflow

1. Call `universe` with action "inspect" to orient yourself.
2. Help the user understand what's happening and what they can do.
3. Route user intent into the right action:

   | User wants to...              | Tool + action                            |
   |-------------------------------|------------------------------------------|
   | See what's happening          | `universe` action="inspect"              |
   | Influence the story           | `universe` action="submit_request"       |
   | Give direct Author guidance   | `universe` action="give_direction"       |
   | Understand the world          | `universe` action="query_world"          |
   | Read what's been written      | `universe` action="read_output"          |
   | Browse canon/source docs      | `universe` action="list_canon"/"read_canon" |
   | Create a new universe         | `universe` action="create_universe"      |
   | Switch active universe        | `universe` action="switch_universe"      |
   | Extend the system             | `extensions` tool                        |
   | Pause/resume the daemon       | `universe` action="control_daemon"       |
   | Read/search wiki knowledge    | `wiki` action="read"/"search"/"list"     |
   | Write wiki content            | `wiki` action="write" (goes to drafts/)  |
   | Promote wiki draft            | `wiki` action="promote"                  |
   | Check wiki health             | `wiki` action="lint"                     |

## Routing: Requests vs. Direction

- **submit_request** is the default for all collaboration. It queues a
  request that goes through the daemon's review gate. Safe for any user.
- **give_direction** writes a note directly to the Author. This is host
  or admin-level — use only when the user explicitly wants to steer.

## Multiplayer Model

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

Users can register their own LangGraph nodes that plug into the
running universe graph. This is how the system evolves — not through
central planning, but through community contribution.

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
    tags={"universe", "daemon", "fiction", "collaboration"},
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
    """Interact with a universe.

    Inspect, steer, and collaborate with autonomous Author daemons writing
    long-form fiction.

    This is the primary tool for all universe operations on a host-run daemon
    platform. Each universe is a self-contained fictional reality with its own
    characters, timeline, canon, and one or more Author daemons writing
    autonomously. Use the 'action' parameter to select an operation.

    **Start here:** call with action="inspect" to see the current state of a
    universe (daemon status, recent activity, work targets, output files).

    READ actions (safe, no side effects):
        list          — List all universes on this server.
        inspect       — Full snapshot: daemon status, premise, notes, work
                        targets, output tree, activity, branches, pending
                        requests. Your primary orientation action.
        read_output   — Read a specific output file. Set 'path' to the
                        relative path (e.g. "book-1/chapter-01.md").
        query_world   — Query the world-state database. Set 'query_type'
                        to: facts, characters, promises, or timeline.
                        Optional 'filter_text' narrows results.
        get_activity  — Tail the activity log. Set 'limit' for line count.
        list_branches — List all narrative branches in the universe.
        get_ledger    — Read the public action ledger (who did what, when).
        read_premise  — Read the current story premise (PROGRAM.md).
        list_canon    — List all canon/reference documents with metadata.
        read_canon    — Read a specific canon document. Set 'filename'.

    WRITE actions (modify universe state):
        submit_request  — Submit a collaboration request that goes through
                          review (safe for any user). Set 'text' to your
                          request. Optional 'request_type': scene_direction,
                          revision, canon_change, branch_proposal, general.
        give_direction  — Write a note directly to the Author (host/admin
                          only). Set 'text' and optional 'category':
                          direction, protect, concern, observation, error.
                          Optional 'target' for file/scene reference.
        set_premise     — Set or overwrite the story premise. Set 'text'.
        add_canon       — Upload a reference document. Set 'filename' and
                          'text' (content). Optional 'provenance_tag'
                          (e.g. "published book", "rough notes").
        control_daemon  — Pause, resume, or check daemon status. Set 'text'
                          to: pause, resume, or status.
        switch_universe — Switch the daemon to a different universe. Set
                          'universe_id'. Daemon restarts automatically.
        create_universe — Create a new empty universe. Set 'universe_id'.
                          Optionally set 'text' as the initial premise.

    Args:
        action: The operation to perform (see actions above).
        universe_id: Target universe. Defaults to the server's active universe.
        text: Content for write operations (request text, direction,
            premise, canon content, or daemon command).
        path: File path for read_output (relative to universe output/).
        category: Note category for give_direction.
        target: File/scene reference for give_direction.
        query_type: World-state query type: facts, characters, promises, timeline.
        filter_text: Text filter for query_world results.
        request_type: Collaboration request type for submit_request.
        branch_id: Target branch for submit_request.
        filename: Filename for add_canon / read_canon.
        provenance_tag: Source description for add_canon (e.g. "published novel").
        limit: Max results for get_activity/get_ledger/query_world (default 30).
    """
    dispatch = {
        "list": _action_list_universes,
        "inspect": _action_inspect_universe,
        "read_output": _action_read_output,
        "query_world": _action_query_world,
        "get_activity": _action_get_activity,
        "list_branches": _action_list_branches,
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

    return handler(**kwargs)


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
        info: dict[str, Any] = {"id": child.name}
        status = _read_json(child / "status.json")
        if status and isinstance(status, dict):
            info["word_count"] = status.get("word_count", 0)
            info["daemon_state"] = status.get("phase", "unknown")
            info["accept_rate"] = status.get("accept_rate")
        info["has_premise"] = (child / "PROGRAM.md").exists()
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

    # Status
    status = _read_json(udir / "status.json")
    if status and isinstance(status, dict):
        result["daemon"] = {
            "phase": status.get("phase", "unknown"),
            "word_count": status.get("word_count", 0),
            "accept_rate": status.get("accept_rate"),
            "is_paused": (udir / ".pause").exists(),
        }

    # Premise
    program = _read_text(udir / "PROGRAM.md")
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

    # Branches
    branches = _read_json(udir / "branches.json")
    if branches:
        result["branches"] = branches

    # Pending requests
    requests = _read_json(udir / "requests.json")
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
            "content": content[:10000],
            "truncated": True,
            "total_chars": len(content),
            "note": "File truncated to 10K chars. Request specific sections if needed.",
        })
    return json.dumps({"content": content, "truncated": False})


def _action_submit_request(
    universe_id: str = "",
    text: str = "",
    request_type: str = "scene_direction",
    branch_id: str = "",
    **_kwargs: Any,
) -> str:
    uid = universe_id or _default_universe()
    udir = _universe_dir(uid)
    if not udir.is_dir():
        return json.dumps({"error": f"Universe '{uid}' not found."})

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

    requests_path = udir / "requests.json"
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

    return json.dumps({
        "request_id": request_id,
        "status": "pending",
        "note": "Request submitted. The Author will consider it at the next review gate.",
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
        from fantasy_author.notes import add_note as _add_note

        udir.mkdir(parents=True, exist_ok=True)
        note = _add_note(
            udir,
            source="user",
            text=text,
            category=category,
            target=target or None,
        )
        return json.dumps({
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
        return _query_world_db(udir, query_type, filter_text, limit)

    if isinstance(data, list) and filter_text:
        lower_filter = filter_text.lower()
        data = [
            item for item in data
            if lower_filter in json.dumps(item, default=str).lower()
        ]

    if isinstance(data, list):
        data = data[:limit]

    return json.dumps({
        "query_type": query_type,
        "results": data,
        "count": len(data) if isinstance(data, list) else 1,
    }, default=str)


def _query_world_db(
    udir: Path, query_type: str, filter_text: str, limit: int,
) -> str:
    """Fallback: query the SQLite world-state database."""
    db_path = udir / "story.db"
    if not db_path.exists():
        return json.dumps({
            "query_type": query_type,
            "results": [],
            "note": "No world-state data found for this universe.",
        })

    import sqlite3

    table_map = {
        "facts": "facts",
        "characters": "entities",
        "promises": "promises",
        "timeline": "timeline",
    }
    table = table_map.get(query_type, "facts")

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check if table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        if not cursor.fetchone():
            conn.close()
            return json.dumps({
                "query_type": query_type,
                "results": [],
                "note": f"Table '{table}' not found in world-state DB.",
            })

        if filter_text:
            # Search across all text columns
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

        return json.dumps({
            "query_type": query_type,
            "results": rows,
            "count": len(rows),
            "source": "world_state_db",
        }, default=str)

    except Exception as exc:
        return json.dumps({"error": f"DB query failed: {exc}"})


def _action_read_premise(universe_id: str = "", **_kwargs: Any) -> str:
    uid = universe_id or _default_universe()
    udir = _universe_dir(uid)
    program_path = udir / "PROGRAM.md"

    content = _read_text(program_path)
    if not content:
        return json.dumps({
            "premise": None,
            "note": "No premise set. Use action='set_premise' to create one.",
        })
    return json.dumps({"premise": content})


def _action_set_premise(universe_id: str = "", text: str = "", **_kwargs: Any) -> str:
    uid = universe_id or _default_universe()
    udir = _universe_dir(uid)
    program_path = udir / "PROGRAM.md"

    if not text.strip():
        return json.dumps({"error": "Premise text cannot be empty."})
    try:
        udir.mkdir(parents=True, exist_ok=True)
        program_path.write_text(text, encoding="utf-8")
        return json.dumps({
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
                "source": os.environ.get("UNIVERSE_SERVER_USER", "anonymous"),
            }
            meta_path.write_text(json.dumps(meta), encoding="utf-8")

        return json.dumps({
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
        return json.dumps({"universe": uid, "canon_files": [], "note": "No canon directory."})

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

    return json.dumps({"universe": uid, "canon_files": files, "count": len(files)})


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
            "universe": uid,
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
                "action": "pause",
                "status": "signal_written",
                "note": "Daemon will pause at the next scene boundary.",
            })
        except OSError as exc:
            return json.dumps({"error": f"Failed to write pause signal: {exc}"})

    elif action == "resume":
        if not pause_path.exists():
            return json.dumps({
                "action": "resume",
                "status": "not_paused",
                "note": "Daemon was not paused.",
            })
        try:
            pause_path.unlink()
            return json.dumps({
                "action": "resume",
                "status": "resumed",
                "note": "Pause signal removed. Daemon will resume.",
            })
        except OSError as exc:
            return json.dumps({"error": f"Failed to remove pause: {exc}"})

    elif action == "status":
        status = _read_json(udir / "status.json")
        if status and isinstance(status, dict):
            return json.dumps({
                "action": "status",
                "phase": status.get("phase", "unknown"),
                "word_count": status.get("word_count", 0),
                "is_paused": pause_path.exists(),
                "accept_rate": status.get("accept_rate"),
            })
        return json.dumps({
            "action": "status",
            "phase": "offline",
            "is_paused": pause_path.exists(),
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
            "lines": [],
            "note": "No activity log found. The daemon may not have run yet.",
        })

    all_lines = content.strip().splitlines()
    tail = all_lines[-limit:]
    return json.dumps({"lines": tail, "count": len(tail), "total": len(all_lines)})


def _action_list_branches(universe_id: str = "", **_kwargs: Any) -> str:
    uid = universe_id or _default_universe()
    udir = _universe_dir(uid)

    branches_path = udir / "branches.json"
    data = _read_json(branches_path)
    if not data:
        return json.dumps({
            "branches": [{"id": "main", "name": "main", "status": "active"}],
            "note": "Default branch only.",
        })

    return json.dumps({"branches": data})


def _action_get_ledger(universe_id: str = "", limit: int = 50, **_kwargs: Any) -> str:
    uid = universe_id or _default_universe()
    udir = _universe_dir(uid)

    ledger_path = udir / "ledger.json"
    data = _read_json(ledger_path)
    if not data or not isinstance(data, list):
        return json.dumps({"entries": [], "note": "No ledger entries yet."})

    entries = list(reversed(data))[:limit]
    return json.dumps({"entries": entries, "count": len(entries)})


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
            (udir / "PROGRAM.md").write_text(text, encoding="utf-8")

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
    from fantasy_author.author_server import (
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
    from fantasy_author.author_server import get_branch_definition

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
    from fantasy_author.author_server import update_branch_definition

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
) -> str:
    """Manage custom LangGraph nodes that extend the daemon's workflow graph.

    Users can register their own Python nodes that plug into the running
    universe graph at declared workflow phases. Registered nodes run in a
    sandboxed subprocess — they cannot access the host filesystem directly.
    The host must approve nodes before they run in production.

    Use the 'extension_guide' prompt to learn the full node contract and
    see examples before registering.

    Actions:
        register — Register a new node. Requires: node_id, display_name,
                   description, phase, input_keys, output_keys, source_code.
                   Optional: dependencies (comma-separated pip packages from
                   the allowlist). Pass input_keys/output_keys as
                   comma-separated state field names.
        list     — List registered nodes. Optional filters: phase,
                   enabled_only (default True).
        inspect  — View a node's full details including source code.
                   Requires: node_id.
        approve  — Approve a node for production use (host only).
                   Requires: node_id.
        disable  — Temporarily disable a node. Requires: node_id.
        enable   — Re-enable a disabled node. Requires: node_id.
        remove   — Permanently remove a node registration. Requires: node_id.

    Args:
        action: Operation to perform (see actions above).
        node_id: Unique node identifier (e.g. "consistency-checker").
        display_name: Human-readable name shown in listings.
        description: What the node does and when it should run.
        phase: Workflow phase where the node executes: orient, plan, draft,
            commit, learn, reflect, worldbuild, or custom.
        input_keys: Comma-separated state fields the node reads.
        output_keys: Comma-separated state fields the node writes.
        source_code: Python source code for the node function.
        dependencies: Comma-separated pip packages (validated against allowlist).
        enabled_only: For list action, show only enabled nodes (default True).
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
    else:
        return json.dumps({
            "error": f"Unknown action '{action}'.",
            "available_actions": [
                "register", "list", "inspect",
                "approve", "disable", "enable", "remove",
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


# ═══════════════════════════════════════════════════════════════════════════
# TOOL 3 — Wiki (global knowledge base)
# ═══════════════════════════════════════════════════════════════════════════

_WIKI_CATEGORIES = ("projects", "concepts", "people", "research")

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
    """Access the global cross-project knowledge wiki.

    Read, search, write, and manage wiki pages across all projects.
    The wiki is a persistent knowledge base shared across all AI agent
    sessions. New content always lands in drafts/ first, then gets
    promoted to pages/ after quality checks (the draft gate).

    **Start here:** call with action="list" to see all wiki pages, or
    action="read" with page="index" for the categorized index.

    READ actions (safe, no side effects):
        read          — Read a wiki page by name. Searches pages/ then
                        drafts/. Special names: index, log, schema.
                        Set 'page' to the page name.
        search        — Search wiki pages by keyword. Searches both
                        promoted and drafts. Set 'query' to search terms.
                        Optional 'max_results' (default 10).
        list          — List all wiki pages (promoted and drafts) with
                        titles, types, paths, and confidence levels.
        lint          — Health-check the wiki: orphan pages, broken
                        wikilinks, staleness, confidence decay, index
                        drift, and pending drafts.

    WRITE actions (modify wiki state):
        write         — Write a wiki page. New pages go to drafts/.
                        Existing promoted pages update in-place.
                        Set 'category' (projects/concepts/people/research),
                        'filename', and 'content'. Optional 'log_entry'.
        consolidate   — Scan drafts for overlapping topics and merge
                        similar ones. Set 'similarity_threshold' (0-1,
                        default 0.25) and 'dry_run' (default True for
                        report only, False to merge).
        promote       — Move a draft to pages/ after lint checks.
                        Set 'filename'. Optional 'category' if ambiguous.
                        Set 'skip_lint' to bypass quality checks.
        ingest        — Save a raw source to raw/ for reference.
                        Set 'filename' and 'content'. Optional 'source_url'.
        supersede     — Mark an existing page as superseded by a newer
                        draft. Set 'old_page', 'new_draft', and 'reason'.
        sync_projects — Scan the Projects folder and auto-create wiki
                        stubs for new projects (bypasses draft gate).

    Args:
        action: The operation to perform (see actions above).
        page: Page name for read action.
        query: Search keywords for search action.
        category: Page category: projects, concepts, people, or research.
        filename: Filename for write/promote/ingest actions.
        content: Page or source content for write/ingest actions.
        log_entry: Optional log message for write action.
        source_url: Optional URL for ingest action.
        old_page: Page to supersede (for supersede action).
        new_draft: Replacement draft (for supersede action).
        reason: Why the old page is being superseded.
        similarity_threshold: Merge threshold for consolidate (0-1, default 0.25).
        dry_run: If true, consolidate reports only (default true).
        skip_lint: If true, promote skips quality checks.
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
