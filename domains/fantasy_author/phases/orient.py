"""Orient node -- deterministic forward-projection.

Queries the world state database for overdue promises, pacing flags,
character gaps, and continuity warnings.  Zero LLM calls -- this is
pure deterministic analysis.

Contract
--------
Input:  SceneState with identity fields populated.
Output: Partial SceneState with ``orient_result`` and ``quality_trace``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from domains.fantasy_author.phases.world_state_db import (
    compute_pacing_flags,
    connect,
    get_active_promises,
    get_all_characters,
    get_chapter_scene_count,
    get_chapter_word_count,
    get_character_gaps,
    get_overdue_promises,
    get_recent_scenes,
    init_db,
)

logger = logging.getLogger(__name__)

# Default path for the world state database.
# Can be overridden via state['_db_path'] for testing.
_DEFAULT_DB_PATH = "story.db"


def orient(state: dict[str, Any]) -> dict[str, Any]:
    """Deterministic orientation -- assembles context for plan node.

    Queries the world state database for:
    - Overdue narrative promises
    - Pacing flags (chapter length, scene word counts)
    - Character state gaps (unknown locations, neutral emotions)
    - Recent scene history for continuity
    - Arc position estimation

    Parameters
    ----------
    state : SceneState
        Must contain ``universe_id``, ``book_number``, ``chapter_number``,
        ``scene_number``.

    Returns
    -------
    dict
        Partial state with:
        - ``orient_result``: warnings and context for the plan node.
        - ``retrieved_context``: retrieval results from RetrievalRouter.
        - ``quality_trace``: decision trace entry.
    """
    from domains.fantasy_author.phases._activity import activity_log, update_phase

    scene_id = (
        f"{state['universe_id']}-B{state['book_number']}"
        f"-C{state['chapter_number']}-S{state['scene_number']}"
    )
    activity_log(state, f"Orient: analyzing context for {scene_id}")
    update_phase(state, "orient")

    db_path = state.get("_db_path", _DEFAULT_DB_PATH)

    # Ensure the database is initialized
    init_db(db_path)

    overdue_promises: list[dict[str, Any]] = []
    active_promises: list[dict[str, Any]] = []
    pacing_flags: list[dict[str, str]] = []
    character_gaps: list[dict[str, Any]] = []
    continuity_warnings: list[dict[str, str]] = []
    recent: list[dict[str, Any]] = []
    characters: list[dict[str, Any]] = []
    chapter_avg_words: int | None = None

    try:
        with connect(db_path) as conn:
            # Query overdue promises
            overdue_promises = get_overdue_promises(conn, state["chapter_number"])
            active_promises = get_active_promises(conn)

            # Compute pacing flags
            pacing_flags = compute_pacing_flags(
                conn,
                state["chapter_number"],
                state["scene_number"],
            )

            # Check for character state gaps
            character_gaps = get_character_gaps(conn)
            characters = [
                _normalize_character_state(char)
                for char in get_all_characters(conn)
            ]

            # Get recent scenes for continuity reference
            recent = get_recent_scenes(conn, state["chapter_number"], limit=3)

            # Estimate typical scene length for chapter-relative pacing checks.
            chapter_scene_count = get_chapter_scene_count(conn, state["chapter_number"])
            if chapter_scene_count > 0:
                chapter_word_count = get_chapter_word_count(conn, state["chapter_number"])
                chapter_avg_words = chapter_word_count // chapter_scene_count

            # Build continuity warnings from recent scene data
            if recent:
                last_scene = recent[0]
                if last_scene.get("verdict") == "revert":
                    continuity_warnings.append({
                        "type": "prior_revert",
                        "text": (
                            f"Previous scene ({last_scene['scene_id']}) was reverted. "
                            "Consider whether this scene needs to account for that."
                        ),
                    })
    except Exception as e:
        logger.warning("Failed to query world state DB: %s", e)
        # Continue with empty results -- orient should never block

    # Estimate arc position from chapter/scene numbers
    arc_position = _estimate_arc_position(
        state["chapter_number"],
        state["scene_number"],
        state.get("_chapters_target"),
    )

    # --- Read canon files for direct context injection ---
    canon_context = _read_canon_context(state)

    # --- Extract POV character for epistemic filtering ---
    pov_character, access_tier = _extract_pov_and_tier(state, db_path)

    warnings = _build_orient_warnings(
        overdue_promises=overdue_promises,
        pacing_flags=pacing_flags,
        character_gaps=character_gaps,
        continuity_warnings=continuity_warnings,
    )
    world_state = _build_world_state_snapshot(
        chapter_number=state["chapter_number"],
        scene_number=state["scene_number"],
        characters=characters,
        active_promises=active_promises,
        recent_scenes=recent,
        chapter_avg_words=chapter_avg_words,
    )

    orient_result = {
        "scene_id": scene_id,
        "overdue_promises": overdue_promises,
        "active_promises": active_promises,
        "pacing_flags": pacing_flags,
        "character_gaps": character_gaps,
        "continuity_warnings": continuity_warnings,
        "warnings": warnings,
        "characters": characters,
        "world_state": world_state,
        "chapter_avg_words": chapter_avg_words,
        "arc_position": arc_position,
        "recent_prose": state.get("recent_prose", ""),
        "canon_context": canon_context,
        "pov_character": pov_character,
        "access_tier": access_tier,
    }

    total_warnings = (
        len(overdue_promises) + len(pacing_flags)
        + len(character_gaps) + len(continuity_warnings)
    )

    # --- Unified search policy ---
    state_with_orient = dict(state)
    state_with_orient["orient_result"] = orient_result
    state_with_orient["_pov_character"] = pov_character
    search_context = _assemble_search_context(state_with_orient, "orient")
    retrieved_context = search_context.get("retrieved_context", {})
    memory_context = search_context.get("memory_context", {})

    result: dict[str, Any] = {
        "orient_result": orient_result,
        "retrieved_context": retrieved_context,
        "memory_context": memory_context,
        "search_context": search_context,
        "quality_trace": [
            {
                "node": "orient",
                "scene_id": scene_id,
                "action": "orient_real",
                "warnings_count": total_warnings,
                "overdue_promises": len(overdue_promises),
                "pacing_flags": len(pacing_flags),
                "character_gaps": len(character_gaps),
                "continuity_warnings": len(continuity_warnings),
                "search_sources": search_context.get("sources", []),
                "search_token_count": search_context.get("token_count", 0),
                "search_fact_count": len(retrieved_context.get("facts", [])),
            }
        ],
    }
    return result


def _estimate_arc_position(
    chapter_number: int,
    scene_number: int,
    chapters_target: int | None = None,
) -> str:
    """Estimate the narrative arc position based on chapter/scene numbers.

    Parameters
    ----------
    chapter_number : int
    scene_number : int
    chapters_target : int or None
        Total expected chapters. If None, uses a default of 20.

    Returns
    -------
    str
        One of: ``'setup'``, ``'rising_action'``, ``'midpoint'``,
        ``'complications'``, ``'climax'``, ``'falling_action'``,
        ``'resolution'``.
    """
    target = chapters_target or 20
    progress = chapter_number / target

    if progress < 0.1:
        return "setup"
    elif progress < 0.3:
        return "rising_action"
    elif progress < 0.4:
        return "midpoint"
    elif progress < 0.6:
        return "complications"
    elif progress < 0.8:
        return "climax"
    elif progress < 0.9:
        return "falling_action"
    else:
        return "resolution"


def _normalize_character_state(character: dict[str, Any]) -> dict[str, Any]:
    """Normalize DB character rows to the scene-state character contract."""
    char = dict(character)
    char.setdefault("id", char.get("character_id", char.get("name", "unknown")))
    return char


def _build_orient_warnings(
    *,
    overdue_promises: list[dict[str, Any]],
    pacing_flags: list[dict[str, str]],
    character_gaps: list[dict[str, Any]],
    continuity_warnings: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Flatten orient diagnostics into one warnings list for downstream consumers."""
    warnings: list[dict[str, Any]] = [*pacing_flags, *continuity_warnings]

    for promise in overdue_promises:
        warnings.append({
            "type": "overdue_promise",
            "promise_id": promise.get("id"),
            "text": promise.get("text", ""),
        })

    for gap in character_gaps:
        char_name = gap.get("name") or gap.get("character_id", "unknown")
        warnings.append({
            "type": "character_gap",
            "character": char_name,
            "text": f"Character state incomplete for {char_name}.",
        })

    return warnings


