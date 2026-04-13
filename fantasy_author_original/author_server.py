"""SQLite-backed multiplayer Author-server substrate."""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

DB_FILENAME = ".author_server.db"
DEFAULT_BRANCH_MODE = "no_fixed_mainline"
DEFAULT_QUICK_VOTE_SECONDS = 300
SESSION_PREFIX = "fa_session_"

CAP_READ_PUBLIC_UNIVERSE = "read_public_universe"
CAP_SUBMIT_REQUEST = "submit_request"
CAP_FORK_BRANCH = "fork_branch"
CAP_PROPOSE_AUTHOR_FORK = "propose_author_fork"
CAP_SPAWN_RUNTIME_CAPACITY = "spawn_runtime_capacity"
CAP_ASSIGN_RUNTIME_PROVIDER = "assign_runtime_provider"
CAP_PAUSE_RESUME_SERVER = "pause_resume_server"
CAP_ROLLBACK_BRANCH = "rollback_branch"
CAP_PROMOTE_BRANCH = "promote_branch"
CAP_SUPERSEDE_BRANCH = "supersede_branch"
CAP_EDIT_UNIVERSE_RULES = "edit_universe_rules"
CAP_GRANT_CAPABILITIES = "grant_capabilities"

ALL_CAPABILITIES: tuple[str, ...] = (
    CAP_READ_PUBLIC_UNIVERSE,
    CAP_SUBMIT_REQUEST,
    CAP_FORK_BRANCH,
    CAP_PROPOSE_AUTHOR_FORK,
    CAP_SPAWN_RUNTIME_CAPACITY,
    CAP_ASSIGN_RUNTIME_PROVIDER,
    CAP_PAUSE_RESUME_SERVER,
    CAP_ROLLBACK_BRANCH,
    CAP_PROMOTE_BRANCH,
    CAP_SUPERSEDE_BRANCH,
    CAP_EDIT_UNIVERSE_RULES,
    CAP_GRANT_CAPABILITIES,
)

DEFAULT_USER_CAPABILITIES: tuple[str, ...] = (
    CAP_READ_PUBLIC_UNIVERSE,
    CAP_SUBMIT_REQUEST,
    CAP_FORK_BRANCH,
    CAP_PROPOSE_AUTHOR_FORK,
)


def _now() -> float:
    return time.time()


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _json_loads(payload: str | None, default: Any) -> Any:
    if not payload:
        return default
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return default


def _slugify(text: str, fallback: str = "item") -> str:
    cleaned = [
        ch.lower() if ch.isalnum() else "-"
        for ch in text.strip()
    ]
    slug = "".join(cleaned).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or fallback


def author_server_db_path(base_path: str | Path) -> Path:
    return Path(base_path) / DB_FILENAME


def base_path_from_universe(universe_path: str | Path) -> Path:
    return Path(universe_path).resolve().parent


def universe_id_from_path(universe_path: str | Path) -> str:
    return Path(universe_path).resolve().name


