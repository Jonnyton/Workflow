"""Per-site canon-containment tests for the guarded call sites.

For every file Codex flagged (plus the additional sites found during the
end-to-end audit), prove that a symlinked ``.md`` whose target lives outside
the canon directory is NOT read/enumerated, while a legitimate sibling file
still is. Symlink-creation skips on platforms that forbid it (Windows without
Developer Mode); the containment primitive itself is exercised live in
``test_canon_io.py`` via ``.resolve()``-lands-outside checks.

Each site is verified through its real public/private function so a future
refactor that bypasses the chokepoint regresses a test.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def _canon_with_escape(tmp_path: Path) -> tuple[Path, Path]:
    """Build canon/ with one legit file and one symlink to an external secret.

    Returns ``(canon_dir, secret_path)``. Skips if symlinks are unavailable.
    """
    canon = tmp_path / "canon"
    canon.mkdir()
    (canon / "real_topic.md").write_text(
        "# Real Topic\n\nLegitimate canon content lives here.", encoding="utf-8"
    )
    secret = tmp_path / "SECRET.md"
    secret.write_text(
        "# SECRET\n\nThis external content must never be read into canon.",
        encoding="utf-8",
    )
    try:
        (canon / "real_topic_evil.md").symlink_to(secret)
    except (OSError, NotImplementedError) as exc:  # pragma: no cover - platform
        pytest.skip(f"symlink unsupported on this platform: {exc}")
    return canon, secret


def _assert_no_secret(text: str) -> None:
    assert "SECRET" not in text
    assert "must never be read" not in text


# =====================================================================
# orient.py -- _read_canon_context
# =====================================================================


def test_orient_read_canon_context_skips_symlink(tmp_path):
    from domains.fantasy_daemon.phases.orient import _read_canon_context

    canon, _ = _canon_with_escape(tmp_path)
    state = {"_universe_path": str(tmp_path)}
    out = _read_canon_context(state)
    assert "Real Topic" in out
    _assert_no_secret(out)


# =====================================================================
# writer_tools.py -- _render_canon_files
# =====================================================================


def test_writer_tools_render_canon_skips_symlink(tmp_path):
    from domains.fantasy_daemon.phases.writer_tools import _render_canon_files

    canon, _ = _canon_with_escape(tmp_path)
    state = {"_universe_path": str(tmp_path)}
    out = _render_canon_files(state)
    assert "Real Topic" in out
    _assert_no_secret(out)


# =====================================================================
# plan.py -- _try_constraint_synthesis (canon docs as source)
# =====================================================================


def test_plan_constraint_synthesis_skips_symlink(tmp_path, monkeypatch):
    from domains.fantasy_daemon.phases import plan as plan_mod

    canon, _ = _canon_with_escape(tmp_path)
    captured: dict[str, object] = {}

    class _FakeSurface:
        readiness_score = 0.0

    class _FakeSynth:
        def process(self, premise, source_docs):
            captured["source_docs"] = source_docs or []
            return _FakeSurface()

    monkeypatch.setattr(
        "workflow.constraints.constraint_synthesis.ConstraintSynthesis",
        _FakeSynth,
    )
    state = {
        "_universe_path": str(tmp_path),
        "workflow_instructions": {"premise": "Epic fantasy."},
    }
    plan_mod._try_constraint_synthesis(state)
    docs = captured.get("source_docs", [])
    joined = "\n".join(docs)
    assert "Real Topic" in joined
    _assert_no_secret(joined)


# =====================================================================
# commit.py -- _read_canon_excerpts
# =====================================================================


def test_commit_read_canon_excerpts_skips_symlink(tmp_path):
    from domains.fantasy_daemon.phases.commit import _read_canon_excerpts

    canon, _ = _canon_with_escape(tmp_path)
    out = _read_canon_excerpts(canon)
    assert "Real Topic" in out
    _assert_no_secret(out)


# =====================================================================
# reflect.py -- _collect_reviewable_canon (enumeration)
#            -- rewrite path rejects LLM ../ filename
# =====================================================================


def test_reflect_collect_reviewable_skips_symlink(tmp_path):
    from domains.fantasy_daemon.phases.reflect import _collect_reviewable_canon

    canon, _ = _canon_with_escape(tmp_path)
    result = _collect_reviewable_canon(canon, signal_topics=None)
    assert "real_topic.md" in result
    assert "real_topic_evil.md" not in result
    for content in result.values():
        _assert_no_secret(content)


def test_reflect_rewrite_rejects_llm_traversal_filename(tmp_path, monkeypatch):
    """An LLM-emitted ``../`` rewrite target must not clobber an external file."""
    import importlib

    # The package re-exports the ``reflect`` *function*, so import the module
    # by its full dotted path to monkeypatch its internals.
    reflect_mod = importlib.import_module(
        "domains.fantasy_daemon.phases.reflect"
    )

    canon = tmp_path / "canon"
    canon.mkdir()
    (canon / "good.md").write_text("# Good\n\nbody", encoding="utf-8")
    victim = tmp_path / "victim.md"
    victim.write_text("ORIGINAL", encoding="utf-8")

    monkeypatch.setattr(reflect_mod, "_read_premise", lambda *a, **k: "Premise.")
    monkeypatch.setattr(reflect_mod, "_extract_signal_topics", lambda *a, **k: None)
    # Force an LLM "issue" pointing at a traversal path and a non-empty rewrite.
    monkeypatch.setattr(
        reflect_mod,
        "_evaluate_canon",
        lambda *a, **k: [
            {"filename": "../victim.md", "reason": "x", "severity": 10}
        ],
    )
    monkeypatch.setattr(
        reflect_mod, "_rewrite_canon_file", lambda *a, **k: "CLOBBERED"
    )
    monkeypatch.setattr(reflect_mod, "_model_tier", lambda *a, **k: 99)
    monkeypatch.setattr(reflect_mod, "_rewrite_justified", lambda *a, **k: True)

    state = {"_universe_path": str(tmp_path)}
    summary = reflect_mod._review_canon_quality(state)
    # The traversal target was skipped, not written.
    assert "../victim.md" not in summary["files_rewritten"]
    assert victim.read_text(encoding="utf-8") == "ORIGINAL"


# =====================================================================
# worldbuild.py -- _scan_existing_canon + premise-context reader
# =====================================================================


def test_worldbuild_scan_existing_skips_symlink(tmp_path):
    from domains.fantasy_daemon.phases.worldbuild import _scan_existing_canon

    canon, _ = _canon_with_escape(tmp_path)
    slugs = _scan_existing_canon(canon)
    assert "real_topic" in slugs
    # The escaping symlink contributes no slug.
    assert "real_topic_evil" not in slugs


# =====================================================================
# raptor.py -- _read_canon_paragraphs
# =====================================================================


def test_raptor_read_canon_paragraphs_skips_symlink(tmp_path):
    from workflow.knowledge.raptor import _read_canon_paragraphs

    canon, _ = _canon_with_escape(tmp_path)
    paragraphs = _read_canon_paragraphs(str(canon))
    joined = "\n".join(paragraphs)
    assert "Legitimate canon content" in joined
    _assert_no_secret(joined)


# =====================================================================
# memory/ingestion.py -- ProgressiveIngestor._find_canon_files (recursive)
# =====================================================================


def test_memory_ingestion_find_files_skips_symlinked_subdir(tmp_path):
    from workflow.memory.ingestion import ProgressiveIngestor

    canon = tmp_path / "canon"
    canon.mkdir()
    (canon / "real.md").write_text("real canon", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "leak.md").write_text("LEAK", encoding="utf-8")
    try:
        (canon / "linkdir").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:  # pragma: no cover - platform
        pytest.skip(f"symlink unsupported on this platform: {exc}")

    ingestor = ProgressiveIngestor(canon, universe_id="u1")
    files = ingestor._find_canon_files()
    names = {p.name for p in files}
    assert "real.md" in names
    # The symlinked subdir's file must not be surfaced by the recursive walk.
    contents = {p.read_text(encoding="utf-8", errors="replace") for p in files}
    assert "LEAK" not in contents


# =====================================================================
# universe.py API -- read_canon / list_canon / read_source
# =====================================================================


def _setup_universe(tmp_path, monkeypatch):
    """Point the universe API base path at tmp_path and return a universe id."""
    monkeypatch.setenv("WORKFLOW_DATA_DIR", str(tmp_path))
    uid = "test_universe"
    udir = tmp_path / uid
    (udir / "canon").mkdir(parents=True)
    return uid, udir


def test_universe_read_canon_rejects_symlink(tmp_path, monkeypatch):
    from workflow.api import universe as uni

    uid, udir = _setup_universe(tmp_path, monkeypatch)
    monkeypatch.setattr(uni, "_default_universe", lambda: uid)
    monkeypatch.setattr(uni, "_universe_dir", lambda _id: udir)

    canon = udir / "canon"
    (canon / "good.md").write_text("good content", encoding="utf-8")
    secret = tmp_path / "secret.md"
    secret.write_text("SECRET CONTENT", encoding="utf-8")
    try:
        (canon / "evil.md").symlink_to(secret)
    except (OSError, NotImplementedError) as exc:  # pragma: no cover - platform
        pytest.skip(f"symlink unsupported on this platform: {exc}")

    # Legit read works.
    good = json.loads(uni._action_read_canon(universe_id=uid, filename="good.md"))
    assert good["content"] == "good content"
    # Symlinked canon file is rejected (not read).
    evil = json.loads(uni._action_read_canon(universe_id=uid, filename="evil.md"))
    assert "error" in evil
    assert "SECRET CONTENT" not in json.dumps(evil)


def test_universe_list_canon_skips_symlink(tmp_path, monkeypatch):
    from workflow.api import universe as uni

    uid, udir = _setup_universe(tmp_path, monkeypatch)
    monkeypatch.setattr(uni, "_default_universe", lambda: uid)
    monkeypatch.setattr(uni, "_universe_dir", lambda _id: udir)

    canon = udir / "canon"
    (canon / "good.md").write_text("good", encoding="utf-8")
    secret = tmp_path / "secret.md"
    secret.write_text("SECRET", encoding="utf-8")
    try:
        (canon / "evil.md").symlink_to(secret)
    except (OSError, NotImplementedError) as exc:  # pragma: no cover - platform
        pytest.skip(f"symlink unsupported on this platform: {exc}")

    listing = json.loads(uni._action_list_canon(universe_id=uid))
    names = {f["filename"] for f in listing["canon_files"]}
    assert "good.md" in names
    assert "evil.md" not in names


def test_universe_read_source_rejects_traversal(tmp_path, monkeypatch):
    """Traversal filename to read_source is rejected (runs live, no symlink)."""
    from workflow.api import universe as uni

    uid, udir = _setup_universe(tmp_path, monkeypatch)
    monkeypatch.setattr(uni, "_default_universe", lambda: uid)
    monkeypatch.setattr(uni, "_universe_dir", lambda _id: udir)

    (udir / "canon" / "sources").mkdir(parents=True)
    (tmp_path / "outside.txt").write_text("OUTSIDE", encoding="utf-8")
    # ``..`` is stripped by Path(...).name first, but assert no leak regardless.
    res = json.loads(uni._action_read_source(universe_id=uid, filename="../outside.txt"))
    assert "OUTSIDE" not in json.dumps(res)
