"""Tests for ``add_canon`` + ``add_canon_from_path`` MCP actions.

Covers two defect fixes landed together:

1. ``add_canon`` previously wrote directly to ``canon/<filename>`` and
   did NOT emit the ``synthesize_source`` signal — premise/canon/entity
   synthesis never fired on MCP uploads. Now routes through
   :func:`workflow.ingestion.core.ingest_file` so the signal fires.

2. ``add_canon_from_path`` is a new action for large uploads. The MCP
   client passes an **absolute server-side path**; the server reads
   the file itself so the LLM never has to copy content through the
   tool-call arg (breaks at >20K tokens: summarization drift, output
   cutoff, JSON-escape errors).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import workflow.universe_server as us


def _call(action: str, **kwargs) -> dict:
    """Invoke an action through the dispatch+ledger path the tool uses."""
    base_kwargs = {
        "universe_id": "",
        "text": "",
        "path": "",
        "category": "direction",
        "target": "",
        "query_type": "facts",
        "filter_text": "",
        "request_type": "scene_direction",
        "branch_id": "",
        "filename": "",
        "provenance_tag": "",
        "limit": 20,
    }
    base_kwargs.update(kwargs)

    dispatch = {
        "add_canon": us._action_add_canon,
        "add_canon_from_path": us._action_add_canon_from_path,
    }
    handler = dispatch[action]
    return json.loads(us._dispatch_with_ledger(action, handler, base_kwargs))


@pytest.fixture
def universe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    base = tmp_path / "output"
    uid = "test-uni"
    (base / uid).mkdir(parents=True)
    monkeypatch.setenv("UNIVERSE_SERVER_BASE", str(base))
    monkeypatch.setenv("UNIVERSE_SERVER_DEFAULT_UNIVERSE", uid)
    monkeypatch.setenv("UNIVERSE_SERVER_USER", "test-user")
    return uid


def _signals(uid: str) -> list[dict]:
    path = us._base_path() / uid / "worldbuild_signals.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


# ─── add_canon now emits synthesize_source ─────────────────────────────


class TestAddCanonSynthesisSignal:
    def test_add_canon_emits_signal(self, universe: str) -> None:
        """The pre-fix path bypassed ingest_file and no signal ever
        fired. Post-fix: every user upload emits synthesize_source."""
        out = _call(
            "add_canon", filename="ryn.md", text="# Ryn\n\nA scout.",
            provenance_tag="rough notes",
        )
        assert out["status"] == "written"
        assert out["synthesis_signal_emitted"] is True

        signals = _signals(universe)
        assert len(signals) == 1
        assert signals[0]["type"] == "synthesize_source"
        assert signals[0]["source_file"] == "ryn.md"

    def test_add_canon_routes_to_sources_dir(self, universe: str) -> None:
        """User uploads land under ``canon/sources/`` per ingest_file
        routing, not ``canon/`` directly."""
        _call("add_canon", filename="notes.md", text="notes")
        udir = us._base_path() / universe
        assert (udir / "canon" / "sources" / "notes.md").exists()
        # The direct-to-canon path is no longer used for uploads.
        assert not (udir / "canon" / "notes.md").exists()

    def test_add_canon_ledger_entry_unchanged(self, universe: str) -> None:
        """Ledger contract from the 2a landing preserved."""
        _call(
            "add_canon", filename="ref.md", text="# Reference\n",
            provenance_tag="rough notes",
        )
        ledger_path = us._base_path() / universe / "ledger.json"
        entries = json.loads(ledger_path.read_text(encoding="utf-8"))
        assert len(entries) == 1
        assert entries[0]["action"] == "add_canon"
        assert entries[0]["target"] == "canon/ref.md"
        assert entries[0]["payload"]["provenance"] == "rough notes"


# ─── add_canon_from_path happy path ────────────────────────────────────


class TestAddCanonFromPathHappyPath:
    def test_large_file_ingests_with_signal(
        self, universe: str, tmp_path: Path,
    ) -> None:
        """A 130KB markdown file — well past the LLM tool-arg reliable
        limit — ingests cleanly and emits synthesize_source."""
        src = tmp_path / "big-lore.md"
        # 130 KB of repeated markdown. Content doesn't matter; size does.
        body = (
            "# Silent Valley Lore\n\n"
            "The river clans have traded along the Ashwater for centuries. "
            * 2000  # ~130 KB
        )
        src.write_text(body, encoding="utf-8")
        size = src.stat().st_size
        assert size > 100 * 1024

        out = _call(
            "add_canon_from_path", path=str(src),
            provenance_tag="published novel",
        )
        assert "error" not in out
        assert out["filename"] == "big-lore.md"
        assert out["bytes_written"] == size
        assert out["synthesis_signal_emitted"] is True
        assert out["routed_to"] == "sources"
        assert out["provenance"] == "published novel"

        signals = _signals(universe)
        assert len(signals) == 1
        assert signals[0]["source_file"] == "big-lore.md"

        # File landed on disk verbatim.
        udir = us._base_path() / universe
        dest = udir / "canon" / "sources" / "big-lore.md"
        assert dest.exists()
        assert dest.stat().st_size == size

    def test_filename_override(
        self, universe: str, tmp_path: Path,
    ) -> None:
        src = tmp_path / "ugly-original-name.txt"
        src.write_text("clean contents", encoding="utf-8")
        out = _call(
            "add_canon_from_path", path=str(src), filename="clean.md",
        )
        assert out["filename"] == "clean.md"
        udir = us._base_path() / universe
        assert (udir / "canon" / "sources" / "clean.md").exists()

    def test_default_provenance_is_user_upload(
        self, universe: str, tmp_path: Path,
    ) -> None:
        src = tmp_path / "notes.md"
        src.write_text("some notes", encoding="utf-8")
        out = _call("add_canon_from_path", path=str(src))
        assert out["provenance"] == "user_upload"

    def test_meta_file_written(
        self, universe: str, tmp_path: Path,
    ) -> None:
        """Sidecar .meta.json records source_path for traceability."""
        src = tmp_path / "lore.md"
        src.write_text("lore", encoding="utf-8")
        _call("add_canon_from_path", path=str(src), provenance_tag="novel")

        udir = us._base_path() / universe
        meta_path = udir / "canon" / ".lore.md.meta.json"
        assert meta_path.exists()
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        assert meta["provenance"] == "novel"
        assert meta["source_path"] == str(src)

    def test_ledger_entry_appended(
        self, universe: str, tmp_path: Path,
    ) -> None:
        src = tmp_path / "ingest.md"
        src.write_text("content", encoding="utf-8")
        _call("add_canon_from_path", path=str(src), provenance_tag="draft")

        ledger_path = us._base_path() / universe / "ledger.json"
        entries = json.loads(ledger_path.read_text(encoding="utf-8"))
        assert len(entries) == 1
        assert entries[0]["action"] == "add_canon_from_path"
        assert entries[0]["target"] == "canon/sources/ingest.md"
        assert entries[0]["payload"]["provenance"] == "draft"
        assert entries[0]["payload"]["source_path"] == str(src)
        assert entries[0]["payload"]["synthesis_signal"] is True


# ─── add_canon_from_path rejects bad input ─────────────────────────────


class TestAddCanonFromPathRejections:
    def test_missing_path_rejected(self, universe: str) -> None:
        out = _call("add_canon_from_path", path="")
        assert "error" in out
        assert "path is required" in out["error"].lower()

    def test_relative_path_rejected(
        self, universe: str, tmp_path: Path,
    ) -> None:
        out = _call("add_canon_from_path", path="notes.md")
        assert "error" in out
        assert "absolute" in out["error"].lower()

    def test_nonexistent_path_rejected(
        self, universe: str, tmp_path: Path,
    ) -> None:
        ghost = tmp_path / "does-not-exist.md"
        out = _call("add_canon_from_path", path=str(ghost))
        assert "error" in out
        assert "not found" in out["error"].lower()

    def test_directory_path_rejected(
        self, universe: str, tmp_path: Path,
    ) -> None:
        """A directory is not a regular file."""
        out = _call("add_canon_from_path", path=str(tmp_path))
        assert "error" in out
        assert "regular file" in out["error"].lower()

    def test_non_utf8_file_rejected(
        self, universe: str, tmp_path: Path,
    ) -> None:
        """Latin-1 / binary content is rejected with a clear error —
        silent corruption of the canon pipeline would be much worse."""
        src = tmp_path / "latin1.md"
        # Valid latin-1 bytes that break UTF-8 decode (e.g. 0xFF).
        src.write_bytes(b"\xff\xfe\xfd not utf-8")
        out = _call("add_canon_from_path", path=str(src))
        assert "error" in out
        assert "utf-8" in out["error"].lower()
        # And the failed upload left no side effects.
        udir = us._base_path() / universe
        assert not (udir / "canon" / "sources" / "latin1.md").exists()
        assert _signals(universe) == []

    def test_rejection_leaves_no_ledger_entry(
        self, universe: str, tmp_path: Path,
    ) -> None:
        _call("add_canon_from_path", path=str(tmp_path / "missing"))
        ledger_path = us._base_path() / universe / "ledger.json"
        assert not ledger_path.exists()
