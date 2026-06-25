from __future__ import annotations

import json

from workflow.enrichment_signals import (
    ENRICHMENT_SIGNALS_FILENAME,
    LEGACY_WORLDBUILD_SIGNALS_FILENAME,
    load_enrichment_signals,
)


def test_neutral_empty_signal_file_does_not_fall_back_to_legacy(tmp_path) -> None:
    (tmp_path / LEGACY_WORLDBUILD_SIGNALS_FILENAME).write_text(
        json.dumps([{"type": "synthesize_source", "source_file": "old.md"}]),
        encoding="utf-8",
    )
    (tmp_path / ENRICHMENT_SIGNALS_FILENAME).write_text("[]\n", encoding="utf-8")

    assert load_enrichment_signals(tmp_path) == []
