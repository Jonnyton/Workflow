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
    from fantasy_author.exceptions import CheckpointError, ProviderError
    from fantasy_author.memory.manager import MemoryManager
    from fantasy_author.providers.base import BaseProvider, ModelConfig
    from fantasy_author.providers.router import ProviderRouter
    from fantasy_author.state import SceneState, UniverseState

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
    from domains.fantasy_author.phases import commit, draft, orient, plan
    from domains.fantasy_author.state import SceneState, UniverseState

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
    from fantasy_author.exceptions import CheckpointError as OldCheckpointError
    from workflow.exceptions import CheckpointError as NewCheckpointError

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
    from fantasy_author.providers.router import FALLBACK_CHAINS as old_chains
    from fantasy_author.providers.router import ProviderRouter as OldRouter
    from workflow.providers.router import FALLBACK_CHAINS as new_chains

    # New path (canonical)
    from workflow.providers.router import ProviderRouter as NewRouter

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
