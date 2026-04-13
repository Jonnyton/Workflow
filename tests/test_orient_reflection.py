"""Tests for bounded reflection loop in orient phase.

Validates the deterministic gap detection, context merging, and
re-query capping added by the orient reflection feature.
"""

from __future__ import annotations

from domains.fantasy_author.phases.orient import (
    _MAX_REFLECTION_PASSES,
    _MIN_ENTITY_FACT_COUNT,
    RetrievalGap,
    _detect_continuity_gap,
    _detect_premise_mismatch,
    _detect_promise_context_gap,
    _detect_retrieval_gaps,
    _merge_contexts,
)

# ---------------------------------------------------------------------------
# RetrievalGap dataclass
# ---------------------------------------------------------------------------


class TestRetrievalGap:
    def test_gap_str_open(self):
        gap = RetrievalGap(
            kind="missing_pov",
            detail="POV character 'Kael' absent",
            query_terms=["Kael"],
        )
        assert "missing_pov" in str(gap)
        assert "open" in str(gap)

    def test_gap_str_resolved(self):
        gap = RetrievalGap(
            kind="missing_pov",
            detail="POV character 'Kael' absent",
            resolved=True,
        )
        assert "resolved" in str(gap)

    def test_gap_defaults(self):
        gap = RetrievalGap(kind="test", detail="test detail")
        assert gap.query_terms == []
        assert gap.resolved is False


# ---------------------------------------------------------------------------
# Gap detection
# ---------------------------------------------------------------------------


class TestDetectRetrievalGaps:
    def test_no_gaps_when_context_is_adequate(self):
        """Full context with POV, prose, and enough facts -> no gaps."""
        retrieved = {
            "facts": [
                {"text": "Kael drew his sword", "entity": "Kael"},
                {"text": "The tower crumbled", "entity": "tower"},
                {"text": "Mira watched from afar", "entity": "Mira"},
            ],
            "prose_chunks": ["Kael stepped forward into the darkness."],
        }
        characters = [{"name": "Kael"}, {"name": "Mira"}]
        gaps = _detect_retrieval_gaps(retrieved, characters, "Kael", [])
        assert gaps == []

    def test_missing_pov_detected(self):
        """POV character not in facts or prose -> missing_pov gap."""
        retrieved = {
            "facts": [{"text": "The tower stood tall", "entity": "tower"}],
            "prose_chunks": ["The wind howled through the valley."],
        }
        gaps = _detect_retrieval_gaps(retrieved, [], "Kael", [])
        assert len(gaps) == 1
        assert gaps[0].kind == "missing_pov"
        assert "Kael" in gaps[0].query_terms

    def test_pov_in_facts_resolves_gap(self):
        """POV character in a fact text -> no missing_pov gap."""
        retrieved = {
            "facts": [{"text": "Kael is a warrior", "entity": "Kael"}],
            "prose_chunks": ["The wind howled."],
        }
        gaps = _detect_retrieval_gaps(retrieved, [], "Kael", [])
        pov_gaps = [g for g in gaps if g.kind == "missing_pov"]
        assert pov_gaps == []

    def test_pov_in_prose_resolves_gap(self):
        """POV character in a prose chunk -> no missing_pov gap."""
        retrieved = {
            "facts": [],
            "prose_chunks": ["Kael stepped into the light."],
        }
        # Will still trigger low_entity_facts if characters present,
        # but should NOT trigger missing_pov
        gaps = _detect_retrieval_gaps(retrieved, [], "Kael", [])
        pov_gaps = [g for g in gaps if g.kind == "missing_pov"]
        assert pov_gaps == []

    def test_no_pov_skips_check(self):
        """If pov_character is None, missing_pov check is skipped."""
        retrieved = {"facts": [], "prose_chunks": ["some prose"]}
        gaps = _detect_retrieval_gaps(retrieved, [], None, [])
        pov_gaps = [g for g in gaps if g.kind == "missing_pov"]
        assert pov_gaps == []

    def test_no_prose_chunks_detected(self):
        """Empty prose_chunks -> no_prior_scene gap."""
        retrieved = {
            "facts": [{"text": "fact1"}],
            "prose_chunks": [],
        }
        gaps = _detect_retrieval_gaps(retrieved, [], None, [])
        scene_gaps = [g for g in gaps if g.kind == "no_prior_scene"]
        assert len(scene_gaps) == 1

    def test_low_entity_facts_detected(self):
        """Known characters + too few facts -> low_entity_facts gap."""
        retrieved = {
            "facts": [{"text": "one fact"}],  # below _MIN_ENTITY_FACT_COUNT
            "prose_chunks": ["some prose"],
        }
        characters = [{"name": "Kael"}, {"name": "Mira"}]
        gaps = _detect_retrieval_gaps(retrieved, characters, None, [])
        entity_gaps = [g for g in gaps if g.kind == "low_entity_facts"]
        assert len(entity_gaps) == 1
        assert "kael" in entity_gaps[0].query_terms

    def test_enough_facts_no_entity_gap(self):
        """Enough facts for named entities -> no low_entity_facts gap."""
        retrieved = {
            "facts": [{"text": f"fact {i}"} for i in range(_MIN_ENTITY_FACT_COUNT)],
            "prose_chunks": ["some prose"],
        }
        characters = [{"name": "Kael"}]
        gaps = _detect_retrieval_gaps(retrieved, characters, None, [])
        entity_gaps = [g for g in gaps if g.kind == "low_entity_facts"]
        assert entity_gaps == []

    def test_character_gaps_contribute_to_entity_names(self):
        """character_gaps entries are included in named entity set."""
        retrieved = {
            "facts": [],  # zero facts
            "prose_chunks": ["some prose"],
        }
        char_gaps = [{"name": "Orphan"}]
        gaps = _detect_retrieval_gaps(retrieved, [], None, char_gaps)
        entity_gaps = [g for g in gaps if g.kind == "low_entity_facts"]
        assert len(entity_gaps) == 1
        assert "orphan" in entity_gaps[0].query_terms

    def test_multiple_gaps_at_once(self):
        """All three gap types can fire simultaneously."""
        retrieved = {"facts": [], "prose_chunks": []}
        characters = [{"name": "Kael"}]
        gaps = _detect_retrieval_gaps(
            retrieved, characters, "Kael", [],
        )
        kinds = {g.kind for g in gaps}
        assert "missing_pov" in kinds
        assert "no_prior_scene" in kinds
        assert "low_entity_facts" in kinds


