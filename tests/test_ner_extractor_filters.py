"""Tests for the NER fact-extractor stop-word filters (task #51).

User-sim Mission 26 found `character_states` polluted with sentence
fragments captured as entities: "If Kael", "For", "Manual", "Oxygen".
These tests pin the filter contract on `_upsert_characters_from_facts`
+ `_infer_fact_entity` so regressions surface before the DB does.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from domains.fantasy_daemon.phases.commit import (
    _NAME_STOPWORDS,
    _infer_fact_entity,
    _is_plausible_name,
    _trim_leading_stopwords,
    _upsert_characters_from_facts,
)

# -------------------------------------------------------------------
# _trim_leading_stopwords
# -------------------------------------------------------------------


def test_trim_single_leading_stopword():
    assert _trim_leading_stopwords("If Kael") == "Kael"


def test_trim_multiple_leading_stopwords():
    assert _trim_leading_stopwords("In The Hall Kael") == "Hall Kael"


def test_trim_stops_at_first_non_stopword():
    """Stopwords in the MIDDLE are not stripped — only leading ones."""
    assert _trim_leading_stopwords("Kael For Oxygen") == "Kael For Oxygen"


def test_trim_all_stopwords_returns_empty():
    assert _trim_leading_stopwords("If For The") == ""


def test_trim_preserves_non_stopword_input():
    assert _trim_leading_stopwords("Kael Ryndor") == "Kael Ryndor"


# -------------------------------------------------------------------
# _is_plausible_name
# -------------------------------------------------------------------


def test_valid_single_word_name():
    assert _is_plausible_name("Kael") is True


def test_valid_multi_word_name():
    assert _is_plausible_name("Kael Ryndor") is True


def test_reject_too_short():
    """2-char name like "If" fails the min-length floor."""
    assert _is_plausible_name("If") is False
    assert _is_plausible_name("Ab") is False


def test_accept_three_char_name():
    """3-char names like "Kai" and "Ryn" should be accepted."""
    assert _is_plausible_name("Kai") is True
    assert _is_plausible_name("Ryn") is True


def test_reject_stopword_first_token():
    """Multi-word where first token is stopword — caller should have
    trimmed, but defense-in-depth gates it anyway."""
    assert _is_plausible_name("If Kael") is False
    assert _is_plausible_name("For Oxygen") is False


def test_reject_empty_string():
    assert _is_plausible_name("") is False


def test_reject_short_token_in_sequence():
    """A name with any token < 3 chars is rejected (e.g. "Ryn X")."""
    assert _is_plausible_name("Ryn X") is False


def test_reject_stopword_in_middle():
    """Stopword tokens anywhere in the sequence are poisonous."""
    assert _is_plausible_name("Kael For Oxygen") is False


def test_reject_mission_26_garbage_fragments():
    """Regression guard for the exact fragments Mission 26 found."""
    for fragment in ["If Kael", "For", "Manual", "Oxygen", "Stasis"]:
        assert _is_plausible_name(fragment) is False, (
            f"Mission 26 garbage fragment {fragment!r} must be rejected"
        )


def test_stopword_set_includes_mission_26_additions():
    """Regression guard — the key stopwords added by task #51 must stay."""
    for required in (
        "If", "For", "Manual", "Oxygen", "Stasis", "A", "An",
        "In", "Of", "On", "From",
    ):
        assert required in _NAME_STOPWORDS, (
            f"_NAME_STOPWORDS missing critical entry {required!r}"
        )


# -------------------------------------------------------------------
# _infer_fact_entity — downstream usage
# -------------------------------------------------------------------


@dataclass
class _Fact:
    text: str = ""
    pov_characters: list[str] | None = None
    narrator: str | None = None

    @property
    def fact_id(self) -> str:  # pragma: no cover - unused here
        return "fact-x"


def test_infer_prefers_pov_characters():
    f = _Fact(pov_characters=["Kael"], text="If Kael ran to Oxygen.")
    assert _infer_fact_entity(f) == "Kael"


def test_infer_trims_leading_stopword_in_text():
    """Text-fallback path must strip leading stopwords before gating."""
    f = _Fact(text="If Kael ran to the stasis pod.")
    assert _infer_fact_entity(f) == "Kael"


