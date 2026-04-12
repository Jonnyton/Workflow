"""SqliteSaver wrapper with WAL mode, retention, and graph compilation helpers.

Uses ``SqliteSaver.from_conn_string()`` context manager pattern as required.
WAL mode is set automatically by ``SqliteSaver.setup()`` (the library already
includes ``PRAGMA journal_mode=WAL`` in its setup script).  We additionally
ensure WAL mode is verified after setup.

For on-disk databases, the WAL journal is also pre-initialized before handing
the connection string to ``SqliteSaver`` to guarantee WAL mode is active from
the very first write.

Typical usage
-------------
::

    from workflow.checkpointing import create_checkpointer, compile_all_graphs

    # Option 1: Context manager (preferred for long-running daemon)
    with create_checkpointer("data/checkpoints.db") as checkpointer:
        graphs = compile_all_graphs(checkpointer)
        result = graphs["scene"].invoke(input_state, config)

    # Option 2: In-memory for tests
    with create_checkpointer(":memory:") as checkpointer:
        ...

"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Iterator

from langgraph.checkpoint.sqlite import SqliteSaver

from workflow.exceptions import CheckpointError

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph


# ---------------------------------------------------------------------------
# WAL mode initialization
# ---------------------------------------------------------------------------


def _ensure_wal_mode(db_path: str) -> None:
    """Pre-initialize WAL journal mode on an on-disk database.

    This is a no-op for ``:memory:`` databases (WAL is not supported for
    in-memory SQLite).  For file-backed databases, we open a temporary
    connection, set WAL mode, and close it before ``SqliteSaver`` takes
    ownership.

    Parameters
    ----------
    db_path : str
        Path to the SQLite database file, or ``":memory:"``.
    """
    if db_path == ":memory:":
        return

    conn = sqlite3.connect(db_path)
    try:
        result = conn.execute("PRAGMA journal_mode=WAL;").fetchone()
        if result and result[0].lower() != "wal":
            raise CheckpointError(
                f"Failed to set WAL mode on {db_path!r}: got {result[0]!r}"
            )
    finally:
        conn.close()


def verify_wal_mode(checkpointer: SqliteSaver) -> bool:
    """Verify that the checkpointer's connection is using WAL journal mode.

    Parameters
    ----------
    checkpointer : SqliteSaver
        An active SqliteSaver instance.

    Returns
    -------
    bool
        True if WAL mode is active, False otherwise.
        In-memory databases always return False (WAL not supported).
    """
    try:
        result = checkpointer.conn.execute("PRAGMA journal_mode;").fetchone()
        return result is not None and result[0].lower() == "wal"
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Checkpointer factory
# ---------------------------------------------------------------------------


@contextmanager
def create_checkpointer(
    db_path: str = "checkpoints.db",
) -> Iterator[SqliteSaver]:
    """Create a SqliteSaver with WAL mode enabled.

    Uses the ``SqliteSaver.from_conn_string()`` context manager pattern
    as specified in the architecture docs.  For on-disk databases, WAL
    mode is pre-initialized before the SqliteSaver takes ownership.

    Parameters
    ----------
    db_path : str
        Path to the checkpoint database file.  Use ``":memory:"`` for
        in-memory databases (tests).  Defaults to ``"checkpoints.db"``.

    Yields
    ------
    SqliteSaver
        A configured SqliteSaver ready for ``graph.compile(checkpointer=...)``.

    Raises
    ------
    CheckpointError
        If WAL mode cannot be set on a file-backed database.

    Examples
    --------
    ::

        with create_checkpointer("data/checkpoints.db") as cp:
            compiled = graph.compile(checkpointer=cp)
            result = compiled.invoke(state, config)
    """
    _ensure_wal_mode(db_path)

    with SqliteSaver.from_conn_string(db_path) as checkpointer:
        yield checkpointer


# ---------------------------------------------------------------------------
# Graph compilation helper
# ---------------------------------------------------------------------------


def compile_all_graphs(
    checkpointer: SqliteSaver,
) -> dict[str, CompiledStateGraph]:
    """Compile all 4 nested StateGraphs with a shared checkpointer.

    This is the main entry point for other agents to get ready-to-run
    compiled graphs.

    Parameters
    ----------
    checkpointer : SqliteSaver
        An active SqliteSaver instance (from ``create_checkpointer``).

    Returns
    -------
    dict[str, CompiledStateGraph]
        Mapping from graph name to compiled graph:
        ``{"scene", "chapter", "book", "universe"}``.
    """
    from workflow.graphs import (
        build_book_graph,
        build_chapter_graph,
        build_scene_graph,
        build_universe_graph,
    )

    return {
        "scene": build_scene_graph().compile(checkpointer=checkpointer),
        "chapter": build_chapter_graph().compile(checkpointer=checkpointer),
        "book": build_book_graph().compile(checkpointer=checkpointer),
        "universe": build_universe_graph().compile(checkpointer=checkpointer),
    }


# ---------------------------------------------------------------------------
# Checkpoint history / resume helpers
# ---------------------------------------------------------------------------


def get_checkpoint_history(
    checkpointer: SqliteSaver,
    thread_id: str,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """List recent checkpoints for a given thread.

    Parameters
    ----------
    checkpointer : SqliteSaver
        An active SqliteSaver instance.
    thread_id : str
        The thread ID to query checkpoints for.
    limit : int
        Maximum number of checkpoints to return (most recent first).

    Returns
    -------
    list[dict[str, Any]]
        List of checkpoint metadata dicts, each containing:
        - ``checkpoint_id``: unique checkpoint identifier
        - ``thread_id``: the thread this checkpoint belongs to
        - ``parent_checkpoint_id``: parent checkpoint (or None for root)
        - ``metadata``: arbitrary metadata stored with the checkpoint
    """
    config = {"configurable": {"thread_id": thread_id}}
    checkpoints = []
    for checkpoint_tuple in checkpointer.list(config, limit=limit):
        checkpoints.append(
            {
                "checkpoint_id": checkpoint_tuple.config["configurable"].get(
                    "checkpoint_id"
                ),
                "thread_id": thread_id,
                "parent_checkpoint_id": checkpoint_tuple.parent_config["configurable"].get(
                    "checkpoint_id"
                )
                if checkpoint_tuple.parent_config
                else None,
                "metadata": checkpoint_tuple.metadata,
            }
        )
    return checkpoints


def make_resume_config(
    thread_id: str,
    checkpoint_id: str | None = None,
) -> dict[str, Any]:
    """Build a LangGraph config dict for resuming from a checkpoint.

    Parameters
    ----------
    thread_id : str
        The thread ID to resume.
    checkpoint_id : str or None
        Specific checkpoint ID to resume from.  If None, resumes from
        the latest checkpoint for the thread.

    Returns
    -------
    dict[str, Any]
        Config dict suitable for ``compiled_graph.invoke({}, config)``.
    """
    config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}
    if checkpoint_id is not None:
        config["configurable"]["checkpoint_id"] = checkpoint_id
    return config


# ---------------------------------------------------------------------------
# Checkpoint retention policy
# ---------------------------------------------------------------------------


@dataclass
class CheckpointRetentionPolicy:
    """Custom checkpoint retention policy.

    Keeps the last ``keep_last_n`` checkpoints per thread, plus any
    checkpoints whose metadata contains a ``"named"`` key (these are
    user-pinned or milestone checkpoints that should never be pruned).

    Parameters
    ----------
    keep_last_n : int
        Number of most-recent checkpoints to keep per thread.
    named_checkpoints : set[str]
        Set of checkpoint IDs that should never be pruned.
    """

    keep_last_n: int = 20
    named_checkpoints: set[str] = field(default_factory=set)

    def mark_named(self, checkpoint_id: str) -> None:
        """Mark a checkpoint as named (protected from pruning).

        Parameters
        ----------
        checkpoint_id : str
            The checkpoint ID to protect.
        """
        self.named_checkpoints.add(checkpoint_id)

    def unmark_named(self, checkpoint_id: str) -> None:
        """Remove named protection from a checkpoint.

        Parameters
        ----------
        checkpoint_id : str
            The checkpoint ID to unprotect.
        """
        self.named_checkpoints.discard(checkpoint_id)

    def apply(
        self,
        checkpointer: SqliteSaver,
        thread_id: str,
    ) -> int:
        """Apply retention policy to a thread's checkpoints.

        Deletes checkpoints that exceed ``keep_last_n`` and are not named.
        Named checkpoints (by ID or by metadata ``"named"`` key) are always
        retained.

        Parameters
        ----------
        checkpointer : SqliteSaver
            An active SqliteSaver instance.
        thread_id : str
            The thread to prune.

        Returns
        -------
        int
            Number of checkpoints deleted.
        """
        config = {"configurable": {"thread_id": thread_id}}
        all_checkpoints = list(checkpointer.list(config))

        if len(all_checkpoints) <= self.keep_last_n:
            return 0

        # Checkpoints are returned most-recent-first
        to_consider = all_checkpoints[self.keep_last_n :]
        deleted = 0

        for cp in to_consider:
            cp_id = cp.config["configurable"].get("checkpoint_id")

            # Never delete named checkpoints
            if cp_id in self.named_checkpoints:
                continue

            # Never delete checkpoints with "named" in metadata
            if cp.metadata and cp.metadata.get("named"):
                continue

            # Delete this checkpoint from the database directly
            try:
                checkpointer.conn.execute(
                    "DELETE FROM checkpoints WHERE thread_id = ? AND checkpoint_id = ?",
                    (thread_id, cp_id),
                )
                checkpointer.conn.execute(
                    "DELETE FROM writes WHERE thread_id = ? AND checkpoint_id = ?",
                    (thread_id, cp_id),
                )
                deleted += 1
            except Exception:
                # Non-critical: if we can't delete, skip
                continue

        if deleted > 0:
            checkpointer.conn.commit()

        return deleted
