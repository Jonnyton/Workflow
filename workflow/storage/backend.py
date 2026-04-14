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

import os
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
    "get_backend",
    "invalidate_backend_cache",
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

    def save_branch(
        self, branch: BranchDefinition, *, force: bool = False,
    ) -> dict[str, Any]:
        """Persist a Branch; return the stored dict shape."""

    def save_goal(
        self, goal: dict[str, Any], *, force: bool = False,
    ) -> dict[str, Any]:
        """Persist a Goal; return the stored dict shape."""

    def save_branch_and_commit(
        self,
        branch: BranchDefinition,
        *,
        author: str,
        message: str,
        extra_paths: list[Path] | None = None,
        force: bool = False,
    ) -> tuple[dict[str, Any], "git_bridge.CommitResult | None"]:
        """Persist a Branch + optional extras as ONE commit."""

    def save_goal_and_commit(
        self,
        goal: dict[str, Any],
        *,
        author: str,
        message: str,
        force: bool = False,
    ) -> tuple[dict[str, Any], "git_bridge.CommitResult | None"]:
        """Persist a Goal and commit in one call."""

    def save_gate_claim_and_commit(
        self,
        *,
        branch_def_id: str,
        goal_id: str,
        rung_key: str,
        evidence_url: str,
        evidence_note: str,
        claimed_by: str,
        goal_slug: str,
        branch_slug: str,
        author: str,
        message: str,
        force: bool = False,
    ) -> tuple[dict[str, Any], "git_bridge.CommitResult | None"]:
        """Claim a rung — SQLite + YAML + commit in one call.

        Raises :class:`BranchRebindError` (from the storage layer) when
        an active claim exists under a different Goal. Raises
        :class:`DirtyFileError` when the target YAML has local edits
        and ``force`` is False.
        """

    def retract_gate_claim_and_commit(
        self,
        *,
        branch_def_id: str,
        rung_key: str,
        reason: str,
        goal_slug: str,
        branch_slug: str,
        author: str,
        message: str,
        force: bool = False,
    ) -> tuple[dict[str, Any], "git_bridge.CommitResult | None"]:
        """Retract a claim — SQLite soft-delete + YAML rewrite +
        commit in one call.

        Raises :class:`KeyError` if no claim exists for
        ``(branch_def_id, rung_key)``.
        """


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

    def save_branch(
        self, branch: BranchDefinition, *, force: bool = False,  # noqa: ARG002
    ) -> dict[str, Any]:
        from workflow.author_server import save_branch_definition

        return save_branch_definition(
            self.base_path, branch_def=branch.to_dict(),
        )

    def save_goal(
        self, goal: dict[str, Any], *, force: bool = False,  # noqa: ARG002
    ) -> dict[str, Any]:
        from workflow.author_server import save_goal as _save_goal

        return _save_goal(self.base_path, goal=goal)

    def save_branch_and_commit(
        self,
        branch: BranchDefinition,
        *,
        author: str,  # noqa: ARG002
        message: str,  # noqa: ARG002
        extra_paths: list[Path] | None = None,  # noqa: ARG002
        force: bool = False,
    ) -> tuple[dict[str, Any], git_bridge.CommitResult | None]:
        """SQLite-only backend has no git seam; commit slot is always None."""
        return self.save_branch(branch, force=force), None

    def save_goal_and_commit(
        self,
        goal: dict[str, Any],
        *,
        author: str,  # noqa: ARG002
        message: str,  # noqa: ARG002
        force: bool = False,
    ) -> tuple[dict[str, Any], git_bridge.CommitResult | None]:
        """SQLite-only backend has no git seam; commit slot is always None."""
        return self.save_goal(goal, force=force), None

    def save_gate_claim_and_commit(
        self,
        *,
        branch_def_id: str,
        goal_id: str,
        rung_key: str,
        evidence_url: str,
        evidence_note: str,
        claimed_by: str,
        goal_slug: str,  # noqa: ARG002
        branch_slug: str,  # noqa: ARG002
        author: str,  # noqa: ARG002
        message: str,  # noqa: ARG002
        force: bool = False,  # noqa: ARG002
    ) -> tuple[dict[str, Any], git_bridge.CommitResult | None]:
        """SQLite-only path for a gate claim. No git seam."""
        from workflow.author_server import claim_gate

        saved = claim_gate(
            self.base_path,
            branch_def_id=branch_def_id,
            goal_id=goal_id,
            rung_key=rung_key,
            evidence_url=evidence_url,
            evidence_note=evidence_note,
            claimed_by=claimed_by,
        )
        return saved, None

    def retract_gate_claim_and_commit(
        self,
        *,
        branch_def_id: str,
        rung_key: str,
        reason: str,
        goal_slug: str,  # noqa: ARG002
        branch_slug: str,  # noqa: ARG002
        author: str,  # noqa: ARG002
        message: str,  # noqa: ARG002
        force: bool = False,  # noqa: ARG002
    ) -> tuple[dict[str, Any], git_bridge.CommitResult | None]:
        """SQLite-only path for a retract. No git seam."""
        from workflow.author_server import retract_gate_claim

        saved = retract_gate_claim(
            self.base_path,
            branch_def_id=branch_def_id,
            rung_key=rung_key,
            reason=reason,
        )
        return saved, None


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

    def save_branch_and_commit(
        self,
        branch: BranchDefinition,
        *,
        author: str,
        message: str,
        extra_paths: list[Path] | None = None,
        force: bool = False,
    ) -> tuple[dict[str, Any], git_bridge.CommitResult | None]:
        """Write branch + nodes + optional extras as ONE git commit.

        Composite semantics matter for ledger-equivalence: one public
        MCP action (``build_branch``, ``patch_branch``) produces exactly
        one commit, even when it writes N+1 YAML files. Splitting the
        commit would violate Phase 4's "one commit per public mutation"
        intent.

        Dirty-checks ALL target paths (branch + node files + extras) up
        front. If any path is dirty and ``force=False``, raises
        :class:`DirtyFileError` with every dirty path listed; nothing
        is written to SQLite or disk.

        When git is disabled, the YAML writes still happen via
        ``save_branch`` and the returned ``CommitResult`` is ``None``.
        """
        branch_slug = slugify(branch.name or branch.branch_def_id)
        _, node_payloads = branch_to_yaml_payload(
            branch, branch_slug=branch_slug,
        )
        branch_path = self.layout.branch_path(branch_slug)
        node_paths = [
            self.layout.node_path(branch_slug, np["id"])
            for np in node_payloads
        ]
        extras = list(extra_paths or [])
        all_paths = [branch_path, *node_paths, *extras]

        # Up-front dirty-check over the full payload so any refusal
        # leaves SQLite, YAML, and git index untouched.
        self._check_dirty(all_paths, force=force)

        # save_branch already runs its own dirty-check; pass force=True
        # so it doesn't re-check (we just cleared the whole payload).
        saved = self.save_branch(branch, force=True)

        # Extras: stage them. Callers are expected to have written them
        # to disk already (they're extra beyond the Branch/Node files
        # the backend owns).
        for p in extras:
            self._stage_hook(p)

        if not self._git_enabled:
            return saved, None

        # Commit with an explicit paths list. Defense-in-depth against a
        # concurrent writer staging unrelated files between our stage
        # calls and this commit.
        result = git_bridge.commit(
            message, author, paths=all_paths, repo_path=self._repo_root,
        )
        return saved, result

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

    def save_goal_and_commit(
        self,
        goal: dict[str, Any],
        *,
        author: str,
        message: str,
        force: bool = False,
    ) -> tuple[dict[str, Any], git_bridge.CommitResult | None]:
        """Save a Goal and commit in one shot. See :meth:`save_branch_and_commit`."""
        # Pre-save dirty check on the provisional slug path.
        provisional_slug = slugify(goal.get("name") or goal.get("goal_id") or "")
        if provisional_slug:
            goal_path_pre = self.layout.goal_path(provisional_slug)
            self._check_dirty([goal_path_pre], force=force)

        saved = self.save_goal(goal, force=True)

        if not self._git_enabled:
            return saved, None

        goal_slug = slugify(saved.get("name") or saved.get("goal_id"))
        goal_path = self.layout.goal_path(goal_slug)
        result = git_bridge.commit(
            message, author, paths=[goal_path], repo_path=self._repo_root,
        )
        return saved, result

    # ── Gate claims (Phase 6.3) ───────────────────────────────────

    def _write_gate_claim_yaml(
        self, saved: dict[str, Any], *, goal_slug: str, branch_slug: str,
    ) -> Path:
        """Serialize + write a claim YAML, stage it, return the path."""
        from workflow.storage.serializer import gate_claim_to_yaml_payload

        payload = gate_claim_to_yaml_payload(saved)
        claim_path = self.layout.gate_claim_path(
            goal_slug, branch_slug, saved.get("rung_key", ""),
        )
        _write_yaml(claim_path, payload)
        self._stage_hook(claim_path)
        return claim_path

    def save_gate_claim_and_commit(
        self,
        *,
        branch_def_id: str,
        goal_id: str,
        rung_key: str,
        evidence_url: str,
        evidence_note: str,
        claimed_by: str,
        goal_slug: str,
        branch_slug: str,
        author: str,
        message: str,
        force: bool = False,
    ) -> tuple[dict[str, Any], git_bridge.CommitResult | None]:
        """Claim + YAML emit + git commit, ONE atomic action.

        Dirty-check fires BEFORE the SQLite write so a refusal leaves
        the system exactly as it was. Storage-layer
        :class:`BranchRebindError` propagates unchanged — handler
        catches it; the rebind guard is not a local-edit-conflict.
        """
        from workflow.author_server import claim_gate

        claim_path = self.layout.gate_claim_path(
            goal_slug, branch_slug, rung_key,
        )
        self._check_dirty([claim_path], force=force)

        saved = claim_gate(
            self.base_path,
            branch_def_id=branch_def_id,
            goal_id=goal_id,
            rung_key=rung_key,
            evidence_url=evidence_url,
            evidence_note=evidence_note,
            claimed_by=claimed_by,
        )
        self._write_gate_claim_yaml(
            saved, goal_slug=goal_slug, branch_slug=branch_slug,
        )
        if not self._git_enabled:
            return saved, None
        result = git_bridge.commit(
            message, author, paths=[claim_path], repo_path=self._repo_root,
        )
        return saved, result

    def retract_gate_claim_and_commit(
        self,
        *,
        branch_def_id: str,
        rung_key: str,
        reason: str,
        goal_slug: str,
        branch_slug: str,
        author: str,
        message: str,
        force: bool = False,
    ) -> tuple[dict[str, Any], git_bridge.CommitResult | None]:
        """Soft-delete a claim + rewrite YAML + commit.

        Same on-disk path as :meth:`save_gate_claim_and_commit`; the
        YAML is rewritten with ``retracted_at`` populated rather than
        being deleted so git history keeps the retraction reason.
        """
        from workflow.author_server import retract_gate_claim

        claim_path = self.layout.gate_claim_path(
            goal_slug, branch_slug, rung_key,
        )
        self._check_dirty([claim_path], force=force)

        saved = retract_gate_claim(
            self.base_path,
            branch_def_id=branch_def_id,
            rung_key=rung_key,
            reason=reason,
        )
        self._write_gate_claim_yaml(
            saved, goal_slug=goal_slug, branch_slug=branch_slug,
        )
        if not self._git_enabled:
            return saved, None
        result = git_bridge.commit(
            message, author, paths=[claim_path], repo_path=self._repo_root,
        )
        return saved, result


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


