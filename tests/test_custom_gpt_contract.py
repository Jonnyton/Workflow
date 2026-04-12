"""Contract tests for the Custom GPT instruction and action schema files."""

from __future__ import annotations

from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


class TestCustomGPTInstructions:
    def test_notes_are_the_feedback_path(self):
        text = _read("custom_gpt/instructions.md")
        assert "Notes are the only feedback/edit path for future writing." in text
        assert "Permanent world facts and story properties (POV, tone, style)." not in text


class TestCustomGPTSchema:
    def test_status_schema_exposes_process_fields(self):
        schema = _read("custom_gpt/actions_schema.yaml")
        assert "last_process_score:" in schema
        assert "process_failures:" in schema

    def test_add_note_description_owns_feedback(self):
        schema = _read("custom_gpt/actions_schema.yaml")
        assert "Notes are the only feedback/edit" in schema
        assert "path for future writing." in schema