# ---------------------------------------------------------------------------
# Context merging
# ---------------------------------------------------------------------------


class TestMergeContexts:
    def test_merge_facts_deduplicates(self):
        base = {"facts": [{"text": "fact A"}]}
        addition = {"facts": [{"text": "fact A"}, {"text": "fact B"}]}
        merged = _merge_contexts(base, addition)
        texts = [f["text"] for f in merged["facts"]]
        assert texts == ["fact A", "fact B"]

    def test_merge_prose_chunks_deduplicates(self):
        base = {"prose_chunks": ["chunk1"]}
        addition = {"prose_chunks": ["chunk1", "chunk2"]}
        merged = _merge_contexts(base, addition)
        assert merged["prose_chunks"] == ["chunk1", "chunk2"]

    def test_merge_token_counts_sum(self):
        base = {"token_count": 100}
        addition = {"token_count": 50}
        merged = _merge_contexts(base, addition)
        assert merged["token_count"] == 150

    def test_merge_empty_addition(self):
        base = {"facts": [{"text": "fact1"}], "token_count": 100}
        merged = _merge_contexts(base, {})
        assert merged["facts"] == [{"text": "fact1"}]
        assert merged["token_count"] == 100

    def test_merge_relationships_appended(self):
        base = {"relationships": ["r1"]}
        addition = {"relationships": ["r2"]}
        merged = _merge_contexts(base, addition)
        assert merged["relationships"] == ["r1", "r2"]

    def test_merge_preserves_base_scalar_fields(self):
        base = {"facts": [], "custom_field": "keep_this", "token_count": 0}
        addition = {"facts": [], "custom_field": "ignore", "token_count": 10}
        merged = _merge_contexts(base, addition)
        assert merged["custom_field"] == "keep_this"

    def test_merge_sources_deduplicates(self):
        base = {"sources": ["kg", "vector"]}
        addition = {"sources": ["vector", "raptor"]}
        merged = _merge_contexts(base, addition)
        assert sorted(merged["sources"]) == ["kg", "raptor", "vector"]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestReflectionConstants:
    def test_max_passes_is_bounded(self):
        assert _MAX_REFLECTION_PASSES == 2

    def test_min_entity_facts_is_reasonable(self):
        assert _MIN_ENTITY_FACT_COUNT >= 1
        assert _MIN_ENTITY_FACT_COUNT <= 10


# ---------------------------------------------------------------------------
# Extended gap detection: premise mismatch
# ---------------------------------------------------------------------------


class TestPremiseMismatch:
    def test_wrong_universe_entities_trigger_gap(self):
        """Retrieved context with no premise terms -> premise_mismatch."""
        retrieved = {
            "facts": [
                {"text": "Wren crept through Durnhollow"},
                {"text": "Torben raiders attacked from the east"},
            ],
            "prose_chunks": ["Daeren watched from Vael Reach."],
        }
        state = {
            "workflow_instructions": {
                "premise": (
                    "Loral Duskspore studies Mycoturgy in the Underhallow."
                ),
            },
        }
        gaps = _detect_premise_mismatch(retrieved, state)
        assert len(gaps) == 1
        assert gaps[0].kind == "premise_mismatch"

    def test_correct_universe_no_gap(self):
        """Retrieved context with premise terms -> no gap."""
        retrieved = {
            "facts": [
                {"text": "Loral explored the Underhallow caverns"},
            ],
            "prose_chunks": ["Mycoturgy threads pulsed in the dark."],
        }
        state = {
            "workflow_instructions": {
                "premise": (
                    "Loral Duskspore studies Mycoturgy in the Underhallow."
                ),
            },
        }
        gaps = _detect_premise_mismatch(retrieved, state)
        assert gaps == []

    def test_no_premise_skips_check(self):
        """No premise in state -> no gap (can't check)."""
        retrieved = {
            "facts": [{"text": "random fact"}],
            "prose_chunks": [],
        }
        state = {"workflow_instructions": {}}
        gaps = _detect_premise_mismatch(retrieved, state)
        assert gaps == []

    def test_empty_context_no_false_positive(self):
        """Empty retrieved context -> no false positive."""
        retrieved = {"facts": [], "prose_chunks": []}
        state = {
            "workflow_instructions": {
                "premise": "Loral Duskspore in the Underhallow.",
            },
        }
        gaps = _detect_premise_mismatch(retrieved, state)
        assert gaps == []  # No content to check against


