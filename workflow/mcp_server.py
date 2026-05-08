"""Deprecated stdio compatibility entry point for Workflow MCP.

The canonical MCP surface lives in :mod:`workflow.universe_server`.
This module keeps the historical ``python -m workflow.mcp_server`` and
``workflow-mcp`` entry points working, but it no longer registers the
old 12 single-purpose daemon-file tools. Stdio clients now see the same
grouped tool surface as the remote universe server.

The plain helper functions below remain importable for older local tests
and scripts that read or write a single universe directory directly.
New code should call ``workflow.universe_server.universe(...)`` or the
other grouped handles instead.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from workflow.universe_server import main, mcp

DEPRECATION_NOTICE = (
    "workflow.mcp_server is deprecated; use workflow.universe_server and "
    "the grouped MCP handles instead."
)


def _universe_dir() -> Path:
    """Resolve the legacy single-universe directory.

    Precedence:
      1. ``$WORKFLOW_UNIVERSE`` for old stdio/local scripts.
      2. ``workflow.storage.data_dir() / "default-universe"``.
    """
    env = os.environ.get("WORKFLOW_UNIVERSE")
    if env:
        return Path(env).expanduser().resolve()
    from workflow.storage import data_dir

    return data_dir() / "default-universe"


def get_status() -> str:
    """Deprecated legacy helper: read ``status.json`` from one universe."""
    status_path = _universe_dir() / "status.json"
    if not status_path.exists():
        return "No status.json found. The daemon may not be running."
    try:
        return status_path.read_text(encoding="utf-8")
    except OSError as exc:
        return f"Error reading status.json: {exc}"


def add_note(text: str, category: str = "direction") -> str:
    """Deprecated legacy helper: append a note for the daemon."""
    valid_categories = {"direction", "protect", "concern", "observation", "error"}
    if category not in valid_categories:
        category = "direction"
    try:
        from workflow.notes import add_note as add_note_to_store

        _universe_dir().mkdir(parents=True, exist_ok=True)
        note = add_note_to_store(
            _universe_dir(),
            source="user",
            text=text,
            category=category,
        )
        return f"Note added (id={note.id[:8]}..., category={category})."
    except Exception as exc:
        return f"Error adding note: {exc}"


def steer(directive: str, category: str = "direction") -> str:
    """Deprecated backward-compatible alias for ``add_note``."""
    return add_note(directive, category)


def get_premise() -> str:
    """Deprecated legacy helper: read ``PROGRAM.md``."""
    program_path = _universe_dir() / "PROGRAM.md"
    if not program_path.exists():
        return "No PROGRAM.md found. Use set_premise() to create one."
    try:
        return program_path.read_text(encoding="utf-8")
    except OSError as exc:
        return f"Error reading PROGRAM.md: {exc}"


def set_premise(text: str) -> str:
    """Deprecated legacy helper: write ``PROGRAM.md``."""
    program_path = _universe_dir() / "PROGRAM.md"
    try:
        _universe_dir().mkdir(parents=True, exist_ok=True)
        program_path.write_text(text, encoding="utf-8")
        return "PROGRAM.md updated."
    except OSError as exc:
        return f"Error writing PROGRAM.md: {exc}"


def get_progress() -> str:
    """Deprecated legacy helper: read ``progress.md``."""
    progress_path = _universe_dir() / "progress.md"
    if not progress_path.exists():
        return "No progress.md found. The daemon may not have started writing yet."
    try:
        return progress_path.read_text(encoding="utf-8")
    except OSError as exc:
        return f"Error reading progress.md: {exc}"


def get_work_targets() -> str:
    """Deprecated legacy helper: read ``work_targets.json``."""
    path = _universe_dir() / "work_targets.json"
    if not path.exists():
        return "No work_targets.json found."
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        return f"Error reading work_targets.json: {exc}"


def get_review_state() -> str:
    """Deprecated legacy helper: read review fields from ``status.json``."""
    status_path = _universe_dir() / "status.json"
    if not status_path.exists():
        return "No status.json found."
    try:
        return status_path.read_text(encoding="utf-8")
    except OSError as exc:
        return f"Error reading status.json: {exc}"


def get_chapter(book: int, chapter: int) -> str:
    """Deprecated legacy helper: read a completed chapter markdown file."""
    chapter_path = (
        _universe_dir() / "output" / f"book-{book}" / f"chapter-{chapter:02d}.md"
    )
    if not chapter_path.exists():
        return f"Chapter file not found: book-{book}/chapter-{chapter:02d}.md"
    try:
        return chapter_path.read_text(encoding="utf-8")
    except OSError as exc:
        return f"Error reading chapter file: {exc}"


def get_activity(lines: int = 20) -> str:
    """Deprecated legacy helper: read the tail of ``activity.log``."""
    log_path = _universe_dir() / "activity.log"
    if not log_path.exists():
        return "No activity.log found."
    try:
        content = log_path.read_text(encoding="utf-8")
        all_lines = content.strip().splitlines()
        tail = all_lines[-lines:] if len(all_lines) > lines else all_lines
        return "\n".join(tail)
    except OSError as exc:
        return f"Error reading activity.log: {exc}"


def pause() -> str:
    """Deprecated legacy helper: write the ``.pause`` sentinel."""
    pause_path = _universe_dir() / ".pause"
    try:
        _universe_dir().mkdir(parents=True, exist_ok=True)
        pause_path.write_text(
            datetime.now(timezone.utc).isoformat(),
            encoding="utf-8",
        )
        return "Pause signal written. The daemon will pause at the next scene boundary."
    except OSError as exc:
        return f"Error writing pause signal: {exc}"


def resume() -> str:
    """Deprecated legacy helper: remove the ``.pause`` sentinel."""
    pause_path = _universe_dir() / ".pause"
    if not pause_path.exists():
        return "Daemon is not paused (no .pause file found)."
    try:
        pause_path.unlink()
        return "Pause signal removed. The daemon will resume."
    except OSError as exc:
        return f"Error removing pause signal: {exc}"


def add_canon(filename: str, content: str) -> str:
    """Deprecated legacy helper: write a canon file into ``canon/``."""
    canon_dir = _universe_dir() / "canon"
    safe_name = Path(filename).name
    if not safe_name:
        return "Invalid filename."
    try:
        canon_dir.mkdir(parents=True, exist_ok=True)
        target = canon_dir / safe_name
        target.write_text(content, encoding="utf-8")
        return f"Written {safe_name} to canon/."
    except OSError as exc:
        return f"Error writing to canon/: {exc}"


__all__ = [
    "DEPRECATION_NOTICE",
    "_universe_dir",
    "add_canon",
    "add_note",
    "get_activity",
    "get_chapter",
    "get_premise",
    "get_progress",
    "get_review_state",
    "get_status",
    "get_work_targets",
    "main",
    "mcp",
    "pause",
    "resume",
    "set_premise",
    "steer",
]


if __name__ == "__main__":
    main()
