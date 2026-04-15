"""Domain-trusted opaque node registry (Phase D).

Engine-side storage for opaque node callables owned by domains. The
engine (`workflow/graph_compiler.py`) resolves registered callables at
compile time; domains (e.g. `fantasy_author/branch_registrations.py`)
populate the registry at import time.

The engine never imports any specific domain — domains are plugins that
call ``register_domain_callable`` from their own package-level modules.
Matches PLAN.md's "engine is infrastructure, not topology" principle.

Registration is idempotent: re-registering the same
``(domain_id, node_id)`` overwrites silently with a debug log. Tests
and re-import scenarios (e.g. ``importlib.reload``) thus stay
side-effect-free. A double-register that ships different callables
would indicate an actual bug in the domain layer; the debug log is
the footprint for investigation.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


_DomainCallable = Callable[[dict[str, Any]], dict[str, Any]]

_REGISTRY: dict[tuple[str, str], _DomainCallable] = {}


def register_domain_callable(
    domain_id: str,
    node_id: str,
    fn: _DomainCallable,
) -> None:
    """Register a domain-trusted opaque node callable.

    ``fn`` must accept the current state dict and return a dict of
    updates. Called from `_build_opaque_node` inside the compiler;
    must be safe under LangGraph's execution model (no hidden
    globals, no blocking I/O beyond domain contract).
    """
    key = (domain_id, node_id)
    if key in _REGISTRY and _REGISTRY[key] is not fn:
        logger.debug(
            "Domain callable re-registered for %s; replacing previous entry.",
            key,
        )
    _REGISTRY[key] = fn


def resolve_domain_callable(
    domain_id: str,
    node_id: str,
) -> _DomainCallable | None:
    """Return the registered callable, or None if unregistered."""
    return _REGISTRY.get((domain_id, node_id))


def clear_registry() -> None:
    """Testing-only helper; drops all registrations."""
    _REGISTRY.clear()
