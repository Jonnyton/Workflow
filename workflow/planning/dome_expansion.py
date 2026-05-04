"""DOME outline expansion -- recursive deepening with KG feedback.

Implements the Dynamic Outline with Memory Enhancement pattern from
NAACL 2025 (arxiv.org/abs/2412.13575).  At each decomposition level:

    rough outline -> query KG -> refine -> detailed outline

The KG feedback parameter is stubbed until the knowledge agent's
retrieval layer is available.
"""

from __future__ import annotations

import copy
import logging

from typing_extensions import TypedDict

from workflow.planning.htn_planner import Outline, ScenePlan

logger = logging.getLogger(__name__)


class SceneBeat(TypedDict):
    """A beat within a scene -- the finest level of outline detail."""

    description: str
    character_focus: str
    tension_level: float  # 0.0-1.0
    beat_type: str  # "action", "dialogue", "reflection", "revelation"


class DetailedScene(TypedDict):
    """A scene with expanded beat-level detail."""

    title: str
    summary: str
    preconditions: list[str]
    effects: list[str]
    characters: list[str]
    location: str
    beats: list[SceneBeat]
    tension_curve: list[float]


class DetailedOutline(TypedDict):
    """An outline with per-scene beats, tension curves, and arc tracking."""

    acts: list[dict]  # Same structure as ActPlan but scenes are DetailedScene
    premise_kernel: str
    thematic_core: str
    characters_extracted: list[str]
    expansion_depth: int
    kg_enriched: bool


