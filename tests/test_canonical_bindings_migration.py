"""Tests for canonical_bindings table — Task #61 Step 0+1.

Step 0: schema DDL (table + 4 indexes).
Step 1: idempotent backfill from goals.canonical_branch_version_id.

See docs/design-notes/2026-04-25-variant-canonicals-proposal.md.
"""
from __future__ import annotations

import sqlite3

import pytest

from workflow.branch_versions import publish_branch_version
from workflow.daemon_server import (
    _connect,
    initialize_author_server,
    save_goal,
    set_canonical_branch,
)


def _seed_goal(base_path, goal_id: str = "g1", author: str = "alice") -> dict:
    initialize_author_server(base_path)
    return save_goal(
        base_path,
        goal={"goal_id": goal_id, "name": f"Test Goal {goal_id}", "author": author},
    )


def _seed_branch_version(base_path, branch_id: str = "b1") -> str:
    from workflow.branches import (
        BranchDefinition,
        EdgeDefinition,
        GraphNodeRef,
        NodeDefinition,
    )
    from workflow.daemon_server import save_branch_definition

    initialize_author_server(base_path)
    nd = NodeDefinition(node_id="n1", display_name="N1", prompt_template="do X")
    branch = BranchDefinition(
        branch_def_id=branch_id,
        name=f"Branch {branch_id}",
        graph_nodes=[GraphNodeRef(id="n1", node_def_id="n1")],
        edges=[EdgeDefinition(from_node="n1", to_node="END")],
        entry_point="n1",
        node_defs=[nd],
        state_schema=[],
    )
    save_branch_definition(base_path, branch_def=branch.to_dict())
    v = publish_branch_version(base_path, branch.to_dict(), publisher="alice")
    return v.branch_version_id


# ── Step 0: schema DDL ────────────────────────────────────────────────────────


class TestSchemaDDL:
    def test_fresh_db_creates_canonical_bindings_table(self, tmp_path):
        initialize_author_server(tmp_path)
        with _connect(tmp_path) as conn:
            tables = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        assert "canonical_bindings" in tables

    def test_table_has_expected_columns(self, tmp_path):
        initialize_author_server(tmp_path)
        with _connect(tmp_path) as conn:
            cols = {
                row["name"]: row
                for row in conn.execute("PRAGMA table_info(canonical_bindings)")
            }
        expected = {
            "goal_id",
            "scope_token",
            "branch_version_id",
            "bound_by_actor_id",
            "bound_at",
            "visibility",
        }
        assert expected <= set(cols)
        # PK is composite (goal_id, scope_token); both have pk>0
        assert cols["goal_id"]["pk"] >= 1
        assert cols["scope_token"]["pk"] >= 1
        # bound_at is REAL per design
        assert cols["bound_at"]["type"].upper() == "REAL"

    def test_indexes_exist(self, tmp_path):
        initialize_author_server(tmp_path)
        with _connect(tmp_path) as conn:
            idx_names = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index'"
                )
            }
        # 4 indexes per lead's brief (3 from design + scope_goal addition)
        assert "idx_canonical_bindings_goal" in idx_names
        assert "idx_canonical_bindings_actor" in idx_names
        assert "idx_canonical_bindings_branch_ver" in idx_names
        assert "idx_canonical_bindings_scope_goal" in idx_names


# ── Step 1: backfill from goals.canonical_branch_version_id ──────────────────


