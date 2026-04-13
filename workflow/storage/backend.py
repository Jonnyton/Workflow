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

from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

import yaml

from workflow import git_bridge
from workflow.branches import BranchDefinition
from workflow.storage.layout import YamlRepoLayout, slugify
from workflow.storage.serializer import (
    branch_to_yaml_payload,
    goal_to_yaml_payload,
)

__all__ = [
    "DirtyFileError",
    "SqliteCachedBackend",
    "SqliteOnlyBackend",
    "StorageBackend",
]


class DirtyFileError(RuntimeError):
    """Raised by :class:`SqliteCachedBackend` when a save would overwrite
    a file the user has uncommitted local edits to.

    Caller resolves manually (commit / stash / discard) or retries with
    ``force=True``. The ``paths`` list carries every dirty file detected
    in the attempted save so the caller can surface them all at once.
    """

    def __init__(self, paths: list[Path]) -> None:
        self.paths = list(paths)
        joined = ", ".join(str(p) for p in self.paths) or "(unknown)"
        super().__init__(
            f"Local edit conflict: {joined} has uncommitted changes. "
            "Commit, stash, or discard — or retry with force=True."
        )


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

    Phase 7.2: when ``git_bridge.is_enabled()`` is True and no explicit
    ``stage_hook`` is provided, the backend wires ``git_bridge.stage``
    as the hook so every YAML write is automatically staged for the
    next commit. A ``has_uncommitted_changes`` pre-check refuses to
    overwrite files the user is editing locally (override with
    ``force=True``).

    The SQLite write still happens so reads keep their current shape
    and performance. Once ``filesystem_only`` lands in 7.x the SQLite
    half retires; until then this backend is strictly additive.
    """

    def __init__(
        self,
        base_path: str | Path,
        *,
        repo_root: str | Path,
        stage_hook: Callable[[Path], None] | None = None,
        git_enabled: bool | None = None,
    ) -> None:
        self.base_path = Path(base_path)
        self.layout = YamlRepoLayout(repo_root)
        self._repo_root = Path(repo_root)
        # ``git_enabled=None`` (default) probes at construction so a
        # caller can override the auto-decision in tests or non-git
        # environments.
        if git_enabled is None:
            git_enabled = git_bridge.is_enabled(self._repo_root)
        self._git_enabled = git_enabled
        if stage_hook is not None:
            self._stage_hook = stage_hook
        elif git_enabled:
            # Bind the repo_root so callers at write time don't need to
            # know about it. Matches the ``Callable[[Path], None]`` shape.
            self._stage_hook = self._make_git_stage_hook()
        else:
            self._stage_hook = _noop_stage

    def _make_git_stage_hook(self) -> Callable[[Path], None]:
        repo_root = self._repo_root

        def _hook(path: Path) -> None:
            git_bridge.stage(path, repo_path=repo_root)

        return _hook

    def _check_dirty(self, paths: list[Path], *, force: bool) -> None:
        """Refuse to overwrite files with uncommitted user edits.

        Raises :class:`DirtyFileError` when any path is dirty and
        ``force`` is False. No-op when git is disabled (cannot tell
        clean from dirty without git).
        """
        if force or not self._git_enabled:
            return
        dirty = [
            p for p in paths
            if git_bridge.has_uncommitted_changes(p, repo_path=self._repo_root)
        ]
        if dirty:
            raise DirtyFileError(dirty)

    # ── Branch ────────────────────────────────────────────────────

    def save_branch(
        self, branch: BranchDefinition, *, force: bool = False,
    ) -> dict[str, Any]:
        from workflow.author_server import save_branch_definition

        branch_slug = slugify(branch.name or branch.branch_def_id)
        branch_payload, node_payloads = branch_to_yaml_payload(
            branch, branch_slug=branch_slug,
        )
        branch_path = self.layout.branch_path(branch_slug)
        node_paths = [
            self.layout.node_path(branch_slug, np["id"])
            for np in node_payloads
        ]

        # Dirty check BEFORE any write (SQLite or YAML) so a refusal
        # leaves the system exactly as it was.
        self._check_dirty([branch_path, *node_paths], force=force)

        # Mirror write: SQLite first so an exception surfaces before
        # we litter the working tree with half-formed YAML.
        saved = save_branch_definition(
            self.base_path, branch_def=branch.to_dict(),
        )

        _write_yaml(branch_path, branch_payload)
        self._stage_hook(branch_path)

        for node_payload, node_path in zip(node_payloads, node_paths, strict=True):
            _write_yaml(node_path, node_payload)
            self._stage_hook(node_path)

        return saved

    # ── Goal ──────────────────────────────────────────────────────

    def save_goal(
        self, goal: dict[str, Any], *, force: bool = False,
    ) -> dict[str, Any]:
        from workflow.author_server import save_goal as _save_goal

        # Slug for dirty-check needs the goal's pre-save name/id. If the
        # goal is new (no id), the file cannot be dirty — skip check.
        provisional_slug = slugify(goal.get("name") or goal.get("goal_id") or "")
        if provisional_slug:
            self._check_dirty(
                [self.layout.goal_path(provisional_slug)], force=force,
            )

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
