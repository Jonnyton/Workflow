"""Explicit scope handling for multiplayer memory.

The multiplayer architecture needs memory that knows whose branch a fact
belongs to. Scope = the combination of universe/branch/author/user/session
that determines visibility and ownership.

Provides:
  MemoryScope         -- universe/branch/author/user/session combination
  ScopedQuery         -- query parameters with scope constraints
  ScopeResolver       -- visibility and write permission logic
  ScopedMemoryRouter  -- wraps MemoryManager with scope filtering
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MemoryScope:
    """Scope = the combination of universe/branch/author/user/session.

    Determines visibility and ownership of facts, observations, and other
    memory items in a multiplayer environment.

    Attributes
    ----------
    universe_id : str
        Required. All facts exist within a universe.
    branch_id : str | None
        None = universal/shared. A branch_id = branch-specific fact.
    author_id : str | None
        None = any author. An author_id = specific author's work.
    user_id : str | None
        None = system-level. A user_id = user-specific (private).
    session_id : str | None
        None = persistent across sessions. A session_id = session-temporary.
    """

    universe_id: str
    branch_id: str | None = None
    author_id: str | None = None
    user_id: str | None = None
    session_id: str | None = None

    def contains(self, other: MemoryScope) -> bool:
        """Returns True if this scope is broader than or equal to other.

        Example: universe scope contains branch scope.
        A caller with universe scope can see branch scope, but not vice versa.
        """
        # If the other is in a different universe, this doesn't contain it.
        if self.universe_id != other.universe_id:
            return False

        # Checking each dimension: a None (broader) contains any value.
        if self.branch_id is not None and self.branch_id != other.branch_id:
            return False
        if self.author_id is not None and self.author_id != other.author_id:
            return False
        if self.user_id is not None and self.user_id != other.user_id:
            return False
        if self.session_id is not None and self.session_id != other.session_id:
            return False

        return True

    def overlaps(self, other: MemoryScope) -> bool:
        """Returns True if the two scopes share any common ground.

        Example: author A on branch X overlaps with the branch X scope.
        """
        # Different universes never overlap.
        if self.universe_id != other.universe_id:
            return False

        # Check each dimension: if both are specified and different, no overlap.
        if (
            self.branch_id is not None
            and other.branch_id is not None
            and self.branch_id != other.branch_id
        ):
            return False
        if (
            self.author_id is not None
            and other.author_id is not None
            and self.author_id != other.author_id
        ):
            return False
        if (
            self.user_id is not None
            and other.user_id is not None
            and self.user_id != other.user_id
        ):
            return False
        if (
            self.session_id is not None
            and other.session_id is not None
            and self.session_id != other.session_id
        ):
            return False

        return True

    def narrow(self, **kwargs: Any) -> MemoryScope:
        """Returns a new scope with additional constraints.

        Parameters
        ----------
        **kwargs
            Any of: branch_id, author_id, user_id, session_id.
            None values are ignored.

        Returns
        -------
        MemoryScope
            A new scope narrower than this one, or the same if no valid
            constraints were provided.

        Raises
        ------
        ValueError
            If trying to narrow to a different universe or conflicting constraint.
        """
        if kwargs.get("universe_id") and kwargs["universe_id"] != self.universe_id:
            raise ValueError(
                f"Cannot narrow to different universe: "
                f"{self.universe_id} -> {kwargs['universe_id']}"
            )

        new_branch = kwargs.get("branch_id", self.branch_id)
        if self.branch_id is not None and new_branch != self.branch_id:
            raise ValueError(
                f"Cannot narrow branch from {self.branch_id} to {new_branch}"
            )

        new_author = kwargs.get("author_id", self.author_id)
        if self.author_id is not None and new_author != self.author_id:
            raise ValueError(
                f"Cannot narrow author from {self.author_id} to {new_author}"
            )

        new_user = kwargs.get("user_id", self.user_id)
        if self.user_id is not None and new_user != self.user_id:
            raise ValueError(
                f"Cannot narrow user from {self.user_id} to {new_user}"
            )

        new_session = kwargs.get("session_id", self.session_id)
        if self.session_id is not None and new_session != self.session_id:
            raise ValueError(
                f"Cannot narrow session from {self.session_id} to {new_session}"
            )

        return MemoryScope(
            universe_id=self.universe_id,
            branch_id=new_branch,
            author_id=new_author,
            user_id=new_user,
            session_id=new_session,
        )

    def broaden(self, **kwargs: str | None) -> MemoryScope:
        """Returns a new scope with constraints removed.

        Parameters
        ----------
        **kwargs
            Any of: branch_id, author_id, user_id, session_id.
            Pass None or omit to remove that constraint.

        Returns
        -------
        MemoryScope
            A new scope broader than this one.
        """
        return MemoryScope(
            universe_id=self.universe_id,
            branch_id=kwargs.get("branch_id", self.branch_id),
            author_id=kwargs.get("author_id", self.author_id),
            user_id=kwargs.get("user_id", self.user_id),
            session_id=kwargs.get("session_id", self.session_id),
        )

    def to_filter_dict(self) -> dict[str, Any]:
        """Returns non-None fields as a dict for query filtering.

        Returns
        -------
        dict
            Keys: "universe_id", "branch_id", "author_id", "user_id", "session_id"
            Only non-None values are included.
        """
        result = {"universe_id": self.universe_id}
        if self.branch_id is not None:
            result["branch_id"] = self.branch_id
        if self.author_id is not None:
            result["author_id"] = self.author_id
        if self.user_id is not None:
            result["user_id"] = self.user_id
        if self.session_id is not None:
            result["session_id"] = self.session_id
        return result


@dataclass
class ScopedQuery:
    """Query parameters with scope constraints.

    Attributes
    ----------
    scope : MemoryScope
        The scope in which to search.
    query_text : str | None
        Free-form text query.
    entity : str | None
        Search for facts about this entity.
    attribute : str | None
        Search for facts about this attribute (e.g., "appearance", "motivation").
    time_range : tuple[str | None, str | None]
        (from_timestamp, to_timestamp) for temporal filtering. ISO 8601 strings.
    include_superseded : bool
        If False, exclude facts marked as superseded. Default: False.
    max_results : int
        Maximum number of results to return. Default: 50.
    tiers : list[str] | None
        Which memory tiers to search: "core", "episodic", "archival".
        None = all tiers.
    """

    scope: MemoryScope
    query_text: str | None = None
    entity: str | None = None
    attribute: str | None = None
    time_range: tuple[str | None, str | None] = (None, None)
    include_superseded: bool = False
    max_results: int = 50
    tiers: list[str] | None = None


class ScopeResolver:
    """Validates scope visibility and write permissions."""

    def resolve_effective_scope(
        self,
        requested: MemoryScope,
        caller_scope: MemoryScope,
    ) -> MemoryScope:
        """Compute the intersection of requested and caller-visible scope.

        A branch-scoped caller can see universal facts but not other
        branches' facts. Returns the effective scope that respects both
        the request and the caller's permissions.

        Parameters
        ----------
        requested : MemoryScope
            The scope being requested.
        caller_scope : MemoryScope
            The scope from which the caller is operating.

        Returns
        -------
        MemoryScope
            The scope the caller is actually allowed to see.

        Raises
        ------
        ValueError
            If universes don't match.
        """
        if requested.universe_id != caller_scope.universe_id:
            raise ValueError(
                f"Universe mismatch: requested {requested.universe_id}, "
                f"caller {caller_scope.universe_id}"
            )

        # The effective scope is the more specific (narrower) of the two.
        # If caller is at branch X, they can see branch X's facts but not
        # facts from other branches.
        effective_branch = requested.branch_id or caller_scope.branch_id
        effective_author = requested.author_id or caller_scope.author_id
        effective_user = requested.user_id or caller_scope.user_id
        effective_session = requested.session_id or caller_scope.session_id

        # But check for conflicts: if caller is scoped to a specific branch
        # and requested is a different branch, deny.
        if (
            caller_scope.branch_id is not None
            and requested.branch_id is not None
            and caller_scope.branch_id != requested.branch_id
        ):
            # Caller at branch X cannot see branch Y.
            raise ValueError(
                f"Cross-branch access denied: caller at {caller_scope.branch_id}, "
                f"requested {requested.branch_id}"
            )

        # Similar checks for author, user, session.
        if (
            caller_scope.author_id is not None
            and requested.author_id is not None
            and caller_scope.author_id != requested.author_id
        ):
            raise ValueError(
                f"Cross-author access denied: caller {caller_scope.author_id}, "
                f"requested {requested.author_id}"
            )

        if (
            caller_scope.user_id is not None
            and requested.user_id is not None
            and caller_scope.user_id != requested.user_id
        ):
            raise ValueError(
                f"Cross-user access denied: caller {caller_scope.user_id}, "
                f"requested {requested.user_id}"
            )

        if (
            caller_scope.session_id is not None
            and requested.session_id is not None
            and caller_scope.session_id != requested.session_id
        ):
            raise ValueError(
                f"Cross-session access denied: caller {caller_scope.session_id}, "
                f"requested {requested.session_id}"
            )

        return MemoryScope(
            universe_id=requested.universe_id,
            branch_id=effective_branch,
            author_id=effective_author,
            user_id=effective_user,
            session_id=effective_session,
        )

    def can_write(self, scope: MemoryScope, caller_scope: MemoryScope) -> bool:
        """Can this caller write to this scope?

        Writers can write to their own scope or narrower scopes. They cannot
        write to broader scopes or cross-branch/user scopes.

        Parameters
        ----------
        scope : MemoryScope
            The scope being written to.
        caller_scope : MemoryScope
            The scope from which the caller is operating.

        Returns
        -------
        bool
            True if the write is allowed, False otherwise.
        """
        if scope.universe_id != caller_scope.universe_id:
            return False

        # If caller is scoped to a specific branch, they can write to that
        # branch or narrower, but not to universal or other branches.
        if caller_scope.branch_id is not None:
            if scope.branch_id is None:
                # Caller trying to write to universal scope from a branch.
                return False
            if scope.branch_id != caller_scope.branch_id:
                # Caller trying to write to a different branch.
                return False

        # Similar logic for author, user, session.
        if caller_scope.author_id is not None:
            if scope.author_id is None:
                return False
            if scope.author_id != caller_scope.author_id:
                return False

        if caller_scope.user_id is not None:
            if scope.user_id is None:
                return False
            if scope.user_id != caller_scope.user_id:
                return False

        if caller_scope.session_id is not None:
            if scope.session_id is None:
                return False
            if scope.session_id != caller_scope.session_id:
                return False

        return True

    def visible_branches(
        self,
        caller_scope: MemoryScope,
        all_branches: list[str],
    ) -> list[str]:
        """Which branches can this caller see?

        A caller with universal scope sees all branches. A branch-scoped
        caller sees only their own branch (and maybe public branches if
        that concept exists).

        Parameters
        ----------
        caller_scope : MemoryScope
            The scope from which the caller is operating.
        all_branches : list[str]
            All available branch IDs.

        Returns
        -------
        list[str]
            Branch IDs the caller is allowed to see.
        """
        if caller_scope.branch_id is not None:
            # Branch-scoped caller sees only their own branch.
            return (
                [caller_scope.branch_id]
                if caller_scope.branch_id in all_branches
                else []
            )

        # Universal scope sees all branches.
        return all_branches


class ScopedMemoryRouter:
    """Wraps MemoryManager with scope awareness.

    Delegates actual storage/retrieval to an underlying MemoryManager but
    wraps every operation with scope filtering.

    Parameters
    ----------
    memory_manager : Any
        An instance of MemoryManager from workflow.memory.manager.
    """

    def __init__(self, memory_manager: Any) -> None:
        self._manager = memory_manager
        self._resolver = ScopeResolver()

    def query(self, scoped_query: ScopedQuery) -> list[dict[str, Any]]:
        """Routes query through scope resolution, then dispatches to tiers.

        Parameters
        ----------
        scoped_query : ScopedQuery
            Query with scope constraints.

        Returns
        -------
        list[dict]
            Matching facts/observations filtered to the caller's scope.
        """
        # For now, this is a delegation point. The actual routing and
        # consolidation of results across tiers will depend on the
        # consolidation.py and temporal.py modules being developed in
        # parallel. This method currently returns empty results as a
        # placeholder for the full implementation.

        logger.debug(
            "ScopedMemoryRouter.query: scope=%s, entity=%s, text=%s",
            scoped_query.scope,
            scoped_query.entity,
            scoped_query.query_text[:50] if scoped_query.query_text else None,
        )

        # Placeholder: return empty list. Full implementation will query
        # core, episodic, and archival tiers through the manager.
        results: list[dict[str, Any]] = []

        # TODO: Implement tier routing once consolidation.py is available.
        # Should merge results from core (active context), episodic
        # (recent facts), and archival (KG/vectors) into a single list.

        return results[:scoped_query.max_results]

    def store(self, data: dict[str, Any], scope: MemoryScope) -> None:
        """Store with scope metadata.

        Parameters
        ----------
        data : dict
            The data to store (fact, observation, etc.).
        scope : MemoryScope
            The scope in which to store it.
        """
        # Add scope metadata to the data.
        enriched = {**data, "scope": scope.to_filter_dict()}

        logger.debug(
            "ScopedMemoryRouter.store: scope=%s, keys=%s",
            scope,
            list(enriched.keys()),
        )

        # Placeholder: actual storage through manager will be implemented
        # once we determine which tier (episodic or archival) should hold
        # scoped facts.
        # TODO: Delegate to appropriate tier in self._manager.