class TestBackfill:
    def test_existing_canonical_is_backfilled(self, tmp_path):
        # Seed a goal + branch version + set legacy canonical column.
        bvid = _seed_branch_version(tmp_path, "b1")
        _seed_goal(tmp_path, "g1", author="alice")
        set_canonical_branch(
            tmp_path, goal_id="g1", branch_version_id=bvid, set_by="alice"
        )

        # Re-run init (simulates daemon restart). Backfill should now have
        # populated canonical_bindings.
        initialize_author_server(tmp_path)

        with _connect(tmp_path) as conn:
            rows = list(
                conn.execute(
                    "SELECT goal_id, scope_token, branch_version_id, "
                    "bound_by_actor_id, visibility "
                    "FROM canonical_bindings WHERE goal_id = ?",
                    ("g1",),
                )
            )
        assert len(rows) == 1
        row = rows[0]
        assert row["goal_id"] == "g1"
        assert row["scope_token"] == ""
        assert row["branch_version_id"] == bvid
        assert row["bound_by_actor_id"] == "alice"
        assert row["visibility"] == "public"

    def test_goals_with_null_canonical_are_not_backfilled(self, tmp_path):
        _seed_goal(tmp_path, "g_no_canonical", author="bob")
        # No set_canonical_branch call — column stays NULL.

        initialize_author_server(tmp_path)

        with _connect(tmp_path) as conn:
            rows = list(
                conn.execute(
                    "SELECT * FROM canonical_bindings WHERE goal_id = ?",
                    ("g_no_canonical",),
                )
            )
        assert rows == []

    def test_backfill_is_idempotent(self, tmp_path):
        bvid = _seed_branch_version(tmp_path, "b1")
        _seed_goal(tmp_path, "g1", author="alice")
        set_canonical_branch(
            tmp_path, goal_id="g1", branch_version_id=bvid, set_by="alice"
        )

        # Run init three times — total row count for g1 must stay at 1.
        for _ in range(3):
            initialize_author_server(tmp_path)

        with _connect(tmp_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM canonical_bindings WHERE goal_id = ?",
                ("g1",),
            ).fetchone()["n"]
        assert count == 1

    def test_composite_primary_key_blocks_duplicate_scope(self, tmp_path):
        bvid = _seed_branch_version(tmp_path, "b1")
        bvid2 = _seed_branch_version(tmp_path, "b2")
        _seed_goal(tmp_path, "g1", author="alice")

        with _connect(tmp_path) as conn:
            conn.execute(
                "INSERT INTO canonical_bindings "
                "(goal_id, scope_token, branch_version_id, "
                " bound_by_actor_id, bound_at, visibility) "
                "VALUES (?, '', ?, 'alice', 0.0, 'public')",
                ("g1", bvid),
            )
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO canonical_bindings "
                    "(goal_id, scope_token, branch_version_id, "
                    " bound_by_actor_id, bound_at, visibility) "
                    "VALUES (?, '', ?, 'alice', 1.0, 'public')",
                    ("g1", bvid2),
                )

    def test_different_scope_tokens_coexist(self, tmp_path):
        """Composite PK = (goal_id, scope_token) — same goal, different scopes ok."""
        bvid = _seed_branch_version(tmp_path, "b1")
        bvid2 = _seed_branch_version(tmp_path, "b2")
        _seed_goal(tmp_path, "g1", author="alice")

        with _connect(tmp_path) as conn:
            conn.execute(
                "INSERT INTO canonical_bindings "
                "(goal_id, scope_token, branch_version_id, "
                " bound_by_actor_id, bound_at, visibility) "
                "VALUES (?, '', ?, 'alice', 0.0, 'public')",
                ("g1", bvid),
            )
            conn.execute(
                "INSERT INTO canonical_bindings "
                "(goal_id, scope_token, branch_version_id, "
                " bound_by_actor_id, bound_at, visibility) "
                "VALUES (?, 'user:mark', ?, 'mark', 1.0, 'public')",
                ("g1", bvid2),
            )
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM canonical_bindings WHERE goal_id = ?",
                ("g1",),
            ).fetchone()["n"]
        assert count == 2


# ── Step 2: dual-write via set_canonical_branch ───────────────────────────────


