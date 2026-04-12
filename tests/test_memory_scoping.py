"""Tests for Phase 3.5 (explicit scope handling) and Phase 3.6 (agent-controlled tools)."""

from __future__ import annotations

import pytest

from workflow.memory.scoping import MemoryScope, ScopedMemoryRouter, ScopedQuery, ScopeResolver
from workflow.memory.tools import (
    get_memory_tools,
    memory_assert,
    memory_conflicts,
    memory_consolidate,
    memory_forget,
    memory_promote,
    memory_search,
)

# =====================================================================
# MemoryScope Tests
# =====================================================================


class TestMemoryScope:
    """Test MemoryScope dataclass and methods."""

    def test_universal_scope(self):
        """A universal scope has only universe_id."""
        scope = MemoryScope(universe_id="world")
        assert scope.universe_id == "world"
        assert scope.branch_id is None
        assert scope.author_id is None
        assert scope.user_id is None
        assert scope.session_id is None

    def test_branch_scope(self):
        """A branch scope adds a branch_id."""
        scope = MemoryScope(universe_id="world", branch_id="main")
        assert scope.universe_id == "world"
        assert scope.branch_id == "main"

    def test_contains_broader_than_narrower(self):
        """A broader scope contains a narrower one."""
        universal = MemoryScope(universe_id="world")
        branch = MemoryScope(universe_id="world", branch_id="main")
        assert universal.contains(branch)
        assert not branch.contains(universal)

    def test_contains_same_scope(self):
        """A scope contains itself."""
        scope = MemoryScope(universe_id="world", branch_id="main")
        assert scope.contains(scope)

    def test_contains_different_universes(self):
        """Scopes in different universes don't contain each other."""
        world1 = MemoryScope(universe_id="world1", branch_id="main")
        world2 = MemoryScope(universe_id="world2", branch_id="main")
        assert not world1.contains(world2)
        assert not world2.contains(world1)

    def test_overlaps_same_branch_different_author(self):
        """Two scopes for the same branch but different authors don't overlap
        (they represent distinct subsets of the branch)."""
        branch_alice = MemoryScope(universe_id="world", branch_id="main", author_id="alice")
        branch_bob = MemoryScope(universe_id="world", branch_id="main", author_id="bob")
        # Different authors on same branch means no overlap in their personal scopes
        assert not branch_alice.overlaps(branch_bob)

    def test_overlaps_same_branch_universal_author(self):
        """A branch-author scope overlaps with a universal-author branch scope."""
        branch_alice = MemoryScope(universe_id="world", branch_id="main", author_id="alice")
        branch_all = MemoryScope(universe_id="world", branch_id="main")
        # Alice's work is a subset of main's universal facts
        assert branch_alice.overlaps(branch_all)
        assert branch_all.overlaps(branch_alice)

    def test_overlaps_different_branches(self):
        """Two scopes for different branches don't overlap."""
        branch1 = MemoryScope(universe_id="world", branch_id="main")
        branch2 = MemoryScope(universe_id="world", branch_id="dev")
        assert not branch1.overlaps(branch2)

    def test_narrow_valid(self):
        """Narrowing a scope is valid."""
        universal = MemoryScope(universe_id="world")
        narrower = universal.narrow(branch_id="main")
        assert narrower.branch_id == "main"
        assert universal.contains(narrower)

    def test_narrow_conflict_raises(self):
        """Narrowing to a conflicting value raises an error."""
        scope = MemoryScope(universe_id="world", branch_id="main")
        with pytest.raises(ValueError, match="Cannot narrow branch"):
            scope.narrow(branch_id="dev")

    def test_broaden_removes_constraint(self):
        """Broadening removes a constraint."""
        scoped = MemoryScope(universe_id="world", branch_id="main", author_id="alice")
        broader = scoped.broaden(author_id=None)
        assert broader.author_id is None
        assert broader.branch_id == "main"

    def test_to_filter_dict(self):
        """to_filter_dict returns only non-None fields."""
        scope = MemoryScope(
            universe_id="world",
            branch_id="main",
            author_id=None,
            user_id="alice",
        )
        filter_dict = scope.to_filter_dict()
        assert filter_dict == {
            "universe_id": "world",
            "branch_id": "main",
            "user_id": "alice",
        }
        assert "author_id" not in filter_dict


