"""Bounded-context storage layers for the multiplayer engine.

Second canonical Module Layout subpackage (after ``workflow/bid/``) per
PLAN.md §Module Layout. Replaces the 3,575-LOC ``workflow/daemon_server.py``
god-module with per-context submodules:

- ``accounts`` — user accounts + auth + sessions + capabilities
- ``universes_branches`` — universes + branches + snapshots + ACLs
- ``daemons`` — daemon (author) definitions + forks + runtime instances
- ``requests_votes`` — user requests + vote windows + ballots + action records
- ``notes_work_targets`` — universe notes + work-targets + hard priorities
- ``goals_gates`` — goals + gate-claims + leaderboard reads

This ``__init__.py`` hosts the shared primitives every context module
needs: path helpers, the ``_connect()`` factory, and the constants +
JSON + slug utilities that were previously at the top of
``daemon_server.py``.

R7 ship sequence (see
``docs/exec-plans/active/2026-04-19-storage-package-split.md``):

- Commit 1 (this commit): shared helpers + constants. ``daemon_server.py``
  imports the helpers back from here rather than duplicating them.
- Commits 2-6: per-bounded-context split.

Per the foundation-end-state rule (``CLAUDE_LEAD_OPS.md
§Foundation End-State``): each commit is itself end-state-shaped —
the helpers move to their final path in commit 1, not to a temporary
intermediate file.
"""

from __future__ import annotations

import hashlib  # noqa: F401  (re-exported for legacy callers of daemon_server)
import json
import secrets  # noqa: F401  (re-exported for legacy callers of daemon_server)
import sqlite3
import time
import uuid  # noqa: F401  (re-exported for legacy callers of daemon_server)
from pathlib import Path
from typing import Any

# -------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------

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


# -------------------------------------------------------------------
# JSON + slug helpers
# -------------------------------------------------------------------


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


# -------------------------------------------------------------------
# Path resolution
# -------------------------------------------------------------------


