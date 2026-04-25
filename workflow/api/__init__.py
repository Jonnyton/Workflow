"""Engine MCP API namespace.

This package is the home for FastMCP sub-apps per PLAN.md §Module Layout:
  api/runs.py, api/branches.py, api/judgments.py, api/goals.py, api/wiki.py

create_app() is a stub — the FastMCP submodule extraction is in-flight.
Tests for the fantasy_daemon REST app belong in fantasy_daemon/api.py scope;
import from fantasy_daemon.api directly, not from this package.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI


def create_app(registry: Any | None = None) -> FastAPI:
    """Return a bare FastAPI app shell.

    Once the FastMCP api/* submodules are built (PLAN.md target), this will
    mount them. Until then it returns an empty app so callers have a stable
    import surface.
    """
    return FastAPI(title="Workflow Engine API")


__all__ = ["create_app"]
