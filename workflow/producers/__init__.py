"""TaskProducer protocol + active registry.

Phase C.3 landing. The protocol is the contract; the registry is the
live list of producers a daemon cycle iterates. No producers register
themselves here in C.3 — that's C.4's job (seed / user_request /
fantasy_authorial each import `workflow.producers` in their domain
init and call ``register(...)``).

See docs/specs/taskproducer_phase_c.md §1 for full contract.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from workflow.work_targets import WorkTarget


@runtime_checkable
class TaskProducer(Protocol):
    """Produces candidate WorkTargets for one universe's daemon cycle.

    Called once per daemon cycle (before review gates run). Must be
    idempotent: calling twice with unchanged inputs returns the same
    WorkTarget set. Producers MAY upsert targets into the universe's
    ``work_targets.json``, but MUST return only the targets produced
    or updated by this call — callers use the return value to
    attribute origin and log what each producer contributed.

    v1 protocol is synchronous; Phase F may introduce an async variant
    for cross-universe producers that read repo-root state with I/O
    latency. Synchronous design is deliberate for v1 — simpler
    contract, easier ON/OFF identity testing.
    """

    name: str
    """Stable identifier. Logged per produced target. Must match
    ``[a-z][a-z0-9_-]*``. Examples: ``"fantasy_authorial"``,
    ``"user_request"``, ``"seed"``."""

    origin: str
    """The ``WorkTarget.origin`` value this producer stamps on every
    emitted target. Must be one of the allowed origin values
    (spec §3). A single producer always stamps one origin —
    producers don't commingle origin values."""

    def produce(
        self,
        universe_path: Path,
        *,
        config: dict | None = None,
    ) -> list[WorkTarget]:
        """Read universe state, return candidate WorkTargets.

        ``config`` is a producer-specific dict passed from the daemon's
        config file — lets producers take parameters without needing
        constructor args. Producers that need no config ignore it.

        Raises: should NOT raise on empty state — return ``[]``. MAY
        raise on genuinely corrupt state (unreadable JSON, missing
        required files); the daemon logs and skips to the next
        producer.
        """
        ...


# Module-level registry. Order is dispatch order — later producers
# overwrite earlier ones on target_id collision per spec §1.2. The
# Phase C.4 identity test depends on this determinism, so do NOT
# reorder at iteration time.
_REGISTRY: list[TaskProducer] = []


def register(producer: TaskProducer) -> None:
    """Add a producer to the active list.

    Idempotent on ``producer.name``: re-registering by name replaces
    the prior instance (supports hot-reload in dev + guards against
    duplicate-register bugs in domain init).
    """
    global _REGISTRY
    _REGISTRY = [p for p in _REGISTRY if p.name != producer.name]
    _REGISTRY.append(producer)


def registered_producers() -> tuple[TaskProducer, ...]:
    """Return active producers in registration order.

    Returns a tuple so callers can't mutate the registry by mutating
    the returned sequence. Use ``register()`` / ``unregister()`` to
    change state.
    """
    return tuple(_REGISTRY)


def unregister(name: str) -> bool:
    """Remove a producer by name. Returns True if it was present."""
    global _REGISTRY
    before = len(_REGISTRY)
    _REGISTRY = [p for p in _REGISTRY if p.name != name]
    return len(_REGISTRY) != before


def reset_registry() -> None:
    """Clear all registered producers. Test-only hook."""
    global _REGISTRY
    _REGISTRY = []
