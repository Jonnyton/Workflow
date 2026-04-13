"""Storage backend protocol for Phase 7 dual-write cutover.

Per spec (``docs/specs/phase7_github_as_catalog.md`` §Architecture):

```
StorageBackend (protocol)
├── sqlite_only      — current default; tests + transitional builds
├── sqlite_cached    — writes go YAML→git first, SQLite mirrors as read cache
└── filesystem_only  — far-future; SQLite gone
```

Phase 7.1 ships ``sqlite_only`` and ``sqlite_cached``. The git op in
``sqlite_cached`` is a no-op in this ship — it writes YAML to the
working directory and returns. Phase 7.2 bolts on ``git_bridge.py``
and the stage/commit calls land at the marked extension points.

Reads stay through SQLite for query performance in both backends.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

import yaml

from workflow.branches import BranchDefinition
from workflow.storage.layout import YamlRepoLayout, slugify
from workflow.storage.serializer import (
    branch_to_yaml_payload,
    goal_to_yaml_payload,
)

__all__ = [
    "SqliteCachedBackend",
    "SqliteOnlyBackend",
    "StorageBackend",
]


class StorageBackend(Protocol):
    """The minimal write surface Phase 7 cutover needs.

    Kept narrow on purpose — every method maps to a public mutation
    already in ``author_server.py`` and ``universe_server.py``. Reads
    stay on the existing ``author_server`` helpers and go through
    whichever cache/file shape the backend populated.
    """

    def save_branch(self, branch: BranchDefinition) -> dict[str, Any]:
        """Persist a Branch; return the stored dict shape."""

    def save_goal(self, goal: dict[str, Any]) -> dict[str, Any]:
        """Persist a Goal; return the stored dict shape."""


# ─────────────────────────────────────────────────────────────────────
# SqliteOnlyBackend
# ─────────────────────────────────────────────────────────────────────


class SqliteOnlyBackend:
    """Current default — pure SQLite. Zero behavior change.

    ``author_server.save_branch_definition`` and
    ``author_server.save_goal`` are the source of truth; this class
    just wraps them so dispatch code can depend on the protocol
    without importing from ``author_server`` directly.
    """

    def __init__(self, base_path: str | Path) -> None:
        self.base_path = Path(base_path)

    def save_branch(self, branch: BranchDefinition) -> dict[str, Any]:
        from workflow.author_server import save_branch_definition

        return save_branch_definition(
            self.base_path, branch_def=branch.to_dict(),
        )

    def save_goal(self, goal: dict[str, Any]) -> dict[str, Any]:
        from workflow.author_server import save_goal as _save_goal

        return _save_goal(self.base_path, goal=goal)


# ─────────────────────────────────────────────────────────────────────
# SqliteCachedBackend
# ─────────────────────────────────────────────────────────────────────


class SqliteCachedBackend:
    """Writes YAML alongside the SQLite row.

    Phase 7.1: YAML write lands; git stage/commit is a deferred hook
    (``self._stage_hook``) that does nothing by default. Phase 7.2
    replaces the hook with a ``git_bridge.stage`` call.

    The SQLite write still happens so reads keep their current shape
    and performance. Once ``filesystem_only`` lands in 7.x the SQLite
    half retires; until then this backend is strictly additive.
    """

    def __init__(
        self,
        base_path: str | Path,
        *,
        repo_root: str | Path,
        stage_hook: Any = None,
    ) -> None:
        self.base_path = Path(base_path)
        self.layout = YamlRepoLayout(repo_root)
        # Callers pass a no-op hook in tests, a ``git_bridge.stage``
        # bound method in production (Phase 7.2).
        self._stage_hook = stage_hook or _noop_stage

    # ── Branch ────────────────────────────────────────────────────

    def save_branch(self, branch: BranchDefinition) -> dict[str, Any]:
        from workflow.author_server import save_branch_definition

        # Mirror write: SQLite first so an exception surfaces before
        # we litter the working tree with half-formed YAML.
        saved = save_branch_definition(
            self.base_path, branch_def=branch.to_dict(),
        )

        branch_slug = slugify(branch.name or branch.branch_def_id)
        branch_payload, node_payloads = branch_to_yaml_payload(
            branch, branch_slug=branch_slug,
        )

        branch_path = self.layout.branch_path(branch_slug)
        _write_yaml(branch_path, branch_payload)
        self._stage_hook(branch_path)

        for node_payload in node_payloads:
            node_path = self.layout.node_path(
                branch_slug, node_payload["id"],
            )
            _write_yaml(node_path, node_payload)
            self._stage_hook(node_path)

        return saved

    # ── Goal ──────────────────────────────────────────────────────

    def save_goal(self, goal: dict[str, Any]) -> dict[str, Any]:
        from workflow.author_server import save_goal as _save_goal

        saved = _save_goal(self.base_path, goal=goal)

        goal_slug = slugify(saved.get("name") or saved.get("goal_id"))
        goal_payload = goal_to_yaml_payload(saved)
        goal_path = self.layout.goal_path(goal_slug)
        _write_yaml(goal_path, goal_payload)
        self._stage_hook(goal_path)

        return saved


# ─────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    """Write a YAML document to ``path``; create parents as needed.

    Sort keys off — payload-declared ordering carries semantic intent
    (``id`` / ``name`` / ``description`` first in the file, mechanical
    fields last). ``default_flow_style=False`` forces block style so
    diffs render line-by-line.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            payload,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )


def _noop_stage(_path: Path) -> None:
    """Phase 7.1 stub; Phase 7.2 replaces with git_bridge.stage."""
    return None
