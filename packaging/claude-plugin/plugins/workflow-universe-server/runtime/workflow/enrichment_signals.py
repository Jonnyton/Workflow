"""Domain-neutral enrichment signal queue helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ENRICHMENT_SIGNALS_FILENAME = "enrichment_signals.json"
LEGACY_WORLDBUILD_SIGNALS_FILENAME = "worldbuild_signals.json"
ENRICHMENT_STATE_KEY = "enrichment_signals"
LEGACY_WORLDBUILD_STATE_KEY = "worldbuild_signals"


def enrichment_signals_path(universe_path: str | Path) -> Path:
    return Path(universe_path) / ENRICHMENT_SIGNALS_FILENAME


def legacy_worldbuild_signals_path(universe_path: str | Path) -> Path:
    return Path(universe_path) / LEGACY_WORLDBUILD_SIGNALS_FILENAME


def state_enrichment_signals(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Return in-memory enrichment signals, accepting the legacy state key."""
    for key in (ENRICHMENT_STATE_KEY, LEGACY_WORLDBUILD_STATE_KEY):
        signals = state.get(key, [])
        if isinstance(signals, list) and signals:
            return [signal for signal in signals if isinstance(signal, dict)]
    return []


def load_enrichment_signals(universe_path: str | Path) -> list[dict[str, Any]]:
    """Load queued signals from the neutral file, falling back to the legacy file."""
    signals_path = enrichment_signals_path(universe_path)
    if signals_path.exists():
        return _read_signal_file(signals_path)
    return _read_signal_file(legacy_worldbuild_signals_path(universe_path))


def write_enrichment_signals(
    universe_path: str | Path,
    signals: list[dict[str, Any]],
) -> None:
    enrichment_signals_path(universe_path).write_text(
        json.dumps(signals, indent=2) + "\n",
        encoding="utf-8",
    )


def append_enrichment_signals(
    universe_path: str | Path,
    signals: list[dict[str, Any]],
) -> None:
    existing = load_enrichment_signals(universe_path)
    write_enrichment_signals(universe_path, existing + signals)


def _read_signal_file(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, TypeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [signal for signal in parsed if isinstance(signal, dict)]