class DOMEExpander:
    """Recursive outline expander with optional KG feedback.

    Parameters
    ----------
    max_depth : int
        Maximum number of expansion iterations (default 2).
    """

    def __init__(self, max_depth: int = 2) -> None:
        self._max_depth = max_depth

    def expand(
        self,
        outline: Outline,
        kg_feedback: dict | None = None,
    ) -> DetailedOutline:
        """Expand a sparse outline into a detailed outline with beats.

        Parameters
        ----------
        outline : Outline
            The HTN-generated outline to expand.
        kg_feedback : dict or None
            Knowledge graph feedback for consistency checking.
            Stubbed -- when None, expansion proceeds without KG enrichment.

        Returns
        -------
        DetailedOutline
            The expanded outline with per-scene beats and tension curves.
        """
        detailed_acts: list[dict] = []

        for act in outline["acts"]:
            detailed_chapters: list[dict] = []

            for chapter in act["chapters"]:
                detailed_scenes: list[DetailedScene] = []

                for scene in chapter["scenes"]:
                    detailed = self._expand_scene(scene, kg_feedback)
                    detailed_scenes.append(detailed)

                detailed_chapter = {
                    "title": chapter["title"],
                    "summary": chapter["summary"],
                    "scenes": detailed_scenes,
                    "preconditions": chapter["preconditions"],
                    "effects": chapter["effects"],
                }
                detailed_chapters.append(detailed_chapter)

            detailed_act = {
                "name": act["name"],
                "summary": act["summary"],
                "chapters": detailed_chapters,
                "preconditions": act["preconditions"],
                "effects": act["effects"],
            }
            detailed_acts.append(detailed_act)

        # Iterative deepening: refine tension curves
        for depth in range(self._max_depth):
            detailed_acts = self._refine_pass(detailed_acts, depth, kg_feedback)

        return DetailedOutline(
            acts=detailed_acts,
            premise_kernel=outline["premise_kernel"],
            thematic_core=outline["thematic_core"],
            characters_extracted=outline["characters_extracted"],
            expansion_depth=self._max_depth,
            kg_enriched=kg_feedback is not None,
        )

    def _expand_scene(
        self,
        scene: ScenePlan,
        kg_feedback: dict | None,
    ) -> DetailedScene:
        """Expand a single scene into beats.

        Generates 3-5 beats per scene with a tension curve.
        """
        beat_count = 4  # Default beat count per scene
        beats: list[SceneBeat] = []
        beat_types = ["action", "dialogue", "reflection", "revelation"]

        for i in range(beat_count):
            # Tension rises through the scene, peaks at 3/4
            tension = self._compute_beat_tension(i, beat_count)
            beat = SceneBeat(
                description=f"Beat {i + 1} of {scene['title']}: {scene['summary']}",
                character_focus=scene["characters"][0] if scene["characters"] else "Protagonist",
                tension_level=tension,
                beat_type=beat_types[i % len(beat_types)],
            )
            beats.append(beat)

        tension_curve = [b["tension_level"] for b in beats]

        return DetailedScene(
            title=scene["title"],
            summary=scene["summary"],
            preconditions=scene["preconditions"],
            effects=scene["effects"],
            characters=scene["characters"] or ["Protagonist"],
            location=scene["location"] or "Unspecified",
            beats=beats,
            tension_curve=tension_curve,
        )

    @staticmethod
    def _compute_beat_tension(beat_index: int, total_beats: int) -> float:
        """Compute tension for a beat using a simple arc curve.

        Tension rises to a peak at approximately 3/4 through the scene,
        then drops slightly for the resolution beat.
        """
        if total_beats <= 1:
            return 0.5
        progress = beat_index / (total_beats - 1)
        # Peak at 0.75 progress
        if progress <= 0.75:
            return round(0.3 + 0.6 * (progress / 0.75), 2)
        else:
            return round(0.9 - 0.3 * ((progress - 0.75) / 0.25), 2)

    def _refine_pass(
        self,
        acts: list[dict],
        depth: int,
        kg_feedback: dict | None,
    ) -> list[dict]:
        """Refine the outline in an iterative deepening pass.

        Currently adjusts tension curves for cross-scene consistency.
        With KG feedback, this would also check entity references and
        adjust beats for knowledge boundary compliance.
        """
        refined = copy.deepcopy(acts)

        if kg_feedback is not None:
            # KG-enriched refinement: check entity consistency
            logger.info("DOME refinement pass %d with KG feedback", depth + 1)
            self._apply_kg_feedback(refined, kg_feedback)
        else:
            logger.debug("DOME refinement pass %d (no KG feedback)", depth + 1)

        # Cross-scene tension normalisation: ensure no two adjacent scenes
        # have identical peak tension
        for act in refined:
            for chapter in act["chapters"]:
                scenes = chapter["scenes"]
                for i in range(1, len(scenes)):
                    prev_peak = max(scenes[i - 1]["tension_curve"], default=0.5)
                    curr_peak = max(scenes[i]["tension_curve"], default=0.5)
                    if abs(prev_peak - curr_peak) < 0.05:
                        # Adjust current scene tension slightly
                        bump = 0.1 * (1 if i % 2 == 0 else -1)
                        scenes[i]["tension_curve"] = [
                            round(max(0.0, min(1.0, t + bump)), 2)
                            for t in scenes[i]["tension_curve"]
                        ]

        return refined

    @staticmethod
    def _apply_kg_feedback(acts: list[dict], kg_feedback: dict) -> None:
        """Apply knowledge graph feedback to refine beats.

        Checks character references in beats against KG entities and
        annotates beats with known relationships and facts.
        """
        kg_entities = kg_feedback.get("facts", [])
        relationships = kg_feedback.get("relationships", [])

        if not kg_entities and not relationships:
            return

        # Build a set of known entity names for quick lookup
        known_names: set[str] = set()
        for fact in kg_entities:
            if isinstance(fact, dict):
                text = fact.get("text", "")
                # Extract entity names from fact text (simple heuristic)
                for word in text.split():
                    if word[0:1].isupper() and len(word) > 2:
                        known_names.add(word)

        # Annotate beats with KG consistency notes
        for act in acts:
            for chapter in act.get("chapters", []):
                for scene in chapter.get("scenes", []):
                    for beat in scene.get("beats", []):
                        desc = beat.get("description", "")
                        # Flag beats that reference unknown entities
                        for word in desc.split():
                            if (word[0:1].isupper() and len(word) > 2
                                    and word not in known_names
                                    and known_names):
                                beat.setdefault("kg_notes", []).append(
                                    f"'{word}' not found in KG"
                                )