class TestDualWrite:
    """Step 2 — set_canonical_branch writes BOTH legacy goals column AND
    canonical_bindings (scope_token=''). Reads still go to legacy column."""

    def test_set_canonical_writes_both_stores(self, tmp_path):
        bvid = _seed_branch_version(tmp_path, "b1")
        _seed_goal(tmp_path, "g1", author="alice")

        set_canonical_branch(
            tmp_path, goal_id="g1", branch_version_id=bvid, set_by="alice"
        )

        # Legacy column populated.
        from workflow.daemon_server import get_goal
        goal = get_goal(tmp_path, goal_id="g1")
        assert goal["canonical_branch_version_id"] == bvid

        # New table also populated with scope_token=''.
        with _connect(tmp_path) as conn:
            row = conn.execute(
                "SELECT branch_version_id, bound_by_actor_id, visibility "
                "FROM canonical_bindings WHERE goal_id = ? AND scope_token = ''",
                ("g1",),
            ).fetchone()
        assert row is not None
        assert row["branch_version_id"] == bvid
        assert row["bound_by_actor_id"] == "alice"
        assert row["visibility"] == "public"

    def test_set_canonical_overwrite_updates_both(self, tmp_path):
        """Setting a new canonical replaces both legacy and new-table values."""
        bvid1 = _seed_branch_version(tmp_path, "b1")
        bvid2 = _seed_branch_version(tmp_path, "b2")
        _seed_goal(tmp_path, "g1", author="alice")

        set_canonical_branch(
            tmp_path, goal_id="g1", branch_version_id=bvid1, set_by="alice"
        )
        set_canonical_branch(
            tmp_path, goal_id="g1", branch_version_id=bvid2, set_by="alice"
        )

        from workflow.daemon_server import get_goal
        goal = get_goal(tmp_path, goal_id="g1")
        assert goal["canonical_branch_version_id"] == bvid2

        with _connect(tmp_path) as conn:
            rows = list(conn.execute(
                "SELECT branch_version_id FROM canonical_bindings "
                "WHERE goal_id = ? AND scope_token = ''",
                ("g1",),
            ))
        assert len(rows) == 1
        assert rows[0]["branch_version_id"] == bvid2

    def test_unset_canonical_removes_default_binding(self, tmp_path):
        """branch_version_id=None unsets BOTH legacy column AND deletes the
        default-scope canonical_bindings row."""
        bvid = _seed_branch_version(tmp_path, "b1")
        _seed_goal(tmp_path, "g1", author="alice")

        set_canonical_branch(
            tmp_path, goal_id="g1", branch_version_id=bvid, set_by="alice"
        )
        set_canonical_branch(
            tmp_path, goal_id="g1", branch_version_id=None, set_by="alice"
        )

        from workflow.daemon_server import get_goal
        goal = get_goal(tmp_path, goal_id="g1")
        assert goal["canonical_branch_version_id"] is None

        with _connect(tmp_path) as conn:
            rows = list(conn.execute(
                "SELECT * FROM canonical_bindings "
                "WHERE goal_id = ? AND scope_token = ''",
                ("g1",),
            ))
        assert rows == []

    def test_unset_does_not_touch_other_scopes(self, tmp_path):
        """Unsetting the default scope must NOT touch non-default scope rows."""
        bvid = _seed_branch_version(tmp_path, "b1")
        bvid2 = _seed_branch_version(tmp_path, "b2")
        _seed_goal(tmp_path, "g1", author="alice")

        # Set the default canonical (writes to both stores).
        set_canonical_branch(
            tmp_path, goal_id="g1", branch_version_id=bvid, set_by="alice"
        )
        # Manually insert a non-default-scope binding (simulates a future
        # user:mark variant added directly via the new table).
        with _connect(tmp_path) as conn:
            conn.execute(
                "INSERT INTO canonical_bindings "
                "(goal_id, scope_token, branch_version_id, "
                " bound_by_actor_id, bound_at, visibility) "
                "VALUES (?, 'user:mark', ?, 'mark', 1.0, 'public')",
                ("g1", bvid2),
            )

        # Unset the default — only the '' scope row should disappear.
        set_canonical_branch(
            tmp_path, goal_id="g1", branch_version_id=None, set_by="alice"
        )

        with _connect(tmp_path) as conn:
            rows = list(conn.execute(
                "SELECT scope_token, branch_version_id "
                "FROM canonical_bindings WHERE goal_id = ? "
                "ORDER BY scope_token",
                ("g1",),
            ))
        assert len(rows) == 1
        assert rows[0]["scope_token"] == "user:mark"
        assert rows[0]["branch_version_id"] == bvid2

    def test_set_canonical_invalid_branch_version_raises(self, tmp_path):
        """Validation runs BEFORE dual-write; invalid version_id raises and
        leaves both stores untouched."""
        _seed_goal(tmp_path, "g1", author="alice")

        with pytest.raises(ValueError, match="not found"):
            set_canonical_branch(
                tmp_path,
                goal_id="g1",
                branch_version_id="nonexistent-bvid",
                set_by="alice",
            )

        from workflow.daemon_server import get_goal
        goal = get_goal(tmp_path, goal_id="g1")
        assert goal["canonical_branch_version_id"] is None

        with _connect(tmp_path) as conn:
            rows = list(conn.execute(
                "SELECT * FROM canonical_bindings WHERE goal_id = ?",
                ("g1",),
            ))
        assert rows == []