def _build_world_state_snapshot(
    *,
    chapter_number: int,
    scene_number: int,
    characters: list[dict[str, Any]],
    active_promises: list[dict[str, Any]],
    recent_scenes: list[dict[str, Any]],
    chapter_avg_words: int | None,
) -> dict[str, Any]:
    """Assemble a deterministic world-state snapshot for planning and memory."""
    return {
        "chapter_number": chapter_number,
        "scene_number": scene_number,
        "chapter_avg_words": chapter_avg_words,
        "characters": characters,
        "active_promises": active_promises,
        "recent_scenes": recent_scenes,
    }


def _assemble_memory(state: dict[str, Any], phase: str) -> dict:
    """Compatibility wrapper around the shared search policy."""
    from workflow.retrieval.agentic_search import assemble_memory_context

    return assemble_memory_context(state, phase)


def _assemble_search_context(state: dict[str, Any], phase: str) -> dict[str, Any]:
    """Build the unified search surface for the orient phase."""
    from workflow.retrieval.agentic_search import assemble_phase_search_context

    return assemble_phase_search_context(state, phase)


def _extract_pov_and_tier(
    state: dict[str, Any],
    db_path: str,
) -> tuple[str | None, int]:
    """Determine the POV character and access tier for this scene.

    Strategy (in priority order):
    1. Most recently updated character in the world state DB
       (the character who appeared in the latest scene).
    2. First character entity in the KG.
    3. None (no epistemic filtering).

    Access tier comes from the KG entity's ``access_tier`` field.
    Defaults to 0 (public knowledge only) if unknown.

    Returns (pov_character, access_tier).
    """
    pov_character: str | None = None
    access_tier = 0

    # 1. Try world state DB: most recently updated character
    try:
        from domains.fantasy_author.phases.world_state_db import get_all_characters

        with connect(db_path) as conn:
            characters = get_all_characters(conn)
        if characters:
            # Sort by last_updated_scene descending to find the most recent
            characters.sort(
                key=lambda c: c.get("last_updated_scene", ""),
                reverse=True,
            )
            pov_character = characters[0].get("character_id") or characters[0].get("name")
    except Exception:
        pass

    # 2. Look up access_tier from the KG entity table
    if pov_character:
        try:
            from fantasy_author import runtime

            kg = runtime.knowledge_graph
            if kg is not None:
                entity = kg.get_entity(pov_character)
                if entity:
                    access_tier = entity.get("access_tier", 0)
        except Exception:
            pass

    return pov_character, access_tier