def _connect(base_path: str | Path) -> sqlite3.Connection:
    db_path = author_server_db_path(base_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def initialize_author_server(base_path: str | Path) -> Path:
    """Ensure the host-level Author-server database exists and is migrated."""
    schema = """
    CREATE TABLE IF NOT EXISTS universes (
        universe_id TEXT PRIMARY KEY,
        display_name TEXT NOT NULL,
        host_path TEXT NOT NULL,
        created_at REAL NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}'
    );

    CREATE TABLE IF NOT EXISTS universe_rules (
        universe_id TEXT PRIMARY KEY,
        public_read INTEGER NOT NULL DEFAULT 1,
        public_fork INTEGER NOT NULL DEFAULT 1,
        branch_mode TEXT NOT NULL DEFAULT 'no_fixed_mainline',
        quick_vote_seconds INTEGER NOT NULL DEFAULT 300,
        updated_at REAL NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        FOREIGN KEY(universe_id) REFERENCES universes(universe_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS user_accounts (
        user_id TEXT PRIMARY KEY,
        username TEXT NOT NULL UNIQUE COLLATE NOCASE,
        display_name TEXT NOT NULL,
        is_host INTEGER NOT NULL DEFAULT 0,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}'
    );

    CREATE TABLE IF NOT EXISTS user_sessions (
        session_token TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        created_at REAL NOT NULL,
        last_seen REAL NOT NULL,
        expires_at REAL,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        FOREIGN KEY(user_id) REFERENCES user_accounts(user_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS capability_grants (
        user_id TEXT NOT NULL,
        capability TEXT NOT NULL,
        scope TEXT NOT NULL DEFAULT '*',
        granted_by TEXT NOT NULL,
        created_at REAL NOT NULL,
        PRIMARY KEY(user_id, capability, scope),
        FOREIGN KEY(user_id) REFERENCES user_accounts(user_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS author_definitions (
        author_id TEXT PRIMARY KEY,
        display_name TEXT NOT NULL UNIQUE COLLATE NOCASE,
        soul_text TEXT NOT NULL,
        soul_hash TEXT NOT NULL,
        lineage_parent_id TEXT,
        reputation_score REAL NOT NULL DEFAULT 0.0,
        created_at REAL NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}'
    );

    CREATE TABLE IF NOT EXISTS author_forks (
        fork_id TEXT PRIMARY KEY,
        parent_author_id TEXT NOT NULL,
        child_author_id TEXT NOT NULL,
        proposed_by TEXT NOT NULL,
        vote_id TEXT,
        reason TEXT NOT NULL DEFAULT '',
        created_at REAL NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}'
    );

    CREATE TABLE IF NOT EXISTS author_runtime_instances (
        instance_id TEXT PRIMARY KEY,
        universe_id TEXT NOT NULL,
        author_id TEXT NOT NULL,
        provider_name TEXT NOT NULL,
        model_name TEXT NOT NULL,
        branch_id TEXT,
        status TEXT NOT NULL,
        created_by TEXT NOT NULL,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}'
    );

    CREATE TABLE IF NOT EXISTS branches (
        branch_id TEXT PRIMARY KEY,
        universe_id TEXT NOT NULL,
        name TEXT NOT NULL,
        parent_branch_id TEXT,
        is_public INTEGER NOT NULL DEFAULT 1,
        status TEXT NOT NULL DEFAULT 'active',
        created_by TEXT NOT NULL,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        UNIQUE(universe_id, name)
    );

    CREATE TABLE IF NOT EXISTS branch_heads (
        branch_id TEXT PRIMARY KEY,
        snapshot_id TEXT,
        updated_at REAL NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}'
    );

    CREATE TABLE IF NOT EXISTS universe_snapshots (
        snapshot_id TEXT PRIMARY KEY,
        universe_id TEXT NOT NULL,
        branch_id TEXT NOT NULL,
        label TEXT NOT NULL,
        artifact_ref TEXT NOT NULL DEFAULT '',
        created_by TEXT NOT NULL,
        created_at REAL NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}'
    );

    CREATE TABLE IF NOT EXISTS user_requests (
        request_id TEXT PRIMARY KEY,
        universe_id TEXT NOT NULL,
        branch_id TEXT,
        user_id TEXT NOT NULL,
        request_type TEXT NOT NULL,
        text TEXT NOT NULL,
        preferred_author_id TEXT,
        status TEXT NOT NULL DEFAULT 'open',
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}'
    );

    CREATE TABLE IF NOT EXISTS vote_windows (
        vote_id TEXT PRIMARY KEY,
        universe_id TEXT NOT NULL,
        vote_type TEXT NOT NULL,
        subject_type TEXT NOT NULL,
        subject_id TEXT NOT NULL,
        created_by TEXT NOT NULL,
        opens_at REAL NOT NULL,
        closes_at REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'open',
        payload_json TEXT NOT NULL DEFAULT '{}',
        result_json TEXT NOT NULL DEFAULT '{}'
    );

    CREATE TABLE IF NOT EXISTS vote_ballots (
        vote_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        choice TEXT NOT NULL,
        comment TEXT NOT NULL DEFAULT '',
        created_at REAL NOT NULL,
        PRIMARY KEY(vote_id, user_id)
    );

    CREATE TABLE IF NOT EXISTS action_records (
        action_id TEXT PRIMARY KEY,
        universe_id TEXT,
        visibility TEXT NOT NULL,
        actor_type TEXT NOT NULL,
        actor_id TEXT NOT NULL,
        action_type TEXT NOT NULL,
        target_type TEXT NOT NULL,
        target_id TEXT NOT NULL,
        summary TEXT NOT NULL,
        created_at REAL NOT NULL,
        payload_json TEXT NOT NULL DEFAULT '{}'
    );

    CREATE TABLE IF NOT EXISTS universe_notes (
        note_id TEXT PRIMARY KEY,
        universe_id TEXT NOT NULL,
        source TEXT NOT NULL,
        text TEXT NOT NULL,
        category TEXT NOT NULL,
        status TEXT NOT NULL,
        target TEXT,
        clearly_wrong INTEGER NOT NULL DEFAULT 0,
        quoted_passage TEXT NOT NULL DEFAULT '',
        tags_json TEXT NOT NULL DEFAULT '[]',
        metadata_json TEXT NOT NULL DEFAULT '{}',
        timestamp REAL NOT NULL,
        updated_at REAL NOT NULL
    );

    CREATE TABLE IF NOT EXISTS universe_work_targets (
        universe_id TEXT NOT NULL,
        target_id TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        updated_at REAL NOT NULL,
        PRIMARY KEY(universe_id, target_id)
    );

    CREATE TABLE IF NOT EXISTS universe_hard_priorities (
        universe_id TEXT NOT NULL,
        priority_id TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        updated_at REAL NOT NULL,
        PRIMARY KEY(universe_id, priority_id)
    );

    CREATE TABLE IF NOT EXISTS branch_definitions (
        branch_def_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        author TEXT NOT NULL DEFAULT 'anonymous',
        domain_id TEXT NOT NULL DEFAULT 'fantasy_author',
        tags_json TEXT NOT NULL DEFAULT '[]',
        version INTEGER NOT NULL DEFAULT 1,
        parent_def_id TEXT,
        entry_point TEXT NOT NULL DEFAULT '',  -- also in graph_json for export/fork
        graph_json TEXT NOT NULL DEFAULT '{}',
        node_defs_json TEXT NOT NULL DEFAULT '[]',
        state_schema_json TEXT NOT NULL DEFAULT '[]',
        published INTEGER NOT NULL DEFAULT 0,
        stats_json TEXT NOT NULL DEFAULT '{}',
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_branch_defs_author
        ON branch_definitions(author);
    CREATE INDEX IF NOT EXISTS idx_branch_defs_published
        ON branch_definitions(published);
    CREATE INDEX IF NOT EXISTS idx_branch_defs_parent
        ON branch_definitions(parent_def_id);
    CREATE INDEX IF NOT EXISTS idx_branch_defs_domain
        ON branch_definitions(domain_id);
    """
    with _connect(base_path) as conn:
        conn.executescript(schema)
    ensure_default_author(base_path)
    return author_server_db_path(base_path)


def _account_id_for_username(username: str) -> str:
    return f"user::{_slugify(username, 'user')}"


def _author_id_for(display_name: str, soul_text: str) -> tuple[str, str]:
    soul_hash = hashlib.sha256(soul_text.encode("utf-8")).hexdigest()
    author_id = f"author::{_slugify(display_name, 'author')}::{soul_hash[:16]}"
    return author_id, soul_hash


def _branch_id_for(universe_id: str, name: str, *, suffix: str = "") -> str:
    branch_id = f"branch::{universe_id}::{_slugify(name, 'branch')}"
    if suffix:
        branch_id = f"{branch_id}::{suffix}"
    return branch_id


def ensure_default_author(base_path: str | Path) -> dict[str, Any]:
    with _connect(base_path) as conn:
        existing = conn.execute(
            "SELECT * FROM author_definitions ORDER BY created_at LIMIT 1"
        ).fetchone()
    if existing is not None:
        return _author_from_row(existing)
    return register_author(
        base_path,
        display_name="House Author",
        soul_text="Default house author for the host-run universe server.",
        created_by="system",
        metadata={"auto_created": True},
    )


def ensure_host_account(base_path: str | Path, username: str) -> dict[str, Any]:
    return create_or_update_account(
        base_path,
        username=username,
        display_name=username,
        is_host=True,
        capabilities=ALL_CAPABILITIES,
        metadata={"host_managed": True},
    )


def create_or_update_account(
    base_path: str | Path,
    *,
    username: str,
    display_name: str | None = None,
    is_host: bool = False,
    capabilities: list[str] | tuple[str, ...] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    initialize_author_server(base_path)
    now = _now()
    user_id = _account_id_for_username(username)
    with _connect(base_path) as conn:
        conn.execute(
            """
            INSERT INTO user_accounts (
                user_id, username, display_name, is_host, is_active,
                created_at, updated_at, metadata_json
            ) VALUES (?, ?, ?, ?, 1, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                display_name=excluded.display_name,
                is_host=MAX(user_accounts.is_host, excluded.is_host),
                is_active=1,
                updated_at=excluded.updated_at,
                metadata_json=excluded.metadata_json
            """,
            (
                user_id,
                username,
                display_name or username,
                1 if is_host else 0,
                now,
                now,
                _json_dumps(metadata or {}),
            ),
        )
    if capabilities:
        grant_capabilities(
            base_path,
            user_id=user_id,
            capabilities=list(capabilities),
            granted_by=user_id,
        )
    return get_account(base_path, user_id=user_id) or {
        "user_id": user_id,
        "username": username,
        "display_name": display_name or username,
        "is_host": is_host,
        "capabilities": list(capabilities or []),
    }


def get_account(
    base_path: str | Path,
    *,
    user_id: str | None = None,
    username: str | None = None,
) -> dict[str, Any] | None:
    if not user_id and not username:
        return None
    initialize_author_server(base_path)
    query = (
        "SELECT * FROM user_accounts WHERE user_id = ?"
        if user_id else
        "SELECT * FROM user_accounts WHERE username = ? COLLATE NOCASE"
    )
    value = user_id or username
    with _connect(base_path) as conn:
        row = conn.execute(query, (value,)).fetchone()
    if row is None:
        return None
    account = dict(row)
    account["is_host"] = bool(account["is_host"])
    account["is_active"] = bool(account["is_active"])
    account["metadata"] = _json_loads(account.pop("metadata_json", None), {})
    account["capabilities"] = list_capabilities(
        base_path,
        user_id=account["user_id"],
    )
    return account


def list_accounts(base_path: str | Path) -> list[dict[str, Any]]:
    initialize_author_server(base_path)
    with _connect(base_path) as conn:
        rows = conn.execute(
            "SELECT * FROM user_accounts ORDER BY created_at, user_id"
        ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        account = dict(row)
        account["is_host"] = bool(account["is_host"])
        account["is_active"] = bool(account["is_active"])
        account["metadata"] = _json_loads(account.pop("metadata_json", None), {})
        account["capabilities"] = list_capabilities(
            base_path,
            user_id=account["user_id"],
        )
        result.append(account)
    return result


def list_capabilities(
    base_path: str | Path,
    *,
    user_id: str,
    universe_id: str | None = None,
) -> list[str]:
    initialize_author_server(base_path)
    scopes = ["*"]
    if universe_id:
        scopes.append(universe_id)
    placeholders = ", ".join("?" for _ in scopes)
    with _connect(base_path) as conn:
        rows = conn.execute(
            f"""
            SELECT capability
            FROM capability_grants
            WHERE user_id = ? AND scope IN ({placeholders})
            ORDER BY capability
            """,
            (user_id, *scopes),
        ).fetchall()
    return [str(row["capability"]) for row in rows]


def grant_capabilities(
    base_path: str | Path,
    *,
    user_id: str,
    capabilities: list[str],
    granted_by: str,
    universe_id: str | None = None,
) -> None:
    initialize_author_server(base_path)
    scope = universe_id or "*"
    with _connect(base_path) as conn:
        for capability in capabilities:
            conn.execute(
                """
                INSERT INTO capability_grants (
                    user_id, capability, scope, granted_by, created_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, capability, scope) DO NOTHING
                """,
                (user_id, capability, scope, granted_by, _now()),
            )


def create_session(
    base_path: str | Path,
    *,
    username: str,
    display_name: str | None = None,
    created_by: str = "system",
    capabilities: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    account = create_or_update_account(
        base_path,
        username=username,
        display_name=display_name,
        capabilities=capabilities or list(DEFAULT_USER_CAPABILITIES),
        metadata=metadata,
    )
    token = SESSION_PREFIX + secrets.token_urlsafe(24)
    now = _now()
    with _connect(base_path) as conn:
        conn.execute(
            """
            INSERT INTO user_sessions (
                session_token, user_id, created_at, last_seen, expires_at, metadata_json
            ) VALUES (?, ?, ?, ?, NULL, ?)
            """,
            (token, account["user_id"], now, now, _json_dumps(metadata or {})),
        )
    return {
        "token": token,
        "account": account,
        "created_at": now,
        "created_by": created_by,
    }


def resolve_bearer_token(
    base_path: str | Path,
    token: str,
    *,
    master_api_key: str = "",
    master_username: str = "host",
) -> dict[str, Any] | None:
    initialize_author_server(base_path)
    if master_api_key and token == master_api_key:
        actor = ensure_host_account(base_path, master_username)
        actor["token_type"] = "master_api_key"
        return actor

    with _connect(base_path) as conn:
        row = conn.execute(
            """
            SELECT s.session_token, s.user_id, s.expires_at, a.username, a.display_name, a.is_host
            FROM user_sessions AS s
            JOIN user_accounts AS a ON a.user_id = s.user_id
            WHERE s.session_token = ?
            """,
            (token,),
        ).fetchone()
        if row is None:
            return None
        expires_at = row["expires_at"]
        if expires_at is not None and float(expires_at) < _now():
            conn.execute("DELETE FROM user_sessions WHERE session_token = ?", (token,))
            return None
        conn.execute(
            "UPDATE user_sessions SET last_seen = ? WHERE session_token = ?",
            (_now(), token),
        )
    actor = get_account(base_path, user_id=str(row["user_id"]))
    if actor is None:
        return None
    actor["token_type"] = "session"
    actor["session_token"] = token
    return actor


def actor_has_capability(actor: dict[str, Any], capability: str) -> bool:
    if actor.get("is_host"):
        return True
    return capability in set(actor.get("capabilities", []))


def ensure_universe_registered(
    base_path: str | Path,
    *,
    universe_id: str,
    universe_path: str | Path,
    display_name: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    initialize_author_server(base_path)
    now = _now()
    with _connect(base_path) as conn:
        existing = conn.execute(
            "SELECT created_at FROM universes WHERE universe_id = ?",
            (universe_id,),
        ).fetchone()
        created_at = float(existing["created_at"]) if existing is not None else now
        conn.execute(
            """
            INSERT INTO universes (
                universe_id, display_name, host_path, created_at, metadata_json
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(universe_id) DO UPDATE SET
                display_name=excluded.display_name,
                host_path=excluded.host_path,
                metadata_json=excluded.metadata_json
            """,
            (
                universe_id,
                display_name or universe_id,
                str(Path(universe_path).resolve()),
                created_at,
                _json_dumps(metadata or {}),
            ),
        )
    ensure_universe_rules(base_path, universe_id=universe_id)
    ensure_default_branch(base_path, universe_id=universe_id)
    return get_universe(base_path, universe_id=universe_id)


def sync_universes_from_filesystem(base_path: str | Path) -> None:
    initialize_author_server(base_path)
    root = Path(base_path)
    if not root.exists():
        return
    for entry in root.iterdir():
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        display_name = entry.name
        meta_path = entry / "universe.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                display_name = str(meta.get("name", entry.name))
            except (OSError, json.JSONDecodeError):
                display_name = entry.name
        ensure_universe_registered(
            base_path,
            universe_id=entry.name,
            universe_path=entry,
            display_name=display_name,
        )


def get_universe(base_path: str | Path, *, universe_id: str) -> dict[str, Any]:
    initialize_author_server(base_path)
    with _connect(base_path) as conn:
        row = conn.execute(
            "SELECT * FROM universes WHERE universe_id = ?",
            (universe_id,),
        ).fetchone()
    if row is None:
        raise KeyError(universe_id)
    result = dict(row)
    result["metadata"] = _json_loads(result.pop("metadata_json", None), {})
    result["rules"] = get_universe_rules(base_path, universe_id=universe_id)
    return result


def ensure_universe_rules(
    base_path: str | Path,
    *,
    universe_id: str,
) -> dict[str, Any]:
    initialize_author_server(base_path)
    with _connect(base_path) as conn:
        conn.execute(
            """
            INSERT INTO universe_rules (
                universe_id, public_read, public_fork, branch_mode,
                quick_vote_seconds, updated_at, metadata_json
            ) VALUES (?, 1, 1, ?, ?, ?, '{}')
            ON CONFLICT(universe_id) DO NOTHING
            """,
            (universe_id, DEFAULT_BRANCH_MODE, DEFAULT_QUICK_VOTE_SECONDS, _now()),
        )
    return get_universe_rules(base_path, universe_id=universe_id)


def get_universe_rules(
    base_path: str | Path,
    *,
    universe_id: str,
) -> dict[str, Any]:
    initialize_author_server(base_path)
    with _connect(base_path) as conn:
        row = conn.execute(
            "SELECT * FROM universe_rules WHERE universe_id = ?",
            (universe_id,),
        ).fetchone()
    if row is None:
        raise KeyError(universe_id)
    result = dict(row)
    result["public_read"] = bool(result["public_read"])
    result["public_fork"] = bool(result["public_fork"])
    result["metadata"] = _json_loads(result.pop("metadata_json", None), {})
    return result


def update_universe_rules(
    base_path: str | Path,
    *,
    universe_id: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    current = get_universe_rules(base_path, universe_id=universe_id)
    merged_metadata = dict(current.get("metadata", {}))
    merged_metadata.update(dict(updates.get("metadata", {})))
    with _connect(base_path) as conn:
        conn.execute(
            """
            UPDATE universe_rules
            SET public_read = ?, public_fork = ?, branch_mode = ?,
                quick_vote_seconds = ?, updated_at = ?, metadata_json = ?
            WHERE universe_id = ?
            """,
            (
                1 if bool(updates.get("public_read", current["public_read"])) else 0,
                1 if bool(updates.get("public_fork", current["public_fork"])) else 0,
                str(updates.get("branch_mode", current["branch_mode"])),
                int(updates.get("quick_vote_seconds", current["quick_vote_seconds"])),
                _now(),
                _json_dumps(merged_metadata),
                universe_id,
            ),
        )
    return get_universe_rules(base_path, universe_id=universe_id)


def ensure_default_branch(base_path: str | Path, *, universe_id: str) -> dict[str, Any]:
    branch_id = _branch_id_for(universe_id, "free-roam")
    with _connect(base_path) as conn:
        conn.execute(
            """
            INSERT INTO branches (
                branch_id, universe_id, name, parent_branch_id, is_public,
                status, created_by, created_at, updated_at, metadata_json
            ) VALUES (?, ?, 'free-roam', NULL, 1, 'active', 'system', ?, ?, ?)
            ON CONFLICT(branch_id) DO NOTHING
            """,
            (
                branch_id,
                universe_id,
                _now(),
                _now(),
                _json_dumps({"default": True, "branch_mode": DEFAULT_BRANCH_MODE}),
            ),
        )
        conn.execute(
            """
            INSERT INTO branch_heads (branch_id, snapshot_id, updated_at, metadata_json)
            VALUES (?, NULL, ?, '{}')
            ON CONFLICT(branch_id) DO NOTHING
            """,
            (branch_id, _now()),
        )
    return get_branch(base_path, branch_id=branch_id)


def create_branch(
    base_path: str | Path,
    *,
    universe_id: str,
    name: str,
    created_by: str,
    parent_branch_id: str | None = None,
    is_public: bool = True,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    branch_id = _branch_id_for(universe_id, name, suffix=uuid.uuid4().hex[:8])
    with _connect(base_path) as conn:
        conn.execute(
            """
            INSERT INTO branches (
                branch_id, universe_id, name, parent_branch_id, is_public,
                status, created_by, created_at, updated_at, metadata_json
            ) VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)
            """,
            (
                branch_id,
                universe_id,
                name,
                parent_branch_id,
                1 if is_public else 0,
                created_by,
                _now(),
                _now(),
                _json_dumps(metadata or {}),
            ),
        )
        conn.execute(
            """
            INSERT INTO branch_heads (branch_id, snapshot_id, updated_at, metadata_json)
            VALUES (?, NULL, ?, '{}')
            """,
            (branch_id, _now()),
        )
    return get_branch(base_path, branch_id=branch_id)


def list_branches(base_path: str | Path, *, universe_id: str) -> list[dict[str, Any]]:
    with _connect(base_path) as conn:
        rows = conn.execute(
            """
            SELECT b.*, h.snapshot_id
            FROM branches AS b
            LEFT JOIN branch_heads AS h ON h.branch_id = b.branch_id
            WHERE b.universe_id = ?
            ORDER BY b.created_at, b.branch_id
            """,
            (universe_id,),
        ).fetchall()
    return [_branch_from_row(row) for row in rows]


def get_branch(base_path: str | Path, *, branch_id: str) -> dict[str, Any]:
    with _connect(base_path) as conn:
        row = conn.execute(
            """
            SELECT b.*, h.snapshot_id
            FROM branches AS b
            LEFT JOIN branch_heads AS h ON h.branch_id = b.branch_id
            WHERE b.branch_id = ?
            """,
            (branch_id,),
        ).fetchone()
    if row is None:
        raise KeyError(branch_id)
    return _branch_from_row(row)


def mark_branch_status(
    base_path: str | Path,
    *,
    branch_id: str,
    status: str,
) -> dict[str, Any]:
    with _connect(base_path) as conn:
        conn.execute(
            "UPDATE branches SET status = ?, updated_at = ? WHERE branch_id = ?",
            (status, _now(), branch_id),
        )
    return get_branch(base_path, branch_id=branch_id)


def create_snapshot(
    base_path: str | Path,
    *,
    universe_id: str,
    branch_id: str,
    label: str,
    created_by: str,
    artifact_ref: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    snapshot_id = f"snapshot::{uuid.uuid4().hex}"
    with _connect(base_path) as conn:
        conn.execute(
            """
            INSERT INTO universe_snapshots (
                snapshot_id, universe_id, branch_id, label, artifact_ref,
                created_by, created_at, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                universe_id,
                branch_id,
                label,
                artifact_ref,
                created_by,
                _now(),
                _json_dumps(metadata or {}),
            ),
        )
        conn.execute(
            """
            INSERT INTO branch_heads (branch_id, snapshot_id, updated_at, metadata_json)
            VALUES (?, ?, ?, '{}')
            ON CONFLICT(branch_id) DO UPDATE SET
                snapshot_id=excluded.snapshot_id,
                updated_at=excluded.updated_at
            """,
            (branch_id, snapshot_id, _now()),
        )
    return get_snapshot(base_path, snapshot_id=snapshot_id)


def set_branch_head(
    base_path: str | Path,
    *,
    branch_id: str,
    snapshot_id: str,
) -> dict[str, Any]:
    with _connect(base_path) as conn:
        conn.execute(
            """
            INSERT INTO branch_heads (branch_id, snapshot_id, updated_at, metadata_json)
            VALUES (?, ?, ?, '{}')
            ON CONFLICT(branch_id) DO UPDATE SET
                snapshot_id=excluded.snapshot_id,
                updated_at=excluded.updated_at
            """,
            (branch_id, snapshot_id, _now()),
        )
    return get_branch(base_path, branch_id=branch_id)


def get_snapshot(base_path: str | Path, *, snapshot_id: str) -> dict[str, Any]:
    with _connect(base_path) as conn:
        row = conn.execute(
            "SELECT * FROM universe_snapshots WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchone()
    if row is None:
        raise KeyError(snapshot_id)
    result = dict(row)
    result["metadata"] = _json_loads(result.pop("metadata_json", None), {})
    return result


def list_snapshots(
    base_path: str | Path,
    *,
    universe_id: str,
    branch_id: str | None = None,
) -> list[dict[str, Any]]:
    query = "SELECT * FROM universe_snapshots WHERE universe_id = ?"
    params: list[Any] = [universe_id]
    if branch_id:
        query += " AND branch_id = ?"
        params.append(branch_id)
    query += " ORDER BY created_at DESC, snapshot_id DESC"
    with _connect(base_path) as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    return [
        {**dict(row), "metadata": _json_loads(row["metadata_json"], {})}
        for row in rows
    ]


def register_author(
    base_path: str | Path,
    *,
    display_name: str,
    soul_text: str,
    created_by: str,
    lineage_parent_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    vote_id: str | None = None,
    reason: str = "",
) -> dict[str, Any]:
    author_id, soul_hash = _author_id_for(display_name, soul_text)
    with _connect(base_path) as conn:
        existing = conn.execute(
            "SELECT author_id FROM author_definitions WHERE display_name = ? COLLATE NOCASE",
            (display_name,),
        ).fetchone()
        if existing is not None and str(existing["author_id"]) != author_id:
            raise ValueError(f"Author display name already exists: {display_name}")
        conn.execute(
            """
            INSERT INTO author_definitions (
                author_id, display_name, soul_text, soul_hash, lineage_parent_id,
                reputation_score, created_at, metadata_json
            ) VALUES (?, ?, ?, ?, ?, 0.0, ?, ?)
            ON CONFLICT(author_id) DO NOTHING
            """,
            (
                author_id,
                display_name,
                soul_text,
                soul_hash,
                lineage_parent_id,
                _now(),
                _json_dumps(metadata or {}),
            ),
        )
        if lineage_parent_id:
            conn.execute(
                """
                INSERT OR IGNORE INTO author_forks (
                    fork_id, parent_author_id, child_author_id, proposed_by,
                    vote_id, reason, created_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"author-fork::{uuid.uuid4().hex}",
                    lineage_parent_id,
                    author_id,
                    created_by,
                    vote_id,
                    reason,
                    _now(),
                    _json_dumps(metadata or {}),
                ),
            )
    return get_author(base_path, author_id=author_id)


def list_authors(base_path: str | Path) -> list[dict[str, Any]]:
    with _connect(base_path) as conn:
        rows = conn.execute(
            "SELECT * FROM author_definitions ORDER BY created_at, author_id"
        ).fetchall()
    return [_author_from_row(row) for row in rows]


def get_author(base_path: str | Path, *, author_id: str) -> dict[str, Any]:
    with _connect(base_path) as conn:
        row = conn.execute(
            "SELECT * FROM author_definitions WHERE author_id = ?",
            (author_id,),
        ).fetchone()
        if row is None:
            raise KeyError(author_id)
        lineage = conn.execute(
            """
            SELECT * FROM author_forks
            WHERE parent_author_id = ? OR child_author_id = ?
            ORDER BY created_at
            """,
            (author_id, author_id),
        ).fetchall()
    result = _author_from_row(row)
    result["lineage"] = [
        {**dict(item), "metadata": _json_loads(item["metadata_json"], {})}
        for item in lineage
    ]
    return result


def spawn_runtime_instance(
    base_path: str | Path,
    *,
    universe_id: str,
    author_id: str,
    provider_name: str,
    model_name: str,
    created_by: str,
    branch_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    instance_id = f"runtime::{uuid.uuid4().hex}"
    with _connect(base_path) as conn:
        conn.execute(
            """
            INSERT INTO author_runtime_instances (
                instance_id, universe_id, author_id, provider_name, model_name,
                branch_id, status, created_by, created_at, updated_at, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, 'provisioned', ?, ?, ?, ?)
            """,
            (
                instance_id,
                universe_id,
                author_id,
                provider_name,
                model_name,
                branch_id,
                created_by,
                _now(),
                _now(),
                _json_dumps(metadata or {}),
            ),
        )
    return get_runtime_instance(base_path, instance_id=instance_id)


def retire_runtime_instance(
    base_path: str | Path,
    *,
    instance_id: str,
) -> dict[str, Any]:
    with _connect(base_path) as conn:
        conn.execute(
            """
            UPDATE author_runtime_instances
            SET status = 'retired', updated_at = ?
            WHERE instance_id = ?
            """,
            (_now(), instance_id),
        )
    return get_runtime_instance(base_path, instance_id=instance_id)


def get_runtime_instance(base_path: str | Path, *, instance_id: str) -> dict[str, Any]:
    with _connect(base_path) as conn:
        row = conn.execute(
            "SELECT * FROM author_runtime_instances WHERE instance_id = ?",
            (instance_id,),
        ).fetchone()
    if row is None:
        raise KeyError(instance_id)
    return _runtime_from_row(row)


def list_runtime_instances(
    base_path: str | Path,
    *,
    universe_id: str | None = None,
) -> list[dict[str, Any]]:
    query = "SELECT * FROM author_runtime_instances"
    params: tuple[Any, ...] = ()
    if universe_id:
        query += " WHERE universe_id = ?"
        params = (universe_id,)
    query += " ORDER BY created_at, instance_id"
    with _connect(base_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [_runtime_from_row(row) for row in rows]


def create_user_request(
    base_path: str | Path,
    *,
    universe_id: str,
    user_id: str,
    request_type: str,
    text: str,
    branch_id: str | None = None,
    preferred_author_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request_id = f"request::{uuid.uuid4().hex}"
    with _connect(base_path) as conn:
        conn.execute(
            """
            INSERT INTO user_requests (
                request_id, universe_id, branch_id, user_id, request_type, text,
                preferred_author_id, status, created_at, updated_at, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?)
            """,
            (
                request_id,
                universe_id,
                branch_id,
                user_id,
                request_type,
                text,
                preferred_author_id,
                _now(),
                _now(),
                _json_dumps(metadata or {}),
            ),
        )
    return get_user_request(base_path, request_id=request_id)


def get_user_request(base_path: str | Path, *, request_id: str) -> dict[str, Any]:
    with _connect(base_path) as conn:
        row = conn.execute(
            """
            SELECT r.*, a.username, a.display_name
            FROM user_requests AS r
            JOIN user_accounts AS a ON a.user_id = r.user_id
            WHERE r.request_id = ?
            """,
            (request_id,),
        ).fetchone()
    if row is None:
        raise KeyError(request_id)
    return _request_from_row(row)


def list_user_requests(base_path: str | Path, *, universe_id: str) -> list[dict[str, Any]]:
    with _connect(base_path) as conn:
        rows = conn.execute(
            """
            SELECT r.*, a.username, a.display_name
            FROM user_requests AS r
            JOIN user_accounts AS a ON a.user_id = r.user_id
            WHERE r.universe_id = ?
            ORDER BY r.created_at DESC, r.request_id DESC
            """,
            (universe_id,),
        ).fetchall()
    return [_request_from_row(row) for row in rows]


def list_active_user_ids(
    base_path: str | Path,
    *,
    max_idle_seconds: int = 30 * 24 * 3600,
) -> list[str]:
    threshold = _now() - max_idle_seconds
    with _connect(base_path) as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT user_id
            FROM user_sessions
            WHERE last_seen >= ?
            ORDER BY user_id
            """,
            (threshold,),
        ).fetchall()
    return [str(row["user_id"]) for row in rows]


def create_vote_window(
    base_path: str | Path,
    *,
    universe_id: str,
    vote_type: str,
    subject_type: str,
    subject_id: str,
    created_by: str,
    duration_seconds: int,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    vote_id = f"vote::{uuid.uuid4().hex}"
    full_payload = dict(payload or {})
    eligible_user_ids = list_active_user_ids(base_path)
    if created_by not in eligible_user_ids:
        eligible_user_ids.append(created_by)
    full_payload["eligible_user_ids"] = eligible_user_ids
    with _connect(base_path) as conn:
        conn.execute(
            """
            INSERT INTO vote_windows (
                vote_id, universe_id, vote_type, subject_type, subject_id,
                created_by, opens_at, closes_at, status, payload_json, result_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, '{}')
            """,
            (
                vote_id,
                universe_id,
                vote_type,
                subject_type,
                subject_id,
                created_by,
                _now(),
                _now() + duration_seconds,
                _json_dumps(full_payload),
            ),
        )
    return get_vote(base_path, vote_id=vote_id)


def propose_author_fork(
    base_path: str | Path,
    *,
    universe_id: str,
    author_id: str,
    display_name: str,
    soul_text: str,
    proposed_by: str,
    duration_seconds: int | None = None,
    metadata: dict[str, Any] | None = None,
    reason: str = "",
) -> dict[str, Any]:
    rules = get_universe_rules(base_path, universe_id=universe_id)
    return create_vote_window(
        base_path,
        universe_id=universe_id,
        vote_type="author_fork",
        subject_type="author_definition",
        subject_id=author_id,
        created_by=proposed_by,
        duration_seconds=duration_seconds or int(rules["quick_vote_seconds"]),
        payload={
            "display_name": display_name,
            "soul_text": soul_text,
            "lineage_parent_id": author_id,
            "metadata": dict(metadata or {}),
            "reason": reason,
        },
    )


def cast_vote(
    base_path: str | Path,
    *,
    vote_id: str,
    user_id: str,
    choice: str,
    comment: str = "",
) -> dict[str, Any]:
    normalized = choice.strip().lower()
    if normalized not in {"yes", "no", "abstain"}:
        raise ValueError("Invalid vote choice")
    with _connect(base_path) as conn:
        vote = conn.execute(
            "SELECT * FROM vote_windows WHERE vote_id = ?",
            (vote_id,),
        ).fetchone()
        if vote is None:
            raise KeyError(vote_id)
        if str(vote["status"]) != "open":
            raise ValueError("Vote is closed")
        conn.execute(
            """
            INSERT INTO vote_ballots (vote_id, user_id, choice, comment, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(vote_id, user_id) DO UPDATE SET
                choice=excluded.choice,
                comment=excluded.comment,
                created_at=excluded.created_at
            """,
            (vote_id, user_id, normalized, comment, _now()),
        )
    return get_vote(base_path, vote_id=vote_id)


def resolve_vote_if_due(
    base_path: str | Path,
    *,
    vote_id: str,
    force: bool = False,
) -> dict[str, Any]:
    with _connect(base_path) as conn:
        vote = conn.execute(
            "SELECT * FROM vote_windows WHERE vote_id = ?",
            (vote_id,),
        ).fetchone()
    if vote is None:
        raise KeyError(vote_id)
    if str(vote["status"]) != "open":
        return get_vote(base_path, vote_id=vote_id)
    if not force and float(vote["closes_at"]) > _now():
        return get_vote(base_path, vote_id=vote_id)
    with _connect(base_path) as conn:
        ballots = conn.execute(
            "SELECT choice FROM vote_ballots WHERE vote_id = ?",
            (vote_id,),
        ).fetchall()
    counts = {"yes": 0, "no": 0, "abstain": 0}
    for ballot in ballots:
        counts[str(ballot["choice"])] += 1
    result: dict[str, Any] = {
        "counts": counts,
        "passed": counts["yes"] > counts["no"] and counts["yes"] > 0,
        "resolved_at": _now(),
    }
    payload = _json_loads(vote["payload_json"], {})
    if str(vote["vote_type"]) == "author_fork" and result["passed"]:
        created = register_author(
            base_path,
            display_name=str(payload.get("display_name", "Forked Author")),
            soul_text=str(payload.get("soul_text", "")),
            created_by=str(vote["created_by"]),
            lineage_parent_id=str(payload.get("lineage_parent_id") or vote["subject_id"]),
            metadata=dict(payload.get("metadata", {})),
            vote_id=str(vote["vote_id"]),
            reason=str(payload.get("reason", "")),
        )
        result["created_author_id"] = created["author_id"]
    with _connect(base_path) as conn:
        conn.execute(
            "UPDATE vote_windows SET status = 'resolved', result_json = ? WHERE vote_id = ?",
            (_json_dumps(result), vote_id),
        )
    return get_vote(base_path, vote_id=vote_id)


def get_vote(base_path: str | Path, *, vote_id: str) -> dict[str, Any]:
    with _connect(base_path) as conn:
        vote = conn.execute(
            "SELECT * FROM vote_windows WHERE vote_id = ?",
            (vote_id,),
        ).fetchone()
    if vote is None:
        raise KeyError(vote_id)
    if str(vote["status"]) == "open" and float(vote["closes_at"]) <= _now():
        return resolve_vote_if_due(base_path, vote_id=vote_id, force=True)
    with _connect(base_path) as conn:
        ballots = conn.execute(
            """
            SELECT b.*, a.username, a.display_name
            FROM vote_ballots AS b
            JOIN user_accounts AS a ON a.user_id = b.user_id
            WHERE b.vote_id = ?
            ORDER BY b.created_at, b.user_id
            """,
            (vote_id,),
        ).fetchall()
    return {
        "vote_id": str(vote["vote_id"]),
        "universe_id": str(vote["universe_id"]),
        "vote_type": str(vote["vote_type"]),
        "subject_type": str(vote["subject_type"]),
        "subject_id": str(vote["subject_id"]),
        "created_by": str(vote["created_by"]),
        "opens_at": float(vote["opens_at"]),
        "closes_at": float(vote["closes_at"]),
        "status": str(vote["status"]),
        "payload": _json_loads(vote["payload_json"], {}),
        "result": _json_loads(vote["result_json"], {}),
        "ballots": [
            {
                "user_id": str(row["user_id"]),
                "username": str(row["username"]),
                "display_name": str(row["display_name"]),
                "choice": str(row["choice"]),
                "comment": str(row["comment"]),
                "created_at": float(row["created_at"]),
            }
            for row in ballots
        ],
    }


def record_action(
    base_path: str | Path,
    *,
    universe_id: str | None,
    actor_type: str,
    actor_id: str,
    action_type: str,
    target_type: str,
    target_id: str,
    summary: str,
    payload: dict[str, Any] | None = None,
    visibility: str = "public",
) -> dict[str, Any]:
    action_id = f"action::{uuid.uuid4().hex}"
    with _connect(base_path) as conn:
        conn.execute(
            """
            INSERT INTO action_records (
                action_id, universe_id, visibility, actor_type, actor_id,
                action_type, target_type, target_id, summary, created_at, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                action_id,
                universe_id,
                visibility,
                actor_type,
                actor_id,
                action_type,
                target_type,
                target_id,
                summary,
                _now(),
                _json_dumps(payload or {}),
            ),
        )
    return {
        "action_id": action_id,
        "universe_id": universe_id,
        "actor_type": actor_type,
        "actor_id": actor_id,
        "action_type": action_type,
        "target_type": target_type,
        "target_id": target_id,
        "summary": summary,
        "payload": dict(payload or {}),
        "visibility": visibility,
    }


def list_actions(
    base_path: str | Path,
    *,
    universe_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    query = "SELECT * FROM action_records"
    params: list[Any] = []
    if universe_id:
        query += " WHERE universe_id = ?"
        params.append(universe_id)
    query += " ORDER BY created_at DESC, action_id DESC LIMIT ?"
    params.append(limit)
    with _connect(base_path) as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    return [
        {**dict(row), "payload": _json_loads(row["payload_json"], {})}
        for row in rows
    ]


def _notes_json_path(universe_path: str | Path) -> Path:
    return Path(universe_path) / "notes.json"


def list_note_dicts(
    universe_path: str | Path,
    *,
    source: str | None = None,
    category: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    base_path = base_path_from_universe(universe_path)
    universe_id = universe_id_from_path(universe_path)
    ensure_universe_registered(
        base_path,
        universe_id=universe_id,
        universe_path=universe_path,
    )
    _bootstrap_notes_from_json(universe_path)
    clauses = ["universe_id = ?"]
    params: list[Any] = [universe_id]
    if source:
        clauses.append("source = ?")
        params.append(source)
    if category:
        clauses.append("category = ?")
        params.append(category)
    if status:
        clauses.append("status = ?")
        params.append(status)
    with _connect(base_path) as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM universe_notes
            WHERE {}
            ORDER BY timestamp, note_id
            """.format(" AND ".join(clauses)),
            tuple(params),
        ).fetchall()
    return [_note_from_row(row) for row in rows]


def add_note_dict(universe_path: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    base_path = base_path_from_universe(universe_path)
    universe_id = universe_id_from_path(universe_path)
    ensure_universe_registered(
        base_path,
        universe_id=universe_id,
        universe_path=universe_path,
    )
    _bootstrap_notes_from_json(universe_path)
    note = {
        "id": str(payload.get("id", uuid.uuid4())),
        "source": str(payload.get("source", "system")),
        "text": str(payload.get("text", "")),
        "category": str(payload.get("category", "observation")),
        "status": str(payload.get("status", "unread")),
        "target": payload.get("target"),
        "clearly_wrong": bool(payload.get("clearly_wrong", False)),
        "quoted_passage": str(payload.get("quoted_passage", "")),
        "tags": list(payload.get("tags", []))
        if isinstance(payload.get("tags"), list) else [],
        "metadata": dict(payload.get("metadata", {}))
        if isinstance(payload.get("metadata"), dict) else {},
        "timestamp": float(payload.get("timestamp", _now())),
    }
    with _connect(base_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO universe_notes (
                note_id, universe_id, source, text, category, status, target,
                clearly_wrong, quoted_passage, tags_json, metadata_json,
                timestamp, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                note["id"],
                universe_id,
                note["source"],
                note["text"],
                note["category"],
                note["status"],
                note["target"],
                1 if note["clearly_wrong"] else 0,
                note["quoted_passage"],
                _json_dumps(note["tags"]),
                _json_dumps(note["metadata"]),
                note["timestamp"],
                _now(),
            ),
        )
    _mirror_notes_json(universe_path)
    return note


def add_note_dicts_bulk(universe_path: str | Path, payloads: list[dict[str, Any]]) -> None:
    if not payloads:
        return
    for payload in payloads:
        add_note_dict(universe_path, payload)


def update_note_status_record(
    universe_path: str | Path,
    note_id: str,
    status: str,
) -> bool:
    base_path = base_path_from_universe(universe_path)
    universe_id = universe_id_from_path(universe_path)
    _bootstrap_notes_from_json(universe_path)
    with _connect(base_path) as conn:
        row = conn.execute(
            """
            SELECT note_id
            FROM universe_notes
            WHERE universe_id = ? AND note_id = ?
            """,
            (universe_id, note_id),
        ).fetchone()
        if row is None:
            return False
        conn.execute(
            """
            UPDATE universe_notes
            SET status = ?, updated_at = ?
            WHERE universe_id = ? AND note_id = ?
            """,
            (status, _now(), universe_id, note_id),
        )
    _mirror_notes_json(universe_path)
    return True


def bulk_update_note_status_records(
    universe_path: str | Path,
    note_ids: list[str],
    status: str,
) -> int:
    if not note_ids:
        return 0
    count = 0
    for note_id in note_ids:
        if update_note_status_record(universe_path, note_id, status):
            count += 1
    return count


def delete_note_record(universe_path: str | Path, note_id: str) -> bool:
    base_path = base_path_from_universe(universe_path)
    universe_id = universe_id_from_path(universe_path)
    _bootstrap_notes_from_json(universe_path)
    with _connect(base_path) as conn:
        result = conn.execute(
            "DELETE FROM universe_notes WHERE universe_id = ? AND note_id = ?",
            (universe_id, note_id),
        )
    deleted = result.rowcount > 0
    if deleted:
        _mirror_notes_json(universe_path)
    return deleted


def list_work_target_dicts(universe_path: str | Path) -> list[dict[str, Any]]:
    base_path = base_path_from_universe(universe_path)
    universe_id = universe_id_from_path(universe_path)
    ensure_universe_registered(
        base_path,
        universe_id=universe_id,
        universe_path=universe_path,
    )
    _bootstrap_payload_table_from_json(
        universe_path,
        table="universe_work_targets",
        id_field="target_id",
        path=Path(universe_path) / "work_targets.json",
    )
    with _connect(base_path) as conn:
        rows = conn.execute(
            """
            SELECT payload_json
            FROM universe_work_targets
            WHERE universe_id = ?
            ORDER BY updated_at, target_id
            """,
            (universe_id,),
        ).fetchall()
    return [_json_loads(row["payload_json"], {}) for row in rows]


def upsert_work_target_dict(universe_path: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    base_path = base_path_from_universe(universe_path)
    universe_id = universe_id_from_path(universe_path)
    ensure_universe_registered(
        base_path,
        universe_id=universe_id,
        universe_path=universe_path,
    )
    _bootstrap_payload_table_from_json(
        universe_path,
        table="universe_work_targets",
        id_field="target_id",
        path=Path(universe_path) / "work_targets.json",
    )
    with _connect(base_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO universe_work_targets (
                universe_id, target_id, payload_json, updated_at
            ) VALUES (?, ?, ?, ?)
            """,
            (
                universe_id,
                str(payload.get("target_id", "")),
                _json_dumps(payload),
                _now(),
            ),
        )
    _mirror_payload_table_to_json(
        universe_path,
        table="universe_work_targets",
        path=Path(universe_path) / "work_targets.json",
    )
    return payload


def replace_work_target_dicts(universe_path: str | Path, payloads: list[dict[str, Any]]) -> None:
    base_path = base_path_from_universe(universe_path)
    universe_id = universe_id_from_path(universe_path)
    ensure_universe_registered(
        base_path,
        universe_id=universe_id,
        universe_path=universe_path,
    )
    with _connect(base_path) as conn:
        conn.execute(
            "DELETE FROM universe_work_targets WHERE universe_id = ?",
            (universe_id,),
        )
        for payload in payloads:
            conn.execute(
                """
                INSERT INTO universe_work_targets (
                    universe_id, target_id, payload_json, updated_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    universe_id,
                    str(payload.get("target_id", "")),
                    _json_dumps(payload),
                    _now(),
                ),
            )
    _mirror_payload_table_to_json(
        universe_path,
        table="universe_work_targets",
        path=Path(universe_path) / "work_targets.json",
    )


def list_hard_priority_dicts(universe_path: str | Path) -> list[dict[str, Any]]:
    base_path = base_path_from_universe(universe_path)
    universe_id = universe_id_from_path(universe_path)
    ensure_universe_registered(
        base_path,
        universe_id=universe_id,
        universe_path=universe_path,
    )
    _bootstrap_payload_table_from_json(
        universe_path,
        table="universe_hard_priorities",
        id_field="priority_id",
        path=Path(universe_path) / "hard_priorities.json",
    )
    with _connect(base_path) as conn:
        rows = conn.execute(
            """
            SELECT payload_json
            FROM universe_hard_priorities
            WHERE universe_id = ?
            ORDER BY updated_at, priority_id
            """,
            (universe_id,),
        ).fetchall()
    return [_json_loads(row["payload_json"], {}) for row in rows]


def upsert_hard_priority_dict(universe_path: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    base_path = base_path_from_universe(universe_path)
    universe_id = universe_id_from_path(universe_path)
    ensure_universe_registered(
        base_path,
        universe_id=universe_id,
        universe_path=universe_path,
    )
    _bootstrap_payload_table_from_json(
        universe_path,
        table="universe_hard_priorities",
        id_field="priority_id",
        path=Path(universe_path) / "hard_priorities.json",
    )
    with _connect(base_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO universe_hard_priorities (
                universe_id, priority_id, payload_json, updated_at
            ) VALUES (?, ?, ?, ?)
            """,
            (
                universe_id,
                str(payload.get("priority_id", "")),
                _json_dumps(payload),
                _now(),
            ),
        )
    _mirror_payload_table_to_json(
        universe_path,
        table="universe_hard_priorities",
        path=Path(universe_path) / "hard_priorities.json",
    )
    return payload


def replace_hard_priority_dicts(universe_path: str | Path, payloads: list[dict[str, Any]]) -> None:
    base_path = base_path_from_universe(universe_path)
    universe_id = universe_id_from_path(universe_path)
    ensure_universe_registered(
        base_path,
        universe_id=universe_id,
        universe_path=universe_path,
    )
    with _connect(base_path) as conn:
        conn.execute(
            "DELETE FROM universe_hard_priorities WHERE universe_id = ?",
            (universe_id,),
        )
        for payload in payloads:
            conn.execute(
                """
                INSERT INTO universe_hard_priorities (
                    universe_id, priority_id, payload_json, updated_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    universe_id,
                    str(payload.get("priority_id", "")),
                    _json_dumps(payload),
                    _now(),
                ),
            )
    _mirror_payload_table_to_json(
        universe_path,
        table="universe_hard_priorities",
        path=Path(universe_path) / "hard_priorities.json",
    )


def _bootstrap_notes_from_json(universe_path: str | Path) -> None:
    base_path = base_path_from_universe(universe_path)
    universe_id = universe_id_from_path(universe_path)
    path = _notes_json_path(universe_path)
    with _connect(base_path) as conn:
        existing = conn.execute(
            "SELECT 1 FROM universe_notes WHERE universe_id = ? LIMIT 1",
            (universe_id,),
        ).fetchone()
        if existing is not None or not path.exists():
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(raw, list):
            return
        for item in raw:
            if not isinstance(item, dict):
                continue
            conn.execute(
                """
                INSERT OR IGNORE INTO universe_notes (
                    note_id, universe_id, source, text, category, status,
                    target, clearly_wrong, quoted_passage, tags_json,
                    metadata_json, timestamp, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(item.get("id", uuid.uuid4())),
                    universe_id,
                    str(item.get("source", "system")),
                    str(item.get("text", "")),
                    str(item.get("category", "observation")),
                    str(item.get("status", "unread")),
                    item.get("target"),
                    1 if item.get("clearly_wrong", False) else 0,
                    str(item.get("quoted_passage", "")),
                    _json_dumps(item.get("tags", [])),
                    _json_dumps(item.get("metadata", {})),
                    float(item.get("timestamp", _now())),
                    _now(),
                ),
            )


def _bootstrap_payload_table_from_json(
    universe_path: str | Path,
    *,
    table: str,
    id_field: str,
    path: Path,
) -> None:
    base_path = base_path_from_universe(universe_path)
    universe_id = universe_id_from_path(universe_path)
    with _connect(base_path) as conn:
        existing = conn.execute(
            f"SELECT 1 FROM {table} WHERE universe_id = ? LIMIT 1",
            (universe_id,),
        ).fetchone()
        if existing is not None or not path.exists():
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(raw, list):
            return
        for item in raw:
            if not isinstance(item, dict):
                continue
            identifier = str(item.get(id_field, ""))
            if not identifier:
                continue
            conn.execute(
                f"""
                INSERT OR IGNORE INTO {table} (
                    universe_id, {id_field}, payload_json, updated_at
                ) VALUES (?, ?, ?, ?)
                """,
                (universe_id, identifier, _json_dumps(item), _now()),
            )


def _mirror_notes_json(universe_path: str | Path) -> None:
    base_path = base_path_from_universe(universe_path)
    universe_id = universe_id_from_path(universe_path)
    with _connect(base_path) as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM universe_notes
            WHERE universe_id = ?
            ORDER BY timestamp, note_id
            """,
            (universe_id,),
        ).fetchall()
    payload = [_note_from_row(row) for row in rows]
    path = _notes_json_path(universe_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )


def _mirror_payload_table_to_json(
    universe_path: str | Path,
    *,
    table: str,
    path: Path,
) -> None:
    base_path = base_path_from_universe(universe_path)
    universe_id = universe_id_from_path(universe_path)
    with _connect(base_path) as conn:
        rows = conn.execute(
            f"""
            SELECT payload_json
            FROM {table}
            WHERE universe_id = ?
            ORDER BY updated_at
            """,
            (universe_id,),
        ).fetchall()
    payload = [_json_loads(row["payload_json"], {}) for row in rows]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _note_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": str(row["note_id"]),
        "source": str(row["source"]),
        "text": str(row["text"]),
        "category": str(row["category"]),
        "status": str(row["status"]),
        "target": row["target"],
        "clearly_wrong": bool(row["clearly_wrong"]),
        "quoted_passage": str(row["quoted_passage"]),
        "tags": _json_loads(row["tags_json"], []),
        "metadata": _json_loads(row["metadata_json"], {}),
        "timestamp": float(row["timestamp"]),
    }


def _branch_from_row(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    result["is_public"] = bool(result["is_public"])
    result["metadata"] = _json_loads(result.pop("metadata_json", None), {})
    return result


def _author_from_row(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    result["metadata"] = _json_loads(result.pop("metadata_json", None), {})
    return result


def _runtime_from_row(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    result["metadata"] = _json_loads(result.pop("metadata_json", None), {})
    return result


def _request_from_row(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    result["metadata"] = _json_loads(result.pop("metadata_json", None), {})
    return result


def _branch_def_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "branch_def_id": row["branch_def_id"],
        "name": row["name"],
        "description": row["description"],
        "author": row["author"],
        "domain_id": row["domain_id"],
        "tags": _json_loads(row["tags_json"], []),
        "version": row["version"],
        "parent_def_id": row["parent_def_id"],
        "entry_point": row["entry_point"],
        "graph": _json_loads(row["graph_json"], {}),
        "node_defs": _json_loads(row["node_defs_json"], []),
        "state_schema": _json_loads(row["state_schema_json"], []),
        "published": bool(row["published"]),
        "stats": _json_loads(row["stats_json"], {}),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Community Branches — CRUD
# ═══════════════════════════════════════════════════════════════════════════


def save_branch_definition(
    base_path: str | Path,
    *,
    branch_def: dict[str, Any],
) -> dict[str, Any]:
    """Insert or replace a branch definition.

    Accepts a dict matching BranchDefinition.to_dict(). Graph topology
    (graph_nodes + edges + conditional_edges) is stored in graph_json.
    Node definitions are stored separately in node_defs_json. State
    schema is an unvalidated JSON blob in state_schema_json.

    Also accepts legacy format with "nodes" key (flat node list stored
    in graph_json for backward compatibility during migration).
    """
    now = _now()
    branch_def_id = branch_def.get("branch_def_id", uuid.uuid4().hex[:12])

    # Build graph topology JSON (LangGraph-native shape)
    graph = {
        "nodes": branch_def.get("graph_nodes", []),
        "edges": branch_def.get("edges", []),
        "conditional_edges": branch_def.get("conditional_edges", []),
        "entry_point": branch_def.get("entry_point", ""),
    }

    # Legacy compat: if "nodes" key exists and graph_nodes doesn't,
    # store nodes in graph_json (migration path from old format)
    if not graph["nodes"] and "nodes" in branch_def:
        graph["nodes"] = branch_def["nodes"]

    # Node definitions — separate from graph topology
    node_defs = branch_def.get("node_defs", [])

    with _connect(base_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO branch_definitions (
                branch_def_id, name, description, author, domain_id,
                tags_json, version, parent_def_id, entry_point,
                graph_json, node_defs_json, state_schema_json,
                published, stats_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                branch_def_id,
                branch_def.get("name", ""),
                branch_def.get("description", ""),
                branch_def.get("author", "anonymous"),
                branch_def.get("domain_id", "fantasy_author"),
                _json_dumps(branch_def.get("tags", [])),
                branch_def.get("version", 1),
                branch_def.get("parent_def_id"),
                branch_def.get("entry_point", ""),
                _json_dumps(graph),
                _json_dumps(node_defs),
                _json_dumps(branch_def.get("state_schema", [])),
                1 if branch_def.get("published") else 0,
                _json_dumps(branch_def.get("stats", {})),
                branch_def.get("created_at", now),
                now,
            ),
        )
    return get_branch_definition(base_path, branch_def_id=branch_def_id)


def get_branch_definition(
    base_path: str | Path,
    *,
    branch_def_id: str,
) -> dict[str, Any]:
    """Retrieve a single branch definition by ID."""
    with _connect(base_path) as conn:
        row = conn.execute(
            "SELECT * FROM branch_definitions WHERE branch_def_id = ?",
            (branch_def_id,),
        ).fetchone()
    if row is None:
        raise KeyError(branch_def_id)
    return _branch_def_from_row(row)


def list_branch_definitions(
    base_path: str | Path,
    *,
    published_only: bool = False,
    author: str = "",
    domain_id: str = "",
    tag: str = "",
    name_contains: str = "",
) -> list[dict[str, Any]]:
    """List branch definitions with optional filters.

    Args:
        published_only: If True, return only published branches.
        author: Filter by author name (exact match).
        domain_id: Filter by domain (exact match).
        tag: Filter by tag (substring match in JSON array).
        name_contains: Filter by name (case-insensitive substring).
    """
    clauses: list[str] = []
    params: list[Any] = []

    if published_only:
        clauses.append("published = 1")
    if author:
        clauses.append("author = ?")
        params.append(author)
    if domain_id:
        clauses.append("domain_id = ?")
        params.append(domain_id)
    if tag:
        clauses.append("tags_json LIKE ?")
        params.append(f'%"{tag}"%')
    if name_contains:
        clauses.append("name LIKE ?")
        params.append(f"%{name_contains}%")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with _connect(base_path) as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM branch_definitions
            {where}
            ORDER BY updated_at DESC
            """,
            params,
        ).fetchall()
    return [_branch_def_from_row(row) for row in rows]


def update_branch_definition(
    base_path: str | Path,
    *,
    branch_def_id: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    """Update specific fields of a branch definition.

    Supports updating: name, description, domain_id, tags, version,
    entry_point, graph_nodes, edges, conditional_edges, node_defs,
    state_schema, published, stats. Also accepts legacy "nodes" key.
    """
    now = _now()
    sets: list[str] = ["updated_at = ?"]
    params: list[Any] = [now]

    simple_fields = {
        "name": "name",
        "description": "description",
        "author": "author",
        "domain_id": "domain_id",
        "version": "version",
        "entry_point": "entry_point",
    }
    for key, col in simple_fields.items():
        if key in updates:
            sets.append(f"{col} = ?")
            params.append(updates[key])

    json_fields = {
        "tags": "tags_json",
        "stats": "stats_json",
        "state_schema": "state_schema_json",
    }
    for key, col in json_fields.items():
        if key in updates:
            sets.append(f"{col} = ?")
            params.append(_json_dumps(updates[key]))

    if "published" in updates:
        sets.append("published = ?")
        params.append(1 if updates["published"] else 0)

    # Update node_defs separately from graph topology
    if "node_defs" in updates:
        sets.append("node_defs_json = ?")
        params.append(_json_dumps(updates["node_defs"]))

    # If graph topology fields are updated, rebuild graph_json
    graph_keys = {"graph_nodes", "edges", "conditional_edges", "nodes"}
    if graph_keys & updates.keys():
        existing = get_branch_definition(base_path, branch_def_id=branch_def_id)
        graph = existing.get("graph", {})
        if "graph_nodes" in updates:
            graph["nodes"] = updates["graph_nodes"]
        elif "nodes" in updates:
            # Legacy compat
            graph["nodes"] = updates["nodes"]
        if "edges" in updates:
            graph["edges"] = updates["edges"]
        if "conditional_edges" in updates:
            graph["conditional_edges"] = updates["conditional_edges"]
        if "entry_point" in updates:
            graph["entry_point"] = updates["entry_point"]
        sets.append("graph_json = ?")
        params.append(_json_dumps(graph))

    params.append(branch_def_id)

    with _connect(base_path) as conn:
        conn.execute(
            f"UPDATE branch_definitions SET {', '.join(sets)} "
            f"WHERE branch_def_id = ?",
            params,
        )
    return get_branch_definition(base_path, branch_def_id=branch_def_id)


def delete_branch_definition(
    base_path: str | Path,
    *,
    branch_def_id: str,
) -> bool:
    """Delete a branch definition. Returns True if a row was deleted."""
    with _connect(base_path) as conn:
        cursor = conn.execute(
            "DELETE FROM branch_definitions WHERE branch_def_id = ?",
            (branch_def_id,),
        )
    return cursor.rowcount > 0


def fork_branch_definition(
    base_path: str | Path,
    *,
    branch_def_id: str,
    new_name: str = "",
    author: str = "anonymous",
) -> dict[str, Any]:
    """Fork an existing branch definition.

    Creates a new branch with a new ID, version reset to 1, and
    parent_def_id set to the source branch for lineage tracking.
    """
    from fantasy_author.branches import BranchDefinition

    source = get_branch_definition(base_path, branch_def_id=branch_def_id)

    # from_dict handles the DB row shape (nested "graph" dict) directly
    branch = BranchDefinition.from_dict(source)
    forked = branch.fork(new_name=new_name, author=author)

    # Increment fork count on source
    stats = source.get("stats", {})
    stats["fork_count"] = stats.get("fork_count", 0) + 1
    update_branch_definition(
        base_path, branch_def_id=branch_def_id, updates={"stats": stats}
    )

    return save_branch_definition(base_path, branch_def=forked.to_dict())
