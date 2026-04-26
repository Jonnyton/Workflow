"""Phase B post-rollback goal-canonical re-point tests (Task #22).

Spec: docs/design-notes/2026-04-25-surgical-rollback-proposal.md §2.4 +
cross-DB refinement note in workflow/rollback.py module docstring.

Covers:
- Cascading walk-up: when both the canonical and its parent are in the
  closure, walk up to the next non-rolled-back ancestor.
- Missing-ancestor edge case: if no eligible ancestor exists, the goal's
  canonical is unset (re-pointed to None).
- Goals NOT pointing into the closure are untouched.
- The repoint dict logs every affected goal.
"""

from __future__ import annotations

from workflow.branch_versions import publish_branch_version
from workflow.daemon_server import (
    get_goal,
    initialize_author_server,
    save_goal,
    set_canonical_branch,
)
from workflow.rollback import (
    execute_rollback_set,
    repoint_goals_after_rollback,
    rollback_merge_orchestrator,
)


def _seed_branch_dict(branch_def_id, parent_version_id=None):
    return {
        "branch_def_id": branch_def_id,
        "entry_point": "n1",
        "graph_nodes": [{"id": "n1", "node_def_id": "n1"}],
        "edges": [{"from_node": "n1", "to_node": "END"}],
        "node_defs": [
            {"node_id": "n1", "display_name": "N1", "prompt_template": "echo"},
        ],
        "state_schema": [],
        "conditional_edges": [],
    }


def _publish(tmp_path, branch_def_id, parent_version_id=None):
    v = publish_branch_version(
        tmp_path, _seed_branch_dict(branch_def_id),
        publisher="alice", parent_version_id=parent_version_id,
    )
    return v.branch_version_id


def _seed_goal(tmp_path, goal_id="g1", canonical_bvid=None):
    initialize_author_server(tmp_path)
    save_goal(tmp_path, goal={
        "goal_id": goal_id, "name": f"Goal {goal_id}", "author": "alice",
    })
    if canonical_bvid is not None:
        set_canonical_branch(
            tmp_path, goal_id=goal_id,
            branch_version_id=canonical_bvid, set_by="alice",
        )


# ─── single-version repoint ──────────────────────────────────────────────


class TestSingleVersionRepoint:
    def test_repoint_to_immediate_active_parent(self, tmp_path):
        # parent (active) ← child (rolled back); goal canonical was
        # pointing at child → should re-point to parent.
        parent = _publish(tmp_path, "rp-parent")
        child = _publish(tmp_path, "rp-child", parent_version_id=parent)
        _seed_goal(tmp_path, "g1", canonical_bvid=child)
        # Roll back the child only (parent stays active).
        execute_rollback_set(
            tmp_path, [child], reason="t", set_by="alice",
        )
        result = repoint_goals_after_rollback(
            tmp_path, [child], set_by="alice",
        )
        assert result["repointed_count"] == 1
        repoint = result["repoints"][0]
        assert repoint["goal_id"] == "g1"
        assert repoint["old_branch_version_id"] == child
        assert repoint["new_branch_version_id"] == parent
        # Confirm the goal canonical actually moved.
        goal = get_goal(tmp_path, goal_id="g1")
        assert goal["canonical_branch_version_id"] == parent

    def test_unaffected_goal_not_touched(self, tmp_path):
        # Goal canonical points at a DIFFERENT version, not in closure.
        unrelated = _publish(tmp_path, "rp-unrelated")
        target = _publish(tmp_path, "rp-target")
        _seed_goal(tmp_path, "g1", canonical_bvid=unrelated)
        execute_rollback_set(
            tmp_path, [target], reason="t", set_by="alice",
        )
        result = repoint_goals_after_rollback(
            tmp_path, [target], set_by="alice",
        )
        assert result["repointed_count"] == 0
        goal = get_goal(tmp_path, goal_id="g1")
        assert goal["canonical_branch_version_id"] == unrelated


# ─── cascading walk-up ───────────────────────────────────────────────────


