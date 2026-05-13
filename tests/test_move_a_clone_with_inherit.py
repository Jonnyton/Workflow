"""Move A regression: build_branch with fork_from clones parent topology.

Before this fix, ``fork_from`` was lineage metadata only — the caller
still had to author the full spec from scratch, and the validator would
reject any non-trivial multi-node graph. Slice-0 substrate-readiness
finding 2026-05-13 named this the single highest-leverage substrate-
finishing move ("Move A").

Fix: when ``fork_from`` points at a published ``branch_version_id``,
``_staged_branch_from_spec`` seeds the staging branch from the parent
version's snapshot (node_defs, edges, conditional_edges, state_schema,
entry_point). The caller's spec then applies overrides on top via
``node_overrides`` (dict[node_id, partial_node_def]) or new top-level
``node_defs`` / ``edges`` / ``state_schema`` entries.

Slice-1 acceptance criteria (per the slice-1 spec):
1. A published version can be cloned via ``build_branch fork_from=<vid>``.
2. The clone inherits the parent's graph, nodes, state schema, lineage.
3. A user can amend exactly one node via ``node_overrides``.
4. The parent branch is unchanged.
5. The clone validates past the inherited graph shape without
   re-triggering PR-037's multi-node build wall.
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
    monkeypatch.setenv("WORKFLOW_DATA_DIR", str(base))
    monkeypatch.setenv("UNIVERSE_SERVER_USER", "tester")
    from workflow import universe_server as us

    importlib.reload(us)
    yield us, base
    importlib.reload(us)


def _call(us, action, **kwargs):
    return json.loads(us.extensions(action=action, **kwargs))


def _build_parent(us, *, name: str = "parent") -> tuple[str, str]:
    """Build + publish a 2-node parent branch. Returns (branch_def_id, version_id)."""
    spec = {
        "name": name,
        "tags": ["parent-tag"],
        "entry_point": "classify",
        "node_defs": [
            {
                "node_id": "classify",
                "display_name": "Classify",
                "prompt_template": "classify {x}",
                "input_keys": ["x"],
                "output_keys": ["y"],
            },
            {
                "node_id": "end_marker",
                "display_name": "End",
                "prompt_template": "done",
                "input_keys": ["y"],
                "output_keys": [],
            },
        ],
        "edges": [
            {"from": "START", "to": "classify"},
            {"from": "classify", "to": "end_marker"},
            {"from": "end_marker", "to": "END"},
        ],
        "state_schema": [{"name": "x", "type": "str"}, {"name": "y", "type": "str"}],
    }
    built = _call(us, "build_branch", spec_json=json.dumps(spec))
    assert built.get("status") == "built", built
    bid = built["branch_def_id"]

    published = _call(us, "publish_version", branch_def_id=bid)
    vid = published.get("branch_version_id")
    assert vid, f"publish_version did not return branch_version_id: {published}"
    return bid, vid


class TestMoveAcceptance:
    """Tests #1-#5 from the slice-1 acceptance criteria."""

    def test_published_version_can_be_cloned(self, ext_env):
        """(1) Empty fork inherits parent topology byte-identically."""
        us, _base = ext_env
        parent_bid, parent_vid = _build_parent(us)

        fork = _call(
            us, "build_branch",
            spec_json=json.dumps({
                "name": "empty-fork",
                "fork_from": parent_vid,
            }),
        )
        assert fork.get("status") == "built", fork
        # Inherited the 3 edges (incl. START + END markers) and 2 nodes.
        assert fork.get("node_count") == 2
        assert fork.get("edge_count") == 3
        assert fork.get("entry_point") == "classify"

    def test_clone_inherits_node_defs_state_lineage(self, ext_env):
        """(2) Clone has the parent's node_defs, state_schema, and fork_from lineage."""
        us, _base = ext_env
        parent_bid, parent_vid = _build_parent(us)

        fork = _call(
            us, "build_branch",
            spec_json=json.dumps({
                "name": "lineage-fork",
                "fork_from": parent_vid,
            }),
        )
        assert fork.get("status") == "built", fork
        fork_bid = fork["branch_def_id"]

        described = _call(us, "get_branch", branch_def_id=fork_bid)
        # Lineage preserved
        assert described.get("fork_from") == parent_vid
        # Inherited node_def_ids match parent's
        node_ids = sorted(n["node_id"] for n in described["node_defs"])
        assert node_ids == ["classify", "end_marker"]
        # state_schema inherited
        field_names = sorted(f["name"] for f in described["state_schema"])
        assert field_names == ["x", "y"]
        # Inherited prompt templates are present
        classify = next(n for n in described["node_defs"] if n["node_id"] == "classify")
        assert classify["prompt_template"] == "classify {x}"

    def test_node_overrides_amend_one_node(self, ext_env):
        """(3) node_overrides applies field-level merges to inherited nodes."""
        us, _base = ext_env
        parent_bid, parent_vid = _build_parent(us)

        fork = _call(
            us, "build_branch",
            spec_json=json.dumps({
                "name": "overrides-fork",
                "fork_from": parent_vid,
                "node_overrides": {
                    "classify": {
                        "prompt_template": "AMENDED: classify {x} differently",
                    },
                },
            }),
        )
        assert fork.get("status") == "built", fork

        described = _call(us, "get_branch", branch_def_id=fork["branch_def_id"])
        classify = next(n for n in described["node_defs"] if n["node_id"] == "classify")
        end_marker = next(n for n in described["node_defs"] if n["node_id"] == "end_marker")
        assert classify["prompt_template"] == "AMENDED: classify {x} differently"
        # Sibling node inherited verbatim
        assert end_marker["prompt_template"] == "done"

    def test_parent_branch_unchanged_after_fork(self, ext_env):
        """(4) The parent branch is byte-identical before/after the fork."""
        us, _base = ext_env
        parent_bid, parent_vid = _build_parent(us)

        before = _call(us, "get_branch", branch_def_id=parent_bid)

        _ = _call(
            us, "build_branch",
            spec_json=json.dumps({
                "name": "unchanged-test-fork",
                "fork_from": parent_vid,
                "node_overrides": {
                    "classify": {"prompt_template": "amended"},
                },
            }),
        )

        after = _call(us, "get_branch", branch_def_id=parent_bid)
        # Topology unchanged
        for field in ("name", "entry_point", "graph", "node_defs", "state_schema"):
            assert before.get(field) == after.get(field), (
                f"parent {field!r} was mutated by the fork"
            )

    def test_clone_validates_past_pr037_wall(self, ext_env):
        """(5) The clone path bypasses PR-037's multi-node spec re-validation.

        Pre-fix, a user submitting a multi-node spec (with edges) via
        build_branch hit PR-037's validator wall. With Move A, the
        clone inherits the parent's already-validated topology and
        only the overrides are validated, so multi-node forks succeed.
        """
        us, _base = ext_env
        parent_bid, parent_vid = _build_parent(us)

        # Submit a fork spec that, pre-Move-A, would have required
        # passing the validator with the full multi-node graph.
        fork = _call(
            us, "build_branch",
            spec_json=json.dumps({
                "name": "pr-037-bypass-fork",
                "fork_from": parent_vid,
                "node_overrides": {"classify": {"prompt_template": "v2"}},
            }),
        )
        # Move A goal: this succeeds without the caller having to
        # author the full graph from scratch.
        assert fork.get("status") == "built", fork
        assert fork.get("node_count") == 2


