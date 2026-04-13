"""Memory manager -- central interface for the three-tier hierarchy.

Consumed by graph-core nodes via:
    ``MemoryManager.assemble_context(phase, state) -> ContextBundle``

Coordinates core, episodic, and archival memory to build phase-specific
context bundles that fit within the ~8-15K token budget.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from workflow.memory.archival import ArchivalMemory
from workflow.memory.core import CoreMemory
from workflow.memory.episodic import EpisodicMemory
from workflow.memory.promotion import PromotionGates, PromotionResult
from workflow.memory.reflexion import ReflexionEngine, ReflexionResult

logger = logging.getLogger(__name__)

# Phase names matching SceneState flow.
ORIENT = "orient"
PLAN = "plan"
DRAFT = "draft"
EVALUATE = "evaluate"

# Maximum token budget for assembled context.
MAX_CONTEXT_TOKENS = 15_000


class ContextBundle(dict):
    """Phase-specific context assembled from the memory hierarchy.

    Extends dict so nodes can access fields with bracket notation.
    """

    @property
    def phase(self) -> str:
        return self.get("phase", "")


class MemoryManager:
    """Central memory coordinator for all four graph levels.

    Parameters
    ----------
    universe_id : str
        Universe namespace.
    db_path : str | Path
        Path to SQLite database for episodic memory.
    window_chapters : int
        Sliding window size for episodic memory.
    """

    def __init__(
        self,
        universe_id: str,
        db_path: str | Path = ":memory:",
        window_chapters: int = 5,
    ) -> None:
        self.core = CoreMemory(universe_id)
        self.episodic = EpisodicMemory(
            db_path=db_path,
            universe_id=universe_id,
            window_chapters=window_chapters,
        )
        self.archival = ArchivalMemory(universe_id, db_path=str(db_path))
        self._promotion = PromotionGates()
        self._reflexion = ReflexionEngine(episodic=self.episodic)
        self._universe_id = universe_id

    def close(self) -> None:
        """Release resources."""
        self.episodic.close()

    # ------------------------------------------------------------------
    # Primary interface: assemble context for a given phase
    # ------------------------------------------------------------------

    def assemble_context(
        self,
        phase: str,
        state: dict[str, Any],
    ) -> ContextBundle:
        """Build a phase-specific context bundle from all memory tiers.

        Parameters
        ----------
        phase : str
            One of ``'orient'``, ``'plan'``, ``'draft'``, ``'evaluate'``.
        state : dict
            Current scene/chapter state.

        Returns
        -------
        ContextBundle
            Dict-like object with phase-relevant fields.
        """
        builder = {
            ORIENT: self._assemble_orient,
            PLAN: self._assemble_plan,
            DRAFT: self._assemble_draft,
            EVALUATE: self._assemble_evaluate,
        }

        build_fn = builder.get(phase, self._assemble_orient)
        bundle = build_fn(state)
        bundle["phase"] = phase

        tokens = self.core.estimated_tokens()
        if tokens > MAX_CONTEXT_TOKENS:
            logger.warning(
                "Context bundle exceeds budget: ~%d tokens (max %d) — trimming",
                tokens, MAX_CONTEXT_TOKENS,
            )
            bundle = self._trim_to_budget(bundle, tokens)

        return ContextBundle(bundle)

    # ------------------------------------------------------------------
    # Budget enforcement
    # ------------------------------------------------------------------

    def _trim_to_budget(
        self, bundle: dict[str, Any], current_tokens: int
    ) -> dict[str, Any]:
        """Progressively trim low-priority fields until under budget.

        Priority order (trimmed first to last):
          1. recent_reflections — least critical, easily regenerated
          2. recent_summaries / recent_scenes — reduce window
          3. facts / canon_facts — keep first N
          4. active_characters — summarise instead of full state
          5. world_state — keep as-is (highest priority)
        """
        ratio = MAX_CONTEXT_TOKENS / max(current_tokens, 1)

        # Trim list-valued fields proportionally
        _list_fields = [
            "recent_reflections",
            "recent_summaries",
            "recent_scenes",
            "facts",
            "canon_facts",
            "promises",
            "orient_warnings",
            "character_goals",
        ]
        for key in _list_fields:
            items = bundle.get(key)
            if isinstance(items, list) and len(items) > 1:
                keep = max(1, int(len(items) * ratio))
                bundle[key] = items[:keep]

        # Trim character dicts: strip verbose fields, keep essentials
        chars = bundle.get("active_characters")
        if isinstance(chars, dict) and current_tokens > MAX_CONTEXT_TOKENS * 2:
            trimmed = {}
            _keep_keys = {"name", "id", "role", "goals", "status"}
            for cid, cdata in chars.items():
                if isinstance(cdata, dict):
                    trimmed[cid] = {
                        k: v for k, v in cdata.items() if k in _keep_keys
                    }
                else:
                    trimmed[cid] = cdata
            bundle["active_characters"] = trimmed

        return bundle

    # ------------------------------------------------------------------
    # Phase-specific assemblers
    # ------------------------------------------------------------------

    def _assemble_orient(self, state: dict[str, Any]) -> dict[str, Any]:
        """ORIENT: world state, promises, warnings, reflections."""
        chapter = state.get("chapter_number", 1)
        characters = state.get("orient_result", {}).get("characters", [])

        # Core: load active characters and world state.
        self.core.clear()
        self.core.load_characters(characters)
        self.core.load_world_state(
            state.get("orient_result", {}).get("world_state", {})
        )

        # Episodic: recent summaries for continuity.
        recent = self.episodic.get_recent(chapter=chapter, k=3)
        reflections = self.episodic.get_recent_reflections(k=2)

        # Archival: open promises.
        promises = self.archival.get_open_promises(overdue=True)

        return {
            "world_state": self.core.get("world_state", "current", {}),
            "active_characters": self.core.get_all("characters"),
            "active_promises": promises,
            "recent_summaries": [
                {"ch": s.chapter_number, "sc": s.scene_number, "summary": s.summary}
                for s in recent
            ],
            "recent_reflections": reflections,
            "continuity_flags": [],
        }

    def _assemble_plan(self, state: dict[str, Any]) -> dict[str, Any]:
        """PLAN: beat context, character goals, orient warnings, style rules."""
        chapter = state.get("chapter_number", 1)
        scene_chars = state.get("orient_result", {}).get("characters", [])
        char_names = [
            c.get("name", c.get("id", "")) for c in scene_chars
        ]

        # Archival: facts about characters in this scene.
        facts = self.archival.hipporag_query(entities=char_names, k=20)

        # Archival: open promises.
        promises = self.archival.get_open_promises(overdue=True)

        # Episodic: recent summaries.
        recent = self.episodic.get_recent(chapter=chapter, k=5)

        # Core: style rules.
        style_rules = self.core.get_all("style_rules")

        return {
            "recent_scenes": [
                {"ch": s.chapter_number, "sc": s.scene_number, "summary": s.summary}
                for s in recent
            ],
            "facts": facts,
            "promises": promises,
            "orient_warnings": state.get("orient_result", {}).get("warnings", []),
            "style_rules": list(style_rules.values()),
            "character_goals": [
                c.get("goals", []) for c in scene_chars
            ],
        }

    def _assemble_draft(self, state: dict[str, Any]) -> dict[str, Any]:
        """DRAFT: recent prose, voice refs, style rules, beat sheet."""
        return {
            "recent_prose": state.get("recent_prose", ""),
            "beat_sheet": state.get("plan_output", {}),
            "voice_refs": self.core.get_all("voice_refs"),
            "style_rules": list(self.core.get_all("style_rules").values()),
        }

    def _assemble_evaluate(self, state: dict[str, Any]) -> dict[str, Any]:
        """EVALUATE: draft text, canon facts, writing system, contract."""
        draft = state.get("draft_output", {})
        scene_chars = state.get("orient_result", {}).get("characters", [])
        char_names = [
            c.get("name", c.get("id", "")) for c in scene_chars
        ]

        canon_facts = self.archival.hipporag_query(entities=char_names, k=30)

        return {
            "draft_text": draft.get("prose", ""),
            "word_count": draft.get("word_count", 0),
            "canon_facts": canon_facts,
            "scene_contract": state.get("plan_output", {}).get(
                "done_when", []
            ),
            "writing_system": self.core.get("style_rules", "writing_system", {}),
        }

    # ------------------------------------------------------------------
    # Scene result storage
    # ------------------------------------------------------------------

    def store_scene_result(self, state: dict[str, Any]) -> None:
        """Persist scene outputs to episodic memory.

        Called after commit node accepts a scene.
        """
        draft = state.get("draft_output", {})
        summary = draft.get("prose", "")[:500]
        word_count = draft.get("word_count", 0)

        self.episodic.store_summary(
            book_number=state.get("book_number", 1),
            chapter_number=state.get("chapter_number", 1),
            scene_number=state.get("scene_number", 1),
            summary=summary,
            word_count=word_count,
        )

        # Store extracted facts.
        for fact in state.get("extracted_facts", []):
            fact_id = fact.get("fact_id")
            content = fact.get("text")
            if not fact_id or not content:
                raise ValueError(
                    "extracted_facts entries must include 'fact_id' and 'text'"
                )
            self.episodic.store_fact(
                fact_id=fact_id,
                entity=fact.get("entity", fact.get("narrator", "unknown")),
                content=content,
                source_scene=(
                    f"b{state.get('book_number', 1)}"
                    f"c{state.get('chapter_number', 1)}"
                    f"s{state.get('scene_number', 1)}"
                ),
            )

        # Store style observations.
        for obs in state.get("style_observations", []):
            self.episodic.store_observation(
                dimension=obs.get("dimension", "general"),
                observation=obs.get("observation", str(obs)),
                scene_ref=(
                    f"b{state.get('book_number', 1)}"
                    f"c{state.get('chapter_number', 1)}"
                    f"s{state.get('scene_number', 1)}"
                ),
            )

        logger.debug(
            "Stored scene result: b%d/c%d/s%d (%d words, %d facts, %d obs)",
            state.get("book_number", 1),
            state.get("chapter_number", 1),
            state.get("scene_number", 1),
            word_count,
            len(state.get("extracted_facts", [])),
            len(state.get("style_observations", [])),
        )

    # ------------------------------------------------------------------
    # Promotion gates
    # ------------------------------------------------------------------

    def run_promotion_gates(
        self,
        violations: list[dict[str, Any]] | None = None,
    ) -> PromotionResult:
        """Run all promotion gates on the current episodic state."""
        return self._promotion.run(
            episodic=self.episodic,
            violations=violations,
        )

    # ------------------------------------------------------------------
    # Reflexion
    # ------------------------------------------------------------------

    def run_reflexion(
        self,
        state: dict[str, Any],
        judge_feedback: list[dict[str, Any]] | None = None,
    ) -> ReflexionResult:
        """Run the reflexion loop on a reverted scene."""
        return self._reflexion.reflect(
            state=state,
            judge_feedback=judge_feedback,
        )

    # ------------------------------------------------------------------
    # Sliding window maintenance
    # ------------------------------------------------------------------

    def evict_old_data(self, current_chapter: int, book: int = 1) -> int:
        """Evict episodic data outside the sliding window."""
        return self.episodic.evict_old_summaries(
            current_chapter=current_chapter,
            book=book,
        )
