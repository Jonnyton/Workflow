"""API scaffolding for workflow engine and domain-specific routes.

Provides a create_app() function that assembles the FastAPI application
from core workflow routes and domain-specific routes.

In Phase 5.2, the API is still primarily served from fantasy_author.api,
but this module provides the future app-builder interface that will
eventually split engine routes from domain routes.

Usage
-----
from workflow.api import create_app
from workflow.registry import default_registry

app = create_app(default_registry)
uvicorn.run(app, host="0.0.0.0", port=8000)

For backward compatibility, importing app and configure will still re-export
from fantasy_author.api.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

# Re-export everything from fantasy_author.api (the Phase 5 bridge file).
# The wildcard covers public names; private helpers used by tests are
# imported explicitly so they're reachable via ``workflow.api``.
from fantasy_author.api import *  # noqa: F401,F403
from fantasy_author.api import app as fantasy_author_app
from fantasy_author.api import configure as fantasy_author_configure
from fantasy_author.api import (  # noqa: F401 – private but test-visible
    _extract_username,
    _load_provider_keys,
    _slugify,
)


def create_app(registry: Any | None = None) -> FastAPI:
    """Create a FastAPI application with core and domain-specific routes.

    Parameters
    ----------
    registry : DomainRegistry, optional
        A DomainRegistry instance. If provided, the function will iterate
        over registered domains and include their api_routes() if available.
        If None, defaults to importing and using default_registry.

    Returns
    -------
    FastAPI
        A FastAPI application instance with all routes configured.

    Notes
    -----
    In Phase 5.2, this function primarily delegates to fantasy_author.api.app
    for backward compatibility. Once domain API separation is complete,
    this will:

    1. Create a fresh FastAPI instance
    2. Include core workflow routes (health, status, domain list, etc.)
    3. Iterate over registered domains and mount their api_routes()
    4. Return the assembled app

    For now, domain-specific routes are still in fantasy_author.api, so
    this returns that app directly.
    """
    # Phase 5.2: For now, just return the fantasy_author app
    # This maintains backward compatibility while the interface is being
    # established. Once domain API separation is complete, this will
    # assemble routes from multiple domains.

    if registry is None:
        from workflow.registry import default_registry

        registry = default_registry

    # TODO: In a later phase, create a fresh app and include routes from:
    # - Core workflow routes (health, status, domain list, etc.)
    # - Domain-specific api_routes() from registered domains

    # For now, delegate to fantasy_author.api for full compatibility
    return fantasy_author_app


# Backward compatibility exports
app = fantasy_author_app
configure = fantasy_author_configure

__all__ = ["create_app", "app", "configure"]