# =====================================================================
# ScopedQuery Tests
# =====================================================================


class TestScopedQuery:
    """Test ScopedQuery dataclass."""

    def test_minimal_query(self):
        """Create a minimal query with just scope."""
        scope = MemoryScope(universe_id="world")
        query = ScopedQuery(scope=scope)
        assert query.scope == scope
        assert query.query_text is None
        assert query.max_results == 50

    def test_full_query(self):
        """Create a full query with all parameters."""
        scope = MemoryScope(universe_id="world", branch_id="main")
        query = ScopedQuery(
            scope=scope,
            query_text="What happened to Ryn?",
            entity="Ryn",
            attribute="history",
            time_range=("2025-01-01", "2025-12-31"),
            include_superseded=True,
            max_results=20,
            tiers=["episodic", "archival"],
        )
        assert query.query_text == "What happened to Ryn?"
        assert query.entity == "Ryn"
        assert query.max_results == 20


# =====================================================================
# ScopeResolver Tests
# =====================================================================


class TestScopeResolver:
    """Test scope resolution and permission logic."""

    def test_resolve_caller_sees_universal_from_branch(self):
        """A branch-scoped caller can see universal facts."""
        resolver = ScopeResolver()
        caller = MemoryScope(universe_id="world", branch_id="main")
        requested = MemoryScope(universe_id="world")  # Universal
        effective = resolver.resolve_effective_scope(requested, caller)
        assert effective.branch_id == "main"

    def test_resolve_rejects_cross_branch_access(self):
        """A branch-scoped caller cannot see other branches."""
        resolver = ScopeResolver()
        caller = MemoryScope(universe_id="world", branch_id="main")
        requested = MemoryScope(universe_id="world", branch_id="dev")
        with pytest.raises(ValueError, match="Cross-branch access denied"):
            resolver.resolve_effective_scope(requested, caller)

    def test_can_write_to_own_scope(self):
        """A caller can write to their own scope."""
        resolver = ScopeResolver()
        scope = MemoryScope(universe_id="world", branch_id="main")
        assert resolver.can_write(scope, scope)

    def test_cannot_write_to_broader_scope(self):
        """A branch-scoped caller cannot write to universal scope."""
        resolver = ScopeResolver()
        caller = MemoryScope(universe_id="world", branch_id="main")
        universal = MemoryScope(universe_id="world")
        assert not resolver.can_write(universal, caller)

    def test_visible_branches_universal_caller(self):
        """A universal caller sees all branches."""
        resolver = ScopeResolver()
        caller = MemoryScope(universe_id="world")
        branches = ["main", "dev", "feature"]
        visible = resolver.visible_branches(caller, branches)
        assert visible == branches

    def test_visible_branches_scoped_caller(self):
        """A branch-scoped caller sees only their branch."""
        resolver = ScopeResolver()
        caller = MemoryScope(universe_id="world", branch_id="main")
        branches = ["main", "dev", "feature"]
        visible = resolver.visible_branches(caller, branches)
        assert visible == ["main"]


# =====================================================================
# Agent-Controlled Tool Tests
# =====================================================================


