"""Tests that universe action responses include `universe_id` for isolation.

Context: Task #15. Claude.ai cross-universe hallucination was enabled by
tool responses that didn't name the universe they came from. When the bot
reads premise, canon, world-state, activity, etc., the response shape now
leads with `universe_id` so downstream reasoning can ground each fact to
its source universe.

Pairs with #47 (on-disk quarantine), #48 (retrieval audit), #51/#49/#53
(live-code hardening). This is the chat-side half of the cross-universe
cluster.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import workflow.universe_server as us


@pytest.fixture
def universe_base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    base = tmp_path / "output"
    base.mkdir()
    monkeypatch.setenv("UNIVERSE_SERVER_BASE", str(base))
    return base


def _make_universe(base: Path, uid: str) -> Path:
    udir = base / uid
    udir.mkdir(parents=True)
    return udir


class TestUniverseIdInResponses:
    """Every read response that pulls universe-scoped content must name it."""

    def test_read_premise_includes_universe_id(self, universe_base):
        udir = _make_universe(universe_base, "alpha")
        (udir / "PROGRAM.md").write_text("An alpha premise.", encoding="utf-8")
        out = json.loads(us._action_read_premise(universe_id="alpha"))
        assert out["universe_id"] == "alpha"
        assert out["premise"] == "An alpha premise."

    def test_read_premise_missing_still_includes_universe_id(self, universe_base):
        _make_universe(universe_base, "alpha")
        out = json.loads(us._action_read_premise(universe_id="alpha"))
        assert out["universe_id"] == "alpha"
        assert out["premise"] is None

    def test_read_output_includes_universe_id(self, universe_base):
        udir = _make_universe(universe_base, "alpha")
        (udir / "output").mkdir()
        (udir / "output" / "note.md").write_text("hello", encoding="utf-8")
        out = json.loads(us._action_read_output(universe_id="alpha", path="note.md"))
        assert out["universe_id"] == "alpha"
        assert out["content"] == "hello"

    def test_list_canon_includes_universe_id(self, universe_base):
        udir = _make_universe(universe_base, "alpha")
        (udir / "canon").mkdir()
        (udir / "canon" / "a.md").write_text("x", encoding="utf-8")
        out = json.loads(us._action_list_canon(universe_id="alpha"))
        assert out["universe_id"] == "alpha"

    def test_list_canon_no_canon_dir_still_includes_universe_id(self, universe_base):
        _make_universe(universe_base, "alpha")
        out = json.loads(us._action_list_canon(universe_id="alpha"))
        assert out["universe_id"] == "alpha"

    def test_read_canon_includes_universe_id(self, universe_base):
        udir = _make_universe(universe_base, "alpha")
        (udir / "canon").mkdir()
        (udir / "canon" / "a.md").write_text("hello", encoding="utf-8")
        out = json.loads(us._action_read_canon(universe_id="alpha", filename="a.md"))
        assert out["universe_id"] == "alpha"
        assert out["filename"] == "a.md"

    def test_query_world_no_data_includes_universe_id(self, universe_base):
        _make_universe(universe_base, "alpha")
        out = json.loads(us._action_query_world(universe_id="alpha", query_type="timeline"))
        # timeline has no store; should still echo the universe
        assert out["universe_id"] == "alpha"

    def test_get_activity_includes_universe_id(self, universe_base):
        udir = _make_universe(universe_base, "alpha")
        (udir / "activity.log").write_text("[..] line\n", encoding="utf-8")
        out = json.loads(us._action_get_activity(universe_id="alpha", limit=5))
        assert out["universe_id"] == "alpha"

    def test_get_activity_missing_log_includes_universe_id(self, universe_base):
        _make_universe(universe_base, "alpha")
        out = json.loads(us._action_get_activity(universe_id="alpha"))
        assert out["universe_id"] == "alpha"

    def test_list_branches_default_includes_universe_id(self, universe_base):
        _make_universe(universe_base, "alpha")
        out = json.loads(us._action_list_branches(universe_id="alpha"))
        assert out["universe_id"] == "alpha"

    def test_get_ledger_empty_includes_universe_id(self, universe_base):
        _make_universe(universe_base, "alpha")
        out = json.loads(us._action_get_ledger(universe_id="alpha"))
        assert out["universe_id"] == "alpha"

    def test_control_daemon_status_includes_universe_id(self, universe_base):
        _make_universe(universe_base, "alpha")
        out = json.loads(us._action_control_daemon(universe_id="alpha", text="status"))
        assert out["universe_id"] == "alpha"

    def test_different_universes_stay_distinct(self, universe_base):
        """Two universes must never cross-contaminate through the response."""
        udir_a = _make_universe(universe_base, "alpha")
        udir_b = _make_universe(universe_base, "beta")
        (udir_a / "PROGRAM.md").write_text("Alpha premise.", encoding="utf-8")
        (udir_b / "PROGRAM.md").write_text("Beta premise.", encoding="utf-8")

        out_a = json.loads(us._action_read_premise(universe_id="alpha"))
        out_b = json.loads(us._action_read_premise(universe_id="beta"))

        assert out_a["universe_id"] == "alpha"
        assert out_a["premise"] == "Alpha premise."
        assert out_b["universe_id"] == "beta"
        assert out_b["premise"] == "Beta premise."

    def test_inspect_includes_universe_id(self, universe_base):
        """Pre-existing behaviour — regression guard."""
        _make_universe(universe_base, "alpha")
        out = json.loads(us._action_inspect_universe(universe_id="alpha"))
        assert out["universe_id"] == "alpha"
