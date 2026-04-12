"""MCP server exposing the Fantasy Author daemon's file interface.

Provides tools for any AI client to read status, add notes for the daemon,
manage premises, read output, and control execution.

Usage::

    python -m fantasy_author.mcp_server

Set ``FANTASY_AUTHOR_UNIVERSE`` to the universe directory path,
or it defaults to ``output/default-universe/``.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from fastmcp import FastMCP

mcp = FastMCP(
    "fantasy-author",
    instructions=(
        "Fantasy Author daemon interface. Use these tools to monitor "
        "and guide an autonomous fiction-writing daemon through notes."
    ),
)


def _universe_dir() -> Path:
    """Resolve the universe directory from environment or default."""
    return Path(
        os.environ.get("FANTASY_AUTHOR_UNIVERSE", "output/default-universe")
    )


@mcp.tool
def get_status() -> str:
    """Read the daemon's current status (phase, word count, accept rate, etc.)."""
    status_path = _universe_dir() / "status.json"
    if not status_path.exists():
        return "No status.json found. The daemon may not be running."
    try:
        return status_path.read_text(encoding="utf-8")
    except OSError as e:
        return f"Error reading status.json: {e}"


@mcp.tool
def add_note(text: str, category: str = "direction") -> str:
    """Add a note to the universe's notes system.

    The daemon reads notes at each scene boundary.

    Args:
        text: The note text.
        category: One of 'direction', 'protect', 'concern', 'observation', 'error'.
    """
    valid_categories = {"direction", "protect", "concern", "observation", "error"}
    if category not in valid_categories:
        category = "direction"
    try:
        from workflow.notes import add_note as add_note_to_store

        _universe_dir().mkdir(parents=True, exist_ok=True)
        note = add_note_to_store(
            _universe_dir(), source="user", text=text, category=category,
        )
        return f"Note added (id={note.id[:8]}..., category={category})."
    except Exception as e:
        return f"Error adding note: {e}"


def steer(directive: str, category: str = "direction") -> str:
    """Backward-compatible alias for ``add_note``."""
    return add_note(directive, category)


@mcp.tool
def get_premise() -> str:
    """Read the current story premise from PROGRAM.md."""
    program_path = _universe_dir() / "PROGRAM.md"
    if not program_path.exists():
        return "No PROGRAM.md found. Use set_premise() to create one."
    try:
        return program_path.read_text(encoding="utf-8")
    except OSError as e:
        return f"Error reading PROGRAM.md: {e}"


@mcp.tool
def set_premise(text: str) -> str:
    """Write or overwrite the story premise in PROGRAM.md.

    The daemon reads this once at startup to seed the story direction.
    """
    program_path = _universe_dir() / "PROGRAM.md"
    try:
        _universe_dir().mkdir(parents=True, exist_ok=True)
        program_path.write_text(text, encoding="utf-8")
        return "PROGRAM.md updated."
    except OSError as e:
        return f"Error writing PROGRAM.md: {e}"


@mcp.tool
def get_progress() -> str:
    """Read the human-readable progress summary from progress.md."""
    progress_path = _universe_dir() / "progress.md"
    if not progress_path.exists():
        return "No progress.md found. The daemon may not have started writing yet."
    try:
        return progress_path.read_text(encoding="utf-8")
    except OSError as e:
        return f"Error reading progress.md: {e}"


@mcp.tool
def get_work_targets() -> str:
    """Read the durable work target registry for the current universe."""
    path = _universe_dir() / "work_targets.json"
    if not path.exists():
        return "No work_targets.json found."
    try:
        return path.read_text(encoding="utf-8")
    except OSError as e:
        return f"Error reading work_targets.json: {e}"


@mcp.tool
def get_review_state() -> str:
    """Read the latest review-state snapshot for the current universe."""
    status_path = _universe_dir() / "status.json"
    if not status_path.exists():
        return "No status.json found."
    try:
        return status_path.read_text(encoding="utf-8")
    except OSError as e:
        return f"Error reading status.json: {e}"


@mcp.tool
def get_chapter(book: int, chapter: int) -> str:
    """Read a completed chapter file.

    Args:
        book: Book number (e.g. 1).
        chapter: Chapter number (e.g. 3).
    """
    chapter_path = _universe_dir() / "output" / f"book-{book}" / f"chapter-{chapter:02d}.md"
    if not chapter_path.exists():
        return f"Chapter file not found: book-{book}/chapter-{chapter:02d}.md"
    try:
        return chapter_path.read_text(encoding="utf-8")
    except OSError as e:
        return f"Error reading chapter file: {e}"


@mcp.tool
def get_activity(lines: int = 20) -> str:
    """Read the most recent lines from the activity log.

    Args:
        lines: Number of lines to return (default 20).
    """
    log_path = _universe_dir() / "activity.log"
    if not log_path.exists():
        return "No activity.log found."
    try:
        content = log_path.read_text(encoding="utf-8")
        all_lines = content.strip().splitlines()
        tail = all_lines[-lines:] if len(all_lines) > lines else all_lines
        return "\n".join(tail)
    except OSError as e:
        return f"Error reading activity.log: {e}"


@mcp.tool
def pause() -> str:
    """Pause the daemon. Creates a control file that the daemon checks."""
    pause_path = _universe_dir() / ".pause"
    try:
        _universe_dir().mkdir(parents=True, exist_ok=True)
        pause_path.write_text(
            datetime.now(timezone.utc).isoformat(), encoding="utf-8",
        )
        return "Pause signal written. The daemon will pause at the next scene boundary."
    except OSError as e:
        return f"Error writing pause signal: {e}"


@mcp.tool
def resume() -> str:
    """Resume the daemon by removing the pause control file."""
    pause_path = _universe_dir() / ".pause"
    if not pause_path.exists():
        return "Daemon is not paused (no .pause file found)."
    try:
        pause_path.unlink()
        return "Pause signal removed. The daemon will resume."
    except OSError as e:
        return f"Error removing pause signal: {e}"


@mcp.tool
def add_canon(filename: str, content: str) -> str:
    """Add a reference file to the canon/ directory.

    The daemon ingests canon files for worldbuilding context (character
    sheets, maps, lore documents, etc.).

    Args:
        filename: Name for the file (e.g. "characters.md").
        content: File content to write.
    """
    canon_dir = _universe_dir() / "canon"
    # Sanitize filename to prevent path traversal
    safe_name = Path(filename).name
    if not safe_name:
        return "Invalid filename."
    try:
        canon_dir.mkdir(parents=True, exist_ok=True)
        target = canon_dir / safe_name
        target.write_text(content, encoding="utf-8")
        return f"Written {safe_name} to canon/."
    except OSError as e:
        return f"Error writing to canon/: {e}"


def main() -> None:
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