# ─────────────────────────────────────────────────────────────────────
# Backend factory (Phase 7.3 H1)
# ─────────────────────────────────────────────────────────────────────

_BACKEND_CACHE: dict[tuple[str, str], StorageBackend] = {}

_BACKEND_SQLITE_ONLY = "sqlite_only"
_BACKEND_SQLITE_CACHED = "sqlite_cached"


def get_backend(
    base_path: str | Path,
    *,
    repo_root: str | Path | None = None,
) -> StorageBackend:
    """Return the memoized :class:`StorageBackend` for this (base, repo).

    Selection:

    1. ``WORKFLOW_STORAGE_BACKEND`` env var, if set to
       ``sqlite_only`` or ``sqlite_cached`` (other values ignored).
    2. Otherwise probe :func:`git_bridge.is_enabled` against
       ``repo_root`` (falls back to the process CWD). Git enabled →
       :class:`SqliteCachedBackend`; git disabled → :class:`SqliteOnlyBackend`.

    Cache key is ``(base_path, repo_root)`` — tests that relocate the
    universe directory between cases get a fresh backend automatically
    without having to explicitly invalidate. :func:`invalidate_backend_cache`
    still clears everything for re-probe scenarios.
    """
    resolved_base = Path(base_path).resolve()
    resolved_repo = Path(repo_root) if repo_root is not None else Path.cwd()
    resolved_repo = resolved_repo.resolve()
    key = (str(resolved_base), str(resolved_repo))
    cached = _BACKEND_CACHE.get(key)
    if cached is not None:
        return cached

    choice = os.environ.get("WORKFLOW_STORAGE_BACKEND", "").strip().lower()
    if choice == _BACKEND_SQLITE_ONLY:
        backend: StorageBackend = SqliteOnlyBackend(resolved_base)
    elif choice == _BACKEND_SQLITE_CACHED:
        backend = SqliteCachedBackend(resolved_base, repo_root=resolved_repo)
    elif git_bridge.is_enabled(resolved_repo):
        backend = SqliteCachedBackend(resolved_base, repo_root=resolved_repo)
    else:
        backend = SqliteOnlyBackend(resolved_base)
    _BACKEND_CACHE[key] = backend
    return backend


def invalidate_backend_cache() -> None:
    """Drop all cached backends. Test helper.

    Also invalidates the git_bridge cache so a subsequent ``get_backend``
    call re-probes the current environment.
    """
    _BACKEND_CACHE.clear()
    git_bridge.invalidate_cache()