# ---------------------------------------------------------------------------
# Extended gap detection: continuity gap
# ---------------------------------------------------------------------------


class TestContinuityGap:
    def test_scene_1_never_has_gap(self):
        """Scene 1 has no prior scene to check."""
        retrieved = {"facts": [], "prose_chunks": []}
        state = {"scene_number": 1}
        gaps = _detect_continuity_gap(retrieved, state)
        assert gaps == []

    def test_scene_2_with_prior_prose_no_gap(self):
        """Scene 2 with recent_prose available -> no gap."""
        retrieved = {"facts": [], "prose_chunks": []}
        state = {
            "scene_number": 2,
            "recent_prose": "Loral walked through the cavern.",
        }
        gaps = _detect_continuity_gap(retrieved, state)
        assert gaps == []

    def test_scene_2_no_prior_prose_triggers_gap(self):
        """Scene 2 with no prior prose and no chunks -> continuity_gap."""
        retrieved = {"facts": [], "prose_chunks": []}
        state = {"scene_number": 2, "recent_prose": "", "_last_scene_prose": ""}
        gaps = _detect_continuity_gap(retrieved, state)
        assert len(gaps) == 1
        assert gaps[0].kind == "continuity_gap"

    def test_scene_2_with_prose_chunks_no_gap(self):
        """Scene 2 with prose chunks in retrieval -> no gap."""
        retrieved = {
            "facts": [],
            "prose_chunks": ["Prior scene content."],
        }
        state = {"scene_number": 2, "recent_prose": "", "_last_scene_prose": ""}
        gaps = _detect_continuity_gap(retrieved, state)
        assert gaps == []


# ---------------------------------------------------------------------------
# Extended gap detection: promise context gap
# ---------------------------------------------------------------------------


class TestPromiseContextGap:
    def test_overdue_promise_absent_from_context(self):
        """Overdue promise not in retrieved context -> gap."""
        retrieved = {
            "facts": [{"text": "The weather was fair"}],
            "prose_chunks": ["Morning light filled the cave."],
        }
        state = {
            "orient_result": {
                "overdue_promises": [
                    {"trigger_text": "the sealed chamber"},
                ],
                "active_promises": [],
            },
        }
        gaps = _detect_promise_context_gap(retrieved, state)
        assert len(gaps) == 1
        assert gaps[0].kind == "promise_context_gap"
        assert "sealed chamber" in gaps[0].detail

    def test_promise_present_in_context_no_gap(self):
        """Promise text in retrieved facts -> no gap."""
        retrieved = {
            "facts": [{"text": "the sealed chamber must be opened"}],
            "prose_chunks": [],
        }
        state = {
            "orient_result": {
                "overdue_promises": [
                    {"trigger_text": "the sealed chamber"},
                ],
                "active_promises": [],
            },
        }
        gaps = _detect_promise_context_gap(retrieved, state)
        assert gaps == []

    def test_no_promises_no_gap(self):
        """No active or overdue promises -> no gap."""
        retrieved = {"facts": [], "prose_chunks": []}
        state = {
            "orient_result": {
                "overdue_promises": [],
                "active_promises": [],
            },
        }
        gaps = _detect_promise_context_gap(retrieved, state)
        assert gaps == []

    def test_partial_promise_coverage_no_gap(self):
        """Some promises in context, some missing -> no gap if partial."""
        retrieved = {
            "facts": [{"text": "the locked door remained shut"}],
            "prose_chunks": [],
        }
        state = {
            "orient_result": {
                "overdue_promises": [
                    {"trigger_text": "the locked door"},
                    {"trigger_text": "the missing key"},
                ],
                "active_promises": [],
            },
        }
        gaps = _detect_promise_context_gap(retrieved, state)
        # Only triggers when ALL promises are absent
        assert gaps == []


class TestExtendedGapsThroughDetect:
    """Verify extended gaps fire when state is passed to _detect_retrieval_gaps."""

    def test_premise_mismatch_via_main_function(self):
        """_detect_retrieval_gaps with state should detect premise_mismatch."""
        retrieved = {
            "facts": [{"text": "Wren in Durnhollow"}],
            "prose_chunks": ["Torben attacked."],
        }
        state = {
            "workflow_instructions": {
                "premise": "Loral Duskspore in the Underhallow.",
            },
            "orient_result": {},
            "scene_number": 1,
        }
        gaps = _detect_retrieval_gaps(
            retrieved, [], None, [], state=state,
        )
        kinds = {g.kind for g in gaps}
        assert "premise_mismatch" in kinds
