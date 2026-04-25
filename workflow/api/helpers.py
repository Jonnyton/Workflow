"""Shared path and I/O helpers for the universe-server action handlers.

Extracted from ``workflow/universe_server.py`` preamble as Bundle 1 of
the #29 decomposition plan. These helpers are used by 3+ future submodules
(branches, runs, evaluation, market, wiki, status) and therefore live in
a shared leaf module with no project-level circular-import risk.

Public surface (stable contract):
    _base_path()               → Path: canonical data root
    _universe_dir(uid)         → Path: specific universe directory (path-traversal guarded)
    _default_universe()        → str:  default universe ID
    _read_json(path)           → dict | list | None: safe JSON reader
    _read_text(path, default)  → str:  safe text reader
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _base_path() -> Path:
    """Resolve the base directory containing all universe directories.

    Delegates to ``workflow.storage.data_dir`` — canonical env var
    ``WORKFLOW_DATA_DIR`` (legacy ``UNIVERSE_SERVER_BASE`` still honored
    with deprecation warning). This replaces the earlier CWD-relative
    ``"output"`` default which wrote to ``/app/output`` in containers
    instead of the bind-mounted ``/data`` volume — the 2026-04-19
    containerization bug class.
    """
    from workflow.storage import data_dir
    return data_dir()


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


__all__ = [
    "_base_path",
    "_default_universe",
    "_read_json",
    "_read_text",
    "_universe_dir",
]
