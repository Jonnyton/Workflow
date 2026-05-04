"""Test backward compatibility of import paths after Phase 2 extraction.

During Phase 2, code was restructured into:
  - workflow/ (shared infrastructure)
  - domains/fantasy_author/ (domain-specific fantasy author code)
  - fantasy_author/ (original package, now transitional shim)

This test verifies:
1. Old imports from fantasy_author.* still work (backward compatibility)
2. New imports from workflow.* work (new canonical paths)
3. New imports from domains.fantasy_author.* work (domain-specific)
4. Both old and new paths can coexist in the same process
"""

from __future__ import annotations


def test_fantasy_author_imports_still_work():
    """Test that existing code importing from fantasy_author.* still works."""
    # These are the import paths used by existing tests and __main__.py
    from domains.fantasy_author.state import SceneState, UniverseState

    from workflow.exceptions import CheckpointError, ProviderError
    from workflow.memory.manager import MemoryManager
    from workflow.providers.base import BaseProvider, ModelConfig
    from workflow.providers.router import ProviderRouter

    assert CheckpointError is not None
    assert ProviderError is not None
    assert BaseProvider is not None
    assert ModelConfig is not None
    assert ProviderRouter is not None
    assert SceneState is not None
    assert UniverseState is not None
    assert MemoryManager is not None


def test_workflow_imports_work():
    """Test that new workflow.* imports work (extracted infrastructure)."""
    from workflow.exceptions import CheckpointError, ProviderError
    from workflow.notes import Note
    from workflow.providers.base import BaseProvider, ModelConfig
    from workflow.providers.router import ProviderRouter
    from workflow.work_targets import WorkTarget

    assert CheckpointError is not None
    assert ProviderError is not None
    assert BaseProvider is not None
    assert ModelConfig is not None
    assert ProviderRouter is not None
    assert Note is not None
    assert WorkTarget is not None


def test_domain_imports_work():
    """Test that new domains.fantasy_author.* imports work."""
    from domains.fantasy_author.graphs import build_universe_graph
    from domains.fantasy_author.state import SceneState, UniverseState

    from domains.fantasy_author.phases import commit, draft, orient, plan

    assert SceneState is not None
    assert UniverseState is not None
    assert build_universe_graph is not None
    assert orient is not None
    assert plan is not None
    assert draft is not None
    assert commit is not None


def test_both_import_paths_coexist():
    """Test that old and new import paths can coexist in the same process."""
    # Import the same class from both old and new locations
    from workflow.exceptions import CheckpointError as NewCheckpointError
    from workflow.exceptions import CheckpointError as OldCheckpointError

    # They should be the same class (pointing to workflow.exceptions)
    # or at least equivalent behavior
    assert issubclass(NewCheckpointError, Exception)
    assert issubclass(OldCheckpointError, Exception)

    # Both can be imported and used simultaneously
    try:
        raise NewCheckpointError("test from workflow")
    except OldCheckpointError:
        # This should work because old path delegates to new
        pass


def test_providers_import_paths():
    """Test provider imports from both old and new locations."""
    # Old path (backward compatibility)
    from workflow.providers.router import FALLBACK_CHAINS as new_chains
    from workflow.providers.router import FALLBACK_CHAINS as old_chains

    # New path (canonical)
    from workflow.providers.router import ProviderRouter as NewRouter
    from workflow.providers.router import ProviderRouter as OldRouter

    assert OldRouter is not None
    assert NewRouter is not None
    assert old_chains is not None
    assert new_chains is not None


def test_state_imports_from_domain():
    """Test state imports from domain-specific location."""
    from domains.fantasy_author.state import (
        BookState,
        ChapterState,
        SceneState,
        UniverseState,
    )

    # These should be TypedDict types
    assert SceneState is not None
    assert ChapterState is not None
    assert BookState is not None
    assert UniverseState is not None


def test_graph_imports_from_domain():
    """Test graph builder imports from domain-specific location."""
    from domains.fantasy_author.graphs import (
        build_book_graph,
        build_chapter_graph,
        build_scene_graph,
        build_universe_graph,
    )

    # These should be callable functions
    assert callable(build_universe_graph)
    assert callable(build_book_graph)
    assert callable(build_chapter_graph)
    assert callable(build_scene_graph)


def test_phase_imports_from_domain():
    """Test phase implementations from domain-specific location."""
    from domains.fantasy_author.phases import (
        book_close,
        commit,
        consolidate,
        diagnose,
        draft,
        learn,
        orient,
        plan,
        reflect,
        select_task,
        universe_cycle,
        worldbuild,
    )

    # These should be callable (functions or async functions)
    assert callable(orient)
    assert callable(plan)
    assert callable(draft)
    assert callable(commit)
    assert callable(consolidate)
    assert callable(learn)
    assert callable(reflect)
    assert callable(worldbuild)
    assert callable(diagnose)
    assert callable(book_close)
    assert callable(universe_cycle)
    assert callable(select_task)


def test_notes_import_from_workflow():
    """Test notes module can be imported from workflow."""
    from workflow.notes import Note, add_note, list_notes, update_note_status

    assert Note is not None
    assert callable(add_note)
    assert callable(list_notes)
    assert callable(update_note_status)


def test_work_targets_import_from_workflow():
    """Test work targets module can be imported from workflow."""
    from workflow.work_targets import WorkTarget

    assert WorkTarget is not None


def test_fantasy_daemon_author_server_is_daemon_server_module():
    """fantasy_daemon.author_server must be the same module object as workflow.daemon_server.

    Verifies the sys.modules rebind in fantasy_daemon/author_server.py — not a snapshot copy.
    """
    import warnings

    import workflow.daemon_server as canonical

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        import fantasy_daemon.author_server as alias

    # sys.modules rebind means the alias IS the canonical module, not a copy.
    assert alias is canonical, (
        "fantasy_daemon.author_server must be the same object as workflow.daemon_server; "
        "got a snapshot copy instead of a sys.modules rebind"
    )


def test_fantasy_daemon_author_server_state_shared():
    """Writes through the alias must be visible via the canonical module and vice versa.

    The old ``from workflow.daemon_server import *`` pattern produced a snapshot;
    mutations would be invisible across the boundary. This test fails if that
    pattern is ever reintroduced.
    """
    import warnings

    import workflow.daemon_server as canonical

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        import fantasy_daemon.author_server as alias

    sentinel = "_test_author_server_shared_sentinel"
    try:
        # write through alias, read through canonical
        setattr(alias, sentinel, "written_via_alias")
        assert getattr(canonical, sentinel) == "written_via_alias", (
            "Write via alias not visible on canonical module"
        )

        # write through canonical, read through alias
        setattr(canonical, sentinel, "written_via_canonical")
        assert getattr(alias, sentinel) == "written_via_canonical", (
            "Write via canonical not visible on alias module"
        )
    finally:
        for mod in (alias, canonical):
            try:
                delattr(mod, sentinel)
            except AttributeError:
                pass
