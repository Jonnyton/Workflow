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


def _nodes_path() -> Path:
    """Path to the global node registry."""
    return _base_path() / ".node_registry.json"


def _load_nodes() -> list[dict[str, Any]]:
    """Load all registered nodes."""
    data = _read_json(_nodes_path())
    if isinstance(data, list):
        return data
    return []


def _save_nodes(nodes: list[dict[str, Any]]) -> None:
    """Save the node registry."""
    path = _nodes_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(nodes, indent=2, default=str), encoding="utf-8")


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
