"""Stopword filter for fact_extraction.py NER patterns.

Task #20 / Mission 26 #B3. The regex fallback extractor's patterns
(`_NAME_PATTERN`, `_LOCATION_PATTERN`, `_ACTION_PATTERN`) match
sentence-initial stopwords as proper nouns ("If Kael", "For",
"Manual", "Oxygen") because capitalization alone cannot distinguish
a sentence-starting connective from a real proper noun.

`_filter_sentence_starts` drops any match that is (or begins with) a
stopword. These tests cover:

- Unit: the helper's drop rules (exact-match, first-token, preserve
  legitimate names).
- End-to-end: `extract_facts_regex` no longer emits facts whose
  subject/location is a stopword, using the exact Mission 26 reproduction
  prose.
"""

from __future__ import annotations

from domains.fantasy_daemon.phases.fact_extraction import (
    _NER_SENTENCE_STOPWORDS,
    _filter_sentence_starts,
    extract_facts_regex,
)

# ---------------------------------------------------------------------------
# Helper unit tests
# ---------------------------------------------------------------------------


class TestFilterSentenceStarts:

    def test_drops_exact_stopword_match(self):
        # Single-word matches that equal a stopword are dropped.
        assert _filter_sentence_starts(["If"]) == []
        assert _filter_sentence_starts(["The"]) == []
        assert _filter_sentence_starts(["He"]) == []

    def test_drops_when_first_token_is_stopword(self):
        # Greedy regex can capture "If Kael" — filter strips the whole
        # match (not just the stopword prefix) because the leading
        # stopword corrupts the entity identity.
        assert _filter_sentence_starts(["If Kael"]) == []
        assert _filter_sentence_starts(["The Chamber"]) == []
        assert _filter_sentence_starts(["For Oxygen"]) == []

    def test_keeps_legitimate_single_word_names(self):
        assert _filter_sentence_starts(["Kael"]) == ["Kael"]
        assert _filter_sentence_starts(["Ryn"]) == ["Ryn"]
        # Capitalized noun that isn't in the stopword set passes —
        # plausibility gating is upstream's job.
        assert _filter_sentence_starts(["Hall"]) == ["Hall"]

    def test_keeps_legitimate_multi_word_names(self):
        assert _filter_sentence_starts(["Kael Voss"]) == ["Kael Voss"]
        assert _filter_sentence_starts(["Marcus Aurelius"]) == [
            "Marcus Aurelius",
        ]

    def test_mixed_list_drops_only_bad(self):
        result = _filter_sentence_starts(["Kael", "If", "Ryn", "The Pod"])
        assert result == ["Kael", "Ryn"]

    def test_empty_input(self):
        assert _filter_sentence_starts([]) == []

    def test_empty_string_filtered(self):
        assert _filter_sentence_starts([""]) == []

    def test_second_token_stopword_is_kept(self):
        # Only the FIRST token triggers rejection — "Kael If" (unusual
        # but possible in dialogue prose) passes because only the
        # leading position is checked. Prevents over-aggressive drops.
        assert _filter_sentence_starts(["Kael If"]) == ["Kael If"]

    def test_stopword_set_includes_mission_26_evidence(self):
        # The exact tokens navigator cited in the 2026-04-19 audit.
        for tok in ("If", "For", "Manual", "Oxygen"):
            assert tok in _NER_SENTENCE_STOPWORDS


# ---------------------------------------------------------------------------
# End-to-end — regex fallback extractor
# ---------------------------------------------------------------------------


class TestExtractFactsRegexStopwords:
    """`extract_facts_regex` must not emit facts whose subject is a
    sentence-initial stopword.
    """

    def test_if_kael_does_not_become_action_fact_subject(self):
        # Mission 26 reproduction: a sentence whose "If" at the start
        # was being captured by the ACTION pattern as a subject.
        # Post-fix: only real subjects survive. "opened" is in the
        # ACTION verb list.
        prose = "If Kael opened the pod.\nRyn watched the dial."
        facts = extract_facts_regex(prose, scene_id="s1", chapter_number=1)
        # No fact's text may start with "If".
        for f in facts:
            assert not f.text.startswith("If "), (
                f"regex leaked sentence-initial 'If' as action subject: "
                f"{f.text!r}"
            )

    def test_kael_action_still_extracted(self):
        # The legitimate subject after the stopword must still be
        # extracted. "Kael opened" and "Ryn watched" are both valid.
        prose = "Kael opened the pod.\nRyn watched the dial."
        facts = extract_facts_regex(prose, scene_id="s1", chapter_number=1)
        texts = {f.text for f in facts}
        assert "Kael opened." in texts
        assert "Ryn watched." in texts

    def test_article_in_action_position_filtered(self):
        # "The watched" shouldn't produce a fact. Article leaking in.
        prose = "The watched intently.\nKael saw it."
        facts = extract_facts_regex(prose, scene_id="s1", chapter_number=1)
        texts = {f.text for f in facts}
        assert "The watched." not in texts
        assert "Kael saw." in texts

    def test_pronoun_as_action_subject_filtered(self):
        # "He opened the pod." regex captures "He opened" — classic
        # pronoun-as-proper-noun false positive from sentence start.
        prose = "He opened the pod."
        facts = extract_facts_regex(prose, scene_id="s1", chapter_number=1)
        texts = {f.text for f in facts}
        assert "He opened." not in texts

    def test_location_with_stopword_prefix_filtered(self):
        # "through The Atrium" — LOCATION pattern group(1) = "The Atrium".
        # Leading stopword → dropped. Future refinement can trim-and-keep
        # the tail, but for now drop matches spec.
        prose = "She walked through The Atrium slowly."
        facts = extract_facts_regex(prose, scene_id="s1", chapter_number=1)
        for f in facts:
            assert "near/at The " not in f.text, (
                f"location leaked with stopword prefix: {f.text!r}"
            )

    def test_clean_location_still_extracted(self):
        # "to the Hall" — regex eats "the" via its optional group, so
        # group(1) = "Hall". Hall is NOT a stopword; must survive.
        prose = "She walked to the Hall quickly."
        facts = extract_facts_regex(prose, scene_id="s1", chapter_number=1)
        location_facts = [
            f for f in facts if "Scene takes place near/at" in f.text
        ]
        assert any("Hall" in f.text for f in location_facts), (
            "legitimate location 'Hall' should survive stopword filter"
        )

    def test_mixed_stopwords_and_real_names(self):
        # Hit multiple Mission 26 patterns at once and confirm exactly
        # the real names leak through.
        prose = (
            "If Kael opened the pod slowly.\n"
            "Manual looked at the console.\n"
            "Oxygen filtered through the vents.\n"
            "Ryn watched silently.\n"
            "For a moment, nothing moved.\n"
        )
        facts = extract_facts_regex(prose, scene_id="s1", chapter_number=1)
        action_subjects = {
            f.text.split(" ", 1)[0]
            for f in facts
            if "walked" not in f.text  # skip locations via filter
        }
        # Must contain real names
        assert "Kael" in action_subjects or "Kael" in {
            t.split()[0] for t in (f.text for f in facts)
        }
        assert "Ryn" in {
            f.text.split()[0] for f in facts if not f.text.startswith("Scene")
        }
        # Must NOT contain stopwords
        for bad in ("If", "Manual", "Oxygen", "For", "The", "He", "She"):
            assert bad not in action_subjects, (
                f"stopword '{bad}' leaked as action subject"
            )
