"""LanceDB vector store -- singleton connection, pre-computed embeddings.

The connection is created once and reused everywhere.  Embeddings must
be pre-computed as numpy arrays; LanceDB does not call an embedding
model itself.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Sequence

import lancedb
import numpy as np

# ---------------------------------------------------------------------------
# Singleton connection
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_db: lancedb.DBConnection | None = None
_db_path: str | None = None


def get_db(path: str = "") -> lancedb.DBConnection:
    """Return the singleton LanceDB connection.

    The first call creates the connection; subsequent calls reuse it.
    Thread-safe via a lock.

    ``path`` must be explicit. CWD-relative defaults cause
    cross-universe contamination: two universes sharing the same
    relative path end up reading and writing each other's vectors.
    Mirror of the guard in
    ``workflow/knowledge/knowledge_graph.py``.
    """
    if not path:
        raise ValueError(
            "get_db requires an explicit path. "
            "CWD-relative defaults cause cross-universe contamination."
        )
    global _db, _db_path
    with _lock:
        if _db is None or _db_path != path:
            Path(path).mkdir(parents=True, exist_ok=True)
            _db = lancedb.connect(path)
            _db_path = path
        return _db


def reset_db() -> None:
    """Reset the singleton (for testing only)."""
    global _db, _db_path
    with _lock:
        _db = None
        _db_path = None


# ---------------------------------------------------------------------------
# VectorStore wrapper
# ---------------------------------------------------------------------------


class VectorStore:
    """High-level wrapper around a LanceDB table for prose chunk storage.

    Parameters
    ----------
    db_path
        Path to the LanceDB directory.
    table_name
        Name of the table to create/open.
    embedding_dim
        Dimension of embedding vectors.
    """

    def __init__(
        self,
        db_path: str = "",
        table_name: str = "prose_chunks",
        embedding_dim: int = 384,
    ) -> None:
        if not db_path:
            raise ValueError(
                "VectorStore requires an explicit db_path. "
                "CWD-relative defaults cause cross-universe contamination."
            )
        self._db = get_db(db_path)
        self._table_name = table_name
        self._embedding_dim = embedding_dim
        self._table: Any = None

    def _ensure_table(self) -> Any:
        """Create or open the table."""
        if self._table is not None:
            return self._table

        existing = self._db.list_tables()
        if self._table_name in existing:
            self._table = self._db.open_table(self._table_name)
        else:
            # Create with a seed row (LanceDB requires at least one row)
            seed = [{
                "chunk_id": "__seed__",
                "text": "",
                "scene_id": "",
                "chapter_number": 0,
                "character": "",
                "location": "",
                "embedding": np.zeros(self._embedding_dim, dtype=np.float32).tolist(),
            }]
            self._table = self._db.create_table(self._table_name, data=seed)
        return self._table

    def index(self, chunks: Sequence[dict]) -> int:
        """Index prose chunks with pre-computed embeddings.

        Each chunk dict must have:
            - chunk_id: str
            - text: str
            - embedding: list[float] or numpy array
            - scene_id: str
            - chapter_number: int
            - character: str (optional)
            - location: str (optional)

        Returns the number of chunks indexed.
        """
        table = self._ensure_table()
        if not chunks:
            return 0

        rows = []
        for chunk in chunks:
            emb = chunk["embedding"]
            if isinstance(emb, np.ndarray):
                emb = emb.tolist()
            rows.append({
                "chunk_id": chunk["chunk_id"],
                "text": chunk["text"],
                "scene_id": chunk.get("scene_id", ""),
                "chapter_number": chunk.get("chapter_number", 0),
                "character": chunk.get("character", ""),
                "location": chunk.get("location", ""),
                "embedding": emb,
            })

        table.add(rows)
        return len(rows)

    def search(
        self,
        embedding: list[float] | np.ndarray,
        limit: int = 5,
        where: str | None = None,
    ) -> list[dict]:
        """Search for similar prose chunks.

        Parameters
        ----------
        embedding
            Query embedding vector (pre-computed).
        limit
            Maximum results.
        where
            Optional SQL WHERE clause for filtering.

        Returns
        -------
        list[dict]
            Matching chunks with text, metadata, and ``_distance``.
        """
        table = self._ensure_table()
        if isinstance(embedding, np.ndarray):
            embedding = embedding.tolist()

        query = table.search(embedding).limit(limit)
        if where:
            query = query.where(where)

        results = query.to_list()
        # Filter out seed rows
        return [r for r in results if r.get("chunk_id") != "__seed__"]

    def count(self) -> int:
        """Return number of rows (excluding seed)."""
        table = self._ensure_table()
        total = len(table)
        return max(0, total - 1)  # Subtract seed row