def test_infer_rejects_all_stopword_phrases():
    f = _Fact(text="In The Hall the door closed.")
    # First match "In The Hall" → trim "In" + "The" → "Hall" plausible → Hall.
    # Verify the trim chain actually finds Hall.
    assert _infer_fact_entity(f) == "Hall"


def test_infer_returns_none_when_no_plausible_name():
    f = _Fact(text="If For And But Or Yet.")
    assert _infer_fact_entity(f) is None


# -------------------------------------------------------------------
# _upsert_characters_from_facts — end-to-end integration
# -------------------------------------------------------------------


class _StubConn:
    """Minimal conn-like stub so upsert doesn't hit sqlite."""

    def execute(self, *args, **kwargs) -> Any:
        return self

    def fetchone(self) -> None:
        return None

    def commit(self) -> None:
        pass


class _StubFact:
    def __init__(
        self,
        fact_id: str,
        text: str = "",
        pov_characters: list[str] | None = None,
        narrator: str | None = None,
    ):
        self.fact_id = fact_id
        self.text = text
        self.pov_characters = pov_characters or []
        self.narrator = narrator


def _collect_upserted(monkeypatch) -> list[str]:
    """Patch `upsert_character` to record char_ids instead of DB-writing.

    `commit.py` imports the symbol at module load time, so we patch it
    on the loaded module object resolved via the file path.
    """
    import importlib
    commit_mod = importlib.import_module(
        "domains.fantasy_daemon.phases.commit"
    )

    captured: list[str] = []

    def _capture(conn, *, character_id, name, knowledge_facts, last_updated_scene):
        captured.append(character_id)

    monkeypatch.setattr(commit_mod, "upsert_character", _capture)
    return captured


def test_upsert_rejects_if_kael_fragment(monkeypatch):
    captured = _collect_upserted(monkeypatch)
    facts = [
        _StubFact("f1", text="If Kael ran to the stasis pod.", pov_characters=["Kael"]),
    ]

    _upsert_characters_from_facts(_StubConn(), facts, scene_id="scene-1")

    # "Kael" survives; "If Kael" fragment does NOT.
    assert "kael" in captured
    assert "if_kael" not in captured


def test_upsert_rejects_manual_oxygen_stasis(monkeypatch):
    """Mission 26 regression: these capitalized nouns must not become characters."""
    captured = _collect_upserted(monkeypatch)
    facts = [
        _StubFact(
            "f1",
            text="Manual override engaged. Oxygen depleted. Stasis Field failed.",
        ),
    ]

    _upsert_characters_from_facts(_StubConn(), facts, scene_id="scene-1")

    for forbidden in ("manual", "oxygen", "stasis", "stasis_field"):
        assert forbidden not in captured, (
            f"{forbidden!r} leaked into character_states via NER extractor"
        )


def test_upsert_rejects_for_alone(monkeypatch):
    """Single-word "For" from sentence-start must not be a character."""
    captured = _collect_upserted(monkeypatch)
    facts = [_StubFact("f1", text="For the record, Kael survived.")]

    _upsert_characters_from_facts(_StubConn(), facts, scene_id="s-1")

    assert "for" not in captured
    assert "kael" in captured


def test_upsert_rejects_garbage_pov_characters_field(monkeypatch):
    """LLM-hallucinated pov_characters like ["If", "Manual"] must be filtered."""
    captured = _collect_upserted(monkeypatch)
    facts = [
        _StubFact(
            "f1",
            text="Kael walked into the hall.",
            pov_characters=["If", "Manual", "Kael"],
        ),
    ]

    _upsert_characters_from_facts(_StubConn(), facts, scene_id="s-1")

    assert "kael" in captured
    assert "if" not in captured
    assert "manual" not in captured


def test_upsert_preserves_legitimate_characters(monkeypatch):
    """Non-regression: real character names still come through."""
    captured = _collect_upserted(monkeypatch)
    facts = [
        _StubFact(
            "f1",
            text="Kael Ryndor approached Captain Sarah.",
            pov_characters=["Kael Ryndor"],
        ),
    ]

    _upsert_characters_from_facts(_StubConn(), facts, scene_id="s-1")

    assert "kael_ryndor" in captured
    assert "captain_sarah" in captured