class TestMoveAEdgeCases:

    def test_unknown_fork_from_version_id_still_rejected(self, ext_env):
        """An invalid version_id surfaces the existing rejection — no
        silent fallback to empty staging.
        """
        us, _base = ext_env
        res = _call(
            us, "build_branch",
            spec_json=json.dumps({
                "name": "bad-fork",
                "fork_from": "nonexistent@deadbeef",
                "node_overrides": {"x": {"prompt_template": "y"}},
            }),
        )
        assert res.get("status") == "rejected"
        # The fork_from validator's specific error must fire.
        assert any(
            "fork_from" in err and "not a known" in err
            for err in res.get("errors", [])
        ), res

    def test_node_overrides_for_nonexistent_node_is_error(self, ext_env):
        """Overriding a node not in the parent is a spec error, not a silent no-op."""
        us, _base = ext_env
        _, parent_vid = _build_parent(us)
        res = _call(
            us, "build_branch",
            spec_json=json.dumps({
                "name": "bad-override",
                "fork_from": parent_vid,
                "node_overrides": {
                    "nonexistent_node": {"prompt_template": "x"},
                },
            }),
        )
        assert res.get("status") == "rejected"
        assert any(
            "nonexistent_node" in err and "no inherited node" in err
            for err in res.get("errors", [])
        ), res

    def test_node_overrides_must_be_dict(self, ext_env):
        """A malformed node_overrides shape is a spec error with a clear message."""
        us, _base = ext_env
        _, parent_vid = _build_parent(us)
        res = _call(
            us, "build_branch",
            spec_json=json.dumps({
                "name": "bad-shape",
                "fork_from": parent_vid,
                "node_overrides": ["this", "should", "be", "a", "dict"],
            }),
        )
        assert res.get("status") == "rejected"
        assert any(
            "node_overrides" in err and "JSON object" in err
            for err in res.get("errors", [])
        ), res

    def test_top_level_node_defs_additive_no_collision_with_parent(self, ext_env):
        """New node_defs that don't collide with parent are additive.

        The new node must connect to the inherited graph via edges or
        the validator's reachability check will reject it. This test
        demonstrates the user re-wires the graph: classify -> new node
        -> end_marker -> END.
        """
        us, _base = ext_env
        _, parent_vid = _build_parent(us)
        res = _call(
            us, "build_branch",
            spec_json=json.dumps({
                "name": "additive-fork",
                "fork_from": parent_vid,
                "node_defs": [{
                    "node_id": "post_classify",
                    "display_name": "Post Classify",
                    "prompt_template": "post {y}",
                    "input_keys": ["y"],
                    "output_keys": [],
                }],
                "edges": [
                    {"from": "classify", "to": "post_classify"},
                    {"from": "post_classify", "to": "end_marker"},
                ],
            }),
        )
        assert res.get("status") == "built", res
        # 2 inherited + 1 new
        assert res.get("node_count") == 3

    def test_top_level_node_def_collision_rejected(self, ext_env):
        """A top-level node_def whose id collides with an inherited node is rejected;
        caller must use node_overrides to amend.
        """
        us, _base = ext_env
        _, parent_vid = _build_parent(us)
        res = _call(
            us, "build_branch",
            spec_json=json.dumps({
                "name": "collision-fork",
                "fork_from": parent_vid,
                "node_defs": [{
                    "node_id": "classify",  # already inherited from parent
                    "display_name": "Re-Classify",
                    "prompt_template": "different",
                }],
            }),
        )
        assert res.get("status") == "rejected"
        assert any(
            "classify" in err and "node_overrides" in err
            for err in res.get("errors", [])
        ), res
