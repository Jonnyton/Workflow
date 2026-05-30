"""Engine MCP API namespace.

This package is the home for FastMCP sub-apps per PLAN.md §Module Layout:
  api/runs.py, api/branches.py, api/judgments.py, api/goals.py, api/wiki.py

create_app() is a stub — the FastMCP submodule extraction is in-flight.
Tests for the fantasy_daemon REST app belong in fantasy_daemon/api.py scope;
import from fantasy_daemon.api directly, not from this package.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from workflow.api.helpers import (
    _base_path,
    _default_universe,
    _read_json,
    _read_text,
    _universe_dir,
)

if TYPE_CHECKING:
    from fastapi import FastAPI


def create_app(registry: Any | None = None) -> FastAPI:
    """Build the Workflow Engine API app.

    fastapi is imported lazily so the MCPB stdio bundle — which doesn't ship
    fastapi — can import this package.
    """
    from fastapi import FastAPI

    from workflow.api.branches import router as branches_router
    from workflow.api.goals import router as goals_router
    from workflow.api.judgments import router as judgments_router
    from workflow.api.runs import router as runs_router
    from workflow.api.wiki import router as wiki_router

    app = FastAPI(title="Workflow Engine API")
    app.include_router(runs_router)
    app.include_router(branches_router)
    app.include_router(judgments_router)
    app.include_router(goals_router)
    app.include_router(wiki_router)
    return app


__all__ = [
    "create_app",
    # helpers (re-exported for submodule consumers)
    "_base_path",
    "_default_universe",
    "_read_json",
    "_read_text",
    "_universe_dir",
]