class TestCascadingWalkUp:
    def test_walk_skips_rolled_back_ancestors(self, tmp_path):
        # active → rolled-1 → rolled-2 (canonical here).
        # Goal canonical at rolled-2 should re-point to `active`,
        # skipping rolled-1.
        active = _publish(tmp_path, "wu-active")
        rolled_1 = _publish(tmp_path, "wu-r1", parent_version_id=active)
        rolled_2 = _publish(tmp_path, "wu-r2", parent_version_id=rolled_1)
        _seed_goal(tmp_path, "g1", canonical_bvid=rolled_2)
        # Roll back BOTH rolled_1 and rolled_2.
        execute_rollback_set(
            tmp_path, [rolled_1, rolled_2], reason="t", set_by="alice",
        )
        result = repoint_goals_after_rollback(
            tmp_path, [rolled_1, rolled_2], set_by="alice",
        )
        assert result["repointed_count"] == 1
        assert result["repoints"][0]["new_branch_version_id"] == active
        goal = get_goal(tmp_path, goal_id="g1")
        assert goal["canonical_branch_version_id"] == active


# ─── missing-ancestor edge case ──────────────────────────────────────────


class TestMissingAncestor:
    def test_no_eligible_ancestor_unsets_canonical(self, tmp_path):
        # Single rolled-back version with no parent → walk-up returns
        # None → goal canonical is unset.
        only = _publish(tmp_path, "ma-only")  # no parent_version_id
        _seed_goal(tmp_path, "g1", canonical_bvid=only)
        execute_rollback_set(
            tmp_path, [only], reason="t", set_by="alice",
        )
        result = repoint_goals_after_rollback(
            tmp_path, [only], set_by="alice",
        )
        assert result["repointed_count"] == 1
        assert result["repoints"][0]["new_branch_version_id"] is None
        goal = get_goal(tmp_path, goal_id="g1")
        assert goal["canonical_branch_version_id"] is None

    def test_all_ancestors_rolled_back_unsets_canonical(self, tmp_path):
        # Every version in the chain is rolled back → no eligible ancestor.
        v1 = _publish(tmp_path, "ar-1")
        v2 = _publish(tmp_path, "ar-2", parent_version_id=v1)
        v3 = _publish(tmp_path, "ar-3", parent_version_id=v2)
        _seed_goal(tmp_path, "g1", canonical_bvid=v3)
        execute_rollback_set(
            tmp_path, [v1, v2, v3], reason="t", set_by="alice",
        )
        result = repoint_goals_after_rollback(
            tmp_path, [v1, v2, v3], set_by="alice",
        )
        assert result["repointed_count"] == 1
        assert result["repoints"][0]["new_branch_version_id"] is None


# ─── orchestrator integration ────────────────────────────────────────────


class TestOrchestratorIntegrationWithGoals:
    def test_orchestrator_repoints_goal_end_to_end(self, tmp_path):
        # Full path: orchestrator computes closure, executes, re-points.
        parent = _publish(tmp_path, "int-parent")
        child = _publish(tmp_path, "int-child", parent_version_id=parent)
        _seed_goal(tmp_path, "g1", canonical_bvid=child)
        # Roll back the parent — closure includes both parent + child;
        # goal canonical was at child → must re-point past both to None.
        result = rollback_merge_orchestrator(
            tmp_path, parent, reason="cascade", set_by="alice",
        )
        assert result["status"] == "ok"
        assert set(result["closure"]) == {parent, child}
        assert result["repoint"]["repointed_count"] == 1
        # Both versions in closure → walk-up has nowhere to go → None.
        assert result["repoint"]["repoints"][0]["new_branch_version_id"] is None
        goal = get_goal(tmp_path, goal_id="g1")
        assert goal["canonical_branch_version_id"] is None

    def test_multiple_goals_repointed_independently(self, tmp_path):
        # Goal A points at child; Goal B points at parent. Roll back
        # parent → A gets re-pointed to None, B gets re-pointed to None.
        parent = _publish(tmp_path, "mg-parent")
        child = _publish(tmp_path, "mg-child", parent_version_id=parent)
        _seed_goal(tmp_path, "ga", canonical_bvid=child)
        _seed_goal(tmp_path, "gb", canonical_bvid=parent)
        result = rollback_merge_orchestrator(
            tmp_path, parent, reason="t", set_by="alice",
        )
        assert result["status"] == "ok"
        assert result["repoint"]["repointed_count"] == 2
        assert get_goal(tmp_path, goal_id="ga")["canonical_branch_version_id"] is None
        assert get_goal(tmp_path, goal_id="gb")["canonical_branch_version_id"] is None