def data_dir() -> Path:
    """Return the on-disk root for all Workflow daemon state.

    Canonical env var: ``WORKFLOW_DATA_DIR``.

    Resolution order (first match wins):
      1. ``$WORKFLOW_DATA_DIR`` if set and non-empty.
      2. Legacy ``$UNIVERSE_SERVER_BASE`` if set and non-empty. Emits a
         deprecation warning when ``WORKFLOW_DEPRECATIONS=1`` so the
         legacy name can be found and updated without noise in normal
         operation.
      3. Platform default:
         - Windows: ``%APPDATA%\\Workflow`` if ``APPDATA`` is set, else
           ``Path.home() / 'AppData' / 'Roaming' / 'Workflow'``.
         - macOS / Linux / container: ``~/.workflow``.

    Always returns an absolute, resolved Path. Callers should NOT re-resolve
    or re-expand; this function is the single source of truth for the
    daemon's on-disk root so that a containerized deploy setting
    ``WORKFLOW_DATA_DIR=/data`` gets all writes inside the bind-mount.

    The previous shape (``UNIVERSE_SERVER_BASE`` defaulting to CWD-relative
    ``"output"``) produced the 2026-04-19 container CWD-drift bug: running
    the daemon from ``/app`` wrote to ``/app/output`` instead of
    ``/data``. This function eliminates that class by refusing to return
    CWD-relative paths.

    Notes
    -----
    - This is the *root* for all on-disk state, not the universe dir.
      Per-universe directories sit under this root. The previous
      ``UNIVERSE_SERVER_BASE`` conflated the two; the new contract is
      that ``WORKFLOW_DATA_DIR`` is the root (e.g., ``/data``) and
      universes are subdirectories (e.g., ``/data/my-universe``).
    - The directory is not created here. Callers that write into it
      are responsible for ``mkdir(parents=True, exist_ok=True)``.
    """
    import os
    import warnings

    explicit = os.environ.get("WORKFLOW_DATA_DIR", "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()

    legacy = os.environ.get("UNIVERSE_SERVER_BASE", "").strip()
    if legacy:
        if os.environ.get("WORKFLOW_DEPRECATIONS", "").strip() in {"1", "true", "yes"}:
            warnings.warn(
                "UNIVERSE_SERVER_BASE is deprecated; migrate to "
                "WORKFLOW_DATA_DIR. Both currently resolve to the same "
                "path; UNIVERSE_SERVER_BASE will be removed in a future "
                "release.",
                DeprecationWarning,
                stacklevel=2,
            )
        return Path(legacy).expanduser().resolve()

    # Platform default.
    appdata = os.environ.get("APPDATA", "").strip()
    if appdata and os.name == "nt":
        return (Path(appdata) / "Workflow").resolve()
    if os.name == "nt":
        # Windows without APPDATA (unusual) — fall back to the standard
        # user path rather than ~/.workflow.
        return (Path.home() / "AppData" / "Roaming" / "Workflow").resolve()
    return (Path.home() / ".workflow").resolve()


def wiki_path() -> Path:
    """Return the on-disk root for the knowledge wiki.

    Canonical env var: ``WORKFLOW_WIKI_PATH``.

    Resolution order (first match wins):
      1. ``$WORKFLOW_WIKI_PATH`` if set and non-empty.
      2. Legacy ``$WIKI_PATH`` if set and non-empty. Emits a
         deprecation warning when ``WORKFLOW_DEPRECATIONS=1``.
      3. Platform default: ``data_dir() / "wiki"`` — inherits the
         canonical data root's platform handling (Windows
         ``%APPDATA%\\Workflow\\wiki``; Linux/macOS ``~/.workflow/wiki``).

    Pre-2026-04-20 the wiki fallback was hardcoded
    ``r"C:\\Users\\Jonathan\\Projects\\Wiki"`` in
    ``workflow/universe_server.py`` — broke every non-host deploy +
    leaked the developer's username into docs. Using this resolver
    closes that class the same way ``data_dir`` did for universe state.

    Returns an absolute, resolved Path. Does not create the directory;
    callers mkdir on first write.
    """
    import os
    import warnings

    explicit = os.environ.get("WORKFLOW_WIKI_PATH", "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()

    legacy = os.environ.get("WIKI_PATH", "").strip()
    if legacy:
        if os.environ.get("WORKFLOW_DEPRECATIONS", "").strip() in {"1", "true", "yes"}:
            warnings.warn(
                "WIKI_PATH is deprecated; migrate to WORKFLOW_WIKI_PATH. "
                "Both currently resolve to the same path; WIKI_PATH will "
                "be removed in a future release.",
                DeprecationWarning,
                stacklevel=2,
            )
        return Path(legacy).expanduser().resolve()

    # Platform default — inherit data_dir's platform handling.
    return (data_dir() / "wiki").resolve()


def author_server_db_path(base_path: str | Path) -> Path:
    return Path(base_path) / DB_FILENAME


def base_path_from_universe(universe_path: str | Path) -> Path:
    return Path(universe_path).resolve().parent


def universe_id_from_path(universe_path: str | Path) -> str:
    return Path(universe_path).resolve().name


# -------------------------------------------------------------------
# SQLite connection factory
# -------------------------------------------------------------------


def _connect(base_path: str | Path) -> sqlite3.Connection:
    db_path = author_server_db_path(base_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


__all__ = [
    # Constants
    "DB_FILENAME",
    "DEFAULT_BRANCH_MODE",
    "DEFAULT_QUICK_VOTE_SECONDS",
    "SESSION_PREFIX",
    "CAP_READ_PUBLIC_UNIVERSE",
    "CAP_SUBMIT_REQUEST",
    "CAP_FORK_BRANCH",
    "CAP_PROPOSE_AUTHOR_FORK",
    "CAP_SPAWN_RUNTIME_CAPACITY",
    "CAP_ASSIGN_RUNTIME_PROVIDER",
    "CAP_PAUSE_RESUME_SERVER",
    "CAP_ROLLBACK_BRANCH",
    "CAP_PROMOTE_BRANCH",
    "CAP_SUPERSEDE_BRANCH",
    "CAP_EDIT_UNIVERSE_RULES",
    "CAP_GRANT_CAPABILITIES",
    "ALL_CAPABILITIES",
    "DEFAULT_USER_CAPABILITIES",
    # Helpers
    "_now",
    "_json_dumps",
    "_json_loads",
    "_slugify",
    "author_server_db_path",
    "base_path_from_universe",
    "data_dir",
    "universe_id_from_path",
    "wiki_path",
    "_connect",
    # Accounts bounded context
    "_account_id_for_username",
    "actor_has_capability",
    "create_or_update_account",
    "create_session",
    "ensure_host_account",
    "get_account",
    "grant_capabilities",
    "list_accounts",
    "list_capabilities",
    "resolve_bearer_token",
]


# -------------------------------------------------------------------
# Bounded-context re-exports — lazy via PEP-562 ``__getattr__``
# -------------------------------------------------------------------
#
# Rationale (docs/design-notes/2026-04-19-storage-init-stale-bytecode-
# mitigation.md Option A): eager re-exports at module-body tail created
# a circular-import window (``accounts.py`` top-imports constants from
# ``workflow.storage``; this file end-imports functions from
# ``accounts``). Worked by accident of ordering. The 2026-04-19 P0
# exposed the fragility when R7a symbol additions raced process restart.
#
# The lazy shape below means a fresh ``from workflow.storage.accounts
# import ...`` runs only at first attribute access, AFTER the package
# body has fully bound its constants. Same public API (``from
# workflow.storage import ensure_host_account`` etc. still works per
# Python's ``from`` import resolution protocol).
#
# ``__all__`` still enumerates every re-export so that ``import *``,
# static analyzers, and the import-graph smoke test can discover them.


_LAZY_IMPORTS = {
    # name -> (submodule, attr). Submodule path is relative to
    # ``workflow.storage``; attr is the name to look up on the submodule.
    "_account_id_for_username": ("accounts", "_account_id_for_username"),
    "actor_has_capability":     ("accounts", "actor_has_capability"),
    "create_or_update_account": ("accounts", "create_or_update_account"),
    "create_session":           ("accounts", "create_session"),
    "ensure_host_account":      ("accounts", "ensure_host_account"),
    "get_account":              ("accounts", "get_account"),
    "grant_capabilities":       ("accounts", "grant_capabilities"),
    "list_accounts":            ("accounts", "list_accounts"),
    "list_capabilities":        ("accounts", "list_capabilities"),
    "resolve_bearer_token":     ("accounts", "resolve_bearer_token"),
}


def __getattr__(name: str) -> Any:  # PEP-562
    """Resolve re-exported names against the current submodule state.

    Cache the resolved value on the package so subsequent accesses are
    O(1) and participate in ``dir()`` discovery. Missing names raise
    ``AttributeError`` (standard module-attribute contract).
    """
    if name in _LAZY_IMPORTS:
        import importlib
        submodule, attr = _LAZY_IMPORTS[name]
        mod = importlib.import_module(f"workflow.storage.{submodule}")
        try:
            value = getattr(mod, attr)
        except AttributeError as exc:
            raise AttributeError(
                f"module 'workflow.storage' lazy-import target "
                f"'workflow.storage.{submodule}' has no attribute {attr!r}"
            ) from exc
        globals()[name] = value  # cache for subsequent accesses
        return value
    raise AttributeError(f"module 'workflow.storage' has no attribute {name!r}")


def __dir__() -> list[str]:  # PEP-562 pair — supports ``dir(workflow.storage)``
    return sorted(set(globals()) | set(_LAZY_IMPORTS))
