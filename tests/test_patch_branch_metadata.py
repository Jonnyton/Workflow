"""#67: patch_branch set_name / set_description / set_tags / set_published.

Pre-#67: any branch-level label change forced delete-and-rebuild,
destroying the branch_def_id (and therefore run history, judgments,
and lineage). Post-#67: patch_branch accepts atomic metadata ops that
preserve identity.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def ext_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    base = tmp_path / "output"
    base.mkdir()
    monkeypatch.setenv("UNIVERSE_SERVER_BASE", str(base))
    monkeypatch.setenv("UNIVERSE_SERVER_USER", "tester")
    from workflow import universe_server as us

    importlib.reload(us)
    yield us, base
    importlib.reload(us)


def _call(us, tool: str, action: str, **kwargs):
    fn = getattr(us, tool)
    return json.loads(fn(action=action, **kwargs))


def _build(us, *, name: str = "b", tags: list | None = None,
           description: str = "") -> str:
    spec = {
        "name": name,
        "description": description,
        "tags": tags or [],
        "entry_point": "capture",
        "node_defs": [{
            "node_id": "capture",
            "display_name": "Capture",
            "prompt_template": "cap: {x}",
        }],
        "edges": [
            {"from": "START", "to": "capture"},
            {"from": "capture", "to": "END"},
        ],
        "state_schema": [{"name": "x", "type": "str"}],
    }
    res = _call(us, "extensions", "build_branch", spec_json=json.dumps(spec))
    assert res["status"] == "built", res
    return res["branch_def_id"]


def _patch(us, bid: str, ops: list) -> dict:
    return _call(us, "extensions", "patch_branch",
                 branch_def_id=bid, changes_json=json.dumps(ops))


def _load(us, base: Path, bid: str) -> dict:
    from workflow.author_server import get_branch_definition

    return get_branch_definition(base, branch_def_id=bid)


# ─────────────────────────────────────────────────────────────────────────────
# set_name / set_description / set_tags / set_published
# ─────────────────────────────────────────────────────────────────────────────


class TestPatchBranchMetadataOps:

    def test_set_name_round_trips(self, ext_env):
        us, base = ext_env
        bid = _build(us, name="original")
        res = _patch(us, bid, [{"op": "set_name", "name": "renamed"}])
        assert res.get("status") != "rejected", res
        assert _load(us, base, bid)["name"] == "renamed"

    def test_set_name_rejects_empty(self, ext_env):
        us, _ = ext_env
        bid = _build(us, name="original")
        res = _patch(us, bid, [{"op": "set_name", "name": ""}])
        assert res.get("status") == "rejected"

    def test_set_description_round_trips(self, ext_env):
        us, base = ext_env
        bid = _build(us, description="first draft")
        res = _patch(us, bid, [{
            "op": "set_description",
            "description": "polished v2 writeup",
        }])
        assert res.get("status") != "rejected", res
        assert _load(us, base, bid)["description"] == "polished v2 writeup"

    def test_set_description_can_clear_to_empty(self, ext_env):
        """Explicit empty string must be allowed — clearing a
        description is a legitimate operation.
        """
        us, base = ext_env
        bid = _build(us, description="old")
        res = _patch(us, bid, [{"op": "set_description", "description": ""}])
        assert res.get("status") != "rejected", res
        assert _load(us, base, bid)["description"] == ""

    def test_set_description_missing_field_rejects(self, ext_env):
        us, _ = ext_env
        bid = _build(us)
        res = _patch(us, bid, [{"op": "set_description"}])
        assert res.get("status") == "rejected"

    def test_set_tags_replaces_list(self, ext_env):
        us, base = ext_env
        bid = _build(us, tags=["old", "stale"])
        res = _patch(us, bid, [{
            "op": "set_tags", "tags": ["alpha", "beta", "gamma"],
        }])
        assert res.get("status") != "rejected", res
        assert _load(us, base, bid)["tags"] == ["alpha", "beta", "gamma"]

    def test_set_tags_accepts_csv_string(self, ext_env):
        us, base = ext_env
        bid = _build(us)
        res = _patch(us, bid, [{
            "op": "set_tags", "tags": "alpha, beta, gamma",
        }])
        assert res.get("status") != "rejected", res
        assert _load(us, base, bid)["tags"] == ["alpha", "beta", "gamma"]

    def test_set_tags_can_clear_to_empty(self, ext_env):
        us, base = ext_env
        bid = _build(us, tags=["old"])
        res = _patch(us, bid, [{"op": "set_tags", "tags": []}])
        assert res.get("status") != "rejected", res
        assert _load(us, base, bid)["tags"] == []

    def test_set_tags_rejects_non_list(self, ext_env):
        us, _ = ext_env
        bid = _build(us)
        res = _patch(us, bid, [{"op": "set_tags", "tags": {"a": 1}}])
        assert res.get("status") == "rejected"

    def test_set_published_round_trips_true(self, ext_env):
        us, base = ext_env
        bid = _build(us)
        assert _load(us, base, bid)["published"] is False
        res = _patch(us, bid, [{"op": "set_published", "published": True}])
        assert res.get("status") != "rejected", res
        assert _load(us, base, bid)["published"] is True

    def test_set_published_round_trips_false(self, ext_env):
        us, base = ext_env
        bid = _build(us)
        _patch(us, bid, [{"op": "set_published", "published": True}])
        res = _patch(us, bid, [{"op": "set_published", "published": False}])
        assert res.get("status") != "rejected", res
        assert _load(us, base, bid)["published"] is False

    def test_set_published_rejects_non_bool(self, ext_env):
        us, _ = ext_env
        bid = _build(us)
        res = _patch(us, bid, [{"op": "set_published", "published": "true"}])
        assert res.get("status") == "rejected"


# ─────────────────────────────────────────────────────────────────────────────
# Identity preservation + combined batches
# ─────────────────────────────────────────────────────────────────────────────


class TestPatchBranchMetadataCombined:

    def test_branch_def_id_preserved_after_metadata_patch(self, ext_env):
        """The entire point of #67: label changes must NOT require a
        new branch_def_id. That preserves run history + judgments.
        """
        us, base = ext_env
        bid_before = _build(us, name="old-name", tags=["old"])
        _patch(us, bid_before, [
            {"op": "set_name", "name": "new-name"},
            {"op": "set_tags", "tags": ["new", "fresh"]},
        ])
        loaded = _load(us, base, bid_before)
        assert loaded["branch_def_id"] == bid_before
        assert loaded["name"] == "new-name"
        assert loaded["tags"] == ["new", "fresh"]

    def test_metadata_and_topology_ops_in_one_batch(self, ext_env):
        """set_tags + add_node + add_edge batch together atomically."""
        us, base = ext_env
        bid = _build(us, tags=["draft"])
        res = _patch(us, bid, [
            {"op": "set_tags", "tags": ["published", "v2"]},
            {
                "op": "add_node",
                "node_id": "archive",
                "display_name": "Archive",
                "prompt_template": "arch: {x}",
            },
            {"op": "add_edge", "from": "capture", "to": "archive"},
            {"op": "remove_edge", "from": "capture", "to": "END"},
            {"op": "add_edge", "from": "archive", "to": "END"},
        ])
        assert res.get("status") != "rejected", res
        loaded = _load(us, base, bid)
        assert loaded["tags"] == ["published", "v2"]
        nids = {n["node_id"] for n in loaded["node_defs"]}
        assert "archive" in nids

    def test_patch_rollback_on_failure_preserves_metadata(self, ext_env):
        """If a later op in the batch fails, prior metadata changes
        must not stick (patch_branch is transactional).
        """
        us, base = ext_env
        bid = _build(us, name="original", tags=["x"])
        res = _patch(us, bid, [
            {"op": "set_name", "name": "would-change"},
            # This op references a non-existent node — should abort.
            {"op": "remove_node", "node_id": "ghost"},
        ])
        assert res.get("status") == "rejected"
        loaded = _load(us, base, bid)
        # Original name must be intact.
        assert loaded["name"] == "original"
        assert loaded["tags"] == ["x"]
