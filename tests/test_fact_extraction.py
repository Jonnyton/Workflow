"""Tests for fact extraction (fantasy_author.nodes.fact_extraction).

Covers: FactWithContext dataclass, regex extraction, LLM response parsing,
promise detection, enums, and temporal/access logic.
"""

from __future__ import annotations

import json

from fantasy_author.nodes.fact_extraction import (
    FactWithContext,
    LanguageType,
    NarrativeFunction,
    SourceType,
    TruthValue,
    build_extraction_prompt,
    detect_promises,
    extract_facts_from_llm_response,
    extract_facts_regex,
)

# ---------------------------------------------------------------------------
# FactWithContext dataclass
# ---------------------------------------------------------------------------


class TestFactWithContext:
    def test_defaults(self):
        f = FactWithContext(fact_id="f1", text="The sky is blue.")
        assert f.source_type == SourceType.NARRATOR_CLAIM
        assert f.language_type == LanguageType.LITERAL
        assert f.narrative_function == NarrativeFunction.WORLD_FACT
        assert f.confidence == 0.5
        assert f.importance == 0.5
        assert f.pov_characters == []
        assert f.access_tier == 0

    def test_is_accessible_to(self):
        f = FactWithContext(
            fact_id="f1", text="Secret lore.",
            access_tier=2, pov_characters=["ryn"],
        )
        # Ryn with high enough tier
        assert f.is_accessible_to("ryn", 2) is True
        # Ryn with too low tier
        assert f.is_accessible_to("ryn", 1) is False
        # Kael with high tier but not in pov_characters
        assert f.is_accessible_to("kael", 2) is False

    def test_is_accessible_no_pov_restriction(self):
        f = FactWithContext(
            fact_id="f1", text="Public fact.", access_tier=0,
        )
        assert f.is_accessible_to("anyone", 0) is True

    def test_is_valid_at_chapter(self):
        f = FactWithContext(
            fact_id="f1", text="Temporal fact.",
            valid_from_chapter=3, valid_to_chapter=7,
        )
        assert f.is_valid_at_chapter(2) is False
        assert f.is_valid_at_chapter(3) is True
        assert f.is_valid_at_chapter(5) is True
        assert f.is_valid_at_chapter(7) is True
        assert f.is_valid_at_chapter(8) is False

    def test_is_valid_open_ended(self):
        f = FactWithContext(
            fact_id="f1", text="Open fact.",
            valid_from_chapter=3, valid_to_chapter=None,
        )
        assert f.is_valid_at_chapter(100) is True
        assert f.is_valid_at_chapter(2) is False

    def test_to_dict(self):
        f = FactWithContext(
            fact_id="f1", text="Test.",
            source_type=SourceType.WORLD_TRUTH,
        )
        d = f.to_dict()
        assert d["fact_id"] == "f1"
        assert d["source_type"] == "world_truth"
        assert isinstance(d, dict)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TestEnums:
    def test_source_type_values(self):
        assert SourceType.NARRATOR_CLAIM.value == "narrator_claim"
        assert SourceType.CHARACTER_BELIEF.value == "character_belief"
        assert SourceType.WORLD_TRUTH.value == "world_truth"

    def test_language_type_values(self):
        assert LanguageType.LITERAL.value == "literal"
        assert LanguageType.METAPHORICAL.value == "metaphorical"
        assert LanguageType.IRONIC.value == "ironic"

    def test_truth_value_values(self):
        assert TruthValue.INITIAL.value == "initial"
        assert TruthValue.REVEALED.value == "revealed"


# ---------------------------------------------------------------------------
# Regex extraction
# ---------------------------------------------------------------------------