class TestMemoryTools:
    """Test agent-controlled memory tools."""

    def test_memory_search_returns_dict(self):
        """memory_search returns a structured result."""
        result = memory_search("What happened to Ryn?")
        assert isinstance(result, dict)
        assert "success" in result
        assert "results" in result
        assert "count" in result
        assert "error" in result

    def test_memory_search_with_scope(self):
        """memory_search accepts a scope dict."""
        result = memory_search(
            "character appearance",
            scope={"universe_id": "world", "branch_id": "main"},
            max_results=5,
        )
        assert result["success"] is True

    def test_memory_promote_validation(self):
        """memory_promote rejects invalid tier progressions."""
        # Cannot promote from core.
        result = memory_promote(
            item_id="fact_1",
            from_tier="core",
            to_tier="episodic",
            reason="Test promotion",
        )
        assert result["success"] is False
        assert "core memory" in result["error"].lower()

    def test_memory_promote_valid_progression(self):
        """memory_promote accepts valid progressions."""
        result = memory_promote(
            item_id="fact_1",
            from_tier="episodic",
            to_tier="archival",
            reason="Fact has 3 scene evidence",
        )
        assert result["success"] is True
        assert result["item_id"] == "fact_1"

    def test_memory_forget_soft_delete(self):
        """memory_forget soft deletes by default."""
        result = memory_forget(
            item_id="fact_1",
            reason="Superseded by new observation",
            hard_delete=False,
        )
        assert result["success"] is True
        assert result["deleted"] is False

    def test_memory_forget_hard_delete(self):
        """memory_forget can hard delete."""
        result = memory_forget(
            item_id="fact_1",
            reason="Completely wrong",
            hard_delete=True,
        )
        assert result["success"] is True
        assert result["deleted"] is True

    def test_memory_consolidate_entity(self):
        """memory_consolidate consolidates a specific entity."""
        result = memory_consolidate(
            entity="Ryn",
            scope={"universe_id": "world"},
        )
        assert result["success"] is True
        assert result["entity"] == "Ryn"

    def test_memory_assert_basic(self):
        """memory_assert stores a fact."""
        result = memory_assert(
            entity="Ryn",
            attribute="class",
            value="Scout",
            confidence=0.95,
        )
        assert result["success"] is True
        assert "fact_id" in result
        assert result["confidence"] == 0.95

    def test_memory_conflicts_entity(self):
        """memory_conflicts returns conflicts for an entity."""
        result = memory_conflicts(
            entity="Ryn",
            scope={"universe_id": "world"},
        )
        assert result["success"] is True
        assert "conflicts" in result
        assert "count" in result

    def test_get_memory_tools_returns_list(self):
        """get_memory_tools returns a list of tool dicts."""
        tools = get_memory_tools()
        assert isinstance(tools, list)
        assert len(tools) == 6

    def test_get_memory_tools_have_required_fields(self):
        """Each tool has name, description, function, and inputs."""
        tools = get_memory_tools()
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "function" in tool
            assert "inputs" in tool
            assert callable(tool["function"])

    def test_get_memory_tools_names(self):
        """get_memory_tools returns the expected tools."""
        tools = get_memory_tools()
        names = {t["name"] for t in tools}
        expected = {
            "memory_search",
            "memory_promote",
            "memory_forget",
            "memory_consolidate",
            "memory_assert",
            "memory_conflicts",
        }
        assert names == expected


# =====================================================================
# ScopedMemoryRouter Tests
# =====================================================================


class TestScopedMemoryRouter:
    """Test the scoped router wrapper."""

    def test_router_initializes(self):
        """ScopedMemoryRouter initializes with a manager."""
        # Mock manager
        mock_manager = type("MockManager", (), {})()
        router = ScopedMemoryRouter(mock_manager)
        assert router._manager is mock_manager

    def test_router_query_returns_list(self):
        """router.query returns a list (placeholder implementation)."""
        mock_manager = type("MockManager", (), {})()
        router = ScopedMemoryRouter(mock_manager)
        query = ScopedQuery(scope=MemoryScope(universe_id="world"))
        result = router.query(query)
        assert isinstance(result, list)

    def test_router_store_accepts_data_and_scope(self):
        """router.store accepts data and scope without error."""
        mock_manager = type("MockManager", (), {})()
        router = ScopedMemoryRouter(mock_manager)
        scope = MemoryScope(universe_id="world", branch_id="main")
        data = {"fact_id": "f1", "text": "Ryn is a scout"}
        # Should not raise
        router.store(data, scope)