def _run_retrieval(
    state: dict[str, Any],
    scene_id: str,
    pov_character: str | None = None,
    access_tier: int = 0,
) -> dict[str, Any]:
    """Compatibility wrapper around the shared phase retrieval policy."""
    from workflow.retrieval.agentic_search import run_phase_retrieval

    retrieval_state = dict(state)
    retrieval_state.setdefault("orient_result", {})
    retrieval_state["orient_result"] = dict(retrieval_state["orient_result"])
    retrieval_state["orient_result"]["scene_id"] = scene_id
    retrieval_state["orient_result"]["pov_character"] = pov_character
    retrieval_state["orient_result"]["access_tier"] = access_tier
    return run_phase_retrieval(retrieval_state, "orient")


def _build_orient_query(state: dict[str, Any], scene_id: str) -> str:
    """Compatibility wrapper around the shared query builder."""
    from workflow.retrieval.agentic_search import build_phase_query

    return build_phase_query(state, "orient", scene_id=scene_id)


def _read_canon_context(state: dict[str, Any]) -> str:
    """Read canon/*.md files and assemble them into a context string.

    Reads all non-hidden .md files from the canon directory, sorted by
    name.  Truncates each file to 2000 chars and the total to 8000 chars
    to stay within reasonable prompt budgets.

    Returns the assembled context string, or empty string if unavailable.
    """
    universe_path = state.get("_universe_path", "")
    if not universe_path:
        return ""

    canon_dir = Path(universe_path) / "canon"
    if not canon_dir.is_dir():
        return ""

    parts: list[str] = []
    total_chars = 0
    max_per_file = 2000
    max_total = 8000

    try:
        for f in sorted(canon_dir.iterdir()):
            if not f.is_file() or f.suffix != ".md" or f.name.startswith("."):
                continue
            try:
                content = f.read_text(encoding="utf-8")[:max_per_file]
                if content.strip():
                    section = f"### {f.stem.replace('_', ' ').title()}\n\n{content}"
                    parts.append(section)
                    total_chars += len(section)
                    if total_chars >= max_total:
                        break
            except OSError:
                continue
    except OSError:
        return ""

    if not parts:
        return ""

    result = "\n\n".join(parts)
    logger.info("Loaded canon context: %d files, %d chars", len(parts), len(result))
    return result