class TestRegexExtraction:
    def test_extracts_character_actions(self):
        prose = "Ryn walked through the forest. Kael drew his sword."
        facts = extract_facts_regex(prose, "s1", chapter_number=1)
        texts = [f.text for f in facts]
        assert any("Ryn walked" in t for t in texts)
        assert any("Kael drew" in t for t in texts)

    def test_extracts_locations(self):
        prose = "She traveled to the Northern Gate and paused near Ashwater Bridge."
        facts = extract_facts_regex(prose, "s1", chapter_number=1)
        texts = [f.text for f in facts]
        assert any("Northern Gate" in t for t in texts)
        assert any("Ashwater Bridge" in t for t in texts)

    def test_sets_scene_id(self):
        prose = "Ryn walked away."
        facts = extract_facts_regex(prose, "test-scene-42")
        for f in facts:
            assert "test-scene-42" in f.fact_id
            assert f.seeded_scene == "test-scene-42"

    def test_empty_prose_returns_empty(self):
        facts = extract_facts_regex("", "s1")
        assert facts == []

    def test_no_matches_returns_empty(self):
        facts = extract_facts_regex("the quiet afternoon passed", "s1")
        assert facts == []

    def test_deduplicates_locations(self):
        prose = "She went to the Northern Gate. Later she returned to the Northern Gate."
        facts = extract_facts_regex(prose, "s1")
        location_facts = [f for f in facts if "Northern Gate" in f.text]
        assert len(location_facts) == 1

    def test_pov_character_set_as_narrator(self):
        prose = "Ryn walked slowly."
        facts = extract_facts_regex(prose, "s1", pov_character="Ryn")
        for f in facts:
            assert f.narrator == "Ryn"


# ---------------------------------------------------------------------------
# LLM response parsing
# ---------------------------------------------------------------------------


class TestLLMResponseParsing:
    def test_valid_json_array(self):
        data = [
            {
                "text": "Ryn is a Glass-Singer.",
                "source_type": "narrator_claim",
                "importance": 0.8,
                "confidence": 0.9,
            },
            {
                "text": "The treaty was signed.",
                "source_type": "world_truth",
            },
        ]
        response = json.dumps(data)
        facts = extract_facts_from_llm_response(response, "s1", chapter_number=2)
        assert len(facts) == 2
        assert facts[0].text == "Ryn is a Glass-Singer."
        assert facts[0].importance == 0.8
        assert facts[1].source_type == SourceType.WORLD_TRUTH

    def test_json_with_markdown_wrapper(self):
        response = "Here are the facts:\n```json\n" + json.dumps([
            {"text": "A fact."}
        ]) + "\n```"
        facts = extract_facts_from_llm_response(response, "s1")
        assert len(facts) == 1

    def test_invalid_json_returns_empty(self):
        facts = extract_facts_from_llm_response("not json at all", "s1")
        assert facts == []

    def test_missing_text_field_skipped(self):
        data = [
            {"text": "Valid fact."},
            {"importance": 0.5},  # Missing text
        ]
        facts = extract_facts_from_llm_response(json.dumps(data), "s1")
        assert len(facts) == 1

    def test_invalid_enum_falls_back(self):
        data = [
            {
                "text": "Some fact.",
                "source_type": "invalid_type",
                "language_type": "bogus",
            }
        ]
        facts = extract_facts_from_llm_response(json.dumps(data), "s1")
        assert len(facts) == 1
        assert facts[0].source_type == SourceType.NARRATOR_CLAIM
        assert facts[0].language_type == LanguageType.LITERAL


# ---------------------------------------------------------------------------
# Promise detection
# ---------------------------------------------------------------------------


class TestPromiseDetection:
    def test_detects_foreshadowing(self):
        prose = "She knew that someday the truth would be revealed."
        promises = detect_promises(prose, "s1", chapter_number=1)
        assert len(promises) >= 1
        assert any(p["promise_type"] == "foreshadowing" for p in promises)

    def test_detects_character_vow(self):
        prose = "He swore he would find the lost blade."
        promises = detect_promises(prose, "s1")
        assert any(p["promise_type"] == "character_vow" for p in promises)

    def test_detects_mystery(self):
        prose = "A secret passage lay hidden behind the tapestry."
        promises = detect_promises(prose, "s1")
        types = [p["promise_type"] for p in promises]
        assert "mystery" in types

    def test_detects_prophecy(self):
        prose = "The prophecy foretold a dark winter."
        promises = detect_promises(prose, "s1")
        types = [p["promise_type"] for p in promises]
        assert "prophecy" in types

    def test_no_promises_in_plain_prose(self):
        prose = "The sun set behind the hills. Birds sang."
        promises = detect_promises(prose, "s1")
        assert promises == []

    def test_promise_includes_context(self):
        prose = "X" * 50 + " He vowed to return. " + "Y" * 50
        promises = detect_promises(prose, "s1")
        assert len(promises) >= 1
        assert "vowed" in promises[0]["context"]


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------


class TestPromptBuilding:
    def test_basic_prompt(self):
        prompt = build_extraction_prompt("Some prose text.")
        assert "Some prose text." in prompt

    def test_includes_pov_character(self):
        prompt = build_extraction_prompt("Prose.", pov_character="Ryn")
        assert "Ryn" in prompt
